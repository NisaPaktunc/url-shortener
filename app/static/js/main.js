// Entry point: decides which view to show and connects the parts.

import { clearSession, getEmail, getToken, setUnauthorizedHandler } from "./api.js";
import { initAuth, resetAuthForm } from "./auth.js";
import { $, setVisible } from "./dom.js";
import { initLinks, loadLinks, resetLinks } from "./links.js";
import { initStats, resetStats, showStats } from "./stats.js";

function showAuthView(notice = "") {
  resetLinks();
  resetStats();
  resetAuthForm(notice);
  setVisible($("dashboard-view"), false);
  setVisible($("auth-view"), true);
}

function showDashboardView() {
  $("user-email").textContent = getEmail();
  setVisible($("auth-view"), false);
  setVisible($("dashboard-view"), true);
  loadLinks();
}

function logout() {
  clearSession();
  showAuthView("You have been logged out.");
}

function start() {
  initAuth(showDashboardView);
  initLinks(showStats);
  initStats();
  $("logout-btn").addEventListener("click", logout);

  // Any request that gets a 401 sends the user back to the log in form.
  setUnauthorizedHandler(() => showAuthView("Your session expired. Please log in again."));

  if (getToken()) {
    showDashboardView();
  } else {
    showAuthView();
  }
}

start();
