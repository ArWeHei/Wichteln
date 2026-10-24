import pytest

from wichteln import create_app


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db")})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def event(client):
    """Legt ein Wichteln mit vier Personen an; liefert den Verwaltungspfad."""
    resp = client.post(
        "/events",
        data={"title": "Test 2026", "budget": "20 €", "names": "Anna\nBen\nCleo\nDora"},
    )
    assert resp.status_code == 303
    return resp.headers["Location"]


def participant_links(client, admin_path):
    import re

    html = client.get(admin_path).get_data(as_text=True)
    return re.findall(r'<input id="link-\d+" readonly value="[^"]*(/w/[^"]+)"', html)


def reveal_paths(client, link):
    """Reveal-Formulare der persönlichen Seite, die aktuelle Auslosung zuerst."""
    import re

    html = client.get(link).get_data(as_text=True)
    return re.findall(r'action="(/w/[^"]+/reveal/\d+)"', html)


def reveal(client, link, index=0):
    return client.post(reveal_paths(client, link)[index])


def result_name(resp):
    return resp.get_data(as_text=True).split('class="result">')[1].split("<")[0]


def own_name(client, link):
    return client.get(link).get_data(as_text=True).split("Hallo ")[1].split("!")[0]
