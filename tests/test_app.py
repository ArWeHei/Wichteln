import re

import pytest

from .conftest import participant_links


def test_index(client):
    assert client.get("/").status_code == 200


@pytest.mark.parametrize(
    "data",
    [
        {"title": "", "names": "A\nB\nC"},
        {"title": "T", "names": "A\nB"},
        {"title": "T", "names": "Anna\nanna\nBen"},
        {"title": "T", "names": "A\nB\n" + "x" * 51},
        {"title": "T" * 101, "names": "A\nB\nC"},
    ],
)
def test_create_validation(client, data):
    resp = client.post("/events", data=data)
    assert resp.status_code == 400


def test_names_are_normalized(client):
    resp = client.post("/events", data={"title": "T", "names": "  Anna   Maria \n\n Ben\nCleo"})
    assert resp.status_code == 303
    html = client.get(resp.headers["Location"]).get_data(as_text=True)
    assert "Anna Maria" in html


def test_unknown_tokens_404(client):
    assert client.get("/admin/nope").status_code == 404
    assert client.post("/admin/nope/draw").status_code == 404
    assert client.get("/w/nope").status_code == 404
    assert client.post("/w/nope/reveal").status_code == 404


def test_draw_flow(client, event):
    assert client.get(event).status_code == 200
    assert client.post(event + "/draw").status_code == 303
    assert client.post(event + "/draw").status_code == 409  # nur einmal

    links = participant_links(client, event)
    assert len(links) == 4

    seen = set()
    for link in links:
        page = client.get(link).get_data(as_text=True)
        assert "Du beschenkst" not in page
        resp = client.post(link + "/reveal")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "Du beschenkst" in html
        seen.add(html.split('class="result">')[1].split("<")[0])
    assert seen == {"Anna", "Ben", "Cleo", "Dora"}


def test_get_page_never_reveals_receiver_names(client, event):
    client.post(event + "/draw")
    link = participant_links(client, event)[0]
    page = client.get(link).get_data(as_text=True)
    own = page.split("Hallo ")[1].split("!")[0]
    others = {"Anna", "Ben", "Cleo", "Dora"} - {own}
    body = page.split("<main>")[1]
    assert not any(name in body for name in others)


def test_admin_page_shows_no_assignment(client, event):
    client.post(event + "/draw")
    html = client.get(event).get_data(as_text=True)
    assert "beschenkt" not in html.replace("wer wen beschenkt", "")
    assert "receiver" not in html


def test_reveal_before_draw_is_rejected(client, event):
    html = client.get(event).get_data(as_text=True)
    assert "/w/" not in html  # Links erscheinen erst nach der Auslosung


def test_first_revealed_is_recorded_and_shown(client, event):
    client.post(event + "/draw")
    link = participant_links(client, event)[0]
    assert "bereits am" not in client.get(link).get_data(as_text=True)
    assert "aufgedeckt" in client.get(event).get_data(as_text=True)
    client.post(link + "/reveal")
    assert "bereits am" in client.get(link).get_data(as_text=True)
    assert "✔ aufgedeckt" in client.get(event).get_data(as_text=True)


def test_delete_event(client, event):
    client.post(event + "/draw")
    link = participant_links(client, event)[0]
    assert client.post(event + "/delete").status_code == 303
    assert client.get(event).status_code == 404
    assert client.get(link).status_code == 404


def test_security_headers(client, event):
    resp = client.get(event)
    assert resp.headers["Referrer-Policy"] == "no-referrer"
    assert "noindex" in resp.headers["X-Robots-Tag"]
    assert resp.headers["Cache-Control"] == "no-store"


def _names(client, admin_path):
    return {
        link: client.get(link).get_data(as_text=True).split("Hallo ")[1].split("!")[0]
        for link in participant_links(client, admin_path)
    }


def test_organizer_does_not_see_assignment_by_default(client, event):
    client.post(event + "/draw")
    html = client.get(event).get_data(as_text=True)
    assert "Zuordnung</h2>" not in html
    assert "→" not in html


def test_organizer_sees_assignment_when_chosen(client):
    path = client.post(
        "/events",
        data={"title": "Kinder", "names": "Anna\nBen\nCleo\nDora", "organizer_sees": "1"},
    ).headers["Location"]
    assert "Zuordnung</h2>" not in client.get(path).get_data(as_text=True)  # vor dem Auslosen
    client.post(path + "/draw")
    html = client.get(path).get_data(as_text=True)
    assert "Zuordnung</h2>" in html

    shown = dict(re.findall(r'class="person">(\w+) → (\w+)<', html))
    assert len(shown) == 4
    for link in participant_links(client, path):
        page = client.get(link).get_data(as_text=True)
        own = page.split("Hallo ")[1].split("!")[0]
        assert "Organisation kann die Zuordnung einsehen" in page
        revealed = client.post(link + "/reveal").get_data(as_text=True)
        assert shown[own] == revealed.split('class="result">')[1].split("<")[0]


def test_default_event_page_has_no_organizer_notice(client, event):
    client.post(event + "/draw")
    link = participant_links(client, event)[0]
    assert "Organisation kann" not in client.get(link).get_data(as_text=True)


def test_existing_db_gets_migrated(tmp_path):
    import sqlite3

    from wichteln import create_app

    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.execute(
        "CREATE TABLE events (id INTEGER PRIMARY KEY, title TEXT NOT NULL, budget TEXT,"
        " admin_token_hash TEXT NOT NULL UNIQUE, status TEXT NOT NULL DEFAULT 'draft',"
        " created_at TEXT NOT NULL, drawn_at TEXT)"
    )
    old.commit()
    old.close()
    app = create_app({"TESTING": True, "DATABASE": str(path)})
    resp = app.test_client().post("/events", data={"title": "T", "names": "A\nB\nC"})
    assert resp.status_code == 303
