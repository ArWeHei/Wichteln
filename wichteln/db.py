import sqlite3

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id               INTEGER PRIMARY KEY,
    title            TEXT NOT NULL,
    budget           TEXT,
    organizer_sees   INTEGER NOT NULL DEFAULT 0,
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
CREATE TABLE IF NOT EXISTS exclusions (
    id          INTEGER PRIMARY KEY,
    event_id    INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    giver_id    INTEGER NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
    receiver_id INTEGER NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
    UNIQUE (giver_id, receiver_id)
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
    columns = {row[1] for row in db.execute("PRAGMA table_info(events)")}
    if "organizer_sees" not in columns:
        db.execute("ALTER TABLE events ADD COLUMN organizer_sees INTEGER NOT NULL DEFAULT 0")
        db.commit()
    db.close()
