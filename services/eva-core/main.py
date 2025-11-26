import os
import google.generativeai as genai
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, File, UploadFile, Form  # <--- Add Form here
from fastapi import File, UploadFile
import io
from pypdf import PdfReader
from docx import Document
# 1. Load Environment Variables
load_dotenv()

# 2. Configure Gemini
# Get your key from https://aistudio.google.com/
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# 3. Configure Supabase
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"), 
    os.getenv("SUPABASE_KEY")
)

app = FastAPI(title="Gemini RAG Backend")

# --- Data Models ---

class DocumentIngest(BaseModel):
    tenant_id: str
    text: str
    metadata: dict = {}

class RAGQuery(BaseModel):
    tenant_id: str
    query: str

# --- Helper Function ---





def get_text_from_file(file: UploadFile) -> str:
    """Extracts text based on file extension."""
    content = file.file.read()
    filename = file.filename.lower()
    
    text = ""
    
    if filename.endswith(".pdf"):
        pdf = PdfReader(io.BytesIO(content))
        for page in pdf.pages:
            text += page.extract_text() + "\n"
            
    elif filename.endswith(".docx"):
        doc = Document(io.BytesIO(content))
        for para in doc.paragraphs:
            text += para.text + "\n"
            
    elif filename.endswith(".txt"):
        text = content.decode("utf-8")
        
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type. Use PDF, DOCX, or TXT.")
        
    return text

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> list[str]:
    """
    Splits text into smaller chunks so valid for embedding models.
    Simple sliding window approach.
    """
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        # Move forward, but keep some overlap context
        start += chunk_size - overlap
        
    return chunks






def get_gemini_embedding(text: str) -> list[float]:
    """
    Generates a 768-dimensional vector using Gemini.
    """
    try:
        # 'models/text-embedding-004' is the latest stable embedding model
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="retrieval_document", 
            title=None
        )
        return result['embedding']
    except Exception as e:
        print(f"Gemini Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate embedding from Gemini")

# --- Endpoints ---

@app.post("/ingest")
async def ingest_document(doc: DocumentIngest):
    """
    1. Receives text.
    2. Turns it into numbers (Vector) using Gemini.
    3. Saves it to Supabase.
    """
    # Generate Vector
    vector = get_gemini_embedding(doc.text)

    # Prepare Data
    data = {
        "tenant_id": doc.tenant_id,
        "text": doc.text,
        "embedding": vector,  # This is now a list of 768 floats
        "metadata": doc.metadata
    }
    
    # Insert to DB
    try:
        response = supabase.table("vector_records").insert(data).execute()
        return {"status": "success", "id": response.data[0]['id']}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat_with_rag(query: RAGQuery):
    """
    1. Receives user question.
    2. Turns question into numbers using Gemini.
    3. Finds most similar text in DB.
    """
    # Generate Query Vector
    # Note: We use task_type="retrieval_query" for the question part
    query_vector = genai.embed_content(
        model="models/text-embedding-004",
        content=query.query,
        task_type="retrieval_query"
    )['embedding']

    # Call Supabase RPC (Stored Procedure)
    rpc_params = {
        "query_embedding": query_vector,
        "match_threshold": 0.5, 
        "match_count": 5,
        "filter_tenant_id": query.tenant_id
    }
    
    try:
        response = supabase.rpc("match_vectors", rpc_params).execute()
        
        # --- BONUS: GENERATE ANSWER ---
        # Since we have Gemini, let's actually answer the question using the context!
        
        context_text = "\n".join([f"- {item['text']}" for item in response.data])
        
        prompt = f"""
        You are a helpful AI assistant. Answer the user's question using ONLY the context below.
        
        Context:
        {context_text}
        
        User Question: {query.query}
        """
        
        # Generate the final answer text
        model = genai.GenerativeModel('gemini-2.0-flash')
        chat_response = model.generate_content(prompt)
        
        return {
            "answer": chat_response.text,
            "sources": response.data  # Return sources so frontend can show "Reference: Doc A"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {"message": "API is running", "docs_url": "/docs"}



@app.post("/ingest/file")
#async def ingest_file(file: UploadFile = File(...), tenant_id: str = "default"):

@app.post("/ingest/file")
async def ingest_file(
    tenant_id: str = Form(...),  # <--- This fixes it!
    file: UploadFile = File(...)
):
    """
    Uploads a file (PDF, DOCX, TXT), chunks it, embeds it, and saves to DB.
    """
    try:
        # 1. Extract Text
        raw_text = get_text_from_file(file)
        if not raw_text.strip():
            raise HTTPException(status_code=400, detail="File is empty or text could not be extracted.")

        # 2. Chunk the Text (Critical Step!)
        text_chunks = chunk_text(raw_text)
        
        print(f"Processing {len(text_chunks)} chunks for {file.filename}...")

        # 3. Embed & Insert Loop
        # In production, you would do this in parallel (batch processing)
        inserted_ids = []
        
        for i, chunk in enumerate(text_chunks):
            vector = get_gemini_embedding(chunk)
            
            data = {
                "tenant_id": tenant_id,
                "text": chunk,
                "embedding": vector,
                "metadata": {
                    "filename": file.filename,
                    "chunk_index": i,
                    "total_chunks": len(text_chunks),
                    "type": "file_upload"
                }
            }
            
            response = supabase.table("vector_records").insert(data).execute()
            inserted_ids.append(response.data[0]['id'])

        return {
            "status": "success", 
            "filename": file.filename, 
            "chunks_processed": len(inserted_ids)
        }

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))