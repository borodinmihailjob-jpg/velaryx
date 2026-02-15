def test_natal_forecast_tarot_flow(client):
    profile_resp = client.post(
        "/v1/natal/profile",
        headers={"X-TG-USER-ID": "401"},
        json={
            "birth_date": "1996-06-11",
            "birth_time": "08:30:00",
            "birth_place": "Moscow",
            "latitude": 55.7558,
            "longitude": 37.6173,
            "timezone": "Europe/Moscow",
        },
    )
    assert profile_resp.status_code == 200
    profile_id = profile_resp.json()["id"]

    chart_resp = client.post(
        "/v1/natal/calculate",
        headers={"X-TG-USER-ID": "401"},
        json={"profile_id": profile_id},
    )
    assert chart_resp.status_code == 200
    assert chart_resp.json()["sun_sign"]

    forecast_resp = client.get(
        "/v1/forecast/daily",
        headers={"X-TG-USER-ID": "401"},
    )
    assert forecast_resp.status_code == 200
    assert 0 < forecast_resp.json()["energy_score"] <= 100

    tarot_resp = client.post(
        "/v1/tarot/draw",
        headers={"X-TG-USER-ID": "401"},
        json={"spread_type": "three_card", "question": "What to focus on?"},
    )
    assert tarot_resp.status_code == 200
    assert len(tarot_resp.json()["cards"]) == 3
