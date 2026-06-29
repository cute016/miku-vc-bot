from __future__ import annotations

from html import escape


def duration(seconds: int) -> str:
    seconds = max(0, int(seconds or 0)); h, rem = divmod(seconds, 3600); m, s = divmod(rem, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"


LANGS = {
    "en": {"queued": "Added to queue", "empty": "The queue is empty, baby.", "unauth": "Only admins and authorized users can do that.", "not_found": "I couldn't find that song."},
    "ta": {"queued": "வரிசையில் சேர்க்கப்பட்டது", "empty": "பாடல் வரிசை காலியாக உள்ளது.", "unauth": "நிர்வாகிகள் மட்டும் இதைச் செய்யலாம்.", "not_found": "அந்தப் பாடல் கிடைக்கவில்லை."},
    "hi": {"queued": "कतार में जोड़ दिया", "empty": "गाने की कतार खाली है।", "unauth": "केवल एडमिन या अधिकृत सदस्य यह कर सकते हैं।", "not_found": "वह गाना नहीं मिला।"},
    "tanglish": {"queued": "Queue-la add panniten", "empty": "Queue empty-ah irukku baby.", "unauth": "Admins/auth users mattum use pannalaam.", "not_found": "Andha song kedaikkala."},
}


def tr(lang: str, key: str) -> str: return LANGS.get(lang, LANGS["en"]).get(key, LANGS["en"].get(key, key))


def now_playing(track, chat_title: str) -> str:
    return (f"🎧 <b>ɴᴏᴡ ᴘʟᴀʏɪɴɢ ❯</b>\n\n"
            f"🎵 <b>ᴛʀᴀᴄᴋ:</b> {escape(track.title)}\n"
            f"⏱ <b>ʟᴇɴɢᴛʜ:</b> {duration(track.duration)}\n"
            f"👤 <b>ᴜsᴇʀ:</b> {escape(track.requester_name)}\n"
            f"💬 <b>ᴄʜᴀᴛ:</b> {escape(chat_title)}\n\n"
            f"<i>Miku VC Music • @mikuvcrobot</i>")

