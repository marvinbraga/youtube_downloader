#!/usr/bin/env python3
"""
Test a single video with detailed error output
"""

import yt_dlp
import os
import sys
from pathlib import Path

def test_single_video():
    """Test a single video with detailed error reporting."""
    
    # The problematic video
    url = "https://www.youtube.com/watch?v=9bZkp7q19f0"  # Gangnam Style
    
    test_dir = Path("single_video_test")
    test_dir.mkdir(exist_ok=True)
    
    # Configuration similar to our tests
    config = {
        'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
        'outtmpl': str(test_dir / '%(title)s.%(ext)s'),
        'quiet': False,  # Enable all output
        'no_warnings': False,
        'merge_output_format': 'mp4',
        'writeinfojson': True,
        'extract_flat': False,
        'ignoreerrors': False,
        'no_color': True,
        'player_client': ['web'],  # Use web client
        'verbose': True,  # Maximum verbosity
    }
    
    print(f"Testing URL: {url}")
    print(f"Configuration: {config}")
    print("\n" + "="*50)
    
    try:
        with yt_dlp.YoutubeDL(config) as ydl:
            print("Step 1: Extracting video information...")
            try:
                info = ydl.extract_info(url, download=False)
                print("SUCCESS: Successfully extracted info:")
                print(f"  Title: {info.get('title')}")
                print(f"  Duration: {info.get('duration')} seconds")
                print(f"  Uploader: {info.get('uploader')}")
                print(f"  Upload date: {info.get('upload_date')}")
                print(f"  View count: {info.get('view_count')}")
                print(f"  Available formats: {len(info.get('formats', []))}")
                
                # Check for available formats
                formats = info.get('formats', [])
                if formats:
                    print("\nAvailable formats:")
                    for fmt in formats[:5]:  # Show first 5 formats
                        print(f"  - {fmt.get('format_id')}: {fmt.get('ext')} {fmt.get('resolution', 'audio')} {fmt.get('filesize', 'unknown size')}")
                
            except Exception as e:
                print(f"FAILED: Info extraction failed: {str(e)}")
                return False
            
            print("\nStep 2: Attempting download...")
            try:
                ydl.download([url])
                
                # Check if files were created
                video_files = list(test_dir.glob("*.mp4"))
                info_files = list(test_dir.glob("*.info.json"))
                
                if video_files:
                    video_file = video_files[0]
                    file_size = video_file.stat().st_size
                    print(f"SUCCESS: Download successful!")
                    print(f"  File: {video_file.name}")
                    print(f"  Size: {file_size:,} bytes ({file_size / 1024 / 1024:.1f} MB)")
                    return True
                else:
                    print("FAILED: Download completed but no video file found")
                    print("Files in output directory:")
                    for file in test_dir.iterdir():
                        print(f"  - {file.name} ({file.stat().st_size} bytes)")
                    return False
                    
            except Exception as e:
                print(f"FAILED: Download failed: {str(e)}")
                return False
                
    except Exception as e:
        print(f"FAILED: Configuration error: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_single_video()
    print("\n" + "="*50)
    print(f"Test result: {'SUCCESS' if success else 'FAILED'}")