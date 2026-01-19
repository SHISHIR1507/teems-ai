"""
CrewAI Tools for Social Media Posting
Synchronous tools that call TikTok API directly (no async, no HTTP self-requests)
"""

from crewai.tools import tool
import requests
import os
import psycopg2
from app.core.config import get_settings

settings = get_settings()


def refresh_tiktok_token(refresh_token: str, user_id: int) -> str:
    """
    Refresh TikTok access token using refresh token
    
    Returns:
        New access token
    """
    url = "https://open.tiktokapis.com/v2/oauth/token/"
    
    # TikTok requires application/x-www-form-urlencoded
    payload = {
        "client_key": os.getenv("TIKTOK_CLIENT_KEY"),
        "client_secret": os.getenv("TIKTOK_CLIENT_SECRET"),
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    # Use data= not json= for form encoding
    response = requests.post(url, data=payload, headers=headers, timeout=10)
    
    if response.status_code == 200:
        data = response.json()
        
        # Extract tokens with validation
        new_access_token = data.get("access_token")
        new_refresh_token = data.get("refresh_token")
        
        if not new_access_token:
            raise ValueError(f"No access_token in response: {data}")
        
        # Update database with new tokens
        conn = psycopg2.connect(settings.database_url.replace('+asyncpg', ''))
        cur = conn.cursor()
        
        cur.execute(
            """UPDATE user_tokens 
               SET access_token = %s, refresh_token = %s, updated_at = NOW() 
               WHERE user_id = %s AND platform = 'tiktok'""",
            (new_access_token, new_refresh_token, user_id)
        )
        
        conn.commit()
        cur.close()
        conn.close()
        
        return new_access_token
    else:
        raise ValueError(f"Failed to refresh token (HTTP {response.status_code}): {response.text}")


def get_tiktok_token(user_id: int) -> str:
    """Get TikTok access token for user from database (sync) with auto-refresh"""
    try:
        # Use psycopg2 for synchronous database access
        conn = psycopg2.connect(settings.database_url.replace('+asyncpg', ''))
        cur = conn.cursor()
        
        cur.execute(
            "SELECT access_token, refresh_token FROM user_tokens WHERE user_id = %s AND platform = 'tiktok'",
            (user_id,)
        )
        result = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if not result:
            raise ValueError(f"No TikTok token found for user_id {user_id}")
        
        access_token, refresh_token = result
        
        # Try using the access token first
        # If it fails, we'll catch it in the tool and refresh
        # For now, just return it - we can add expiry checking later
        return access_token
        
    except Exception as e:
        raise ValueError(f"Failed to get token: {str(e)}")


@tool
def post_to_tiktok(user_id: int, video_url: str, caption: str, hashtags: list[str] = None) -> str:
    """
    Post a video to TikTok using FILE_UPLOAD method.
    
    Use this tool when the user wants to post a video to TikTok.
    
    Args:
        user_id: User ID from the system
        video_url: Publicly accessible video URL (must be direct link to MP4)
        caption: Video caption/description
        hashtags: List of hashtags (without # symbol), optional
    
    Returns:
        Success message with TikTok publish ID
    """
    if hashtags is None:
        hashtags = []
    
    def try_post_with_file_upload(access_token):
        """Download video and upload to TikTok using FILE_UPLOAD method"""
        
        # 1. Download video
        try:
            video_resp = requests.get(video_url, stream=True, timeout=30)
            video_resp.raise_for_status()
            video_data = video_resp.content
            video_size = len(video_data)
            
            if video_size == 0:
                raise ValueError("Video file is empty")
        except Exception as e:
            raise RuntimeError(f"Failed to download video: {e}")
        
        # 2. Build caption with hashtags
        full_caption = caption
        if hashtags:
            hashtag_str = " ".join([f"#{tag}" for tag in hashtags])
            full_caption = f"{caption} {hashtag_str}" if caption else hashtag_str
        full_caption = full_caption[:150]  # TikTok limit
        
        # 3. Initialize upload
        init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8"
        }
        
        init_data = {
            "post_info": {
                "title": full_caption,
                "privacy_level": "SELF_ONLY",
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
                "video_cover_timestamp_ms": 1000
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": video_size,
                "total_chunk_count": 1
            }
        }
        
        response = requests.post(init_url, headers=headers, json=init_data, timeout=30)
        
        if response.status_code != 200:
            return response
        
        init_json = response.json()
        if 'data' not in init_json:
            return response
        
        upload_url = init_json['data']['upload_url']
        publish_id = init_json['data']['publish_id']
        
        # 4. Upload video
        upload_headers = {
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes 0-{video_size-1}/{video_size}"
        }
        
        upload_resp = requests.put(upload_url, data=video_data, headers=upload_headers, timeout=60)
        
        if upload_resp.status_code not in [200, 201]:
            raise RuntimeError(f"Upload failed: {upload_resp.text}")
        
        # Return success response with publish_id
        class MockResponse:
            status_code = 200
            def json(self):
                return {'data': {'publish_id': publish_id}}
        
        return MockResponse()
    
    try:
        # Get access token
        access_token = get_tiktok_token(user_id)
        
        # Try posting with current token
        response = try_post_with_file_upload(access_token)
        
        # Check if token is invalid
        should_refresh = False
        if response.status_code == 401:
            should_refresh = True
        elif response.status_code == 200:
            try:
                response_data = response.json()
                error_msg = response_data.get("error", {}).get("message", "")
                if "token" in error_msg.lower() and "invalid" in error_msg.lower():
                    should_refresh = True
            except:
                pass
        
        # If token is invalid, refresh and retry
        if should_refresh:
            conn = psycopg2.connect(settings.database_url.replace('+asyncpg', ''))
            cur = conn.cursor()
            cur.execute(
                "SELECT refresh_token FROM user_tokens WHERE user_id = %s AND platform = 'tiktok'",
                (user_id,)
            )
            result = cur.fetchone()
            cur.close()
            conn.close()
            
            if result and result[0]:
                new_access_token = refresh_tiktok_token(result[0], user_id)
                response = try_post_with_file_upload(new_access_token)
        
        if response.status_code == 200:
            result = response.json()
            
            if "error" in result:
                error_msg = result.get("error", {}).get("message", "Unknown error")
                return f"❌ Failed to post to TikTok: {error_msg}"
            
            publish_id = result.get("data", {}).get("publish_id", "N/A")
            hashtag_text = ' '.join(['#' + tag for tag in hashtags]) if hashtags else 'none'
            
            return f"""✅ Successfully posted to TikTok!

📝 Caption: {caption}
🏷️ Hashtags: {hashtag_text}
🆔 Publish ID: {publish_id}

Your video is now live on TikTok (private - only you can see it)!"""
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", "Unknown error")
            except:
                error_msg = f"HTTP {response.status_code}"
            return f"❌ Failed to post to TikTok: {error_msg}"
    
    except Exception as e:
        return f"❌ Failed to post to TikTok: {str(e)}"


@tool
def post_to_facebook(user_id: int, video_url: str, caption: str) -> str:
    """
    Post a video to Facebook.
    
    ** NOT YET IMPLEMENTED **
    This tool is a placeholder for future Facebook integration.
    
    Args:
        user_id: User ID from the system
        video_url: Publicly accessible video URL
        caption: Video caption/description
    
    Returns:
        Error message indicating Facebook posting is not yet available
    """
    return """❌ Facebook posting is not yet implemented.

Currently supported platforms:
✅ TikTok

Coming soon:
🔜 Facebook
🔜 Instagram
🔜 YouTube

Would you like to post to TikTok instead?"""


@tool  
def get_user_posts(user_id: int, platform: str = "tiktok") -> str:
    """
    Get a user's posting history.
    
    Args:
        user_id: User ID from the system
        platform: Platform to get posts from ("tiktok" or "facebook")
    
    Returns:
        List of user's posts
    """
    if platform.lower() != "tiktok":
        return f"❌ {platform} history not yet available. Only TikTok is supported currently."
    
    # For now, return placeholder
    # In production, query database synchronously
    return """📊 Post history coming soon!

For now, focus on posting new videos. History tracking will be added in the next update."""
