const DASHBOARD_API_KEY = window.localStorage.getItem('razzy_api_key') || 'change-me';

const greetingEl = document.getElementById('dashboardGreeting');
const clockEl = document.getElementById('dashboardClock');
const refreshBtnEl = document.getElementById('dashboardRefreshBtn');
const actionRefreshBtnEl = document.getElementById('dashboardActionRefresh');
const actionStartBtnEl = document.getElementById('dashboardActionStartOllama');
const actionStopBtnEl = document.getElementById('dashboardActionStopOllama');
const actionStatusEl = document.getElementById('dashboardActionStatus');

const piStateEl = document.getElementById('dashboardPiState');
const piTempEl = document.getElementById('dashboardPiTemp');
const piAdvisoryEl = document.getElementById('dashboardPiAdvisory');
const piCacheEl = document.getElementById('dashboardPiCache');
const piUpdatedEl = document.getElementById('dashboardPiUpdated');
const piStateTextEl = document.getElementById('dashboardPiStateText');
const piCardEl = document.getElementById('dashboardPiCard');

const llmListEl = document.getElementById('dashboardLlmList');
const serviceSummaryEl = document.getElementById('dashboardServiceSummary');
const serviceListEl = document.getElementById('dashboardServiceList');
const chatCountEl = document.getElementById('dashboardChatCount');
const chatListEl = document.getElementById('dashboardChatList');
const activityListEl = document.getElementById('dashboardActivityList');

let dashboardBusy = false;
let latestSnapshot = {
  pi: null,
  llmChecks: [],
  conversations: [],
  services: [],
};

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function setGreetingAndClock() {
  const now = new Date();
  const hour = now.getHours();
  let greeting = 'Good evening';
  if (hour < 12) greeting = 'Good morning';
  else if (hour < 18) greeting = 'Good afternoon';
  if (greetingEl) greetingEl.textContent = `${greeting}, Gio.`;
  if (clockEl) clockEl.textContent = now.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

function setActionStatus(text) {
  if (actionStatusEl) actionStatusEl.textContent = text;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const contentType = response.headers.get('content-type') || '';
  const raw = await response.text();
  const isJson = contentType.includes('application/json');
  const data = isJson && raw ? JSON.parse(raw) : null;

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('Unauthorized. Add a valid API key in localStorage as razzy_api_key.');
    }
    if (data?.error) {
      throw new Error(data.error);
    }
    if (!isJson) {
      throw new Error('The server returned HTML instead of JSON.');
    }
    throw new Error('Request failed');
  }

  if (!isJson) {
    throw new Error('The server returned HTML instead of JSON.');
  }

  return data;
}

function formatEpochSeconds(value) {
  if (!value) return '--';
  try {
    return new Date(value * 1000).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  } catch {
    return '--';
  }
}

function formatIso(value) {
  if (!value) return '--';
  try {
    return new Date(value).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
  } catch {
    return value;
  }
}

function minutesAgo(value) {
  if (!value) return null;
  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return null;
  return Math.max(0, Math.round((Date.now() - timestamp) / 60000));
}

function setPill(el, text, tone) {
  if (!el) return;
  el.textContent = text;
  el.classList.remove('ok', 'warn', 'error', 'neutral');
  el.classList.add(tone || 'neutral');
}

function renderPiCard(data) {
  latestSnapshot.pi = data;
  piCardEl.classList.remove('thermal-cool', 'thermal-normal', 'thermal-warm', 'thermal-hot');
  piCardEl.classList.add(`thermal-${data.thermal_state || 'normal'}`);
  setPill(piStateEl, (data.thermal_state || 'normal').toUpperCase(), data.thermal_state === 'hot' ? 'error' : data.thermal_state === 'warm' ? 'warn' : 'ok');
  piTempEl.textContent = `${data.temperature_f.toFixed(1)}°F`;
  piAdvisoryEl.textContent = data.advisory || 'No advisory.';
  piCacheEl.textContent = data.cached ? 'Cached' : 'Fresh';
  piUpdatedEl.textContent = formatEpochSeconds(data.fetched_at);
  piStateTextEl.textContent = data.thermal_state || '--';
}

function renderPiError(error) {
  setPill(piStateEl, 'ERROR', 'error');
  piTempEl.textContent = 'Unavailable';
  piAdvisoryEl.textContent = error.message;
  piCacheEl.textContent = '--';
  piUpdatedEl.textContent = '--';
  piStateTextEl.textContent = '--';
}

function renderLlmChecks(checks) {
  latestSnapshot.llmChecks = checks;
  if (!checks.length) {
    llmListEl.innerHTML = '<div class="empty-state">No provider results returned.</div>';
    return;
  }

  llmListEl.innerHTML = checks.map((check) => {
    const badgeTone = check.ok ? 'ok' : check.status === 'quota' || check.status === 'timeout' ? 'warn' : 'error';
    const models = Array.isArray(check.models) && check.models.length
      ? `<div class="dashboard-item-meta">${escapeHtml(check.models.slice(0, 3).join(', '))}</div>`
      : '';
    const detail = check.detail ? `<div class="dashboard-item-meta">${escapeHtml(check.detail)}</div>` : '';
    return `
      <div class="dashboard-list-item dashboard-list-item-soft">
        <div class="dashboard-list-main">
          <div class="dashboard-list-title">${escapeHtml(check.provider)}</div>
          ${detail}
          ${models}
        </div>
        <div class="dashboard-status-pill ${badgeTone}">${escapeHtml(check.status || 'unknown')}</div>
      </div>
    `;
  }).join('');
}

function renderServices(services) {
  latestSnapshot.services = services;
  const okCount = services.filter((service) => service.tone === 'ok').length;
  const warnCount = services.filter((service) => service.tone === 'warn').length;
  const errorCount = services.filter((service) => service.tone === 'error').length;
  const summaryTone = errorCount ? 'error' : warnCount ? 'warn' : 'ok';
  const summaryText = errorCount ? `${errorCount} issue${errorCount === 1 ? '' : 's'}` : warnCount ? `${warnCount} warning${warnCount === 1 ? '' : 's'}` : 'Healthy';
  setPill(serviceSummaryEl, summaryText, summaryTone);

  serviceListEl.innerHTML = services.map((service) => `
    <div class="dashboard-list-item dashboard-list-item-soft">
      <div class="dashboard-list-main">
        <div class="dashboard-list-title">${escapeHtml(service.label)}</div>
        <div class="dashboard-item-meta">${escapeHtml(service.detail)}</div>
      </div>
      <div class="dashboard-status-pill ${escapeHtml(service.tone)}">${escapeHtml(service.status)}</div>
    </div>
  `).join('');
}

function renderChats(conversations) {
  latestSnapshot.conversations = conversations;
  chatCountEl.textContent = String(conversations.length);
  if (!conversations.length) {
    chatListEl.innerHTML = '<div class="empty-state">No Gio chats yet.</div>';
    return;
  }

  const recent = [...conversations]
    .sort((a, b) => new Date(b.updated_at || 0).getTime() - new Date(a.updated_at || 0).getTime())
    .slice(0, 5);

  chatListEl.innerHTML = recent.map((conversation) => {
    const age = minutesAgo(conversation.updated_at);
    const meta = age === null ? 'Last update unknown' : age === 0 ? 'Updated just now' : `Updated ${age}m ago`;
    return `
      <a class="dashboard-list-item dashboard-list-link" href="/gio">
        <div class="dashboard-list-main">
          <div class="dashboard-list-title">${escapeHtml(conversation.title || 'New Chat')}</div>
          <div class="dashboard-item-meta">${escapeHtml(meta)}</div>
        </div>
        <div class="dashboard-list-time">${escapeHtml(formatIso(conversation.updated_at))}</div>
      </a>
    `;
  }).join('');
}

function renderActivity() {
  const items = [];

  if (latestSnapshot.pi) {
    items.push({
      title: `Pi temperature ${latestSnapshot.pi.temperature_f.toFixed(1)}°F`,
      meta: latestSnapshot.pi.advisory,
      tone: latestSnapshot.pi.thermal_state === 'hot' ? 'error' : latestSnapshot.pi.thermal_state === 'warm' ? 'warn' : 'ok',
    });
  }

  for (const check of latestSnapshot.llmChecks.slice(0, 2)) {
    items.push({
      title: `${check.provider} ${check.ok ? 'reachable' : 'needs attention'}`,
      meta: check.detail || check.status || 'Unknown state',
      tone: check.ok ? 'ok' : check.status === 'quota' ? 'warn' : 'error',
    });
  }

  if (latestSnapshot.conversations.length) {
    const latestConversation = [...latestSnapshot.conversations]
      .sort((a, b) => new Date(b.updated_at || 0).getTime() - new Date(a.updated_at || 0).getTime())[0];
    items.push({
      title: `Latest chat: ${latestConversation.title || 'New Chat'}`,
      meta: `Updated ${formatIso(latestConversation.updated_at)}`,
      tone: 'neutral',
    });
  }

  if (!items.length) {
    activityListEl.innerHTML = '<div class="empty-state">No live activity yet.</div>';
    return;
  }

  activityListEl.innerHTML = items.map((item) => `
    <div class="dashboard-activity-row">
      <div class="dashboard-list-main">
        <div class="dashboard-list-title">${escapeHtml(item.title)}</div>
        <div class="dashboard-item-meta">${escapeHtml(item.meta)}</div>
      </div>
      <div class="dashboard-status-pill ${escapeHtml(item.tone || 'neutral')}">${escapeHtml((item.tone || 'neutral').toUpperCase())}</div>
    </div>
  `).join('');
}

async function loadServices() {
  const services = [];

  try {
    const health = await fetchJson('/health');
    services.push({
      label: 'Web UI',
      detail: health.status === 'ok' ? 'HTTP health endpoint responded.' : 'Unexpected health payload.',
      status: health.status === 'ok' ? 'Running' : 'Unknown',
      tone: health.status === 'ok' ? 'ok' : 'warn',
    });
  } catch (error) {
    services.push({
      label: 'Web UI',
      detail: error.message,
      status: 'Error',
      tone: 'error',
    });
  }

  try {
    const ollama = await fetchJson('/api/system/ollama/control', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': DASHBOARD_API_KEY,
      },
      body: JSON.stringify({ action: 'status' }),
    });

    const state = ollama.service_state || 'unknown';
    services.push({
      label: 'Ollama Service',
      detail: ollama.detail || 'Service state checked.',
      status: state === 'active' ? 'Running' : state,
      tone: state === 'active' ? 'ok' : state === 'inactive' ? 'warn' : 'error',
    });
  } catch (error) {
    services.push({
      label: 'Ollama Service',
      detail: error.message,
      status: 'Blocked',
      tone: 'error',
    });
  }

  try {
    const gio = await fetchJson('/api/gio/conversations', {
      headers: {
        'X-API-Key': DASHBOARD_API_KEY,
      },
    });

    const conversations = gio.conversations || [];
    renderChats(conversations);
    services.push({
      label: 'Gio Chat Store',
      detail: `${conversations.length} conversation${conversations.length === 1 ? '' : 's'} available.`,
      status: 'Ready',
      tone: 'ok',
    });
  } catch (error) {
    renderChats([]);
    services.push({
      label: 'Gio Chat Store',
      detail: error.message,
      status: 'Blocked',
      tone: 'error',
    });
  }

  renderServices(services);
}

function setBusy(isBusy) {
  dashboardBusy = isBusy;
  if (refreshBtnEl) refreshBtnEl.disabled = isBusy;
  if (actionRefreshBtnEl) actionRefreshBtnEl.disabled = isBusy;
  if (actionStartBtnEl) actionStartBtnEl.disabled = isBusy;
  if (actionStopBtnEl) actionStopBtnEl.disabled = isBusy;
}

async function refreshDashboard() {
  if (dashboardBusy) return;
  setBusy(true);
  setActionStatus('Refreshing dashboard...');

  try {
    const [piResponse, llmResponse] = await Promise.allSettled([
      fetchJson('/api/system/temperature'),
      fetchJson('/api/system/llm-status'),
    ]);

    if (piResponse.status === 'fulfilled') {
      renderPiCard(piResponse.value);
    } else {
      renderPiError(piResponse.reason instanceof Error ? piResponse.reason : new Error('Pi status failed.'));
    }

    if (llmResponse.status === 'fulfilled') {
      renderLlmChecks(llmResponse.value.checks || []);
    } else {
      llmListEl.innerHTML = `<div class="empty-state">${escapeHtml(llmResponse.reason?.message || 'LLM status failed.')}</div>`;
      latestSnapshot.llmChecks = [];
    }

    await loadServices();
    renderActivity();
    setActionStatus('Dashboard refreshed.');
  } finally {
    setBusy(false);
  }
}

async function controlOllama(action) {
  if (dashboardBusy) return;
  setBusy(true);
  setActionStatus(`${action === 'start' ? 'Starting' : 'Stopping'} Ollama...`);

  try {
    const data = await fetchJson('/api/system/ollama/control', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': DASHBOARD_API_KEY,
      },
      body: JSON.stringify({ action }),
    });
    setActionStatus(data.detail || `Ollama ${action} completed.`);
    setBusy(false);
    await refreshDashboard();
  } catch (error) {
    setActionStatus(`Ollama ${action} failed: ${error.message}`);
    setBusy(false);
  }
}

if (refreshBtnEl) refreshBtnEl.addEventListener('click', refreshDashboard);
if (actionRefreshBtnEl) actionRefreshBtnEl.addEventListener('click', refreshDashboard);
if (actionStartBtnEl) actionStartBtnEl.addEventListener('click', () => controlOllama('start'));
if (actionStopBtnEl) actionStopBtnEl.addEventListener('click', () => controlOllama('stop'));

setGreetingAndClock();
window.setInterval(setGreetingAndClock, 30000);
refreshDashboard();
