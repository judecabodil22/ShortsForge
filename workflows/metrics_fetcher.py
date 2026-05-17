#!/usr/bin/env python3
"""
ShortsForge Metrics Fetcher
Fetches video performance metrics from YouTube Data API v3.
"""
import os
import re
import json
import time
import logging
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List, Any

WORKSPACE = os.path.expanduser("~/ShortsForge")
CLIENT_SECRETS_FILE = os.path.join(WORKSPACE, "client_secret.json")
OAUTH_CREDENTIALS_FILE = os.path.join(WORKSPACE, ".shortsforge", "youtube_oauth.json")
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass


def get_api_key() -> str:
    """Get YouTube API key."""
    key = os.getenv("YOUTUBE_API_KEY", "")
    if not key:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(WORKSPACE, ".env"))
        key = os.getenv("YOUTUBE_API_KEY", "")
    return key


def _get_oauth_credentials() -> Optional[Any]:
    """Load OAuth credentials from file, return None if not found or invalid."""
    if not os.path.exists(OAUTH_CREDENTIALS_FILE):
        return None
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        creds = Credentials.from_authorized_user_file(OAUTH_CREDENTIALS_FILE, SCOPES)
        if creds and creds.valid:
            return creds
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _save_oauth_credentials(creds)
            return creds
    except Exception:
        pass
    return None


def _save_oauth_credentials(creds: Any) -> None:
    """Save OAuth credentials to file."""
    os.makedirs(os.path.dirname(OAUTH_CREDENTIALS_FILE), exist_ok=True)
    creds_str = creds.to_json()
    with open(OAUTH_CREDENTIALS_FILE, "w") as f:
        f.write(creds_str)


def _get_oauth_service():
    """Get authenticated YouTube service using OAuth2."""
    creds = _get_oauth_credentials()
    if not creds:
        raise RuntimeError("OAuth not configured")
    
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_oauth_credentials(creds)
    
    return build("youtube", "v3", credentials=creds)


def authenticate_oauth(port: int = 8080, open_browser: bool = True) -> bool:
    """Run OAuth2 authentication flow. Returns True on success, False on failure."""
    if not os.path.exists(CLIENT_SECRETS_FILE):
        log.error("client_secret.json not found in workspace")
        return False
    
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
        
        if open_browser:
            creds = flow.run_local_server(port=port, open_browser=True)
        else:
            creds = flow.run_local_server(port=port, open_browser=False)
        
        _save_oauth_credentials(creds)
        log.info("OAuth2 authentication successful")
        return True
        
    except Exception as e:
        log.error(f"OAuth2 authentication failed: {e}")
        return False


def is_oauth_configured() -> bool:
    """Check if OAuth credentials exist and are valid."""
    if not os.path.exists(OAUTH_CREDENTIALS_FILE):
        return False
    try:
        with open(OAUTH_CREDENTIALS_FILE, 'r') as f:
            data = json.load(f)
            return bool(data.get('token') or data.get('refresh_token'))
    except Exception:
        return False


def get_video_id_from_url(url: str) -> Optional[str]:
    """Extract YouTube video ID from URL."""
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    if re.match(r'^[a-zA-Z0-9_-]{11}$', url):
        return url
    
    return None


def fetch_video_metadata(video_id: str) -> Optional[Dict[str, Any]]:
    """Fetch video metadata from YouTube Data API."""
    api_key = get_api_key()
    if not api_key:
        return None
    
    url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics,contentDetails&id={video_id}&key={api_key}"
    
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
        
        if data.get('items') and len(data['items']) > 0:
            return data['items'][0]
        return None
        
    except Exception:
        return None


def fetch_metrics(video_id: str) -> Optional[Dict[str, Any]]:
    """Fetch public metrics for a YouTube video."""
    api_key = get_api_key()
    if not api_key:
        return None
    
    url = f"https://www.googleapis.com/youtube/v3/videos?part=statistics&id={video_id}&key={api_key}"
    
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
        
        if not data.get('items') or len(data['items']) == 0:
            return None
        
        stats = data['items'][0]['statistics']
        
        views = int(stats.get('viewCount', 0))
        likes = int(stats.get('likeCount', 0))
        comments = int(stats.get('commentCount', 0))
        favorites = int(stats.get('favoriteCount', 0))
        
        total_engagement = likes + comments
        engagement_ratio = (total_engagement / views * 100) if views > 0 else 0
        
        return {
            'video_id': video_id,
            'views': views,
            'likes': likes,
            'comments': comments,
            'favorites': favorites,
            'engagement_ratio': round(engagement_ratio, 4),
            'fetched_at': datetime.now(timezone.utc).isoformat()
        }
        
    except Exception:
        return None


def search_channel_videos(channel_id: str = None, max_results: int = 50) -> List[Dict]:
    """Search for videos on a YouTube channel."""
    api_key = get_api_key()
    if not api_key:
        return []
    
    if not channel_id:
        channel_id = get_own_channel_id()
        if not channel_id:
            return []
    
    url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&channelId={channel_id}&type=video&order=date&maxResults={max_results}&key={api_key}"
    
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
        
        videos = []
        for item in data.get('items', []):
            if item['id']['kind'] == 'youtube#video':
                videos.append({
                    'video_id': item['id']['videoId'],
                    'title': item['snippet']['title'],
                    'published_at': item['snippet']['publishedAt'],
                    'thumbnail': item['snippet']['thumbnails'].get('default', {}).get('url')
                })
        
        return videos
        
    except Exception:
        return []


def get_own_channel_id() -> Optional[str]:
    """Get the authenticated user's channel ID using OAuth2."""
    try:
        youtube = _get_oauth_service()
        response = youtube.channels().list(
            mine=True,
            part='id,snippet'
        ).execute()
        
        if response.get('items') and len(response['items']) > 0:
            channel_id = response['items'][0]['id']
            return channel_id
        return None
        
    except Exception as e:
        log.warning(f"Could not get channel ID via OAuth: {e}")
        return None


def get_recent_uploads(days: int = 7, max_results: int = 50) -> List[Dict[str, Any]]:
    """Get recent video uploads from user's channel using OAuth2.
    
    Args:
        days: Number of days to look back (default 7)
        max_results: Maximum number of videos to return (default 50)
    
    Returns:
        List of dicts with video_id, title, published_at, thumbnail, views, likes, comments
    """
    try:
        youtube = _get_oauth_service()
        
        channels_response = youtube.channels().list(
            mine=True,
            part='contentDetails'
        ).execute()
        
        uploads_playlist_id = None
        for channel in channels_response.get('items', []):
            uploads_playlist_id = channel['contentDetails']['relatedPlaylists']['uploads']
            break
        
        if not uploads_playlist_id:
            return []
        
        published_after = datetime.now(timezone.utc) - timedelta(days=days)
        published_after_iso = published_after.strftime('%Y-%m-%dT%H:%M:%SZ')
        
        videos = []
        next_page_token = None
        
        while len(videos) < max_results:
            playlist_params = {
                'playlistId': uploads_playlist_id,
                'part': 'snippet',
                'maxResults': min(50, max_results - len(videos)),
            }
            if next_page_token:
                playlist_params['pageToken'] = next_page_token
            
            playlist_response = youtube.playlistItems().list(**playlist_params).execute()
            
            for item in playlist_response.get('items', []):
                snippet = item.get('snippet', {})
                published_at = snippet.get('publishedAt', '')
                
                if published_at < published_after_iso:
                    return videos
                
                videos.append({
                    'video_id': snippet.get('resourceId', {}).get('videoId', ''),
                    'title': snippet.get('title', ''),
                    'description': snippet.get('description', ''),
                    'published_at': published_at,
                    'thumbnail': snippet.get('thumbnails', {}).get('default', {}).get('url', ''),
                    'views': 0,
                    'likes': 0,
                    'comments': 0,
                    'engagement_ratio': 0.0,
                })
            
            next_page_token = playlist_response.get('nextPageToken')
            if not next_page_token:
                break
        
        if not videos:
            return []
        
        video_ids = [v['video_id'] for v in videos if v['video_id']]
        if not video_ids:
            return []
        
        video_chunks = [video_ids[i:i+50] for i in range(0, len(video_ids), 50)]
        
        for chunk in video_chunks:
            stats_response = youtube.videos().list(
                part='statistics,contentDetails',
                id=','.join(chunk)
            ).execute()

            stats_map = {item['id']: item['statistics'] for item in stats_response.get('items', [])}
            content_map = {item['id']: item.get('contentDetails', {}) for item in stats_response.get('items', [])}

            for video in videos:
                video_id = video['video_id']
                if video_id in stats_map:
                    stats = stats_map[video_id]
                    content = content_map.get(video_id, {})
                    views = int(stats.get('viewCount', 0))
                    likes = int(stats.get('likeCount', 0))
                    comments = int(stats.get('commentCount', 0))
                    total_engagement = likes + comments
                    engagement_ratio = (total_engagement / views * 100) if views > 0 else 0
                    duration_str = content.get('duration', 'PT0S')
                    duration_seconds = parse_duration(duration_str)
                    video['views'] = views
                    video['likes'] = likes
                    video['comments'] = comments
                    video['engagement_ratio'] = round(engagement_ratio, 4)
                    video['duration_seconds'] = duration_seconds
                    video['fetched_at'] = datetime.now(timezone.utc).isoformat()
        
        return videos
        
    except Exception as e:
        log.warning(f"Could not fetch recent uploads via OAuth: {e}")
        return []


def fetch_video_details(url_or_id: str) -> Optional[Dict[str, Any]]:
    """Fetch full details for a video from URL or ID."""
    video_id = get_video_id_from_url(url_or_id)
    if not video_id:
        return None
    
    api_key = get_api_key()
    if not api_key:
        return None
    
    url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics,contentDetails&id={video_id}&key={api_key}"
    
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
        
        if not data.get('items') or len(data['items']) == 0:
            return None
        
        item = data['items'][0]
        snippet = item['snippet']
        stats = item['statistics']
        content = item['contentDetails']
        
        views = int(stats.get('viewCount', 0))
        likes = int(stats.get('likeCount', 0))
        comments = int(stats.get('commentCount', 0))
        total_engagement = likes + comments
        engagement_ratio = (total_engagement / views * 100) if views > 0 else 0
        
        duration_str = content.get('duration', 'PT0S')
        duration_seconds = parse_duration(duration_str)
        
        return {
            'video_id': video_id,
            'title': snippet.get('title', ''),
            'description': snippet.get('description', ''),
            'published_at': snippet.get('publishedAt', ''),
            'channel_id': snippet.get('channelId', ''),
            'channel_title': snippet.get('channelTitle', ''),
            'tags': snippet.get('tags', []),
            'category_id': snippet.get('categoryId', ''),
            'views': views,
            'likes': likes,
            'comments': comments,
            'favorites': int(stats.get('favoriteCount', 0)),
            'duration_seconds': duration_seconds,
            'engagement_ratio': round(engagement_ratio, 4),
            'fetched_at': datetime.now(timezone.utc).isoformat(),
            'raw_data': item
        }
        
    except Exception:
        return None


def parse_duration(duration_str: str) -> int:
    """Parse YouTube duration string to seconds (e.g., PT1M30S -> 90)."""
    pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
    match = re.match(pattern, duration_str)
    
    if not match:
        return 0
    
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    
    return hours * 3600 + minutes * 60 + seconds


def calculate_performance_score(views: int, engagement_ratio: float, duration: int = None) -> float:
    """Calculate a combined performance score (0-100)."""
    if views == 0:
        return 0.0
    
    views_score = min(views / 100, 100) * 0.4
    engagement_score = min(engagement_ratio * 10, 100) * 0.6
    
    score = views_score + engagement_score
    
    if duration:
        optimal_duration = 45
        duration_factor = 1.0 - abs(duration - optimal_duration) / 120
        duration_factor = max(0.5, min(1.0, duration_factor))
        score = score * (0.7 + 0.3 * duration_factor)
    
    return round(score, 2)


def get_video_id_from_title(title: str, channel_id: str = None) -> Optional[str]:
    """Search for a video by title and return its ID."""
    api_key = get_api_key()
    if not api_key:
        return None
    
    if not channel_id:
        channel_id = get_own_channel_id()
        if not channel_id:
            return None
    
    query = urllib.parse.quote(title[:100])
    url = f"https://www.googleapis.com/youtube/v3/search?part=id&channelId={channel_id}&q={query}&type=video&maxResults=5&key={api_key}"
    
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
        
        for item in data.get('items', []):
            if item['id']['kind'] == 'youtube#video':
                return item['id']['videoId']
        return None
        
    except Exception:
        return None


if __name__ == "__main__":
    print("YouTube Metrics Fetcher Test")
    print("-" * 40)
    
    api_key = get_api_key()
    if api_key:
        print(f"API Key: {api_key[:20]}...{api_key[-6:]}")
    else:
        print("No API key configured")
    
    print(f"OAuth configured: {is_oauth_configured()}")
    
    print("\nTesting video ID extraction:")
    test_urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://youtube.com/shorts/dQw4w9WgXcQ",
        "dQw4w9WgXcQ"
    ]
    
    for url in test_urls:
        vid = get_video_id_from_url(url)
        print(f"  {url} -> {vid}")