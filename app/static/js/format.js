// Helpers that turn data into text for people to read.

import { ApiError, NetworkError } from "./api.js";

const SESSION_EXPIRED = "Your session expired. Please log in again.";

/** Format a number with thousands separators: 1234 -> "1,234". */
export function formatNumber(value) {
  return Number(value).toLocaleString("en-US");
}

/** Format an ISO timestamp as a date in UTC: "Oct 11, 2026". */
export function formatDate(isoString) {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("en-US", {
    timeZone: "UTC",
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/** Format a "YYYY-MM-DD" day (already in UTC) as "Oct 11". */
export function formatDay(isoDay) {
  const [year, month, day] = String(isoDay).split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  if (Number.isNaN(date.getTime())) return String(isoDay);
  return date.toLocaleDateString("en-US", {
    timeZone: "UTC",
    month: "short",
    day: "numeric",
  });
}

/** True only for http and https addresses. Used before putting a URL in a link. */
export function isHttpUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

/**
 * Turn an error into a short message for the user.
 *
 * `context` tells where the error came from: "login", "register" or "create".
 * The same status code means different things in different places.
 */
export function friendlyError(error, context = "") {
  if (error instanceof NetworkError) {
    return "Could not reach the server. Check your connection and try again.";
  }
  if (!(error instanceof ApiError)) {
    return "Something went wrong. Please try again.";
  }
  switch (error.status) {
    case 401:
      return context === "login" ? "Wrong email or password." : SESSION_EXPIRED;
    case 409:
      if (context === "register") {
        return "An account with this email already exists. Try logging in.";
      }
      return "This code is already taken. Please choose another one.";
    case 422:
      return validationMessage(error.detail);
    case 429:
      return "Too many attempts. Please wait a minute and try again.";
    case 503:
      return "The server could not make a free code. Please try again.";
    default:
      return `Something went wrong (error ${error.status}). Please try again.`;
  }
}

// The API sends 422 details as a list: [{ field: "url", message: "..." }].
function validationMessage(detail) {
  if (!Array.isArray(detail) || detail.length === 0) {
    return "Some of the values are not valid.";
  }
  const first = detail[0] || {};
  const field = String(first.field || "").split(".").pop();
  const message = String(first.message || "");
  if (message.toLowerCase().includes("reserved")) {
    return message.replace(/^Value error,\s*/i, "");
  }
  const byField = {
    url: "Please enter a valid web address that starts with http:// or https://.",
    custom_code: "The custom code must be 3 to 32 letters or digits.",
    email: "Please enter a valid email address.",
    password: "The password must be 8 to 128 characters long.",
    username: "Please enter a valid email address.",
  };
  return byField[field] || "Some of the values are not valid.";
}
