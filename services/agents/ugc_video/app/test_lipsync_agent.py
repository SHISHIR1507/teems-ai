"""
Test script for Lipsync Agent (CrewAI)
Tests the lipsync agent directly with video and audio URLs
No need to run the full 3-step workflow - just test Step 3
"""
import sys
import os
from pathlib import Path

# Add app directory to path so imports work
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from crewai import Task, Crew, Agent, LLM
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type
import requests
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import config values
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LIPSYNC_API_KEY = os.getenv("LIPSYNC_API_KEY")


# Define the LipsyncTool inline to avoid import issues
from pydantic import BaseModel, Field
from typing import Type


class LipsyncToolInput(BaseModel):
    """Input schema for LipsyncTool."""
    video_url: str = Field(..., description="URL to the video file")
    audio_url: str = Field(..., description="URL to the audio file")
    output_filename: str = Field(default="lipsynced_output", description="Optional custom output filename")
    poll_interval: int = Field(default=5, description="Seconds between status checks")
    max_wait: int = Field(default=300, description="Maximum seconds to wait for completion")


class LipsyncTool(BaseTool):
    name: str = "Lipsync Video Generator"
    description: str = "Generates a lipsynced video by combining a video file and an audio file using the Sync API lipsync-2-pro model. Accepts URLs for video and audio."
    args_schema: Type[BaseModel] = LipsyncToolInput

    def _check_status(self, job_id: str, api_key: str) -> dict:
        """Check the status of a generation job."""
        url = f"https://api.sync.so/v2/generate/{job_id}"
        headers = {"x-api-key": api_key}
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    def _run(self, video_url: str, audio_url: str, output_filename: str = "lipsynced_output", poll_interval: int = 5, max_wait: int = 300) -> str:
        """
        Generate a lipsynced video using the Sync API.
        
        Args:
            video_url: URL to the video file
            audio_url: URL to the audio file
            output_filename: Optional custom output filename (default: "lipsynced_output")
            poll_interval: Seconds between status checks (default: 5)
            max_wait: Maximum seconds to wait for completion (default: 300)
            
        Returns:
            str: Status message with the result URL or error message
        """
        if not LIPSYNC_API_KEY:
            return "Error: LIPSYNC_API_KEY not found in .env file"
        
        api_url = "https://api.sync.so/v2/generate"
        
        headers = {
            "x-api-key": LIPSYNC_API_KEY,
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "lipsync-2-pro",
            "input": [
                {
                    "type": "video",
                    "url": video_url
                },
                {
                    "type": "audio",
                    "url": audio_url
                }
            ],
            "outputFileName": output_filename
        }
        
        try:
            print("Submitting lipsync job...")
            response = requests.post(api_url, headers=headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            if "id" not in result:
                return f"Unexpected response: {result}"
            
            job_id = result["id"]
            print(f"Job submitted! ID: {job_id}")
            print(f"Polling for status every {poll_interval} seconds...")
            
            # Poll for completion
            elapsed = 0
            while elapsed < max_wait:
                time.sleep(poll_interval)
                elapsed += poll_interval
                
                status_result = self._check_status(job_id, LIPSYNC_API_KEY)
                status = status_result.get("status")
                
                print(f"[{elapsed}s] Status: {status}")
                
                if status == "COMPLETED":
                    output_url = status_result.get("outputUrl")
                    duration = status_result.get("outputDuration")
                    print(f"✓ Video generated successfully!")
                    print(f"Duration: {duration}s")
                    print(f"URL: {output_url}")
                    return f"Success! Output URL: {output_url}\nDuration: {duration}s\nFull result: {status_result}"
                
                elif status == "FAILED":
                    error = status_result.get("error", "Unknown error")
                    error_code = status_result.get("error_code", "")
                    return f"Generation failed. Error: {error} (Code: {error_code})"
                
                elif status == "REJECTED":
                    return f"Generation rejected. Result: {status_result}"
                
                elif status in ["PENDING", "PROCESSING"]:
                    continue
                
                else:
                    return f"Unknown status: {status}. Result: {status_result}"
            
            return f"Timeout: Video generation took longer than {max_wait} seconds. Job ID: {job_id}. Check status manually."
            
        except requests.exceptions.RequestException as e:
            return f"Error generating lipsync video: {str(e)}"


def create_lipsync_agent():
    """
    Create an agent specialized in lipsyncing videos with audio using Sync API
    """
    lipsync_tool = LipsyncTool()
    
    llm = LLM(
        model="gpt-4o",
        api_key=OPENAI_API_KEY,
        temperature=0.7
    )
    
    agent = Agent(
        role="UGC Lipsync Specialist",
        goal="Call Lipsync Video Generator tool once",
        backstory="""You call the Lipsync Video Generator tool.

INSTRUCTIONS:
1. Call the tool with: video_url, audio_url, output_filename
2. Wait for response (this takes time)
3. Return the lipsynced video URL

DO NOT call the tool twice.
When you see "Success! Output URL:" you are done.""",
        tools=[lipsync_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=2
    )
    
    return agent


def test_lipsync_agent(video_url: str, audio_url: str):
    """
    Test the lipsync agent with video and audio URLs
    """
    
    # Check for required API keys
    if not OPENAI_API_KEY:
        print("❌ ERROR: OPENAI_API_KEY not found in .env file")
        return
    
    if not LIPSYNC_API_KEY:
        print("❌ ERROR: LIPSYNC_API_KEY not found in .env file")
        return
    
    output_filename = "test_lipsync_output"
    
    print("\n" + "="*60)
    print("Testing Lipsync Agent (CrewAI)")
    print("="*60)
    print(f"Video URL: {video_url}")
    print(f"Audio URL: {audio_url}")
    print(f"Output: {output_filename}")
    print("="*60)
    print()
    
    # Create the lipsync agent
    print("Creating lipsync agent...")
    lipsync_agent = create_lipsync_agent()
    print("✓ Agent created")
    print()
    
    # Create the task
    print("Creating task...")
    task = Task(
        description=f"""Call the Lipsync Video Generator tool to sync audio with video.

Parameters:
- video_url: {video_url}
- audio_url: {audio_url}
- output_filename: {output_filename}

Wait for the result and return the final video URL.""",
        expected_output="Final lipsynced video URL from Sync.so",
        agent=lipsync_agent,
        human_input=False
    )
    print("✓ Task created")
    print()
    
    # Execute the crew
    print("Starting lipsync process...")
    print("This may take 30-60 seconds...")
    print("-"*60)
    
    crew = Crew(
        agents=[lipsync_agent],
        tasks=[task],
        verbose=True,
        process="sequential"
    )
    
    result = crew.kickoff()
    
    print("-"*60)
    print()
    print("="*60)
    print("RESULT")
    print("="*60)
    print(result)
    print("="*60)
    
    # Parse the result
    result_str = str(result)
    
    if "Success! Output URL:" in result_str:
        print("\n✅ SUCCESS! Lipsync completed")
        
        # Extract URL - handle multiple possible patterns
        import re
        
        # Try storage.sync.so URLs first (final video)
        urls = re.findall(r'https://storage\.sync\.so[^\s<>"{}|\\^`\[\]]+', result_str)
        
        # Try api.sync.so generation URLs (with token)
        if not urls:
            urls = re.findall(r'https://api\.sync\.so/v2/generations/[^\s<>"{}|\\^`\[\]]+', result_str)
        
        # Try any .mp4 URLs
        if not urls:
            urls = re.findall(r'https://[^\s<>"{}|\\^`\[\]]+\.mp4[^\s<>"{}|\\^`\[\]]*', result_str)
        
        if urls:
            final_url = urls[0]
            print(f"\n🎬 Final Video URL:")
            print(f"   {final_url}")
            
            # Check if it's a generation URL (needs token) or direct storage URL
            if "api.sync.so/v2/generations" in final_url:
                print("\n⚠️  This is a generation URL (temporary, requires token)")
                print("   The actual video file should be at storage.sync.so")
                print("   You can access it via this URL or wait for the storage URL")
            else:
                print("\n✅ This is a direct storage URL - you can download it!")
    else:
        print("\n❌ Lipsync failed or timed out")
        print("Check the output above for error details")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("CREWAI LIPSYNC AGENT TEST")
    print("="*60)
    print()
    print("This tests the CrewAI lipsync agent (Step 3 only)")
    print("You need video and audio URLs from Steps 1 & 2")
    print()
    print("="*60)
    print()
    
    # Get URLs from user
    video_url = input("Enter video URL: ").strip()
    audio_url = input("Enter audio URL: ").strip()
    
    if not video_url or not audio_url:
        print("\n❌ Both video and audio URLs are required!")
        print("\nExample URLs:")
        print("Video: https://cdn.aimlapi.com/your-video.mp4")
        print("Audio: https://teems-agents.s3.amazonaws.com/your-audio.mp3")
    else:
        test_lipsync_agent(video_url, audio_url)
