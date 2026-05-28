const state = {
  stores: [],
  filtered: [],
  sortKey: "county",
  sortDirection: "asc",
};

const statusLabels = {
  confirmed: "已取得 GMB",
  no_gmb_found: "找不到 GMB",
  closed_or_moved: "歇業 / 搬遷",
  unavailable_or_blocked: "無法讀取",
  needs_manual_review: "待人工查核",
};

const providerColors = {
  Nidin: "var(--green)",
  foodpanda: "var(--pink)",
  "Uber Eats": "var(--blue)",
  "lin.ee": "var(--blue)",
  其他: "var(--amber)",
};

function unique(values) {
  return [...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b, "zh-Hant"));
}

function boolLabel(value) {
  if (value === true) return "有";
  if (value === false) return "無";
  return "未確認";
}

function boolClass(value) {
  if (value === true) return "confirmed";
  if (value === false) return "none";
  return "pending";
}

function providersText(values) {
  return Array.isArray(values) && values.length ? values.join("、") : "未確認";
}

function renderMetric(id, value) {
  document.getElementById(id).textContent = Number(value || 0).toLocaleString("zh-Hant");
}

function calculateStats() {
  const providerCounts = new Map();
  for (const store of state.stores) {
    const providers = unique([...(store.takeoutProviders || []), ...(store.deliveryProviders || []), ...(store.otherProviders || [])]);
    for (const provider of providers) {
      providerCounts.set(provider, (providerCounts.get(provider) || 0) + 1);
    }
  }

  return {
    officialStoreCount: state.stores.length,
    gmbFoundCount: state.stores.filter((store) => store.gmbStatus === "confirmed").length,
    takeoutCount: state.stores.filter((store) => store.takeoutAvailable === true).length,
    deliveryCount: state.stores.filter((store) => store.deliveryAvailable === true).length,
    unknownCount: state.stores.filter((store) => store.takeoutAvailable == null || store.deliveryAvailable == null).length,
    providerCounts,
  };
}

function renderBarChart(node, rows, maxValue) {
  node.innerHTML = "";
  if (!rows.length || maxValue === 0) {
    node.innerHTML = '<p class="small">目前沒有已確認資料</p>';
    return;
  }

  for (const row of rows) {
    const width = Math.max(3, (row.value / maxValue) * 100);
    const element = document.createElement("div");
    element.className = "bar-row";
    element.innerHTML = `
      <span class="bar-label">${row.label}</span>
      <span class="bar-track"><span class="bar-fill" style="width:${width}%; background:${row.color}"></span></span>
      <span class="bar-value">${row.value.toLocaleString("zh-Hant")}</span>
    `;
    node.appendChild(element);
  }
}

function renderCharts() {
  const stats = calculateStats();
  renderMetric("officialStoreCount", stats.officialStoreCount);
  renderMetric("gmbFoundCount", stats.gmbFoundCount);
  renderMetric("takeoutCount", stats.takeoutCount);
  renderMetric("deliveryCount", stats.deliveryCount);
  renderMetric("unknownCount", stats.unknownCount);

  renderBarChart(
    document.getElementById("orderChart"),
    [
      { label: "外帶", value: stats.takeoutCount, color: "var(--blue)" },
      { label: "外送", value: stats.deliveryCount, color: "var(--green)" },
      { label: "未確認", value: stats.unknownCount, color: "var(--amber)" },
    ],
    Math.max(stats.takeoutCount, stats.deliveryCount, stats.unknownCount)
  );

  const providers = [...stats.providerCounts.entries()]
    .map(([label, value]) => ({ label, value, color: providerColors[label] || providerColors["其他"] }))
    .sort((a, b) => b.value - a.value || a.label.localeCompare(b.label, "zh-Hant"));
  renderBarChart(document.getElementById("providerChart"), providers, Math.max(...providers.map((row) => row.value), 0));
}

function fillFilters() {
  const countyFilter = document.getElementById("countyFilter");
  const statusFilter = document.getElementById("statusFilter");
  for (const county of unique(state.stores.map((store) => store.county))) {
    const option = document.createElement("option");
    option.value = county;
    option.textContent = county;
    countyFilter.appendChild(option);
  }
  for (const status of unique(state.stores.map((store) => store.gmbStatus))) {
    const option = document.createElement("option");
    option.value = status;
    option.textContent = statusLabels[status] || status;
    statusFilter.appendChild(option);
  }
}

function matchesFilters(store) {
  const query = document.getElementById("searchInput").value.trim().toLowerCase();
  const county = document.getElementById("countyFilter").value;
  const status = document.getElementById("statusFilter").value;
  const service = document.getElementById("serviceFilter").value;
  const haystack = [
    store.storeName,
    store.county,
    store.district,
    store.address,
    store.phone,
    ...(store.takeoutProviders || []),
    ...(store.deliveryProviders || []),
    ...(store.otherProviders || []),
    store.evidenceNotes,
  ]
    .join(" ")
    .toLowerCase();

  if (query && !haystack.includes(query)) return false;
  if (county && store.county !== county) return false;
  if (status && store.gmbStatus !== status) return false;
  if (service === "takeout" && store.takeoutAvailable !== true) return false;
  if (service === "delivery" && store.deliveryAvailable !== true) return false;
  if (service === "unknown" && store.takeoutAvailable !== null && store.deliveryAvailable !== null) return false;
  return true;
}

function sortStores(a, b) {
  const left = String(a[state.sortKey] || "");
  const right = String(b[state.sortKey] || "");
  const result = left.localeCompare(right, "zh-Hant");
  return state.sortDirection === "asc" ? result : -result;
}

function renderTags(values, fallback = "未確認") {
  if (!Array.isArray(values) || !values.length) {
    return `<span class="small">${fallback}</span>`;
  }
  return `<span class="tag-list">${values.map((value) => `<span class="tag">${value}</span>`).join("")}</span>`;
}

function evidenceLinks(store) {
  const links = [];
  if (store.gmbUrl) links.push(`<a href="${store.gmbUrl}" target="_blank" rel="noreferrer">GMB</a>`);
  if (store.nidinOrderUrl) links.push(`<a href="${store.nidinOrderUrl}" target="_blank" rel="noreferrer">Nidin</a>`);
  if (store.providerEvidenceUrl) links.push(`<a href="${store.providerEvidenceUrl}" target="_blank" rel="noreferrer">外送證據</a>`);
  if (store.officialSourceUrl) links.push(`<a href="${store.officialSourceUrl}" target="_blank" rel="noreferrer">官方</a>`);
  return links.join("");
}

function renderRows() {
  state.filtered = state.stores.filter(matchesFilters).sort(sortStores);
  document.getElementById("rowCount").textContent = `${state.filtered.length.toLocaleString("zh-Hant")} 筆`;
  const body = document.getElementById("storeRows");
  body.innerHTML = "";

  for (const store of state.filtered) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>
        <div class="store-name">${store.storeName}</div>
        <div class="small">${store.phone || "無電話"}</div>
      </td>
      <td>
        <div>${store.county || "未解析"}${store.district ? ` / ${store.district}` : ""}</div>
        <div class="small">${store.address || "無地址"}</div>
      </td>
      <td>
        <span class="tag ${store.gmbStatus === "confirmed" ? "confirmed" : "pending"}">${statusLabels[store.gmbStatus] || store.gmbStatus}</span>
        <div class="small">${store.evidenceNotes || ""}</div>
      </td>
      <td>
        <span class="tag ${boolClass(store.takeoutAvailable)}">${boolLabel(store.takeoutAvailable)}</span>
        ${renderTags(store.takeoutProviders)}
      </td>
      <td>
        <span class="tag ${boolClass(store.deliveryAvailable)}">${boolLabel(store.deliveryAvailable)}</span>
        ${renderTags(store.deliveryProviders)}
      </td>
      <td>${renderTags(store.otherProviders, "無")}</td>
      <td class="links">${evidenceLinks(store)}</td>
    `;
    body.appendChild(row);
  }
}

function bindEvents() {
  for (const id of ["searchInput", "countyFilter", "statusFilter", "serviceFilter"]) {
    document.getElementById(id).addEventListener("input", renderRows);
  }
  document.querySelectorAll("th[data-sort]").forEach((header) => {
    header.addEventListener("click", () => {
      const nextKey = header.dataset.sort;
      if (state.sortKey === nextKey) {
        state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
      } else {
        state.sortKey = nextKey;
        state.sortDirection = "asc";
      }
      renderRows();
    });
  });
}

async function init() {
  const response = await fetch("data/stores.json", { cache: "no-store" });
  const payload = await response.json();
  state.stores = payload.stores || [];
  document.getElementById("checkedAt").textContent = payload.generatedAt || "-";
  fillFilters();
  renderCharts();
  renderRows();
  bindEvents();
}

init().catch((error) => {
  console.error(error);
  document.getElementById("rowCount").textContent = "資料載入失敗";
});
