import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

def test_get_characters():
    resp = client.get("/characters")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(c["id"] == "shopkeeper" for c in data)

def test_chat_endpoint_invalid_char():
    resp = client.post("/chat/invalid_char", json={
        "user_id": "user1",
        "message": "Hello",
        "language": "english"
    })
    assert resp.status_code == 404

# Note: For full test of chat response you would need to mock the AI call.
