import logging

log = logging.info

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