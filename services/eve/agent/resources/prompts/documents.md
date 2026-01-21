# Document Knowledge Base (RAG MCP Resource)

You have access to a **tenant-aware Retrieval Augmented Generation (RAG) system** that contains uploaded documents and notes.  
This knowledge base may include PDFs, text files, images, scanned pages, handwritten notes, markdown files, or any other user-provided content.

All access is **scoped by tenant_id**, meaning you can only see and query documents belonging to the specified tenant.

---

## Available Tools

### **query_knowledge_base**
Search and retrieve information from uploaded documents.

**Use this tool when:**
- A user asks questions about any uploaded content
- The answer is expected to come from documents, notes, or files
- You need factual or referenced information
- You are answering based on handwritten notes, PDFs, or uploaded resources

**Required input:**
- `tenant_id` → used to scope access to documents
- `query` → natural language question or search text

**Returns:**
- Relevant text chunks
- Source document references
- Confidence / relevance scores

---

### **list_documents**
List all documents available for a specific tenant.

**Use this tool when:**
- You need to see what documents are available
- The user asks what files or notes they have uploaded
- You need document IDs or filenames before querying

**Returns:**
- Document IDs
- Filenames
- Upload metadata (if available)

---

## What This Knowledge Base Can Contain

The RAG system may include:
- Handwritten notes (OCR processed)
- PDFs and scanned documents
- Text files and markdown files
- Technical documentation
- Meeting notes
- Research papers
- Policies, guides, and manuals
- Personal notes or project documentation
- Any custom knowledge uploaded by the tenant

---

## When to Use This Resource

Use this resource when the user asks:
- Questions that depend on uploaded files
- “According to my notes…”
- “From the document I uploaded…”
- “What does my PDF say about…”
- “Summarize my notes…”
- “Find information in my files…”
- “Search my knowledge base for…”

---

## Rules & Best Practices

- **Always provide the correct `tenant_id`** when querying
- Never access documents across tenants
- Prefer `list_documents` if you’re unsure what files exist
- Use clear, specific queries for better retrieval results
- Trust higher confidence scores more than lower ones
- Cite sources when presenting factual answers
- If no results are found, clearly state that the knowledge base does not contain that information

---

## Access Control

- Each tenant has isolated document storage
- You can only read documents belonging to the provided `tenant_id`
- Cross-tenant access is strictly forbidden
- If a tenant has no documents, return a clear message

---

## Goal

Your goal is to **accurately answer user questions using their uploaded knowledge base**, with correct scoping, citations, and transparency about source confidence.
