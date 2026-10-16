// Small helpers for building the page.
//
// Safety rule: all text goes in with textContent / text nodes, never as HTML.
// So text from the server (like a target URL or a referrer) can never run
// as code, even if someone saved something nasty.

/** Find an element by id. Throws if it is missing, so mistakes show early. */
export function $(id) {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Element #${id} was not found in dashboard.html`);
  }
  return element;
}

/** Show or hide an element with the `hidden` attribute. */
export function setVisible(element, visible) {
  element.hidden = !visible;
}

/** Remove all children of an element. */
export function clear(element) {
  element.replaceChildren();
}

/**
 * Create an element.
 *
 *   h("button", { class: "btn", onclick: handler }, "Copy")
 *
 * Attributes: "class" sets the class name, "on..." adds an event listener,
 * "dataset" takes an object, true/false turn a boolean attribute on/off,
 * null/undefined are skipped. Children can be strings (added as text),
 * elements, or arrays of them. null/false children are skipped.
 */
export function h(tag, attrs = {}, ...children) {
  const element = document.createElement(tag);
  for (const [name, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (name === "class") {
      element.className = value;
    } else if (name === "dataset") {
      Object.assign(element.dataset, value);
    } else if (name.startsWith("on") && typeof value === "function") {
      element.addEventListener(name.slice(2), value);
    } else if (value === true) {
      element.setAttribute(name, "");
    } else {
      element.setAttribute(name, String(value));
    }
  }
  appendChildren(element, children);
  return element;
}

function appendChildren(element, children) {
  for (const child of children) {
    if (child === null || child === undefined || child === false) continue;
    if (Array.isArray(child)) {
      appendChildren(element, child);
    } else if (typeof child === "string" || typeof child === "number") {
      element.append(document.createTextNode(String(child)));
    } else {
      element.append(child);
    }
  }
}
