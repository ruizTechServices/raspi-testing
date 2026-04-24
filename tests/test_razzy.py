from __future__ import annotations


def test_razzy_profile_returns_identity(client):
    response = client.get('/api/razzy/profile')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['profile']['nickname'] == 'RAZZY'


def test_razzy_session_and_memory_flow(client, auth_headers):
    session_response = client.post('/api/razzy/session', headers=auth_headers, json={'title': 'Razzy Test'})
    assert session_response.status_code == 200
    conversation_id = session_response.get_json()['conversation_id']

    remember_response = client.post(
        '/api/razzy/remember',
        headers=auth_headers,
        json={
            'conversation_id': conversation_id,
            'content': 'Gio likes direct, skeptical help.',
            'cell_type': 'preference',
            'salience': 0.95,
        },
    )
    assert remember_response.status_code == 200

    memory_response = client.get(f'/api/razzy/memory/{conversation_id}', headers=auth_headers)
    assert memory_response.status_code == 200
    memory = memory_response.get_json()['memory']
    assert any(item['content'] == 'Gio likes direct, skeptical help.' for item in memory)


def test_razzy_chat_endpoint_returns_reply(client, auth_headers):
    session_response = client.post('/api/razzy/session', headers=auth_headers, json={'title': 'Razzy Chat'})
    conversation_id = session_response.get_json()['conversation_id']

    response = client.post(
        '/api/razzy/chat',
        headers=auth_headers,
        json={
            'conversation_id': conversation_id,
            'message': 'hello razzy',
            'provider': 'ollama',
            'model': 'lfm2.5-thinking:latest',
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['message']['content'] == 'fake response'
