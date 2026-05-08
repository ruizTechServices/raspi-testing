from __future__ import annotations


def test_homepage_is_command_center_dashboard(client):
    response = client.get('/')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Razzy Command Center' in html
    assert 'Your local AI command hub' in html
    assert 'System Overview' in html
    assert 'Raspberry Pi 5' in html
    assert 'LLM Connections' in html
    assert 'Worker / Service Status' in html
    assert 'Active Chats' in html
    assert 'Recent Activity' in html
    assert '/console' in html
    assert '/gio/dreams' in html
    assert 'navMenuBtn' in html
    assert 'Provider' not in html
    assert 'Conversation ID' not in html


def test_console_page_serves_history_aware_console(client):
    response = client.get('/console')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Ollama Chatbot' in html
    assert 'navMenuBtn' in html
    assert 'History' in html
    assert '<label for="providerSelect">Provider</label>' in html
    assert 'Conversation ID' in html
    assert 'Server-first SQLite chat history' in html
    assert '/health' not in html
    assert '/api/providers' not in html
    assert '/api/razzy/profile' not in html
    assert '/api/twitter/status' not in html


def test_razzy_nav_hides_raw_api_links(client):
    response = client.get('/razzy')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'RAZZY' in html
    assert '/console' in html
    assert 'navMenuBtn' in html
    assert 'Pi Temperature' in html
    assert 'LLM Connections' in html
    assert 'Start Ollama' in html
    assert 'Stop Ollama' in html
    assert 'Razzy chatbot has been removed from this page' in html
    assert 'Developer testing console lives at <code>/console</code>' in html
    assert '<label for="provider">Provider</label>' not in html
    assert '<label for="model">Model</label>' not in html
    assert '<label for="message">Message</label>' not in html
    assert '/health' not in html
    assert '/api/providers' not in html
    assert '/api/razzy/profile' not in html
    assert '/api/twitter/status' not in html


def test_gio_nav_hides_raw_api_links_and_gio_models(client):
    response = client.get('/gio')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Gio Chat' in html
    assert '/console' in html
    assert 'navMenuBtn' in html
    assert '/gio/dreams' in html
    assert '/health' not in html
    assert '/api/providers' not in html
    assert '/api/gio/models' not in html


def test_gio_dreams_nav_hides_raw_api_links(client):
    response = client.get('/gio/dreams')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Dream Mode' in html
    assert '/console' in html
    assert 'navMenuBtn' in html
    assert '/health' not in html
