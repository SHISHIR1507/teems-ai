#!/usr/bin/env python3
"""
MCP Server for RAG Meeting Search System

This server exposes meeting transcript search and RAG-based Q&A capabilities
through the Model Context Protocol (MCP).
"""

import asyncio
import sys
import os
from typing import Any, Optional
from datetime import datetime

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp import types

# Import existing modules
from database import SessionLocal
from models import Call, CallChunk
from rag_service import rag_service

# Initialize MCP server
server = Server("meeting-rag-server")


def get_db_session():
    """Create a new database session"""
    return SessionLocal()


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    List all available MCP tools for meeting search and RAG.
    """
    return [
        types.Tool(
            name="search_meetings",
            description="Search across all meeting transcripts using vector similarity search. Returns relevant chunks from meetings that match the query.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to find relevant meeting content"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="list_meetings",
            description="List all available meetings with their metadata (title, date, summary preview).",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of meetings to return (default: 10)",
                        "default": 10
                    }
                }
            }
        ),
        types.Tool(
            name="get_meeting_details",
            description="Get complete details of a specific meeting including full transcript, summary, and action items.",
            inputSchema={
                "type": "object",
                "properties": {
                    "call_id": {
                        "type": "string",
                        "description": "The unique identifier of the meeting"
                    }
                },
                "required": ["call_id"]
            }
        ),
        types.Tool(
            name="ask_meeting_question",
            description="Ask a question about a specific meeting. Uses RAG (Retrieval Augmented Generation) to find relevant context and generate an intelligent answer.",
            inputSchema={
                "type": "object",
                "properties": {
                    "call_id": {
                        "type": "string",
                        "description": "The unique identifier of the meeting"
                    },
                    "question": {
                        "type": "string",
                        "description": "The question to ask about the meeting"
                    }
                },
                "required": ["call_id", "question"]
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    Handle tool execution requests.
    """
    
    if not arguments:
        arguments = {}
    
    try:
        if name == "search_meetings":
            return await search_meetings_tool(arguments)
        elif name == "list_meetings":
            return await list_meetings_tool(arguments)
        elif name == "get_meeting_details":
            return await get_meeting_details_tool(arguments)
        elif name == "ask_meeting_question":
            return await ask_meeting_question_tool(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")
    
    except Exception as e:
        return [
            types.TextContent(
                type="text",
                text=f"Error executing {name}: {str(e)}"
            )
        ]


async def search_meetings_tool(arguments: dict) -> list[types.TextContent]:
    """
    Search across all meeting transcripts using vector similarity.
    """
    query = arguments.get("query")
    top_k = arguments.get("top_k", 5)
    
    if not query:
        return [types.TextContent(type="text", text="Error: 'query' parameter is required")]
    
    db = get_db_session()
    try:
        # Get query embedding
        from embeddings import embedder
        query_embedding = await embedder.embed_one(query)
        
        # Search across ALL meetings using vector similarity
        chunks = db.query(CallChunk).order_by(
            CallChunk.embedding.cosine_distance(query_embedding)
        ).limit(top_k).all()
        
        if not chunks:
            return [types.TextContent(
                type="text",
                text="No relevant meeting content found for your query."
            )]
        
        # Get meeting details for each chunk
        results = []
        for chunk in chunks:
            call = db.query(Call).filter(Call.id == chunk.call_id).first()
            if call:
                results.append({
                    "meeting_id": call.id,
                    "meeting_title": call.title,
                    "meeting_date": call.start_time.isoformat() if call.start_time else None,
                    "content": chunk.content,
                    "chunk_index": chunk.chunk_index
                })
        
        # Format results
        result_text = f"Found {len(results)} relevant results:\n\n"
        for i, result in enumerate(results, 1):
            result_text += f"**Result {i}: {result['meeting_title']}**\n"
            result_text += f"Date: {result['meeting_date']}\n"
            result_text += f"Meeting ID: {result['meeting_id']}\n"
            result_text += f"Content:\n{result['content']}\n\n"
            result_text += "---\n\n"
        
        return [types.TextContent(type="text", text=result_text)]
    
    finally:
        db.close()


async def list_meetings_tool(arguments: dict) -> list[types.TextContent]:
    """
    List all available meetings.
    """
    limit = arguments.get("limit", 10)
    
    db = get_db_session()
    try:
        meetings = db.query(Call).order_by(Call.created_at.desc()).limit(limit).all()
        
        if not meetings:
            return [types.TextContent(
                type="text",
                text="No meetings found in the database."
            )]
        
        result_text = f"Found {len(meetings)} meetings:\n\n"
        for meeting in meetings:
            result_text += f"**{meeting.title}**\n"
            result_text += f"ID: {meeting.id}\n"
            result_text += f"Date: {meeting.start_time.isoformat() if meeting.start_time else 'N/A'}\n"
            
            # Add summary preview if available
            if meeting.summary:
                preview = meeting.summary[:200] + "..." if len(meeting.summary) > 200 else meeting.summary
                result_text += f"Summary: {preview}\n"
            
            # Add flags for available data
            flags = []
            if meeting.transcript:
                flags.append("Has Transcript")
            if meeting.summary:
                flags.append("Has Summary")
            if meeting.action_items:
                flags.append("Has Action Items")
            
            if flags:
                result_text += f"Available: {', '.join(flags)}\n"
            
            result_text += "\n---\n\n"
        
        return [types.TextContent(type="text", text=result_text)]
    
    finally:
        db.close()


async def get_meeting_details_tool(arguments: dict) -> list[types.TextContent]:
    """
    Get complete details of a specific meeting.
    """
    call_id = arguments.get("call_id")
    
    if not call_id:
        return [types.TextContent(type="text", text="Error: 'call_id' parameter is required")]
    
    db = get_db_session()
    try:
        call = db.query(Call).filter(Call.id == call_id).first()
        
        if not call:
            return [types.TextContent(
                type="text",
                text=f"Meeting not found with ID: {call_id}"
            )]
        
        # Build detailed response
        result_text = f"# {call.title}\n\n"
        result_text += f"**Meeting ID:** {call.id}\n"
        result_text += f"**Date:** {call.start_time.isoformat() if call.start_time else 'N/A'}\n"
        result_text += f"**Meeting Link:** {call.meeting_link or 'N/A'}\n\n"
        
        # Summary
        if call.summary:
            result_text += "## Summary\n\n"
            result_text += f"{call.summary}\n\n"
        
        # Action Items
        if call.action_items:
            result_text += "## Action Items\n\n"
            if isinstance(call.action_items, list):
                for item in call.action_items:
                    result_text += f"- {item}\n"
            else:
                result_text += f"{call.action_items}\n"
            result_text += "\n"
        
        # Transcript
        if call.transcript:
            result_text += "## Transcript\n\n"
            # Limit transcript length for display
            if len(call.transcript) > 5000:
                result_text += f"{call.transcript[:5000]}\n\n... (transcript truncated, {len(call.transcript)} total characters)\n"
            else:
                result_text += f"{call.transcript}\n"
        else:
            result_text += "## Transcript\n\nNo transcript available.\n"
        
        return [types.TextContent(type="text", text=result_text)]
    
    finally:
        db.close()


async def ask_meeting_question_tool(arguments: dict) -> list[types.TextContent]:
    """
    Ask a question about a specific meeting using RAG.
    """
    call_id = arguments.get("call_id")
    question = arguments.get("question")
    
    if not call_id:
        return [types.TextContent(type="text", text="Error: 'call_id' parameter is required")]
    
    if not question:
        return [types.TextContent(type="text", text="Error: 'question' parameter is required")]
    
    db = get_db_session()
    try:
        # Get meeting
        call = db.query(Call).filter(Call.id == call_id).first()
        
        if not call:
            return [types.TextContent(
                type="text",
                text=f"Meeting not found with ID: {call_id}"
            )]
        
        if not call.transcript:
            return [types.TextContent(
                type="text",
                text=f"No transcript available for meeting: {call.title}"
            )]
        
        # Use RAG service to find relevant chunks and generate answer
        relevant_chunks = await rag_service.search_relevant_chunks(
            question, call_id, db, top_k=5
        )
        
        if not relevant_chunks:
            return [types.TextContent(
                type="text",
                text=f"I couldn't find relevant information in the meeting '{call.title}' to answer your question."
            )]
        
        # Generate answer using LLM
        answer = await rag_service.generate_answer(
            question, relevant_chunks, call.title
        )
        
        # Format response
        result_text = f"**Question:** {question}\n\n"
        result_text += f"**Meeting:** {call.title}\n"
        result_text += f"**Date:** {call.start_time.isoformat() if call.start_time else 'N/A'}\n\n"
        result_text += f"**Answer:**\n\n{answer}\n\n"
        result_text += f"---\n\n"
        result_text += f"*Answer generated using {len(relevant_chunks)} relevant context chunks from the meeting transcript.*"
        
        return [types.TextContent(type="text", text=result_text)]
    
    finally:
        db.close()


async def main():
    """
    Main entry point for the MCP server.
    """
    # Run the server using stdin/stdout streams
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="meeting-rag-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
