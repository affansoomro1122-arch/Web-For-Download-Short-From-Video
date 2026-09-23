@echo off
cd /d "%~dp0"
if not exist .venv (
  echo Setting up for the first time...
  python -m venv .venv
  .venv\Scripts\python.exe -m pip install -r requirements.txt
)
.venv\Scripts\python.exe -m pip install -q -U yt-dlp
start "" http://127.0.0.1:5000
.venv\Scripts\python.exe app.py
pause
