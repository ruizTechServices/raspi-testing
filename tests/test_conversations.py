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


def test_rename_and_delete_conversation(client, auth_headers):
    create_response = client.post('/api/conversations', headers=auth_headers, json={'title': 'Original Title'})
    conversation_id = create_response.get_json()['conversation_id']

    rename_response = client.patch(
        f'/api/conversations/{conversation_id}',
        headers=auth_headers,
        json={'title': 'Renamed Chat'},
    )
    assert rename_response.status_code == 200
    assert rename_response.get_json()['title'] == 'Renamed Chat'

    delete_response = client.delete(f'/api/conversations/{conversation_id}', headers=auth_headers)
    assert delete_response.status_code == 200
    assert delete_response.get_json()['ok'] is True

    missing_response = client.get(f'/api/conversations/{conversation_id}/messages', headers=auth_headers)
    assert missing_response.status_code == 400
    assert missing_response.get_json()['error'] == 'Conversation not found.'
