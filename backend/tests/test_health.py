from sqlalchemy.exc import OperationalError

from app import __version__
from app.db.session import get_db


def test_health_ok_when_database_reachable(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__, "database": "ok"}


def test_health_degraded_when_database_down(app, client):
    class BrokenSession:
        def execute(self, *args, **kwargs):
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    app.dependency_overrides[get_db] = lambda: BrokenSession()

    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["database"] == "unavailable"


def test_unknown_route_returns_404(client):
    assert client.get("/api/does-not-exist").status_code == 404
