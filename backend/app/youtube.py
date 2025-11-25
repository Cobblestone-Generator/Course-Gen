from youtube_transcript_api import YouTubeTranscriptApi
from pytube import YouTube
import re

def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from URL"""
    patterns = [
        r'(?:youtube\.com\/watch\?v=|\
         youtube\.com\/embed\/|\
         youtube\.com\/v\/|\
         youtu\.be\/)([^&\n?#]+)',
        r'youtube\.com\/watch\?.*v=([^&\n?#]+)',
        r'youtube\.com\/embed\/([^&\n?#]+)',
        r'youtu\.be\/([^&\n?#]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    raise ValueError("Invalid YouTube URL")

def get_video_info(url: str) -> dict:
    """Get YouTube video information"""
    try:
        yt = YouTube(url)
        return {
            "title": yt.title,
            "description": yt.description,
            "duration": yt.length,
            "author": yt.author,
            "thumbnail_url": yt.thumbnail_url
        }
    except Exception as e:
        raise Exception(f"Error getting video info: {str(e)}")

def get_video_transcript(url: str) -> str:
    """Get YouTube video transcript"""
    try:
        video_id = extract_video_id(url)
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['ru', 'en'])
        
        # Combine all transcript parts
        full_transcript = " ".join([item['text'] for item in transcript_list])
        return full_transcript
    
    except Exception as e:
        # If no transcript available, return empty string
        print(f"Transcript not available: {str(e)}")
        return ""