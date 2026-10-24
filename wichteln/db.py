import sqlite3

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id               INTEGER PRIMARY KEY,
    title            TEXT NOT NULL,
    budget           TEXT,
    organizer_sees   INTEGER NOT NULL DEFAULT 0,
    admin_token_hash TEXT NOT NULL UNIQUE,
    admin_token      TEXT,
    created_at       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS participants (
    id       INTEGER PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    name     TEXT NOT NULL,
    token    TEXT NOT NULL UNIQUE,
    UNIQUE (event_id, name COLLATE NOCASE)
);
CREATE TABLE IF NOT EXISTS exclusions (
    id          INTEGER PRIMARY KEY,
    event_id    INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    giver_id    INTEGER NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
    receiver_id INTEGER NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
    UNIQUE (giver_id, receiver_id)
);
CREATE TABLE IF NOT EXISTS draws (
    id         INTEGER PRIMARY KEY,
    event_id   INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS draws_event ON draws (event_id);
CREATE TABLE IF NOT EXISTS assignments (
    draw_id           INTEGER NOT NULL REFERENCES draws(id) ON DELETE CASCADE,
    giver_id          INTEGER NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
    receiver_id       INTEGER NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
    first_revealed_at TEXT,
    PRIMARY KEY (draw_id, giver_id),
    UNIQUE (draw_id, receiver_id)
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


def _columns(db, table):
    return {row[1] for row in db.execute(f"PRAGMA table_info({table})")}


def _migrate(db):
    """Bringt Datenbanken älterer Versionen auf den aktuellen Stand."""
    if "organizer_sees" not in _columns(db, "events"):
        db.execute("ALTER TABLE events ADD COLUMN organizer_sees INTEGER NOT NULL DEFAULT 0")

    if "admin_token" not in _columns(db, "events"):
        db.execute("ALTER TABLE events ADD COLUMN admin_token TEXT")

    # Früher lag die Zuordnung direkt an der Person; jetzt gehört sie zu einer Auslosung.
    # Die alten Spalten bleiben (SQLite kann sie nicht sauber entfernen), werden aber geleert.
    if "receiver_id" in _columns(db, "participants"):
        old_events = db.execute(
            "SELECT DISTINCT p.event_id, COALESCE(e.drawn_at, e.created_at)"
            " FROM participants p JOIN events e ON e.id = p.event_id"
            " WHERE p.receiver_id IS NOT NULL"
        ).fetchall()
        for event_id, created_at in old_events:
            cur = db.execute(
                "INSERT INTO draws (event_id, name, created_at) VALUES (?, 'Auslosung 1', ?)",
                (event_id, created_at),
            )
            db.execute(
                "INSERT INTO assignments (draw_id, giver_id, receiver_id, first_revealed_at)"
                " SELECT ?, id, receiver_id, first_revealed_at FROM participants"
                " WHERE event_id = ? AND receiver_id IS NOT NULL",
                (cur.lastrowid, event_id),
            )
        db.execute(
            "UPDATE participants SET receiver_id = NULL, first_revealed_at = NULL"
            " WHERE receiver_id IS NOT NULL"
        )
    db.commit()


def init_db(path):
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    _migrate(db)
    db.close()
