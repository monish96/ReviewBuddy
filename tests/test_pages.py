from fastapi.testclient import TestClient

from prreviewbot.web.app import create_app


def test_pages_render(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path))
    assert client.get("/").status_code == 200
    assert client.get("/tool").status_code == 200
    assert client.get("/settings").status_code == 200


