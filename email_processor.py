import imaplib
import email
import re
import logging

from utils import load_downloaded, extract_sender_name
from mail_utils import ensure_done_label_exists
from downloader import process_email_body


log = logging.info

def get_filtered_emails(config):
    downloaded = load_downloaded()
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
        
        # Extract sender name when AUTO_MAKE_FOLDERS is enabled
        sender_name = None
        if config["auto_make_folders"]:
            from_header = msg.get("From", "")
            sender_name = extract_sender_name(from_header)
            log(f"Matching Email: {subject} from {sender_name}")
        else:
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

        process_email_body(body, mail, e_id, config, downloaded, sender_name)

    mail.logout()