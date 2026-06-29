from __future__ import annotations

import asyncio
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from html import escape
from pathlib import Path

import psutil
from pyrogram import filters

from config import BASE_DIR, settings
from runtime import runtime
from utils.permissions import require_sudo
from utils.text import duration


def register(app):
    @app.on_message(filters.command(["maintenance","logger"]))
    async def toggle(_,m):
        if not await require_sudo(m): return
        if len(m.command)<2 or m.command[1].lower() not in {"enable","disable"}: await m.reply_text(f"Use /{m.command[0]} enable or disable"); return
        value=m.command[1].lower()=="enable"; await runtime.db.set(m.command[0].lower(),value); await m.reply_text(f"✅ {m.command[0].title()} {'enabled' if value else 'disabled'}.")

    @app.on_message(filters.command("stats"))
    async def stats(_,m):
        users,chats=await asyncio.gather(runtime.db.count("users"),runtime.db.count("chats")); daily,total=await runtime.db.song_stats()
        disk=shutil.disk_usage(BASE_DIR); downloads=sum(p.stat().st_size for p in (BASE_DIR/"downloads").glob("**/*") if p.is_file())
        up=int((datetime.now(timezone.utc)-runtime.started_at).total_seconds())
        await m.reply_text(f"📊 <b>ᴍɪᴋᴜ sᴛᴀᴛs</b>\n\n👤 Users: <b>{users}</b>\n💬 Chats: <b>{chats}</b>\n🎙 Active streams: <b>{runtime.queues.active_count()}</b>\n🎵 Songs today / total: <b>{daily} / {total}</b>\n⏱ Uptime: <b>{duration(up)}</b>\n🧠 RAM: <b>{psutil.virtual_memory().percent}%</b>\n⚙️ CPU: <b>{psutil.cpu_percent()}%</b>\n💾 Storage: <b>{disk.used/disk.total*100:.1f}%</b>\n📥 Downloads: <b>{downloads/1048576:.1f} MB</b>")

    @app.on_message(filters.command("logs"))
    async def logs(_,m):
        if not await require_sudo(m): return
        path=BASE_DIR/"miku.log"
        if not path.exists(): await m.reply_text("📜 No log file yet."); return
        if path.stat().st_size<1_500_000: await m.reply_document(str(path),caption="📜 Miku logs")
        else: await m.reply_text("📜 <b>Latest log lines</b>\n<pre>"+escape("\n".join(path.read_text("utf-8",errors="replace").splitlines()[-60:]))+"</pre>")

    @app.on_message(filters.command("backupdb"))
    async def backup(_,m):
        if await require_sudo(m): await m.reply_document(str(settings.sqlite_path),caption="💾 Miku database backup")

    @app.on_message(filters.command("restoredb"))
    async def restore(_,m):
        if not await require_sudo(m): return
        if not m.reply_to_message or not m.reply_to_message.document: await m.reply_text("Reply to a SQLite backup with /restoredb"); return
        temp=BASE_DIR/"database"/"restore.tmp"; await m.reply_to_message.download(str(temp)); await runtime.db.close(); shutil.copy2(temp,settings.sqlite_path); temp.unlink(missing_ok=True); await runtime.db.connect(); await m.reply_text("✅ Database restored.")

    @app.on_message(filters.command(["blacklist","whitelist"]))
    async def blacklist(_,m):
        if not await require_sudo(m): return
        if len(m.command)<2 or not m.command[1].lstrip("-").isdigit(): await m.reply_text(f"Use /{m.command[0]} user_or_chat_id"); return
        target=int(m.command[1]); conn=runtime.db.conn
        if m.command[0].lower()=="blacklist": await conn.execute("INSERT OR REPLACE INTO blacklist VALUES (?,?)",(target," ".join(m.command[2:])[:300])); word="blacklisted"
        else: await conn.execute("DELETE FROM blacklist WHERE target_id=?",(target,)); word="whitelisted"
        await conn.commit(); await m.reply_text(f"✅ <code>{target}</code> {word}.")

    @app.on_message(filters.command("broadcast"))
    async def broadcast(_,m):
        if not await require_sudo(m): return
        tokens=m.command[1:]; flags={x for x in tokens if x.startswith("-")}; text=" ".join(x for x in tokens if not x.startswith("-"))
        source=m.reply_to_message
        if not text and not source: await m.reply_text("Reply to a message or add text after /broadcast."); return
        targets=[]
        if "-user" in flags: targets+=await runtime.db.all_ids("users")
        if "-nobot" not in flags or "-user" not in flags: targets+=await runtime.db.all_ids("chats")
        targets=list(dict.fromkeys(targets)); ok=failed=users=groups=0; started=time.monotonic()
        for target in targets:
            try:
                sent=await (source.copy(target) if source else runtime.bot.send_message(target,text))
                if "-pin" in flags or "-pinloud" in flags: await sent.pin(disable_notification="-pinloud" not in flags)
                ok+=1; users+=target>0; groups+=target<0
            except Exception: failed+=1
            await asyncio.sleep(.08)
        if "-assistant" in flags and text:
            for target in await runtime.db.all_ids("chats"):
                try: await runtime.assistant.send_message(target,text)
                except Exception: pass
        await m.reply_text(f"📡 <b>Broadcast complete</b>\n\nTotal: {len(targets)}\nSuccess: {ok}\nFailed: {failed}\nUsers: {users}\nGroups: {groups}\nTime: {time.monotonic()-started:.1f}s")

    @app.on_message(filters.command("update"))
    async def update(_,m):
        if not await require_sudo(m): return
        try:
            proc=await asyncio.create_subprocess_exec("git","pull","--stat",cwd=BASE_DIR,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT)
            out,_=await asyncio.wait_for(proc.communicate(),90); await m.reply_text("🔄 <b>Update result</b>\n<pre>"+escape(out.decode(errors="replace")[-3500:])+"</pre>")
        except Exception as exc: await m.reply_text(f"❌ Update failed: <code>{escape(str(exc))}</code>")

    @app.on_message(filters.command("speedtest"))
    async def speedtest(_,m):
        if not await require_sudo(m): return
        x=await m.reply_text("📡 Testing connection...")
        try:
            proc=await asyncio.create_subprocess_exec("speedtest-cli","--simple",stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT)
            out,_=await asyncio.wait_for(proc.communicate(),60); await x.edit_text("📡 <b>Connection</b>\n<pre>"+escape(out.decode()[:1000])+"</pre>")
        except Exception as exc: await x.edit_text(f"❌ Speed test unavailable: <code>{escape(str(exc))}</code>")

    @app.on_message(filters.command("restart"))
    async def restart(_,m):
        if not await require_sudo(m): return
        await m.reply_text("🔄 Restarting Miku..."); await runtime.db.close(); await runtime.assistant.stop(); await runtime.bot.stop(); os.execv(sys.executable,[sys.executable,*sys.argv])

