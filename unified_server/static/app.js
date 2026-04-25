const API_KEY = "change-me";

const providerSelect = document.getElementById("providerSelect");
const modelInput = document.getElementById("modelInput");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const clearBtn = document.getElementById("clearBtn");
const transcript = document.getElementById("transcript");
const debugOutput = document.getElementById("debugOutput");
const conversationIdText = document.getElementById("conversationIdText");
const statusText = document.getElementById("statusText");

let currentConversationId = null;

function setStatus(text) {
  statusText.textContent = text;
}

function setDebug(value) {
  debugOutput.textContent =
    typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

function clearEmptyState() {
  const empty = transcript.querySelector(".empty-state");
  if (empty) empty.remove();
}

function appendMessage(role, content) {
  clearEmptyState();

  const card = document.createElement("div");
  card.className = "message-card";

  const roleLabel = document.createElement("div");
  roleLabel.className = "message-role";
  roleLabel.textContent = role;

  const body = document.createElement("div");
  body.className = "message-content";
  body.textContent = content;

  card.appendChild(roleLabel);
  card.appendChild(body);
  transcript.appendChild(card);
}

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.error || "Request failed");
  }

  return data;
}

async function loadProviders() {
  setStatus("Loading providers...");

  try {
    const data = await fetchJSON("/api/providers");
    const providers = data.providers || [];

    providerSelect.innerHTML = "";

    for (const provider of providers) {
      const option = document.createElement("option");
      option.value = provider.id;
      option.textContent = provider.id;
      providerSelect.appendChild(option);
    }

    providerSelect.value = providers.find(p => p.id === "ollama") ? "ollama" : (providers[0]?.id || "");
    setDebug(data);
    setStatus("Ready");
  } catch (error) {
    setDebug({ error: error.message });
    setStatus("Error loading providers");
  }
}

async function sendMessage() {
  const provider = providerSelect.value.trim();
  const model = modelInput.value.trim();
  const message = messageInput.value.trim();

  if (!provider || !model || !message) {
    setStatus("Provider, model, and message are required");
    return;
  }

  appendMessage("user", message);
  setStatus("Model is thinking...");

  const payload = {
    provider,
    model,
    message
  };

  if (currentConversationId) {
    payload.conversation_id = currentConversationId;
  }

  try {
    const data = await fetchJSON("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY
      },
      body: JSON.stringify(payload)
    });

    currentConversationId = data.conversation_id || currentConversationId;
    conversationIdText.textContent = currentConversationId || "Not started yet";

    appendMessage("assistant", data?.message?.content || "(No content returned)");
    setDebug(data);
    setStatus("Completed");
    messageInput.value = "";
  } catch (error) {
    appendMessage("assistant", `Error: ${error.message}`);
    setDebug({ error: error.message });
    setStatus("Request failed");
  }
}

function clearChat() {
  currentConversationId = null;
  conversationIdText.textContent = "Not started yet";
  transcript.innerHTML = `<div class="empty-state">No messages yet.</div>`;
  setDebug("Waiting...");
  setStatus("Idle");
}

sendBtn.addEventListener("click", sendMessage);
clearBtn.addEventListener("click", clearChat);

window.addEventListener("DOMContentLoaded", () => {
  setDebug("Waiting...");
  setStatus("Idle");
  loadProviders();
});