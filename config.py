from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _ids(value: str) -> set[int]:
    return {int(x.strip()) for x in value.split(",") if x.strip().lstrip("-").isdigit()}


@dataclass(frozen=True, slots=True)
class Settings:
    api_id: int = int(os.getenv("API_ID", "0"))
    api_hash: str = os.getenv("API_HASH", "")
    bot_token: str = os.getenv("BOT_TOKEN", "")
    owner_id: int = int(os.getenv("OWNER_ID", "0"))
    sudo_users: frozenset[int] = frozenset(_ids(os.getenv("SUDO_USERS", "")))
    session_string: str = os.getenv("SESSION_STRING", "")
    log_group_id: int = int(os.getenv("LOG_GROUP_ID", "0") or 0)
    support_group: str = os.getenv("SUPPORT_GROUP", "https://t.me/mikuvcsupport")
    update_channel: str = os.getenv("UPDATE_CHANNEL", "https://t.me/mikuvcupdates")
    owner_username: str = os.getenv("OWNER_USERNAME", "telegram")
    bot_username: str = os.getenv("BOT_USERNAME", "mikuvcrobot").lstrip("@")
    bot_name: str = os.getenv("BOT_NAME", "Miku")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///miku.db")
    thumb_watermark: str = os.getenv("THUMB_WATERMARK", "@mikuvcrobot")
    default_bg_image: str = os.getenv("DEFAULT_BG_IMAGE", str(BASE_DIR / "assets" / "miku_background.png"))
    default_avatar: str = os.getenv("DEFAULT_AVATAR", "")
    font_path: str = os.getenv("FONT_PATH", "")
    max_duration: int = int(os.getenv("MAX_DURATION", "7200"))
    auto_leave: bool = os.getenv("AUTO_LEAVE", "true").lower() in {"1", "true", "yes"}

    @property
    def all_sudo(self) -> set[int]:
        return set(self.sudo_users) | ({self.owner_id} if self.owner_id else set())

    @property
    def sqlite_path(self) -> Path:
        raw = self.database_url.removeprefix("sqlite:///")
        path = Path(raw)
        return path if path.is_absolute() else BASE_DIR / path

    def validate(self) -> None:
        missing = [name for name, value in (("API_ID", self.api_id), ("API_HASH", self.api_hash),
                                             ("BOT_TOKEN", self.bot_token), ("SESSION_STRING", self.session_string)) if not value]
        if missing:
            raise RuntimeError(f"Missing required .env values: {', '.join(missing)}")


settings = Settings()

