from __future__ import annotations

import subprocess

from unified_server.system import llm_status as llm_status_module
from unified_server.system import ollama_control as ollama_control_module
from unified_server.system import temperature as temperature_module


def test_system_temperature_returns_cached_snapshot(client, monkeypatch):
    reads: list[float] = []

    def fake_read() -> float:
        reads.append(48.2)
        return 48.2

    monkeypatch.setattr(temperature_module, '_read_pi_temperature_c', fake_read)

    first = client.get('/api/system/temperature')
    second = client.get('/api/system/temperature')

    assert first.status_code == 200
    assert second.status_code == 200

    first_payload = first.get_json()
    second_payload = second.get_json()

    assert first_payload['status'] == 'ok'
    assert first_payload['temperature_c'] == 48.2
    assert first_payload['temperature_f'] == 118.8
    assert first_payload['thermal_state'] == 'cool'
    assert first_payload['advisory'] == 'Cool, plenty of thermal headroom.'
    assert first_payload['cached'] is False

    assert second_payload['temperature_c'] == 48.2
    assert second_payload['temperature_f'] == 118.8
    assert second_payload['thermal_state'] == 'cool'
    assert second_payload['cached'] is True

    assert len(reads) == 1


def test_system_temperature_classifies_warm_values():
    payload = temperature_module._build_temperature_payload(73.2, 1234567890.0, cached=True, age_seconds=4.2)

    assert payload['thermal_state'] == 'warm'
    assert payload['advisory'] == 'Warm, but still acceptable under load.'
    assert payload['temperature_f'] == 163.8


def test_system_temperature_returns_502_when_sensor_read_fails(client, monkeypatch):
    def fake_read() -> float:
        raise RuntimeError('sensor missing')

    monkeypatch.setattr(temperature_module, '_read_pi_temperature_c', fake_read)

    response = client.get('/api/system/temperature')

    assert response.status_code == 502
    assert 'Unable to read Pi temperature' in response.get_json()['error']


def test_system_llm_status_returns_provider_checks(client, monkeypatch):
    monkeypatch.setattr(llm_status_module, '_probe_ollama_status', lambda: {
        'provider': 'ollama',
        'ok': True,
        'status': 'online',
        'detail': 'Reachable.',
        'models': ['mistral:latest'],
    })
    monkeypatch.setattr(llm_status_module, '_probe_openai_status', lambda: {
        'provider': 'openai',
        'ok': False,
        'status': 'quota',
        'detail': 'Out of quota.',
    })

    response = client.get('/api/system/llm-status')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'ok'
    assert len(payload['checks']) == 2
    assert payload['checks'][0]['provider'] == 'ollama'
    assert payload['checks'][1]['provider'] == 'openai'


def test_ollama_control_rejects_missing_api_key(client):
    response = client.post('/api/system/ollama/control', json={'action': 'stop'})

    assert response.status_code == 401
    assert response.get_json()['error'] == 'Unauthorized'


def test_ollama_control_runs_real_action(client, auth_headers, monkeypatch):
    responses = iter([
        subprocess.CompletedProcess(args=['systemctl', 'stop', 'ollama'], returncode=0, stdout='done\n', stderr=''),
        subprocess.CompletedProcess(args=['systemctl', 'is-active', 'ollama'], returncode=3, stdout='inactive\n', stderr=''),
    ])

    monkeypatch.setattr(ollama_control_module.subprocess, 'run', lambda *args, **kwargs: next(responses))

    response = client.post('/api/system/ollama/control', headers=auth_headers, json={'action': 'stop'})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'ok'
    assert payload['action'] == 'stop'
    assert payload['service_state'] == 'inactive'


def test_ollama_control_returns_502_when_command_fails(client, auth_headers, monkeypatch):
    responses = iter([
        subprocess.CompletedProcess(args=['systemctl', 'start', 'ollama'], returncode=1, stdout='', stderr='permission denied\n'),
        subprocess.CompletedProcess(args=['systemctl', 'is-active', 'ollama'], returncode=3, stdout='inactive\n', stderr=''),
    ])

    monkeypatch.setattr(ollama_control_module.subprocess, 'run', lambda *args, **kwargs: next(responses))

    response = client.post('/api/system/ollama/control', headers=auth_headers, json={'action': 'start'})

    assert response.status_code == 502
    payload = response.get_json()
    assert payload['status'] == 'error'
    assert payload['action'] == 'start'
    assert payload['stderr'] == 'permission denied'
