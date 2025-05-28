import logging
import os


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
        "output_folder":"/downloads",
        "auto_make_folders": os.environ.get("AUTO_MAKE_FOLDERS", "false").lower() == "true"
    }