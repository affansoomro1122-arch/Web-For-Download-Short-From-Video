# ShortsForge: YouTube to Shorts converter

Paste a YouTube link and it produces **multiple vertical 9:16 shorts, each 1:00 to 1:30 long**, ready for YouTube Shorts, TikTok and Reels. Every short has its own **Download** button, and there is also a **Download all (ZIP)** button.

## Run it (Windows)

Double-click **`start.bat`**. The first run installs everything automatically. After that, the browser opens at http://127.0.0.1:5000.

Manual way:

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python app.py
```

Requires Python 3.9+. **ffmpeg is bundled** through `imageio-ffmpeg`, so you don't need to install it separately.

## How it works

1. `yt-dlp` downloads the video (up to 1080p).
2. ffmpeg `silencedetect` finds pauses in the audio. Cuts are placed at a pause between 60 and 90 seconds, so clips don't end mid-sentence.
3. Each clip is converted to vertical format:
   - **Blur fill**: the full video in the center with a blurred copy behind it (nothing is cropped out).
   - **Center crop**: fills the whole 9:16 frame by cropping the sides.
4. Shorts appear on the page one by one as they finish rendering.

Leftover footage shorter than 60 seconds at the end of a video is skipped. Job files are deleted automatically after 3 hours.

## Files

| File | Purpose |
|---|---|
| `app.py` | Flask server, download, cutting and rendering |
| `static/index.html` | Page structure |
| `static/style.css` | Yellow and black theme |
| `static/app.js` | Form, progress polling, shorts grid, downloads |

## Notes

- If YouTube starts failing, update yt-dlp: `.venv\Scripts\pip install -U yt-dlp` (`start.bat` does this on every launch).
- Only convert videos you own or have permission to repost.
- Static hosts like GitHub Pages or Netlify **cannot** run this app. It needs a server that runs Python.

## Deploy

The included `Dockerfile` works on any Docker host.

**Railway / Render:**
1. Push this folder to GitHub.
2. Create a new service from the repo. The host detects the Dockerfile.
3. Pick a plan with at least 1 GB RAM.

**VPS (Hetzner, DigitalOcean, Contabo):**

```bash
git clone <your-repo> && cd yt-shorts-maker
docker build -t shortsforge .
docker run -d --restart unless-stopped -p 80:8000 -v $PWD/cookies.txt:/app/cookies.txt shortsforge
```

**YouTube bot block:** YouTube often blocks cloud-server IPs with "Sign in to confirm you're not a bot". To fix it:
1. Export `cookies.txt` from a logged-in browser using the "Get cookies.txt LOCALLY" extension. Use a spare Google account.
2. Put the file next to `app.py`, or set `YTDLP_COOKIES_FILE=/path/to/cookies.txt`. On Render, upload it as a Secret File and set `YTDLP_COOKIES_FILE=/etc/secrets/cookies.txt`.

Never commit `cookies.txt`. It's already listed in `.gitignore`.
