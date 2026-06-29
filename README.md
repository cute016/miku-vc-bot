# Miku VC Music Bot

Miku is a modular Telegram group voice-chat music bot with an original anime cyber-DJ visual theme. It streams audio/video through an assistant user account, resolves YouTube/search/direct/Telegram media, keeps one queue per chat, renders every card with Pillow, and stores settings locally in SQLite.

Every generated banner and now-playing card is branded with `@mikuvcrobot`. Telegram does not offer arbitrary colored inline buttons, so Miku uses emoji, compact labels, and balanced rows instead.

## What works

- Audio and video VC playback, force play, pause, resume, skip, stop, loop, shuffle, volume, player and queue panels
- YouTube search/links through `yt-dlp`, direct HTTP(S) streams, and replied Telegram audio/video files
- Automatic assistant join through PyTgCalls, automatic queue advance, auto-leave, temporary-file cleanup, and fresh YouTube stream URL resolution
- Per-group admin/auth permissions and English, Tamil, Hindi, and Tanglish preferences
- Owner panel, editable captions/links/watermark/emoji values, live UI previews, maintenance and logging switches
- Broadcast flags, logs, stats, update, restart, database backup/restore, blacklist, and emoji games
- Lightweight SQLite WAL storage; no MongoDB server is required on the phone

## Telegram prerequisites

1. Create the bot with [@BotFather](https://t.me/BotFather), set its username to `@mikuvcrobot`, disable privacy mode if it must read non-command replies, and copy the bot token.
2. Get `API_ID` and `API_HASH` from [my.telegram.org](https://my.telegram.org).
3. Use a separate Telegram user account as the assistant. Add it to groups where Miku will play.
4. Start a group voice/video chat before `/play`. The assistant must be allowed to join and speak.

Never publish `.env`, a session string, or a bot token. A session string grants access to the assistant account.

## Termux installation

Use Termux from F-Droid or GitHub; the very old Play Store build is unsupported.

```bash
pkg update && pkg upgrade -y
pkg install python git ffmpeg nano unzip -y
unzip miku-vc-bot.zip
cd miku-vc-bot
python -m venv venv
source venv/bin/activate
pip install -U pip setuptools wheel
pip install -r requirements.txt
cp .env.example .env
nano .env
```

Set `API_ID` and `API_HASH` first, then generate the assistant session interactively:

```bash
python generate_session.py
```

Paste the printed value after `SESSION_STRING=` in `.env`, complete the other secret values, then run:

```bash
chmod +x run.sh
termux-wake-lock
./run.sh
```

For a detachable terminal:

```bash
pkg install tmux -y
tmux new -s miku
bash run.sh
```

Detach with `CTRL+B`, then `D`. Resume with `tmux attach -t miku`.

Android may kill Termux in the background. Disable battery optimization for Termux, allow background activity, keep `termux-wake-lock` active, and leave the phone on a safe charger with adequate ventilation.

## Configuration

Copy `.env.example` to `.env`. Required values are `API_ID`, `API_HASH`, `BOT_TOKEN`, `OWNER_ID`, and `SESSION_STRING`. `SUDO_USERS` accepts comma-separated numeric IDs. Relative SQLite and image paths resolve from the project directory.

The owner can edit visible settings from `/panel`. `/emojis` stores either a normal emoji or a Telegram custom-emoji document ID. Telegram clients only render a custom ID where the message entity/API surface permits it; Miku safely retains the normal emoji labels as fallback.

## Commands

- General: `/start`, `/help`, `/ping`, `/stats`, `/settings`, `/language`, `/preview`
- Playback: `/play`, `/vplay`, `/playforce`, `/vplayforce`, `/pause`, `/resume`, `/skip`, `/stop`, `/end`, `/queue`, `/player`, `/loop`, `/shuffle`, `/seek`, `/speed`, `/volume`
- Linked-channel aliases: `cplay`, `cvplay`, `cpause`, `cresume`, `cskip`, `cstop`, `cend`, `cqueue`, `cplayer`
- Admin/auth: `/auth`, `/unauth`, `/authusers`, `/panel`, `/emojis`, `/maintenance`, `/logger`, `/command`
- Owner: `/broadcast`, `/logs`, `/restart`, `/update`, `/speedtest`, `/backupdb`, `/restoredb`, `/blacklist`, `/whitelist`
- Sudo manager: `/addsudo`, `/delsudo`, `/sudousers`
- Games: `/dice`, `/dart`, `/basket`, `/ball`, `/football`, `/jackpot`

Broadcast flags: `-user`, `-assistant`, `-pin`, `-pinloud`, and `-nobot`. Example: `/broadcast -user -pinloud Maintenance is complete!`

`/seek` and `/speed` rebuild the active PyTgCalls `MediaStream` with safe FFmpeg start/tempo parameters. Supported speeds are 0.5×, 0.75×, 1×, 1.25×, 1.5×, and 2×.

## Updating and recovery

`/update` performs a non-shell `git pull --stat`. `/restart` gracefully closes clients and replaces the Python process. `run.sh` restarts after crashes. `/backupdb` sends the owner the SQLite file; reply to a backup document with `/restoredb` to restore it.

The live schema is created automatically from `database/db.py`; a readable copy is in `database/schema.sql`. WAL mode protects normal concurrent reads/writes, but keep periodic `/backupdb` copies outside the phone.

## Quick checks

```bash
python -m compileall -q .
python main.py --check
ffmpeg -version
```

If PyTgCalls has no wheel for a very old 32-bit Android device, use a 64-bit Termux install/device. Current NTgCalls provides Android ARM builds, but architecture support is ultimately determined by the installed package release.
