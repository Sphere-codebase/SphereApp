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
const frontendDebugBufferKey = "frontend_debug_log_buffer";
const frontendDebugMaxEntries = 200;
const frontendLogQueueMax = 200;
const frontendLogFlushIntervalMs = 1000;
const frontendLogMaxString = 500;
const chatLogEventAllowlist = new Set([
  "chat_request",
  "chat_response",
  "chat_response_parse_error",
  "send_message",
  "send_failed",
  "send_exception",
  "messages_load_start",
  "messages_load_ok",
  "messages_load_error",
  "reload_view_start",
  "reload_view_ok",
  "reload_view_default",
  "reload_view_empty",
  "session_select",
  "session_select_click",
  "session_create_start",
  "session_create_ok",
  "session_delete_click",
  "session_delete_cancel",
  "session_delete_ok",
  "session_delete_error",
  "render_thread",
  "fetch_start",
  "fetch_ok",
  "fetch_error",
  "fetch_no_content",
]);
const frontendLogForbiddenKeys = [
  "authorization",
  "access_token",
  "password",
  "cookie",
  "cookies",
  "token",
  "jwt",
];
let frontendLogCooldownUntil = 0;
let sessionId = null;
let frontendLogFlushTimer = null;
const frontendLogQueue = [];
let debugLogBuffer = [];
let chatAppInitialized = false;
let lastMessagesCount = 0;
let refreshTimer = null;

try {
  const persistedBuffer = sessionStorage.getItem(frontendDebugBufferKey);
  if (persistedBuffer) {
    debugLogBuffer = JSON.parse(persistedBuffer);
  }
} catch (error) {
  debugLogBuffer = [];
}

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
    logEvent("frontend_log_reset");
  } catch (error) {
    // ignore
  }
}

async function frontendLog(entry) {
  if (!frontendLogEnabled()) {
    return "drop";
  }
  const now = Date.now();
  const persistedCooldown = Number(localStorage.getItem(frontendLogCooldownKey) || 0);
  if (now < frontendLogCooldownUntil || now < persistedCooldown) {
    return "cooldown";
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
      return "cooldown";
    }
    if (!response.ok) {
      return "drop";
    }
    return "sent";
  } catch (error) {
    return "drop";
  }
}

function truncateLogValue(value) {
  if (typeof value !== "string") {
    return value;
  }
  if (value.length <= frontendLogMaxString) {
    return value;
  }
  return `${value.slice(0, frontendLogMaxString)}...`;
}

function sanitizeLogEntry(value) {
  if (Array.isArray(value)) {
    return value.map((item) => sanitizeLogEntry(item));
  }
  if (value && typeof value === "object") {
    const sanitized = {};
    Object.entries(value).forEach(([key, item]) => {
      const lowered = key.toLowerCase();
      if (frontendLogForbiddenKeys.includes(lowered) || lowered.includes("token")) {
        sanitized[key] = "[REDACTED]";
        return;
      }
      sanitized[key] = sanitizeLogEntry(item);
    });
    return sanitized;
  }
  if (typeof value === "string") {
    const lowered = value.toLowerCase();
    if (lowered.includes("bearer ")) {
      return "[REDACTED]";
    }
    return truncateLogValue(value);
  }
  return value;
}

function isChatEndpoint(endpoint) {
  if (!endpoint || typeof endpoint !== "string") {
    return false;
  }
  return endpoint === "/chat" || endpoint.startsWith("/api/chat");
}

function shouldLogEvent(event, data) {
  if (!chatLogEventAllowlist.has(event)) {
    return false;
  }
  if (event.startsWith("fetch_")) {
    return isChatEndpoint(data?.endpoint);
  }
  return true;
}

function persistDebugBuffer() {
  try {
    const trimmed = debugLogBuffer.slice(-frontendDebugMaxEntries);
    sessionStorage.setItem(frontendDebugBufferKey, JSON.stringify(trimmed));
  } catch (error) {
    // ignore
  }
}

function appendDebugBuffer(entry) {
  debugLogBuffer.push(entry);
  if (debugLogBuffer.length > frontendDebugMaxEntries) {
    debugLogBuffer = debugLogBuffer.slice(-frontendDebugMaxEntries);
  }
  persistDebugBuffer();
}

function queueFrontendLog(entry) {
  if (!frontendLogEnabled()) {
    return;
  }
  frontendLogQueue.push(entry);
  if (frontendLogQueue.length > frontendLogQueueMax) {
    frontendLogQueue.splice(0, frontendLogQueue.length - frontendLogQueueMax);
  }
  if (!frontendLogFlushTimer) {
    frontendLogFlushTimer = setTimeout(flushFrontendLogQueue, frontendLogFlushIntervalMs);
  }
}

async function flushFrontendLogQueue() {
  frontendLogFlushTimer = null;
  if (!frontendLogQueue.length) {
    return;
  }
  const now = Date.now();
  const persistedCooldown = Number(localStorage.getItem(frontendLogCooldownKey) || 0);
  if (now < frontendLogCooldownUntil || now < persistedCooldown) {
    frontendLogFlushTimer = setTimeout(flushFrontendLogQueue, frontendLogFlushIntervalMs);
    return;
  }
  const entry = frontendLogQueue[0];
  const result = await frontendLog(entry);
  if (result === "sent" || result === "drop") {
    frontendLogQueue.shift();
  }
  if (frontendLogQueue.length) {
    frontendLogFlushTimer = setTimeout(flushFrontendLogQueue, frontendLogFlushIntervalMs);
  }
}

function logEvent(event, data = {}) {
  if (!shouldLogEvent(event, data)) {
    return;
  }
  const entry = sanitizeLogEntry({
    ts: new Date().toISOString(),
    event,
    path: window.location.pathname,
    session_id: sessionId,
    ...data,
  });
  console.debug("[chat]", entry);
  appendDebugBuffer(entry);
  queueFrontendLog(entry);
}

function installFrontendLogHandlers() {
  window.addEventListener("error", (event) => {
    console.error("[chat] window_error", event.message);
  });
  window.addEventListener("unhandledrejection", (event) => {
    console.error("[chat] unhandled_rejection", event.reason);
  });
  window.addEventListener("beforeunload", () => {
    // no-op: keep chat logs minimal
  });
}

function updateSessionActiveUI(activeSessionId) {
  const items = sessionList.querySelectorAll("li.list-group-item-action");
  items.forEach((item) => {
    item.classList.toggle("active", item.dataset.sessionId === activeSessionId);
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
    lastMessagesCount = 0;
    logEvent("render_thread", { count: 0 });
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
  lastMessagesCount = messages.length;
  logEvent("render_thread", { count: messages.length });
}

async function fetchJson(url, options = {}) {
  const token = getToken();
  if (!token) {
    logEvent("fetch_missing_token", { endpoint: url });
    throw new Error("missing token");
  }
  const headers = options.headers || {};
  headers.Authorization = `Bearer ${token}`;
  options.headers = headers;
  logEvent("fetch_start", {
    endpoint: url,
    method: options.method || "GET",
  });
  const response = await fetch(url, options);
  if (!response.ok) {
    logEvent("fetch_error", { endpoint: url, status: response.status });
    showToast(`Request failed (${response.status}).`);
    throw new Error("request failed");
  }
  if (response.status === 204) {
    logEvent("fetch_no_content", { endpoint: url, status: response.status });
    return null;
  }
  logEvent("fetch_ok", { endpoint: url, status: response.status });
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
  logEvent("toast", { variant, message });
  setTimeout(() => {
    toast.remove();
  }, 3500);
}

async function loadStatus() {
  try {
    logEvent("status_check_start");
    const response = await fetch("/api/status");
    if (!response.ok) {
      setBadge(statusOverall, false, "Error");
      showToast("Status check failed.");
      logEvent("status_check_error", { status: response.status });
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
    logEvent("status_check_ok", {
      db_ready: data.db_ready,
      llm_ready: data.llm_ready,
      overall_ready: data.overall_ready,
    });
  } catch (error) {
    setBadge(statusOverall, false, "Error");
    showToast("Status check failed.");
    logEvent("status_check_exception", { message: String(error) });
  }
}

async function loadSessions() {
  logEvent("sessions_load_start");
  const sessions = await fetchJson("/api/chat/sessions");
  sessionList.innerHTML = "";
  if (!sessions.length) {
    const empty = document.createElement("li");
    empty.className = "list-group-item text-muted";
    empty.textContent = "No sessions yet.";
    sessionList.appendChild(empty);
    logEvent("sessions_load_empty");
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
      logEvent("session_delete_click", { session_id: session.id });
      if (!confirm("Delete this session and its history?")) {
        logEvent("session_delete_cancel", { session_id: session.id });
        return;
      }
      try {
        await fetchJson(`/api/chat/sessions/${session.id}`, { method: "DELETE" });
        if (sessionId === session.id) {
          sessionId = null;
          localStorage.removeItem("active_session_id");
        }
        await reloadChatView();
        logEvent("session_delete_ok", { session_id: session.id });
      } catch (error) {
        renderThread([]);
        logEvent("session_delete_error", { session_id: session.id, message: String(error) });
      }
    });
    item.dataset.sessionId = session.id;
    item.addEventListener("click", () => {
      logEvent("session_select_click", { session_id: session.id });
      switchSession(session.id);
    });
    if (session.id === sessionId) {
      item.classList.add("active");
    }
    item.appendChild(label);
    item.appendChild(deleteButton);
    sessionList.appendChild(item);
  });
  logEvent("sessions_load_ok", { count: sessions.length });
  return sessions;
}

async function loadMessages(activeSessionId) {
  try {
    logEvent("messages_load_start", { session_id: activeSessionId });
    const messages = await fetchJson(`/api/chat/sessions/${activeSessionId}/messages`);
    renderThread(messages);
    logEvent("messages_load_ok", {
      session_id: activeSessionId,
      count: messages.length,
    });
  } catch (error) {
    showToast("Unable to load messages.");
    logEvent("messages_load_error", { session_id: activeSessionId, message: String(error) });
  }
}

function scheduleRefreshMessages(activeSessionId) {
  if (refreshTimer) {
    clearTimeout(refreshTimer);
  }
  refreshTimer = setTimeout(async () => {
    refreshTimer = null;
    await loadMessages(activeSessionId);
  }, 100);
}

async function switchSession(newSessionId) {
  sessionId = newSessionId;
  localStorage.setItem("active_session_id", newSessionId);
  logEvent("session_select", { session_id: newSessionId });
  updateSessionActiveUI(newSessionId);
  await loadMessages(newSessionId);
}

async function reloadChatView() {
  logEvent("reload_view_start");
  if (sessionId) {
    localStorage.setItem("active_session_id", sessionId);
  }
  const sessions = await loadSessions();
  if (!sessions.length) {
    renderThread([]);
    logEvent("reload_view_empty");
    return;
  }
  const persisted = localStorage.getItem("active_session_id");
  const matched = sessions.find((session) => session.id === persisted);
  if (matched) {
    sessionId = matched.id;
    localStorage.setItem("active_session_id", sessionId);
    updateSessionActiveUI(sessionId);
    await loadMessages(matched.id);
    logEvent("reload_view_ok", { session_id: matched.id });
    return;
  }
  sessionId = sessions[0].id;
  localStorage.setItem("active_session_id", sessionId);
  updateSessionActiveUI(sessionId);
  await loadMessages(sessionId);
  logEvent("reload_view_default", { session_id: sessionId });
}

async function createSession() {
  logEvent("session_create_start");
  const session = await fetchJson("/api/chat/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  sessionId = session.id;
  localStorage.setItem("active_session_id", sessionId);
  logEvent("session_create_ok", { session_id: session.id });
  await loadSessions();
  updateSessionActiveUI(sessionId);
  await loadMessages(sessionId);
}

newSessionButton.addEventListener("click", async () => {
  try {
    logEvent("new_session_click");
    await createSession();
  } catch (error) {
    renderThread([]);
    logEvent("new_session_error", { message: String(error) });
  }
});

logoutButton.addEventListener("click", () => {
  logEvent("logout_click");
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
  logEvent("send_message", {
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
    logEvent("chat_request", { session_id: sessionId });
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2500);
    const chatPromise = fetch("/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    scheduleRefreshMessages(sessionId);

    chatPromise
      .then(async (response) => {
        clearTimeout(timeoutId);
        if (!response.ok) {
          logEvent("send_failed", { status: response.status });
          showToast("Message send failed.");
          return;
        }

        let data = null;
        try {
          data = await response.json();
        } catch (error) {
          logEvent("chat_response_parse_error", {
            status: response.status,
            message: String(error),
          });
          showToast("Message send failed.");
          return;
        }
        logEvent("chat_response", { status: response.status, session_id: data.session_id });
        if (data.session_id && data.session_id !== sessionId) {
          sessionId = data.session_id;
        }
        if (sessionId) {
          localStorage.setItem("active_session_id", sessionId);
        }
        await reloadChatView();
      })
      .catch((error) => {
        if (error?.name === "AbortError") {
          logEvent("send_exception", { message: "chat_timeout" });
          return;
        }
        logEvent("send_exception", { message: String(error) });
        showToast("Message send failed.");
      });
  } catch (error) {
    showToast("Message send failed.");
    renderThread([]);
    logEvent("send_exception", { message: String(error) });
  }
});

const alreadyInitialized = Boolean(window.__chatAppInitialized);
if (alreadyInitialized) {
  console.debug("[chat] init skipped (already initialized)");
} else {
  window.__chatAppInitialized = true;
  chatAppInitialized = true;
  (async () => {
    try {
      await frontendLogReset();
      logEvent("page_init");
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
}
