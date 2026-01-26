"""
Facebook Graph API client for posting videos
"""
import requests
from typing import Dict, Optional
import time


class FacebookClient:
    """Client for Facebook Graph API video posting"""
    
    def __init__(self):
        self.base_url = "https://graph.facebook.com/v18.0"
    
    def post_video(
        self,
        video_url: str,
        caption: str,
        access_token: str,
        page_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict:
        """
        Post a video to Facebook using Graph API.
        
        Args:
            video_url: Publicly accessible video URL
            caption: Video caption/description
            access_token: Facebook access token (page token for pages, user token for profiles)
            page_id: Facebook Page ID (if posting to a page)
            user_id: Facebook User ID (if posting to personal profile)
        
        Returns:
            Dict with post_id and status
        
        Note: Facebook requires either page_id or user_id, not both.
        """
        if not page_id and not user_id:
            raise ValueError("Either page_id or user_id must be provided")
        
        if page_id and user_id:
            raise ValueError("Cannot specify both page_id and user_id")
        
        # Determine target (page or user)
        target_id = page_id if page_id else user_id
        
        # Step 1: Upload video using resumable upload API
        # For simplicity, we'll use the direct video upload endpoint
        upload_url = f"{self.base_url}/{target_id}/videos"
        
        # Download video to get size
        try:
            video_resp = requests.get(video_url, stream=True, timeout=30)
            video_resp.raise_for_status()
            video_data = video_resp.content
            video_size = len(video_data)
            
            if video_size == 0:
                raise ValueError("Video file is empty")
        except Exception as e:
            raise RuntimeError(f"Failed to download video from {video_url}: {e}")
        
        # Step 2: Upload video
        # Facebook Graph API supports direct video upload
        files = {
            'source': ('video.mp4', video_data, 'video/mp4')
        }
        
        data = {
            'description': caption,
            'access_token': access_token
        }
        
        try:
            response = requests.post(
                upload_url,
                files=files,
                data=data,
                timeout=120  # Video uploads can take time
            )
            
            if response.status_code != 200:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get('error', {}).get('message', f"HTTP {response.status_code}")
                raise RuntimeError(f"Facebook API error: {error_msg}")
            
            result = response.json()
            
            # Facebook returns a session_id or video_id, then we need to check status
            video_id = result.get('id') or result.get('video_id')
            
            if not video_id:
                raise RuntimeError(f"Facebook API did not return video ID: {result}")
            
            # Step 3: Wait for video processing and get post_id
            # Facebook processes videos asynchronously
            post_id = None
            max_attempts = 30  # Wait up to 5 minutes (10s * 30)
            
            for attempt in range(max_attempts):
                status_url = f"{self.base_url}/{video_id}"
                status_params = {
                    'fields': 'status,permalink_url',
                    'access_token': access_token
                }
                
                status_resp = requests.get(status_url, params=status_params, timeout=10)
                
                if status_resp.status_code == 200:
                    status_data = status_resp.json()
                    video_status = status_data.get('status', {})
                    
                    # Status can be: 'processing', 'published', 'encoding_error'
                    if video_status.get('video_status') == 'ready':
                        # Get the post ID from the permalink or status
                        permalink = status_data.get('permalink_url', '')
                        if permalink:
                            # Extract post ID from permalink if possible
                            # Or use video_id as post_id
                            post_id = video_id
                        break
                    elif video_status.get('video_status') == 'encoding_error':
                        raise RuntimeError("Facebook video encoding failed")
                
                time.sleep(10)  # Wait 10 seconds before next check
            
            if not post_id:
                # Use video_id as post_id even if processing isn't complete
                post_id = video_id
            
            return {
                "status": "success",
                "post_id": post_id,
                "video_id": video_id,
                "message": "Video posted to Facebook successfully"
            }
            
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to post video to Facebook: {str(e)}")
    
    def check_post_status(self, post_id: str, access_token: str) -> Dict:
        """
        Check the status of a posted video.
        
        Args:
            post_id: The post/video ID from post_video response
            access_token: Facebook access token
        
        Returns:
            Dict with status information
        """
        status_url = f"{self.base_url}/{post_id}"
        params = {
            'fields': 'status,permalink_url,created_time',
            'access_token': access_token
        }
        
        try:
            response = requests.get(status_url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise RuntimeError(f"Failed to check post status: {e}")
