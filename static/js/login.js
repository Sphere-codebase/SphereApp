const form = document.getElementById("login-form");
const errorBox = document.getElementById("login-error");

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("d-none");
}

function clearError() {
  errorBox.textContent = "";
  errorBox.classList.add("d-none");
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError();

  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value;

  try {
    const response = await fetch("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      showError("Invalid credentials.");
      return;
    }

    const payload = await response.json();
    const token = payload.access_token;
    if (!token) {
      showError("Login failed. Please try again.");
      return;
    }

    localStorage.setItem("access_token", token);
    document.cookie = `access_token=${token}; path=/; SameSite=Lax`;
    window.location.href = "/app/chat";
  } catch (error) {
    showError("Unable to reach the server.");
  }
});
