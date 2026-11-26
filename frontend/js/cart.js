/* =====================================================================
   Hotel Lazzy-Kitchen — Cart module
   The cart lives in sessionStorage so it survives switching between the
   FOOD and SNACKS & BEVERAGES tabs and navigating to the payment page.
   Prices shown here are for display only: the Python backend re-prices the
   cart (/api/cart/validate and /api/orders) and is the source of truth.
   ===================================================================== */

const CART_KEY = "lazzy_cart";
const TAX_KEY = "lazzy_tax";
const MAX_QTY = 20;

const Cart = {
  get() {
    try { return JSON.parse(sessionStorage.getItem(CART_KEY)) || []; } catch { return []; }
  },
  save(items, silent = false) {
    sessionStorage.setItem(CART_KEY, JSON.stringify(items));
    if (!silent) Cart.changed();
  },
  changed() {
    updateCartBadge();
    renderCartDrawer();
    document.dispatchEvent(new CustomEvent("cart:changed"));
  },
  qty(menuItemId) {
    const line = Cart.get().find((i) => i.menu_item_id === menuItemId);
    return line ? line.quantity : 0;
  },
  add(menuItem, quantity = 1) {
    if (!menuItem.is_available) return false;
    const items = Cart.get();
    const existing = items.find((i) => i.menu_item_id === menuItem.id);
    if (existing) {
      existing.quantity = Math.min(existing.quantity + quantity, MAX_QTY);
    } else {
      items.push({
        menu_item_id: menuItem.id, name: menuItem.name, unit_price: menuItem.price,
        image_path: menuItem.image_path, category: menuItem.category, available: true,
        prep_time_min: menuItem.prep_time_min, prep_time_max: menuItem.prep_time_max,
        quantity: Math.min(quantity, MAX_QTY),
      });
    }
    Cart.save(items);
    return true;
  },
  change(menuItemId, delta) {
    let items = Cart.get();
    const line = items.find((i) => i.menu_item_id === menuItemId);
    if (!line) return;
    line.quantity = Math.min(line.quantity + delta, MAX_QTY);
    if (line.quantity <= 0) items = items.filter((i) => i.menu_item_id !== menuItemId);
    Cart.save(items);
  },
  remove(menuItemId) {
    Cart.save(Cart.get().filter((i) => i.menu_item_id !== menuItemId));
  },
  clear(silent = false) {
    Cart.save([], silent);
  },
  count() {
    return Cart.get().reduce((s, i) => s + i.quantity, 0);
  },
  taxPercent() {
    const v = parseFloat(sessionStorage.getItem(TAX_KEY));
    return Number.isFinite(v) ? v : 5;
  },
  setTaxPercent(v) {
    if (Number.isFinite(v)) sessionStorage.setItem(TAX_KEY, String(v));
  },
  hasUnavailable() {
    return Cart.get().some((i) => i.available === false);
  },
  /** Display totals (available items only). Backend recomputes the real ones. */
  totals() {
    const items = Cart.get().filter((i) => i.available !== false);
    const cents = items.reduce((s, i) => s + Math.round(i.unit_price * 100) * i.quantity, 0);
    const taxCents = Math.round((cents * Cart.taxPercent()) / 100);
    return { subtotal: cents / 100, tax: taxCents / 100, total: (cents + taxCents) / 100 };
  },
  /** Refresh display snapshots from the live menu list (menu page). */
  reconcile(menuItems) {
    const byId = new Map(menuItems.map((m) => [m.id, m]));
    const items = Cart.get().filter((i) => byId.has(i.menu_item_id)).map((i) => {
      const m = byId.get(i.menu_item_id);
      return { ...i, name: m.name, unit_price: m.price, image_path: m.image_path, category: m.category, available: m.is_available };
    });
    Cart.save(items, true);
    Cart.changed();
  },
  /** Ask the server for authoritative prices / availability of what is in the cart. */
  async syncWithServer() {
    const items = Cart.get();
    if (!items.length) return null;
    const res = await apiRequest("/cart/validate", {
      method: "POST",
      body: JSON.stringify({ items: items.map((i) => ({ menu_item_id: i.menu_item_id, quantity: i.quantity })) }),
    });
    if (!res.ok) return res;
    const byId = new Map(res.data.items.map((l) => [l.menu_item_id, l]));
    const merged = Cart.get().map((i) => {
      const l = byId.get(i.menu_item_id);
      return l ? { ...i, name: l.item_name, unit_price: l.unit_price, available: l.available } : i;
    });
    Cart.setTaxPercent(res.data.tax_percent);
    Cart.save(merged, true);
    Cart.changed();
    return res;
  },
};

/* ---------------------------------------------------------------------
   Badge + floating bar
   --------------------------------------------------------------------- */
function updateCartBadge() {
  const count = Cart.count();
  const badge = document.querySelector("#cartCount");
  if (badge) badge.textContent = count;

  const fab = document.querySelector("#cartFab");
  if (fab) {
    fab.classList.toggle("show", count > 0);
    const t = Cart.totals();
    fab.innerHTML = `<span>🛒 <b>${count}</b> item${count === 1 ? "" : "s"}</span><span>${inr(t.total)} · View Cart →</span>`;
  }
}
function bumpCartBadge() {
  const el = document.querySelector("#cartOpenBtn");
  if (!el) return;
  el.classList.remove("bump"); void el.offsetWidth; el.classList.add("bump");
}

/* ---------------------------------------------------------------------
   Drawer
   --------------------------------------------------------------------- */
function cartLineHtml(item) {
  const unavailable = item.available === false;
  const thumb = `<div class="cart-thumb">${GROUP_EMOJI[item.category] || "🍽️"}${
    item.image_path ? `<img src="${esc(item.image_path)}" alt="" loading="lazy" onerror="this.remove()">` : ""}</div>`;
  return `
    <div class="cart-line ${unavailable ? "is-unavailable" : ""}">
      ${thumb}
      <div>
        <h4>${esc(item.name)}</h4>
        <div class="unit-price">${inr(item.unit_price)} each</div>
        ${unavailable ? `<div class="unavail-note">Currently unavailable — remove to continue</div>` : ""}
        <div class="mini-stepper">
          <button data-action="dec" data-id="${item.menu_item_id}" aria-label="Decrease quantity of ${esc(item.name)}">−</button>
          <span>${item.quantity}</span>
          <button data-action="inc" data-id="${item.menu_item_id}" aria-label="Increase quantity of ${esc(item.name)}" ${unavailable || item.quantity >= MAX_QTY ? "disabled" : ""}>+</button>
        </div>
      </div>
      <div class="cart-line-right">
        <div class="cart-line-total">${unavailable ? "—" : inr(item.unit_price * item.quantity)}</div>
        <button class="cart-line-remove" data-action="remove" data-id="${item.menu_item_id}">Remove</button>
      </div>
    </div>`;
}

function renderCartDrawer() {
  const list = document.querySelector("#cartItemsList");
  const summary = document.querySelector("#cartSummary");
  const sub = document.querySelector("#cartSubtitle");
  if (!list) return;

  const items = Cart.get();
  const count = Cart.count();
  if (sub) sub.textContent = count ? `${count} item${count === 1 ? "" : "s"} selected` : "No items yet";

  list.innerHTML = items.length
    ? items.map(cartLineHtml).join("")
    : `<div class="cart-empty"><div class="big">🛒</div>Your cart is empty.<br>Add something delicious from the menu!</div>`;

  if (!summary) return;
  const t = Cart.totals();
  const blocked = Cart.hasUnavailable();
  summary.innerHTML = items.length ? `
    ${blocked ? `<div class="demo-banner danger">Some items are unavailable. Remove them to proceed.</div>` : ""}
    <div class="summary-count">${count} item${count === 1 ? "" : "s"} · ${items.length} dish${items.length === 1 ? "" : "es"}</div>
    <div class="summary-row"><span>Subtotal</span><span>${inr(t.subtotal)}</span></div>
    <div class="summary-row"><span>Tax (${Cart.taxPercent()}%)</span><span>${inr(t.tax)}</span></div>
    <div class="summary-row total"><span>Grand Total</span><span>${inr(t.total)}</span></div>
    <button class="btn btn-gold btn-block" id="checkoutBtn" style="margin-top:14px" ${blocked ? "disabled" : ""}>Proceed to Payment →</button>
    <button class="btn btn-secondary btn-block btn-sm" id="clearCartBtn" style="margin-top:10px">Clear Cart</button>` : "";
}

function openCart() {
  document.querySelector("#cartDrawer")?.classList.add("open");
  document.querySelector("#cartOverlay")?.classList.add("open");
  Cart.syncWithServer();   // refresh prices / availability while the drawer is open
}
function closeCart() {
  document.querySelector("#cartDrawer")?.classList.remove("open");
  document.querySelector("#cartOverlay")?.classList.remove("open");
}
function bindCartOpeners() {
  document.querySelector("#cartOpenBtn")?.addEventListener("click", openCart);
}

function initCartDrawer() {
  const drawer = document.querySelector("#cartDrawer");
  if (!drawer) return;

  document.querySelector("#cartCloseBtn")?.addEventListener("click", closeCart);
  document.querySelector("#cartOverlay")?.addEventListener("click", closeCart);
  document.querySelector("#cartFab")?.addEventListener("click", openCart);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeCart(); });

  drawer.addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    const id = Number(btn.dataset.id);
    if (btn.dataset.action === "inc") Cart.change(id, 1);
    else if (btn.dataset.action === "dec") Cart.change(id, -1);
    else if (btn.dataset.action === "remove") Cart.remove(id);
    else if (btn.id === "clearCartBtn") Cart.clear();
    else if (btn.id === "checkoutBtn" && Cart.count() > 0 && !Cart.hasUnavailable()) window.location.href = "payment.html";
  });

  updateCartBadge();
  renderCartDrawer();
}

document.addEventListener("DOMContentLoaded", initCartDrawer);
