// The "create a link" form and the list of links.

import { api, ApiError } from "./api.js";
import { $, clear, h, setVisible } from "./dom.js";
import { formatDate, formatNumber, friendlyError, isHttpUrl } from "./format.js";

let onSelect = () => {};
let links = [];
let selectedCode = null;
let loadId = 0; // ignores answers from older requests
let creating = false;

// ---------- Copy to clipboard ----------

/** Copy text. Returns true if it worked. Falls back for plain http pages. */
export async function copyText(text) {
  const nav = window.navigator;
  if (nav.clipboard && window.isSecureContext) {
    try {
      await nav.clipboard.writeText(text);
      return true;
    } catch {
      /* try the old way below */
    }
  }
  return copyWithTextarea(text);
}

function copyWithTextarea(text) {
  const field = h("textarea", {
    class: "clipboard-fallback",
    readonly: true,
    "aria-hidden": "true",
    tabindex: "-1",
  });
  field.value = text;
  document.body.append(field);
  field.select();
  let copied = false;
  try {
    copied = typeof document.execCommand === "function" && document.execCommand("copy");
  } catch {
    copied = false;
  }
  field.remove();
  return copied;
}

// ---------- The list ----------

function showListState(title, message, extra = null, isError = false) {
  const element = $("links-state");
  element.className = isError ? "state state-error" : "state";
  clear(element);
  element.append(h("span", { class: "state-title" }, title));
  if (message) element.append(message);
  if (extra) element.append(h("div", {}, extra));
  setVisible(element, true);
  setVisible($("links-list"), false);
}

function showList() {
  setVisible($("links-state"), false);
  setVisible($("links-list"), true);
}

async function copyButtonClick(event, link) {
  event.stopPropagation();
  const button = event.currentTarget;
  const copied = await copyText(link.short_url);
  button.textContent = copied ? "Copied!" : "Copy failed";
  window.setTimeout(() => {
    button.textContent = "Copy";
  }, 1500);
}

function renderLink(link) {
  const shortLabel = isHttpUrl(link.short_url)
    ? h(
        "a",
        {
          class: "link-short",
          href: link.short_url,
          target: "_blank",
          rel: "noopener noreferrer",
          onclick: (event) => event.stopPropagation(),
        },
        link.short_url,
      )
    : h("span", { class: "link-short" }, link.short_url);

  const clickWord = link.total_clicks === 1 ? "click" : "clicks";
  return h(
    "li",
    {
      class: "link-item",
      dataset: { code: link.code },
      "aria-current": String(link.code === selectedCode),
      onclick: () => select(link.code),
    },
    h(
      "div",
      { class: "link-main" },
      shortLabel,
      h("div", { class: "link-target", title: link.target_url }, link.target_url),
      h(
        "div",
        { class: "link-meta" },
        h("span", { class: "link-clicks" }, `${formatNumber(link.total_clicks)} ${clickWord}`),
        h("span", {}, `Created ${formatDate(link.created_at)}`),
      ),
    ),
    h(
      "div",
      { class: "link-actions" },
      h(
        "button",
        { class: "btn btn-small", type: "button", onclick: (e) => copyButtonClick(e, link) },
        "Copy",
      ),
      h(
        "button",
        {
          class: "btn btn-small btn-primary",
          type: "button",
          onclick: (event) => {
            event.stopPropagation();
            select(link.code);
          },
        },
        "View stats",
      ),
    ),
  );
}

function renderList() {
  const list = $("links-list");
  clear(list);
  for (const link of links) {
    list.append(renderLink(link));
  }
  showList();
}

function select(code) {
  const link = links.find((item) => item.code === code);
  if (!link) return;
  selectedCode = code;
  for (const item of $("links-list").children) {
    item.setAttribute("aria-current", String(item.dataset.code === code));
  }
  onSelect(link);
}

/** Load the links from the server and show them. */
export async function loadLinks() {
  const myId = ++loadId;
  showListState("Loading your links...", "");
  try {
    const result = await api.listLinks();
    if (myId !== loadId) return;
    links = result;
    if (links.length === 0) {
      showListState("No links yet", "Create your first short link with the form above.");
      return;
    }
    renderList();
  } catch (error) {
    if (myId !== loadId) return;
    if (error instanceof ApiError && error.status === 401) return; // main.js handles it
    const retry = h("button", { class: "btn", type: "button", onclick: loadLinks }, "Try again");
    showListState("Could not load your links", friendlyError(error), retry, true);
  }
}

// ---------- The create form ----------

function showCreateError(message) {
  const element = $("create-error");
  element.textContent = message;
  setVisible(element, message !== "");
}

function showCreateStatus(message) {
  const element = $("create-status");
  element.textContent = message;
  setVisible(element, message !== "");
}

async function submitCreate(event) {
  event.preventDefault();
  if (creating) return;

  const url = $("create-url").value.trim();
  const code = $("create-code").value.trim();
  showCreateError("");
  showCreateStatus("");

  if (!isHttpUrl(url)) {
    showCreateError("Please enter a valid web address that starts with http:// or https://.");
    return;
  }

  creating = true;
  $("create-submit").disabled = true;
  try {
    const link = await api.createLink(url, code);
    $("create-url").value = "";
    $("create-code").value = "";
    showCreateStatus(`Done! Your short link is ${link.short_url}`);
    selectedCode = link.code;
    await loadLinks();
    select(link.code);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return; // main.js handles it
    showCreateError(friendlyError(error, "create"));
  } finally {
    creating = false;
    $("create-submit").disabled = false;
  }
}

/** Connect the form. `selected(link)` runs when the user picks a link. */
export function initLinks(selected) {
  onSelect = selected;
  $("create-form").addEventListener("submit", submitCreate);
}

/** Forget everything (used at log out). */
export function resetLinks() {
  loadId += 1;
  links = [];
  selectedCode = null;
  clear($("links-list"));
  $("create-url").value = "";
  $("create-code").value = "";
  showCreateError("");
  showCreateStatus("");
}
