import os
import shutil
import subprocess
from typing import Optional, Tuple

def get_ffmpeg_path():
    return shutil.which("ffmpeg") or os.path.join(os.path.dirname(os.path.dirname(__file__)), "bin", "ffmpeg")

class VideoProcessor:
    """Handles cutting video clips and reformatting to vertical 9:16 or horizontal formats using FFmpeg."""

    @staticmethod
    def render_clip(
        input_video_path: str,
        output_clip_path: str,
        start_time: float,
        end_time: float,
        style: str = "vertical_blur",
        target_resolution: Tuple[int, int] = (1080, 1920)
    ) -> str:
        """
        Renders a trimmed video clip formatted for social media.
        Styles:
          - 'vertical_blur': 9:16 canvas with blurred background and centered foreground (best for podcasts/talks).
          - 'vertical_crop': 9:16 center-cropped fill.
          - 'landscape': original aspect ratio trimmed cleanly.
        """
        os.makedirs(os.path.dirname(output_clip_path), exist_ok=True)
        duration = end_time - start_time
        width, height = target_resolution

        if style == "vertical_blur":
            # 9:16 blurred background + centered crisp foreground
            filter_complex = (
                f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},"
                f"boxblur=25:5,"
                f"eq=brightness=-0.1[bg];"
                f"[0:v]scale={width}:-2[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2[v]"
            )
            cmd = [
                get_ffmpeg_path(), "-y",
                "-ss", str(start_time),
                "-t", str(duration),
                "-i", input_video_path,
                "-filter_complex", filter_complex,
                "-map", "[v]",
                "-map", "0:a?",
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "22",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                output_clip_path
            ]

        elif style in ("vertical_fit", "vertical_letterbox", "fit_9_16"):
            # 9:16 vertical canvas (1080x1920) with full uncropped 16:9 scene centered + clean black bars (Classic TikTok/Shorts clip style)
            filter_vf = (
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
                f"setsar=1"
            )
            cmd = [
                get_ffmpeg_path(), "-y",
                "-ss", str(start_time),
                "-t", str(duration),
                "-i", input_video_path,
                "-vf", filter_vf,
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "22",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                output_clip_path
            ]

        elif style == "vertical_crop":
            # 9:16 center crop
            filter_vf = f"scale=-2:{height},crop={width}:{height}"
            cmd = [
                get_ffmpeg_path(), "-y",
                "-ss", str(start_time),
                "-t", str(duration),
                "-i", input_video_path,
                "-vf", filter_vf,
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "22",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                output_clip_path
            ]

        else:
            # Landscape / original aspect ratio
            cmd = [
                get_ffmpeg_path(), "-y",
                "-ss", str(start_time),
                "-t", str(duration),
                "-i", input_video_path,
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "21",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                output_clip_path
            ]

        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if process.returncode != 0:
            raise RuntimeError(f"FFmpeg error: {process.stderr[-500:]}")

        return output_clip_path

    @staticmethod
    def generate_thumbnail(
        video_path: str,
        output_image_path: str,
        timestamp: float = 1.0
    ) -> str:
        """Extract a single frame as JPEG thumbnail for clip preview."""
        os.makedirs(os.path.dirname(output_image_path), exist_ok=True)
        cmd = [
            get_ffmpeg_path(), "-y",
            "-ss", str(timestamp),
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            output_image_path
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return output_image_path
