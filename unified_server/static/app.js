const DEFAULT_API_KEY = "change-me";
const STORAGE_KEYS = {
  conversationId: "razzy_console_current_conversation_id",
  provider: "razzy_console_provider",
  model: "razzy_console_model",
};

const providerSelect = document.getElementById("providerSelect");
const modelSelect = document.getElementById("modelSelect");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const clearBtn = document.getElementById("clearBtn");
const transcript = document.getElementById("transcript");
const debugOutput = document.getElementById("debugOutput");
const conversationIdText = document.getElementById("conversationIdText");
const statusText = document.getElementById("statusText");
const conversationListEl = document.getElementById("conversationList");
const newChatBtn = document.getElementById("newChatBtn");
const renameChatBtn = document.getElementById("renameChatBtn");
const deleteChatBtn = document.getElementById("deleteChatBtn");
const topNavEl = document.querySelector('.top-nav');
const navMenuBtnEl = document.getElementById('navMenuBtn');
const sidebarToggleBtnEl = document.getElementById('consoleSidebarToggleBtn');
const chatSidebarBtnEl = document.getElementById('consoleChatSidebarBtn');
const mobileOverlayEl = document.getElementById('consoleMobileOverlay');

const state = {
  currentConversationId: window.localStorage.getItem(STORAGE_KEYS.conversationId),
  providerCatalog: [],
  conversations: [],
  busy: false,
};

function getApiKey() {
  return window.localStorage.getItem("razzy_dev_api_key") || DEFAULT_API_KEY;
}

function getStoredProvider() {
  return window.localStorage.getItem(STORAGE_KEYS.provider) || "";
}

function getStoredModel() {
  return window.localStorage.getItem(STORAGE_KEYS.model) || "";
}

function setStoredProvider(provider) {
  if (provider) window.localStorage.setItem(STORAGE_KEYS.provider, provider);
}

function setStoredModel(model) {
  if (model) window.localStorage.setItem(STORAGE_KEYS.model, model);
}

function persistConversationId() {
  if (state.currentConversationId) {
    window.localStorage.setItem(STORAGE_KEYS.conversationId, state.currentConversationId);
  } else {
    window.localStorage.removeItem(STORAGE_KEYS.conversationId);
  }
}

function setStatus(text) {
  statusText.textContent = text;
}

function setDebug(value) {
  debugOutput.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

function isMobileLayout() {
  return window.matchMedia('(max-width: 960px)').matches;
}

function setNavOpen(isOpen) {
  const open = isOpen && isMobileLayout();
  if (topNavEl) topNavEl.classList.toggle('is-open', open);
  if (navMenuBtnEl) navMenuBtnEl.setAttribute('aria-expanded', String(open));
}

function setSidebarOpen(isOpen) {
  const open = isOpen && isMobileLayout();
  document.body.classList.toggle('mobile-sidebar-open', open);
  if (sidebarToggleBtnEl) sidebarToggleBtnEl.setAttribute('aria-expanded', String(open));
  if (chatSidebarBtnEl) chatSidebarBtnEl.setAttribute('aria-expanded', String(open));
  if (mobileOverlayEl) mobileOverlayEl.hidden = !open;
}

function closeMobileChrome() {
  setNavOpen(false);
  setSidebarOpen(false);
}

function setBusy(isBusy) {
  state.busy = isBusy;
  sendBtn.disabled = isBusy;
  messageInput.disabled = isBusy;
  providerSelect.disabled = isBusy;
  modelSelect.disabled = isBusy;
  newChatBtn.disabled = isBusy;
  renameChatBtn.disabled = isBusy || !state.currentConversationId;
  deleteChatBtn.disabled = isBusy || !state.currentConversationId;
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', '&quot;')
    .replaceAll("'", "&#39;");
}

function formatTime(value) {
  if (!value) return "";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function getProviderMeta(providerId) {
  return state.providerCatalog.find((provider) => provider.id === providerId) || null;
}

function syncModelOptions() {
  const provider = providerSelect.value;
  const meta = getProviderMeta(provider);
  const models = meta?.models || [];
  const defaultModel = meta?.default_model || "";
  const preferredModel = getStoredModel();

  modelSelect.innerHTML = "";
  for (const model of models) {
    const option = document.createElement("option");
    option.value = model;
    option.textContent = model;
    modelSelect.appendChild(option);
  }

  const nextValue = models.includes(preferredModel)
    ? preferredModel
    : models.includes(defaultModel)
      ? defaultModel
      : (models[0] || "");

  modelSelect.value = nextValue;
  setStoredModel(nextValue);
}

function renderEmptyTranscript(message = "Start a new chat to begin.") {
  transcript.innerHTML = `<div class="empty-state">${escapeHtml(message)}</div>`;
}

function renderMessageCard(message) {
  const wrapper = document.createElement("div");
  wrapper.className = `console-message ${message.role}`;
  wrapper.innerHTML = `
    <div class="message-card">
      <div class="message-role">${escapeHtml(message.role)}</div>
      <div class="message-content">${escapeHtml(message.content)}</div>
      <div class="console-message-footer">
        <div class="console-message-meta">${escapeHtml(formatTime(message.created_at))}</div>
        <div class="console-message-meta">${escapeHtml([message.provider, message.model].filter(Boolean).join(" · "))}</div>
      </div>
    </div>
  `;
  return wrapper;
}

function renderTranscript(messages) {
  transcript.innerHTML = "";
  if (!messages.length) {
    renderEmptyTranscript("No messages yet.");
    return;
  }

  for (const message of messages) {
    transcript.appendChild(renderMessageCard(message));
  }
  transcript.scrollTop = transcript.scrollHeight;
}

function renderConversationList() {
  conversationListEl.innerHTML = "";
  if (!state.conversations.length) {
    conversationListEl.innerHTML = '<div class="empty-state">No chats yet.</div>';
    return;
  }

  for (const conversation of state.conversations) {
    const item = document.createElement("button");
    item.type = "button";
    item.className = `console-conversation-item${conversation.id === state.currentConversationId ? ' active' : ''}`;
    item.innerHTML = `
      <div class="console-conversation-title">${escapeHtml(conversation.title || 'New Chat')}</div>
      <div class="console-conversation-time">${escapeHtml(formatTime(conversation.updated_at))}</div>
    `;
    item.addEventListener("click", async () => {
      state.currentConversationId = conversation.id;
      persistConversationId();
      renderConversationList();
      await loadMessages(conversation.id);
      closeMobileChrome();
    });
    conversationListEl.appendChild(item);
  }
}

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";
  const raw = await response.text();
  const isJSON = contentType.includes("application/json");
  const data = isJSON && raw ? JSON.parse(raw) : null;

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error("Unauthorized. Add a valid API key to use the dev console.");
    }
    if (data?.error) {
      throw new Error(data.error);
    }
    if (!isJSON) {
      throw new Error("The server returned an unexpected page instead of API JSON.");
    }
    throw new Error("Request failed");
  }

  if (!isJSON) {
    throw new Error("The server returned an unexpected page instead of API JSON.");
  }

  return data;
}

async function loadProviders() {
  const data = await fetchJSON("/api/providers");
  const providers = data.providers || [];
  state.providerCatalog = providers;

  providerSelect.innerHTML = "";
  for (const provider of providers) {
    const option = document.createElement("option");
    option.value = provider.id;
    option.textContent = provider.id;
    providerSelect.appendChild(option);
  }

  const preferredProvider = getStoredProvider();
  providerSelect.value = providers.some((p) => p.id === preferredProvider)
    ? preferredProvider
    : (providers.find((p) => p.id === "ollama")?.id || providers[0]?.id || "");

  setStoredProvider(providerSelect.value);
  syncModelOptions();
  setDebug(data);
}

async function loadConversations() {
  const data = await fetchJSON("/api/conversations", {
    headers: {
      "X-API-Key": getApiKey(),
    },
  });
  state.conversations = data.conversations || [];

  if (state.currentConversationId && !state.conversations.some((item) => item.id === state.currentConversationId)) {
    state.currentConversationId = null;
  }
  if (!state.currentConversationId) {
    state.currentConversationId = state.conversations[0]?.id || null;
  }

  persistConversationId();
  renderConversationList();
  conversationIdText.textContent = state.currentConversationId || "Not started yet";

  if (state.currentConversationId) {
    await loadMessages(state.currentConversationId);
  } else {
    renderEmptyTranscript();
  }
}

async function loadMessages(conversationId) {
  if (!conversationId) {
    renderEmptyTranscript();
    conversationIdText.textContent = "Not started yet";
    return;
  }

  const data = await fetchJSON(`/api/conversations/${conversationId}/messages`, {
    headers: {
      "X-API-Key": getApiKey(),
    },
  });
  conversationIdText.textContent = conversationId;
  renderTranscript(data.messages || []);
}

async function createConversation() {
  const data = await fetchJSON("/api/conversations", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": getApiKey(),
    },
    body: JSON.stringify({ title: "New Chat" }),
  });

  state.currentConversationId = data.conversation_id;
  persistConversationId();
  await loadConversations();
  setStatus("New chat created");
}

async function renameConversation() {
  if (!state.currentConversationId) return;
  const current = state.conversations.find((item) => item.id === state.currentConversationId);
  const nextTitle = window.prompt("Rename chat", current?.title || "New Chat");
  if (nextTitle === null) return;

  await fetchJSON(`/api/conversations/${state.currentConversationId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": getApiKey(),
    },
    body: JSON.stringify({ title: nextTitle }),
  });

  await loadConversations();
  setStatus("Renamed");
}

async function deleteConversation() {
  if (!state.currentConversationId) return;
  const current = state.conversations.find((item) => item.id === state.currentConversationId);
  const confirmed = window.confirm(`Delete ${current?.title || 'this chat'}? This cannot be undone.`);
  if (!confirmed) return;

  await fetchJSON(`/api/conversations/${state.currentConversationId}`, {
    method: "DELETE",
    headers: {
      "X-API-Key": getApiKey(),
    },
  });

  state.currentConversationId = null;
  persistConversationId();
  await loadConversations();
  setStatus("Deleted");
}

async function sendMessage() {
  const provider = providerSelect.value.trim();
  const model = modelSelect.value.trim();
  const message = messageInput.value.trim();

  if (!provider || !model || !message) {
    setStatus("Provider, model, and message are required");
    return;
  }

  if (!state.currentConversationId) {
    await createConversation();
  }

  setBusy(true);
  setStatus("Saving and sending...");

  try {
    const data = await fetchJSON("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": getApiKey(),
      },
      body: JSON.stringify({
        conversation_id: state.currentConversationId,
        provider,
        model,
        message,
      }),
    });

    state.currentConversationId = data.conversation_id || state.currentConversationId;
    persistConversationId();
    await loadConversations();
    await loadMessages(state.currentConversationId);
    setDebug(data);
    setStatus("Completed");
    messageInput.value = "";
  } catch (error) {
    setDebug({ error: error.message });
    setStatus("Request failed");
    throw error;
  } finally {
    setBusy(false);
  }
}

function clearView() {
  renderEmptyTranscript(state.currentConversationId ? "Reload a saved conversation from the left, or send a new message." : "Start a new chat to begin.");
  setStatus("View cleared");
}

async function init() {
  setBusy(false);
  setStatus("Loading...");
  setDebug("Waiting...");

  try {
    await loadProviders();
    await loadConversations();
    setStatus("Ready");
  } catch (error) {
    setDebug({ error: error.message });
    setStatus(`Error: ${error.message}`);
    renderEmptyTranscript("Unable to load chat state.");
  }
}

sendBtn.addEventListener("click", () => {
  sendMessage().catch((error) => {
    renderTranscript([{ role: "assistant", content: `Error: ${error.message}`, created_at: new Date().toISOString(), provider: providerSelect.value, model: modelSelect.value }]);
  });
});
clearBtn.addEventListener("click", clearView);
newChatBtn.addEventListener("click", () => createConversation().catch((error) => setStatus(`Error: ${error.message}`)));
renameChatBtn.addEventListener("click", () => renameConversation().catch((error) => setStatus(`Error: ${error.message}`)));
deleteChatBtn.addEventListener("click", () => deleteConversation().catch((error) => setStatus(`Error: ${error.message}`)));
providerSelect.addEventListener("change", () => {
  setStoredProvider(providerSelect.value);
  syncModelOptions();
  setStatus(`Provider selected: ${providerSelect.value}`);
});
modelSelect.addEventListener("change", () => {
  setStoredModel(modelSelect.value);
  setStatus(`Model selected: ${modelSelect.value}`);
});
messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendMessage().catch((error) => setStatus(`Error: ${error.message}`));
  }
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
  if (!isMobileLayout()) closeMobileChrome();
});
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') closeMobileChrome();
});
window.addEventListener("DOMContentLoaded", init);
