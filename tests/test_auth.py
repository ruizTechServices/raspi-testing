from __future__ import annotations


def test_protected_endpoint_rejects_missing_api_key(client):
    response = client.post('/api/conversations', json={'title': 'Nope'})

    assert response.status_code == 401
    assert response.get_json()['error'] == 'Unauthorized'


def test_protected_endpoint_accepts_valid_api_key(client, auth_headers):
    response = client.post('/api/conversations', headers=auth_headers, json={'title': 'Allowed'})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['title'] == 'Allowed'
    assert payload['conversation_id']
