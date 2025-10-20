"""
Flask HLS Proxy Server
----------------------
This application proxies HLS playlists (.m3u8), media segments (.ts, .mp4),
and other resources (e.g., .vtt subtitles). It rewrites relative URLs in
playlists so that all subsequent requests are routed back through this proxy.

Features:
- CORS headers for cross-origin playback
- Configurable chunk sizes and maximum response sizes
- Timeout handling for upstream requests
- Optional domain allow-listing for security
- Dual-mode launcher: Flask dev server or Gunicorn production server
"""

from flask import Flask, request, Response
import requests
from urllib.parse import urljoin, quote, urlparse
import os
import multiprocessing
from fake_useragent import UserAgent

# Initialize fake_useragent once
try:
    ua = UserAgent()
    user_agent = ua.chrome
except Exception:
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

# ---------------------------------------------------------------------------
# Flask application setup
# ---------------------------------------------------------------------------
app = Flask(__name__)

# ---------------------------------------------------------------------------
# Configuration (environment-driven, with defaults)
# ---------------------------------------------------------------------------
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", 131072))  # 128 KB per chunk
MAX_PLAYLIST_BYTES = int(os.environ.get("MAX_PLAYLIST_BYTES", 10 * 1024 * 1024))  # 10 MB max playlist
MAX_SEGMENT_BYTES = int(os.environ.get("MAX_SEGMENT_BYTES", 200 * 1024 * 1024))  # 200 MB max segment
CONNECT_TIMEOUT = float(os.environ.get("CONNECT_TIMEOUT", 5.0))   # seconds
READ_TIMEOUT = float(os.environ.get("READ_TIMEOUT", 20.0))        # seconds

# Optional allowlist of hostnames (comma-separated via ALLOWED_HOSTS env var)
ALLOWED_HOSTS = set(
    h.strip().lower()
    for h in os.environ.get("ALLOWED_HOSTS", "").split(",")
    if h.strip()
)

def validate_url(u: str):
    p = urlparse(u)
    if p.scheme not in ("http", "https"):
        return False, "Unsupported URL scheme"
    if ALLOWED_HOSTS and p.hostname:
        host = p.hostname.lower()
        allowed = False
        for h in ALLOWED_HOSTS:
            if h.startswith("*.") and host.endswith(h[1:]):
                allowed = True
                break
            if host == h:
                allowed = True
                break
        if not allowed:
            return False, f"Host {p.hostname} not allowed"
    return True, None

# ---------------------------------------------------------------------------
# Utility: Build CORS headers
# ---------------------------------------------------------------------------
def cors_headers(extra=None):
    """
    Return a dictionary of CORS headers, optionally merged with extra headers.
    """
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "*",
        "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
    }
    if extra:
        headers.update(extra)
    return headers

# ---------------------------------------------------------------------------
# Proxy endpoint
# ---------------------------------------------------------------------------
@app.route("/proxy", methods=["GET", "HEAD", "OPTIONS"])
def proxy():
    """
    Proxy endpoint that fetches the given ?url= parameter and returns it
    with CORS headers. Special handling for .m3u8 playlists:
    - Rewrites relative segment URLs to point back through this proxy.
    - Enforces maximum playlist size.
    For other resources (segments, subtitles, etc.):
    - Streams the response in chunks.
    - Enforces maximum segment size.
    """
    url = request.args.get("url")
    if not url:
        return Response("Missing ?url= parameter", status=400, headers=cors_headers())

    # Validate URL against allowlist
    ok, err = validate_url(url)
    if not ok:
        return Response(f"Invalid URL: {err}", status=400, headers=cors_headers())

    # Fetch upstream resource
    try:
        # Pick a desktop browser UA (Windows/Chrome by default)
        user_agent = ua.chrome
        # Normalize referer to just scheme://host[:port]/
        p = urlparse(url)
        referer = f"{p.scheme}://{p.netloc}/"
        r = requests.get(
            url,
            stream=True,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            headers={
                "User-Agent": user_agent,
                "Referer": referer,
            },
        )
    except requests.RequestException as e:
        return Response(f"Upstream fetch error: {e}", status=502, headers=cors_headers())

    # -----------------------------------------------------------------------
    # Handle HLS playlist (.m3u8)
    # -----------------------------------------------------------------------
    if url.endswith(".m3u8"):
        content = []
        read = 0
        # Read playlist in chunks, enforce max size
        for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
            if not chunk:
                continue
            read += len(chunk)
            if read > MAX_PLAYLIST_BYTES:
                return Response("Playlist too large", status=413, headers=cors_headers())
            content.append(chunk)

        # Decode playlist text
        text = b"".join(content).decode(r.encoding or "utf-8", errors="replace")

        # Rewrite relative URLs to go through proxy
        base = url.rsplit("/", 1)[0] + "/"
        lines = []
        for line in text.splitlines():
            if line and not line.startswith("#") and not line.startswith("http"):
                proxied = f"/proxy?url={quote(urljoin(base, line), safe='')}"
                lines.append(proxied)
            else:
                lines.append(line)
        body = "\n".join(lines)

        # Normalize Content-Type
        ctype = r.headers.get("Content-Type", "").lower()
        if "mpegurl" not in ctype:
            ctype = "application/vnd.apple.mpegurl"
        else:
            ctype = r.headers.get("Content-Type")

        return Response(body, headers=cors_headers({"Content-Type": ctype}), status=r.status_code)

    # -----------------------------------------------------------------------
    # Handle other resources (segments, subtitles, etc.)
    # -----------------------------------------------------------------------
    def generate():
        """
        Generator that streams upstream response in CHUNK_SIZE increments,
        enforcing MAX_SEGMENT_BYTES.
        """
        sent = 0
        for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
            if not chunk:
                continue
            sent += len(chunk)
            if sent > MAX_SEGMENT_BYTES:
                break
            yield chunk

    headers = {"Content-Type": r.headers.get("Content-Type") or "application/octet-stream"}
    headers.update(cors_headers())
    return Response(generate(), headers=headers, status=r.status_code)

# ---------------------------------------------------------------------------
# Entrypoint: run with Flask dev server or Gunicorn
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    use_gunicorn = os.environ.get("USE_GUNICORN", "").lower() in ("1", "true", "yes")

    if use_gunicorn:
        # Run under Gunicorn
        from gunicorn.app.wsgiapp import run
        import sys

        workers = int(os.environ.get("WORKERS", multiprocessing.cpu_count()))
        sys.argv = [
            "gunicorn",
            "-w", str(workers),
            "-b", "0.0.0.0:3000",
            "--log-level", os.environ.get("LOG_LEVEL", "debug"),
            "--access-logfile", os.environ.get("ACCESS_LOGFILE", "-"),
            "--error-logfile", os.environ.get("ERROR_LOGFILE", "-"),
            "--capture-output",
            "app:app",
        ]
        run()
    else:
        # Run with Flask's built-in dev server
        app.run(host="0.0.0.0", port=3000, debug=True, threaded=True)