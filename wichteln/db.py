import sqlite3

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id               INTEGER PRIMARY KEY,
    title            TEXT NOT NULL,
    budget           TEXT,
    admin_token_hash TEXT NOT NULL UNIQUE,
    status           TEXT NOT NULL DEFAULT 'draft',
    created_at       TEXT NOT NULL,
    drawn_at         TEXT
);
CREATE TABLE IF NOT EXISTS participants (
    id                INTEGER PRIMARY KEY,
    event_id          INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    name              TEXT NOT NULL,
    token             TEXT NOT NULL UNIQUE,
    receiver_id       INTEGER REFERENCES participants(id) ON DELETE SET NULL,
    first_revealed_at TEXT,
    UNIQUE (event_id, name COLLATE NOCASE),
    UNIQUE (event_id, receiver_id)
);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(path):
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    db.close()
