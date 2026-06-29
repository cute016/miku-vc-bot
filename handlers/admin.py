from __future__ import annotations

from html import escape

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton as B, InlineKeyboardMarkup as M

from config import settings
from database.db import EMOJI_DEFAULTS
from runtime import runtime
from utils.keyboards import back_keyboard, panel_keyboard
from utils.permissions import can_control, is_sudo, require_control, require_sudo

pending: dict[tuple[int,int], str] = {}
EDITABLE={"bot_name","start_caption","help_caption","watermark","theme","support_group","update_channel","owner_username","force_subscribe","assistant_username"}


async def resolve_user(m):
    if m.reply_to_message and m.reply_to_message.from_user: return m.reply_to_message.from_user
    if len(m.command)<2: return None
    value=m.command[1]
    try: return await runtime.bot.get_users(int(value) if value.lstrip("-").isdigit() else value)
    except Exception: return None


def register(app):
    @app.on_message(filters.command(["settings"]))
    async def group_settings(_,m):
        lang=await runtime.db.chat_get(m.chat.id,"language","en")
        await m.reply_text(f"⚙️ <b>ᴍɪᴋᴜ sᴇᴛᴛɪɴɢs</b>\n\n🌐 Language: <b>{lang}</b>\n🔊 Default volume: <b>{runtime.queues.get(m.chat.id).volume}%</b>\n🔁 Loop: <b>{runtime.queues.get(m.chat.id).loop_mode}</b>\n\nUse /language, /volume and /loop to change them.",reply_markup=back_keyboard("home"))

    @app.on_message(filters.command(["auth","unauth","authusers"]))
    async def auth(_,m):
        if not await require_control(m): return
        cmd=m.command[0].lower()
        if cmd=="authusers":
            ids=await runtime.db.auth_list(m.chat.id); await m.reply_text("🔐 <b>Authorized users</b>\n\n"+("\n".join(f"• <code>{x}</code>" for x in ids) if ids else "Nobody yet.")); return
        user=await resolve_user(m)
        if not user: await m.reply_text(f"Reply to a user or use /{cmd} user_id"); return
        if cmd=="auth": await runtime.db.auth_add(m.chat.id,user.id); word="authorized"
        else: await runtime.db.auth_remove(m.chat.id,user.id); word="removed"
        await m.reply_text(f"✅ {user.mention} {word}.")

    @app.on_message(filters.command("panel"))
    async def panel(_,m):
        if not await require_sudo(m): return
        card=await runtime.thumbs.render("admin panel","Miku Control Room","Edit the bot without touching code",requester=m.from_user.first_name,chat=m.chat.title or "Owner")
        try: await m.reply_photo(str(card),caption="👑 <b>ᴍɪᴋᴜ ᴄᴏɴᴛʀᴏʟ ʀᴏᴏᴍ</b>\nEverything important lives behind these buttons.\n\n@mikuvcrobot",reply_markup=panel_keyboard())
        finally: runtime.thumbs.cleanup(card)

    @app.on_message(filters.command("command"))
    async def command_setting(_,m):
        if not await require_sudo(m): return
        if len(m.command)<3 or m.command[2].lower() not in {"enable","disable"}: await m.reply_text("Use /command play enable (or disable)"); return
        name=m.command[1].lower().lstrip("/"); value=m.command[2].lower()=="enable"; await runtime.db.set(f"command:{name}",value); await m.reply_text(f"✅ /{name} {'enabled' if value else 'disabled'}.")

    @app.on_message(filters.command(["addsudo","delsudo","sudousers"]))
    async def sudo_manager(_,m):
        if not m.from_user or m.from_user.id!=settings.owner_id: await m.reply_text("👑 Owner only."); return
        current=set(await runtime.db.get("sudo_users",[])); cmd=m.command[0].lower()
        if cmd=="sudousers": await m.reply_text("👑 <b>Database sudo users</b>\n"+("\n".join(f"• <code>{x}</code>" for x in sorted(current)) or "None")); return
        user=await resolve_user(m)
        if not user: await m.reply_text(f"Reply to a user or use /{cmd} user_id"); return
        if cmd=="addsudo": current.add(user.id)
        else: current.discard(user.id)
        await runtime.db.set("sudo_users",sorted(current)); await m.reply_text("✅ Sudo list updated.")

    @app.on_message(filters.command("emojis"))
    async def emojis(_,m):
        if not await require_sudo(m): return
        rows=[[B(f"{fallback} {key.title()}",callback_data=f"edit:emoji:{key}")] for key,fallback in EMOJI_DEFAULTS.items()]
        rows.append([B("⬅️ Back",callback_data="panel:main"),B("✖️ Close",callback_data="close")])
        await m.reply_text("✨ <b>ᴘʀᴇᴍɪᴜᴍ ᴇᴍᴏᴊɪ ᴇᴅɪᴛᴏʀ</b>\nTap a field, then send a custom emoji ID or a normal emoji fallback.",reply_markup=M(rows))

    @app.on_message(filters.command("preview"))
    async def preview(_,m):
        if not await require_sudo(m): return
        await m.reply_text("👁 <b>ʟɪᴠᴇ ᴜɪ ᴘʀᴇᴠɪᴇᴡ</b>",reply_markup=M([[B("👁 Preview Start",callback_data="preview:start"),B("🎧 Preview Player",callback_data="preview:player")],[B("📜 Preview Help",callback_data="preview:help"),B("🎵 Preview Queue",callback_data="preview:queue")],[B("🖼 Preview Thumbnail",callback_data="preview:thumbnail"),B("❌ Preview Error",callback_data="preview:error")],[B("🛠 Maintenance",callback_data="preview:maintenance")],[B("✅ Apply",callback_data="preview:apply"),B("❌ Cancel",callback_data="close")],[B("⬅️ Back",callback_data="panel:main"),B("✖️ Close",callback_data="close")]]))

    @app.on_callback_query(filters.regex(r"^(panel:|edit:|preview:)"))
    async def panel_callbacks(_,q):
        if not await is_sudo(q.from_user.id): await q.answer("Owner only",show_alert=True); return
        data=q.data
        if data=="panel:main": await q.message.edit_caption("👑 <b>ᴍɪᴋᴜ ᴄᴏɴᴛʀᴏʟ ʀᴏᴏᴍ</b>",reply_markup=panel_keyboard()) if q.message.photo else await q.message.edit_text("👑 <b>ᴍɪᴋᴜ ᴄᴏɴᴛʀᴏʟ ʀᴏᴏᴍ</b>",reply_markup=panel_keyboard()); return
        if data.startswith("edit:"):
            key=data.removeprefix("edit:"); pending[(q.message.chat.id,q.from_user.id)]=key
            await q.message.reply_text(f"✏️ Send the new value for <b>{escape(key)}</b>.\nSend <code>cancel</code> to stop."); await q.answer(); return
        if data.startswith("preview:"):
            kind=data.split(":",1)[1]
            if kind=="apply": await q.answer("Current settings are already live ✓",show_alert=True); return
            title={"start":"Welcome to Miku","player":"Midnight Melody","help":"Help & Commands","queue":"Up Next","thumbnail":"Miku VC Music","error":"Oops, a tiny glitch","maintenance":"Miku is tuning up"}.get(kind,"Miku Preview")
            card=await runtime.thumbs.render("now playing" if kind=="player" else kind,title,"Live preview • all changes are instant",requester=q.from_user.first_name,chat=q.message.chat.title or "Preview",length=245,progress=82)
            try: await q.message.reply_photo(str(card),caption=f"👁 <b>{kind.title()} preview</b>\n@mikuvcrobot")
            finally: runtime.thumbs.cleanup(card)
            await q.answer(); return
        section=data.split(":",1)[1]
        if section=="maintenance":
            value=not await runtime.db.get("maintenance",False); await runtime.db.set("maintenance",value); await q.answer(f"Maintenance {'enabled' if value else 'disabled'}",show_alert=True); return
        if section=="logger":
            value=not await runtime.db.get("logger",True); await runtime.db.set("logger",value); await q.answer(f"Logger {'enabled' if value else 'disabled'}",show_alert=True); return
        if section=="emojis":
            rows=[[B(f"{v} {k.title()}",callback_data=f"edit:emoji:{k}")] for k,v in EMOJI_DEFAULTS.items()]; rows.append([B("⬅️ Back",callback_data="panel:main")])
            await q.message.reply_text("✨ Pick an emoji field to edit.",reply_markup=M(rows)); await q.answer(); return
        if section in {"bot","thumbs","start","help","buttons","language"}:
            mapping={"bot":["bot_name","owner_username","assistant_username"],"thumbs":["watermark","theme"],"start":["start_caption"],"help":["help_caption"],"buttons":["support_group","update_channel"],"language":["force_subscribe"]}
            rows=[[B(k.replace('_',' ').title(),callback_data=f"edit:{k}")] for k in mapping[section]]; rows.append([B("⬅️ Back",callback_data="panel:main"),B("✖️ Close",callback_data="close")]); await q.message.reply_text(f"⚙️ <b>{section.upper()}</b> settings",reply_markup=M(rows)); await q.answer(); return
        if section=="commands": await q.message.reply_text("⌨️ Use <code>/command play disable</code> or <code>/command play enable</code> for any command.",reply_markup=back_keyboard("panel:main")); await q.answer(); return
        if section=="sudo": await q.message.reply_text("👑 Owner tools: /addsudo, /delsudo, /sudousers (reply to a user or give an ID).",reply_markup=back_keyboard("panel:main")); await q.answer(); return
        await q.answer("Use the matching command shown in /help for this section.",show_alert=True)

    @app.on_message(filters.text & ~filters.regex(r"^/"),group=2)
    async def pending_input(_,m):
        if not m.from_user: return
        key=pending.pop((m.chat.id,m.from_user.id),None)
        if not key: return
        if m.text.strip().lower()=="cancel": await m.reply_text("❌ Edit cancelled."); return
        if key.startswith("emoji:"):
            name=key.split(":",1)[1]
            if name not in EMOJI_DEFAULTS: return
            await runtime.db.set(key,m.text.strip()[:80])
        elif key in EDITABLE:
            value=m.text.strip()[:3500]; await runtime.db.set(key,value)
            if key=="watermark": runtime.thumbs.watermark=value
        await m.reply_text(f"✅ <b>{escape(key)}</b> updated. Preview it with /preview.")
