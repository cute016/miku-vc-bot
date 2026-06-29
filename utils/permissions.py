from __future__ import annotations

from pyrogram.enums import ChatMemberStatus, ChatType

from config import settings
from runtime import runtime


async def is_sudo(user_id: int) -> bool:
    stored=await runtime.db.get("sudo_users",[]) if runtime.db else []
    return user_id in settings.all_sudo or user_id in stored


async def can_control(message) -> bool:
    if not message.from_user: return bool(message.sender_chat)
    uid = message.from_user.id
    if await is_sudo(uid): return True
    if message.chat.type == ChatType.PRIVATE: return False
    if await runtime.db.is_auth(message.chat.id, uid): return True
    try:
        member = await runtime.bot.get_chat_member(message.chat.id, uid)
        return member.status in {ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR}
    except Exception: return False


async def require_control(message) -> bool:
    if await can_control(message): return True
    await message.reply_text("🔐 <b>Not authorized</b>\nOnly admins and authorized users can control Miku.")
    return False


async def can_control_user(chat_id: int, user_id: int) -> bool:
    if await is_sudo(user_id) or await runtime.db.is_auth(chat_id, user_id): return True
    try:
        member = await runtime.bot.get_chat_member(chat_id, user_id)
        return member.status in {ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR}
    except Exception: return False


async def require_sudo(message) -> bool:
    if message.from_user and await is_sudo(message.from_user.id): return True
    await message.reply_text("👑 This command is reserved for Miku's owner and sudo users.")
    return False
