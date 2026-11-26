/* My Orders: history + live status tracker (polls while any order is active). */
let lastSig = "";
let pollTimer = null;

function orderCardHtml(o) {
  const active = !["SERVED", "CANCELLED"].includes(o.status);
  return `
  <article class="order-card">
    <div class="order-card-head"><strong>${esc(o.order_number)}</strong><span>${statusBadge(o.status)} ${paymentBadge(o)}</span></div>
    <div class="order-meta">Table ${esc(o.table_number)} · ${esc(fmtDateTime(o.created_at))} · ${esc(o.payment_method_label)}</div>
    ${trackerHtml(o.status)}
    ${active ? `<div class="demo-banner" style="margin-bottom:12px">⏱ Estimated preparation: ${o.est_prep_min_minutes}–${o.est_prep_max_minutes} min (estimate) · around ${esc(fmtClock(o.est_ready_at))}</div>` : ""}
    ${o.payment_status === "PENDING_CASH" && o.status !== "CANCELLED" ? `<div class="cash-reminder">💵 Pay cash at the restaurant counter</div>` : ""}
    ${o.items.map((i) => `<div class="order-line"><span>${esc(i.item_name)} × ${i.quantity}</span><span>${inr(i.total_price)}</span></div>`).join("")}
    <div class="order-line total"><span>Total</span><span>${inr(o.total)}</span></div>
  </article>`;
}

async function loadMyOrders(first) {
  const list = document.querySelector("#ordersList");
  if (first) list.innerHTML = `<div class="spinner"></div>`;
  const res = await apiRequest("/orders");
  if (!res.ok) {
    if (first) list.innerHTML = `<div class="state-message">Unable to load your orders.<br>${esc(res.message)}</div>`;
    return;
  }
  const orders = res.data.orders;
  const sig = JSON.stringify(orders.map((o) => [o.order_number, o.status, o.payment_status]));
  if (sig === lastSig) return;
  lastSig = sig;

  list.innerHTML = orders.length
    ? orders.map(orderCardHtml).join("")
    : `<div class="state-message">You haven't placed any orders yet.<br><a href="menu.html" class="btn btn-primary">Browse Menu</a></div>`;

  clearInterval(pollTimer);
  if (orders.some((o) => !["SERVED", "CANCELLED"].includes(o.status))) {
    pollTimer = setInterval(() => loadMyOrders(false), 10000);
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  if (!document.querySelector("#ordersList")) return;
  if (await ensureAuth()) loadMyOrders(true);
});
