/* =====================================================================
   Hotel Lazzy-Kitchen — Payment & order confirmation
   DEMO ONLY. No real gateway, UPI or card processing. Card details are
   sent over the API for comparison with fixed test values and are never
   stored. The demo QR is a decorative picture: it encodes nothing.
   ===================================================================== */

const Pay = {
  customer: null, summary: null, method: "DEMO_CARD", busy: false,
  qrRun: 0, qrTimer: null, qrToken: null,
};

/* ---- idempotency key: one per distinct cart, reused on retries ---- */
function cartSignature() {
  return Cart.get().map((i) => `${i.menu_item_id}x${i.quantity}`).sort().join(",");
}
function checkoutKey() {
  const sig = cartSignature();
  let saved = null;
  try { saved = JSON.parse(sessionStorage.getItem("lazzy_checkout")); } catch { /* ignore */ }
  if (saved && saved.sig === sig) return saved.key;
  const key = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(16).slice(2));
  sessionStorage.setItem("lazzy_checkout", JSON.stringify({ sig, key }));
  return key;
}

/* ---- summary ---- */
function renderSummary() {
  const s = Pay.summary;
  const tables = Array.from({ length: 20 }, (_, i) => String(i + 1).padStart(2, "0"));
  const current = Pay.customer.table_number;
  if (!tables.includes(current)) tables.unshift(current);

  document.querySelector("#orderSummary").innerHTML = `
    <div class="info-grid">
      <div><label>Customer</label>${esc(Pay.customer.full_name)}</div>
      <div><label>Table</label>
        <select id="tableSelect" aria-label="Table number">${tables.map((t) => `<option ${t === current ? "selected" : ""}>${esc(t)}</option>`).join("")}</select>
      </div>
    </div>
    ${s.items.map((l) => `
      <div class="order-line ${l.available ? "" : "unavail"}">
        <span>${esc(l.item_name)} × ${l.quantity}<span class="sub">${inr(l.unit_price)} each${l.available ? "" : " — unavailable"}</span></span>
        <span>${l.available ? inr(l.total_price) : "—"}</span>
      </div>`).join("")}
    <div class="order-line"><span>Subtotal</span><span>${inr(s.subtotal)}</span></div>
    <div class="order-line"><span>Tax (${s.tax_percent}%)</span><span>${inr(s.tax)}</span></div>
    <div class="order-line total"><span>Grand Total</span><span>${inr(s.total)}</span></div>
    <p class="qr-label" style="margin-top:12px">⏱ Estimated preparation: ${s.est_prep_min_minutes}–${s.est_prep_max_minutes} minutes (estimate)</p>`;
}

/* ---- method switching ---- */
function selectMethod(method) {
  if (Pay.busy) return;
  if (Pay.method === "DEMO_QR" && method !== "DEMO_QR") cancelQr();
  Pay.method = method;
  document.querySelectorAll(".pay-method").forEach((b) => {
    const on = b.dataset.method === method;
    b.classList.toggle("active", on);
    b.setAttribute("aria-pressed", String(on));
  });
  document.querySelectorAll(".pay-panel").forEach((p) => { p.hidden = p.dataset.panel !== method; });
  if (method === "DEMO_QR") startQr();
}

/* ---- decorative demo QR (NOT a valid QR code; encodes nothing) ---- */
function demoQrSvg() {
  const N = 25, cell = 8; let seed = 7;
  const rnd = () => ((seed = (seed * 9301 + 49297) % 233280) / 233280);
  const finder = (x, y) => (x < 8 && y < 8) || (x > N - 9 && y < 8) || (x < 8 && y > N - 9);
  let rects = "";
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    if (finder(x, y)) continue;
    if (rnd() > 0.52) rects += `<rect x="${x * cell}" y="${y * cell}" width="${cell}" height="${cell}" rx="1.5"/>`;
  }
  const eye = (x, y) => `<g transform="translate(${x * cell},${y * cell})"><rect width="56" height="56" rx="6" fill="#12362a"/><rect x="8" y="8" width="40" height="40" rx="4" fill="#fff"/><rect x="16" y="16" width="24" height="24" rx="3" fill="#d9a21b"/></g>`;
  return `<svg viewBox="0 0 ${N * cell} ${N * cell}" role="img" aria-label="Demonstration QR picture (not a real code)">
    <g fill="#12362a">${rects}</g>${eye(0, 0)}${eye(N - 7, 0)}${eye(0, N - 7)}</svg>`;
}

function cancelQr() {
  Pay.qrRun++;
  clearInterval(Pay.qrTimer);
  Pay.qrTimer = null; Pay.qrToken = null;
}

async function startQr() {
  cancelQr();
  const run = Pay.qrRun;
  const stage = document.querySelector("#qrStage");
  stage.className = "qr-stage";
  stage.innerHTML = `<div class="spinner"></div>`;

  const res = await apiRequest("/payments/demo-qr/start", {
    method: "POST",
    body: JSON.stringify({ items: Cart.get().map((i) => ({ menu_item_id: i.menu_item_id, quantity: i.quantity })) }),
  });
  if (run !== Pay.qrRun) return;                       // user switched option meanwhile
  if (!res.ok) {
    stage.innerHTML = `<div class="qr-error">${esc(res.message)}</div><button class="btn btn-secondary btn-sm" id="qrRetry">Try again</button>`;
    document.querySelector("#qrRetry").addEventListener("click", startQr);
    return;
  }

  const wait = res.data.wait_seconds;
  Pay.qrToken = res.data.token;
  stage.innerHTML = `
    <div class="qr-frame">${demoQrSvg()}<div class="demo-ribbon">DEMO</div></div>
    <div class="qr-amount">${inr(res.data.amount)}</div>
    <div class="qr-label">Demo Google Pay simulation · no real payment</div>
    <div class="qr-wait" role="status">
      <div class="ring"><svg viewBox="0 0 48 48"><circle class="bg" cx="24" cy="24" r="22"/><circle class="fg" id="qrRing" cx="24" cy="24" r="22"/></svg><div class="num" id="qrNum">${wait}</div></div>
      <span>Waiting for demo payment confirmation…</span>
    </div>
    <div class="qr-success"><span class="tick">✓</span> Demo Payment Successful</div>`;

  const end = Date.now() + wait * 1000 + 300;          // small pad: server clock started earlier than ours
  Pay.qrTimer = setInterval(() => {
    if (run !== Pay.qrRun) return clearInterval(Pay.qrTimer);
    const left = Math.max(0, Math.ceil((end - 300 - Date.now()) / 1000));
    const num = document.querySelector("#qrNum"), ring = document.querySelector("#qrRing");
    if (num) num.textContent = left;
    if (ring) ring.style.strokeDashoffset = String(138.2 * (1 - left / wait));
    if (Date.now() >= end) {
      clearInterval(Pay.qrTimer); Pay.qrTimer = null;
      stage.classList.add("done");
      setTimeout(() => { if (run === Pay.qrRun) placeOrder("DEMO_QR", { demo_payment_token: Pay.qrToken }, null, startQr); }, 900);
    }
  }, 250);
}

/* ---- order placement (shared by the three methods) ---- */
async function placeOrder(method, extra = {}, button = null, onFail = null) {
  if (Pay.busy) return;                                // blocks double click / double submit
  Pay.busy = true;
  setBusy(button, true, "Placing order…");

  const payload = {
    payment_method: method,
    table_number: document.querySelector("#tableSelect")?.value || Pay.customer.table_number,
    items: Cart.get().map((i) => ({ menu_item_id: i.menu_item_id, quantity: i.quantity })),
    idempotency_key: checkoutKey(),
    ...extra,
  };
  const res = await apiRequest("/orders", { method: "POST", body: JSON.stringify(payload) });
  Pay.busy = false;
  setBusy(button, false);

  if (!res.ok) {
    if (res.status === 401) { window.location.href = "index.html"; return; }
    showToast(res.message, "error");
    const err = document.querySelector("#cardError");
    if (method === "DEMO_CARD" && err) err.textContent = res.message;
    if (method === "DEMO_QR") {
      document.querySelector("#qrStage").innerHTML =
        `<div class="qr-error">${esc(res.message)}</div><button class="btn btn-secondary btn-sm" id="qrRetry">Start again</button>`;
      document.querySelector("#qrRetry").addEventListener("click", () => onFail && onFail());
    }
    return;
  }
  sessionStorage.removeItem("lazzy_checkout");
  Cart.clear();
  showToast(res.data.duplicate ? "This order was already placed." : "Order placed successfully!");
  renderConfirmation(res.data.order);
}

/* ---- confirmation ---- */
let liveTimer = null, countTimer = null;

function renderConfirmation(order) {
  cancelQr();
  document.querySelector("#checkout").hidden = true;
  document.querySelector(".page-title").hidden = true;
  const root = document.querySelector("#confirmation");
  root.hidden = false;
  root.innerHTML = `
    <div class="confirm-card">
      <div class="confirm-head">
        <div class="tick">✓</div>
        <h2>${order.payment_status === "PAID" ? "Order Confirmed!" : "Order Placed!"}</h2>
        <p>Thank you for dining at <b>Hotel Lazzy-Kitchen</b></p>
        <div class="order-id-pill">${esc(order.order_number)}</div>
      </div>
      <div class="confirm-body">
        ${order.payment_status === "PENDING_CASH" ? `<div class="cash-reminder">💵 Pay Cash at the Restaurant Counter</div>` : ""}
        <div id="liveTracker"></div>
        <div id="prepBox"></div>
        <div class="detail-grid">
          <div class="detail"><label>Customer</label><div>${esc(order.customer_name)}</div></div>
          <div class="detail"><label>Table</label><div>${esc(order.table_number)}</div></div>
          <div class="detail"><label>Payment Method</label><div>${esc(order.payment_method_label)}</div></div>
          <div class="detail"><label>Payment Status</label><div>${paymentBadge(order)}</div></div>
          <div class="detail"><label>Order Status</label><div id="liveStatus">${statusBadge(order.status)}</div></div>
          <div class="detail"><label>Placed At</label><div>${esc(fmtDateTime(order.created_at))}</div></div>
        </div>
        <h3 style="margin-bottom:8px;color:var(--green-900)">Your Order</h3>
        ${order.items.map((i) => `<div class="order-line"><span>${esc(i.item_name)} × ${i.quantity}<span class="sub">${inr(i.unit_price)} each</span></span><span>${inr(i.total_price)}</span></div>`).join("")}
        <div class="order-line"><span>Subtotal</span><span>${inr(order.subtotal)}</span></div>
        <div class="order-line"><span>Tax</span><span>${inr(order.tax)}</span></div>
        <div class="order-line total"><span>Total Amount</span><span>${inr(order.total)}</span></div>
        <div class="confirm-actions">
          <a href="menu.html" class="btn btn-secondary">Order More</a>
          <a href="myorders.html" class="btn btn-primary">View My Orders</a>
        </div>
      </div>
    </div>`;
  window.scrollTo({ top: 0, behavior: "smooth" });
  renderLive(order);
  startLive(order);
}

function renderLive(o) {
  document.querySelector("#liveTracker").innerHTML = trackerHtml(o.status);
  const st = document.querySelector("#liveStatus");
  if (st) st.innerHTML = statusBadge(o.status);
  const box = document.querySelector("#prepBox");
  if (["SERVED", "CANCELLED"].includes(o.status)) { box.innerHTML = ""; return; }
  box.innerHTML = `
    <div class="prep-box">
      <div class="clock">⏱️</div>
      <div><b>Estimated preparation: ${o.est_prep_min_minutes}–${o.est_prep_max_minutes} minutes</b>
        <div class="est">This is only an estimate. Ready around ${esc(fmtClock(o.est_ready_at))}. Staff will update the status when your food is ready.</div></div>
      <div class="prep-count" id="prepCount"></div>
    </div>`;
  tickCountdown(o);
}

function tickCountdown(o) {
  const el = document.querySelector("#prepCount");
  if (!el) return;
  if (o.status === "READY") { el.innerHTML = `<small>Status</small>Ready!`; return; }
  const ms = new Date(o.est_ready_at) - Date.now();
  if (ms <= 0) { el.className = "prep-count late"; el.innerHTML = `Taking slightly longer than estimated`; return; }
  const m = Math.floor(ms / 60000), s = Math.floor((ms % 60000) / 1000);
  el.className = "prep-count";
  el.innerHTML = `<small>Est. time left</small>${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function startLive(order) {
  let current = order;
  clearInterval(countTimer); clearInterval(liveTimer);
  countTimer = setInterval(() => tickCountdown(current), 1000);
  liveTimer = setInterval(async () => {
    const r = await apiRequest(`/orders/${encodeURIComponent(order.order_number)}`);
    if (!r.ok) return;
    if (r.data.order.status !== current.status) { current = r.data.order; renderLive(current); }
    if (["SERVED", "CANCELLED"].includes(current.status)) { clearInterval(liveTimer); clearInterval(countTimer); }
  }, 8000);
}

/* ---- page init ---- */
function bindCardForm() {
  const form = document.querySelector("#cardForm");
  const num = form.elements.card_number;
  num.addEventListener("input", () => {
    const d = num.value.replace(/\D/g, "").slice(0, 16);
    num.value = d.replace(/(.{4})/g, "$1 ").trim();
  });
  document.querySelector("#fillDemo").addEventListener("click", () => {
    form.elements.card_number.value = "1234 4321 5678 8765"; form.elements.pin.value = "4321"; form.elements.cvv.value = "123";
  });
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const err = document.querySelector("#cardError");
    err.textContent = "";
    const card = form.elements.card_number.value.replace(/\D/g, "");
    if (card.length !== 16 || form.elements.pin.value.length !== 4 || form.elements.cvv.value.length !== 3) {
      err.textContent = "Enter the 16-digit card number, 4-digit PIN and 3-digit CVV.";
      return;
    }
    placeOrder("DEMO_CARD", { payment: { card_number: form.elements.card_number.value, pin: form.elements.pin.value, cvv: form.elements.cvv.value } },
      form.querySelector("button[type=submit]"));
  });
}

async function initPayment() {
  const customer = await ensureAuth();
  if (!customer) return;
  Pay.customer = customer;

  const empty = (html) => {
    document.querySelector("#checkout").hidden = true;
    const c = document.querySelector("#emptyState");
    c.hidden = false; c.innerHTML = html;
  };
  if (Cart.count() === 0) {
    return empty(`<div class="state-message">Your cart is empty.<br><a href="menu.html" class="btn btn-primary">Browse Menu</a></div>`);
  }

  const res = await Cart.syncWithServer();
  if (!res || !res.ok) {
    return empty(`<div class="state-message">${esc(res ? res.message : "Unable to validate your cart.")}<br><a href="menu.html" class="btn btn-primary">Back to Menu</a></div>`);
  }
  Pay.summary = res.data;
  renderSummary();

  if (!res.data.restaurant_open) {
    document.querySelector("#payBlock").innerHTML = `<div class="demo-banner danger">The kitchen is closed right now, so orders can't be placed.</div>`;
    return;
  }
  if (!res.data.valid) {
    document.querySelector("#payBlock").innerHTML = `<div class="demo-banner danger">Unavailable right now: <b>${res.data.unavailable_items.map(esc).join(", ")}</b>.<br>Please remove them from your cart to continue.</div>
      <a href="menu.html" class="btn btn-primary btn-block" style="margin-top:14px">Update Cart</a>`;
    return;
  }

  document.querySelectorAll("[data-total]").forEach((el) => { el.textContent = inr(res.data.total); });
  document.querySelectorAll(".pay-method").forEach((b) => b.addEventListener("click", () => selectMethod(b.dataset.method)));
  bindCardForm();
  document.querySelector("#cashConfirm").addEventListener("click", (e) => placeOrder("CASH", {}, e.currentTarget));
  selectMethod("DEMO_CARD");
}

window.addEventListener("pagehide", () => { cancelQr(); clearInterval(liveTimer); clearInterval(countTimer); });
document.addEventListener("DOMContentLoaded", () => { if (document.querySelector("#checkout")) initPayment(); });
