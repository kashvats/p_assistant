# Universal Media Downloader v7

v7 keeps the simple v6 interface and adds convenience features without crowding the default screen.

## New in v7

- Clipboard URL detection
- Drag-and-drop `.txt` URL lists (when tkinterdnd2 is available)
- Import URLs from `.txt`
- Persistent queue saved to `queue.json`
- Retry failed downloads from History
- Disk-space warning before download
- Desktop completion notifications
- Queue-finish actions: Do nothing / Sleep / Shut down
- One-click Quick Download presets
- Remember quality/audio choices per site
- Optional target-size compression in MB
- Open downloaded file
- Copy downloaded file path
- Duplicate-download warning
- Light / Dark / System theme
- Preferred and fallback audio language
- Optional automatic opening of completed file

## Main workflow

1. Paste a URL (or let clipboard detection offer it automatically)
2. Wait for automatic analysis
3. Choose Quality / Audio / Subtitles
4. Click Download

Quick presets:
- Best Quality
- 1080p Recommended
- 720p Small Size
- MP3 Audio
- Best + All Audio

Advanced options remain hidden by default.

## Windows 11

Recommended one-time install:

    winget install --id Gyan.FFmpeg -e

Then double-click:

    run.bat

## Ubuntu / Debian

One-time setup:

    sudo apt update
    sudo apt install -y python3 python3-venv python3-tk ffmpeg

Then:

    chmod +x run.sh
    ./run.sh

## Notes

- Sleep/shutdown after queue completion may require OS permissions.
- Target-size compression is approximate; exact size cannot be guaranteed with single-pass encoding.
- Drag/drop requires the `tkinterdnd2` Python package, installed automatically by the launchers.
- Desktop notifications use the `plyer` package.

Use only for media you own, have permission to download, or the site allows you to save.
The application does not bypass DRM-protected streams.
