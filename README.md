# python-cors-proxy

A Python‑based CORS‑enabled proxy server for HLS streaming and related resources.  
Built with Flask and Gunicorn, it rewrites playlists, streams segments in configurable chunks, and enforces strict safety limits.

---

## ✨ Features
- 🌐 **CORS Everywhere** — Adds permissive CORS headers for cross‑origin playback.
- 🔄 **Playlist Rewriting** — Ensures `.m3u8` relative URLs route back through the proxy.
- 📦 **Chunked Streaming** — Configurable `CHUNK_SIZE` for efficient delivery.
- 🚦 **Safety Limits** — Enforce maximum playlist and segment sizes.
- ⏱ **Timeout Handling** — Separate connect/read timeouts for upstream requests.
- 🔒 **Optional Host Allow‑List** — Restrict proxying to trusted domains.
- 🛠 **Dual‑Mode Launcher** — Run with Flask dev server or scale with Gunicorn.
- 🐳 **Alpine Dockerfile** — Small, efficient container image.

---

## Run locally
```bash
pip install flask requests gunicorn
python app.py
```

## 🧩 Environment variables
| Variable | Default | Description |
|----------|-------------|-------------|
| `CHUNK_SIZE` | 131072 | Chunk size in bytes (default 128 KB) |
| `MAX_PLAYLIST_BYTES` | 10485760 | Max playlist size (10 MB) |
| `MAX_SEGMENT_BYTES` | 209715200 | Max segment size (200 MB) |
| `CONNECT_TIMEOUT` | 5.0 | Upstream connect timeout (seconds) |
| `READ_TIMEOUT` | 20.0	 | Upstream read timeout (seconds) |
| `ALLOWED_HOSTS` | (empty)	| Comma‑separated list of allowed hostnames. <br>Supports exact matches (example.com) and optional wildcards (*.example.com). |
| `USE_GUNICORN` | true | Run under Gunicorn if true |
| `WORKERS` | CPU count	| Number of Gunicorn workers |

## Run with Docker
```bash
docker run -d \
  --name python-cors-proxy \
  -p 3000:3000 \
  -e CHUNK_SIZE=131072 \
  -e MAX_PLAYLIST_BYTES=10485760 \
  -e MAX_SEGMENT_BYTES=209715200 \
  -e CONNECT_TIMEOUT=5.0 \
  -e READ_TIMEOUT=20.0 \
  -e ALLOWED_HOSTS="example.com,cdn.example.org,*.example.org" \
  -e USE_GUNICORN=true \
  -e WORKERS=4 \
  techroy23/python-cors-proxy
```

## Usage
```
http://localhost:3000/proxy?url=https://xxx.domain.zzz/master.m3u8
```