from __future__ import annotations

import asyncio
import logging
from time import monotonic

from pytgcalls.types import MediaStream

from config import settings
from database import Database
from modules.queue import QueueManager
from services.media import MediaResolver

log = logging.getLogger(__name__)


class PlayerError(RuntimeError): pass


class VoiceController:
    """Small compatibility layer for current and legacy PyTgCalls control names."""
    def __init__(self, calls, queues: QueueManager, media: MediaResolver, db: Database):
        self.calls, self.queues, self.media, self.db = calls, queues, media, db

    async def _invoke(self, names: tuple[str, ...], *args):
        for name in names:
            method = getattr(self.calls, name, None)
            if method:
                result = method(*args)
                return await result if hasattr(result, "__await__") else result
        raise PlayerError(f"Your PyTgCalls build does not provide: {names[0]}")

    async def play_next(self, chat_id: int):
        p = self.queues.get(chat_id)
        async with p.lock:
            old = p.current
            track = self.queues.next(chat_id)
            if old and old is not track and old not in p.queue:
                self.media.cleanup(old)
            if not track:
                if settings.auto_leave:
                    try: await self.leave(chat_id)
                    except Exception: pass
                return None
            try:
                track = await self.media.refresh(track)
                stream = self._stream(track.input, 0, p.speed)
                await self._invoke(("play", "join_group_call"), chat_id, stream)
            except Exception as exc:
                log.exception("Could not play in %s", chat_id)
                p.current = None
                raise PlayerError(f"Voice chat playback failed: {str(exc)[:180]}") from exc
            p.paused = False; p.started_at = monotonic(); p.offset = 0
            await self.db.song_played(); return track

    async def force(self, chat_id: int, track):
        await self.stop(chat_id); self.queues.add(chat_id, track); return await self.play_next(chat_id)

    async def pause(self, chat_id: int): await self._invoke(("pause", "pause_stream"), chat_id); self.queues.get(chat_id).paused = True
    async def resume(self, chat_id: int): await self._invoke(("resume", "resume_stream"), chat_id); self.queues.get(chat_id).paused = False
    async def leave(self, chat_id: int): await self._invoke(("leave_call", "leave_group_call"), chat_id)
    async def skip(self, chat_id: int): return await self.play_next(chat_id)

    async def stop(self, chat_id: int):
        p = self.queues.get(chat_id)
        for track in [p.current, *p.queue]: self.media.cleanup(track)
        self.queues.clear(chat_id)
        try: await self.leave(chat_id)
        except Exception: pass

    async def volume(self, chat_id: int, level: int):
        await self._invoke(("change_volume_call", "change_volume"), chat_id, level); self.queues.get(chat_id).volume = level

    @staticmethod
    def _stream(source: str, offset: int = 0, speed: float = 1.0):
        if not offset and speed == 1.0: return source
        params = f"---start -ss {max(0, int(offset))}"
        if speed != 1.0:
            params += f" --audio ---mid -filter:a atempo={speed} --video ---mid -filter:v setpts=PTS/{speed}"
        return MediaStream(source, ffmpeg_parameters=params)

    async def replay(self, chat_id: int, offset: int = 0):
        p = self.queues.get(chat_id)
        if not p.current: raise PlayerError("Nothing is playing.")
        await self._invoke(("play", "change_stream"), chat_id, self._stream(p.current.input, offset, p.speed))
        p.started_at = monotonic(); p.offset = offset
