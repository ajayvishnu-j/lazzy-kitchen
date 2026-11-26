/* =====================================================================
   Hotel Lazzy-Kitchen — Shared application logic
   API base is relative ("/api/...") so Nginx proxies it to Flask.
   The customer session lives in a signed HttpOnly cookie set by Flask;
   sessionStorage only caches the display name for the navbar.
   ===================================================================== */

const API_BASE = "/api";

/* ---------------------------------------------------------------------
   Safe-output helpers (customer names etc. are user-supplied => escape)
   --------------------------------------------------------------------- */
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function inr(n) {
  const v = Number(n) || 0;
  return "₹" + (Number.isInteger(v) ? v.toLocaleString("en-IN") : v.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
}
function fmtDateTime(iso) {
  return iso ? new Date(iso).toLocaleString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "";
}
function fmtClock(iso) {
  return iso ? new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }) : "";
}

/* ---------------------------------------------------------------------
   Generic API helper
   --------------------------------------------------------------------- */
async function apiRequest(path, options = {}) {
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      credentials: "same-origin",
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      return { ok: false, status: response.status, message: data.message || "Request failed." };
    }
    return { ok: true, status: response.status, data };
  } catch (err) {
    return { ok: false, status: 0, message: "Unable to reach the server. Please try again." };
  }
}

/* ---------------------------------------------------------------------
   Toast notifications
   --------------------------------------------------------------------- */
function showToast(message, type = "success") {
  let container = document.querySelector(".toast-container");
  if (!container) {
    container = document.createElement("div");
    container.className = "toast-container";
    container.setAttribute("role", "status");
    container.setAttribute("aria-live", "polite");
    document.body.appendChild(container);
  }
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => { toast.classList.add("out"); setTimeout(() => toast.remove(), 320); }, 3200);
}

/* ---------------------------------------------------------------------
   Session (display cache) + auth guard
   --------------------------------------------------------------------- */
const Session = {
  save(customer) { sessionStorage.setItem("lazzy_customer", JSON.stringify(customer)); },
  get() { try { return JSON.parse(sessionStorage.getItem("lazzy_customer")); } catch { return null; } },
  clear() { sessionStorage.removeItem("lazzy_customer"); },
};

/** Verifies the cookie session with the server. Redirects to the login page if not logged in. */
async function ensureAuth() {
  const result = await apiRequest("/me");
  if (result.ok) {
    Session.save(result.data.customer);
    renderNav();
    return result.data.customer;
  }
  if (result.status === 401) {
    Session.clear();
    window.location.href = "index.html";
  }
  return null;
}

async function logout() {
  await apiRequest("/logout", { method: "POST" });
  Session.clear();
  if (typeof Cart !== "undefined") Cart.clear(true);
  sessionStorage.removeItem("lazzy_checkout");
  window.location.href = "index.html";
}

/* ---------------------------------------------------------------------
   Navbar (single source for every page)
   --------------------------------------------------------------------- */
function renderNav() {
  const nav = document.querySelector("#siteNav");
  if (!nav) return;
  const active = nav.dataset.active || "";
  const withCart = nav.hasAttribute("data-cart");
  const customer = Session.get();
  const link = (href, key, label) => `<a href="${href}" class="${active === key ? "active" : ""}">${label}</a>`;

  nav.innerHTML = `
    <div class="navbar-inner">
      <a href="index.html" class="brand" aria-label="Hotel Lazzy-Kitchen home">
        <span class="brand-mark">🍽️</span>
        <span class="brand-text">Lazzy-Kitchen<small>Hotel · Coimbatore</small></span>
      </a>
      <button class="hamburger" id="hamburger" aria-label="Toggle navigation" aria-expanded="false"><span></span><span></span><span></span></button>
      <div class="nav-links" id="navLinks">
        ${link("index.html", "home", "Home")}
        ${link("menu.html", "menu", "Menu")}
        ${link("myorders.html", "orders", "My Orders")}
        ${withCart ? `<button class="nav-btn cart-badge nav-cart" id="cartOpenBtn">🛒 Cart <span class="count" id="cartCount">0</span></button>` : ""}
        ${customer ? `<div class="nav-user"><span class="nav-hello">Hi, ${esc(customer.full_name.split(" ")[0])}</span><button class="nav-logout" id="logoutBtn">Logout</button></div>` : ""}
      </div>
    </div>`;

  const burger = nav.querySelector("#hamburger");
  const links = nav.querySelector("#navLinks");
  burger.addEventListener("click", () => {
    const open = links.classList.toggle("open");
    burger.classList.toggle("open", open);
    burger.setAttribute("aria-expanded", String(open));
  });
  const lo = nav.querySelector("#logoutBtn");
  if (lo) lo.addEventListener("click", logout);
  if (typeof updateCartBadge === "function") updateCartBadge();
  if (withCart && typeof bindCartOpeners === "function") bindCartOpeners();
}

/* ---------------------------------------------------------------------
   Food imagery: local photo on top of a category-themed fallback tile,
   so a missing/slow image never shows a broken-image icon.
   --------------------------------------------------------------------- */
const GROUP_EMOJI = {
  "South Indian": "🥞", "Rice & Main Course": "🍛", Tea: "🍵", Coffee: "☕", Donuts: "🍩",
  Pizza: "🍕", Burger: "🍔", Shawarma: "🌯", "Additional Snacks": "🍟",
};
function foodImage(item, { lazy = true } = {}) {
  const emoji = GROUP_EMOJI[item.category] || "🍽️";
  const fallback = `<div class="img-fallback"><div>${emoji}</div><span>${esc(item.name)}</span></div>`;
  if (!item.image_path) return fallback;
  return `${fallback}<img src="${esc(item.image_path)}" alt="${esc(item.name)}" width="800" height="600"
    ${lazy ? 'loading="lazy"' : ""} decoding="async" onload="this.classList.add('loaded')" onerror="this.remove()">`;
}

/* ---------------------------------------------------------------------
   Order progress tracker
   Order Placed → Confirmed → Preparing → Ready to Serve → Served
   --------------------------------------------------------------------- */
const TRACK_STEPS = [
  { key: "PLACED", label: "Order Placed", icon: "📝" },
  { key: "CONFIRMED", label: "Confirmed", icon: "✅" },
  { key: "PREPARING", label: "Preparing", icon: "👨‍🍳" },
  { key: "READY", label: "Ready to Serve", icon: "🛎️" },
  { key: "SERVED", label: "Served", icon: "🍽️" },
];
function trackerHtml(status) {
  if (status === "CANCELLED") return `<div class="cancel-banner">This order was cancelled.</div>`;
  const idx = Math.max(0, TRACK_STEPS.findIndex((s) => s.key === status));
  const finished = status === "SERVED";
  const fill = (idx / (TRACK_STEPS.length - 1)) * 80;
  return `<div class="tracker" role="list" aria-label="Order progress">
    <div class="fill" style="width:${fill}%"></div>
    ${TRACK_STEPS.map((s, i) => {
      const cls = i < idx || (finished && i === idx) ? "done" : i === idx ? "current" : "";
      return `<div class="t-step ${cls}" role="listitem"><div class="t-dot">${cls === "done" ? "✓" : s.icon}</div>${s.label}</div>`;
    }).join("")}
  </div>`;
}
function paymentBadge(order) {
  return order.payment_status === "PAID"
    ? `<span class="badge paid">PAID</span>`
    : `<span class="badge pending">PENDING_CASH</span>`;
}
function statusBadge(status) {
  return `<span class="badge ${status === "CANCELLED" ? "cancelled" : "status"}">${esc(status)}</span>`;
}

/* ---------------------------------------------------------------------
   Validation helpers (mirror backend rules — backend is source of truth)
   --------------------------------------------------------------------- */
const Validate = {
  mobile: (v) => /^[6-9]\d{9}$/.test(v.trim()),
  email: (v) => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v.trim()),
  password: (v) => v.length >= 6 && /[A-Za-z]/.test(v) && /\d/.test(v),
};
function setFieldError(formId, field, message) {
  const el = document.querySelector(`#${formId} [data-err="${field}"]`);
  if (el) el.textContent = message || "";
  const input = document.querySelector(`#${formId} [name="${field}"]`);
  if (input) input.classList.toggle("invalid", !!message);
}
function setBusy(btn, busy, label) {
  if (!btn) return;
  btn.disabled = busy;
  if (busy) { btn.dataset.label = btn.innerHTML; btn.innerHTML = `<span class="spin"></span> ${label || "Please wait..."}`; }
  else if (btn.dataset.label) { btn.innerHTML = btn.dataset.label; }
}

/* ---------------------------------------------------------------------
   Home page: login / register tabs
   --------------------------------------------------------------------- */
function populateTableOptions() {
  const select = document.querySelector("#registerForm [name=table_number]");
  if (!select || select.options.length > 1) return;
  for (let i = 1; i <= 20; i++) {
    const value = String(i).padStart(2, "0");
    select.add(new Option(`Table ${value}`, value));
  }
}

function switchAuthTab(which) {
  document.querySelectorAll(".auth-tab").forEach((t) => {
    const on = t.dataset.tab === which;
    t.classList.toggle("active", on);
    t.setAttribute("aria-selected", String(on));
  });
  document.querySelectorAll(".auth-panel").forEach((p) => { p.hidden = p.dataset.panel !== which; });
}

function initAuthPage() {
  if (!document.querySelector("#authCard")) return;
  populateTableOptions();

  document.querySelectorAll(".auth-tab").forEach((t) => t.addEventListener("click", () => switchAuthTab(t.dataset.tab)));
  document.querySelectorAll("[data-pw-toggle]").forEach((btn) => btn.addEventListener("click", () => {
    const input = btn.previousElementSibling;
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    btn.textContent = show ? "Hide" : "Show";
  }));

  // Already logged in? Offer to continue instead of showing the forms.
  apiRequest("/me").then((r) => {
    if (!r.ok) return;
    Session.save(r.data.customer);
    renderNav();
    document.querySelector("#authForms").hidden = true;
    const w = document.querySelector("#welcomeBack");
    w.hidden = false;
    w.querySelector("[data-name]").textContent = r.data.customer.full_name;
  });
  const lo = document.querySelector("#welcomeLogout");
  if (lo) lo.addEventListener("click", logout);

  /* ---- Login ---- */
  const loginForm = document.querySelector("#loginForm");
  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const identifier = loginForm.elements.identifier.value.trim();
    const password = loginForm.elements.password.value;
    setFieldError("loginForm", "identifier", ""); setFieldError("loginForm", "password", "");
    let ok = true;
    if (!identifier || !(Validate.email(identifier) || /^\d{10}$/.test(identifier))) {
      setFieldError("loginForm", "identifier", "Enter your registered email or 10-digit mobile number."); ok = false;
    }
    if (!password) { setFieldError("loginForm", "password", "Enter your password."); ok = false; }
    if (!ok) return;

    const btn = loginForm.querySelector("button[type=submit]");
    setBusy(btn, true, "Signing in...");
    const result = await apiRequest("/login", { method: "POST", body: JSON.stringify({ identifier, password }) });
    setBusy(btn, false);
    if (!result.ok) { showToast(result.message, "error"); return; }

    Session.save(result.data.customer);
    showToast(`Welcome back, ${result.data.customer.full_name.split(" ")[0]}!`);
    setTimeout(() => { window.location.href = "menu.html"; }, 600);
  });

  /* ---- Register ---- */
  const form = document.querySelector("#registerForm");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const v = Object.fromEntries(new FormData(form).entries());
    const fullName = (v.full_name || "").trim();
    ["full_name", "mobile", "email", "table_number", "password", "confirm_password"].forEach((f) => setFieldError("registerForm", f, ""));

    let valid = true;
    const bad = (f, m) => { setFieldError("registerForm", f, m); valid = false; };
    if (!fullName) bad("full_name", "Name cannot be empty.");
    if (!Validate.mobile(v.mobile || "")) bad("mobile", "Enter a valid 10-digit mobile number.");
    if (!Validate.email(v.email || "")) bad("email", "Enter a valid email address.");
    if (!v.table_number) bad("table_number", "Please select a table number.");
    if (!Validate.password(v.password || "")) bad("password", "Min 6 chars, with a letter and a number.");
    if (v.password !== v.confirm_password) bad("confirm_password", "Passwords do not match.");
    if (!valid) return;

    const btn = form.querySelector("button[type=submit]");
    setBusy(btn, true, "Creating account...");
    const result = await apiRequest("/register", {
      method: "POST",
      body: JSON.stringify({ full_name: fullName, mobile: v.mobile.trim(), email: v.email.trim(), table_number: v.table_number, password: v.password, confirm_password: v.confirm_password }),
    });
    setBusy(btn, false);

    if (!result.ok) {
      showToast(result.message, "error");
      if (result.status === 409) {   // existing customer -> guide them to log in, don't create a duplicate
        const dupEmail = /email/i.test(result.message);
        setFieldError("registerForm", dupEmail ? "email" : "mobile", "Already registered — please log in.");
        loginForm.elements.identifier.value = dupEmail ? v.email.trim() : v.mobile.trim();
        switchAuthTab("login");
        loginForm.elements.password.focus();
      }
      return;
    }
    Session.save(result.data.customer);
    showToast("Account created. Welcome to Lazzy-Kitchen!");
    setTimeout(() => { window.location.href = "menu.html"; }, 700);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  renderNav();
  initAuthPage();
});
