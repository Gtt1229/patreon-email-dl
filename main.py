import os
import fcntl
import errno
import sys
import logging

from config import get_config
from email_processor import get_filtered_emails
from utils import setup_logging

log = logging.info

def main():
    config = get_config()
    
    # Create lock file to prevent concurrent runs
    lock_file = "/app/state/patreon_dl.lock"
    os.makedirs(os.path.dirname(lock_file), exist_ok=True)
    
    try:
        # Try to acquire a hard lock
        lock_handle = open(lock_file, 'w')
        fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        
        log("Lock acquired, starting email processing...")
        get_filtered_emails(config)
        
    except IOError as e:
        if e.errno == errno.EWOULDBLOCK:
            log("Another instance is already running. Exiting.")
            sys.exit(0)
        raise
    except Exception as e:
        log(f"Error during execution: {e}")
    finally:
        # Release the lock when done
        if 'lock_handle' in locals():
            fcntl.flock(lock_handle, fcntl.LOCK_UN)
            lock_handle.close()

if __name__ == "__main__":
    main()
