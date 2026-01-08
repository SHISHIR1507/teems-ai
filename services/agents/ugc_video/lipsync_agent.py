"""
Lipsync Agent - Combines video and audio to create lipsynced UGC videos
"""
from crewai import Agent, LLM
from ugc_lipsync_tool import LipsyncTool
from dotenv import load_dotenv
import os
import langsmith
from langsmith import traceable

load_dotenv()

@traceable(
    name="create_lipsync_agent",
    tags=["agent-creation", "lipsync"],
    metadata={"role": "lipsync_generator", "num_tools": 1}
)
def create_lipsync_agent():
    """
    Create an agent specialized in lipsyncing videos with audio using Sync API
    """
    with langsmith.trace(
        name="initialize_lipsync_tool",
        tags=["tool-initialization"]
    ) as tool_trace:
        lipsync_tool = LipsyncTool()
        tool_trace.outputs = {"tool": "LipsyncTool"}

    with langsmith.trace(
        name="configure_lipsync_llm",
        tags=["llm-configuration", "gpt-5.2"]
    ) as llm_trace:
        llm = LLM(
            model="gpt-5.2-2025-12-11",
            api_key=os.getenv("AIML_API_KEY"),
            base_url="https://api.aimlapi.com/v1",
            temperature=0.7
        )
        llm_trace.outputs = {"llm": "gpt-5.2-2025-12-11"}

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


if __name__ == "__main__":
    """
    Test the lipsync agent independently
    """
    import requests
    from crewai import Task, Crew
    
    print("="*60)
    print("Testing Lipsync Agent")
    print("="*60)
    
    # UPDATE THESE WITH YOUR ACTUAL FILES/URLS
    video_url = "https://cdn.aimlapi.com/flamingo/files/b/0a879621/Q3s4o7thO4Ui3MFMJjNrR_441c55e460da4b8e98673bea02e27df6.mp4"
    audio_file = "audio_08598c08-f4e6-403a-ab62-460a16a9e089.mp3"  # Your local audio file
    
    # Check if audio file exists
    if not os.path.exists(audio_file):
        print(f"\n❌ Error: Audio file not found: {audio_file}")
        print("Please update the 'audio_file' variable with your actual audio file path")
        exit(1)
    
    print(f"\nTest Parameters:")
    print(f"  Video URL: {video_url}")
    print(f"  Audio File: {audio_file}")
    print()
    
    # Step 1: Upload audio to tmpfiles.org
    print("Step 1: Uploading audio file to tmpfiles.org...")
    try:
        with open(audio_file, 'rb') as f:
            files = {'file': f}
            upload_response = requests.post('https://tmpfiles.org/api/v1/upload', files=files)
            upload_response.raise_for_status()
            upload_data = upload_response.json()
            
            if upload_data.get('status') == 'success':
                # Convert to download URL
                temp_url = upload_data['data']['url']
                audio_url = temp_url.replace('tmpfiles.org/', 'tmpfiles.org/dl/')
                print(f"✅ Audio uploaded successfully")
                print(f"  Audio URL: {audio_url}")
            else:
                print(f"❌ Failed to upload audio: {upload_data}")
                exit(1)
    except Exception as e:
        print(f"❌ Error uploading audio: {str(e)}")
        exit(1)
    
    # Step 2: Create lipsync agent and generate lipsynced video
    print("\nStep 2: Creating lipsync agent and generating lipsynced video...")
    lipsync_agent = create_lipsync_agent()
    
    task = Task(
        description=f"""Generate a lipsynced video by combining the video and audio.

VIDEO URL: {video_url}
AUDIO URL: {audio_url}

Call the "Lipsync Video Generator" tool with:
- video_url: {video_url}
- audio_url: {audio_url}
- output_filename: test_lipsynced_output

Wait for the lipsync generation to complete and return the final video URL.""",
        expected_output="Lipsynced video URL from Sync API",
        agent=lipsync_agent,
        human_input=False
    )
    
    crew = Crew(
        agents=[lipsync_agent],
        tasks=[task],
        verbose=True,
        process="sequential"
    )
    
    result = crew.kickoff()
    result_str = str(result)
    
    print(f"\n{'='*60}")
    print("Result")
    print(f"{'='*60}")
    print(result_str)
    print(f"{'='*60}\n")
    
    # Extract lipsynced video URL
    lipsynced_url = None
    if "Success! Output URL:" in result_str:
        parts = result_str.split("Success! Output URL:")
        if len(parts) > 1:
            url_part = parts[1].strip()
            lipsynced_url = url_part.split()[0] if url_part else None
    
    if lipsynced_url:
        print(f"\n✅ TEST COMPLETE")
        print(f"  Lipsynced Video URL: {lipsynced_url}")
    else:
        print(f"\n❌ TEST FAILED")
        print(f"  Could not extract lipsynced video URL from result")
