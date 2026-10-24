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
