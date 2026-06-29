from __future__ import annotations

import re
from html import escape

from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.errors import SessionPasswordNeeded
from pyrogram.types import InlineKeyboardButton as B, InlineKeyboardMarkup as M

from config import settings, update_env_value
from database.db import EMOJI_DEFAULTS
from runtime import runtime
from utils.keyboards import back_keyboard, panel_keyboard
from utils.permissions import require_control, require_sudo, is_sudo

pending: dict[tuple[int, int], str] = {}
EDITABLE = {
    "bot_name",
    "start_caption",
    "help_caption",
    "watermark",
    "theme",
    "support_group",
    "update_channel",
    "owner_username",
    "force_subscribe",
    "assistant_username",
}
PHONE_RE = re.compile(r"^\+\d{8,15}$")
session_flows: dict[int, dict[str, object]] = {}


async def resolve_user(message):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    if len(message.command) < 2:
        return None
    value = message.command[1]
    try:
        return await runtime.bot.get_users(int(value) if value.lstrip("-").isdigit() else value)
    except Exception:
        return None


def assistant_keyboard() -> M:
    return M(
        [
            [B("Generate Session", callback_data="session:generate"), B("Replace String", callback_data="session:replace")],
            [B("Status", callback_data="session:status")],
            [B("Back", callback_data="panel:main"), B("Close", callback_data="close")],
        ]
    )


def private_panel_keyboard() -> M:
    return M([[B("Open Private Chat", url=f"https://t.me/{settings.bot_username}")]])


async def assistant_status_text() -> str:
    configured = bool(settings.session_string) or bool(await runtime.db.get("assistant_session_configured", False))
    return (
        "<b>Assistant session controls</b>\n\n"
        f"Configured: <b>{'yes' if configured else 'no'}</b>\n"
        "Create a new assistant session or replace the current session string here.\n"
        "For safety, the session string is never shown back."
    )


async def close_session_flow(user_id: int) -> None:
    flow = session_flows.pop(user_id, None)
    client = flow.get("client") if flow else None
    if client:
        try:
            await client.disconnect()
        except Exception:
            pass


async def validate_session_string(value: str):
    client = Client(
        "miku_session_check",
        api_id=settings.api_id,
        api_hash=settings.api_hash,
        session_string=value,
        in_memory=True,
        no_updates=True,
    )
    try:
        await client.connect()
        return await client.get_me()
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


async def save_session_string(value: str) -> None:
    update_env_value("SESSION_STRING", value)
    await runtime.db.set("assistant_session_configured", True)


async def finish_generated_session(message, client: Client) -> None:
    session_string = await client.export_session_string()
    me = await client.get_me()
    await save_session_string(session_string)
    await close_session_flow(message.from_user.id)
    try:
        await message.delete()
    except Exception:
        pass
    await message.reply_text(
        f"Assistant session saved for <b>{escape(me.first_name)}</b>.\n"
        "Restart the bot once so the new assistant account takes over."
    )


def register(app):
    @app.on_message(filters.command(["settings"]))
    async def group_settings(_, message):
        lang = await runtime.db.chat_get(message.chat.id, "language", "en")
        queue = runtime.queues.get(message.chat.id)
        await message.reply_text(
            f"<b>Miku settings</b>\n\n"
            f"Language: <b>{lang}</b>\n"
            f"Default volume: <b>{queue.volume}%</b>\n"
            f"Loop: <b>{queue.loop_mode}</b>\n\n"
            "Use /language, /volume and /loop to change them.",
            reply_markup=back_keyboard("home"),
        )

    @app.on_message(filters.command(["auth", "unauth", "authusers"]))
    async def auth(_, message):
        if not await require_control(message):
            return
        command = message.command[0].lower()
        if command == "authusers":
            ids = await runtime.db.auth_list(message.chat.id)
            body = "\n".join(f"- <code>{item}</code>" for item in ids) if ids else "Nobody yet."
            await message.reply_text(f"<b>Authorized users</b>\n\n{body}")
            return
        user = await resolve_user(message)
        if not user:
            await message.reply_text(f"Reply to a user or use /{command} user_id")
            return
        if command == "auth":
            await runtime.db.auth_add(message.chat.id, user.id)
            word = "authorized"
        else:
            await runtime.db.auth_remove(message.chat.id, user.id)
            word = "removed"
        await message.reply_text(f"{user.mention} {word}.")

    @app.on_message(filters.command("panel"))
    async def panel(_, message):
        if not await require_sudo(message):
            return
        card = await runtime.thumbs.render(
            "admin panel",
            "Miku Control Room",
            "Edit the bot without touching code",
            requester=message.from_user.first_name,
            chat=message.chat.title or "Owner",
        )
        try:
            await message.reply_photo(
                str(card),
                caption="<b>Miku control room</b>\nEverything important lives behind these buttons.\n\n@mikuvcrobot",
                reply_markup=panel_keyboard(),
            )
        finally:
            runtime.thumbs.cleanup(card)

    @app.on_message(filters.command("command"))
    async def command_setting(_, message):
        if not await require_sudo(message):
            return
        if len(message.command) < 3 or message.command[2].lower() not in {"enable", "disable"}:
            await message.reply_text("Use /command play enable or /command play disable")
            return
        name = message.command[1].lower().lstrip("/")
        enabled = message.command[2].lower() == "enable"
        await runtime.db.set(f"command:{name}", enabled)
        await message.reply_text(f"/{name} {'enabled' if enabled else 'disabled'}.")

    @app.on_message(filters.command(["addsudo", "delsudo", "sudousers"]))
    async def sudo_manager(_, message):
        if not message.from_user or message.from_user.id != settings.owner_id:
            await message.reply_text("Owner only.")
            return
        current = set(await runtime.db.get("sudo_users", []))
        command = message.command[0].lower()
        if command == "sudousers":
            body = "\n".join(f"- <code>{item}</code>" for item in sorted(current)) or "None"
            await message.reply_text(f"<b>Database sudo users</b>\n{body}")
            return
        user = await resolve_user(message)
        if not user:
            await message.reply_text(f"Reply to a user or use /{command} user_id")
            return
        if command == "addsudo":
            current.add(user.id)
        else:
            current.discard(user.id)
        await runtime.db.set("sudo_users", sorted(current))
        await message.reply_text("Sudo list updated.")

    @app.on_message(filters.command("emojis"))
    async def emojis(_, message):
        if not await require_sudo(message):
            return
        rows = [[B(f"{fallback} {key.title()}", callback_data=f"edit:emoji:{key}")] for key, fallback in EMOJI_DEFAULTS.items()]
        rows.append([B("Back", callback_data="panel:main"), B("Close", callback_data="close")])
        await message.reply_text(
            "<b>Premium emoji editor</b>\nTap a field, then send a custom emoji ID or a normal emoji fallback.",
            reply_markup=M(rows),
        )

    @app.on_message(filters.command("preview"))
    async def preview(_, message):
        if not await require_sudo(message):
            return
        await message.reply_text(
            "<b>Live UI preview</b>",
            reply_markup=M(
                [
                    [B("Preview Start", callback_data="preview:start"), B("Preview Player", callback_data="preview:player")],
                    [B("Preview Help", callback_data="preview:help"), B("Preview Queue", callback_data="preview:queue")],
                    [B("Preview Thumbnail", callback_data="preview:thumbnail"), B("Preview Error", callback_data="preview:error")],
                    [B("Maintenance", callback_data="preview:maintenance")],
                    [B("Apply", callback_data="preview:apply"), B("Cancel", callback_data="close")],
                    [B("Back", callback_data="panel:main"), B("Close", callback_data="close")],
                ]
            ),
        )

    @app.on_callback_query(filters.regex(r"^(panel:|edit:|preview:|session:)"))
    async def panel_callbacks(_, query):
        if not await is_sudo(query.from_user.id):
            await query.answer("Owner only", show_alert=True)
            return
        data = query.data
        if data == "panel:main":
            if query.message.photo:
                await query.message.edit_caption("<b>Miku control room</b>", reply_markup=panel_keyboard())
            else:
                await query.message.edit_text("<b>Miku control room</b>", reply_markup=panel_keyboard())
            return
        if data.startswith("edit:"):
            key = data.removeprefix("edit:")
            pending[(query.message.chat.id, query.from_user.id)] = key
            await query.message.reply_text(
                f"Send the new value for <b>{escape(key)}</b>.\nSend <code>cancel</code> to stop."
            )
            await query.answer()
            return
        if data.startswith("session:"):
            if query.message.chat.type != ChatType.PRIVATE:
                await query.message.reply_text(
                    "Open this panel in my private chat to manage the assistant session safely.",
                    reply_markup=private_panel_keyboard(),
                )
                await query.answer()
                return
            action = data.split(":", 1)[1]
            if action == "status":
                await query.message.reply_text(await assistant_status_text(), reply_markup=assistant_keyboard())
                await query.answer()
                return
            if action == "replace":
                await close_session_flow(query.from_user.id)
                pending[(query.message.chat.id, query.from_user.id)] = "session_string"
                await query.message.reply_text(
                    "Send the new <code>SESSION_STRING</code> now.\n"
                    "I will save it without showing it back. Send <code>cancel</code> to stop."
                )
                await query.answer()
                return
            if action == "generate":
                await close_session_flow(query.from_user.id)
                pending[(query.message.chat.id, query.from_user.id)] = "session_phone"
                await query.message.reply_text(
                    "Send the assistant phone number in international format.\n"
                    "Example: <code>+12345678901</code>"
                )
                await query.answer()
                return
        if data.startswith("preview:"):
            kind = data.split(":", 1)[1]
            if kind == "apply":
                await query.answer("Current settings are already live", show_alert=True)
                return
            title = {
                "start": "Welcome to Miku",
                "player": "Midnight Melody",
                "help": "Help & Commands",
                "queue": "Up Next",
                "thumbnail": "Miku VC Music",
                "error": "Oops, a tiny glitch",
                "maintenance": "Miku is tuning up",
            }.get(kind, "Miku Preview")
            card = await runtime.thumbs.render(
                "now playing" if kind == "player" else kind,
                title,
                "Live preview - all changes are instant",
                requester=query.from_user.first_name,
                chat=query.message.chat.title or "Preview",
                length=245,
                progress=82,
            )
            try:
                await query.message.reply_photo(str(card), caption=f"<b>{kind.title()} preview</b>\n@mikuvcrobot")
            finally:
                runtime.thumbs.cleanup(card)
            await query.answer()
            return
        section = data.split(":", 1)[1]
        if section == "maintenance":
            value = not await runtime.db.get("maintenance", False)
            await runtime.db.set("maintenance", value)
            await query.answer(f"Maintenance {'enabled' if value else 'disabled'}", show_alert=True)
            return
        if section == "logger":
            value = not await runtime.db.get("logger", True)
            await runtime.db.set("logger", value)
            await query.answer(f"Logger {'enabled' if value else 'disabled'}", show_alert=True)
            return
        if section == "emojis":
            rows = [[B(f"{value} {key.title()}", callback_data=f"edit:emoji:{key}")] for key, value in EMOJI_DEFAULTS.items()]
            rows.append([B("Back", callback_data="panel:main")])
            await query.message.reply_text("Pick an emoji field to edit.", reply_markup=M(rows))
            await query.answer()
            return
        if section == "assistant":
            if query.message.chat.type != ChatType.PRIVATE:
                await query.message.reply_text(
                    "Assistant session tools work only in private chat.",
                    reply_markup=private_panel_keyboard(),
                )
            else:
                await query.message.reply_text(await assistant_status_text(), reply_markup=assistant_keyboard())
            await query.answer()
            return
        if section in {"bot", "thumbs", "start", "help", "buttons", "language"}:
            mapping = {
                "bot": ["bot_name", "owner_username", "assistant_username"],
                "thumbs": ["watermark", "theme"],
                "start": ["start_caption"],
                "help": ["help_caption"],
                "buttons": ["support_group", "update_channel"],
                "language": ["force_subscribe"],
            }
            rows = [[B(item.replace("_", " ").title(), callback_data=f"edit:{item}")] for item in mapping[section]]
            rows.append([B("Back", callback_data="panel:main"), B("Close", callback_data="close")])
            await query.message.reply_text(f"<b>{section.upper()}</b> settings", reply_markup=M(rows))
            await query.answer()
            return
        if section == "commands":
            await query.message.reply_text(
                "Use <code>/command play disable</code> or <code>/command play enable</code> for any command.",
                reply_markup=back_keyboard("panel:main"),
            )
            await query.answer()
            return
        if section == "sudo":
            await query.message.reply_text(
                "Owner tools: /addsudo, /delsudo, /sudousers (reply to a user or give an ID).",
                reply_markup=back_keyboard("panel:main"),
            )
            await query.answer()
            return
        await query.answer("Use the matching command shown in /help for this section.", show_alert=True)

    @app.on_message(filters.text & ~filters.regex(r"^/"), group=2)
    async def pending_input(_, message):
        if not message.from_user:
            return
        key = pending.pop((message.chat.id, message.from_user.id), None)
        if not key:
            return
        if message.text.strip().lower() == "cancel":
            await close_session_flow(message.from_user.id)
            await message.reply_text("Edit cancelled.")
            return
        if key == "session_string":
            if message.chat.type != ChatType.PRIVATE:
                await message.reply_text("Replace the assistant session in private chat only.")
                return
            value = message.text.strip()
            try:
                me = await validate_session_string(value)
                await save_session_string(value)
                try:
                    await message.delete()
                except Exception:
                    pass
                await message.reply_text(
                    f"Assistant string updated for <b>{escape(me.first_name)}</b>.\n"
                    "Restart the bot once so the new session takes over."
                )
            except Exception as exc:
                pending[(message.chat.id, message.from_user.id)] = "session_string"
                await message.reply_text(f"That session string could not be used.\n<code>{escape(str(exc)[:220])}</code>")
            return
        if key == "session_phone":
            if message.chat.type != ChatType.PRIVATE:
                await message.reply_text("Generate the assistant session in private chat only.")
                return
            phone = message.text.strip().replace(" ", "")
            if not PHONE_RE.fullmatch(phone):
                pending[(message.chat.id, message.from_user.id)] = "session_phone"
                await message.reply_text("Send the number like <code>+12345678901</code>.")
                return
            client = Client(
                f"miku_session_builder_{message.from_user.id}",
                api_id=settings.api_id,
                api_hash=settings.api_hash,
                in_memory=True,
                no_updates=True,
            )
            try:
                await client.connect()
                sent = await client.send_code(phone)
                session_flows[message.from_user.id] = {
                    "client": client,
                    "phone": phone,
                    "phone_code_hash": sent.phone_code_hash,
                }
                pending[(message.chat.id, message.from_user.id)] = "session_code"
                try:
                    await message.delete()
                except Exception:
                    pass
                await message.reply_text(
                    "Telegram sent a login code.\nSend that code here now. You can type it with or without spaces."
                )
            except Exception as exc:
                try:
                    await client.disconnect()
                except Exception:
                    pass
                pending[(message.chat.id, message.from_user.id)] = "session_phone"
                await message.reply_text(f"I could not request the Telegram login code.\n<code>{escape(str(exc)[:220])}</code>")
            return
        if key == "session_code":
            flow = session_flows.get(message.from_user.id)
            if not flow:
                await message.reply_text("The session setup expired. Start again from the assistant panel.")
                return
            code = "".join(ch for ch in message.text if ch.isdigit())
            if len(code) < 4:
                pending[(message.chat.id, message.from_user.id)] = "session_code"
                await message.reply_text("That code looks too short. Send the full Telegram code.")
                return
            client = flow["client"]
            try:
                await client.sign_in(flow["phone"], flow["phone_code_hash"], code)
                await finish_generated_session(message, client)
            except SessionPasswordNeeded:
                pending[(message.chat.id, message.from_user.id)] = "session_password"
                try:
                    await message.delete()
                except Exception:
                    pass
                await message.reply_text("This account has 2-step verification. Send the password now.")
            except Exception as exc:
                pending[(message.chat.id, message.from_user.id)] = "session_code"
                await message.reply_text(f"Telegram rejected that code.\n<code>{escape(str(exc)[:220])}</code>")
            return
        if key == "session_password":
            flow = session_flows.get(message.from_user.id)
            if not flow:
                await message.reply_text("The session setup expired. Start again from the assistant panel.")
                return
            client = flow["client"]
            try:
                await client.check_password(message.text)
                await finish_generated_session(message, client)
            except Exception as exc:
                pending[(message.chat.id, message.from_user.id)] = "session_password"
                await message.reply_text(f"Telegram rejected that password.\n<code>{escape(str(exc)[:220])}</code>")
            return
        if key.startswith("emoji:"):
            name = key.split(":", 1)[1]
            if name in EMOJI_DEFAULTS:
                await runtime.db.set(key, message.text.strip()[:80])
        elif key in EDITABLE:
            value = message.text.strip()[:3500]
            await runtime.db.set(key, value)
            if key == "watermark":
                runtime.thumbs.watermark = value
        await message.reply_text(f"<b>{escape(key)}</b> updated. Preview it with /preview.")
