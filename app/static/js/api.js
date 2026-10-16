// Talks to the backend API and remembers the login in localStorage.

const TOKEN_KEY = "urlshortener.token";
const EMAIL_KEY = "urlshortener.email";

/**
 * The server answered with an error status (4xx or 5xx).
 *
 * The API sends errors as { error: { code, message, details?, request_id } }.
 * `details` (only for 422) is a list of { field, message }.
 */
export class ApiError extends Error {
  constructor(status, error) {
    super(`API error ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.code = error ? error.code : undefined;
    this.serverMessage = error ? error.message : undefined;
    this.detail = error ? error.details : undefined;
    this.requestId = error ? error.request_id : undefined;
  }
}

/** The request never got an answer (offline, server down). */
export class NetworkError extends Error {
  constructor() {
    super("Network error");
    this.name = "NetworkError";
  }
}

// ---------- Saved login ----------
// localStorage can be missing or can throw (private mode, blocked cookies).
// The dashboard still works then, you just have to log in again next time.

function readStorage(key) {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* ignore: the login only lives until the page is closed */
  }
}

function removeStorage(key) {
  try {
    window.localStorage.removeItem(key);
  } catch {
    /* ignore */
  }
}

// Kept in memory too, so a blocked localStorage does not log the user out
// in the middle of a visit.
let memoryToken = null;
let memoryEmail = null;

export function getToken() {
  return memoryToken || readStorage(TOKEN_KEY);
}

export function getEmail() {
  return memoryEmail || readStorage(EMAIL_KEY) || "";
}

export function saveSession(token, email) {
  memoryToken = token;
  memoryEmail = email;
  writeStorage(TOKEN_KEY, token);
  writeStorage(EMAIL_KEY, email);
}

export function clearSession() {
  memoryToken = null;
  memoryEmail = null;
  removeStorage(TOKEN_KEY);
  removeStorage(EMAIL_KEY);
}

// ---------- Requests ----------

let unauthorizedHandler = null;

/** Set a function that runs when a logged-in request gets a 401. */
export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler;
}

async function request(path, { method = "GET", json, form, auth = true } = {}) {
  const headers = { Accept: "application/json" };
  const options = { method, headers };
  if (auth && getToken()) {
    headers.Authorization = `Bearer ${getToken()}`;
  }
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(json);
  } else if (form !== undefined) {
    // URLSearchParams makes the browser send a form body.
    options.body = new URLSearchParams(form);
  }

  let response;
  try {
    response = await fetch(path, options);
  } catch {
    throw new NetworkError();
  }

  let body = null;
  try {
    body = await response.json();
  } catch {
    /* the answer had no JSON body */
  }

  if (!response.ok) {
    if (response.status === 401 && auth) {
      clearSession();
      if (unauthorizedHandler) unauthorizedHandler();
    }
    throw new ApiError(response.status, body ? body.error : undefined);
  }
  return body;
}

export const api = {
  register(email, password) {
    return request("/auth/register", {
      method: "POST",
      json: { email, password },
      auth: false,
    });
  },

  /** Log in. The login endpoint expects a form with the email as "username". */
  login(email, password) {
    return request("/auth/login", {
      method: "POST",
      form: { username: email, password },
      auth: false,
    });
  },

  listLinks() {
    return request("/links");
  },

  createLink(url, customCode) {
    const payload = { url };
    if (customCode) payload.custom_code = customCode;
    return request("/links", { method: "POST", json: payload });
  },

  getStats(code, days) {
    return request(`/links/${encodeURIComponent(code)}/stats?days=${days}`);
  },
};
