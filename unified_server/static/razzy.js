const apiKey = window.localStorage.getItem('razzy_api_key') || 'change-me';
const piTemperatureCardEl = document.getElementById('piTemperatureCard');
const piTemperatureBadgeEl = document.getElementById('piTemperatureBadge');
const piTemperatureValueEl = document.getElementById('piTemperatureValue');
const piTemperatureMetaEl = document.getElementById('piTemperatureMeta');
const piTemperatureAdvisoryEl = document.getElementById('piTemperatureAdvisory');
const llmRefreshBtnEl = document.getElementById('llmRefreshBtn');
const ollamaStartBtnEl = document.getElementById('ollamaStartBtn');
const ollamaStopBtnEl = document.getElementById('ollamaStopBtn');
const llmStatusMetaEl = document.getElementById('llmStatusMeta');
const llmLoaderEl = document.getElementById('llmLoader');
const llmStatusListEl = document.getElementById('llmStatusList');
let ollamaAvailability = 'unknown';
let llmBusy = false;

async function fetchAPI(url, options = {}) {
  const res = await fetch(url, options);
  const contentType = res.headers.get('content-type') || '';
  const raw = await res.text();
  const isJSON = contentType.includes('application/json');
  const data = isJSON && raw ? JSON.parse(raw) : null;

  if (!res.ok) {
    if (res.status === 401) {
      throw new Error('Unauthorized. Add a valid API key to use Razzy Chat.');
    }
    if (data?.error) {
      throw new Error(data.error);
    }
    if (!isJSON) {
      throw new Error('The server returned an unexpected page instead of API JSON.');
    }
    throw new Error('Request failed');
  }

  if (!isJSON) {
    throw new Error('The server returned an unexpected page instead of API JSON.');
  }

  return data;
}

function formatTime(value) {
  if (!value) return '';
  try {
    return new Date(value * 1000).toLocaleTimeString();
  } catch {
    return '';
  }
}

function applyThermalState(state) {
  piTemperatureCardEl.classList.remove('thermal-cool', 'thermal-normal', 'thermal-warm', 'thermal-hot');
  piTemperatureCardEl.classList.add(`thermal-${state}`);
}

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function renderLlmChecks(checks) {
  if (!checks.length) {
    llmStatusListEl.innerHTML = '<div class="empty-state">No provider results returned.</div>';
    return;
  }

  llmStatusListEl.innerHTML = checks.map((check) => {
    const stateClass = check.ok ? 'ok' : 'error';
    const models = Array.isArray(check.models) && check.models.length
      ? `<div class="llm-status-models">Models: ${escapeHtml(check.models.join(', '))}</div>`
      : '';
    const error = check.error
      ? `<div class="llm-status-error">${escapeHtml(check.error)}</div>`
      : '';
    return `
      <div class="llm-status-item ${stateClass}">
        <div class="llm-status-row">
          <div class="llm-status-provider">${escapeHtml(check.provider)}</div>
          <div class="system-metric-badge">${escapeHtml(check.status)}</div>
        </div>
        <div class="llm-status-detail">${escapeHtml(check.detail || '')}</div>
        ${models}
        ${error}
      </div>
    `;
  }).join('');
}

function updateOllamaActionButtons() {
  if (llmBusy) {
    ollamaStartBtnEl.disabled = true;
    ollamaStopBtnEl.disabled = true;
    return;
  }

  if (ollamaAvailability === 'online') {
    ollamaStartBtnEl.disabled = true;
    ollamaStopBtnEl.disabled = false;
    return;
  }

  if (ollamaAvailability === 'offline') {
    ollamaStartBtnEl.disabled = false;
    ollamaStopBtnEl.disabled = true;
    return;
  }

  ollamaStartBtnEl.disabled = false;
  ollamaStopBtnEl.disabled = false;
}

function setLlmBusy(isBusy, message) {
  llmBusy = isBusy;
  llmRefreshBtnEl.disabled = isBusy;
  llmLoaderEl.hidden = !isBusy;
  updateOllamaActionButtons();
  if (message) {
    llmStatusMetaEl.textContent = message;
  }
}

async function refreshLlmStatus() {
  setLlmBusy(true, 'Checking connections...');
  try {
    const data = await fetchAPI('/api/system/llm-status');
    const checks = data.checks || [];
    renderLlmChecks(checks);
    const ollamaCheck = checks.find((check) => check.provider === 'ollama');
    ollamaAvailability = ollamaCheck?.ok ? 'online' : ollamaCheck?.status === 'offline' ? 'offline' : 'unknown';
    const checkedAt = data.checked_at ? new Date(data.checked_at * 1000).toLocaleTimeString() : 'just now';
    llmStatusMetaEl.textContent = `Last checked at ${checkedAt}.`;
  } catch (error) {
    ollamaAvailability = 'unknown';
    llmStatusListEl.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
    llmStatusMetaEl.textContent = 'LLM status check failed.';
  } finally {
    setLlmBusy(false);
  }
}

async function controlOllama(action) {
  const actionLabel = action === 'stop' ? 'Stopping' : action === 'start' ? 'Starting' : 'Updating';
  setLlmBusy(true, `${actionLabel} Ollama...`);
  try {
    const data = await fetchAPI('/api/system/ollama/control', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': apiKey,
      },
      body: JSON.stringify({ action }),
    });

    const detail = data.detail || `Ollama ${action} completed.`;
    const state = data.service_state ? ` Current state: ${data.service_state}.` : '';
    const stderr = data.stderr ? ` ${data.stderr}` : '';
    llmStatusMetaEl.textContent = `${detail}${state}${stderr}`.trim();
    await refreshLlmStatus();
  } catch (error) {
    llmStatusMetaEl.textContent = `Ollama ${action} failed.`;
    llmStatusListEl.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
  } finally {
    setLlmBusy(false);
  }
}

async function loadPiTemperature() {
  try {
    const data = await fetchAPI('/api/system/temperature');
    const state = data.thermal_state || 'normal';
    applyThermalState(state);
    piTemperatureBadgeEl.textContent = state.toUpperCase();
    piTemperatureValueEl.textContent = `${data.temperature_f.toFixed(1)}°F`;
    const sourceLabel = data.cached ? 'Cached' : 'Fresh';
    const updatedAt = formatTime(data.fetched_at);
    piTemperatureMetaEl.textContent = `${sourceLabel} reading, updated ${updatedAt || 'just now'}, cache ${data.cache_ttl_seconds}s.`;
    piTemperatureAdvisoryEl.textContent = data.advisory || 'No thermal advisory available.';
  } catch (error) {
    applyThermalState('hot');
    piTemperatureBadgeEl.textContent = 'UNAVAILABLE';
    piTemperatureValueEl.textContent = 'Unavailable';
    piTemperatureMetaEl.textContent = error.message;
    piTemperatureAdvisoryEl.textContent = 'Temperature telemetry is unavailable right now.';
  }
}

llmRefreshBtnEl.addEventListener('click', refreshLlmStatus);
ollamaStartBtnEl.addEventListener('click', () => controlOllama('start'));
ollamaStopBtnEl.addEventListener('click', () => controlOllama('stop'));

updateOllamaActionButtons();
loadPiTemperature();
window.setInterval(loadPiTemperature, 15000);
