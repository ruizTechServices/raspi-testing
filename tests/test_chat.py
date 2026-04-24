from __future__ import annotations


def test_chat_creates_assistant_reply(client, auth_headers):
    create_response = client.post('/api/conversations', headers=auth_headers, json={'title': 'Chat Test'})
    conversation_id = create_response.get_json()['conversation_id']

    response = client.post(
        '/api/chat',
        headers=auth_headers,
        json={
            'conversation_id': conversation_id,
            'message': 'hello there',
            'provider': 'ollama',
            'model': 'lfm2.5-thinking:latest',
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['conversation_id'] == conversation_id
    assert payload['message']['content'] == 'fake response'
    assert payload['message']['provider'] == 'ollama'
    assert payload['message']['model'] == 'lfm2.5-thinking:latest'


def test_chat_rejects_empty_message(client, auth_headers):
    response = client.post(
        '/api/chat',
        headers=auth_headers,
        json={'message': '   ', 'provider': 'openai'},
    )

    assert response.status_code == 400
    assert response.get_json()['error'] == 'Message cannot be empty.'
