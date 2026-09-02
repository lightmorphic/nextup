import os
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_TMP = tempfile.mkdtemp(prefix="nextup-tests-")
os.environ["NEXTUP_DATA_DIR"] = _TMP


@pytest.fixture()
def app():
    from app import create_app

    application = create_app(start_sync=False)
    application.config.update(TESTING=True)
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def signed_in(client):
    client.post("/login", data={"username": "admin", "password": "nextup"})
    return client
