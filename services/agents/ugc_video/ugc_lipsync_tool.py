import os
import requests
import time
from crewai.tools import BaseTool
from dotenv import load_dotenv


class LipsyncTool(BaseTool):
    name: str = "Lipsync Video Generator"
    description: str = "Generates a lipsynced video by combining a video file and an audio file using the Sync API lipsync-2-pro model. Accepts URLs for video and audio."

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
        load_dotenv()
        
        api_key = os.getenv("LIPSYNC_API_KEY")
        if not api_key:
            return "Error: LIPSYNC_API_KEY not found in .env file"
        
        api_url = "https://api.sync.so/v2/generate"
        
        headers = {
            "x-api-key": api_key,
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
                
                status_result = self._check_status(job_id, api_key)
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


if __name__ == "__main__":
    # Test the tool
    tool = LipsyncTool()
    
    # Example with URLs
    result = tool._run(
        video_url="https://cdn.aimlapi.com/flamingo/files/b/0a878afc/FigQhki9o10QD81pr-zie_6e1362ec0fbd445a8302f0d3a6af5ae3.mp4",
        audio_url="https://tmpfiles.org/dl/16870024/test_ugc_audio.mp3",
        output_filename="test_output"
    )
    
    print(result)
