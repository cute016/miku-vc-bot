import asyncio

# Pyrogram 2 expects a current loop during import. Python 3.14 no longer
# creates one implicitly for the main thread.
asyncio.set_event_loop(asyncio.new_event_loop())

from pyrogram import Client

from config import settings

def main() -> None:
    if not settings.api_id or not settings.api_hash:
        raise SystemExit("Set API_ID and API_HASH in .env first.")

    with Client("miku_session_generator",api_id=settings.api_id,api_hash=settings.api_hash,in_memory=True) as app:
        print("\nSESSION_STRING=\n"+app.export_session_string()+"\n")


if __name__ == "__main__":
    main()
