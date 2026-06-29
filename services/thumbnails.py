from __future__ import annotations

import asyncio
import io
import textwrap
import time
from pathlib import Path

import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from config import BASE_DIR, settings
from utils.text import duration


class ThumbnailService:
    SIZE = (1280, 720)

    def __init__(self):
        self.output = BASE_DIR / "thumbnails"; self.output.mkdir(exist_ok=True)
        self.background = Path(settings.default_bg_image)
        if not self.background.is_absolute(): self.background = BASE_DIR / self.background
        self.watermark = settings.thumb_watermark

    def _font(self, size: int, bold: bool = False):
        candidates = [settings.font_path,
            "/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSans-Bold.ttf" if bold else "/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"]
        for item in candidates:
            if item and Path(item).exists(): return ImageFont.truetype(item, size)
        return ImageFont.load_default()

    async def _fetch(self, url: str | None) -> bytes | None:
        if not url: return None
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12)) as s:
                async with s.get(url) as r:
                    if r.status == 200 and int(r.headers.get("content-length", 0) or 0) < 8_000_000: return await r.read()
        except Exception: return None
        return None

    async def render(self, kind: str, title: str = "Miku VC Music", subtitle: str = "Your cyber music assistant",
                     artwork_url: str | None = None, requester: str = "Miku", chat: str = "Telegram",
                     length: int = 0, progress: int = 0) -> Path:
        art = await self._fetch(artwork_url)
        output = self.output / f"{kind}_{time.time_ns()}.jpg"
        await asyncio.to_thread(self._draw, output, kind, title, subtitle, art, requester, chat, length, progress)
        return output

    def _draw(self, output: Path, kind: str, title: str, subtitle: str, art: bytes | None,
              requester: str, chat: str, length: int, progress: int) -> None:
        if self.background.exists(): bg = Image.open(self.background).convert("RGB")
        else: bg = Image.new("RGB", self.SIZE, "#080c2a")
        bg = ImageOps.fit(bg, self.SIZE, Image.Resampling.LANCZOS)
        bg = ImageEnhance.Brightness(bg).enhance(.58).filter(ImageFilter.GaussianBlur(1.2))
        overlay = Image.new("RGBA", self.SIZE, (4, 7, 30, 0)); od = ImageDraw.Draw(overlay)
        od.rounded_rectangle((42, 42, 1238, 678), 38, fill=(8, 13, 45, 190), outline=(74, 236, 255, 150), width=3)
        od.ellipse((-120, 430, 380, 930), fill=(146, 52, 255, 75)); od.ellipse((830, -230, 1380, 330), fill=(0, 235, 255, 55))
        bg = Image.alpha_composite(bg.convert("RGBA"), overlay); draw = ImageDraw.Draw(bg)
        accent = (84, 239, 255, 255); pink = (255, 104, 220, 255); white = (243, 249, 255, 255); muted = (178, 194, 225, 255)
        draw.text((84, 70), f"MIKU  •  {kind.upper()}", font=self._font(25, True), fill=accent)
        x = 84
        if art:
            try:
                cover = ImageOps.fit(Image.open(io.BytesIO(art)).convert("RGB"), (390, 390), Image.Resampling.LANCZOS)
                mask = Image.new("L", cover.size); ImageDraw.Draw(mask).rounded_rectangle((0, 0, 389, 389), 30, fill=255)
                bg.paste(cover, (84, 160), mask); draw.rounded_rectangle((82, 158, 476, 552), 32, outline=accent, width=3); x = 530
            except Exception: x = 84
        max_chars = 31 if x > 100 else 46
        lines = textwrap.wrap(title.replace("\n", " "), width=max_chars)[:3] or ["Miku VC Music"]
        y = 174
        for line in lines: draw.text((x, y), line, font=self._font(49, True), fill=white); y += 58
        draw.text((x, y + 14), subtitle[:65], font=self._font(27), fill=pink)
        draw.text((x, y + 72), f"Requested by  {requester[:28]}", font=self._font(23), fill=muted)
        draw.text((x, y + 112), f"Chat  {chat[:38]}", font=self._font(23), fill=muted)
        if kind in {"now playing", "player", "preview"}:
            left, right, py = x, 1165, 535; draw.rounded_rectangle((left, py, right, py + 10), 5, fill=(70, 79, 120, 255))
            ratio = min(1, progress / length) if length else 0
            draw.rounded_rectangle((left, py, left + int((right-left)*ratio), py + 10), 5, fill=accent)
            draw.text((left, py + 25), duration(progress), font=self._font(21), fill=muted)
            draw.text((right - 80, py + 25), duration(length), font=self._font(21), fill=muted)
        draw.text((84, 620), "MIKU VC MUSIC BOT", font=self._font(23, True), fill=white)
        mark = "@mikuvcrobot"
        box = draw.textbbox((0, 0), mark, font=self._font(25, True)); draw.text((1190 - (box[2]-box[0]), 618), mark, font=self._font(25, True), fill=accent)
        if self.watermark and self.watermark.lower() != mark:
            draw.text((84, 580), self.watermark[:48], font=self._font(19), fill=muted)
        bg.convert("RGB").save(output, "JPEG", quality=88, optimize=True)

    def cleanup(self, path: Path | None) -> None:
        if path:
            try: path.unlink(missing_ok=True)
            except OSError: pass
