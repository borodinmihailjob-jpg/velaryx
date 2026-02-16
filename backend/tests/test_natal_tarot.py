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

    full_natal_resp = client.get(
        "/v1/natal/full",
        headers={"X-TG-USER-ID": "401"},
    )
    assert full_natal_resp.status_code == 200
    assert isinstance(full_natal_resp.json()["interpretation_sections"], list)

    forecast_resp = client.get(
        "/v1/forecast/daily",
        headers={"X-TG-USER-ID": "401"},
    )
    assert forecast_resp.status_code == 200
    assert 0 < forecast_resp.json()["energy_score"] <= 100

    stories_resp = client.get(
        "/v1/forecast/stories",
        headers={"X-TG-USER-ID": "401"},
    )
    assert stories_resp.status_code == 200
    assert len(stories_resp.json()["slides"]) >= 2

    tarot_resp = client.post(
        "/v1/tarot/draw",
        headers={"X-TG-USER-ID": "401"},
        json={"spread_type": "three_card", "question": "What to focus on?"},
    )
    assert tarot_resp.status_code == 200
    tarot_payload = tarot_resp.json()
    assert "ai_interpretation" in tarot_payload
    if tarot_payload.get("llm_provider") == "local:fallback":
        assert tarot_payload["cards"] == []
        assert tarot_payload["ai_interpretation"] == "Карты скрыли ответ.\nВозможно, время ещё не пришло."
    else:
        assert len(tarot_payload["cards"]) == 3

    combo_resp = client.post(
        "/v1/insights/astro-tarot",
        headers={"X-TG-USER-ID": "401"},
        json={"spread_type": "three_card", "question": "Main decision this week?"},
    )
    assert combo_resp.status_code == 404

    report_resp = client.get(
        "/v1/reports/natal.pdf",
        headers={"X-TG-USER-ID": "401"},
    )
    assert report_resp.status_code == 404
