from __future__ import annotations


def test_razzy_chat_endpoints_return_gone(client, auth_headers):
    session_response = client.post('/api/razzy/session', headers=auth_headers, json={})
    assert session_response.status_code == 410
    assert 'removed' in session_response.get_json()['error'].lower()

    chat_response = client.post('/api/razzy/chat', headers=auth_headers, json={'message': 'hello'})
    assert chat_response.status_code == 410
    assert 'removed' in chat_response.get_json()['error'].lower()

    memory_response = client.post('/api/razzy/remember', headers=auth_headers, json={'conversation_id': 'x', 'content': 'y'})
    assert memory_response.status_code == 410
    assert 'removed' in memory_response.get_json()['error'].lower()

    recall_response = client.get('/api/razzy/memory/x', headers=auth_headers)
    assert recall_response.status_code == 410
    assert 'removed' in recall_response.get_json()['error'].lower()
