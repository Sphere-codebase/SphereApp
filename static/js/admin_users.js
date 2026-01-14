const form = document.getElementById("admin-user-form");
const successBox = document.getElementById("admin-success");
const errorBox = document.getElementById("admin-error");
const logoutButton = document.getElementById("logout-button");

function getToken() {
  return localStorage.getItem("access_token");
}

async function frontendLogReset() {
  const token = getToken();
  if (!token) {
    return;
  }
  try {
    await fetch("/api/frontend-log/reset", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch (error) {
    // ignore
  }
}

async function frontendLog(entry) {
  const token = getToken();
  if (!token) {
    return;
  }
  try {
    await fetch("/api/frontend-log", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(entry),
    });
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

function setMessage(element, message) {
  element.textContent = message;
  element.classList.remove("d-none");
}

function clearMessage(element) {
  element.textContent = "";
  element.classList.add("d-none");
}

logoutButton.addEventListener("click", () => {
  localStorage.removeItem("access_token");
  sessionStorage.removeItem("access_token");
  window.location.href = "/login";
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearMessage(successBox);
  clearMessage(errorBox);

  const token = getToken();
  if (!token) {
    setMessage(errorBox, "Please sign in again.");
    return;
  }

  const payload = {
    email: document.getElementById("admin-email").value.trim(),
    full_name: document.getElementById("admin-name").value.trim() || null,
    password: document.getElementById("admin-password").value,
    role: document.getElementById("admin-role").value || null,
  };

  try {
    const response = await fetch("/api/admin/users", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorPayload = await response.json().catch(() => null);
      const detail = errorPayload?.error?.message || "Unable to create user.";
      setMessage(errorBox, detail);
      frontendLog({ event: "admin_create_failed", status: response.status });
      return;
    }

    const data = await response.json();
    setMessage(successBox, `Created user ${data.email}.`);
    frontendLog({ event: "admin_create_success", user_email: data.email });
    form.reset();
  } catch (error) {
    setMessage(errorBox, "Network error. Please try again.");
  }
});

frontendLogReset();
installFrontendLogHandlers();
