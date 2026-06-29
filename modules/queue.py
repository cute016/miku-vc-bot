from __future__ import annotations

import asyncio
import random

from modules.models import ChatPlayer, Track


class QueueManager:
    def __init__(self): self.players: dict[int, ChatPlayer] = {}

    def get(self, chat_id: int) -> ChatPlayer:
        player = self.players.setdefault(chat_id, ChatPlayer())
        if player.lock is None: player.lock = asyncio.Lock()
        return player

    def add(self, chat_id: int, track: Track) -> int:
        p = self.get(chat_id); p.queue.append(track); return len(p.queue)

    def next(self, chat_id: int) -> Track | None:
        p = self.get(chat_id)
        if p.current and p.loop_mode == "one": return p.current
        if p.current and p.loop_mode == "all": p.queue.append(p.current)
        p.current = p.queue.pop(0) if p.queue else None
        return p.current

    def clear(self, chat_id: int) -> None:
        p = self.get(chat_id); p.queue.clear(); p.current = None; p.paused = False

    def shuffle(self, chat_id: int) -> None: random.shuffle(self.get(chat_id).queue)

    def active_count(self) -> int: return sum(1 for p in self.players.values() if p.current)

