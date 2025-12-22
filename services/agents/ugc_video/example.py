"""
FastAPI Chat-based UGC Orchestrator with LangSmith Monitoring

Wraps the existing CrewAI UGC agent for continuous chat interaction
with comprehensive LangSmith tracing and monitoring
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
import os
import base64
import uuid
import json
import asyncio
from datetime import datetime
from dotenv import load_dotenv

# LangSmith imports
from langsmith import Client, traceable
from langsmith.wrappers import wrap_openai
import langsmith

# Import UGC orchestrator agent (true multi-tool intelligence)
from ugc_orchestrator_agent import generate_ugc_with_orchestrator

# Load environment variables
load_dotenv()

# Initialize LangSmith
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "ugc-orchestrator"
# Make sure to set LANGCHAIN_API_KEY in your .env file

langsmith_client = Client()

app = FastAPI(title="UGC Orchestrator API", version="1.0.0")

# Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store conversation history and generated images
conversations = {}
generated_images = {}

class ChatRequest(BaseModel):
    message: str
    person_image_path: Optional[str] = None
    product_image_path: Optional[str] = None
    conversation_id: Optional[str] = None

class ScriptRequest(BaseModel):
    ugc_image_path: str
    product_name: str
    tone: Optional[str] = "energetic and authentic"
    platform: Optional[str] = "Instagram"
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    conversation_id: str
    assistant_message: str
    steps: List[Dict]
    generated_images: Optional[List[str]] = None  # Changed to list for 4 images
    timestamp: str
    trace_url: Optional[str] = None  # Added for LangSmith trace URL

class ScriptResponse(BaseModel):
    conversation_id: str
    script: str
    ugc_image_path: str
    timestamp: str
    trace_url: Optional[str] = None

@app.get("/")
async def serve_frontend():
    """Serve the chatbox HTML frontend"""
    if os.path.exists("chatbox.html"):
        return FileResponse("chatbox.html")
    elif os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"message": "Frontend not found"}

@app.get("/old")
async def serve_old_frontend():
    """Serve the old grid-based HTML frontend"""
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"message": "Frontend not found"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "UGC Orchestrator API",
        "version": "1.0.0",
        "langsmith_enabled": os.getenv("LANGCHAIN_TRACING_V2") == "true"
    }

@traceable(
    name="chat_ugc_endpoint",
    tags=["fastapi", "ugc-generation"],
    metadata={"endpoint": "/chat/ugc"}
)
async def chat_ugc(request: ChatRequest):
    """Main chat endpoint - handles agent execution and image generation"""
    from ugc_orchestrator_agent import chat_with_agent
    
    conversation_id = request.conversation_id or str(uuid.uuid4())

    if conversation_id not in conversations:
        conversations[conversation_id] = []

    conversations[conversation_id].append({
        "role": "user",
        "message": request.message,
        "timestamp": datetime.now().isoformat()
    })

    run_tree = langsmith.get_current_run_tree()
    trace_url = None

    try:
        # Check if user wants to generate images (both images uploaded)
        if request.person_image_path and request.product_image_path:
            # Build image metadata
            image_metadata = {
                "person_image_uploaded": True,
                "product_image_uploaded": True,
            }

            if os.path.exists(request.person_image_path):
                image_metadata["person_image_size"] = os.path.getsize(request.person_image_path)
            if os.path.exists(request.product_image_path):
                image_metadata["product_image_size"] = os.path.getsize(request.product_image_path)

            # Track uploaded images
            with langsmith.trace(
                name="process_uploaded_images",
                inputs={
                    "person_image": request.person_image_path,
                    "product_image": request.product_image_path
                },
                tags=["image-upload"],
                metadata=image_metadata
            ) as image_trace:
                image_trace.outputs = {"status": "images_processed"}

            # Use agent orchestrator to generate 4 images
            print(f"\n{'='*60}")
            print(f"Processing UGC generation: {conversation_id}")
            print(f"User message: {request.message}")
            print(f"{'='*60}\n")
            
            with langsmith.trace(
                name="agent_orchestration",
                inputs={"message": request.message, "conversation_id": conversation_id},
                tags=["agent-execution", "multi-tool"]
            ) as agent_trace:
                result = generate_ugc_with_orchestrator(
                    person_image_path=request.person_image_path,
                    product_image_path=request.product_image_path,
                    base_intent=request.message
                )
                agent_trace.outputs = {"result": str(result)}
            
            assistant_message = str(result)
        else:
            # No images or partial images - use chat agent
            print(f"\n{'='*60}")
            print(f"Processing chat: {conversation_id}")
            print(f"User message: {request.message}")
            print(f"{'='*60}\n")
            
            with langsmith.trace(
                name="chat_agent",
                inputs={"message": request.message, "conversation_id": conversation_id},
                tags=["agent-execution", "chat"]
            ) as chat_trace:
                result = chat_with_agent(request.message)
                chat_trace.outputs = {"result": str(result)}
            
            assistant_message = str(result)
        
        steps = []

        # Handle multiple generated images (4 images)
        generated_image_list = []
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        print(f"\n{'='*60}")
        print("Checking for generated images...")
        print(f"{'='*60}")
        
        for i in range(1, 5):  # Check for 4 images
            original_filename = f"generated_ugc_image_{i}.png"
            print(f"Looking for: {original_filename}")
            
            if os.path.exists(original_filename):
                # Rename with conversation ID
                new_filename = f"ugc_{conversation_id}_{timestamp_str}_{i}.png"
                os.rename(original_filename, new_filename)
                generated_image_list.append(new_filename)
                print(f"✅ Found and renamed to: {new_filename}")
                
                # Build metadata
                image_size = os.path.getsize(new_filename)
                image_save_metadata = {
                    "filename": new_filename,
                    "size_bytes": image_size,
                    "conversation_id": conversation_id,
                    "variant_index": i
                }
                
                # Create trace with metadata
                with langsmith.trace(
                    name=f"save_generated_image_{i}",
                    tags=["image-output", "ugc-generation", f"variant-{i}"],
                    metadata=image_save_metadata
                ) as save_trace:
                    save_trace.outputs = {"image_path": new_filename}
            else:
                print(f"❌ Not found: {original_filename}")
        
        print(f"\nTotal images found: {len(generated_image_list)}")
        print(f"{'='*60}\n")
        
        # Store all generated images for this conversation
        if generated_image_list:
            generated_images[conversation_id] = generated_image_list
            
            # Log feedback
            try:
                if run_tree and run_tree.id:
                    langsmith_client.create_feedback(
                        run_tree.id,
                        key="images_generated",
                        score=1.0,
                        comment=f"{len(generated_image_list)} images generated: {', '.join(generated_image_list)}"
                    )
            except Exception as e:
                print(f"Failed to log feedback: {e}")

        steps.append({
            "type": "agent_thinking",
            "description": "GPT-5 agent analyzed the request",
            "timestamp": datetime.now().isoformat()
        })

        if "Success" in assistant_message and "generated_ugc_image" in assistant_message:
            steps.append({
                "type": "tool_call",
                "tool": "Multi Banana UGC Image Generator",
                "description": f"Generated {len(generated_image_list)} diverse UGC images using nano-banana-pro-edit model",
                "timestamp": datetime.now().isoformat()
            })

        conversations[conversation_id].append({
            "role": "assistant",
            "message": assistant_message,
            "timestamp": datetime.now().isoformat()
        })

        # Get trace URL
        if run_tree and run_tree.id:
            try:
                tenant_id = langsmith_client._get_tenant_id()
                project_name = os.getenv("LANGCHAIN_PROJECT", "ugc-orchestrator")
                trace_url = f"https://smith.langchain.com/o/{tenant_id}/projects/p/{project_name}/r/{run_tree.id}"
            except Exception as e:
                print(f"Could not generate trace URL: {e}")
                trace_url = None

        return ChatResponse(
            conversation_id=conversation_id,
            assistant_message=assistant_message,
            steps=steps,
            generated_images=generated_image_list if generated_image_list else None,
            timestamp=datetime.now().isoformat(),
            trace_url=trace_url
        )

    except Exception as e:
        print(f"Error in chat_ugc: {str(e)}")
        if run_tree and run_tree.id:
            langsmith_client.create_feedback(
                run_tree.id,
                key="error",
                score=0.0,
                comment=f"Error: {str(e)}"
            )
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")


@traceable(name="chat_ugc_upload_endpoint", tags=["fastapi", "file-upload"])
async def chat_ugc_with_upload(
    message: str = Form(...),
    person_image: Optional[UploadFile] = File(None),
    product_image: Optional[UploadFile] = File(None),
    conversation_id: Optional[str] = Form(None)
):
    """Upload wrapper - just saves files and calls chat_ugc()"""
    person_image_path = None
    product_image_path = None

    # Prepare metadata
    upload_metadata = {}

    if person_image:
        person_image_path = f"temp_person_{uuid.uuid4()}.jpg"
        content = await person_image.read()
        with open(person_image_path, "wb") as f:
            f.write(content)
        upload_metadata["person_image"] = {
            "filename": person_image.filename,
            "size": len(content),
            "path": person_image_path
        }

    if product_image:
        product_image_path = f"temp_product_{uuid.uuid4()}.jpg"
        content = await product_image.read()
        with open(product_image_path, "wb") as f:
            f.write(content)
        upload_metadata["product_image"] = {
            "filename": product_image.filename,
            "size": len(content),
            "path": product_image_path
        }

    # Log upload
    with langsmith.trace(
        name="save_uploaded_files", 
        tags=["file-upload"],
        metadata=upload_metadata
    ) as upload_trace:
        upload_trace.outputs = {"status": "files_saved"}

    # Create request
    request = ChatRequest(
        message=message,
        person_image_path=person_image_path,
        product_image_path=product_image_path,
        conversation_id=conversation_id
    )

    # ✅ JUST CALL chat_ugc() - it handles everything else
    response = await chat_ugc(request)

    # Clean up temp files
    if person_image_path and os.path.exists(person_image_path):
        os.remove(person_image_path)
    if product_image_path and os.path.exists(product_image_path):
        os.remove(product_image_path)

    # ✅ NO IMAGE HANDLING HERE - just return the response
    return response



@app.post("/chat/ugc/upload", response_model=ChatResponse)
async def chat_ugc_upload_endpoint(
    message: str = Form(...),
    person_image: Optional[UploadFile] = File(None),
    product_image: Optional[UploadFile] = File(None),
    conversation_id: Optional[str] = Form(None)
):
    """Wrapper endpoint"""
    return await chat_ugc_with_upload(message, person_image, product_image, conversation_id)

@app.post("/chat/ugc/upload/simple")
async def chat_ugc_upload_simple(
    message: str = Form(...),
    person_image: Optional[UploadFile] = File(None),
    product_image: Optional[UploadFile] = File(None),
    conversation_id: Optional[str] = Form(None)
):
    """Simple endpoint - just run and return results"""
    return await chat_ugc_with_upload(message, person_image, product_image, conversation_id)

@app.get("/image/{filename}")
async def get_image(filename: str):
    """
    Retrieve a generated image by filename
    """
    if not os.path.exists(filename):
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(filename, media_type="image/png")

@app.get("/conversation/{conversation_id}")
async def get_conversation(conversation_id: str):
    """
    Retrieve conversation history
    """
    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {
        "conversation_id": conversation_id,
        "messages": conversations[conversation_id],
        "generated_image": generated_images.get(conversation_id)
    }

@app.delete("/conversation/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """
    Delete conversation history
    """
    if conversation_id in conversations:
        del conversations[conversation_id]

    if conversation_id in generated_images:
        image_file = generated_images[conversation_id]
        if os.path.exists(image_file):
            os.remove(image_file)
        del generated_images[conversation_id]

    return {"status": "deleted", "conversation_id": conversation_id}

class ScriptVideoResponse(BaseModel):
    conversation_id: str
    script: str
    video_url: Optional[str] = None
    ugc_image_path: str
    timestamp: str
    trace_url: Optional[str] = None

@app.post("/chat/ugc/script", response_model=ScriptVideoResponse)
@traceable(
    name="generate_script_and_video_endpoint",
    tags=["fastapi", "script-generation", "video-generation"],
    metadata={"endpoint": "/chat/ugc/script"}
)
async def generate_script_and_video(request: ScriptRequest):
    """
    Generate UGC video script and video for a selected image (2-agent sequential workflow)
    """
    from crewai import Task, Crew
    from script_agent import create_script_agent
    from video_agent import create_video_agent
    
    conversation_id = request.conversation_id or str(uuid.uuid4())
    
    if conversation_id not in conversations:
        conversations[conversation_id] = []
    
    # Add user request to conversation
    conversations[conversation_id].append({
        "role": "user",
        "message": f"Generate video script and video for {request.ugc_image_path}",
        "timestamp": datetime.now().isoformat()
    })
    
    run_tree = langsmith.get_current_run_tree()
    trace_url = None
    
    try:
        # Validate image exists
        if not os.path.exists(request.ugc_image_path):
            raise HTTPException(status_code=404, detail=f"Image not found: {request.ugc_image_path}")
        
        print(f"\n{'='*60}")
        print(f"Starting Script → Video Workflow")
        print(f"Image: {request.ugc_image_path}")
        print(f"Product: {request.product_name}")
        print(f"Tone: {request.tone}")
        print(f"Platform: {request.platform}")
        print(f"{'='*60}\n")
        
        # Create both agents
        with langsmith.trace(
            name="create_script_video_agents",
            tags=["agent-creation"]
        ) as agent_trace:
            script_agent = create_script_agent()
            video_agent = create_video_agent()
            agent_trace.outputs = {"agents": ["ScriptAgent", "VideoAgent"]}
        
        # Task 1: Generate script
        with langsmith.trace(
            name="create_script_task",
            inputs={
                "ugc_image": request.ugc_image_path,
                "product_name": request.product_name,
                "tone": request.tone,
                "platform": request.platform
            },
            tags=["task-creation", "script-generation"]
        ) as task_trace:
            task1 = Task(
                description=f"""Generate an 8-second UGC video script.

Call the "UGC Script Maker" tool with these parameters:
- ugc_image_reference: {request.ugc_image_path}
- product_name: {request.product_name}
- tone: {request.tone}
- platform: {request.platform}

Return the complete script.""",
                expected_output="Complete 8-second UGC video script",
                agent=script_agent,
                human_input=False
            )
            task_trace.outputs = {"task": "script_generation"}
        
        # Task 2: Generate video (depends on Task 1)
        with langsmith.trace(
            name="create_video_task",
            inputs={
                "ugc_image": request.ugc_image_path,
                "duration": 8
            },
            tags=["task-creation", "video-generation"]
        ) as task2_trace:
            task2 = Task(
                description=f"""Generate a UGC video using Veo-3.1.

The previous task generated a script. Use that script to create the video.

Call the "Veo3.1 Image-to-Video Generator" tool with:
- image_reference: {request.ugc_image_path}
- script_text: [Use the script from the previous task]
- duration_seconds: 8

Wait for the video generation to complete and return the video URL.""",
                expected_output="Video URL from Veo-3.1 generation",
                agent=video_agent,
                human_input=False,
                context=[task1]  # Task 2 depends on Task 1
            )
            task2_trace.outputs = {"task": "video_generation"}
        
        # Execute crew with sequential tasks
        with langsmith.trace(
            name="execute_script_video_crew",
            tags=["crew-execution", "sequential", "script-video"],
            metadata={"agents": 2, "tasks": 2, "workflow": "sequential"}
        ) as crew_trace:
            crew = Crew(
                agents=[script_agent, video_agent],
                tasks=[task1, task2],  # Sequential: script → video
                verbose=True,
                process="sequential",
                full_output=False
            )
            
            import time
            start_time = time.time()
            
            print("\n" + "="*60)
            print("Starting 2-Agent Sequential Workflow")
            print("Agent 1: Script Generator → Agent 2: Video Generator")
            print("="*60 + "\n")
            
            result = crew.kickoff()
            execution_time = time.time() - start_time
            
            crew_trace.metadata["execution_time_seconds"] = round(execution_time, 2)
            crew_trace.outputs = {"result": str(result)}
            
            print(f"\n{'='*60}")
            print(f"Script + Video workflow completed in {execution_time:.2f} seconds")
            print(f"{'='*60}\n")
        
        # Parse result to extract script and video URL
        result_str = str(result)
        
        # The result will contain both script and video info
        # We need to extract them properly
        script = ""
        video_url = None
        
        # Extract video URL if present
        if "Video generated successfully:" in result_str or "✅ Video generated successfully:" in result_str:
            # Split on the success message
            if "✅ Video generated successfully:" in result_str:
                parts = result_str.split("✅ Video generated successfully:")
            else:
                parts = result_str.split("Video generated successfully:")
            
            if len(parts) > 1:
                # Extract URL (should be the next word/line)
                url_part = parts[1].strip()
                # Remove completion signal if present
                url_part = url_part.split("[VIDEO_GENERATION_COMPLETE]")[0].strip()
                # Get first line or first space-separated token
                video_url = url_part.split()[0] if url_part else None
                
                # Script is everything before the video message
                script = parts[0].strip()
        else:
            # No video URL found, entire result is the script
            script = result_str
        
        print(f"\n{'='*60}")
        print("📊 Workflow Results:")
        print(f"{'='*60}")
        print(f"Script Length: {len(script)} characters")
        print(f"Video URL: {video_url if video_url else 'Not generated'}")
        print(f"{'='*60}\n")
        
        # Add to conversation
        conversations[conversation_id].append({
            "role": "assistant",
            "message": f"Generated script and video for {request.ugc_image_path}",
            "script": script,
            "video_url": video_url,
            "timestamp": datetime.now().isoformat()
        })
        
        # Get trace URL
        if run_tree and run_tree.id:
            try:
                tenant_id = langsmith_client._get_tenant_id()
                project_name = os.getenv("LANGCHAIN_PROJECT", "ugc-orchestrator")
                trace_url = f"https://smith.langchain.com/o/{tenant_id}/projects/p/{project_name}/r/{run_tree.id}"
            except Exception as e:
                print(f"Could not generate trace URL: {e}")
                trace_url = None
        
        return ScriptVideoResponse(
            conversation_id=conversation_id,
            script=script,
            video_url=video_url,
            ugc_image_path=request.ugc_image_path,
            timestamp=datetime.now().isoformat(),
            trace_url=trace_url
        )
        
    except Exception as e:
        print(f"Error generating script/video: {str(e)}")
        if run_tree and run_tree.id:
            langsmith_client.create_feedback(
                run_tree.id,
                key="error",
                score=0.0,
                comment=f"Error: {str(e)}"
            )
        raise HTTPException(status_code=500, detail=f"Error generating script/video: {str(e)}")

@app.post("/feedback/{conversation_id}")
async def submit_feedback(
    conversation_id: str,
    feedback_type: str,  # "thumbs_up" or "thumbs_down"
    run_id: Optional[str] = None,
    comment: Optional[str] = None
):
    """
    Submit user feedback for a conversation
    """
    try:
        if not run_id:
            return {"status": "error", "message": "run_id required"}

        score = 1.0 if feedback_type == "thumbs_up" else 0.0

        langsmith_client.create_feedback(
            run_id,
            key=feedback_type,
            score=score,
            comment=comment
        )

        return {
            "status": "success",
            "conversation_id": conversation_id,
            "feedback_type": feedback_type
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error submitting feedback: {str(e)}")

if __name__ == "__main__":
    import uvicorn

    print("\n" + "="*60)
    print("🚀 Starting UGC Orchestrator API Server")
    print("="*60)
    print("📡 Endpoint: http://localhost:8000/chat/ugc")
    print("📚 Docs: http://localhost:8000/docs")
    print("🔍 LangSmith Tracing:", os.getenv("LANGCHAIN_TRACING_V2", "false"))
    print("📊 Project:", os.getenv("LANGCHAIN_PROJECT", "ugc-orchestrator"))
    print("="*60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)


"""
UGC Orchestrator with 2-Agent Sequential Workflow
Agent 1: Prompt Variator → Agent 2: Image Generator
"""
from crewai import Agent, Task, Crew, LLM
from prompt_agent import create_prompt_agent
from image_generator_agent import create_image_generator_agent
from dotenv import load_dotenv
import os
import langsmith
from langsmith import traceable

# Load environment variables
load_dotenv()

# Initialize LangSmith tracing
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "ugc-orchestrator")

@traceable(
    name="create_chat_agent",
    tags=["agent-creation", "crewai", "chat"],
    metadata={"model": "gpt-5-2025-08-07", "provider": "aiml-api", "mode": "chat"}
)
def create_chat_agent():
    """
    Create a conversational agent for general chat without tools
    """
    with langsmith.trace(
        name="configure_chat_llm",
        tags=["llm-configuration", "gpt-5", "chat"]
    ) as llm_trace:
        llm = LLM(
            model="openai/gpt-5-2025-08-07",
            api_key=os.getenv("AIML_API_KEY"),
            base_url="https://api.aimlapi.com/v1",
            temperature=0.7
        )
        llm_trace.outputs = {"llm": "openai/gpt-5-2025-08-07"}

    agent = Agent(
        role="UGC AI Assistant",
        goal="Help users understand UGC generation capabilities and answer their questions",
        backstory="""You are a friendly AI assistant specializing in User-Generated Content (UGC) image creation.

Your capabilities:
- Generate 4 diverse UGC images when users upload a person image and a product image
- Use advanced AI models (nano-banana-pro-edit) for realistic image composition
- Create variations with different poses, angles, and styles
- Provide guidance on how to use the UGC generation system

When users ask what you can do, explain:
1. You can generate authentic-looking UGC images by combining a person photo with a product photo
2. You create 4 different variants for variety
3. Users need to upload both a person image and a product image to generate UGC
4. You can also chat and answer questions about the system

Be helpful, friendly, and informative. If users haven't uploaded images yet, encourage them to do so to try the UGC generation.""",
        tools=[],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=3
    )

    return agent

@traceable(
    name="chat_with_agent",
    tags=["chat", "conversation"],
    metadata={"mode": "general-chat"}
)
def chat_with_agent(message: str):
    """
    Handle general chat without image generation
    """
    agent = create_chat_agent()
    
    task = Task(
        description=f"""Respond to the user's message: "{message}"
        
Be helpful and informative. If they ask what you can do, explain your UGC generation capabilities.""",
        expected_output="A helpful response to the user's message",
        agent=agent,
        human_input=False
    )
    
    crew = Crew(
        agents=[agent],
        tasks=[task],
        verbose=True,
        max_iter=3,
        full_output=False
    )
    
    result = crew.kickoff()
    return result

@traceable(
    name="create_chat_agent",
    tags=["agent-creation", "crewai", "chat"],
    metadata={"model": "gpt-5-2025-08-07", "provider": "aiml-api", "mode": "chat"}
)
def create_chat_agent():
    """
    Create a conversational agent for general chat without tools
    """
    with langsmith.trace(
        name="configure_chat_llm",
        tags=["llm-configuration", "gpt-5", "chat"]
    ) as llm_trace:
        llm = LLM(
            model="openai/gpt-5-2025-08-07",
            api_key=os.getenv("AIML_API_KEY"),
            base_url="https://api.aimlapi.com/v1",
            temperature=0.7
        )
        llm_trace.outputs = {"llm": "openai/gpt-5-2025-08-07"}

    agent = Agent(
        role="UGC AI Assistant",
        goal="Help users understand UGC generation capabilities and answer their questions",
        backstory="""You are a friendly AI assistant specializing in User-Generated Content (UGC) image creation.

Your capabilities:
- Generate 4 diverse UGC images when users upload a person image and a product image
- Use advanced AI models (nano-banana-pro-edit) for realistic image composition
- Create variations with different poses, angles, and styles
- Provide guidance on how to use the UGC generation system

When users ask what you can do, explain:
1. You can generate authentic-looking UGC images by combining a person photo with a product photo
2. You create 4 different variants for variety
3. Users need to upload both a person image and a product image to generate UGC
4. You can also chat and answer questions about the system

Be helpful, friendly, and informative. If users haven't uploaded images yet, encourage them to do so to try the UGC generation.""",
        tools=[],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=3
    )

    return agent

@traceable(
    name="chat_with_agent",
    tags=["chat", "conversation"],
    metadata={"mode": "general-chat"}
)
def chat_with_agent(message: str):
    """
    Handle general chat without image generation
    """
    agent = create_chat_agent()
    
    task = Task(
        description=f"""Respond to the user's message: "{message}"
        
Be helpful and informative. If they ask what you can do, explain your UGC generation capabilities.""",
        expected_output="A helpful response to the user's message",
        agent=agent,
        human_input=False
    )
    
    crew = Crew(
        agents=[agent],
        tasks=[task],
        verbose=True,
        max_iter=3,
        full_output=False
    )
    
    result = crew.kickoff()
    return result

@traceable(
    name="generate_ugc_with_orchestrator",
    tags=["multi-agent-orchestration", "ugc", "end-to-end"],
    metadata={"workflow": "2-agent-sequential", "expected_images": 4}
)
def generate_ugc_with_orchestrator(
    person_image_path: str,
    product_image_path: str,
    base_intent: str = None
):
    """
    Generate 4 diverse UGC images using 2-agent sequential workflow.
    
    Workflow:
    1. Agent 1 (Prompt Variator) generates 4 prompts
    2. Agent 2 (Image Generator) generates 4 images
    
    Args:
        person_image_path: Path to the person image
        product_image_path: Path to the product image
        base_intent: Base intent for image generation
    
    Returns:
        Result with confirmation of all 4 generated images
    """
    with langsmith.trace(
        name="validate_inputs",
        inputs={
            "person_image_path": person_image_path,
            "product_image_path": product_image_path,
            "base_intent": base_intent
        },
        tags=["validation"]
    ) as validate_trace:
        if not os.path.exists(person_image_path):
            error_msg = f"Person image not found: {person_image_path}"
            validate_trace.outputs = {"error": error_msg}
            return error_msg

        if not os.path.exists(product_image_path):
            error_msg = f"Product image not found: {product_image_path}"
            validate_trace.outputs = {"error": error_msg}
            return error_msg

        if not base_intent:
            base_intent = "A person showcasing a product in a natural, engaging way"

        validate_trace.outputs = {"status": "validated"}

    # Create both agents
    with langsmith.trace(
        name="create_agents",
        tags=["agent-creation"]
    ) as agent_trace:
        prompt_agent = create_prompt_agent()
        image_agent = create_image_generator_agent()
        agent_trace.outputs = {"agents": ["PromptAgent", "ImageGeneratorAgent"]}

    # Create Task 1: Generate 4 prompts
    with langsmith.trace(
        name="create_prompt_task",
        inputs={"base_intent": base_intent},
        tags=["task-creation", "prompt-generation"]
    ) as task1_trace:
        task1 = Task(
            description=f"""Generate 4 diverse UGC prompts.

Base intent: "{base_intent}"

Call the "UGC Prompt Variator" tool ONCE with this base_intent.
The tool will return 4 prompts. 

After receiving the prompts, your task is complete. Output the 4 prompts clearly.""",
            expected_output="4 diverse UGC prompts clearly listed and numbered 1-4",
            agent=prompt_agent,
            human_input=False
        )
        task1_trace.outputs = {"task": "prompt_generation"}

    # Create Task 2: Generate 4 images (depends on Task 1)
    with langsmith.trace(
        name="create_image_task",
        inputs={
            "person_image": person_image_path,
            "product_image": product_image_path
        },
        tags=["task-creation", "image-generation"]
    ) as task2_trace:
        task2 = Task(
            description=f"""The previous task provided 4 prompts. You must generate 4 images, one for each prompt.

Person image: {person_image_path}
Product image: {product_image_path}

Your task is to make 4 separate tool calls. After each successful call, move to the next one.

STEP 1: Generate first image
- Use the FIRST prompt from the previous task
- Set output_filename to "generated_ugc_image_1.png"
- Wait for success confirmation

STEP 2: Generate second image  
- Use the SECOND prompt from the previous task
- Set output_filename to "generated_ugc_image_2.png"
- Wait for success confirmation

STEP 3: Generate third image
- Use the THIRD prompt from the previous task
- Set output_filename to "generated_ugc_image_3.png"
- Wait for success confirmation

STEP 4: Generate fourth image
- Use the FOURTH prompt from the previous task
- Set output_filename to "generated_ugc_image_4.png"
- Wait for success confirmation

After completing all 4 steps, report: "Successfully generated 4 images: generated_ugc_image_1.png, generated_ugc_image_2.png, generated_ugc_image_3.png, generated_ugc_image_4.png"

CRITICAL: The output_filename MUST change for each call (1, 2, 3, 4). Do not repeat filenames.""",
            expected_output="Confirmation message listing all 4 generated image files",
            agent=image_agent,
            human_input=False,
            context=[task1]  # Task 2 depends on Task 1 output
        )
        task2_trace.outputs = {"task": "image_generation"}

    # Execute crew with sequential tasks
    with langsmith.trace(
        name="execute_crew",
        tags=["crew-execution", "crewai", "sequential"],
        metadata={"agents": 2, "tasks": 2, "workflow": "sequential", "expected_images": 4}
    ) as crew_trace:
        crew = Crew(
            agents=[prompt_agent, image_agent],
            tasks=[task1, task2],  # Sequential: task1 → task2
            verbose=True,
            process="sequential",  # Enforce sequential execution
            full_output=False
        )

        import time
        start_time = time.time()
        
        print("\n" + "="*60)
        print("Starting 2-Agent Sequential Workflow")
        print("Agent 1: Prompt Variator → Agent 2: Image Generator")
        print("="*60 + "\n")
        
        result = crew.kickoff()
        execution_time = time.time() - start_time

        crew_trace.metadata["execution_time_seconds"] = round(execution_time, 2)
        crew_trace.outputs = {"result": str(result)}
        
        print("\n" + "="*60)
        print(f"2-Agent workflow completed in {execution_time:.2f} seconds")
        print("="*60 + "\n")

    return result

if __name__ == "__main__":
    print("="*60)
    print("UGC Orchestrator Agent - Multi-Tool Intelligence")
    print("="*60)

    result = generate_ugc_with_orchestrator(
        person_image_path="person.jpg",
        product_image_path="product.jpg",
        base_intent="A happy person holding and showing off the product to the camera"
    )

    print("\n" + "="*60)
    print("Orchestration Result:")
    print("="*60)
    print(result)

"""
UGC Script Maker Tool for CrewAI
Generates Veo-3-compatible 8-second video scripts using GPT-5.2
"""

import os
from typing import Type, Optional
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class UGCScriptMakerInput(BaseModel):
    """Input schema for UGC Script Maker Tool."""
    ugc_image_reference: str = Field(
        ...,
        description="Path or URL to the UGC image reference"
    )
    product_name: str = Field(
        ...,
        description="Name of the product to feature in the video"
    )
    tone: str = Field(
        ...,
        description="Desired tone for the video (e.g., energetic, calm, professional, playful)"
    )
    platform: str = Field(
        ...,
        description="Target platform for the video (e.g., TikTok, Instagram, YouTube Shorts)"
    )


class UGCScriptMakerTool(BaseTool):
    name: str = "UGC Script Maker"
    description: str = (
        "Generates a highly detailed, Veo-3-compatible 8-second video script "
        "based on a selected UGC image."
    )
    args_schema: Type[BaseModel] = UGCScriptMakerInput
    cache_function: bool = False
    
    def _run(
        self,
        ugc_image_reference: str,
        product_name: str,
        tone: str,
        platform: str
    ) -> str:
        """
        Generate an 8-second video script optimized for Veo 3.
        
        Args:
            ugc_image_reference: Path or URL to the UGC image
            product_name: Name of the product
            tone: Desired tone for the video
            platform: Target platform
            
        Returns:
            Structured 8-second video script
        """
        # Initialize OpenAI client with AI/ML API
        api_key = os.getenv("AIML_API_KEY")
        if not api_key:
            return "Error: AIML_API_KEY environment variable not set"
        
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.aimlapi.com/v1"
        )
        
        # System prompt for GPT-5.2
        system_prompt = '''You are a professional UGC commercial video director and script supervisor.

Your task:
- Generate a SINGLE, production-ready video script optimized for Veo 3
- The script must feel like authentic creator-made UGC, not a polished advertisement
- The script must strictly follow the output format below
- Output ONLY the script, no explanations, no markdown

GLOBAL RULES (CRITICAL):
- Assume the person, face, clothing, hair, and environment come directly from the provided UGC image reference
- Do NOT invent new identities, outfits, locations, props, or backgrounds
- The video is ALWAYS silent (no speech audio, no music, no ambient sound, no captions)
- Lip motion may be present but is visual-only
- The product must NEVER approach the mouth or face
- No sipping, no pretending to drink
- Everything described must be physically filmable

PLATFORM & FORMAT RULES:
- Default format: Vertical 9:16 (Instagram Stories / Reels)
- Respect Instagram safe areas (avoid extreme top and bottom edges)
- Duration must match the requested duration exactly

LIP MOTION CONSTRAINT (MANDATORY):
- Subtle, continuous speech-mimicking lip motion must persist from 0 seconds through the final frame
- Lip motion must NOT stop, pause, or freeze at any point, including the ending frame
- Lip motion continues even if body, camera, or product motion settles

PRODUCT VISIBILITY & TEXT SAFETY (MANDATORY):
- The product must NEVER be fully visible
- Only a partial section of the product may appear in frame at any time
- Fingers, framing, angle, and/or crop must naturally obscure fine printed text, nutrition labels, and barcodes
- Only brand colors and a partial logo may be visible
- Never request readable fine print

PRODUCT HANDLING RULES:
- Product stays at chest or torso level
- Grip must look relaxed and natural
- Product handling must feel casual, not deliberately showcased

CAMERA & MOTION STYLE:
- Medium close-up unless specified otherwise
- Subtle handheld realism
- Gentle push-in or static framing only
- No fast pans, no aggressive movement

CLIP CHAINING RULES (IMPORTANT):
- The ending frame may become more stable to allow seamless continuation into the next clip
- Product motion may settle near the end
- Lip motion must still continue through the final frame

EXPRESSION & PERFORMANCE:
- Energetic but natural creator demeanor
- No exaggerated facial expressions
- No wide smiles, laughter, or comedic acting
- Eye contact with the camera should feel confident and intentional

OUTPUT FORMAT (STRICT — FOLLOW EXACTLY):

FORMAT:
DURATION:
OUTPUT CONSTRAINT:
SCENE:
CAMERA:
SUBJECT:
ACTION TIMELINE:
  0–2s:
  2–4s:
  4–6s:
  6–8s:
PRODUCT HANDLING CONSTRAINT:
PRODUCT VISIBILITY:
DEPTH OF FIELD:
SUBTLE MOTION:
ENVIRONMENT:
LIGHTING:
MOTION DETAILS:
ENDING FRAME:

'''
        
        # User prompt with context
        user_prompt = f"""Generate an 8-second video script with the following parameters:

UGC Image Reference: {ugc_image_reference}
Product Name: {product_name}
Tone: {tone}
Platform: {platform}

Use the visual identity from the UGC image reference. Create a script that showcases the product naturally and authentically."""
        
        try:
            # Call GPT-5.2 via AI/ML API
            response = client.chat.completions.create(
                model="openai/gpt-5-2",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.4
            )
            
            script = response.choices[0].message.content
            return script
            
        except Exception as e:
            return f"Error generating script: {str(e)}"


# Example usage
if __name__ == "__main__":
    tool = UGCScriptMakerTool()
    
    result = tool._run(
        ugc_image_reference="ugc_fb54f3f9-aefa-474d-b6ac-9f82a41145a4_20251214_121128.png",
        product_name="starbucks coffe",
        tone="calm",
        platform="instagram stories"
    )
    
    print(result)

"""
Veo-3.1 Image-to-Video Generator Tool for CrewAI
Converts: (image + script) -> Veo-3.1 Image-to-Video output
"""

import os
import base64
import time
import requests
from typing import Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from dotenv import load_dotenv

# Load .env variables
load_dotenv()


class Veo3VideoMakerInput(BaseModel):
    """Input schema for Veo3 Video Generator."""
    image_reference: str = Field(
        ...,
        description="URL or local path to reference image for Veo-3 video conditioning"
    )
    script_text: str = Field(
        ...,
        description="The final structured script to turn into a video"
    )
    duration_seconds: int = Field(
        default=8,
        description="Desired video duration (default 8 seconds)"
    )


class Veo3VideoMakerTool(BaseTool):
    name: str = "Veo3.1 Image-to-Video Generator"
    description: str = (
        "Converts a script + reference image into a generated video using "
        "Google Veo-3.1 Image-to-Video API."
    )
    args_schema: Type[BaseModel] = Veo3VideoMakerInput
    cache_function: bool = False

    def _get_image_url(self, path_or_url: str) -> str:
        """Converts local image to base64 data URI or returns URL directly."""
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            return path_or_url
        
        # Read local file and convert to base64 data URI
        try:
            with open(path_or_url, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")
            
            # Determine MIME type from extension
            ext = path_or_url.lower().split('.')[-1]
            mime_map = {
                'png': 'image/png',
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'gif': 'image/gif',
                'webp': 'image/webp'
            }
            mime_type = mime_map.get(ext, 'image/png')
            
            return f"data:{mime_type};base64,{image_data}"
        except Exception as e:
            raise Exception(f"Error reading local image file: {str(e)}")

    def _run(self, image_reference: str, script_text: str, duration_seconds: int) -> str:
        """Generate Veo-3.1 video from image + script."""

        api_key = os.getenv("AIML_API_KEY")
        if not api_key:
            return "Error: AIML_API_KEY environment variable not set"

        base_url = "https://api.aimlapi.com/v2"
        
        # Get image URL (converts local files to base64 data URI)
        try:
            image_url = self._get_image_url(image_reference)
        except Exception as e:
            return f"Error processing image: {str(e)}"

        # Step 1: Create video generation task
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "google/veo-3.1-i2v",
            "prompt": script_text,
            "image_url": image_url,
            "duration": duration_seconds,
            "aspect_ratio": "9:16",
            "resolution": "1080p",
            "generate_audio": False
        }

        try:
            # Submit generation request
            response = requests.post(
                f"{base_url}/video/generations",
                json=payload,
                headers=headers
            )
            
            if response.status_code >= 400:
                return f"Error submitting video generation: {response.status_code} - {response.text}"
            
            response_data = response.json()
            generation_id = response_data.get("id")
            
            if not generation_id:
                return f"Error: No generation ID returned. Response: {response_data}"
            
            print(f"Video generation started. ID: {generation_id}")
            
            # Step 2: Poll for completion
            timeout = 300  # 5 minutes timeout
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                check_response = requests.get(
                    f"{base_url}/video/generations",
                    params={"generation_id": generation_id},
                    headers=headers
                )
                
                if check_response.status_code >= 400:
                    return f"Error checking status: {check_response.status_code} - {check_response.text}"
                
                result = check_response.json()
                status = result.get("status")
                
                print(f"Status: {status}")
                
                if status == "completed":
                    video_url = result.get("video", {}).get("url")
                    if video_url:
                        return f"✅ Video generated successfully: {video_url}\n\n[VIDEO_GENERATION_COMPLETE] - Task finished."
                    return f"Video completed but no URL found. Response: {result}"
                
                elif status == "failed":
                    error = result.get("error", "Unknown error")
                    return f"Video generation failed: {error}"
                
                elif status in ["waiting", "active", "queued", "generating"]:
                    time.sleep(10)
                else:
                    return f"Unknown status: {status}. Response: {result}"
            
            return f"Timeout: Video generation took longer than {timeout} seconds. Generation ID: {generation_id}"

        except Exception as e:
            return f"Error generating Veo-3.1 video: {str(e)}"


# Example direct run
if __name__ == "__main__":
    tool = Veo3VideoMakerTool()
    
    result = tool._run(
        image_reference="ugc_fb54f3f9-aefa-474d-b6ac-9f82a41145a4_20251214_121128.png",
        script_text='''FORMAT:
Vertical 9:16 (Instagram Stories)

DURATION:
8 seconds

OUTPUT CONSTRAINT:
Silent video (no speech audio, no music, no captions). Subtle, continuous speech-mimicking lip motion from 0s through the final frame without stopping. Product never approaches mouth/face. Only partial product visible at all times; fine print/barcodes/nutrition text must be naturally obscured.

SCENE:
Use the exact person, outfit, hair, and environment from the provided UGC image reference. Medium close-up framing with torso visible.

CAMERA:
Handheld smartphone feel, medium close-up, gentle push-in (very subtle) with stable horizon. Keep subject centered within Instagram safe areas.

SUBJECT:
The same creator from the reference image, calm demeanor, intentional eye contact with camera, relaxed posture.

ACTION TIMELINE:
  0–2s:
Subject faces camera with calm, steady eye contact and subtle continuous lip motion as if speaking softly. One hand holds the product at mid-chest level, but it’s mostly out of frame—only a corner/edge of the Starbucks coffee packaging peeks in from the lower-right side. Fingers naturally cover any text; only brand color and a partial logo shape may be hinted.
  2–4s:
A small, natural wrist adjustment brings a slightly different partial angle of the product into view (still only a portion visible). Subject gives a gentle, approving micro-nod while maintaining continuous lip motion. The other hand briefly smooths or taps the front of their shirt/torso area casually, then returns to a relaxed position.
  4–6s:
Subject glances down briefly toward the product (eyes dip for a moment), then returns to direct eye contact. Product remains at chest level; grip stays relaxed. The camera continues a barely noticeable push-in, keeping the product partially cropped and text obscured.
  6–8s:
Subject holds steady, calm expression, continuing subtle lip motion through the end. Product motion settles with only a small natural sway from handheld movement. Maintain partial product visibility at the lower edge/side of frame; no deliberate “showing” gesture.

PRODUCT HANDLING CONSTRAINT:
Product must remain at chest/torso level the entire time. No lifting toward face. No sipping or drinking. Grip relaxed; no pointing at labels.

PRODUCT VISIBILITY:
Never fully visible. Only a partial section appears in frame at any moment. Fingers and cropping must obscure fine printed text, nutrition labels, and barcodes; only brand colors and a partial logo may be visible. 

DEPTH OF FIELD:
Natural smartphone depth; subject in clear focus, background slightly soft but recognizable as the same environment from the reference.

SUBTLE MOTION:
Continuous speech-mimicking lip motion throughout. Minimal head movement (micro-nods). Gentle handheld sway; very subtle push-in.

ENVIRONMENT:
Exactly as in the reference image—no new props or background changes introduced.

LIGHTING:
Match the reference image lighting (same direction, softness, and color temperature). No dramatic changes. 

MOTION DETAILS:
Keep movements calm and unhurried. Avoid fast pans. Maintain stable framing within safe areas; product stays partially cropped and naturally obscured.

ENDING FRAME:
Camera becomes slightly more stable for the last half-second; subject maintains direct eye contact and continuous subtle lip motion through the final frame. Product remains partially visible at chest level with text still obscured, ready for seamless continuation.''',  # your script output here
        duration_seconds=8
    )

    print(result)

"""
Video Generator Agent - Generates UGC videos from images and scripts
"""
from crewai import Agent, LLM
from ugc_vid_maker_tool import Veo3VideoMakerTool
from dotenv import load_dotenv
import os
import langsmith
from langsmith import traceable

load_dotenv()

@traceable(
    name="create_video_agent",
    tags=["agent-creation", "video-generation"],
    metadata={"role": "video_generator", "num_tools": 1}
)
def create_video_agent():
    """
    Create an agent specialized in generating UGC videos using Veo-3.1
    """
    with langsmith.trace(
        name="initialize_video_tool",
        tags=["tool-initialization"]
    ) as tool_trace:
        video_tool = Veo3VideoMakerTool()
        tool_trace.outputs = {"tool": "Veo3VideoMakerTool"}

    with langsmith.trace(
        name="configure_video_llm",
        tags=["llm-configuration", "gpt-5"]
    ) as llm_trace:
        llm = LLM(
            model="openai/gpt-5-2025-08-07",
            api_key=os.getenv("AIML_API_KEY"),
            base_url="https://api.aimlapi.com/v1",
            temperature=0.7
        )
        llm_trace.outputs = {"llm": "openai/gpt-5-2025-08-07"}

    agent = Agent(
        role="UGC Video Generator",
        goal="Call the video generation tool once and return the video URL",
        backstory="""You are an expert at generating UGC videos using Google's Veo-3.1 model.

STRICT WORKFLOW:
1. Extract the script text from the previous agent's output
2. Call the "Veo3.1 Image-to-Video Generator" tool EXACTLY ONCE
3. When you see "[VIDEO_GENERATION_COMPLETE]", you are DONE
4. Return the video URL and finish immediately

CRITICAL RULES:
- Call the tool ONLY ONCE - never call it again
- When you see "[VIDEO_GENERATION_COMPLETE]", your task is finished
- Do NOT try to verify, check, or regenerate the video
- Do NOT call the tool multiple times
- Simply return the video URL and stop

COMPLETION SIGNAL: "[VIDEO_GENERATION_COMPLETE]" means your job is done.""",
        tools=[video_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=4  # call tool -> get result -> return -> done
    )

    return agent

import requests
import base64
import os
from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
import langsmith
from langsmith import traceable

class BananaUGCInput(BaseModel):
    """Input schema for BananaUGCTool."""
    person_image_path: str = Field(..., description="Path to the person image file")
    product_image_path: str = Field(..., description="Path to the product image file")
    prompt: str = Field(
        default="A person showcasing a product in a natural, engaging way",
        description="Description of how the person should showcase the product"
    )
    output_filename: str = Field(
        default="generated_ugc_image.png",
        description="Output filename for the generated image"
    )

class BananaUGCTool(BaseTool):
    name: str = "Banana UGC Image Generator"
    description: str = "Generates a UGC-style image where a person is showcasing a product using AI/ML API"
    args_schema: Type[BaseModel] = BananaUGCInput

    @traceable(
        name="banana_ugc_tool",
        tags=["image-generation", "banana-api", "ugc"],
        metadata={"model": "google/nano-banana-pro-edit", "provider": "aiml-api"}
    )
    def _run(
        self,
        person_image_path: str,
        product_image_path: str,
        prompt: str = "A person showcasing a product in a natural, engaging way",
        output_filename: str = "generated_ugc_image.png"
    ) -> str:
        """
        Generate UGC image using AI/ML API with google/nano-banana-pro model.
        Includes comprehensive LangSmith tracing for all steps.
        """
        api_key = os.getenv("AIML_API_KEY")
        if not api_key:
            return "Error: AIML_API_KEY not found in environment variables"

        # Read and encode images with tracing
        with langsmith.trace(
            name="encode_input_images",
            inputs={
                "person_image_path": person_image_path,
                "product_image_path": product_image_path
            },
            tags=["image-processing", "base64-encoding"],
            metadata={}
        ) as encode_trace:
            try:
                with open(person_image_path, "rb") as f:
                    person_image_data = f.read()
                    person_image_b64 = base64.b64encode(person_image_data).decode()

                with open(product_image_path, "rb") as f:
                    product_image_data = f.read()
                    product_image_b64 = base64.b64encode(product_image_data).decode()

                # Log image metadata
                encode_trace.metadata.update( {
                    "person_image_size": len(person_image_data),
                    "product_image_size": len(product_image_data),
                    "person_image_b64_length": len(person_image_b64),
                    "product_image_b64_length": len(product_image_b64)
                })
                encode_trace.outputs = {"status": "images_encoded"}

            except FileNotFoundError as e:
                error_msg = f"Error: Image file not found - {str(e)}"
                encode_trace.outputs = {"error": error_msg}
                return error_msg

        # AI/ML API endpoint
        url = "https://api.aimlapi.com/v1/images/generations"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        # Construct prompt for image-to-image composition
        full_prompt = (
            f"Combine these images to create a realistic UGC-style photo where the person "
            f"from the first image is naturally showcasing the product from the second image. "
            f"{prompt}. Keep the same person's face and identity, and the exact product appearance. "
            f"Make it look like authentic user-generated content."
        )

        # Use correct schema for google/nano-banana-pro-edit
        payload = {
            "model": "google/nano-banana-pro-edit",
            "prompt": full_prompt,
            "image_urls": [
                f"data:image/jpeg;base64,{person_image_b64}",
                f"data:image/jpeg;base64,{product_image_b64}"
            ],
            "aspect_ratio": "1:1",
            "resolution": "1K",
            "num_images": 1
        }

        # Call image generation API with detailed tracing
        with langsmith.trace(
            name="call_banana_api",
            inputs={
                "model": "google/nano-banana-pro-edit",
                "prompt": full_prompt,
                "num_images": 1
            },
            tags=["api-call", "image-generation", "aiml-api"],
            metadata={
                "provider": "AI/ML API",
                "endpoint": url,
                "model": "google/nano-banana-pro-edit"
            }
        ) as api_trace:
            try:
                import time
                start_time = time.time()

                print(f"\n🎨 Calling Banana API for {output_filename}...")
                print(f"   Model: {payload['model']}")
                print(f"   Prompt: {full_prompt[:100]}...")
                
                response = requests.post(url, json=payload, headers=headers, timeout=180)

                latency = time.time() - start_time

                # Log API call metadata
                api_trace.metadata.update({
                    "status_code": response.status_code,
                    "latency_seconds": round(latency, 2),
                    "response_size_bytes": len(response.content)
                })

                # Accept both 200 and 201 status codes
                if response.status_code not in [200, 201]:
                    error_msg = f"Error: API returned status {response.status_code}: {response.text[:500]}"
                    api_trace.outputs = {"error": error_msg, "status_code": response.status_code}
                    print(f"❌ API Error: {error_msg}")
                    return error_msg

                result = response.json()
                print(f"✅ API Success! Status: {response.status_code}")
                api_trace.outputs = {"status": "success", "result_keys": list(result.keys())}

                # Estimate cost (approximate pricing for nano-banana-pro-edit)
                # This is a placeholder - adjust based on actual pricing
                estimated_cost = 0.02  # $0.02 per generation (example)
                api_trace.metadata["estimated_cost_usd"] = estimated_cost

            except requests.exceptions.Timeout:
                error_msg = f"Error: API request timed out after 180 seconds"
                api_trace.outputs = {"error": error_msg}
                print(error_msg)
                return error_msg
            except requests.exceptions.RequestException as e:
                error_msg = f"Error calling AI/ML API: {str(e)[:200]}"
                api_trace.outputs = {"error": error_msg}
                print(error_msg)
                return error_msg

        # Save the generated image with tracing
        with langsmith.trace(
            name="save_generated_image",
            tags=["image-output", "file-save"],
            metadata={}
        ) as save_trace:
            if "data" in result and len(result["data"]) > 0:
                image_data = result["data"][0]
                output_path = output_filename

                # Check if it's a URL or base64
                if "url" in image_data:
                    # Download from URL
                    img_response = requests.get(image_data["url"])
                    img_response.raise_for_status()

                    with open(output_path, "wb") as f:
                        f.write(img_response.content)

                    save_trace.metadata.update( {
                        "method": "url_download",
                        "image_url": image_data["url"],
                        "output_path": output_path,
                        "image_size_bytes": len(img_response.content)
                    })
                    save_trace.outputs = {"output_path": output_path, "url": image_data["url"]}

                    return f"✅ SUCCESS: Image saved to {output_path}"

                elif "b64_json" in image_data:
                    # Decode base64
                    image_bytes = base64.b64decode(image_data["b64_json"])

                    with open(output_path, "wb") as f:
                        f.write(image_bytes)

                    save_trace.metadata.update({
                        "method": "base64_decode",
                        "output_path": output_path,
                        "image_size_bytes": len(image_bytes)
                    })
                    save_trace.outputs = {"output_path": output_path}

                    return f"✅ SUCCESS: Image saved to {output_path}"

                else:
                    error_msg = f"Error: Unexpected image format in response - {result}"
                    save_trace.outputs = {"error": error_msg}
                    return error_msg
            else:
                error_msg = f"Error: No image data in response - {result}"
                save_trace.outputs = {"error": error_msg}
                return error_msg

"""
Image Generator Agent - Generates 4 UGC images from prompts
"""
from crewai import Agent, LLM
from banana_tool_with_langsmith import BananaUGCTool
from dotenv import load_dotenv
import os
import langsmith
from langsmith import traceable

load_dotenv()

@traceable(
    name="create_image_generator_agent",
    tags=["agent-creation", "image-generation"],
    metadata={"role": "image_generator", "num_tools": 1}
)
def create_image_generator_agent():
    """
    Create an agent specialized in generating UGC images
    """
    with langsmith.trace(
        name="initialize_banana_tool",
        tags=["tool-initialization"]
    ) as tool_trace:
        banana_tool = BananaUGCTool()
        tool_trace.outputs = {"tool": "BananaUGCTool"}

    with langsmith.trace(
        name="configure_image_llm",
        tags=["llm-configuration", "gpt-5"]
    ) as llm_trace:
        llm = LLM(
            model="openai/gpt-5-2025-08-07",
            api_key=os.getenv("AIML_API_KEY"),
            base_url="https://api.aimlapi.com/v1",
            temperature=0.7
        )
        llm_trace.outputs = {"llm": "openai/gpt-5-2025-08-07"}

    agent = Agent(
        role="UGC Image Generator",
        goal="Generate exactly 4 UGC images by calling the tool 4 times with different filenames",
        backstory="""You are an expert at generating UGC images using the Banana UGC tool.

MANDATORY WORKFLOW - Follow this EXACT sequence:

STEP 1: Extract the 4 prompts from the previous task
STEP 2: Call tool with Prompt 1 → output_filename="generated_ugc_image_1.png"
STEP 3: Call tool with Prompt 2 → output_filename="generated_ugc_image_2.png"
STEP 4: Call tool with Prompt 3 → output_filename="generated_ugc_image_3.png"
STEP 5: Call tool with Prompt 4 → output_filename="generated_ugc_image_4.png"
STEP 6: Report completion

CRITICAL RULES:
- Make EXACTLY 4 tool calls (one per prompt)
- Each call MUST use a DIFFERENT output_filename
- Filenames: generated_ugc_image_1.png, generated_ugc_image_2.png, generated_ugc_image_3.png, generated_ugc_image_4.png
- After seeing "✅ SUCCESS" 4 times, you are DONE
- Track your progress: "Completed 1/4", "Completed 2/4", "Completed 3/4", "Completed 4/4"

When you see "✅ SUCCESS" for the 4th time, immediately finish and report all 4 filenames.""",
        tools=[banana_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=15  # 4 tool calls + thinking + reporting
    )

    return agent

"""
Prompt Variator Agent - Generates 4 diverse UGC prompts
"""
from crewai import Agent, LLM
from prompt_variator_tool import PromptVariatorTool
from dotenv import load_dotenv
import os
import langsmith
from langsmith import traceable

load_dotenv()

@traceable(
    name="create_prompt_agent",
    tags=["agent-creation", "prompt-generation"],
    metadata={"role": "prompt_variator", "num_tools": 1}
)
def create_prompt_agent():
    """
    Create an agent specialized in generating diverse prompts
    """
    with langsmith.trace(
        name="initialize_prompt_tool",
        tags=["tool-initialization"]
    ) as tool_trace:
        prompt_variator = PromptVariatorTool()
        tool_trace.outputs = {"tool": "PromptVariatorTool"}

    with langsmith.trace(
        name="configure_prompt_llm",
        tags=["llm-configuration", "gpt-5"]
    ) as llm_trace:
        llm = LLM(
            model="openai/gpt-5-2025-08-07",
            api_key=os.getenv("AIML_API_KEY"),
            base_url="https://api.aimlapi.com/v1",
            temperature=0.7
        )
        llm_trace.outputs = {"llm": "openai/gpt-5-2025-08-07"}

    agent = Agent(
        role="UGC Prompt Variator",
        goal="Call the prompt variator tool once and return the 4 prompts",
        backstory="""You are a creative prompt engineer specializing in UGC content.

STRICT WORKFLOW:
1. Call the "UGC Prompt Variator" tool EXACTLY ONCE with the base intent
2. When you see "[PROMPT_GENERATION_COMPLETE]" in the response, you are DONE
3. Return the 4 prompts exactly as received
4. DO NOT call the tool again
5. DO NOT modify or improve the prompts

COMPLETION SIGNAL: When you see "[PROMPT_GENERATION_COMPLETE]", immediately finish your task and return the prompts.""",
        tools=[prompt_variator],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=3  # think -> call tool -> return result
    )

    return agent

"""
Prompt Variator Tool for CrewAI
Generates 4 diverse prompt variants from a base intent
"""
import os
import json
from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
import langsmith
from langsmith import traceable
from openai import OpenAI

class PromptVariatorInput(BaseModel):
    """Input schema for PromptVariatorTool."""
    base_intent: str = Field(..., description="Base user intent for generating diverse prompt variants")

class PromptVariatorTool(BaseTool):
    name: str = "UGC Prompt Variator"
    description: str = """Generates 4 diverse prompt variants from a base user intent. 
    Each variant preserves identity and intent but varies pose, hand usage, framing, and body orientation.
    Returns a JSON string with 4 prompts that you can use for image generation."""
    args_schema: Type[BaseModel] = PromptVariatorInput
    cache_function: bool = False

    @traceable(
        name="prompt_variator_tool",
        tags=["prompt-variation", "gpt-5"],
        metadata={"model": "gpt-5-2025-08-07", "num_variants": 4}
    )
    def _run(self, base_intent: str) -> str:
        """
        Generate 4 diverse prompt variants using GPT-5.
        """
        with langsmith.trace(
            name="initialize_gpt5_client",
            tags=["llm-initialization"]
        ) as init_trace:
            client = OpenAI(
                api_key=os.getenv("AIML_API_KEY"),
                base_url="https://api.aimlapi.com/v1"
            )
            init_trace.outputs = {"client": "OpenAI"}

        system_instruction = """You are a UGC Prompt Variator. Given a base user intent, generate 4 concise, image-model-ready prompts that preserve identity and intent but vary pose, hand usage, framing, and body orientation. Do not change clothing, environment, lighting, or facial expression.

Output STRICT JSON format:
{"prompts": ["prompt_variant_1", "prompt_variant_2", "prompt_variant_3", "prompt_variant_4"]}

Variation guidelines:
- Variant 1: Mid-shot, holding product with right hand, facing camera directly
- Variant 2: Waist-up, holding product with left hand, body slightly angled
- Variant 3: Close framing, both hands on product, front view
- Variant 4: Mid-shot, one hand gesture, body at 45-degree angle"""

        with langsmith.trace(
            name="call_gpt5_for_variants",
            inputs={"base_intent": base_intent},
            tags=["llm-call"]
        ) as llm_trace:
            try:
                response = client.chat.completions.create(
                    model="openai/gpt-5-2025-08-07",
                    messages=[
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": f"Base intent: {base_intent}\n\nGenerate 4 prompt variants."}
                    ],
                    temperature=0.7,
                    timeout=60
                )

                content = response.choices[0].message.content
                llm_trace.metadata.update({
                    "tokens_used": response.usage.total_tokens,
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens
                })

                # Parse and validate JSON
                variants_data = json.loads(content)
                prompts = variants_data.get("prompts", [])

                if len(prompts) != 4:
                    raise ValueError(f"Expected 4 prompts, got {len(prompts)}")

                llm_trace.outputs = {"prompts": prompts}
                
                # Return structured response that clearly signals completion
                response_text = "✅ TASK COMPLETE - 4 prompts generated successfully:\n\n"
                
                for i, prompt in enumerate(prompts, 1):
                    response_text += f"Prompt {i}: {prompt}\n\n"
                
                response_text += "\n[PROMPT_GENERATION_COMPLETE] - Do not call this tool again."
                
                return response_text

            except Exception as e:
                error_msg = f"Error generating prompt variants: {str(e)[:200]}"
                llm_trace.outputs = {"error": error_msg}
                
                # Fallback: generate simple variants without API
                print(f"API failed, using fallback prompts: {error_msg}")
                fallback_prompts = [
                    f"{base_intent}, mid-shot, holding product with right hand, facing camera directly",
                    f"{base_intent}, waist-up, holding product with left hand, body slightly angled",
                    f"{base_intent}, close framing, both hands on product, front view",
                    f"{base_intent}, mid-shot, one hand gesture, body at 45-degree angle"
                ]
                
                response_text = "✅ TASK COMPLETE - 4 prompts generated successfully (fallback):\n\n"
                
                for i, prompt in enumerate(fallback_prompts, 1):
                    response_text += f"Prompt {i}: {prompt}\n\n"
                
                response_text += "\n[PROMPT_GENERATION_COMPLETE] - Do not call this tool again."
                
                return response_text

"""
Script Generator Agent - Generates UGC video scripts from images
"""
from crewai import Agent, LLM
from ugc_script_maker_tool import UGCScriptMakerTool
from dotenv import load_dotenv
import os
import langsmith
from langsmith import traceable

load_dotenv()

@traceable(
    name="create_script_agent",
    tags=["agent-creation", "script-generation"],
    metadata={"role": "script_generator", "num_tools": 1}
)
def create_script_agent():
    """
    Create an agent specialized in generating UGC video scripts
    """
    with langsmith.trace(
        name="initialize_script_tool",
        tags=["tool-initialization"]
    ) as tool_trace:
        script_tool = UGCScriptMakerTool()
        tool_trace.outputs = {"tool": "UGCScriptMakerTool"}

    with langsmith.trace(
        name="configure_script_llm",
        tags=["llm-configuration", "gpt-5"]
    ) as llm_trace:
        llm = LLM(
            model="openai/gpt-5-2025-08-07",
            api_key=os.getenv("AIML_API_KEY"),
            base_url="https://api.aimlapi.com/v1",
            temperature=0.7
        )
        llm_trace.outputs = {"llm": "openai/gpt-5-2025-08-07"}

    agent = Agent(
        role="UGC Video Script Creator",
        goal="Generate professional 8-second UGC video scripts optimized for Veo 3",
        backstory="""You are an expert UGC video script writer specializing in authentic creator content.

STRICT WORKFLOW:
1. Receive a UGC image reference and product details
2. Call the "UGC Script Maker" tool EXACTLY ONCE
3. When you see the complete script output, you are DONE
4. Return the script exactly as received

CRITICAL RULES:
- Call the tool ONLY ONCE
- Do NOT modify or improve the script
- Do NOT call the tool again
- After receiving the script, your task is complete

The script will be optimized for Veo 3 video generation with authentic UGC style.""",
        tools=[script_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=3  # think -> call tool -> return result
    )

    return agent

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from ..database.base import Base


# =====================
# TASKS
# =====================

class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(128), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(128), nullable=False, index=True)

    created_by_user_id = Column(String(128), nullable=True, index=True)
    assigned_agent_id = Column(String(128), nullable=True, index=True)

    status = Column(String(32), nullable=False)

    success_criteria = Column(JSON, nullable=True)
    meta_data = Column(JSON, name="metadata", nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    execution_links = relationship(
        "AgentExecutionTask",
        back_populates="task",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    artifacts = relationship(
        "Artifact",
        back_populates="task",
        lazy="selectin",
    )


# =====================================
# JOIN TABLE (EXECUTIONS ↔ TASKS)
# =====================================

class AgentExecutionTask(Base):
    __tablename__ = "agent_execution_tasks"

    id = Column(String(128), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(128), nullable=False, index=True)

    agent_execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    task_id = Column(
        String(128),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    role = Column(String(64), nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    task = relationship(
        "Task",
        back_populates="execution_links",
    )

    agent_execution = relationship(
        "AgentExecution",
        lazy="selectin",
    )


# =====================
# ARTIFACT & MEMORY
# =====================

class Artifact(Base):
    __tablename__ = "artifacts"

    id = Column(String(128), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(128), nullable=False, index=True)

    conversation_id = Column(
        String(128),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    task_id = Column(
        String(128),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    agent_execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_executions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    artifact_type = Column(String(64), nullable=False)
    visibility_scope = Column(String(32), nullable=False)
    execution_task_role = Column(String(64), nullable=True)

    content = Column(Text, nullable=True)

    # pgvector column (created when CREATE EXTENSION vector exists)
    embedding = Column(
        Text,
        nullable=True,
        comment="pgvector column; actual type resolved at DB init",
    )

    meta_data = Column(JSON, name="metadata", nullable=True)

    parent_artifact_id = Column(
        String(128),
        ForeignKey("artifacts.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_by = Column(String(128), nullable=True)
    agent_id = Column(String(128), nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    parent = relationship(
        "Artifact",
        remote_side="Artifact.id",
        lazy="selectin",
    )

    task = relationship(
        "Task",
        back_populates="artifacts",
    )

