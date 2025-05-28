#!/bin/bash
set -e

CRON_SCHEDULE="${CRON_SCHEDULE:-"@hourly"}"
export LOG_FILE="${LOG_FILE:-/app/logs/patreon-dl.log}"

mkdir -p "$(dirname "$LOG_FILE")"

# run at start
echo "Running job at start..."
python -u /app/main.py


# supercronic
echo "$CRON_SCHEDULE bash -c 'python -u /app/main.py'" > /app/crontab.txt

echo "Using schedule: $CRON_SCHEDULE"
echo "Logging to: $LOG_FILE"
cat /app/crontab.txt

exec /usr/local/bin/supercronic /app/crontab.txt
