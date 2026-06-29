from __future__ import annotations

import asyncio
import logging
from time import monotonic

try:
    from pytgcalls.types import MediaStream
    LEGACY_CALLS = False
except ImportError:  # PyTgCalls 0.9.7, used by 32-bit ARMv7 hosts
    from pytgcalls import StreamType
    from pytgcalls.types.input_stream import AudioPiped, AudioVideoPiped
    from pytgcalls.types.input_stream.quality import HighQualityAudio, HighQualityVideo
    LEGACY_CALLS = True

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

    async def _play_stream(self, chat_id: int, stream, replace: bool = False):
        if not LEGACY_CALLS:
            return await self._invoke(("play",), chat_id, stream)
        if replace:
            return await self._invoke(("change_stream",), chat_id, stream)
        result = self.calls.join_group_call(
            chat_id,
            stream,
            stream_type=StreamType().pulse_stream,
        )
        return await result if hasattr(result, "__await__") else result

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
                stream = self._stream(track, 0, p.speed)
                await self._play_stream(chat_id, stream, replace=old is not None)
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
    def _stream(track, offset: int = 0, speed: float = 1.0):
        source = track.input
        if LEGACY_CALLS:
            params = []
            if offset: params += ["-ss", str(max(0, int(offset)))]
            if speed != 1.0:
                params += ["-filter:a", f"atempo={speed}"]
                if track.is_video: params += ["-filter:v", f"setpts=PTS/{speed}"]
            extra = " ".join(params)
            kwargs = {"additional_ffmpeg_parameters": extra} if extra else {}
            if track.is_video:
                return AudioVideoPiped(source, HighQualityAudio(), HighQualityVideo(), **kwargs)
            return AudioPiped(source, HighQualityAudio(), **kwargs)
        if not offset and speed == 1.0: return source
        params = f"---start -ss {max(0, int(offset))}"
        if speed != 1.0:
            params += f" --audio ---mid -filter:a atempo={speed} --video ---mid -filter:v setpts=PTS/{speed}"
        return MediaStream(source, ffmpeg_parameters=params)

    async def replay(self, chat_id: int, offset: int = 0):
        p = self.queues.get(chat_id)
        if not p.current: raise PlayerError("Nothing is playing.")
        stream = self._stream(p.current, offset, p.speed)
        if LEGACY_CALLS: await self._invoke(("change_stream",), chat_id, stream)
        else: await self._invoke(("play",), chat_id, stream)
        p.started_at = monotonic(); p.offset = offset
