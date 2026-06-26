import glob, os, subprocess

from workflows.cogitator import (
    log, log_error, set_status, set_progress, env, MEDIA_DIR, notify,
    find_video, retry, run
)


def download_from_url(url: str) -> bool:
    """Download video or playlist from a URL."""
    set_status("Downloading from URL...")
    log(f"Downloading from URL: {url}")
    notify(f"Download Started: {url}")

    os.makedirs(MEDIA_DIR, exist_ok=True)

    def do_dl():
        r = run([
            "yt-dlp",
            "--cookies-from-browser", "chrome",
            "-f", "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
            "--merge-output-format", "mp4",
            "-o", f"{MEDIA_DIR}/%(title)s.%(ext)s",
            "--progress",
            url
        ], check=False)
        return r

    result = do_dl()

    if result.returncode != 0:
        log_error(f"Download failed: {result.stderr}")
        notify(f"Download Failed: {result.stderr[:200]}")
        set_status("Download FAILED")
        return False

    downloaded_files = list(glob.glob(os.path.join(MEDIA_DIR, "*.mp4")))
    downloaded_files += list(glob.glob(os.path.join(MEDIA_DIR, "*.mk4")))
    downloaded_files += list(glob.glob(os.path.join(MEDIA_DIR, "*.webm")))

    if downloaded_files:
        latest = max(downloaded_files, key=os.path.getmtime)
        log(f"Download complete: {os.path.basename(latest)}")
        notify(f"Download Complete: {os.path.basename(latest)}")
        set_status("Download Complete")
        return True
    else:
        log_error("Download completed but no video file found")
        notify("Download Failed: No file found")
        set_status("Download FAILED")
        return False


def phase_download():
    set_status("Phase 1: Downloading video...")
    log("Phase 1: Downloading 1440p stream...")
    notify("Phase 1 Started: Downloading video...")

    playlist_url = env("PLAYLIST_URL")
    if not playlist_url:
        log_error("Phase 1 Failed: PLAYLIST_URL not configured")
        notify("Phase 1 Failed: PLAYLIST_URL not set in .env")
        set_status("Phase 1 FAILED")
        raise RuntimeError("PLAYLIST_URL not configured")

    if playlist_url.startswith("--"):
        log_error("Phase 1 Failed: PLAYLIST_URL starts with '--' (possible injection)")
        notify("Phase 1 Failed: Invalid PLAYLIST_URL")
        set_status("Phase 1 FAILED")
        raise RuntimeError("PLAYLIST_URL starts with '--'")

    cookies_ok = run(["yt-dlp", "--cookies-from-browser", "chrome", "--dump-single-json", "https://youtube.com"], check=False)
    if cookies_ok.returncode != 0:
        log_error("Phase 1 Failed: Chrome cookies not available. Run 'yt-dlp --cookies-from-browser chrome --dummy https://youtube.com' to create cookies.")
        notify("Phase 1 Failed: Chrome cookies not available")
        set_status("Phase 1 FAILED")
        raise RuntimeError("Chrome cookies not available")

    set_progress(1, 10, "Downloading video")

    # Check for a pending download URL (set by UI/backend)
    pending_file = os.path.join(os.path.expanduser("~/.cogitator"), "pending_download.txt")
    pending_url = ""
    if os.path.exists(pending_file):
        try:
            with open(pending_file) as f:
                pending_url = f.read().strip()
        except OSError:
            pass
        if pending_url:
            log(f"Using pending download URL: {pending_url}")
        else:
            log("Pending download file is empty, ignoring")

    def do_dl():
        if pending_url:
            os.makedirs(MEDIA_DIR, exist_ok=True)
            log(f"Downloading from URL: {pending_url}")
            set_progress(1, 30, "Downloading video")
            r = run(["yt-dlp",
                     "--cookies-from-browser", "chrome",
                     "-f", "bestvideo+bestaudio",
                     "-o", f"{MEDIA_DIR}/%(title)s.%(ext)s",
                     pending_url])
            log(r.stdout[-500:] if r.stdout else "")
            if r.returncode != 0 and r.stderr:
                log_error(f"yt-dlp error: {r.stderr[-300:]}")
            set_progress(1, 80, "Downloading video")
        elif playlist_url:
            raw_index = env("PLAYLIST_INDEX", "1")
            try:
                playlist_index = str(int(raw_index))
            except (ValueError, TypeError):
                log_error(f"Phase 1 Failed: Invalid PLAYLIST_INDEX '{raw_index}'")
                raise RuntimeError("Invalid PLAYLIST_INDEX")
            os.makedirs(MEDIA_DIR, exist_ok=True)
            set_progress(1, 30, "Downloading video")
            r = run(["yt-dlp", "--playlist-items", playlist_index,
                     "--cookies-from-browser", "chrome",
                     "-f", "bestvideo+bestaudio",
                     "-o", f"{MEDIA_DIR}/%(title)s.%(ext)s",
                     playlist_url])
            log(r.stdout[-500:] if r.stdout else "")
            if r.returncode != 0 and r.stderr:
                log_error(f"yt-dlp error: {r.stderr[-300:]}")
            set_progress(1, 80, "Downloading video")
        else:
            log_error("Phase 1 Failed: No URL to download")
            raise RuntimeError("No URL to download")

    if not retry(do_dl, 3, 10, "Download video"):
        log_error("Phase 1 failed after 3 attempts")
        notify("Phase 1 Failed: Download failed after 3 attempts")
        set_status("Phase 1 FAILED")
        raise RuntimeError("Phase 1 failed")

    video = find_video()
    if not video:
        log_error("Phase 1 Failed: No video file found after download")
        notify("Phase 1 Failed: No video downloaded")
        set_status("Phase 1 FAILED")
        raise RuntimeError("No video found after download")

    # Clean up pending download file
    if pending_url:
        try:
            if os.path.exists(pending_file):
                os.remove(pending_file)
        except OSError:
            pass

    set_status("Phase 1 Complete")
    notify("Phase 1 Complete: Video downloaded")
