from __future__ import annotations

import asyncio
import re
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp

from config import BASE_DIR, settings
from modules.models import Track

URL_RE = re.compile(r"^https?://", re.I)


class MediaError(RuntimeError): pass


class MediaResolver:
    def __init__(self):
        self.downloads = BASE_DIR / "downloads"
        self.downloads.mkdir(exist_ok=True)

    @staticmethod
    def _ydl(stream: bool = True) -> dict:
        return {
            "quiet": True, "no_warnings": True, "noplaylist": True,
            "format": "best[height<=720]/best" if stream else "bestaudio/best",
            "socket_timeout": 20, "retries": 2,
            "extract_flat": False, "skip_download": True,
        }

    async def resolve(self, query: str, requester_id: int, requester_name: str, is_video: bool, reply=None) -> Track:
        if reply and (reply.audio or reply.video or reply.document or reply.voice):
            media = reply.audio or reply.video or reply.document or reply.voice
            path = await reply.download(file_name=str(self.downloads) + "/")
            return Track(title=getattr(media, "file_name", None) or "Telegram upload", source="Telegram",
                         webpage_url=path, local_path=path, duration=int(getattr(media, "duration", 0) or 0),
                         requester_id=requester_id, requester_name=requester_name, is_video=bool(reply.video or is_video))
        query = query.strip()
        if not query: raise MediaError("Reply to an audio/video file or give me a song name or URL.")
        if URL_RE.match(query) and urlparse(query).scheme not in {"http", "https"}: raise MediaError("Only HTTP(S) media links are supported.")
        target = query if URL_RE.match(query) else f"ytsearch1:{query}"
        loop = asyncio.get_running_loop()

        def extract():
            with yt_dlp.YoutubeDL(self._ydl(is_video)) as ydl: return ydl.extract_info(target, download=False)
        try: info = await loop.run_in_executor(None, extract)
        except Exception as exc: raise MediaError(f"Media lookup failed: {str(exc)[:160]}") from exc
        if info.get("entries"): info = next((x for x in info["entries"] if x), None)
        if not info: raise MediaError("Song not found.")
        length = int(info.get("duration") or 0)
        if length and length > settings.max_duration: raise MediaError(f"Tracks longer than {settings.max_duration // 60} minutes are disabled.")
        stream = info.get("url")
        webpage = info.get("webpage_url") or query
        source = info.get("extractor_key") or info.get("extractor") or "Direct link"
        return Track(title=(info.get("title") or "Unknown track")[:180], source=source, webpage_url=webpage,
                     stream_url=stream, duration=length, requester_id=requester_id, requester_name=requester_name,
                     thumbnail=info.get("thumbnail"), is_video=is_video)

    async def refresh(self, track: Track) -> Track:
        if track.local_path or not URL_RE.match(track.webpage_url): return track
        if "youtube" not in track.source.lower() and track.stream_url: return track
        loop = asyncio.get_running_loop()
        def extract():
            with yt_dlp.YoutubeDL(self._ydl(track.is_video)) as ydl: return ydl.extract_info(track.webpage_url, download=False)
        info = await loop.run_in_executor(None, extract)
        track.stream_url = info.get("url") or track.stream_url
        return track

    def cleanup(self, track: Track | None) -> None:
        if not track or not track.local_path: return
        try:
            path = Path(track.local_path).resolve()
            if path.is_file() and self.downloads.resolve() in path.parents: path.unlink(missing_ok=True)
        except OSError: pass

