from __future__ import annotations

import time

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton as B, InlineKeyboardMarkup as M

from config import settings
from runtime import runtime
from utils.keyboards import back_keyboard, help_keyboard, start_keyboard
from utils.permissions import is_sudo

START_TEXT = """💞 <b>ʜᴇʏ, {name}</b> 💞
I'm <b>Miku</b> ✨ your cute VC music assistant.

🎵 Play melodies in voice chat
🖼 Branded neon music cards
🌐 English • தமிழ் • हिंदी • Tanglish
🛡 Admin controls & private auth

<i>Turn up the glow. I brought the playlist.</i>"""

HELP = {
"main":"Choose a category below. Every control is available as a command or a clean inline player button.",
"play":"/play /vplay /playforce /vplayforce\n/pause /resume /skip /stop /end\n/queue /player /loop /shuffle\n/seek /speed /volume",
"admin":"Admins and auth users control playback.\n/auth /unauth /authusers\n/panel /settings /language /preview",
"auth":"/auth user — allow control\n/unauth user — revoke\n/authusers — list authorized users",
"broadcast":"Owner: /broadcast [-user] [-assistant] [-pin|-pinloud] message",
"games":"/dice /dart /basket /ball /football /jackpot",
"logs":"Owner: /logs /logger /stats /backupdb /restoredb",
"settings":"/settings — group settings\n/panel — owner control room\n/emojis — editable emoji values",
"thumbnail":"Every banner and YouTube card is rendered by Miku with the @mikuvcrobot watermark.",
"language":"/language en|ta|hi|tanglish",
"assistant":"The assistant account joins the group VC. Add it to your group and allow it to speak if the chat is restricted.",
}


def register(app):
    @app.on_message(group=-10)
    async def guard_and_record(_,m):
        uid=m.from_user.id if m.from_user else 0
        if await runtime.db.is_blacklisted(uid,m.chat.id):
            m.stop_propagation(); return
        command=(m.text or m.caption or "").split(maxsplit=1)[0].lstrip("/!").split("@",1)[0].lower()
        if (m.text or m.caption or "").startswith(("/","!")) and command and await runtime.db.get(f"command:{command}",True) is False and not await is_sudo(uid):
            await m.reply_text("🚫 This command is disabled by Miku's owner."); m.stop_propagation(); return
        if m.from_user:
            await runtime.db.touch(uid,m.from_user.first_name,m.chat.id if m.chat.id<0 else None,m.chat.title or "")
        if settings.log_group_id and await runtime.db.get("logger",True) and (m.text or "").startswith("/"):
            try: await runtime.bot.send_message(settings.log_group_id,f"📜 <b>Command</b> <code>{escape((m.text or '').split()[0])}</code>\nUser: <code>{uid}</code>\nChat: <code>{m.chat.id}</code>")
            except Exception: pass

    @app.on_message(filters.command("start"))
    async def start(_, m):
        u = m.from_user
        await runtime.db.touch(u.id, u.first_name, m.chat.id if m.chat.id < 0 else None, m.chat.title or "")
        caption = await runtime.db.get("start_caption", "") or START_TEXT.format(name=u.mention)
        support=await runtime.db.get("support_group","") or settings.support_group
        updates=await runtime.db.get("update_channel","") or settings.update_channel
        owner=await runtime.db.get("owner_username","") or settings.owner_username
        card = await runtime.thumbs.render("welcome", "Welcome to Miku", "Cute music. Serious controls.", requester=u.first_name, chat=m.chat.title or "Private chat")
        try: await m.reply_photo(str(card), caption=caption, reply_markup=start_keyboard(settings.bot_username, support, updates, owner))
        finally: runtime.thumbs.cleanup(card)

    @app.on_message(filters.command("help"))
    async def help_cmd(_, m):
        caption = await runtime.db.get("help_caption", "") or f"🎧 <b>ᴍɪᴋᴜ ʜᴇʟᴘ</b>\n\n{HELP['main']}\n\n@mikuvcrobot"
        await m.reply_text(caption, reply_markup=help_keyboard())

    @app.on_message(filters.command("ping"))
    async def ping(_, m):
        start_at=time.perf_counter(); x=await m.reply_text("🎼 Tuning..."); ms=(time.perf_counter()-start_at)*1000
        await x.edit_text(f"💗 <b>Pong!</b> <code>{ms:.0f} ms</code>")

    @app.on_message(filters.command("language"))
    async def language(_, m):
        if len(m.command) == 1:
            await m.reply_text("🌐 Choose Miku's language:", reply_markup=M([[B("English",callback_data="lang:en"),B("தமிழ்",callback_data="lang:ta")],[B("हिंदी",callback_data="lang:hi"),B("Tanglish",callback_data="lang:tanglish")],[B("⬅️ Back",callback_data="home"),B("✖️ Close",callback_data="close")]])); return
        lang=m.command[1].lower()
        if lang not in {"en","ta","hi","tanglish"}: await m.reply_text("Use: en, ta, hi, or tanglish"); return
        await runtime.db.chat_set(m.chat.id,"language",lang); await m.reply_text(f"✅ Language set to <b>{lang}</b>.")

    @app.on_callback_query(filters.regex(r"^(home|help:|lang:|language|close)"))
    async def navigation(_, q):
        data=q.data
        if data=="close": await q.message.delete(); return
        if data.startswith("lang:"):
            lang=data.split(":",1)[1]; await runtime.db.chat_set(q.message.chat.id,"language",lang); await q.answer("Language updated",show_alert=True); return
        if data=="language": await q.message.edit_text("🌐 Use /language en, ta, hi, or tanglish.",reply_markup=back_keyboard("help:main")); return
        if data=="home": await q.message.edit_text("💗 <b>Miku VC Music</b>\nYour cute cyber music assistant.\n\n@mikuvcrobot",reply_markup=start_keyboard(settings.bot_username,settings.support_group,settings.update_channel,settings.owner_username)); return
        cat=data.split(":",1)[1]
        if cat=="main": await q.message.edit_text(f"🎧 <b>ᴍɪᴋᴜ ʜᴇʟᴘ</b>\n\n{HELP['main']}",reply_markup=help_keyboard())
        else: await q.message.edit_text(f"✨ <b>{cat.upper()}</b>\n\n{HELP.get(cat, HELP['main'])}",reply_markup=back_keyboard())
