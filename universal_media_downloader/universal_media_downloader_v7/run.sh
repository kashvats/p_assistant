#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo "============================================"
echo "  Universal Media Downloader v7 - Ubuntu/Linux"
echo "============================================"
echo

if ! command -v python3 >/dev/null 2>&1; then
    echo "Install Python with:"
    echo "  sudo apt update && sudo apt install -y python3 python3-venv python3-tk"
    exit 1
fi

if ! python3 -c "import tkinter" >/dev/null 2>&1; then
    echo "Tkinter is missing. Install:"
    echo "  sudo apt update && sudo apt install -y python3-tk"
    exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
    python3 -m venv .venv || {
        echo "Install venv first:"
        echo "  sudo apt update && sudo apt install -y python3-venv"
        exit 1
    }
fi

source ".venv/bin/activate"

if ! python -c "import yt_dlp, PIL, plyer, tkinterdnd2" >/dev/null 2>&1; then
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "WARNING: FFmpeg is missing."
    echo "Install once:"
    echo "  sudo apt update && sudo apt install -y ffmpeg"
fi

python "downloader_gui.py"
