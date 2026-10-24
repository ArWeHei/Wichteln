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
