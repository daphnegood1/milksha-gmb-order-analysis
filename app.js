const state = {
  stores: [],
  filtered: [],
};

const providerColors = {
  foodpanda: "var(--rose)",
  "Uber Eats": "var(--green)",
  "lin.ee": "var(--blue)",
};

function boolLabel(value) {
  if (value === true) return "有";
  if (value === false) return "無";
  return "待查核";
}

function tagClass(value) {
  if (value === true) return "confirmed";
  if (value === false) return "none";
  return "pending";
}

function providersText(providers) {
  return Array.isArray(providers) && providers.length ? providers.join("、") : "無";
}

function unique(values) {
  return [...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b, "zh-Hant"));
}

function confirmedStores() {
  return state.stores.filter((store) => store.gmb_status === "已人工確認");
}

function calculateStats() {
  const confirmed = confirmedStores();
  const providerCounts = new Map();

  for (const store of confirmed) {
    const providers = unique([...(store.takeout_providers || []), ...(store.delivery_providers || [])]);
    for (const provider of providers) {
      providerCounts.set(provider, (providerCounts.get(provider) || 0) + 1);
    }
  }

  return {
    total: state.stores.length,
    confirmed: confirmed.length,
    pending: state.stores.filter((store) => store.gmb_status !== "已人工確認").length,
    takeout: confirmed.filter((store) => store.has_takeout_order === true).length,
    delivery: confirmed.filter((store) => store.has_delivery_order === true).length,
    providerCounts,
  };
}

function renderMetric(id, value) {
  document.getElementById(id).textContent = value.toLocaleString("zh-Hant");
}

function renderBarChart(node, rows, maxValue) {
  node.innerHTML = "";
  if (!rows.length) {
    node.innerHTML = '<p class="small">尚無已確認資料</p>';
    return;
  }

  for (const row of rows) {
    const width = maxValue > 0 ? Math.max(2, (row.value / maxValue) * 100) : 0;
    const element = document.createElement("div");
    element.className = "bar-row";
    element.innerHTML = `
      <span class="bar-label">${row.label}</span>
      <span class="bar-track"><span class="bar-fill" style="width:${width}%; background:${row.color || "var(--green)"}"></span></span>
      <span class="bar-value">${row.value}</span>
    `;
    node.appendChild(element);
  }
}

function renderCharts() {
  const stats = calculateStats();
  renderMetric("totalStores", stats.total);
  renderMetric("confirmedStores", stats.confirmed);
  renderMetric("takeoutStores", stats.takeout);
  renderMetric("deliveryStores", stats.delivery);
  renderMetric("pendingStores", stats.pending);

  renderBarChart(
    document.getElementById("orderChart"),
    [
      { label: "點餐外帶", value: stats.takeout, color: "var(--blue)" },
      { label: "點餐外送", value: stats.delivery, color: "var(--green)" },
      { label: "待查核", value: stats.pending, color: "var(--amber)" },
    ],
    Math.max(stats.takeout, stats.delivery, stats.pending)
  );

  const providers = [...stats.providerCounts.entries()]
    .map(([label, value]) => ({ label, value, color: providerColors[label] || "var(--amber)" }))
    .sort((a, b) => b.value - a.value || a.label.localeCompare(b.label, "zh-Hant"));
  renderBarChart(document.getElementById("providerChart"), providers, Math.max(...providers.map((row) => row.value), 0));
}

function fillFilters() {
  const cityFilter = document.getElementById("cityFilter");
  const statusFilter = document.getElementById("statusFilter");

  for (const city of unique(state.stores.map((store) => store.city_group))) {
    const option = document.createElement("option");
    option.value = city;
    option.textContent = city;
    cityFilter.appendChild(option);
  }

  for (const status of unique(state.stores.map((store) => store.gmb_status))) {
    const option = document.createElement("option");
    option.value = status;
    option.textContent = status;
    statusFilter.appendChild(option);
  }
}

function matchesFilters(store) {
  const query = document.getElementById("searchInput").value.trim().toLowerCase();
  const city = document.getElementById("cityFilter").value;
  const status = document.getElementById("statusFilter").value;
  const haystack = [
    store.official_name,
    store.gmb_name,
    store.city_group,
    store.address,
    ...(store.takeout_providers || []),
    ...(store.delivery_providers || []),
    ...(store.other_providers || []),
    store.verification_note,
  ]
    .join(" ")
    .toLowerCase();

  return (!query || haystack.includes(query)) && (!city || store.city_group === city) && (!status || store.gmb_status === status);
}

function renderTags(values, fallback = "無") {
  if (!Array.isArray(values) || !values.length) {
    return `<span class="small">${fallback}</span>`;
  }
  return `<span class="tag-list">${values.map((value) => `<span class="tag">${value}</span>`).join("")}</span>`;
}

function renderRows() {
  state.filtered = state.stores.filter(matchesFilters);
  document.getElementById("rowCount").textContent = `${state.filtered.length.toLocaleString("zh-Hant")} 筆資料`;
  const body = document.getElementById("storeRows");
  body.innerHTML = "";

  for (const store of state.filtered) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>
        <div class="store-name">${store.official_name}</div>
        <div class="small">${store.city_group}</div>
      </td>
      <td>${store.address || '<span class="small">未提供</span>'}</td>
      <td>
        <span class="tag ${store.gmb_status === "已人工確認" ? "confirmed" : "pending"}">${store.gmb_status}</span>
        <div class="small">${store.verification_note || ""}</div>
      </td>
      <td>
        <span class="tag ${tagClass(store.has_takeout_order)}">${boolLabel(store.has_takeout_order)}</span>
        ${renderTags(store.takeout_providers, "待查核")}
      </td>
      <td>
        <span class="tag ${tagClass(store.has_delivery_order)}">${boolLabel(store.has_delivery_order)}</span>
        ${renderTags(store.delivery_providers, "待查核")}
      </td>
      <td>${renderTags(store.other_providers)}</td>
      <td>
        <a href="${store.gmb_url}" target="_blank" rel="noreferrer">GMB</a>
        <span class="small"> / </span>
        <a href="${store.official_url}" target="_blank" rel="noreferrer">官網</a>
      </td>
    `;
    body.appendChild(row);
  }
}

function bindEvents() {
  for (const id of ["searchInput", "cityFilter", "statusFilter"]) {
    document.getElementById(id).addEventListener("input", renderRows);
  }
}

async function init() {
  const response = await fetch("data/stores.json", { cache: "no-store" });
  const payload = await response.json();
  state.stores = payload.stores || [];
  document.getElementById("updatedAt").textContent = `資料更新：${payload.generated_at || "未標示"}`;
  fillFilters();
  renderCharts();
  renderRows();
  bindEvents();
}

init().catch((error) => {
  console.error(error);
  document.getElementById("rowCount").textContent = "資料載入失敗";
});
