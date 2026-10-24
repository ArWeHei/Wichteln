import re
import sqlite3

from wichteln.tokens import hash_token


def run(app, *args):
    return app.test_cli_runner().invoke(args=["admin-links", *args])


def test_no_events(app):
    result = run(app)
    assert result.exit_code == 0
    assert "Noch keine Wichteln" in result.output


def test_lists_working_admin_links(app, client, event):
    result = run(app, "--base-url", "https://example.org/")
    assert result.exit_code == 0
    assert "Test 2026" in result.output
    assert "4 Personen" in result.output
    link = re.search(r"https://example\.org(/admin/\S+)", result.output).group(1)
    assert link == event
    assert client.get(link).status_code == 200


def test_without_base_url_prints_path_and_hint(app, event):
    result = run(app)
    assert f"    {event}\n" in result.output
    assert "--base-url" in result.output


def test_base_url_from_environment(app, event):
    result = app.test_cli_runner().invoke(
        args=["admin-links"], env={"WICHTELN_BASE_URL": "https://env.example"}
    )
    assert f"https://env.example{event}" in result.output


def test_lists_every_event(app, client, event):
    client.post("/events", data={"title": "Zweites", "names": "X\nY\nZ"})
    result = run(app)
    assert "Test 2026" in result.output
    assert "Zweites" in result.output
    assert result.output.count("/admin/") == 2


def _insert_event_without_stored_token(app, token="legacy-token"):
    db = sqlite3.connect(app.config["DATABASE"])
    db.execute(
        "INSERT INTO events (id, title, admin_token_hash, created_at)"
        " VALUES (50, 'Alt', ?, '2025-12-01T10:00:00+00:00')",
        (hash_token(token),),
    )
    db.commit()
    db.close()


def test_event_without_stored_token_shows_reset_hint(app):
    _insert_event_without_stored_token(app)
    result = run(app)
    assert "Alt" in result.output
    assert "--reset 50" in result.output
    assert "/admin/" not in result.output


def test_reset_issues_new_working_link_and_invalidates_old(app, client):
    _insert_event_without_stored_token(app)
    assert client.get("/admin/legacy-token").status_code == 200

    result = run(app, "--reset", "50")
    assert result.exit_code == 0
    new_link = re.search(r"(/admin/\S+)", result.output).group(1)
    assert new_link != "/admin/legacy-token"
    assert client.get(new_link).status_code == 200
    assert client.get("/admin/legacy-token").status_code == 404

    # danach wird er auch beim normalen Auflisten angezeigt
    assert new_link in run(app).output


def test_reset_only_shows_that_event(app, client, event):
    _insert_event_without_stored_token(app)
    result = run(app, "--reset", "50")
    assert "Test 2026" not in result.output


def test_reset_unknown_id_fails(app):
    result = run(app, "--reset", "999")
    assert result.exit_code != 0
    assert "Kein Wichteln mit der ID 999" in result.output


def test_migrated_old_database_gets_column(tmp_path):
    from wichteln import create_app

    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript(
        """
        CREATE TABLE events (
            id INTEGER PRIMARY KEY, title TEXT NOT NULL, budget TEXT,
            organizer_sees INTEGER NOT NULL DEFAULT 0, admin_token_hash TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL);
        INSERT INTO events (id, title, admin_token_hash, created_at)
            VALUES (1, 'Alt', 'h', '2025-12-01T10:00:00+00:00');
        """
    )
    old.commit()
    old.close()
    app = create_app({"TESTING": True, "DATABASE": str(path)})
    assert "--reset 1" in run(app).output
