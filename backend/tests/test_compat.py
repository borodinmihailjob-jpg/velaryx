def test_compat_invite_one_use(client):
    for user_id in ("100", "200"):
        profile_resp = client.post(
            "/v1/natal/profile",
            headers={"X-TG-USER-ID": user_id},
            json={
                "birth_date": "1994-03-21",
                "birth_time": "11:00:00",
                "birth_place": "Moscow",
                "latitude": 55.7558,
                "longitude": 37.6173,
                "timezone": "Europe/Moscow",
            },
        )
        assert profile_resp.status_code == 200
        calc_resp = client.post(
            "/v1/natal/calculate",
            headers={"X-TG-USER-ID": user_id},
            json={"profile_id": profile_resp.json()["id"]},
        )
        assert calc_resp.status_code == 200

    invite_resp = client.post(
        "/v1/compat/invites",
        headers={"X-TG-USER-ID": "100"},
        json={"ttl_days": 7, "max_uses": 1},
    )
    assert invite_resp.status_code == 200
    token = invite_resp.json()["token"]

    start_resp = client.post(
        "/v1/compat/start",
        headers={"X-TG-USER-ID": "200"},
        json={"invite_token": token},
    )
    assert start_resp.status_code == 200
    assert "session_id" in start_resp.json()
    assert "strengths" in start_resp.json()

    second_resp = client.post(
        "/v1/compat/start",
        headers={"X-TG-USER-ID": "200"},
        json={"invite_token": token},
    )
    assert second_resp.status_code == 409
