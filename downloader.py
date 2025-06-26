import imaplib
import email
import re
import logging
import os
import subprocess
import shutil

from utils import extract_firefox_cookies, stream_process_output, extract_valid_links, save_downloaded_batch, clean_title_from_filename
from media_utils import get_ffmpeg_metadata_title
from mail_utils import label_as_done


log = logging.info

def process_email_body(body, mail, email_id, config, downloaded, sender_name=None):
    links = extract_valid_links(body)
    # Remove duplicates within this email
    links = list(set(links))
    
    # Set up output folder and subfolder
    final_output_folder = config["output_folder"]
    if sender_name and config["auto_make_folders"]:
        # Clean up sender name for subfolder
        safe_name = re.sub(r'[\\/*?:"<>|]', "_", sender_name)
        final_output_folder = os.path.join(final_output_folder, safe_name)
        log(f"Using subfolder for sender: {safe_name}")
    
    # Use temp folder for processing
    temp_folder = "/tmp/patreon_downloads"
    os.makedirs(temp_folder, exist_ok=True)
    output_template = os.path.join(temp_folder, "%(title)s.%(ext)s")
    
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
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; rv:139.0) Gecko/20100101 Firefox/139.0",
            "--extractor-args", "generic:impersonate",
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

        # Clean title from filename
        basename = os.path.basename(filename)
        title = clean_title_from_filename(basename) 

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
    
    # Move files to output folder
    if newly_downloaded:
        os.makedirs(final_output_folder, exist_ok=True)
        for i, (link, temp_filename) in enumerate(newly_downloaded):
            basename = os.path.basename(temp_filename)
            final_filename = os.path.join(final_output_folder, basename)
            
            try:
                shutil.move(temp_filename, final_filename)
                log(f"Moved to final location: {final_filename}")
                newly_downloaded[i] = (link, final_filename)
            except Exception as e:
                log(f"Failed to move file: {e}")
    
    # Save all at the end
    if newly_downloaded:
        save_downloaded_batch(newly_downloaded)
        
    if successful:
        label_as_done(mail, email_id)
