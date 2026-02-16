def test_geo_city_search_uses_extended_russian_list(client):
    response = client.get("/v1/geo/cities", params={"q": "наро"})
    assert response.status_code == 200
    payload = response.json()
    assert any(item["name"] == "Наро-Фоминск" for item in payload)


def test_geo_timezone_detection(client):
    response = client.get("/v1/geo/timezone", params={"latitude": 55.754047, "longitude": 37.620405})
    assert response.status_code == 200
    assert response.json()["timezone"] == "Europe/Moscow"


def test_geo_timezone_for_far_east_city_is_russian(client):
    response = client.get("/v1/geo/cities", params={"q": "владивосток"})
    assert response.status_code == 200
    payload = response.json()
    assert payload
    assert payload[0]["name"] == "Владивосток"
    assert payload[0]["timezone"] == "Asia/Vladivostok"
