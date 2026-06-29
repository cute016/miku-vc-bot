from __future__ import annotations

from html import escape


def duration(seconds: int) -> str:
    seconds = max(0, int(seconds or 0))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours}:{minutes:02}:{secs:02}" if hours else f"{minutes}:{secs:02}"


def short_title(value: str, limit: int = 52) -> str:
    text = " ".join((value or "").replace("\n", " ").split())
    if len(text) <= limit:
        return text
    return text[: max(10, limit - 3)].rstrip() + "..."


LANGS = {
    "en": {
        "queued": "Added to queue",
        "empty": "The queue is empty.",
        "unauth": "Only admins and authorized users can do that.",
        "not_found": "I couldn't find that song.",
    },
    "ta": {
        "queued": "Added to queue",
        "empty": "The queue is empty.",
        "unauth": "Only admins and authorized users can do that.",
        "not_found": "I couldn't find that song.",
    },
    "hi": {
        "queued": "Added to queue",
        "empty": "The queue is empty.",
        "unauth": "Only admins and authorized users can do that.",
        "not_found": "I couldn't find that song.",
    },
    "tanglish": {
        "queued": "Added to queue",
        "empty": "The queue is empty.",
        "unauth": "Only admins and authorized users can do that.",
        "not_found": "I couldn't find that song.",
    },
}


def tr(lang: str, key: str) -> str:
    return LANGS.get(lang, LANGS["en"]).get(key, LANGS["en"].get(key, key))


def now_playing(track, chat_title: str) -> str:
    return (
        "<b>Now Playing</b>\n\n"
        f"Track: {escape(short_title(track.title, 58))}\n"
        f"Length: {duration(track.duration)}\n"
        f"User: {escape(track.requester_name)}\n"
        f"Chat: {escape(chat_title)}\n\n"
        "<i>Miku VC Music - @mikuvcrobot</i>"
    )
