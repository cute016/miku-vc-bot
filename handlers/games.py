from pyrogram import filters

GAMES={"dice":"🎲","dart":"🎯","basket":"🏀","ball":"🎳","football":"⚽","jackpot":"🎰"}


def register(app):
    @app.on_message(filters.command(list(GAMES)))
    async def game(_,m): await app.send_dice(m.chat.id,emoji=GAMES[m.command[0].lower()],reply_to_message_id=m.id)

