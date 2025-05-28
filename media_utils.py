import subprocess
import logging

log = logging.info

def get_ffmpeg_metadata_title(filename):
    try:
        result = subprocess.run([
            "ffprobe", "-v", "quiet",
            "-show_entries", "format_tags=title",
            "-of", "default=noprint_wrappers=1:nokey=1",
            filename
        ], capture_output=True, text=True, encoding='utf-8')
        return result.stdout.strip()
    except Exception as e:
        log(f"Could not read metadata: {e}")
        return None