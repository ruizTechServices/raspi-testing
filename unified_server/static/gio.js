const apiKey = window.localStorage.getItem('razzy_api_key') || 'change-me';

const conversationListEl = document.getElementById('conversationList');
const transcriptEl = document.getElementById('gioTranscript');
const modelSelectEl = document.getElementById('gioModelSelect');
const messageInputEl = document.getElementById('gioMessageInput');
const sendBtnEl = document.getElementById('gioSendBtn');
const stopBtnEl = document.getElementById('gioStopBtn');
const newChatBtnEl = document.getElementById('newChatBtn');
const renameChatBtnEl = document.getElementById('renameChatBtn');
const deleteChatBtnEl = document.getElementById('deleteChatBtn');
const dreamChatBtnEl = document.getElementById('dreamChatBtn');
const statusTextEl = document.getElementById('gioStatusText');
const chatMetaEl = document.getElementById('chatMeta');
const topNavEl = document.querySelector('.top-nav');
const navMenuBtnEl = document.getElementById('navMenuBtn');
const sidebarToggleBtnEl = document.getElementById('sidebarToggleBtn');
const chatSidebarBtnEl = document.getElementById('chatSidebarBtn');
const mobileOverlayEl = document.getElementById('mobileOverlay');

let currentConversationId = window.localStorage.getItem('gio_current_conversation_id');
let conversations = [];
let currentStreamController = null;

function getStoredModel() {
  return window.localStorage.getItem('gio_selected_model') || '';
}

function setStoredModel(modelId) {
  if (!modelId) return;
  window.localStorage.setItem('gio_selected_model', modelId);
}

function persistCurrentConversationId() {
  if (currentConversationId) {
    window.localStorage.setItem('gio_current_conversation_id', currentConversationId);
  } else {
    window.localStorage.removeItem('gio_current_conversation_id');
  }
}

function hasConversation(conversationId) {
  return conversations.some((conversation) => conversation.id === conversationId);
}

function syncCurrentConversationId() {
  if (currentConversationId && hasConversation(currentConversationId)) {
    persistCurrentConversationId();
    return;
  }
  currentConversationId = conversations[0]?.id || null;
  persistCurrentConversationId();
}

function isMobileLayout() {
  return window.matchMedia('(max-width: 900px)').matches;
}

function setNavOpen(isOpen) {
  const open = isOpen && isMobileLayout();
  if (topNavEl) {
    topNavEl.classList.toggle('is-open', open);
  }
  if (navMenuBtnEl) {
    navMenuBtnEl.setAttribute('aria-expanded', String(open));
  }
}

function setSidebarOpen(isOpen) {
  const open = isOpen && isMobileLayout();
  document.body.classList.toggle('mobile-sidebar-open', open);
  if (sidebarToggleBtnEl) {
    sidebarToggleBtnEl.setAttribute('aria-expanded', String(open));
  }
  if (chatSidebarBtnEl) {
    chatSidebarBtnEl.setAttribute('aria-expanded', String(open));
  }
  if (mobileOverlayEl) {
    mobileOverlayEl.hidden = !open;
  }
}

function closeMobileChrome() {
  setNavOpen(false);
  setSidebarOpen(false);
}

function setStatus(text) {
  statusTextEl.textContent = text;
}

function setComposerBusy(isBusy) {
  sendBtnEl.disabled = isBusy;
  stopBtnEl.disabled = !isBusy;
  messageInputEl.disabled = isBusy;
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
      throw new Error('Unauthorized. Add a valid API key to use Gio Chat.');
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

async function loadModels() {
  const data = await apiFetch('/api/gio/models');
  modelSelectEl.innerHTML = '';
  const models = data.models || [];

  for (const model of models) {
    const option = document.createElement('option');
    option.value = model.id;
    option.textContent = model.supports_reasoning ? `${model.id} (thinking-capable)` : model.id;
    modelSelectEl.appendChild(option);
  }

  const preferredModel = getStoredModel();
  const preferredOption = models.find((model) => model.id === preferredModel);
  if (preferredOption) {
    modelSelectEl.value = preferredOption.id;
  } else if (models.length) {
    modelSelectEl.value = data.default_model && models.some((model) => model.id === data.default_model)
      ? data.default_model
      : models[0].id;
    setStoredModel(modelSelectEl.value);
  }
}

async function loadConversations() {
  const data = await apiFetch('/api/gio/conversations');
  conversations = data.conversations;
  syncCurrentConversationId();
  renderConversationList();
  if (currentConversationId) {
    await loadMessages(currentConversationId);
  } else {
    transcriptEl.innerHTML = '<div class="empty-state">No chats yet.</div>';
    chatMetaEl.textContent = 'Persistent Supabase-backed chat.';
  }
}

function renderConversationList() {
  conversationListEl.innerHTML = '';
  if (!conversations.length) {
    conversationListEl.innerHTML = '<div class="empty-state">No chats yet.</div>';
    return;
  }

  for (const conversation of conversations) {
    const item = document.createElement('button');
    item.type = 'button';
    item.className = `conversation-item${conversation.id === currentConversationId ? ' active' : ''}`;
    item.innerHTML = `
      <div class="conversation-title">${escapeHtml(conversation.title || 'New Chat')}</div>
      <div class="conversation-time">${escapeHtml(formatTime(conversation.updated_at))}</div>
    `;
    item.addEventListener('click', async () => {
      currentConversationId = conversation.id;
      persistCurrentConversationId();
      renderConversationList();
      await loadMessages(currentConversationId);
      setSidebarOpen(false);
    });
    conversationListEl.appendChild(item);
  }
}

function getCurrentConversation() {
  return conversations.find((conversation) => conversation.id === currentConversationId) || null;
}

async function createConversation() {
  const data = await apiFetch('/api/gio/session', {
    method: 'POST',
    body: JSON.stringify({ title: 'New Chat' }),
  });
  currentConversationId = data.id;
  persistCurrentConversationId();
  await loadConversations();
  transcriptEl.innerHTML = '<div class="empty-state">New chat created.</div>';
  setSidebarOpen(false);
}

async function renameConversation() {
  if (!currentConversationId) return;
  const currentConversation = getCurrentConversation();
  const currentTitle = currentConversation?.title || 'New Chat';
  const nextTitle = window.prompt('Rename chat', currentTitle);
  if (nextTitle === null) return;

  await apiFetch(`/api/gio/conversations/${currentConversationId}`, {
    method: 'PATCH',
    body: JSON.stringify({ title: nextTitle }),
  });
  await loadConversations();
  setStatus('Renamed');
}

async function deleteConversation() {
  if (!currentConversationId) return;
  const currentConversation = getCurrentConversation();
  const label = currentConversation?.title || 'this chat';
  const confirmed = window.confirm(`Delete ${label}? This cannot be undone.`);
  if (!confirmed) return;

  await apiFetch(`/api/gio/conversations/${currentConversationId}`, {
    method: 'DELETE',
  });

  conversations = conversations.filter((conversation) => conversation.id !== currentConversationId);
  currentConversationId = conversations[0]?.id || null;
  persistCurrentConversationId();

  renderConversationList();
  if (currentConversationId) {
    await loadMessages(currentConversationId);
  } else {
    transcriptEl.innerHTML = '<div class="empty-state">No chats yet.</div>';
    chatMetaEl.textContent = 'Persistent Supabase-backed chat.';
  }
  setStatus('Deleted');
}

async function createDream() {
  if (!currentConversationId) return;
  setStatus('Generating dream...');
  if (dreamChatBtnEl) dreamChatBtnEl.disabled = true;
  try {
    await apiFetch(`/api/gio/conversations/${currentConversationId}/dream`, {
      method: 'POST',
    });
    setStatus('Dream created');
    window.location.href = '/gio/dreams';
  } finally {
    if (dreamChatBtnEl) dreamChatBtnEl.disabled = false;
  }
}

async function loadMessages(conversationId) {
  const data = await apiFetch(`/api/gio/conversations/${conversationId}/messages`);
  renderMessages(data.messages || []);
  chatMetaEl.textContent = `Conversation ID: ${conversationId}`;
}

function renderMessages(messages) {
  transcriptEl.innerHTML = '';
  if (!messages.length) {
    transcriptEl.innerHTML = '<div class="empty-state">No messages yet.</div>';
    return;
  }
  for (const message of messages) {
    transcriptEl.appendChild(renderMessageCard(message));
  }
  transcriptEl.scrollTop = transcriptEl.scrollHeight;
}

function renderMessageCard(message) {
  const wrapper = document.createElement('div');
  wrapper.className = `gio-message ${message.role}`;
  const thinkingBlock = message.thinking_content
    ? `<details class="gio-thinking"><summary>Thinking</summary><pre>${escapeHtml(message.thinking_content)}</pre></details>`
    : '';
  const modelLabel = message.model ? escapeHtml(message.model) : '';
  const responseLabel = modelLabel;
  const footerMeta = responseLabel
    ? `<div class="message-model">${responseLabel}</div>`
    : '';
  wrapper.innerHTML = `
    <div class="message-card">
      <div class="message-role">${escapeHtml(message.role)}</div>
      <div class="message-content">${escapeHtml(message.content)}</div>
      ${thinkingBlock}
      <div class="message-footer">
        <div class="message-time">${escapeHtml(formatTime(message.created_at))}</div>
        ${footerMeta}
      </div>
    </div>
  `;
  return wrapper;
}

function createPendingAssistantCard(model) {
  const card = document.createElement('div');
  card.className = 'gio-message assistant is-streaming';
  const responseLabel = model || '';
  card.innerHTML = `
    <div class="message-card">
      <div class="message-role">assistant</div>
      <div class="message-content" data-role="content"></div>
      <div class="message-footer">
        <div class="message-time">Streaming...</div>
        <div class="message-model">${escapeHtml(responseLabel)}</div>
      </div>
    </div>
  `;
  transcriptEl.appendChild(card);
  transcriptEl.scrollTop = transcriptEl.scrollHeight;
  return {
    card,
    contentEl: card.querySelector('[data-role="content"]'),
    timeEl: card.querySelector('.message-time'),
  };
}

function stopStreaming() {
  if (currentStreamController) {
    currentStreamController.abort();
  }
}

async function sendMessage() {
  const message = messageInputEl.value.trim();
  if (!message) return;
  if (currentConversationId && !hasConversation(currentConversationId)) {
    currentConversationId = null;
    persistCurrentConversationId();
  }
  if (!currentConversationId) {
    await createConversation();
  }

  const model = modelSelectEl.value;
  setStatus('Streaming response...');
  setComposerBusy(true);

  const userTempMessage = {
    role: 'user',
    content: message,
    created_at: new Date().toISOString(),
    model,
  };
  transcriptEl.appendChild(renderMessageCard(userTempMessage));
  const pending = createPendingAssistantCard(model);
  let finalConversationId = currentConversationId;
  let buffer = '';
  let sawDone = false;

  try {
    currentStreamController = new AbortController();
    const response = await fetch('/api/gio/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': apiKey,
      },
      body: JSON.stringify({
        conversation_id: currentConversationId,
        message,
        model,
      }),
      signal: currentStreamController.signal,
    });

    if (!response.ok || !response.body) {
      const contentType = response.headers.get('content-type') || '';
      const text = await response.text();
      const isJSON = contentType.includes('application/json');
      const data = isJSON && text ? JSON.parse(text) : null;
      if (response.status === 401) {
        throw new Error('Unauthorized. Add a valid API key to use Gio Chat.');
      }
      throw new Error(data?.error || (isJSON ? 'Streaming request failed' : 'The server returned an unexpected page instead of streaming data.'));
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.trim()) continue;
        const event = JSON.parse(line);
        if (event.type === 'meta') {
          finalConversationId = event.conversation_id || finalConversationId;
          if (finalConversationId && finalConversationId !== currentConversationId) {
            currentConversationId = finalConversationId;
            persistCurrentConversationId();
            chatMetaEl.textContent = `Conversation ID: ${currentConversationId}`;
          }
        } else if (event.type === 'delta') {
          pending.contentEl.textContent += event.delta || '';
          transcriptEl.scrollTop = transcriptEl.scrollHeight;
        } else if (event.type === 'done') {
          sawDone = true;
          finalConversationId = event.conversation_id || finalConversationId;
          pending.timeEl.textContent = 'Finalizing...';
          pending.card.classList.remove('is-streaming');
        } else if (event.type === 'error') {
          throw new Error(event.error || 'Streaming request failed');
        }
      }
    }

    if (buffer.trim()) {
      const event = JSON.parse(buffer);
      if (event.type === 'done') {
        sawDone = true;
        finalConversationId = event.conversation_id || finalConversationId;
      } else if (event.type === 'error') {
        throw new Error(event.error || 'Streaming request failed');
      }
    }

    if (!sawDone) {
      throw new Error('Stream ended before completion');
    }

    messageInputEl.value = '';
    await loadConversations();
    await loadMessages(finalConversationId || currentConversationId);
    setStatus('Done');
  } catch (error) {
    pending.card.classList.remove('is-streaming');
    if (error.name === 'AbortError') {
      pending.timeEl.textContent = 'Stopped';
      setStatus('Stopped');
    } else {
      pending.contentEl.textContent = pending.contentEl.textContent || `Error: ${error.message}`;
      pending.timeEl.textContent = 'Error';
      setStatus('Error');
    }
  } finally {
    currentStreamController = null;
    setComposerBusy(false);
  }
}

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

newChatBtnEl.addEventListener('click', createConversation);
renameChatBtnEl.addEventListener('click', renameConversation);
deleteChatBtnEl.addEventListener('click', deleteConversation);
if (dreamChatBtnEl) {
  dreamChatBtnEl.addEventListener('click', () => {
    createDream().catch((error) => {
      setStatus(`Error: ${error.message}`);
    });
  });
}
stopBtnEl.addEventListener('click', stopStreaming);
sendBtnEl.addEventListener('click', sendMessage);
modelSelectEl.addEventListener('change', () => {
  setStoredModel(modelSelectEl.value);
});
if (navMenuBtnEl) {
  navMenuBtnEl.addEventListener('click', () => {
    const nextOpen = !topNavEl?.classList.contains('is-open');
    setNavOpen(nextOpen);
    if (nextOpen) setSidebarOpen(false);
  });
}
if (sidebarToggleBtnEl) {
  sidebarToggleBtnEl.addEventListener('click', () => {
    const nextOpen = !document.body.classList.contains('mobile-sidebar-open');
    setSidebarOpen(nextOpen);
    if (nextOpen) setNavOpen(false);
  });
}
if (chatSidebarBtnEl) {
  chatSidebarBtnEl.addEventListener('click', () => {
    const nextOpen = !document.body.classList.contains('mobile-sidebar-open');
    setSidebarOpen(nextOpen);
    if (nextOpen) setNavOpen(false);
  });
}
if (mobileOverlayEl) {
  mobileOverlayEl.addEventListener('click', closeMobileChrome);
}
window.addEventListener('resize', () => {
  if (!isMobileLayout()) {
    closeMobileChrome();
  }
});
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') {
    closeMobileChrome();
  }
});
messageInputEl.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
});

(async function init() {
  setStatus('Loading...');
  try {
    await loadModels();
    await loadConversations();
    setStatus('Idle');
  } catch (error) {
    setStatus(`Error: ${error.message}`);
  }
})();
