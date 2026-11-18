import os
import re
import shutil
import subprocess
import json
from typing import Dict, Any, Optional, Callable
import yt_dlp

def get_ffmpeg_path():
    return shutil.which("ffmpeg") or os.path.join(os.path.dirname(os.path.dirname(__file__)), "bin", "ffmpeg")

class VideoDownloader:
    """Handles downloading YouTube videos and extracting metadata using yt-dlp."""

    @staticmethod
    def get_info(url: str) -> Dict[str, Any]:
        """Fetch video metadata without downloading the full video."""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'socket_timeout': 30,
            'retries': 10,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web']
                }
            },
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'id': info.get('id', ''),
                'title': info.get('title', 'Untitled Video'),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'Unknown'),
                'thumbnail': info.get('thumbnail', ''),
                'view_count': info.get('view_count', 0),
            }

    @staticmethod
    def download_video(
        url: str,
        output_dir: str,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Download video at best resolution up to 1080p in MP4 format.
        Returns metadata and output file path.
        """
        os.makedirs(output_dir, exist_ok=True)
        out_template = os.path.join(output_dir, '%(id)s_full.%(ext)s')

        def ydl_hook(d):
            if d['status'] == 'downloading':
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes', 0)
                if total_bytes > 0 and progress_callback:
                    percent = (downloaded / total_bytes) * 100
                    progress_callback(percent, f"Downloading video: {percent:.1f}%")
            elif d['status'] == 'finished':
                if progress_callback:
                    progress_callback(100.0, "Download completed. Processing video...")

        ydl_opts = {
            'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[ext=mp4]/18/best',
            'outtmpl': out_template,
            'merge_output_format': 'mp4',
            'progress_hooks': [ydl_hook],
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web']
                }
            },
            'socket_timeout': 60,
            'retries': 25,
            'fragment_retries': 25,
            'file_access_retries': 10,
            'extractor_retries': 10,
            'continuedl': True,
            'http_chunk_size': 5242880,
            'quiet': True,
            'no_warnings': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info.get('id', 'video')
            final_path = os.path.join(output_dir, f"{video_id}_full.mp4")

            # Fallback check if file exists with another extension
            if not os.path.exists(final_path):
                expected = ydl.prepare_filename(info)
                if os.path.exists(expected):
                    final_path = expected

            return {
                'id': video_id,
                'title': info.get('title', 'Untitled Video'),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'Unknown'),
                'thumbnail': info.get('thumbnail', ''),
                'file_path': final_path
            }

    @staticmethod
    def extract_audio(video_path: str, output_path: Optional[str] = None) -> str:
        """
        Extract compressed MP3 audio from a video file for ultra-fast upload to Gemini.
        """
        if output_path is None:
            base, _ = os.path.splitext(video_path)
            output_path = f"{base}_audio.mp3"

        cmd = [
            get_ffmpeg_path(), "-y",
            "-i", video_path,
            "-vn",
            "-acodec", "libmp3lame",
            "-ar", "24000",
            "-ac", "1",
            "-b:a", "48k",
            output_path
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return output_path
