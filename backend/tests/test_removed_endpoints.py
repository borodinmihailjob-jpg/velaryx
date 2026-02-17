"""Verify that removed endpoints return 404 and are not accidentally re-registered."""


def test_compat_endpoints_removed(client):
    assert client.post("/v1/compat/invites", headers={"X-TG-USER-ID": "1"}, json={}).status_code == 404
    assert client.post("/v1/compat/start", headers={"X-TG-USER-ID": "1"}, json={}).status_code == 404


def test_wishlist_endpoints_removed(client):
    assert client.post("/v1/wishlists", headers={"X-TG-USER-ID": "1"}, json={}).status_code == 404


def test_insights_endpoint_removed(client):
    assert client.post("/v1/insights/astro-tarot", headers={"X-TG-USER-ID": "1"}, json={}).status_code == 404


def test_reports_endpoints_removed(client):
    assert client.get("/v1/reports/natal.pdf", headers={"X-TG-USER-ID": "1"}).status_code == 404
    assert client.get("/v1/reports/natal-link", headers={"X-TG-USER-ID": "1"}).status_code == 404
