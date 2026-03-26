"""Test health endpoint."""


def test_health_check(client):
    """Test GET /health returns 200 with status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_check_no_auth_required(client):
    """Test that /health does not require authentication."""
    # Should work without X-API-Key header
    response = client.get("/health")
    assert response.status_code == 200
