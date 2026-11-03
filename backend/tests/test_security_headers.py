def test_api_responses_carry_security_headers(client):
    headers = client.get("/api/health").headers

    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "no-referrer"
    assert headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in headers["content-security-policy"]
    assert "strict-transport-security" not in headers  # development and tests use plain HTTP


def test_errors_carry_them_too(client):
    assert client.get("/api/auth/me").headers["x-content-type-options"] == "nosniff"


def test_the_interactive_docs_keep_working(client):
    response = client.get("/api/docs")

    assert response.status_code == 200
    assert "content-security-policy" not in response.headers
