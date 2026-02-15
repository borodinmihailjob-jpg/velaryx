def test_compat_invite_one_use(client):
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

    second_resp = client.post(
        "/v1/compat/start",
        headers={"X-TG-USER-ID": "200"},
        json={"invite_token": token},
    )
    assert second_resp.status_code == 409
