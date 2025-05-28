# utils.py
import os
import logging
import tempfile
import shutil
import subprocess
import re

from http.cookiejar import Cookie


log = logging.info

def setup_logging():
    log_file = os.environ.get("LOG_FILE")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            *([] if not log_file else [logging.FileHandler(log_file)])
        ]
    )
    # No need to return - logging is configured globally

def stream_process_output(cmd):
    """Run a command and stream its output in real time"""
    print(f"Running command: {' '.join(cmd)}", flush=True)  # Trying to direct to container logs
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # Combine stdout and stderr to try to capture all logs
        text=True,
        encoding='utf-8',
        bufsize=1,  # Line buffering
        universal_newlines=True
    )
    
    output_lines = []
    filepath = None
    
    # Process output in real time
    for line in process.stdout:
        line = line.strip()
        output_lines.append(line)
        # Maybe irect print to container logs and log to the logger
        print(f"yt-dlp: {line}", flush=True)
        log(f"yt-dlp: {line}")
        
        if line and not line.startswith("["):
            filepath = line
    
    # Wait for process to complete
    return_code = process.wait()
    return return_code, filepath, "\n".join(output_lines)


def load_downloaded():
    if not os.path.exists("/app/state/downloaded.txt"):
        return set()
    links = set()
    with open("/app/state/downloaded.txt", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                parts = line.strip().split(" --> ")[0]
                links.add(parts)
    return links

def save_downloaded(link, filename=None):
    existing = load_downloaded()
    if link in existing:
        return  # Already saved

    with open("/app/state/downloaded.txt", "a", encoding="utf-8") as f:
        if filename:
            f.write(f"{link} --> {filename}\n")
        else:
            f.write(f"{link}\n")

def save_downloaded_batch(items):
    with open("/app/state/downloaded.txt", "a", encoding="utf-8") as f:
        for link, filename in items:
            if filename:
                f.write(f"{link} --> {filename}\n")
            else:
                f.write(f"{link}\n")

def extract_sender_name(from_header):
    """Extract sender name from a From email header"""
    if not from_header:
        return "Unknown"
    
    # Try to match sender name
    match = re.search(r'^(.*?)\s*<', from_header)
    if match:
        name = match.group(1).strip()
        if name:
            return name
    
    # If no name found use email
    email_part = re.search(r'<?([\w\.-]+)@', from_header)
    if email_part:
        return email_part.group(1)
    
    # fall way back to "Unknown"
    return "Unknown"

def extract_valid_links(body):
    links = re.findall(r'https?://[^\s<>"]+', body)
    return [
        re.sub(r'^https://open\.patreon\.com/posts/', 'https://www.patreon.com/posts/', url).split('?')[0]
        for url in links if "patreon.com/posts/" in url
    ]

def extract_firefox_cookies(sqlite_path="/app/cookies/profile/cookies.sqlite", output_path="/app/cookies/cookies.txt"):
    from http.cookiejar import MozillaCookieJar, Cookie
    import sqlite3
    import os

    if not os.path.exists(sqlite_path):
        logging.warning(f"Firefox cookie DB not found at: {sqlite_path}")
        return False

    # Create a temporary copy to avoid locking issues
    with tempfile.NamedTemporaryFile(delete=False) as temp:
        temp_db_path = temp.name
    shutil.copy2(sqlite_path, temp_db_path)

    try:
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT host, path, isSecure, expiry, name, value FROM moz_cookies WHERE host LIKE '%patreon.com%'")
        rows = cursor.fetchall()
        conn.close()
    finally:
        os.remove(temp_db_path)

    cj = MozillaCookieJar(output_path)
    for host, path, secure, expiry, name, value in rows:
        cj.set_cookie(Cookie(
            version=0, name=name, value=value, port=None, port_specified=False,
            domain=host, domain_specified=True, domain_initial_dot=host.startswith('.'),
            path=path, path_specified=True, secure=bool(secure),
            expires=int(expiry), discard=False, comment=None, comment_url=None, rest={}
        ))
    cj.save(ignore_discard=True)
    logging.info(f"Extracted {len(rows)} cookies to: {output_path}")
    return True