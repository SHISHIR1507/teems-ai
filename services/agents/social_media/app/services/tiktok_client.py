"""
TikTok API client for posting videos
Using PULL_FROM_URL method (simpler, as per TikTok docs)
"""

import requests
from typing import List, Dict


class TikTokClient:
    """Client for TikTok Content Posting API"""
    
    def __init__(self):
        self.base_url = "https://open.tiktokapis.com/v2/post/publish/video"
    
    def post_video(
        self,
        video_url: str,
        caption: str,
        hashtags: List[str],
        access_token: str
    ) -> Dict:
        """
        Post a video to TikTok using FILE_UPLOAD method.
        
        Args:
            video_url: Publicly accessible video URL
            caption: Video caption/title
            hashtags: List of hashtags
            access_token: User's TikTok access token
        
        Returns:
            Dict with publish_id and status
        """
        
        # 1. Download video content
        try:
            print(f"Downloading video from {video_url}...")
            video_resp = requests.get(video_url, stream=True, timeout=30)
            video_resp.raise_for_status()
            video_data = video_resp.content
            video_size = len(video_data)
            
            if video_size == 0:
                raise ValueError("Video file is empty")
            
            print(f"✓ Downloaded {video_size:,} bytes")
        
        except Exception as e:
            raise RuntimeError(f"Failed to download video from {video_url}: {e}")
        
        # 2. Initialize upload with TikTok
        init_url = f"{self.base_url}/init/"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json; charset=UTF-8'
        }
        
        # Prepare title with hashtags
        full_title = caption
        if hashtags:
            hashtag_str = " ".join([f"#{tag}" for tag in hashtags])
            full_title = f"{caption} {hashtag_str}" if caption else hashtag_str
        
        # Limit to 150 characters
        full_title = full_title[:150]
        
        # Use FILE_UPLOAD method (works without domain verification)
        init_data = {
            "post_info": {
                "title": full_title,
                "privacy_level": "SELF_ONLY",  # Most private setting
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
                "video_cover_timestamp_ms": 1000
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": video_size,  # Single chunk upload
                "total_chunk_count": 1
            }
        }
        
        try:
            print("Initializing TikTok upload...")
            resp_init = requests.post(init_url, headers=headers, json=init_data, timeout=30)
            resp_init.raise_for_status()
            init_json = resp_init.json()
            
            if 'data' not in init_json:
                raise RuntimeError(f"TikTok API error: {init_json}")
            
            upload_url = init_json['data']['upload_url']
            publish_id = init_json['data']['publish_id']
            
            print(f"✓ Got upload URL and publish_id: {publish_id}")
        
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"TikTok API error: {e.response.text}")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize TikTok upload: {e}")
        
        # 3. Upload video to TikTok
        headers_upload = {
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes 0-{video_size-1}/{video_size}"
        }
        
        try:
            print("Uploading video to TikTok...")
            resp_upload = requests.put(upload_url, data=video_data, headers=headers_upload, timeout=60)
            resp_upload.raise_for_status()
            print("✓ Video uploaded successfully!")
        
        except Exception as e:
            raise RuntimeError(f"Failed to upload video to TikTok: {e}")
        
        return {
            "status": "success",
            "publish_id": publish_id,
            "message": "Video posted to TikTok successfully"
        }
    
    def check_post_status(self, publish_id: str, access_token: str) -> Dict:
        """
        Check the status of a posted video.
        
        Args:
            publish_id: The publish_id from post_video response
            access_token: User's TikTok access token
        
        Returns:
            Dict with status information
        """
        status_url = f"{self.base_url}/status/fetch/"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json; charset=UTF-8'
        }
        
        payload = {
            "publish_id": publish_id
        }
        
        try:
            response = requests.post(status_url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        
        except Exception as e:
            raise RuntimeError(f"Failed to check post status: {e}")
