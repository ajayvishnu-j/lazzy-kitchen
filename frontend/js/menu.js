/* =====================================================================
   Hotel Lazzy-Kitchen — Menu page logic
   Two main categories (FOOD / SNACKS & BEVERAGES) switch client-side, so
   the cart is never lost. Prices/availability come from MySQL via the API.
   ===================================================================== */

const MAIN_TABS = [
  { key: "FOOD", hash: "food", label: "🍛 FOOD" },
  { key: "SNACKS_BEVERAGES", hash: "snacks", label: "☕ SNACKS & BEVERAGES" },
];

const MenuState = { items: [], main: "FOOD", group: "ALL", open: true };

function mainFromHash() {
  const h = window.location.hash.replace("#", "").toLowerCase();
  const found = MAIN_TABS.find((t) => t.hash === h);
  if (found) return found.key;
  return sessionStorage.getItem("lazzy_main") || "FOOD";
}

async function loadMenu() {
  const grid = document.querySelector("#menuGrid");
  grid.innerHTML = Array.from({ length: 8 }).map(() => `<div class="skeleton skeleton-card"></div>`).join("");

  const result = await apiRequest("/menu");
  if (!result.ok) {
    grid.innerHTML = `<div class="state-message">Unable to load the menu.<br>${esc(result.message)}<br><button class="btn btn-primary" id="retryMenu">Try again</button></div>`;
    document.querySelector("#retryMenu")?.addEventListener("click", loadMenu);
    return;
  }

  MenuState.items = result.data.items;
  const status = result.data.restaurant_status;
  if (status) {
    Cart.setTaxPercent(status.tax_percent);
    MenuState.open = status.is_open;
    renderRestaurantStatus(status);
  }
  Cart.reconcile(MenuState.items);   // refresh prices/availability of items already in the cart

  MenuState.main = mainFromHash();
  renderMainTabs();
  renderGroupChips();
  renderGrid();
}

function renderRestaurantStatus(status) {
  const el = document.querySelector("#restaurantStatus");
  if (el) {
    el.innerHTML = status.is_open
      ? `<span class="status-pill">🟢 Kitchen Open · Dine-in only</span>`
      : `<span class="status-pill closed">🔴 Kitchen Closed</span>`;
  }
  const banner = document.querySelector("#closedBanner");
  if (banner) banner.hidden = status.is_open;
}

function itemsOfMain() {
  return MenuState.items.filter((i) => i.main_category === MenuState.main);
}
function groupsOfMain() {
  return [...new Set(itemsOfMain().map((i) => i.category))];
}

function renderMainTabs() {
  const wrap = document.querySelector("#mainTabs");
  wrap.innerHTML = MAIN_TABS.map((t) => {
    const n = MenuState.items.filter((i) => i.main_category === t.key).length;
    return `<button class="main-tab ${t.key === MenuState.main ? "active" : ""}" data-main="${t.key}" role="tab" aria-selected="${t.key === MenuState.main}">${t.label}<span class="n">${n}</span></button>`;
  }).join("");
}

function renderGroupChips() {
  const wrap = document.querySelector("#groupChips");
  const groups = groupsOfMain();
  wrap.innerHTML = ["ALL", ...groups].map((g) =>
    `<button class="chip ${g === MenuState.group ? "active" : ""}" data-group="${esc(g)}">${g === "ALL" ? "All" : esc(g)}</button>`).join("");
}

function actionHtml(item) {
  if (!item.is_available || !MenuState.open) {
    return `<button class="add-btn" disabled>${item.is_available ? "Kitchen Closed" : "Unavailable"}</button>`;
  }
  const q = Cart.qty(item.id);
  return q > 0
    ? `<div class="stepper">
         <button data-act="dec" aria-label="Remove one ${esc(item.name)}">−</button>
         <span class="q" aria-live="polite">${q}</span>
         <button data-act="inc" aria-label="Add one more ${esc(item.name)}" ${q >= MAX_QTY ? "disabled" : ""}>+</button>
       </div>`
    : `<button class="add-btn" data-act="add">Add to Cart</button>`;
}

function cardHtml(item, i) {
  return `
    <article class="food-card ${item.is_available ? "" : "is-unavailable"}" data-id="${item.id}" style="animation-delay:${Math.min(i, 12) * 35}ms">
      <div class="img-wrap">
        ${foodImage(item)}
        <span class="veg-badge ${item.is_vegetarian ? "" : "nonveg"}" title="${item.is_vegetarian ? "Vegetarian" : "Non-vegetarian"}"></span>
        ${item.flavour ? `<span class="flavour-tag">${esc(item.flavour)}</span>` : ""}
        ${item.is_available ? "" : `<div class="unavailable-overlay">Currently Unavailable</div>`}
      </div>
      <div class="food-card-body">
        <h3>${esc(item.name)}</h3>
        <p>${esc(item.description)}</p>
        <div class="food-meta">
          <span class="food-price">${inr(item.price)}</span>
          <span class="prep-chip">⏱ ${item.prep_time_min}–${item.prep_time_max} min</span>
        </div>
        <div class="card-action">${actionHtml(item)}</div>
      </div>
    </article>`;
}

function renderGrid() {
  const root = document.querySelector("#menuGrid");
  let items = itemsOfMain();
  if (MenuState.group !== "ALL") items = items.filter((i) => i.category === MenuState.group);
  if (!items.length) { root.innerHTML = `<div class="state-message">No items in this category yet.</div>`; return; }

  const groups = [...new Set(items.map((i) => i.category))];
  let counter = 0;
  root.innerHTML = groups.map((g) => {
    const list = items.filter((i) => i.category === g);
    return `<section class="group-section" id="grp-${esc(g.replace(/\W+/g, "-").toLowerCase())}">
      <h2 class="group-title">${esc(g)} <small>${list.length} item${list.length === 1 ? "" : "s"}</small></h2>
      <div class="menu-grid">${list.map((it) => cardHtml(it, counter++)).join("")}</div>
    </section>`;
  }).join("");
}

function refreshCardActions() {
  document.querySelectorAll(".food-card").forEach((card) => {
    const item = MenuState.items.find((i) => i.id === Number(card.dataset.id));
    if (item) card.querySelector(".card-action").innerHTML = actionHtml(item);
  });
}

function initMenuEvents() {
  document.querySelector("#mainTabs").addEventListener("click", (e) => {
    const btn = e.target.closest(".main-tab");
    if (!btn || btn.dataset.main === MenuState.main) return;
    MenuState.main = btn.dataset.main;
    MenuState.group = "ALL";
    sessionStorage.setItem("lazzy_main", MenuState.main);
    history.replaceState(null, "", "#" + MAIN_TABS.find((t) => t.key === MenuState.main).hash);
    renderMainTabs(); renderGroupChips(); renderGrid();
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  document.querySelector("#groupChips").addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    MenuState.group = chip.dataset.group;
    renderGroupChips(); renderGrid();
  });

  document.querySelector("#menuGrid").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-act]");
    const card = e.target.closest(".food-card");
    if (!btn || !card) return;
    const item = MenuState.items.find((i) => i.id === Number(card.dataset.id));
    if (!item) return;
    if (!MenuState.open) { showToast("The kitchen is closed right now.", "error"); return; }

    if (btn.dataset.act === "add") {
      if (Cart.add(item, 1)) { showToast(`${item.name} added to cart`); bumpCartBadge(); }
    } else if (btn.dataset.act === "inc") Cart.change(item.id, 1);
    else if (btn.dataset.act === "dec") Cart.change(item.id, -1);
  });

  // Keep every card's button/stepper in sync with the cart (drawer, other tab, etc.)
  document.addEventListener("cart:changed", refreshCardActions);
  window.addEventListener("hashchange", () => {
    const next = mainFromHash();
    if (next !== MenuState.main && MenuState.items.length) {
      MenuState.main = next; MenuState.group = "ALL";
      renderMainTabs(); renderGroupChips(); renderGrid();
    }
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  if (!document.querySelector("#menuGrid")) return;
  const customer = await ensureAuth();
  if (!customer) return;
  initMenuEvents();
  loadMenu();
});
