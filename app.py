import os
import shutil
import uuid
import zipfile
import threading
import subprocess
from typing import Dict, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from clipper.schemas import TaskStatus, Moment, ProcessRequest
from clipper.downloader import VideoDownloader
from clipper.analyzer import VideoAnalyzer
from clipper.video_processor import VideoProcessor

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BIN_DIR = os.path.join(BASE_DIR, "bin")
if os.path.exists(BIN_DIR) and BIN_DIR not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{BIN_DIR}:{os.environ.get('PATH', '')}"

STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = FastAPI(title="AI Video Clipping Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory task registry
TASKS: Dict[str, TaskStatus] = {}

def check_system_deps():
    """Verify ffmpeg and yt-dlp availability."""
    ffmpeg_ok = shutil.which("ffmpeg") is not None
    api_key_ok = bool(os.getenv("GEMINI_API_KEY"))
    return {
        "ffmpeg": ffmpeg_ok,
        "gemini_api_key": api_key_ok,
    }

def run_pipeline(
    task_id: str,
    source_type: str,
    source_path_or_url: str,
    style: str,
    min_duration: int,
    max_duration: int,
    max_clips: int,
    focus_prompt: Optional[str] = None,
    api_key: Optional[str] = None
):
    """Background task executing download, Gemini analysis, and video clipping."""
    task = TASKS[task_id]
    task_out_dir = os.path.join(OUTPUT_DIR, task_id)
    os.makedirs(task_out_dir, exist_ok=True)

    try:
        gemini_key = api_key or os.getenv("GEMINI_API_KEY")
        if not gemini_key:
            raise ValueError("GEMINI_API_KEY is not configured. Please supply an API key.")

        # Phase 1: Ingest video
        task.status = "downloading"
        task.progress = 10
        task.message = "Ingesting media..."

        if source_type == "url":
            task.message = "Downloading video from YouTube..."
            def dl_progress(p, msg):
                task.progress = int(10 + (p * 0.25))  # 10% to 35%
                task.message = msg

            meta = VideoDownloader.download_video(
                source_path_or_url,
                task_out_dir,
                progress_callback=dl_progress
            )
            video_path = meta['file_path']
            task.video_title = meta.get('title', 'YouTube Video')
            task.video_duration = float(meta.get('duration', 0))
            task.video_author = meta.get('uploader', 'Unknown')
            task.thumbnail_url = meta.get('thumbnail')
        else:
            video_path = source_path_or_url
            task.video_title = os.path.splitext(os.path.basename(video_path))[0]
            # Probe duration
            ffprobe_bin = shutil.which("ffprobe") or os.path.join(BIN_DIR, "ffprobe")
            probe = subprocess.run([
                ffprobe_bin, "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", video_path
            ], stdout=subprocess.PIPE, text=True)
            task.video_duration = float(probe.stdout.strip() or 0.0)

        # Phase 2: Audio extraction for lightweight Gemini multimodal analysis
        task.status = "analyzing"
        task.progress = 40
        task.message = "Extracting audio track for fast multimodal processing..."
        audio_path = VideoDownloader.extract_audio(video_path)

        # Phase 3: Gemini Analysis
        task.message = "Google Gemini is analyzing video hooks and virality..."
        def analyzer_progress(p, msg):
            task.progress = int(40 + (p * 0.35))  # 40% to 75%
            task.message = msg

        analyzer = VideoAnalyzer(api_key=gemini_key)
        moments = analyzer.analyze_media(
            media_path=audio_path,
            video_duration=task.video_duration or 0.0,
            min_duration=min_duration,
            max_duration=max_duration,
            max_clips=max_clips,
            focus_prompt=focus_prompt,
            progress_callback=analyzer_progress
        )

        if not moments:
            raise ValueError("No highlight moments were detected. Try adjusting clip duration or topic.")

        task.moments = moments

        # Phase 4: Render Clips
        task.status = "clipping"
        task.message = f"Rendering {len(moments)} vertical clips..."
        total_m = len(moments)

        for i, moment in enumerate(task.moments):
            task.progress = int(75 + ((i / total_m) * 23))
            task.message = f"Clipping highlight {i + 1} of {total_m}: {moment.title[:30]}..."

            clip_filename = f"clip_{i+1}_{moment.id}_{style}.mp4"
            clip_path = os.path.join(task_out_dir, clip_filename)
            thumb_filename = f"thumb_{i+1}_{moment.id}.jpg"
            thumb_path = os.path.join(task_out_dir, thumb_filename)

            VideoProcessor.render_clip(
                input_video_path=video_path,
                output_clip_path=clip_path,
                start_time=moment.start_time,
                end_time=moment.end_time,
                style=style
            )

            # Generate preview thumbnail
            try:
                VideoProcessor.generate_thumbnail(
                    clip_path,
                    thumb_path,
                    timestamp=min(1.0, moment.duration / 2)
                )
                moment.thumbnail_url = f"/api/media/{task_id}/{thumb_filename}"
            except Exception:
                pass

            moment.clip_path = clip_path
            moment.clip_url = f"/api/media/{task_id}/{clip_filename}"

        task.status = "completed"
        task.progress = 100
        task.message = f"Done! {len(moments)} viral clips generated successfully."

    except Exception as e:
        task.status = "failed"
        task.error = str(e)
        task.message = f"Error: {str(e)}"
        print(f"[TASK {task_id} FAILED]: {e}")

@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/api/system")
def get_system_status():
    deps = check_system_deps()
    return JSONResponse(deps)

@app.post("/api/process/url")
def process_url(
    req: ProcessRequest,
    background_tasks: BackgroundTasks
):
    if not req.youtube_url:
        raise HTTPException(status_code=400, detail="YouTube URL is required.")

    task_id = str(uuid.uuid4())[:8]
    task = TaskStatus(task_id=task_id)
    TASKS[task_id] = task

    background_tasks.add_task(
        run_pipeline,
        task_id=task_id,
        source_type="url",
        source_path_or_url=req.youtube_url,
        style=req.style,
        min_duration=req.min_duration,
        max_duration=req.max_duration,
        max_clips=req.max_clips,
        focus_prompt=req.focus_prompt,
        api_key=req.api_key
    )

    return {"task_id": task_id, "status": "queued"}

@app.post("/api/process/upload")
async def process_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    style: str = Form("vertical_fit"),
    min_duration: int = Form(15),
    max_duration: int = Form(60),
    max_clips: int = Form(5),
    focus_prompt: Optional[str] = Form(None),
    api_key: Optional[str] = Form(None)
):
    task_id = str(uuid.uuid4())[:8]
    task = TaskStatus(task_id=task_id)
    TASKS[task_id] = task

    task_upload_dir = os.path.join(UPLOADS_DIR, task_id)
    os.makedirs(task_upload_dir, exist_ok=True)
    file_path = os.path.join(task_upload_dir, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    background_tasks.add_task(
        run_pipeline,
        task_id=task_id,
        source_type="upload",
        source_path_or_url=file_path,
        style=style,
        min_duration=min_duration,
        max_duration=max_duration,
        max_clips=max_clips,
        focus_prompt=focus_prompt,
        api_key=api_key
    )

    return {"task_id": task_id, "status": "queued"}

@app.get("/api/tasks/{task_id}")
def get_task(task_id: str):
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
    return TASKS[task_id]

@app.get("/api/media/{task_id}/{filename}")
def serve_media(task_id: str, filename: str):
    file_path = os.path.join(OUTPUT_DIR, task_id, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Media file not found")
    return FileResponse(file_path)

@app.get("/api/download-all/{task_id}")
def download_all_clips(task_id: str):
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")

    task = TASKS[task_id]
    task_out_dir = os.path.join(OUTPUT_DIR, task_id)
    zip_path = os.path.join(OUTPUT_DIR, f"{task_id}_all_clips.zip")

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Include summary readme with captions and hashtags
        summary_lines = [
            f"Clips for: {task.video_title or 'Video'}",
            f"Generated: {len(task.moments)} viral clips\n",
            "=" * 50 + "\n"
        ]

        for idx, m in enumerate(task.moments, 1):
            if m.clip_path and os.path.exists(m.clip_path):
                zipf.write(m.clip_path, arcname=os.path.basename(m.clip_path))

            summary_lines.append(f"CLIP #{idx}: {m.title}")
            summary_lines.append(f"Timestamp: {m.start_formatted} - {m.end_formatted}")
            summary_lines.append(f"Hook: {m.hook}")
            summary_lines.append(f"Caption:\n{m.suggested_caption}")
            summary_lines.append(f"Hashtags: {' '.join(m.hashtags)}")
            summary_lines.append("-" * 40 + "\n")

        zipf.writestr("social_captions_and_info.txt", "\n".join(summary_lines))

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"viral_clips_{task_id}.zip"
    )

# Mount static assets
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"\n🚀 Starting Video Clipping Engine Web UI on port {port} ...")
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
