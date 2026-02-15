def test_wishlist_reservation_unique_constraint(client):
    create_resp = client.post(
        "/v1/wishlists",
        headers={"X-TG-USER-ID": "300"},
        json={"title": "Birthday", "slug": "birthday-2026", "is_public": True},
    )
    assert create_resp.status_code == 200
    wishlist_id = create_resp.json()["id"]
    public_token = create_resp.json()["public_token"]

    item_resp = client.post(
        f"/v1/wishlists/{wishlist_id}/items",
        headers={"X-TG-USER-ID": "300"},
        json={"title": "Book", "budget_cents": 2500},
    )
    assert item_resp.status_code == 200
    item_id = item_resp.json()["id"]

    reserve_1 = client.post(
        f"/v1/public/wishlists/{public_token}/items/{item_id}/reserve",
        json={"reserver_name": "Friend A"},
    )
    assert reserve_1.status_code == 200

    reserve_2 = client.post(
        f"/v1/public/wishlists/{public_token}/items/{item_id}/reserve",
        json={"reserver_name": "Friend B"},
    )
    assert reserve_2.status_code == 409
