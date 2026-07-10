from __future__ import annotations

import pytest

from unified_server.razzy.service import RazzyService


def test_razzy_chat_validates_conversation_exists(fake_service):
    razzy = RazzyService(repository=fake_service.repository, providers=fake_service.providers)

    with pytest.raises(ValueError, match="Conversation not found"):
        razzy.chat("no-such-conversation", "hello razzy")


def test_razzy_chat_works_for_existing_conversation(fake_service):
    razzy = RazzyService(repository=fake_service.repository, providers=fake_service.providers)
    conversation_id = razzy.create_session()

    result = razzy.chat(conversation_id, "hello razzy")

    assert result["conversation_id"] == conversation_id
    assert result["message"]["content"] == "fake response"


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
