from pyrogram.types import InlineKeyboardButton as B, InlineKeyboardMarkup as M


def start_keyboard(username: str, support: str, updates: str, owner: str) -> M:
    return M([[B("➕ Add Me Baby", url=f"https://t.me/{username}?startgroup=true")],
              [B("👑 Owner", url=f"https://t.me/{owner.lstrip('@')}"), B("🌐 Language", callback_data="language")],
              [B("💬 Support", url=support), B("📢 Updates", url=updates)],
              [B("⚙️ Help & Commands", callback_data="help:main")], [B("✖️ Close", callback_data="close")]])


def player_keyboard() -> M:
    return M([[B("▶️ Resume", callback_data="player:resume"), B("⏸ Pause", callback_data="player:pause"), B("🔄 Replay", callback_data="player:replay")],
              [B("⏭ Skip", callback_data="player:skip"), B("⏹ Stop", callback_data="player:stop"), B("📜 Queue", callback_data="player:queue")],
              [B("⬅️ Back", callback_data="home"), B("✖️ Close", callback_data="close")]])


def help_keyboard() -> M:
    rows = []
    cats = [("🎵 Play","play"),("👑 Admin","admin"),("🔐 Auth","auth"),("📡 Broadcast","broadcast"),("🎮 Games","games"),("📜 Logs","logs"),("⚙️ Settings","settings"),("🖼 Thumbnail","thumbnail"),("🌐 Language","language"),("🤖 Assistant","assistant")]
    for i in range(0, len(cats), 2): rows.append([B(a, callback_data=f"help:{b}") for a,b in cats[i:i+2]])
    rows.append([B("⬅️ Back", callback_data="home"), B("✖️ Close", callback_data="close")]); return M(rows)


def back_keyboard(target: str = "help:main") -> M: return M([[B("⬅️ Back", callback_data=target), B("✖️ Close", callback_data="close")]])


def panel_keyboard() -> M:
    items=[("🤖 Bot Settings","panel:bot"),("⌨️ Commands","panel:commands"),("✨ Emojis","panel:emojis"),("🖼 Thumbnails","panel:thumbs"),("📝 Start Text","panel:start"),("📖 Help Text","panel:help"),("🔘 Buttons","panel:buttons"),("🌐 Language","panel:language"),("🛠 Maintenance","panel:maintenance"),("📜 Logger","panel:logger"),("📡 Broadcast","panel:broadcast"),("📊 Statistics","panel:stats"),("🔐 Auth Users","panel:auth"),("👑 Sudo Users","panel:sudo"),("🚫 Blacklist","panel:blacklist"),("🔄 Restart","panel:restart")]
    rows=[[B(a,callback_data=b) for a,b in items[i:i+2]] for i in range(0,len(items),2)]
    rows.append([B("✖️ Close",callback_data="close")]); return M(rows)
