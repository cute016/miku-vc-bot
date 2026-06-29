from . import admin, games, general, playback, sudo


def register_all(app):
    general.register(app); playback.register(app); admin.register(app); games.register(app); sudo.register(app)
