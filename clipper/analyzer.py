import os
import time
import json
import re
import uuid
import mimetypes
import requests
from typing import List, Dict, Any, Optional, Callable
from .schemas import Moment

SYSTEM_PROMPT = """You are an elite short-form content strategist and viral video editor (specializing in YouTube Shorts, TikTok, and Instagram Reels).
Your job is to analyze this video/audio media and identify the most viral, captivating, and high-retention moments.

For each highlight moment:
1. THE HOOK: The first 3-5 seconds MUST grab attention immediately (e.g., a provocative question, shocking claim, powerful insight, hilarious reaction, or mystery).
2. THE PAYOFF: Contains a self-contained story, lesson, punchline, or debate that provides value or entertainment.
3. NATURAL BOUNDARIES: Start right before the hook phrase begins, and end right as the thought completes (do NOT cut off mid-word or mid-sentence).
4. DURATION: Each clip MUST be between {min_duration} and {max_duration} seconds long.
5. NO OVERLAPPING: Each clip should be distinct and not significantly overlap with other clips.

Identify up to {max_clips} best moments.

Return ONLY a valid, strictly parseable JSON array of objects with realistic values matching this example format (NO COMMENTS, NO TRAILING COMMAS):
[
  {{
    "start_time": 12.5,
    "end_time": 48.0,
    "title": "Shocking Revelation That Changed History",
    "hook": "Nobody expected this single decision to redirect the entire world...",
    "summary": "Explains how a surprise turning point completely altered historical outcomes.",
    "virality_score": 94,
    "suggested_caption": "Did you know this actually happened? 🤯 Watch till the end!",
    "hashtags": ["#Shorts", "#History", "#Viral", "#Trending"]
  }}
]
"""

class VideoAnalyzer:
    """Analyzes video or audio media using Google Gemini Multimodal API to pinpoint viral moments."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Gemini API key is required. Set GEMINI_API_KEY environment variable or pass api_key."
            )

    def analyze_media(
        self,
        media_path: str,
        video_duration: float,
        min_duration: int = 15,
        max_duration: int = 60,
        max_clips: int = 5,
        focus_prompt: Optional[str] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> List[Moment]:
        """
        Uploads media to Gemini File API and prompts Gemini to identify viral moments.
        """
        if progress_callback:
            progress_callback(10.0, "Uploading media to Gemini API for multimodal analysis...")

        # Build prompt
        prompt = SYSTEM_PROMPT.format(
            min_duration=min_duration,
            max_duration=max_duration,
            max_clips=max_clips
        )
        if focus_prompt and focus_prompt.strip():
            prompt += f"\n\nSPECIAL FOCUS INSTRUCTION FROM USER:\nPrioritize moments that match: {focus_prompt.strip()}"

        prompt += f"\n\nNOTE: The total media duration is {video_duration:.1f} seconds. All timestamps must be within 0.0 and {video_duration:.1f}."

        raw_json_text = self._call_gemini(media_path, prompt, progress_callback)

        if progress_callback:
            progress_callback(80.0, "Parsing viral moments and generating clip timelines...")

        moments = self._parse_and_validate(raw_json_text, video_duration, min_duration, max_duration)
        return moments

    def _call_gemini(
        self,
        media_path: str,
        prompt: str,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> str:
        """Upload media to Gemini File API via direct REST and generate viral moments."""
        mime_type = mimetypes.guess_type(media_path)[0] or "audio/mp3"
        file_size = os.path.getsize(media_path)

        if progress_callback:
            progress_callback(20.0, "Uploading media file directly to Google Gemini API...")

        # 1. Resumable Upload Init (with retry guard)
        init_url = f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={self.api_key}"
        headers = {
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(file_size),
            "X-Goog-Upload-Header-Content-Type": mime_type,
            "Content-Type": "application/json"
        }
        init_res = None
        for attempt in range(3):
            try:
                init_res = requests.post(init_url, headers=headers, json={"file": {"display_name": os.path.basename(media_path)}}, timeout=30)
                if init_res.status_code == 200:
                    break
            except Exception as e:
                if attempt == 2:
                    raise RuntimeError(f"SSL/Network error initializing upload with Gemini: {e}")
                time.sleep(2)

        if not init_res or init_res.status_code != 200:
            err_msg = init_res.text if init_res else "No response"
            raise RuntimeError(f"Failed to initialize media upload with Gemini: {err_msg}")

        upload_url = init_res.headers.get("X-Goog-Upload-URL")
        if not upload_url:
            raise RuntimeError("No upload URL returned by Gemini Files API.")

        # 2. Upload Binary Data
        if progress_callback:
            progress_callback(40.0, "Sending media stream to Gemini...")

        upload_headers = {
            "Content-Length": str(file_size),
            "X-Goog-Upload-Offset": "0",
            "X-Goog-Upload-Command": "upload, finalize"
        }

        up_res = None
        for attempt in range(3):
            try:
                with open(media_path, "rb") as f:
                    up_res = requests.post(
                        upload_url,
                        headers=upload_headers,
                        data=f,
                        timeout=(30, 300)
                    )
                if up_res.status_code == 200:
                    break
            except Exception as e:
                if attempt == 2:
                    raise RuntimeError(f"Network write timeout uploading audio to Gemini: {e}")
                time.sleep(2)

        if not up_res or up_res.status_code != 200:
            err_text = up_res.text if up_res else "No response"
            raise RuntimeError(f"Failed to upload media to Gemini: {err_text}")

        file_info = up_res.json()["file"]
        file_uri = file_info["uri"]
        file_name = file_info["name"]

        # 3. Poll processing state if needed
        if progress_callback:
            progress_callback(55.0, "Verifying media processing...")

        for _ in range(30):
            check_url = f"https://generativelanguage.googleapis.com/v1beta/{file_name}?key={self.api_key}"
            check_res = requests.get(check_url, timeout=15)
            if check_res.status_code == 200:
                state = check_res.json().get("state")
                if state == "ACTIVE":
                    break
                elif state == "FAILED":
                    raise RuntimeError("Gemini failed to process uploaded media file.")
            time.sleep(2)

        # 4. Generate Content with active models
        if progress_callback:
            progress_callback(65.0, "Gemini is analyzing audio hooks & high-retention moments...")

        model_candidates = ["gemini-3-flash-preview", "gemini-3.5-flash", "gemini-3.8-flash", "gemini-flash-latest"]
        last_err = None

        for model in model_candidates:
            gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
            payload = {
                "contents": [{
                    "parts": [
                        {"file_data": {"mime_type": mime_type, "file_uri": file_uri}},
                        {"text": prompt}
                    ]
                }],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "maxOutputTokens": 8192
                }
            }
            try:
                r = requests.post(gen_url, json=payload, timeout=180)
                if r.status_code == 200:
                    data = r.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                else:
                    last_err = f"Model {model} returned HTTP {r.status_code}: {r.text[:200]}"
            except Exception as e:
                last_err = str(e)
                continue

        raise RuntimeError(f"All Gemini models failed to analyze media: {last_err}")

    def _parse_and_validate(
        self,
        raw_text: str,
        total_duration: float,
        min_duration: int,
        max_duration: int
    ) -> List[Moment]:
        """Parses JSON text and validates boundaries with multi-layer sanitization."""
        clean_text = raw_text.strip()
        # Strip markdown code blocks
        clean_text = re.sub(r'^```(?:json)?\s*', '', clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'\s*```$', '', clean_text)
        # Strip JS single-line comments // ...
        clean_text = re.sub(r'//.*?(?=\n|$)', '', clean_text)
        # Strip JS multi-line comments /* ... */
        clean_text = re.sub(r'/\*.*?\*/', '', clean_text, flags=re.DOTALL)
        # Strip trailing commas before closing braces/brackets
        clean_text = re.sub(r',\s*([\]}])', r'\1', clean_text)
        clean_text = clean_text.strip()

        data = None
        try:
            data = json.loads(clean_text)
        except Exception:
            # Try regex extract between outer [ and ] or { and }
            match = re.search(r'(\[.*\]|\{.*\})', clean_text, re.DOTALL)
            if match:
                candidate = match.group(1).strip()
                candidate = re.sub(r'//.*?(?=\n|$)', '', candidate)
                candidate = re.sub(r',\s*([\]}])', r'\1', candidate)
                try:
                    data = json.loads(candidate)
                except Exception:
                    pass

        if data is None:
            raise ValueError(f"Could not parse Gemini JSON response: {clean_text[:200]}...")

        if not isinstance(data, list):
            if isinstance(data, dict):
                for key in ["moments", "clips", "highlights", "data"]:
                    if key in data and isinstance(data[key], list):
                        data = data[key]
                        break
                else:
                    data = [data]
            else:
                data = [data]

        moments: List[Moment] = []
        for idx, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            try:
                start = float(item.get("start_time", 0.0))
                end = float(item.get("end_time", 0.0))

                # Boundary guards
                if start < 0:
                    start = 0.0
                if total_duration > 0 and end > total_duration:
                    end = total_duration

                duration = end - start
                if duration < 5:
                    continue  # Too short

                # Format timestamps
                start_formatted = self._format_timestamp(start)
                end_formatted = self._format_timestamp(end)

                moment = Moment(
                    id=str(uuid.uuid4())[:8],
                    start_time=round(start, 2),
                    end_time=round(end, 2),
                    start_formatted=start_formatted,
                    end_formatted=end_formatted,
                    duration=round(duration, 1),
                    title=str(item.get("title", f"Highlight #{idx + 1}")).strip(),
                    hook=str(item.get("hook", "")).strip(),
                    summary=str(item.get("summary", "")).strip(),
                    virality_score=int(item.get("virality_score", 85)),
                    suggested_caption=str(item.get("suggested_caption", "")).strip(),
                    hashtags=item.get("hashtags", ["#Shorts", "#Viral", "#Trending"])
                )
                moments.append(moment)
            except Exception as e:
                print(f"Skipping malformed moment item: {e}")
                continue

        # Sort moments by virality score descending
        moments.sort(key=lambda m: m.virality_score, reverse=True)
        return moments

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        """Converts seconds to MM:SS or HH:MM:SS."""
        secs = int(seconds)
        hours = secs // 3600
        minutes = (secs % 3600) // 60
        rem_secs = secs % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{rem_secs:02d}"
        return f"{minutes:02d}:{rem_secs:02d}"
