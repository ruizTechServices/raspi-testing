from __future__ import annotations


def test_twitter_status(client, auth_headers):
    response = client.get('/api/twitter/status', headers=auth_headers)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['twitter']['configured'] is True
    assert payload['twitter']['supports_read'] is True
    assert payload['twitter']['supports_write'] is True


def test_twitter_me(client, auth_headers):
    response = client.get('/api/twitter/me', headers=auth_headers)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['data']['username'] == 'razzy'


def test_twitter_create_post(client, auth_headers):
    response = client.post('/api/twitter/post', headers=auth_headers, json={'text': 'hello x'})

    assert response.status_code == 201
    payload = response.get_json()
    assert payload['data']['text'] == 'hello x'


def test_twitter_reply(client, auth_headers):
    response = client.post('/api/twitter/posts/123/reply', headers=auth_headers, json={'text': 'reply text'})

    assert response.status_code == 201
    payload = response.get_json()
    assert payload['data']['reply_to_id'] == '123'
    assert payload['data']['text'] == 'reply text'


def test_twitter_quote(client, auth_headers):
    response = client.post('/api/twitter/posts/456/quote', headers=auth_headers, json={'text': 'quote text'})

    assert response.status_code == 201
    payload = response.get_json()
    assert payload['data']['quote_post_id'] == '456'
    assert payload['data']['text'] == 'quote text'


def test_twitter_delete_post(client, auth_headers):
    response = client.delete('/api/twitter/posts/789', headers=auth_headers)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['data']['deleted'] is True
    assert payload['data']['id'] == '789'


def test_twitter_user_timeline(client, auth_headers):
    response = client.get('/api/twitter/timeline/user/123456?max_results=15', headers=auth_headers)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['meta']['user_id'] == '123456'
    assert payload['meta']['max_results'] == 15


def test_twitter_create_post_rejects_empty_text(client, auth_headers):
    response = client.post('/api/twitter/post', headers=auth_headers, json={'text': '   '})

    assert response.status_code == 400
    assert response.get_json()['error'] == 'text is required.'
