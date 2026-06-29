from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class Runtime:
    bot: object = None
    assistant: object = None
    calls: object = None
    db: object = None
    queues: object = None
    media: object = None
    thumbs: object = None
    player: object = None
    started_at: datetime = datetime.now(timezone.utc)


runtime = Runtime()

