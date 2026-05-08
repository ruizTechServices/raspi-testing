const apiKey = window.localStorage.getItem('razzy_api_key') || 'change-me';
const dreamListEl = document.getElementById('dreamList');
const dreamDetailEl = document.getElementById('dreamDetail');
const dreamMetaEl = document.getElementById('dreamMeta');
const refreshDreamsBtnEl = document.getElementById('refreshDreamsBtn');

let dreams = [];
let currentDreamId = null;

function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatTime(value) {
  if (!value) return '';
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

async function apiFetch(url, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    'X-API-Key': apiKey,
    ...(options.headers || {}),
  };
  const response = await fetch(url, { ...options, headers });
  const contentType = response.headers.get('content-type') || '';
  const raw = await response.text();
  const isJSON = contentType.includes('application/json');
  const data = isJSON && raw ? JSON.parse(raw) : null;
  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('Unauthorized. Add a valid API key to view dream entries.');
    }
    if (data?.error) {
      throw new Error(data.error);
    }
    if (!isJSON) {
      throw new Error('Dream Mode received an unexpected page instead of API JSON.');
    }
    throw new Error('Request failed');
  }
  if (!isJSON) {
    throw new Error('Dream Mode received an unexpected page instead of API JSON.');
  }
  return data;
}

function renderDreamList() {
  dreamListEl.innerHTML = '';
  if (!dreams.length) {
    dreamListEl.innerHTML = '<div class="empty-state">No dream entries yet.</div>';
    return;
  }

  for (const dream of dreams) {
    const item = document.createElement('button');
    item.type = 'button';
    item.className = `conversation-item${dream.id === currentDreamId ? ' active' : ''}`;
    item.innerHTML = `
      <div class="conversation-title">${escapeHtml(dream.title || 'Dream Entry')}</div>
      <div class="conversation-time">${escapeHtml(formatTime(dream.updated_at))}</div>
    `;
    item.addEventListener('click', async () => {
      currentDreamId = dream.id;
      renderDreamList();
      await loadDream(dream.id);
    });
    dreamListEl.appendChild(item);
  }
}

async function loadDreams() {
  const data = await apiFetch('/api/gio/dreams');
  dreams = data.dreams || [];
  currentDreamId = dreams[0]?.id || null;
  renderDreamList();
  if (currentDreamId) {
    await loadDream(currentDreamId);
  } else {
    dreamDetailEl.innerHTML = '<div class="empty-state">No dream entries yet.</div>';
  }
}

async function loadDream(dreamId) {
  const dream = await apiFetch(`/api/gio/dreams/${dreamId}`);
  dreamMetaEl.textContent = `Conversation ID: ${dream.conversation_id} • Sources: ${(dream.source_message_ids || []).length}`;
  dreamDetailEl.innerHTML = `
    <div class="gio-message assistant">
      <div class="message-card">
        <div class="message-role">dream</div>
        <div class="message-content"><strong>${escapeHtml(dream.title)}</strong><br><br>${escapeHtml(dream.content).replace(/\n/g, '<br>')}</div>
        <div class="message-footer">
          <div class="message-time">${escapeHtml(formatTime(dream.created_at))}</div>
          <div class="message-model">${escapeHtml(dream.model || '')}</div>
        </div>
      </div>
    </div>
  `;
}

refreshDreamsBtnEl?.addEventListener('click', () => {
  loadDreams().catch((error) => {
    dreamDetailEl.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
  });
});

loadDreams().catch((error) => {
  dreamListEl.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
  dreamDetailEl.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
});
