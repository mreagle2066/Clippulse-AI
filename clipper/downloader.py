import os
import re
import shutil
import subprocess
import json
from typing import Dict, Any, Optional, Callable
import yt_dlp

def get_ffmpeg_path():
    return shutil.which("ffmpeg") or os.path.join(os.path.dirname(os.path.dirname(__file__)), "bin", "ffmpeg")

def get_ffprobe_path():
    return shutil.which("ffprobe") or os.path.join(os.path.dirname(os.path.dirname(__file__)), "bin", "ffprobe")

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
    def has_audio_stream(video_path: str) -> bool:
        """Check if video file contains at least one audio stream."""
        cmd = [
            get_ffprobe_path(), "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_type",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return bool(res.stdout.strip())
        except Exception:
            return False

    @staticmethod
    def extract_audio(video_path: str, output_path: Optional[str] = None, duration: float = 0.0) -> str:
        """
        Extract compressed MP3 audio from a video file for ultra-fast upload to Gemini.
        If the video has no audio stream, generates a silent placeholder so FFmpeg never crashes.
        """
        if output_path is None:
            base, _ = os.path.splitext(video_path)
            output_path = f"{base}_audio.mp3"

        if VideoDownloader.has_audio_stream(video_path):
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
        else:
            t = duration if duration > 0 else 10.0
            cmd = [
                get_ffmpeg_path(), "-y",
                "-f", "lavfi",
                "-i", "anullsrc=r=24000:cl=mono",
                "-t", str(t),
                "-acodec", "libmp3lame",
                "-b:a", "48k",
                output_path
            ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return output_path

    @staticmethod
    def prepare_media_for_analysis(video_path: str, duration: float = 0.0) -> str:
        """
        Returns the best media format for Gemini multimodal analysis:
        - If audio exists: extracts ultra-compact 24kHz mono MP3 (~3MB)
        - If silent / video-only: uses video directly (or a 480p proxy if video > 60MB)
        """
        if VideoDownloader.has_audio_stream(video_path):
            return VideoDownloader.extract_audio(video_path, duration=duration)

        # Silent or video-only file:
        file_size = os.path.getsize(video_path)
        if file_size <= 60 * 1024 * 1024:
            return video_path

        base, _ = os.path.splitext(video_path)
        proxy_path = f"{base}_proxy_480p.mp4"
        if not os.path.exists(proxy_path):
            cmd = [
                get_ffmpeg_path(), "-y",
                "-i", video_path,
                "-vf", "scale=-2:480",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "30",
                "-an",
                proxy_path
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return proxy_path
