"""
Direct test of Lipsync Tool (no agent, just the tool)
Faster way to test if the Sync.so API is working
"""
import sys
from pathlib import Path

# Add app directory to path
app_dir = Path(__file__).parent
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))

from tools.lipsync import LipsyncTool


def test_lipsync_tool_direct():
    """
    Test the lipsync tool directly without CrewAI agent
    """
    
    # Sample URLs - Replace these with your actual URLs
    video_url = "https://cdn.aimlapi.com/your-video.mp4"
    audio_url = "https://teems-agents.s3.amazonaws.com/your-audio.mp3"
    output_filename = "test_direct_lipsync"
    
    print("="*60)
    print("Direct Lipsync Tool Test")
    print("="*60)
    print(f"Video URL: {video_url}")
    print(f"Audio URL: {audio_url}")
    print(f"Output: {output_filename}")
    print("="*60)
    print()
    
    # Create tool instance
    print("Creating lipsync tool...")
    tool = LipsyncTool()
    print("✓ Tool created")
    print()
    
    # Call the tool directly
    print("Calling Sync.so API...")
    print("This will poll every 5 seconds for up to 5 minutes...")
    print("-"*60)
    
    result = tool._run(
        video_url=video_url,
        audio_url=audio_url,
        output_filename=output_filename,
        poll_interval=5,
        max_wait=300
    )
    
    print("-"*60)
    print()
    print("="*60)
    print("RESULT")
    print("="*60)
    print(result)
    print("="*60)
    
    # Check result
    if "Success! Output URL:" in result:
        print("\n✅ SUCCESS! Lipsync completed")
        
        # Extract URL
        import re
        urls = re.findall(r'https://storage\.sync\.so[^\s<>"{}|\\^`\[\]]+', result)
        if not urls:
            urls = re.findall(r'https://[^\s<>"{}|\\^`\[\]]+\.mp4[^\s<>"{}|\\^`\[\]]*', result)
        
        if urls:
            final_url = urls[0]
            print(f"\n🎬 Final Video URL:")
            print(f"   {final_url}")
            print("\nYou can download or view this video in your browser!")
    elif "Error:" in result:
        print("\n❌ Error occurred:")
        print(result)
    elif "Timeout:" in result:
        print("\n⏱️  Timeout - video generation took too long")
        print(result)
    else:
        print("\n⚠️  Unexpected result")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("DIRECT LIPSYNC TOOL TEST")
    print("="*60)
    print()
    print("INSTRUCTIONS:")
    print("1. Edit this file and replace the sample URLs")
    print("2. Make sure LIPSYNC_API_KEY is set in your .env file")
    print("3. Run: python test_lipsync_direct.py")
    print()
    print("This test bypasses CrewAI and calls the tool directly.")
    print("Useful for debugging API issues.")
    print()
    
    # Check if user wants to proceed
    response = input("Have you updated the URLs? (y/n): ").strip().lower()
    
    if response == 'y':
        print("\nStarting test...\n")
        test_lipsync_tool_direct()
    else:
        print("\n⚠️  Please update the video_url and audio_url in this file first!")
        print("Then run the script again.")
