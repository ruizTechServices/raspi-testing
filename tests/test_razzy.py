from __future__ import annotations


def test_razzy_profile_returns_identity(client):
    response = client.get('/api/razzy/profile')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['profile']['nickname'] == 'RAZZY'


def test_razzy_removed_endpoints_return_gone(client, auth_headers):
    session_response = client.post('/api/razzy/session', headers=auth_headers, json={'title': 'Razzy Test'})
    assert session_response.status_code == 410
    assert 'removed' in session_response.get_json()['error'].lower()

    remember_response = client.post(
        '/api/razzy/remember',
        headers=auth_headers,
        json={
            'conversation_id': 'dead-end',
            'content': 'Gio likes direct, skeptical help.',
            'cell_type': 'preference',
            'salience': 0.95,
        },
    )
    assert remember_response.status_code == 410
    assert 'removed' in remember_response.get_json()['error'].lower()

    memory_response = client.get('/api/razzy/memory/dead-end', headers=auth_headers)
    assert memory_response.status_code == 410
    assert 'removed' in memory_response.get_json()['error'].lower()

    chat_response = client.post(
        '/api/razzy/chat',
        headers=auth_headers,
        json={
            'conversation_id': 'dead-end',
            'message': 'hello razzy',
            'provider': 'ollama',
            'model': 'lfm2.5-thinking:latest',
        },
    )
    assert chat_response.status_code == 410
    assert 'removed' in chat_response.get_json()['error'].lower()
