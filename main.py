from __future__ import annotations

import asyncio
import logging
import shutil
import sys
from logging.handlers import RotatingFileHandler

from pyrogram import Client, idle
from pyrogram.types import BotCommand
from pytgcalls import PyTgCalls, filters as call_filters
from pytgcalls.types import StreamEnded

from config import BASE_DIR, settings
from database import Database
from handlers import register_all
from modules.queue import QueueManager
from runtime import runtime
from services.media import MediaResolver
from services.player import VoiceController
from services.thumbnails import ThumbnailService


def configure_logging() -> None:
    formatter=logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    root=logging.getLogger(); root.setLevel(logging.INFO)
    console=logging.StreamHandler(); console.setFormatter(formatter)
    file=RotatingFileHandler(BASE_DIR/"miku.log",maxBytes=2_000_000,backupCount=3,encoding="utf-8"); file.setFormatter(formatter)
    root.handlers[:]=[console,file]


async def set_commands(bot: Client) -> None:
    commands=[("play","Play a song or YouTube link"),("vplay","Play a video"),("pause","Pause the stream"),("resume","Resume the stream"),("skip","Skip this song"),("stop","Stop and clear queue"),("queue","Show the queue"),("player","Open player controls"),("help","Show all commands"),("settings","Group settings"),("language","Change language"),("ping","Check response time")]
    try: await bot.set_bot_commands([BotCommand(x,y) for x,y in commands])
    except Exception: logging.getLogger(__name__).warning("Could not set Telegram command menu",exc_info=True)


async def main() -> None:
    configure_logging(); settings.validate()
    if not shutil.which("ffmpeg"): raise RuntimeError("FFmpeg is missing. In Termux run: pkg install ffmpeg -y")
    for folder in ("downloads","thumbnails","database","assets","admin_panel","modules","services","handlers","utils"):
        (BASE_DIR/folder).mkdir(exist_ok=True)
    db=Database(settings.sqlite_path); await db.connect()
    bot=Client("miku_bot",api_id=settings.api_id,api_hash=settings.api_hash,bot_token=settings.bot_token,workdir=str(BASE_DIR),workers=8)
    assistant=Client("miku_assistant",api_id=settings.api_id,api_hash=settings.api_hash,session_string=settings.session_string,workdir=str(BASE_DIR),sleep_threshold=60)
    calls=PyTgCalls(assistant); queues=QueueManager(); media=MediaResolver(); thumbs=ThumbnailService(); thumbs.watermark=await db.get("watermark",settings.thumb_watermark)
    runtime.bot=bot; runtime.assistant=assistant; runtime.calls=calls; runtime.db=db; runtime.queues=queues; runtime.media=media; runtime.thumbs=thumbs
    runtime.player=VoiceController(calls,queues,media,db)
    register_all(bot)

    @calls.on_update(call_filters.stream_end(StreamEnded.Type.AUDIO))
    async def stream_end(_,update):
        try:
            track=await runtime.player.play_next(update.chat_id)
            if track:
                chat=await bot.get_chat(update.chat_id)
                card=await thumbs.render("now playing",track.title,track.source,track.thumbnail,track.requester_name,chat.title or "Telegram",track.duration,0)
                try: await bot.send_photo(update.chat_id,str(card),caption=f"🎧 <b>Now playing</b>\n🎵 {track.title}\n👤 {track.requester_name}\n\n@mikuvcrobot")
                finally: thumbs.cleanup(card)
        except Exception:
            logging.getLogger(__name__).exception("Failed to advance queue in %s",update.chat_id)

    try:
        await bot.start(); await assistant.start(); await calls.start(); await set_commands(bot)
        me=await bot.get_me(); helper=await assistant.get_me(); await db.set("assistant_username",helper.username or str(helper.id))
        logging.info("%s (@%s) is online; assistant: %s",me.first_name,me.username,helper.first_name)
        if settings.log_group_id:
            try: await bot.send_message(settings.log_group_id,f"💗 <b>Miku is online</b>\nAssistant: {helper.mention}")
            except Exception: logging.warning("Could not send startup log",exc_info=True)
        await idle()
    finally:
        for client in (calls,assistant,bot):
            try: await client.stop()
            except Exception: pass
        await db.close()


if __name__=="__main__":
    if "--check" in sys.argv:
        configure_logging(); print("Miku source imports successfully. FFmpeg:",shutil.which("ffmpeg") or "MISSING")
    else: asyncio.run(main())
