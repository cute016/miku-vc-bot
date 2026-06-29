PRAGMA journal_mode=WAL;
CREATE TABLE users (user_id INTEGER PRIMARY KEY, name TEXT, first_seen TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE chats (chat_id INTEGER PRIMARY KEY, title TEXT, language TEXT DEFAULT 'en', first_seen TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE auth_users (chat_id INTEGER, user_id INTEGER, PRIMARY KEY(chat_id,user_id));
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE chat_settings (chat_id INTEGER, key TEXT, value TEXT NOT NULL, PRIMARY KEY(chat_id,key));
CREATE TABLE blacklist (target_id INTEGER PRIMARY KEY, reason TEXT DEFAULT '');
CREATE TABLE stats (day TEXT PRIMARY KEY, songs INTEGER DEFAULT 0);

