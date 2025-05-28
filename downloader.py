
import imaplib
import email
import re
import logging
import os
import subprocess

from utils import extract_firefox_cookies, stream_process_output, extract_valid_links, save_downloaded_batch
from media_utils import get_ffmpeg_metadata_title
from mail_utils import label_as_done


log = logging.info

def process_email_body(body, mail, email_id, config, downloaded, sender_name=None):
    links = extract_valid_links(body)
    # Remove duplicates within this email
    links = list(set(links))
    
    # Set up output folder and subfolder
    output_folder = config["output_folder"]
    if sender_name and config["auto_make_folders"]:
        # Clean up sender name for subfolder
        safe_name = re.sub(r'[\\/*?:"<>|]', "_", sender_name)
        output_folder = os.path.join(output_folder, safe_name)
        log(f"Using subfolder for sender: {safe_name}")
        
    os.makedirs(output_folder, exist_ok=True)
    output_template = os.path.join(output_folder, "%(title)s.%(ext)s")
    
    successful = False
    newly_downloaded = []

    for link in links:
        if link in downloaded:
            log(f"Already downloaded: {link}")
            continue

        log(f"New post found: {link}")
        use_firefox = os.environ.get("FIREFOX_CONTAINER_COOKIES", "false").lower() == "true"
        cookie_file = os.environ.get("COOKIE_FILE", "/app/cookies/cookies.txt")
        
        if use_firefox:
            extracted = extract_firefox_cookies(
                sqlite_path="/app/cookies/profile/cookies.sqlite",
                output_path=cookie_file
            )
            if not extracted:
                log("Failed to extract Firefox cookies. Skipping download.")
                continue
        
        ytdlp_cmd = [
            "yt-dlp",
            "--cookies", cookie_file,
            "--restrict-filenames",
            "--referer", "https://www.patreon.com/",
            "--print", "after_move:filepath",
            "-o", output_template,
            link
        ]
        
        # Use the streaming function instead of subprocess.run to maybe get better logs
        returncode, filename, output = stream_process_output(ytdlp_cmd)
        
        if returncode != 0:
            log(f"yt-dlp failed with return code {returncode}")
            continue

        if not filename or not os.path.exists(filename):
            log(f"Could not locate downloaded file: {filename}")
            continue
        
        if link in downloaded:
            log(f"Skipping ffmpeg tagging, already processed: {link}")
            continue

        # Get intended title from filename
        basename = os.path.basename(filename)
        title = os.path.splitext(basename)[0]      

        # Check if metadata title already matches
        existing_title = get_ffmpeg_metadata_title(filename)
        if existing_title == title:
            log(f"Skipping ffmpeg, title already set: '{title}'")
            # Add to curreunt list
            newly_downloaded.append((link, filename))
            # Update download.txt set
            downloaded.add(link)
            successful = True
            continue        

        # Apply new metadata
        temp_output = filename + ".tmp.mp4"     

        ffmpeg_cmd = [
            "ffmpeg",
            "-i", filename,
            "-c", "copy",
            "-metadata", f"title={title}",
            temp_output
        ]

        ffmpeg_result = subprocess.run(ffmpeg_cmd)
        if ffmpeg_result.returncode == 0:
            os.replace(temp_output, filename)
            log(f"Metadata updated: title = '{title}'")
        else:
            log("Failed to set metadata with ffmpeg")
            if os.path.exists(temp_output):
                os.remove(temp_output)

        # Just add to current list
        newly_downloaded.append((link, filename))
        # Update memory to prevent same session dupes
        downloaded.add(link)
        successful = True
    
    # Save all at the end
    if newly_downloaded:
        save_downloaded_batch(newly_downloaded)
        
    if successful:
        label_as_done(mail, email_id)
