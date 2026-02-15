def test_wishlist_endpoints_are_disabled(client):
    create_resp = client.post(
        "/v1/wishlists",
        headers={"X-TG-USER-ID": "300"},
        json={"title": "Birthday", "slug": "birthday-2026", "is_public": True},
    )
    assert create_resp.status_code == 404
