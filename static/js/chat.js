const form = document.getElementById("chat-form");
const input = document.getElementById("chat-input");
const thread = document.getElementById("chat-thread");
const sessionList = document.getElementById("session-list");
const newSessionButton = document.getElementById("new-session-button");
const logoutButton = document.getElementById("logout-button");
const statusOverall = document.getElementById("status-overall");
const statusAgent = document.getElementById("status-agent");
const statusDb = document.getElementById("status-db");
const statusChecked = document.getElementById("status-checked");
const statusModel = document.getElementById("status-model");
const statusHost = document.getElementById("status-host");
const statusSteps = document.getElementById("status-steps");
const toastContainer = document.getElementById("toast-container");
const frontendLogCooldownKey = "frontend_log_cooldown_until";
let frontendLogCooldownUntil = 0;
let sessionId = null;

function getToken() {
  return localStorage.getItem("access_token");
}

function frontendLogEnabled() {
  return Boolean(getToken());
}

async function frontendLogReset() {
  if (!frontendLogEnabled()) {
    return;
  }
  try {
    await fetch("/api/frontend-log/reset", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${getToken()}`,
      },
    });
  } catch (error) {
    // ignore
  }
}

async function frontendLog(entry) {
  if (!frontendLogEnabled()) {
    return;
  }
  const now = Date.now();
  const persistedCooldown = Number(localStorage.getItem(frontendLogCooldownKey) || 0);
  if (now < frontendLogCooldownUntil || now < persistedCooldown) {
    return;
  }
  try {
    const response = await fetch("/api/frontend-log", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${getToken()}`,
      },
      body: JSON.stringify(entry),
    });
    if (response.status === 429) {
      const cooldownUntil = Date.now() + 10_000;
      frontendLogCooldownUntil = cooldownUntil;
      localStorage.setItem(frontendLogCooldownKey, String(cooldownUntil));
    }
  } catch (error) {
    // ignore
  }
}

function installFrontendLogHandlers() {
  window.addEventListener("error", (event) => {
    frontendLog({
      event: "window_error",
      message: event.message,
      filename: event.filename,
      lineno: event.lineno,
      colno: event.colno,
    });
  });
  window.addEventListener("unhandledrejection", (event) => {
    frontendLog({
      event: "unhandled_rejection",
      reason: String(event.reason || "unknown"),
    });
  });
}

function formatTime(isoString) {
  if (!isoString) {
    return "";
  }
  const date = new Date(isoString);
  return date.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function renderThread(messages) {
  thread.innerHTML = "";
  if (!messages.length) {
    const empty = document.createElement("div");
    empty.className = "text-muted small";
    empty.textContent = "Start by asking about a claim.";
    thread.appendChild(empty);
    return;
  }

  messages.forEach((message) => {
    const wrapper = document.createElement("div");
    wrapper.className = `message ${message.role}`;

    const content = document.createElement("div");
    content.textContent = message.content || "";

    const meta = document.createElement("div");
    meta.className = "message-meta";
    meta.textContent = formatTime(message.created_at);

    wrapper.appendChild(content);
    wrapper.appendChild(meta);
    thread.appendChild(wrapper);
  });
  thread.scrollTop = thread.scrollHeight;
}

async function fetchJson(url, options = {}) {
  const token = getToken();
  if (!token) {
    throw new Error("missing token");
  }
  const headers = options.headers || {};
  headers.Authorization = `Bearer ${token}`;
  options.headers = headers;
  const response = await fetch(url, options);
  if (!response.ok) {
    frontendLog({ event: "fetch_error", endpoint: url, status: response.status });
    showToast(`Request failed (${response.status}).`);
    throw new Error("request failed");
  }
  return response.json();
}

function formatClock(isoString) {
  if (!isoString) {
    return "--:--";
  }
  const date = new Date(isoString);
  return date.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function setBadge(element, ok, text) {
  element.classList.remove("bg-success", "bg-danger", "bg-secondary", "bg-warning");
  if (ok === null) {
    element.classList.add("bg-secondary");
  } else if (ok) {
    element.classList.add("bg-success");
  } else {
    element.classList.add("bg-danger");
  }
  element.textContent = text;
}

function showToast(message, variant = "danger") {
  if (!toastContainer) {
    return;
  }
  const toast = document.createElement("div");
  toast.className = `alert alert-${variant} shadow-sm mb-2`;
  toast.textContent = message;
  toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 3500);
}

async function loadStatus() {
  try {
    const response = await fetch("/api/status");
    if (!response.ok) {
      setBadge(statusOverall, false, "Error");
      showToast("Status check failed.");
      return;
    }
    const data = await response.json();
    setBadge(statusDb, data.db_ready, data.db_ready ? "OK" : "Down");
    setBadge(
      statusAgent,
      data.llm_ready === null ? null : data.llm_ready,
      data.llm_ready === null ? "N/A" : data.llm_ready ? "OK" : "Down"
    );
    setBadge(statusOverall, data.overall_ready, data.overall_ready ? "Ready" : "Degraded");
    statusChecked.textContent = `Checked: ${formatClock(data.checked_at)}`;
    statusModel.textContent = data.llm_model;
    statusHost.textContent = data.lmstudio_base_url;
    statusSteps.textContent = data.llm_max_steps;
  } catch (error) {
    setBadge(statusOverall, false, "Error");
    showToast("Status check failed.");
  }
}

async function loadSessions() {
  const sessions = await fetchJson("/api/chat/sessions");
  sessionList.innerHTML = "";
  if (!sessions.length) {
    const empty = document.createElement("li");
    empty.className = "list-group-item text-muted";
    empty.textContent = "No sessions yet.";
    sessionList.appendChild(empty);
    return [];
  }

  sessions.forEach((session) => {
    const item = document.createElement("li");
    item.className = "list-group-item list-group-item-action d-flex justify-content-between align-items-center";
    const label = document.createElement("span");
    label.textContent =
      session.title ||
      (session.claim_id ? `Claim ${session.claim_id}` : "General session");
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "btn btn-sm btn-outline-danger";
    deleteButton.textContent = "Delete";
    deleteButton.addEventListener("click", async (event) => {
      event.stopPropagation();
      if (!confirm("Delete this session and its history?")) {
        return;
      }
      try {
        await fetchJson(`/api/chat/sessions/${session.id}`, { method: "DELETE" });
        if (sessionId === session.id) {
          sessionId = null;
          localStorage.removeItem("active_session_id");
        }
        await reloadChatView();
      } catch (error) {
        renderThread([]);
      }
    });
    item.dataset.sessionId = session.id;
    item.addEventListener("click", () => {
      switchSession(session.id);
    });
    if (session.id === sessionId) {
      item.classList.add("active");
    }
    item.appendChild(label);
    item.appendChild(deleteButton);
    sessionList.appendChild(item);
  });
  return sessions;
}

async function loadMessages(activeSessionId) {
  try {
    const messages = await fetchJson(`/api/chat/sessions/${activeSessionId}/messages`);
    renderThread(messages);
    frontendLog({
      event: "load_messages",
      session_id: activeSessionId,
      count: messages.length,
    });
  } catch (error) {
    showToast("Unable to load messages.");
  }
}

async function switchSession(newSessionId) {
  sessionId = newSessionId;
  localStorage.setItem("active_session_id", newSessionId);
  frontendLog({ event: "select_session", session_id: newSessionId });
  await loadSessions();
  await loadMessages(newSessionId);
}

async function reloadChatView() {
  if (sessionId) {
    localStorage.setItem("active_session_id", sessionId);
  }
  const sessions = await loadSessions();
  if (!sessions.length) {
    renderThread([]);
    return;
  }
  const persisted = localStorage.getItem("active_session_id");
  const matched = sessions.find((session) => session.id === persisted);
  if (matched) {
    sessionId = matched.id;
    localStorage.setItem("active_session_id", sessionId);
    await loadMessages(matched.id);
    return;
  }
  sessionId = sessions[0].id;
  localStorage.setItem("active_session_id", sessionId);
  await loadMessages(sessionId);
}

async function createSession() {
  const session = await fetchJson("/api/chat/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  await switchSession(session.id);
}

newSessionButton.addEventListener("click", async () => {
  try {
    await createSession();
  } catch (error) {
    renderThread([]);
  }
});

logoutButton.addEventListener("click", () => {
  localStorage.removeItem("access_token");
  sessionStorage.removeItem("access_token");
  window.location.href = "/login";
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) {
    return;
  }

  input.value = "";
  frontendLog({
    event: "send_message",
    session_id: sessionId,
    message_length: message.length,
  });

  try {
    if (!sessionId) {
      await createSession();
    }

    const token = getToken();
    if (!token) {
      renderThread([]);
      return;
    }

    const payload = buildChatPayload(message, sessionId, null);
    const response = await fetch("/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      frontendLog({ event: "send_failed", status: response.status });
      showToast("Message send failed.");
      renderThread([]);
      return;
    }

    const data = await response.json();
    if (data.session_id && data.session_id !== sessionId) {
      sessionId = data.session_id;
    }
    if (sessionId) {
      localStorage.setItem("active_session_id", sessionId);
    }
    await reloadChatView();
  } catch (error) {
    showToast("Message send failed.");
    renderThread([]);
  }
});

(async () => {
  try {
    await frontendLogReset();
    installFrontendLogHandlers();
    const sessions = await loadSessions();
    const persisted = localStorage.getItem("active_session_id");
    const matched = sessions.find((session) => session.id === persisted);
    if (matched) {
      await switchSession(matched.id);
      return;
    }
    if (sessions.length) {
      await switchSession(sessions[0].id);
      return;
    }
    renderThread([]);
  } catch (error) {
    showToast("Unable to load sessions.");
    renderThread([]);
  }
})();

loadStatus();
setInterval(loadStatus, 12000);
