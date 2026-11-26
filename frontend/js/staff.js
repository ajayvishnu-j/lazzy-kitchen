/* Staff board: move orders through PLACED → CONFIRMED → PREPARING → READY → SERVED.
   Requires STAFF_API_KEY on the server. The key is kept in sessionStorage only. */
const NEXT = { PLACED: ["CONFIRMED", "Confirm"], CONFIRMED: ["PREPARING", "Start Preparing"], PREPARING: ["READY", "Mark Ready"], READY: ["SERVED", "Mark Served"] };
let staffTimer = null;

const headers = () => ({ "X-Staff-Key": sessionStorage.getItem("lazzy_staff_key") || "" });

async function loadStaff() {
  const scope = document.querySelector("#scope").value;
  const res = await apiRequest(`/staff/orders?scope=${scope}`, { headers: headers() });
  const el = document.querySelector("#staffList");
  if (!res.ok) { el.innerHTML = `<div class="state-message">${esc(res.message)}</div>`; clearInterval(staffTimer); return; }
  const orders = res.data.orders;
  el.innerHTML = orders.length ? orders.map((o) => `
    <article class="order-card">
      <div class="order-card-head"><strong>${esc(o.order_number)} · Table ${esc(o.table_number)}</strong><span>${statusBadge(o.status)} ${paymentBadge(o)}</span></div>
      <div class="order-meta">${esc(o.customer_name)} · ${esc(fmtDateTime(o.created_at))} · ${esc(o.payment_method_label)} · est ${o.est_prep_min_minutes}–${o.est_prep_max_minutes} min</div>
      ${o.items.map((i) => `<div class="order-line"><span>${esc(i.item_name)} × ${i.quantity}</span><span>${inr(i.total_price)}</span></div>`).join("")}
      <div class="order-line total"><span>Total</span><span>${inr(o.total)}</span></div>
      <div class="staff-actions">
        ${NEXT[o.status] ? `<button class="btn btn-primary btn-sm" data-n="${esc(o.order_number)}" data-status="${NEXT[o.status][0]}">${NEXT[o.status][1]}</button>` : ""}
        ${o.payment_method === "CASH" && o.payment_status === "PENDING_CASH" && o.status !== "CANCELLED" ? `<button class="btn btn-gold btn-sm" data-n="${esc(o.order_number)}" data-pay="1">Cash Received</button>` : ""}
        ${["PLACED", "CONFIRMED", "PREPARING", "READY"].includes(o.status) ? `<button class="btn btn-danger btn-sm" data-n="${esc(o.order_number)}" data-status="CANCELLED">Cancel</button>` : ""}
      </div>
    </article>`).join("") : `<div class="state-message">No orders.</div>`;
}

document.addEventListener("DOMContentLoaded", () => {
  const input = document.querySelector("#staffKey");
  input.value = sessionStorage.getItem("lazzy_staff_key") || "";
  const start = () => { sessionStorage.setItem("lazzy_staff_key", input.value.trim()); loadStaff(); clearInterval(staffTimer); staffTimer = setInterval(loadStaff, 10000); };
  document.querySelector("#staffGo").addEventListener("click", start);
  document.querySelector("#scope").addEventListener("change", loadStaff);
  document.querySelector("#staffList").addEventListener("click", async (e) => {
    const b = e.target.closest("button[data-n]");
    if (!b) return;
    const path = b.dataset.pay ? `/staff/orders/${b.dataset.n}/payment` : `/staff/orders/${b.dataset.n}/status`;
    const r = await apiRequest(path, { method: "PATCH", headers: headers(), body: JSON.stringify(b.dataset.pay ? {} : { status: b.dataset.status }) });
    showToast(r.ok ? "Updated" : r.message, r.ok ? "success" : "error");
    loadStaff();
  });
  if (input.value) start();
});
