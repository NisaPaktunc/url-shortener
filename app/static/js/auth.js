// The log in / create account form.

import { api, saveSession } from "./api.js";
import { $, setVisible } from "./dom.js";
import { friendlyError } from "./format.js";

let mode = "login"; // "login" or "register"
let busy = false;
let onLoggedIn = () => {};

function setMode(newMode) {
  mode = newMode;
  for (const button of document.querySelectorAll(".mode-btn")) {
    button.setAttribute("aria-pressed", String(button.dataset.mode === mode));
  }
  const isRegister = mode === "register";
  $("auth-submit").textContent = isRegister ? "Create account" : "Log in";
  $("auth-password").autocomplete = isRegister ? "new-password" : "current-password";
  setVisible($("auth-hint"), isRegister);
  showError("");
}

function showError(message) {
  const element = $("auth-error");
  element.textContent = message;
  setVisible(element, message !== "");
}

function setBusy(value) {
  busy = value;
  $("auth-submit").disabled = value;
}

async function submit(event) {
  event.preventDefault();
  if (busy) return;

  const email = $("auth-email").value.trim().toLowerCase();
  const password = $("auth-password").value;
  if (!email || !password) {
    showError("Please enter your email and password.");
    return;
  }

  showError("");
  setVisible($("auth-notice"), false);
  setBusy(true);
  try {
    if (mode === "register") {
      await api.register(email, password);
    }
    const token = await api.login(email, password);
    saveSession(token.access_token, email);
    $("auth-password").value = "";
    onLoggedIn();
  } catch (error) {
    showError(friendlyError(error, mode));
  } finally {
    setBusy(false);
  }
}

/** Connect the form. `loggedIn` runs after a successful log in. */
export function initAuth(loggedIn) {
  onLoggedIn = loggedIn;
  for (const button of document.querySelectorAll(".mode-btn")) {
    button.addEventListener("click", () => setMode(button.dataset.mode));
  }
  $("auth-form").addEventListener("submit", submit);
}

/** Prepare the form to be shown. `notice` is an optional message above it. */
export function resetAuthForm(notice = "") {
  setMode("login");
  $("auth-password").value = "";
  const element = $("auth-notice");
  element.textContent = notice;
  setVisible(element, notice !== "");
}
