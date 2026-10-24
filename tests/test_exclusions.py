import re

from .conftest import participant_links


def ids_by_name(client, admin_path):
    html = client.get(admin_path).get_data(as_text=True)
    select = html.split('name="giver"')[1].split("</select>")[0]
    return {
        name: int(i) for i, name in re.findall(r'<option value="(\d+)">([^<]+)</option>', select)
    }


def assignment(client, admin_path):
    """Deckt alle Links auf und liefert {Name: beschenkte Person}."""
    result = {}
    for link in participant_links(client, admin_path):
        own = client.get(link).get_data(as_text=True).split("Hallo ")[1].split("!")[0]
        html = client.post(link + "/reveal").get_data(as_text=True)
        result[own] = html.split('class="result">')[1].split("<")[0]
    return result


def test_mutual_exclusion_is_respected(client):
    for _ in range(15):
        path = client.post(
            "/events", data={"title": "T", "names": "Anna\nBen\nCleo\nDora"}
        ).headers["Location"]
        ids = ids_by_name(client, path)
        resp = client.post(
            path + "/exclusions",
            data={"giver": ids["Anna"], "receiver": ids["Ben"], "mutual": "1"},
        )
        assert resp.status_code == 303
        client.post(path + "/draw")
        result = assignment(client, path)
        assert result["Anna"] != "Ben"
        assert result["Ben"] != "Anna"


def test_one_way_exclusion_only_blocks_one_direction(client, event):
    ids = ids_by_name(client, event)
    client.post(event + "/exclusions", data={"giver": ids["Anna"], "receiver": ids["Ben"]})
    html = client.get(event).get_data(as_text=True)
    assert "Anna → Ben" in html
    assert "Ben → Anna" not in html


def test_impossible_exclusions_show_error_and_stay_draft(client, event):
    ids = ids_by_name(client, event)
    for other in ("Ben", "Cleo", "Dora"):
        client.post(event + "/exclusions", data={"giver": ids["Anna"], "receiver": ids[other]})
    resp = client.post(event + "/draw")
    assert resp.status_code == 409
    assert "keine Auslosung möglich" in resp.get_data(as_text=True)
    assert "Jetzt auslosen" in client.get(event).get_data(as_text=True)


def test_invalid_exclusion_input(client, event):
    ids = ids_by_name(client, event)
    same = client.post(event + "/exclusions", data={"giver": ids["Anna"], "receiver": ids["Anna"]})
    assert same.status_code == 400
    assert (
        client.post(event + "/exclusions", data={"giver": "x", "receiver": "y"}).status_code == 400
    )
    assert (
        client.post(event + "/exclusions", data={"giver": "999", "receiver": "998"}).status_code
        == 400
    )


def test_exclusion_from_other_event_is_rejected(client, event):
    other = client.post("/events", data={"title": "O", "names": "X\nY\nZ"}).headers["Location"]
    foreign = ids_by_name(client, other)
    resp = client.post(
        event + "/exclusions", data={"giver": foreign["X"], "receiver": foreign["Y"]}
    )
    assert resp.status_code == 400


def test_delete_exclusion(client, event):
    ids = ids_by_name(client, event)
    client.post(event + "/exclusions", data={"giver": ids["Anna"], "receiver": ids["Ben"]})
    html = client.get(event).get_data(as_text=True)
    path = re.search(r'action="([^"]*/exclusions/\d+/delete)"', html).group(1)
    assert client.post(path).status_code == 303
    assert "Anna → Ben" not in client.get(event).get_data(as_text=True)


def test_exclusions_locked_after_draw(client, event):
    ids = ids_by_name(client, event)
    client.post(event + "/draw")
    resp = client.post(event + "/exclusions", data={"giver": ids["Anna"], "receiver": ids["Ben"]})
    assert resp.status_code == 409
