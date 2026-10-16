// The statistics panel: total, line chart, device doughnut, referrer table.

import { api, ApiError } from "./api.js";
import { $, clear, h, setVisible } from "./dom.js";
import { formatDay, formatNumber, friendlyError } from "./format.js";

const DEFAULT_DAYS = 30;

// Fixed colors and names, so a device type always looks the same.
const DEVICES = [
  { key: "mobile", label: "Mobile", color: "#3b5bdb" },
  { key: "desktop", label: "Desktop", color: "#12b886" },
  { key: "tablet", label: "Tablet", color: "#f59f00" },
  { key: "bot", label: "Bots", color: "#868e96" },
];

let currentLink = null;
let currentDays = DEFAULT_DAYS;
let requestId = 0; // ignores answers from older requests
let dailyChart = null;
let deviceChart = null;

function prefersReducedMotion() {
  return typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function destroyCharts() {
  if (dailyChart) dailyChart.destroy();
  if (deviceChart) deviceChart.destroy();
  dailyChart = null;
  deviceChart = null;
}

function setRangeButtons(days) {
  for (const button of document.querySelectorAll(".range-btn")) {
    button.setAttribute("aria-pressed", String(Number(button.dataset.days) === days));
  }
}

function showState(title, message, extra = null, isError = false) {
  const element = $("stats-state");
  element.className = isError ? "state state-error" : "state";
  clear(element);
  element.append(h("span", { class: "state-title" }, title));
  if (message) element.append(message);
  if (extra) element.append(h("div", {}, extra));
  setVisible(element, true);
  setVisible($("stats-content"), false);
}

function showContent() {
  setVisible($("stats-state"), false);
  setVisible($("stats-content"), true);
}

// ---------- Drawing ----------

function renderTotal(stats) {
  $("stats-total").textContent = formatNumber(stats.total_clicks);
  $("stats-total-label").textContent = stats.total_clicks === 1 ? "click" : "clicks";
  $("stats-days").textContent = String(stats.days);
}

function renderReferrers(referrers) {
  const body = $("referrers-body");
  clear(body);
  const hasData = referrers.length > 0;
  setVisible($("referrers-empty"), !hasData);
  setVisible($("referrers-table"), hasData);
  for (const item of referrers) {
    body.append(
      h(
        "tr",
        {},
        h("td", { class: "referrer" }, item.referrer),
        h("td", { class: "num" }, formatNumber(item.clicks)),
      ),
    );
  }
}

function renderLegend(devices, total) {
  const legend = $("device-legend");
  clear(legend);
  for (const device of DEVICES) {
    const count = devices[device.key] || 0;
    const percent = total > 0 ? Math.round((count / total) * 100) : 0;
    legend.append(
      h(
        "li",
        {},
        h("span", { class: "swatch", style: `background:${device.color}` }),
        h("span", { class: "legend-name" }, device.label),
        h(
          "span",
          { class: count === 0 ? "legend-value legend-zero" : "legend-value" },
          `${formatNumber(count)} (${percent}%)`,
        ),
      ),
    );
  }
}

function drawDailyChart(daily, animate) {
  dailyChart = new window.Chart($("daily-chart"), {
    type: "line",
    data: {
      labels: daily.map((item) => formatDay(item.date)),
      datasets: [
        {
          label: "Clicks",
          data: daily.map((item) => item.clicks),
          borderColor: "#3b5bdb",
          backgroundColor: "rgba(59, 91, 219, 0.12)",
          fill: true,
          tension: 0.3,
          pointRadius: daily.length > 40 ? 0 : 3,
          pointHoverRadius: 5,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: animate ? undefined : false,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { maxTicksLimit: 8, maxRotation: 0 }, grid: { display: false } },
        y: { beginAtZero: true, ticks: { precision: 0 } },
      },
    },
  });
}

function drawDeviceChart(devices, animate) {
  deviceChart = new window.Chart($("device-chart"), {
    type: "doughnut",
    data: {
      labels: DEVICES.map((device) => device.label),
      datasets: [
        {
          data: DEVICES.map((device) => devices[device.key] || 0),
          backgroundColor: DEVICES.map((device) => device.color),
          borderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: animate ? undefined : false,
      cutout: "60%",
      plugins: { legend: { display: false } }, // we draw our own legend in HTML
    },
  });
}

function renderCharts(stats) {
  destroyCharts();
  const total = DEVICES.reduce((sum, d) => sum + (stats.devices[d.key] || 0), 0);
  renderLegend(stats.devices, total);

  const chartsAvailable = typeof window.Chart === "function";
  setVisible($("charts-unavailable"), !chartsAvailable);
  setVisible($("daily-card"), chartsAvailable);
  setVisible($("device-chart").parentElement, chartsAvailable && total > 0);
  if (!chartsAvailable) return;

  const animate = !prefersReducedMotion();
  drawDailyChart(stats.daily, animate);
  if (total > 0) drawDeviceChart(stats.devices, animate);
}

function render(stats) {
  if (stats.total_clicks === 0) {
    destroyCharts();
    showState(
      "No clicks yet",
      `Nobody opened this link in the last ${stats.days} days. Open the short link to record a click.`,
    );
    return;
  }
  renderTotal(stats);
  renderReferrers(stats.top_referrers);
  showContent();
  // Charts need a visible canvas to measure their size, so draw after showing.
  renderCharts(stats);
}

// ---------- Loading ----------

async function load() {
  if (!currentLink) return;
  const myId = ++requestId;
  const code = currentLink.code;
  const days = currentDays;
  showState("Loading statistics...", "");
  try {
    const stats = await api.getStats(code, days);
    if (myId !== requestId) return;
    render(stats);
  } catch (error) {
    if (myId !== requestId) return;
    if (error instanceof ApiError && error.status === 401) return; // main.js handles it
    destroyCharts();
    const retry = h("button", { class: "btn", type: "button", onclick: load }, "Try again");
    showState("Could not load statistics", friendlyError(error), retry, true);
  }
}

/** Show the statistics of a link (an item from the links list). */
export function showStats(link) {
  currentLink = link;
  $("stats-subtitle").textContent = link.short_url;
  setVisible($("stats-section"), true);
  load();
}

/** Hide the panel and forget the link (used at log out). */
export function resetStats() {
  requestId += 1;
  currentLink = null;
  currentDays = DEFAULT_DAYS;
  destroyCharts();
  setRangeButtons(DEFAULT_DAYS);
  setVisible($("stats-section"), false);
}

/** Connect the 7 / 30 / 90 day buttons. */
export function initStats() {
  for (const button of document.querySelectorAll(".range-btn")) {
    button.addEventListener("click", () => {
      currentDays = Number(button.dataset.days);
      setRangeButtons(currentDays);
      load();
    });
  }
}
