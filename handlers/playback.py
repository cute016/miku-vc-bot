from __future__ import annotations

import asyncio
from html import escape

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton as B, InlineKeyboardMarkup as M

from runtime import runtime
from services.player import PlayerError
from utils.keyboards import player_keyboard
from utils.permissions import can_control_user, is_sudo, require_control
from utils.text import duration, now_playing, short_title, tr

PLAY_COMMANDS = ["play", "vplay", "playforce", "vplayforce", "cplay", "cvplay", "cplayforce", "cvplayforce"]
CONTROL_COMMANDS = ["pause", "resume", "skip", "stop", "end", "queue", "player", "loop", "shuffle", "seek", "speed", "volume", "cpause", "cresume", "cskip", "cstop", "cend", "cqueue", "cplayer"]


async def send_now(message, track):
    card = await runtime.thumbs.render(
        "now playing",
        short_title(track.title, 42),
        track.source,
        track.thumbnail,
        track.requester_name,
        message.chat.title or "Telegram",
        track.duration,
        0,
    )
    try:
        await message.reply_photo(
            str(card),
            caption=now_playing(track, message.chat.title or "Telegram"),
            reply_markup=player_keyboard(),
        )
    finally:
        runtime.thumbs.cleanup(card)


async def playback_chat_id(message) -> int:
    if not message.command[0].lower().startswith("c"):
        return message.chat.id
    try:
        chat = await runtime.bot.get_chat(message.chat.id)
        linked = getattr(chat, "linked_chat", None)
        return linked.id if linked else message.chat.id
    except Exception:
        return message.chat.id


async def ensure_assistant(chat_id: int):
    helper = await runtime.assistant.get_me()
    try:
        await runtime.assistant.get_chat_member(chat_id, helper.id)
        return helper
    except Exception:
        pass

    invite = None
    try:
        chat = await runtime.bot.get_chat(chat_id)
        if getattr(chat, "username", None):
            await runtime.assistant.join_chat(chat.username)
        else:
            invite = await runtime.bot.create_chat_invite_link(
                chat_id,
                name="Miku assistant auto-join",
                member_limit=1,
            )
            await runtime.assistant.join_chat(invite.invite_link)
        await asyncio.sleep(1)
        await runtime.assistant.get_chat_member(chat_id, helper.id)
        return helper
    except Exception as exc:
        raise PlayerError(
            "I couldn't add the assistant automatically. Make the bot an admin "
            "with Invite Users permission, then try /play again. "
            f"Telegram said: {str(exc)[:120]}"
        ) from exc
    finally:
        if invite:
            try:
                await runtime.bot.revoke_chat_invite_link(chat_id, invite.invite_link)
            except Exception:
                pass


def register(app):
    @app.on_message(filters.command(PLAY_COMMANDS))
    async def play(_, message):
        if not await require_control(message):
            return
        if await runtime.db.get("maintenance", False) and not await is_sudo(message.from_user.id):
            await message.reply_text("<b>Miku is under maintenance.</b>\nPlease try again soon.")
            return
        command = message.command[0].lower()
        video = "vplay" in command
        force = "force" in command
        chat_id = await playback_chat_id(message)
        try:
            helper = await ensure_assistant(chat_id)
        except PlayerError as exc:
            helper = await runtime.assistant.get_me()
            await message.reply_text(
                f"<b>Assistant auto-join failed</b>\n{escape(str(exc))}",
                reply_markup=M([[B("Add Assistant", url=f"tg://user?id={helper.id}")]]),
            )
            return

        query = " ".join(message.command[1:])
        status = await message.reply_text("<b>Searching...</b>")
        try:
            track = await runtime.media.resolve(query, message.from_user.id, message.from_user.first_name, video, message.reply_to_message)
            player = runtime.queues.get(chat_id)
            if force:
                await runtime.player.force(chat_id, track)
                await status.delete()
                await send_now(message, track)
                return
            position = runtime.queues.add(chat_id, track)
            if not player.current:
                await runtime.player.play_next(chat_id)
                await status.delete()
                await send_now(message, track)
            else:
                lang = await runtime.db.chat_get(message.chat.id, "language", "en")
                await status.edit_text(
                    f"<b>{tr(lang, 'queued')}</b>\n\n"
                    f"Track: {escape(short_title(track.title, 52))}\n"
                    f"Length: {duration(track.duration)} - Position <b>{position}</b>"
                )
        except Exception as exc:
            detail = str(exc)
            if "googlevideo.com" in detail:
                detail = "YouTube media preparation failed. Please try the song again."
            await status.edit_text(
                f"<b>Miku couldn't play that</b>\n<code>{escape(detail[:300])}</code>\n\n"
                "Check that a group voice chat is active and the assistant is a member."
            )

    @app.on_message(filters.command(CONTROL_COMMANDS))
    async def controls(_, message):
        if not await require_control(message):
            return
        chat_id = await playback_chat_id(message)
        command = message.command[0].lower().lstrip("c")
        player = runtime.queues.get(chat_id)
        try:
            if command == "pause":
                await runtime.player.pause(chat_id)
                text = "Paused."
            elif command == "resume":
                await runtime.player.resume(chat_id)
                text = "Resumed."
            elif command == "skip":
                track = await runtime.player.skip(chat_id)
                if track:
                    await send_now(message, track)
                    return
                text = "Queue finished. I left the voice chat."
            elif command in {"stop", "end"}:
                await runtime.player.stop(chat_id)
                text = "Stream stopped and queue cleared."
            elif command in {"queue", "player"}:
                if not player.current:
                    text = "<b>The queue is empty.</b>"
                else:
                    upcoming = "\n".join(
                        f"{index}. {escape(short_title(track.title, 36))} - {duration(track.duration)}"
                        for index, track in enumerate(player.queue[:10], 1)
                    ) or "No more tracks queued."
                    text = (
                        "<b>Miku Queue</b>\n\n"
                        f"Playing: {escape(short_title(player.current.title, 42))}\n\n"
                        f"{upcoming}\n\n"
                        f"Loop: {player.loop_mode} - Volume: {player.volume}%"
                    )
                if player.current:
                    card = await runtime.thumbs.render(
                        "player" if command == "player" else "queue",
                        short_title(player.current.title, 42),
                        "Interactive player" if command == "player" else f"{len(player.queue)} track(s) waiting",
                        player.current.thumbnail,
                        player.current.requester_name,
                        message.chat.title or "Telegram",
                        player.current.duration,
                        player.elapsed(),
                    )
                    try:
                        await message.reply_photo(str(card), caption=text, reply_markup=player_keyboard() if command == "player" else None)
                    finally:
                        runtime.thumbs.cleanup(card)
                else:
                    await message.reply_text(text, reply_markup=player_keyboard() if command == "player" else None)
                return
            elif command == "shuffle":
                runtime.queues.shuffle(chat_id)
                text = "Upcoming songs shuffled."
            elif command == "loop":
                mode = message.command[1].lower() if len(message.command) > 1 else {"off": "one", "one": "all", "all": "off"}[player.loop_mode]
                if mode not in {"off", "one", "all"}:
                    raise PlayerError("Use /loop off, /loop one, or /loop all.")
                player.loop_mode = mode
                text = f"Loop mode: <b>{mode}</b>"
            elif command == "volume":
                level = int(message.command[1]) if len(message.command) > 1 else player.volume
                if not 1 <= level <= 200:
                    raise ValueError("Volume must be 1-200.")
                await runtime.player.volume(chat_id, level)
                text = f"Volume: <b>{level}%</b>"
            elif command == "seek":
                seconds = int(message.command[1]) if len(message.command) > 1 else 0
                if seconds < 0 or not player.current or (player.current.duration and seconds >= player.current.duration):
                    raise ValueError("Give a valid second within the track.")
                await runtime.player.replay(chat_id, seconds)
                text = f"Seeked to {duration(seconds)}."
            elif command == "speed":
                speed = float(message.command[1]) if len(message.command) > 1 else player.speed
                if speed not in {0.5, 0.75, 1.0, 1.25, 1.5, 2.0}:
                    raise ValueError("Use 0.5, 0.75, 1, 1.25, 1.5, or 2.")
                position = player.elapsed()
                player.speed = speed
                await runtime.player.replay(chat_id, position)
                text = f"Playback speed: <b>{speed}x</b>."
            await message.reply_text(text)
        except Exception as exc:
            await message.reply_text(f"<b>Control failed</b>\n<code>{escape(str(exc)[:250])}</code>")

    @app.on_callback_query(filters.regex(r"^player:"))
    async def player_callback(_, query):
        if not await can_control_user(query.message.chat.id, query.from_user.id):
            await query.answer("Admins/auth users only", show_alert=True)
            return
        action = query.data.split(":", 1)[1]
        try:
            if action == "pause":
                await runtime.player.pause(query.message.chat.id)
            elif action == "resume":
                await runtime.player.resume(query.message.chat.id)
            elif action == "skip":
                await runtime.player.skip(query.message.chat.id)
            elif action == "stop":
                await runtime.player.stop(query.message.chat.id)
            elif action == "replay":
                await runtime.player.replay(query.message.chat.id)
            elif action == "queue":
                player = runtime.queues.get(query.message.chat.id)
                await query.answer(f"{len(player.queue)} song(s) waiting", show_alert=True)
                return
            await query.answer(f"Miku: {action}")
        except Exception as exc:
            await query.answer(str(exc)[:180], show_alert=True)
