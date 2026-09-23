FROM python:3.12-slim

# Deno lets yt-dlp solve YouTube's JavaScript challenges
COPY --from=denoland/deno:bin /deno /usr/local/bin/deno

# Bold font for the "PART N" titles
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV PORT=8000
EXPOSE 8000

# One worker on purpose: job progress is kept in memory, so every request
# must hit the same process. Threads handle concurrent users.
CMD gunicorn app:app --workers 1 --threads 8 --timeout 120 --bind 0.0.0.0:$PORT
