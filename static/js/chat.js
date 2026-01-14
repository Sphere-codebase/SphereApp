const form = document.getElementById("chat-form");
const input = document.getElementById("chat-input");
const thread = document.getElementById("chat-thread");
let sessionId = null;

function appendMessage(role, text) {
  const message = document.createElement("div");
  message.className = `message ${role}`;
  message.textContent = text;
  thread.appendChild(message);
  thread.scrollTop = thread.scrollHeight;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) {
    return;
  }

  appendMessage("user", message);
  input.value = "";

  const token = localStorage.getItem("access_token");
  if (!token) {
    appendMessage("assistant", "Please sign in again.");
    return;
  }

  const payload = { message };
  if (sessionId) {
    payload.session_id = sessionId;
  }

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      appendMessage("assistant", "Unable to complete the request.");
      return;
    }

    const data = await response.json();
    sessionId = data.session_id;
    appendMessage("assistant", data.assistant_message || "OK");
  } catch (error) {
    appendMessage("assistant", "Network error. Please retry.");
  }
});
