from pyrogram import Client

from config import settings

if not settings.api_id or not settings.api_hash:
    raise SystemExit("Set API_ID and API_HASH in .env first.")

with Client("miku_session_generator",api_id=settings.api_id,api_hash=settings.api_hash,in_memory=True) as app:
    print("\nSESSION_STRING=\n"+app.export_session_string()+"\n")

