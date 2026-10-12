import pytest

from community_manager import create_app
from community_manager.db import get_db


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("COMMUNITY_DATA_DIR", str(tmp_path))
    app = create_app({"TESTING": True})
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    with app.app_context():
        yield get_db()
