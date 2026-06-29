from __future__ import annotations

from html import escape

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton as B, InlineKeyboardMarkup as M

from runtime import runtime
from services.media import MediaError
from services.player import PlayerError
from utils.keyboards import player_keyboard
from utils.permissions import can_control_user, is_sudo, require_control
from utils.text import duration, now_playing, tr

PLAY_COMMANDS=["play","vplay","playforce","vplayforce","cplay","cvplay","cplayforce","cvplayforce"]
CONTROL_COMMANDS=["pause","resume","skip","stop","end","queue","player","loop","shuffle","seek","speed","volume","cpause","cresume","cskip","cstop","cend","cqueue","cplayer"]


async def send_now(m, track):
    card=await runtime.thumbs.render("now playing",track.title,track.source,track.thumbnail,track.requester_name,m.chat.title or "Telegram",track.duration,0)
    try: await m.reply_photo(str(card),caption=now_playing(track,m.chat.title or "Telegram"),reply_markup=player_keyboard())
    finally: runtime.thumbs.cleanup(card)


async def playback_chat_id(m) -> int:
    if not m.command[0].lower().startswith("c"): return m.chat.id
    try:
        chat=await runtime.bot.get_chat(m.chat.id)
        linked=getattr(chat,"linked_chat",None)
        return linked.id if linked else m.chat.id
    except Exception: return m.chat.id


def register(app):
    @app.on_message(filters.command(PLAY_COMMANDS))
    async def play(_,m):
        if not await require_control(m): return
        if await runtime.db.get("maintenance",False) and not await is_sudo(m.from_user.id):
            await m.reply_text("🛠 <b>Miku is having a tiny tune-up.</b>\nPlease try again soon."); return
        cmd=m.command[0].lower(); video="vplay" in cmd; force="force" in cmd
        chat_id=await playback_chat_id(m)
        try:
            helper=await runtime.assistant.get_me(); await runtime.assistant.get_chat_member(chat_id,helper.id)
        except Exception:
            helper=await runtime.assistant.get_me()
            await m.reply_text("🤖 <b>Add me baby</b>\nThe assistant account must be in this chat before I can join its voice chat.",reply_markup=M([[B("➕ Add Assistant",url=f"tg://user?id={helper.id}")]])); return
        query=" ".join(m.command[1:]); status=await m.reply_text("⏳ <b>Searching the neon soundscape...</b>")
        try:
            track=await runtime.media.resolve(query,m.from_user.id,m.from_user.first_name,video,m.reply_to_message)
            p=runtime.queues.get(chat_id)
            if force:
                await runtime.player.force(chat_id,track); await status.delete(); await send_now(m,track); return
            pos=runtime.queues.add(chat_id,track)
            if not p.current:
                await runtime.player.play_next(chat_id); await status.delete(); await send_now(m,track)
            else:
                lang=await runtime.db.chat_get(m.chat.id,"language","en")
                await status.edit_text(f"💗 <b>{tr(lang,'queued')}</b>\n\n🎵 {escape(track.title)}\n⏱ {duration(track.duration)} • Position <b>{pos}</b>")
        except (MediaError,PlayerError,Exception) as exc:
            await status.edit_text(f"❌ <b>Miku couldn't play that</b>\n<code>{escape(str(exc)[:300])}</code>\n\nCheck that a group voice chat is active and the assistant is a member.")

    @app.on_message(filters.command(CONTROL_COMMANDS))
    async def controls(_,m):
        if not await require_control(m): return
        chat_id=await playback_chat_id(m); cmd=m.command[0].lower().lstrip("c"); p=runtime.queues.get(chat_id)
        try:
            if cmd=="pause": await runtime.player.pause(chat_id); text="⏸ Paused."
            elif cmd=="resume": await runtime.player.resume(chat_id); text="▶️ Resumed."
            elif cmd=="skip":
                track=await runtime.player.skip(chat_id)
                if track: await send_now(m,track); return
                text="⏹ Queue finished. I left the voice chat."
            elif cmd in {"stop","end"}: await runtime.player.stop(chat_id); text="⏹ Stream stopped and queue cleared."
            elif cmd in {"queue","player"}:
                if not p.current: text="📭 <b>The queue is empty, baby.</b>"
                else:
                    upcoming="\n".join(f"{i}. {escape(t.title)} — {duration(t.duration)}" for i,t in enumerate(p.queue[:10],1)) or "No more tracks queued."
                    text=f"📜 <b>ᴍɪᴋᴜ ǫᴜᴇᴜᴇ</b>\n\n▶️ {escape(p.current.title)}\n\n{upcoming}\n\nLoop: {p.loop_mode} • Volume: {p.volume}%"
                if p.current:
                    card=await runtime.thumbs.render("player" if cmd=="player" else "queue",p.current.title,"Interactive player" if cmd=="player" else f"{len(p.queue)} track(s) waiting",p.current.thumbnail,p.current.requester_name,m.chat.title or "Telegram",p.current.duration,p.elapsed())
                    try: await m.reply_photo(str(card),caption=text,reply_markup=player_keyboard() if cmd=="player" else None)
                    finally: runtime.thumbs.cleanup(card)
                else: await m.reply_text(text,reply_markup=player_keyboard() if cmd=="player" else None)
                return
            elif cmd=="shuffle": runtime.queues.shuffle(chat_id); text="🔀 Upcoming songs shuffled."
            elif cmd=="loop":
                mode=(m.command[1].lower() if len(m.command)>1 else {"off":"one","one":"all","all":"off"}[p.loop_mode])
                if mode not in {"off","one","all"}: raise PlayerError("Use /loop off, /loop one, or /loop all.")
                p.loop_mode=mode; text=f"🔁 Loop mode: <b>{mode}</b>"
            elif cmd=="volume":
                level=int(m.command[1]) if len(m.command)>1 else p.volume
                if not 1<=level<=200: raise ValueError("Volume must be 1–200.")
                await runtime.player.volume(chat_id,level); text=f"🔊 Volume: <b>{level}%</b>"
            elif cmd=="seek":
                seconds=int(m.command[1]) if len(m.command)>1 else 0
                if seconds<0 or not p.current or (p.current.duration and seconds>=p.current.duration): raise ValueError("Give a valid second within the track.")
                await runtime.player.replay(chat_id,seconds); text=f"⏩ Seeked to {duration(seconds)}."
            elif cmd=="speed":
                speed=float(m.command[1]) if len(m.command)>1 else p.speed
                if speed not in {.5,.75,1.0,1.25,1.5,2.0}: raise ValueError("Use 0.5, 0.75, 1, 1.25, 1.5, or 2.")
                position=p.elapsed(); p.speed=speed; await runtime.player.replay(chat_id,position); text=f"⚡ Playback speed: <b>{speed}×</b>."
            await m.reply_text(text)
        except Exception as exc: await m.reply_text(f"❌ <b>Control failed</b>\n<code>{escape(str(exc)[:250])}</code>")

    @app.on_callback_query(filters.regex(r"^player:"))
    async def player_callback(_,q):
        if not await can_control_user(q.message.chat.id,q.from_user.id): await q.answer("Admins/auth users only",show_alert=True); return
        action=q.data.split(":",1)[1]
        try:
            if action=="pause": await runtime.player.pause(q.message.chat.id)
            elif action=="resume": await runtime.player.resume(q.message.chat.id)
            elif action=="skip": await runtime.player.skip(q.message.chat.id)
            elif action=="stop": await runtime.player.stop(q.message.chat.id)
            elif action=="replay": await runtime.player.replay(q.message.chat.id)
            elif action=="queue":
                p=runtime.queues.get(q.message.chat.id); await q.answer(f"{len(p.queue)} song(s) waiting",show_alert=True); return
            await q.answer(f"Miku: {action} ✓")
        except Exception as exc: await q.answer(str(exc)[:180],show_alert=True)
