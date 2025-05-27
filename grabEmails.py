import os
import imaplib
import email
import re
import subprocess
import logging
from datetime import datetime
from http.cookiejar import Cookie
import shutil
import tempfile


# --- Logging setup ---
log_file = os.environ.get("LOG_FILE")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file) if log_file else logging.StreamHandler()
    ]
)
log = logging.info

# --- Config from environment ---
def load_env_secrets(path="/run/secrets/patreon_email_dl_secrets"):
    result = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    key, val = line.strip().split("=", 1)
                    result[key] = val
    except Exception as e:
        logging.error(f"Failed to load secret file: {e}")
    return result


def get_config():
    secrets = load_env_secrets()
    return {
        "email": secrets.get("EMAIL", ""),
        "app_password": secrets.get("APP_PASSWORD", ""),
        "imap_server": os.environ.get("IMAP_SERVER", "imap.gmail.com"),
        "sender_filter": secrets.get("SENDER_FILTER", ""),
        "subject_keywords": [s.strip().lower() for s in os.environ.get("SUBJECT_KEYWORDS", "").split(",") if s.strip()],
        "output_folder": os.environ.get("OUTPUT_FOLDER", "/downloads")
    }

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

def ensure_done_label_exists(mail):
    result, mailboxes = mail.list()
    existing = [box.decode().split(' "/" ')[-1].strip('"') for box in mailboxes]
    if "done" not in existing:
        mail.create("done")
        log("Created IMAP label 'done'")

def label_as_done(mail, email_id):
    try:
        mail.copy(email_id, "done")
        mail.store(email_id, '+FLAGS', '\\Deleted')
        mail.expunge()
        log("Moved email to 'done'")
    except Exception as e:
        log(f"Failed to label email as done: {e}")

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


def get_filtered_emails(config):
    mail = imaplib.IMAP4_SSL(config["imap_server"])
    mail.login(config["email"], config["app_password"])
    mail.select("inbox")

    ensure_done_label_exists(mail)

    search_criteria = '(ALL)'
    if config["sender_filter"]:
        search_criteria = f'(FROM "{config["sender_filter"]}")'

    result, data = mail.search(None, search_criteria)
    email_ids = data[0].split()

    for e_id in email_ids:
        result, msg_data = mail.fetch(e_id, "(RFC822)")
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)
        subject = msg.get("Subject", "")
        log(f"Matching Email: {subject}")

        if config["subject_keywords"] and not any(k in subject.lower() for k in config["subject_keywords"]):
            continue

        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body += part.get_payload(decode=True).decode(errors="ignore")
        else:
            body += msg.get_payload(decode=True).decode(errors="ignore")

        process_email_body(body, mail, e_id, config)

    mail.logout()

def process_email_body(body, mail, email_id, config):
    downloaded = load_downloaded()
    links = extract_valid_links(body)

    os.makedirs(config["output_folder"], exist_ok=True)
    output_template = os.path.join(config["output_folder"], "%(title)s.%(ext)s")
    successful = False

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
        
        result = subprocess.run([
            "yt-dlp",
            "--cookies", cookie_file,
            "--restrict-filenames",
            "--referer", "https://www.patreon.com/",
            "--print", "after_move:filepath",
            "-o", output_template,
            link
        ], capture_output=True, text=True, encoding='utf-8')
        

        filename = result.stdout.strip()
        if result.returncode != 0:
            log(f"yt-dlp failed with return code {result.returncode}")
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
            save_downloaded(link, filename)
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

        save_downloaded(link, filename)
        successful = True

    if successful:
        label_as_done(mail, email_id)

def main():
    config = get_config()
    get_filtered_emails(config)

if __name__ == "__main__":
    main()
