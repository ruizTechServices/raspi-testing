from __future__ import annotations


def test_create_and_list_conversations(client, auth_headers):
    create_response = client.post('/api/conversations', headers=auth_headers, json={'title': 'Test Chat'})
    assert create_response.status_code == 200

    list_response = client.get('/api/conversations', headers=auth_headers)
    assert list_response.status_code == 200

    conversations = list_response.get_json()['conversations']
    assert any(item['title'] == 'Test Chat' for item in conversations)


def test_get_messages_returns_empty_list_for_new_conversation(client, auth_headers):
    create_response = client.post('/api/conversations', headers=auth_headers, json={'title': 'Empty Chat'})
    conversation_id = create_response.get_json()['conversation_id']

    response = client.get(f'/api/conversations/{conversation_id}/messages', headers=auth_headers)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['conversation_id'] == conversation_id
    assert payload['messages'] == []
