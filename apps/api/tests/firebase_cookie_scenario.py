"""Isolated HTTP scenario: cookie alias must be selected before app imports."""

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.database import Base, get_db
from app.main import app
from app.scripts.seed import seed_database


def main() -> None:
    settings = get_settings()
    assert settings.session_cookie_name == "__session"
    assert settings.frontend_origin == "https://groupware.pikan.dev"
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed_database(db)

    def database() -> Generator[Session, None, None]:
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = database
    # Seed is local-only. Exercise production Origin policy after local setup.
    settings.environment = "production"
    try:
        with TestClient(app, base_url=settings.frontend_origin) as client:
            response = client.post(
                "/api/v1/auth/login", headers={"Origin": settings.frontend_origin},
                json={"email": "seojin.yoon@jhworks.test", "password": "demo1234"},
            )
            assert response.status_code == 200
            cookie = next(iter(response.cookies.jar))
            assert cookie.name == "__session" and cookie.secure
            assert cookie.has_nonstandard_attr("HttpOnly")
            assert cookie.get_nonstandard_attr("SameSite") == "lax"
            assert cookie.domain == "groupware.pikan.dev" and cookie.path == "/"
            assert "no-store" in response.headers.get("Cache-Control", "")
            assert client.get("/api/v1/employees/me").status_code == 200
            denied = client.post("/api/v1/auth/logout", headers={"Origin": "https://pikan.dev"})
            assert denied.status_code == 403 and "set-cookie" not in denied.headers
            assert client.get("/api/v1/employees/me").status_code == 200
            token = cookie.value
            assert isinstance(token, str)
            client.cookies.clear()
            client.cookies.set("jhworks_session", token, domain="groupware.pikan.dev", path="/")
            assert client.get("/api/v1/employees/me").status_code == 401
            client.cookies.set("__session", token, domain="groupware.pikan.dev", path="/")
            logout = client.post(
                "/api/v1/auth/logout", headers={"Origin": settings.frontend_origin},
            )
            assert logout.status_code == 200
            assert "no-store" in logout.headers.get("Cache-Control", "")
            assert client.get("/api/v1/employees/me").status_code == 401
        print("firebase-cookie-scenario: passed")
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


if __name__ == "__main__":
    main()
