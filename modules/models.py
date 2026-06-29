from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic


@dataclass(slots=True)
class Track:
    title: str
    source: str
    webpage_url: str
    duration: int
    requester_id: int
    requester_name: str
    thumbnail: str | None = None
    stream_url: str | None = None
    local_path: str | None = None
    is_video: bool = False

    @property
    def input(self) -> str:
        return self.local_path or self.stream_url or self.webpage_url


@dataclass(slots=True)
class ChatPlayer:
    queue: list[Track] = field(default_factory=list)
    current: Track | None = None
    loop_mode: str = "off"
    volume: int = 100
    speed: float = 1.0
    paused: bool = False
    started_at: float = 0.0
    offset: int = 0
    lock: object | None = None

    def elapsed(self) -> int:
        if not self.current or not self.started_at:
            return 0
        value = self.offset + int((monotonic() - self.started_at) * self.speed)
        return min(self.current.duration, value) if self.current.duration else value
