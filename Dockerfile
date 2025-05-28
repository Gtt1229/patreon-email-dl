FROM python:3.10-slim

# ─── OS-level deps ──────────────────────────────────────────────────────────────
RUN apt-get update && \
    apt-get install -y ffmpeg curl wget ca-certificates coreutils bash && \
    rm -rf /var/lib/apt/lists/*

# ─── Python deps ────────────────────────────────────────────────────────────────
RUN pip install --no-cache-dir yt-dlp

# ─── supercronic (lightweight cron for containers) ──────────────────────────────
RUN wget -q -O /usr/local/bin/supercronic https://github.com/aptible/supercronic/releases/latest/download/supercronic-linux-amd64 \
 && chmod +x /usr/local/bin/supercronic

# ─── App code ───────────────────────────────────────────────────────────────────
WORKDIR /app

# Only copy needed files (no COPY . /app!)
COPY ./*.py /app/
COPY ./entrypoint.sh /entrypoint.sh

# Make entrypoint executable
RUN chmod +x /entrypoint.sh

# ─── Entrypoint ────────────────────────────────────────────────────────────────
ENTRYPOINT ["/entrypoint.sh"]
