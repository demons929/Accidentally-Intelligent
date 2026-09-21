const API_BASE = window.location.origin;
const TOKEN_KEY = "harryport_token";
const USER_KEY = "harryport_user";
const THEME_KEY = "harryport_theme";

const CATEGORY_IDS = {
  "Comparison requests": ["sidebar-count-comparison", "opt-comparison"],
  "New SI requests": ["sidebar-count-si", "opt-si"],
  "Invoice queries": ["sidebar-count-invoice", "opt-invoice"],
  "General mail": ["sidebar-count-general", "opt-general"],
  "Spam": ["sidebar-count-spam", "opt-spam"],
};

/* ------------------------------------------------------------------ */
/* Session helpers                                                     */
/* ------------------------------------------------------------------ */

function getToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

function getUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || "null");
  } catch {
    return null;
  }
}

function authHeaders() {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

async function requireSession() {
  try {
    const response = await fetch(`${API_BASE}/api/auth/session`, {
      headers: authHeaders(),
    });
    if (response.ok) return;
  } catch {
    // server unreachable -> fall through to redirect
  }
  redirectToLogin();
}

function redirectToLogin() {
  if (window.location.pathname.endsWith("login.html") || window.location.pathname === "/") return;
  window.location.href = "/login.html";
}

function signOut() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  window.location.href = "/login.html";
}

function renderUserBadge() {
  const user = getUser();
  if (!user) return;
  const initial = (user.name || "C").trim().charAt(0).toUpperCase();
  const avatar = document.querySelector("#header-avatar");
  const nameEl = document.getElementById("header-user-name");
  const roleEl = document.getElementById("header-user-role");
  if (avatar) avatar.innerText = initial;
  if (nameEl) nameEl.innerText = user.name;
  if (roleEl) roleEl.innerText = user.role;
}

/* ------------------------------------------------------------------ */
/* User profile modal                                                  */
/* ------------------------------------------------------------------ */

function renderProfile() {
  const user = getUser();
  if (!user) return;
  const initial = (user.name || "C").trim().charAt(0).toUpperCase();
  const setText = (id, value) => {
    const node = document.getElementById(id);
    if (node) node.innerText = value || "—";
  };
  const avatar = document.getElementById("profile-avatar");
  if (avatar) avatar.innerText = initial;
  setText("profile-name", user.name);
  setText("profile-role", user.role);
  setText("profile-email", user.email);
  setText("profile-job-title", user.job_title);
  setText("profile-department", user.department);
  setText("profile-employee-id", user.employee_id);
  setText("profile-phone", user.phone);
  setText("profile-location", user.location);
  setText("profile-joined", user.joined);
  setText("profile-timezone", user.timezone);
  setText("profile-last-login", user.last_login);
}

function openProfileModal() {
  renderProfile();
  openModal("profile-modal");
}

/* ------------------------------------------------------------------ */
/* API helpers                                                         */
/* ------------------------------------------------------------------ */

async function apiGet(path) {
  const response = await fetch(`${API_BASE}${path}`, { headers: authHeaders() });
  if (!response.ok) throw new Error(`API request failed: ${response.status}`);
  return response.json();
}

async function apiPost(path, body) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(body || {}),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `API request failed: ${response.status}`);
  }
  return response.json();
}

/* ------------------------------------------------------------------ */
/* Rendering helpers                                                   */
/* ------------------------------------------------------------------ */

function categoryBadge(category) {
  const styles = {
    "Comparison requests": "bg-navy text-gold border gold-border",
    "New SI requests": "bg-amber-100 text-amber-900 border border-amber-300",
    "Invoice queries": "bg-amber-900 text-amber-100 border border-amber-700",
    "General mail": "bg-slate-200 text-slate-800 border border-slate-300",
    "Spam": "bg-rose-100 text-rose-800 border border-rose-300",
  };
  return styles[category] || styles["General mail"];
}

function initials(sender) {
  return (sender || "?").trim().slice(0, 1).toUpperCase();
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

/* ------------------------------------------------------------------ */
/* Dashboard summary (sidebar counts + review cards)                   */
/* ------------------------------------------------------------------ */

async function updateDashboardSummary() {
  const summary = await apiGet("/api/emails/stats");
  Object.entries(CATEGORY_IDS).forEach(([category, ids]) => {
    const count = summary.categories[category] || 0;
    const sidebar = document.getElementById(ids[0]);
    const option = document.getElementById(ids[1]);
    if (sidebar) sidebar.innerText = count;
    if (option) option.innerText = `${category} (${count})`;
  });

  const optAll = document.getElementById("opt-all");
  if (optAll) optAll.innerText = `All Categories (${summary.total})`;

  const unreadable = summary.human_review.unreadable || 0;
  const corrupted = summary.human_review.corrupted || 0;
  const resolved = summary.human_review.resolved || 0;
  const reviewBadge = document.getElementById("review-badge");
  if (reviewBadge) reviewBadge.innerText = unreadable + corrupted;

  [
    ["unreadable-count", unreadable],
    ["summary-unreadable-count", unreadable],
    ["card-unreadable-count", unreadable],
    ["corrupted-count", corrupted],
    ["summary-corrupted-count", corrupted],
    ["card-corrupted-count", corrupted],
    ["resolved-count", resolved],
    ["summary-resolved-count", resolved],
    ["total-review-count", unreadable + corrupted + resolved],
  ].forEach(([id, value]) => {
    const node = document.getElementById(id);
    if (node) node.innerText = value;
  });
}

/* ------------------------------------------------------------------ */
/* View switching                                                      */
/* ------------------------------------------------------------------ */

function switchView(view) {
  const isInbox = view === "inbox";
  const inbox = document.getElementById("view-inbox");
  const review = document.getElementById("view-human-review");
  const title = document.getElementById("page-title");
  if (inbox) inbox.classList.toggle("hidden", !isInbox);
  if (review) review.classList.toggle("hidden", isInbox);
  if (title) title.innerText = isInbox ? "Inbox" : "Human Review";
  updateSidebarActive(isInbox ? "nav-inbox" : "nav-review");
}

function switchReviewSubPage(page) {
  switchView("human-review");
  const pages = [
    "hr-sub-dashboard",
    "hr-sub-unreadable-detail",
    "hr-sub-corrupted-detail",
  ];
  pages.forEach((id) => {
    const node = document.getElementById(id);
    if (node) node.classList.add("hidden");
  });
  const target = document.getElementById(`hr-sub-${page}`);
  if (target) target.classList.remove("hidden");
}

function updateSidebarActive(activeId) {
  ["nav-inbox", "nav-review", "nav-comparison", "nav-si", "nav-invoice", "nav-general", "nav-spam"].forEach((id) => {
    const node = document.getElementById(id);
    if (!node) return;
    node.classList.remove("gold-active-nav", "sidebar-active-gold", "sidebar-active-red");
  });
  const active = document.getElementById(activeId);
  if (active) active.classList.add("sidebar-active-gold");
}

/* ------------------------------------------------------------------ */
/* UI utilities                                                        */
/* ------------------------------------------------------------------ */

function openModal(id) {
  const node = document.getElementById(id);
  if (node) node.classList.remove("hidden");
}

function closeModal(id) {
  const node = document.getElementById(id);
  if (node) node.classList.add("hidden");
}

function toggleSidebar() {
  const sidebar = document.getElementById("sidebar");
  if (!sidebar) return;
  sidebar.classList.toggle("w-64");
  sidebar.classList.toggle("w-20");
  document.querySelectorAll(".sidebar-text").forEach((el) => el.classList.toggle("hidden"));
  const brand = document.getElementById("brand-text");
  if (brand) brand.classList.toggle("hidden");
}

function applyTheme(dark) {
  const body = document.getElementById("app-body");
  if (!body) return;
  body.classList.toggle("dark-mode", dark);
  try {
    localStorage.setItem(THEME_KEY, dark ? "dark" : "light");
  } catch {
    // storage unavailable (private mode) -> theme still applies for this page
  }
  const label = document.getElementById("theme-mode-label");
  const icon = document.getElementById("theme-icon");
  const toggle = document.getElementById("theme-toggle");
  if (label) label.innerText = dark ? "Dark Mode" : "Light Mode";
  if (toggle) toggle.checked = dark;
  if (icon) {
    icon.className = dark
      ? "fa-solid fa-moon text-gold text-lg"
      : "fa-solid fa-sun text-gold text-lg";
  }
}

function toggleTheme() {
  const body = document.getElementById("app-body");
  if (!body) return;
  applyTheme(!body.classList.contains("dark-mode"));
}

function goToComparison() {
  window.location.href = "/Comparison.html";
}

function goToInbox() {
  window.location.href = "/frontpage.html";
}

document.addEventListener("DOMContentLoaded", () => {
  let savedTheme = "light";
  try {
    savedTheme = localStorage.getItem(THEME_KEY) || "light";
  } catch {
    // ignore storage failures
  }
  applyTheme(savedTheme === "dark");
  requireSession().then(() => {
    renderUserBadge();
    Promise.allSettled([loadInbox(), loadHumanReview(), updateDashboardSummary()]).then(() => {
      const view = new URLSearchParams(window.location.search).get('view');
      if (view === 'review') switchReviewSubPage('dashboard');
    });
  });
});
