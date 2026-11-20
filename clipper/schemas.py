from pydantic import BaseModel, Field
from typing import List, Optional
import time

class Moment(BaseModel):
    id: str
    start_time: float = Field(..., description="Start timestamp in seconds")
    end_time: float = Field(..., description="End timestamp in seconds")
    start_formatted: str = Field(..., description="Start time formatted (MM:SS)")
    end_formatted: str = Field(..., description="End time formatted (MM:SS)")
    duration: float = Field(..., description="Clip duration in seconds")
    title: str = Field(..., description="Catchy title for the clip")
    hook: str = Field(..., description="First 3-5s opening hook of this moment")
    summary: str = Field(..., description="What happens in this clip")
    virality_score: int = Field(default=80, ge=1, le=100, description="Predicted virality score (1-100)")
    suggested_caption: str = Field(default="", description="Social media caption")
    hashtags: List[str] = Field(default_factory=list, description="Relevant hashtags for Shorts/TikTok")
    clip_path: Optional[str] = None
    clip_url: Optional[str] = None
    thumbnail_url: Optional[str] = None

class ProcessRequest(BaseModel):
    source_type: str = "url"  # "url" or "upload"
    youtube_url: Optional[str] = None
    style: str = "vertical_fit"  # "vertical_fit", "vertical_blur", "vertical_crop", "landscape"
    min_duration: int = 15
    max_duration: int = 60
    max_clips: int = Field(default=5, ge=1, le=50, description="Max viral moments to extract")
    focus_prompt: Optional[str] = None
    api_key: Optional[str] = None

class TaskStatus(BaseModel):
    task_id: str
    status: str = "queued"  # queued, downloading, analyzing, clipping, completed, failed
    progress: int = 0
    message: str = "Initializing task..."
    video_title: Optional[str] = None
    video_duration: Optional[float] = None
    video_author: Optional[str] = None
    thumbnail_url: Optional[str] = None
    moments: List[Moment] = Field(default_factory=list)
    error: Optional[str] = None
    created_at: float = Field(default_factory=time.time)
