#!/usr/bin/env python3
"""
CLI tool for AI Video Clipping Engine.
Usage:
  python cli.py --url "https://www.youtube.com/watch?v=..." --style vertical_blur
  python cli.py --file "./sample.mp4" --style vertical_crop
"""

import os
import sys
import argparse
from dotenv import load_dotenv

load_dotenv()

from clipper.downloader import VideoDownloader
from clipper.analyzer import VideoAnalyzer
from clipper.video_processor import VideoProcessor

def main():
    parser = argparse.ArgumentParser(description="AI Video Clipping Engine - Auto-generate Shorts & Reels")
    parser.add_argument("--url", type=str, help="YouTube video URL")
    parser.add_argument("--file", type=str, help="Local video file path")
    parser.add_argument("--output-dir", type=str, default="./output", help="Directory to save generated clips")
    parser.add_argument("--style", type=str, default="vertical_fit", choices=["vertical_fit", "vertical_blur", "vertical_crop", "landscape"],
                        help="Video format style: vertical_fit (TikTok full scene with black bars), vertical_blur, vertical_crop, or landscape")
    parser.add_argument("--min-duration", type=int, default=15, help="Minimum clip duration in seconds")
    parser.add_argument("--max-duration", type=int, default=60, help="Maximum clip duration in seconds")
    parser.add_argument("--max-clips", type=int, default=5, help="Number of viral clips to detect")
    parser.add_argument("--focus", type=str, default=None, help="Specific focus prompt (e.g. 'funniest moments')")
    parser.add_argument("--api-key", type=str, default=None, help="Gemini API key")

    args = parser.parse_args()

    api_key = args.api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("\n[ERROR] GEMINI_API_KEY not found. Please set GEMINI_API_KEY environment variable or pass --api-key.\n")
        sys.exit(1)

    if not args.url and not args.file:
        print("\n[ERROR] Please provide either --url or --file.\n")
        parser.print_help()
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)
    cache_dir = os.path.join(args.output_dir, "cache")
    os.makedirs(cache_dir, exist_ok=True)

    print("\n🎬 ==================================================")
    print("🔥 AI VIDEO CLIPPING ENGINE (Shorts & Reels)")
    print("====================================================\n")

    video_path = ""
    duration = 0.0
    title = ""

    # Step 1: Ingest
    if args.url:
        print(f"📥 [1/4] Fetching YouTube video: {args.url}")
        meta = VideoDownloader.download_video(args.url, cache_dir,
            progress_callback=lambda p, msg: print(f"    {msg}", end="\r"))
        video_path = meta['file_path']
        duration = float(meta['duration'])
        title = meta['title']
        print(f"\n✅ Downloaded: '{title}' ({duration:.0f}s)")
    else:
        video_path = args.file
        title = os.path.splitext(os.path.basename(video_path))[0]
        # Get duration using ffprobe
        import subprocess
        probe = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", video_path
        ], stdout=subprocess.PIPE, text=True)
        duration = float(probe.stdout.strip() or 0.0)
        print(f"📁 [1/4] Loaded local video: '{title}' ({duration:.0f}s)")

    # Step 2: Extract audio for lightweight Gemini upload
    print("\n🎵 [2/4] Extracting audio track for fast AI multimodal ingestion...")
    audio_path = VideoDownloader.extract_audio(video_path)

    # Step 3: Analyze with Gemini
    print("\n🧠 [3/4] Analyzing video with Google Gemini API for high-retention hooks...")
    analyzer = VideoAnalyzer(api_key=api_key)
    moments = analyzer.analyze_media(
        media_path=audio_path,
        video_duration=duration,
        min_duration=args.min_duration,
        max_duration=args.max_duration,
        max_clips=args.max_clips,
        focus_prompt=args.focus,
        progress_callback=lambda p, msg: print(f"    {msg}")
    )

    if not moments:
        print("\n⚠️ No highlight moments identified. Try adjusting duration or focus prompt.")
        return

    print(f"\n✨ Found {len(moments)} viral moment(s)!\n")

    # Step 4: Render Clips
    print(f"✂️  [4/4] Rendering clips with style '{args.style}'...")
    for idx, moment in enumerate(moments, 1):
        print(f"\n--- Clip #{idx}: {moment.title} (Virality: {moment.virality_score}/100) ---")
        print(f"⏱️  Timestamp: {moment.start_formatted} - {moment.end_formatted} ({moment.duration:.1f}s)")
        print(f"🪝 Hook: \"{moment.hook}\"")

        safe_title = "".join(c for c in moment.title if c.isalnum() or c in (' ', '-', '_')).strip()[:40]
        out_clip_name = f"clip_{idx}_{safe_title.replace(' ', '_')}_{args.style}.mp4"
        out_clip_path = os.path.join(args.output_dir, out_clip_name)

        print(f"⚙️  Rendering -> {out_clip_name}...")
        VideoProcessor.render_clip(
            input_video_path=video_path,
            output_clip_path=out_clip_path,
            start_time=moment.start_time,
            end_time=moment.end_time,
            style=args.style
        )
        print(f"🎉 Saved: {out_clip_path}")
        if moment.suggested_caption:
            print(f"📝 Caption: {moment.suggested_caption}")
            print(f"🏷️  Hashtags: {' '.join(moment.hashtags)}")

    print("\n🚀 All clips generated successfully in:", os.path.abspath(args.output_dir))

if __name__ == "__main__":
    main()
