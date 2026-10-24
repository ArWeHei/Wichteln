import re
import sqlite3

from wichteln import create_app
from wichteln.tokens import hash_token

from .conftest import own_name, participant_links, result_name, reveal, reveal_paths
from .test_exclusions import ids_by_name


def draw(client, path, name=None):
    return client.post(path + "/draw", data={"name": name} if name is not None else {})


def results(client, path, index=0):
    """{Name: beschenkte Person} für die index-te Auslosung (0 = aktuelle)."""
    return {
        own_name(client, link): result_name(reveal(client, link, index))
        for link in participant_links(client, path)
    }


def test_default_names_are_numbered(client, event):
    draw(client, event)
    draw(client, event)
    html = client.get(event).get_data(as_text=True)
    assert "Auslosung 1" in html
    assert "Auslosung 2" in html


def test_custom_name_is_shown_to_admin_and_participants(client, event):
    draw(client, event, "  Weihnachten   2026 ")
    assert "Weihnachten 2026" in client.get(event).get_data(as_text=True)
    link = participant_links(client, event)[0]
    assert "Weihnachten 2026" in client.get(link).get_data(as_text=True)


def test_name_too_long_is_rejected(client, event):
    resp = draw(client, event, "x" * 51)
    assert resp.status_code == 400
    assert "Jetzt auslosen" in client.get(event).get_data(as_text=True)  # nichts ausgelost


def test_reshuffle_keeps_links_and_keeps_history(client, event):
    draw(client, event, "Erste")
    links = participant_links(client, event)
    first = results(client, event)

    assert draw(client, event, "Zweite").status_code == 303
    assert participant_links(client, event) == links

    # die persönliche Seite zeigt beide, neueste zuerst
    for link in links:
        page = client.get(link).get_data(as_text=True)
        assert page.index("Zweite") < page.index("Erste")
        assert "gilt nicht mehr" in page
        assert len(reveal_paths(client, link)) == 2

    # die alte Auslosung liefert weiter genau das alte Ergebnis
    assert results(client, event, index=1) == first


def test_reveal_state_is_tracked_per_draw(client, event):
    draw(client, event)
    link = participant_links(client, event)[0]
    reveal(client, link)
    draw(client, event)

    page = client.get(link).get_data(as_text=True)
    assert page.count("Bereits am") == 1  # nur die alte ist aufgedeckt
    admin = client.get(event).get_data(as_text=True)
    assert "✔ aufgedeckt" not in admin  # aktuelle Auslosung: noch niemand
    assert "1 von 4" in admin  # Verlauf: eine von vier Personen hat die alte aufgedeckt


def test_get_page_never_contains_any_receiver_name(client, event):
    draw(client, event)
    draw(client, event)
    link = participant_links(client, event)[0]
    own = own_name(client, link)
    body = client.get(link).get_data(as_text=True).split("<main>")[1]
    assert not any(n in body for n in {"Anna", "Ben", "Cleo", "Dora"} - {own})


def test_organizer_without_permission_sees_no_pairs_in_history(client, event):
    draw(client, event)
    draw(client, event)
    assert 'class="pairs"' not in client.get(event).get_data(as_text=True)


def test_organizer_with_permission_sees_pairs_of_all_draws(client):
    path = client.post(
        "/events",
        data={"title": "Kinder", "names": "Anna\nBen\nCleo\nDora", "organizer_sees": "1"},
    ).headers["Location"]
    draw(client, path)
    draw(client, path)
    html = client.get(path).get_data(as_text=True)
    assert html.count('class="pairs"') == 2

    shown = re.findall(r'class="person">(\w+) → (\w+)<', html)
    assert len(shown) == 8
    current, old = dict(shown[:4]), dict(shown[4:])
    assert current == results(client, path, index=0)
    assert old == results(client, path, index=1)


def test_reshuffle_respects_exclusions_added_later(client, event):
    ids = ids_by_name(client, event)
    draw(client, event)
    client.post(
        event + "/exclusions",
        data={"giver": ids["Anna"], "receiver": ids["Ben"], "mutual": "1"},
    )
    for _ in range(15):
        draw(client, event)
        current = results(client, event)
        assert current["Anna"] != "Ben"
        assert current["Ben"] != "Anna"


def test_impossible_reshuffle_keeps_existing_draw(client, event):
    ids = ids_by_name(client, event)
    draw(client, event)
    before = results(client, event)
    for other in ("Ben", "Cleo", "Dora"):
        client.post(event + "/exclusions", data={"giver": ids["Anna"], "receiver": ids[other]})
    resp = draw(client, event)
    assert resp.status_code == 409
    assert "keine Auslosung möglich" in resp.get_data(as_text=True)
    assert results(client, event) == before
    assert len(reveal_paths(client, participant_links(client, event)[0])) == 1


def test_rename_draw(client, event):
    draw(client, event, "Alt")
    draw(client, event, "Neu")
    html = client.get(event).get_data(as_text=True)
    old_id = re.search(r"/draws/(\d+)/rename", html.split("<h2>Verlauf</h2>")[1]).group(1)

    resp = client.post(f"{event}/draws/{old_id}/rename", data={"name": "Umbenannt"})
    assert resp.status_code == 303
    html = client.get(event).get_data(as_text=True)
    assert "Umbenannt" in html
    assert "Alt<" not in html
    assert "Umbenannt" in client.get(participant_links(client, event)[0]).get_data(as_text=True)


def test_rename_validation_and_scope(client, event):
    draw(client, event)
    html = client.get(event).get_data(as_text=True)
    draw_id = re.search(r"/draws/(\d+)/rename", html).group(1)
    assert client.post(f"{event}/draws/{draw_id}/rename", data={"name": " "}).status_code == 400
    long_name = {"name": "x" * 51}
    assert client.post(f"{event}/draws/{draw_id}/rename", data=long_name).status_code == 400

    other = client.post("/events", data={"title": "O", "names": "X\nY\nZ"}).headers["Location"]
    # fremde Auslosung ist über einen anderen Wichtel-Admin-Link nicht erreichbar
    assert client.post(f"{other}/draws/{draw_id}/rename", data={"name": "Hack"}).status_code == 404
    assert client.post(f"{event}/draws/9999/rename", data={"name": "x"}).status_code == 404


def test_cannot_reveal_draw_of_another_event_or_person(client, event):
    draw(client, event)
    other = client.post("/events", data={"title": "O", "names": "X\nY\nZ"}).headers["Location"]
    draw(client, other)
    own_link = participant_links(client, event)[0]
    other_link = participant_links(client, other)[0]
    foreign_draw_id = reveal_paths(client, other_link)[0].rsplit("/", 1)[1]
    assert client.post(f"{own_link}/reveal/{foreign_draw_id}").status_code == 404
    assert client.post(f"{own_link}/reveal/99999").status_code == 404


def test_old_database_is_migrated_to_draw_history(tmp_path):
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript(
        """
        CREATE TABLE events (
            id INTEGER PRIMARY KEY, title TEXT NOT NULL, budget TEXT,
            organizer_sees INTEGER NOT NULL DEFAULT 0,
            admin_token_hash TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'draft', created_at TEXT NOT NULL, drawn_at TEXT);
        CREATE TABLE participants (
            id INTEGER PRIMARY KEY, event_id INTEGER NOT NULL, name TEXT NOT NULL,
            token TEXT NOT NULL UNIQUE, receiver_id INTEGER, first_revealed_at TEXT,
            UNIQUE (event_id, name COLLATE NOCASE), UNIQUE (event_id, receiver_id));
        """
    )
    old.execute(
        "INSERT INTO events VALUES (1, 'Alt', NULL, 0, ?, 'drawn', '2025-12-01T10:00:00+00:00',"
        " '2025-12-02T10:00:00+00:00')",
        (hash_token("admintoken"),),
    )
    old.executemany(
        "INSERT INTO participants VALUES (?, 1, ?, ?, ?, ?)",
        [
            (1, "Anna", "tok-anna", 2, "2025-12-03T10:00:00+00:00"),
            (2, "Ben", "tok-ben", 3, None),
            (3, "Cleo", "tok-cleo", 1, None),
        ],
    )
    old.commit()
    old.close()

    client = create_app({"TESTING": True, "DATABASE": str(path)}).test_client()

    admin = client.get("/admin/admintoken").get_data(as_text=True)
    assert "Auslosung 1" in admin
    assert "✔ aufgedeckt" in admin  # Annas bisheriger Status blieb erhalten

    page = client.get("/w/tok-anna").get_data(as_text=True)
    assert "Bereits am" in page
    assert result_name(reveal(client, "/w/tok-anna")) == "Ben"
    assert result_name(reveal(client, "/w/tok-cleo")) == "Anna"

    # nach der Migration lässt sich neu auslosen
    assert client.post("/admin/admintoken/draw", data={"name": "Neu"}).status_code == 303
    assert len(reveal_paths(client, "/w/tok-anna")) == 2
