const state = {
  stores: [],
  filtered: [],
  sortKey: "district",
  sortDirection: "asc",
};

const providerColors = {
  Nidin: "var(--teal)",
  foodpanda: "var(--rose)",
  "Uber Eats": "var(--indigo)",
  "lin.ee": "var(--amber)",
};

const confidenceLabels = {
  high: "高",
  medium: "中",
  low: "低",
};

function unique(values) {
  return [...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b, "zh-Hant"));
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString("zh-Hant");
}

function boolLabel(value) {
  if (value === true) return "可用";
  if (value === false) return "未提供";
  return "待複核";
}

function serviceSourceLabel(store) {
  if (store.gmbEvidence?.takeout === "Google Places API" || store.gmbEvidence?.delivery === "Google Places API") {
    return "Google API 確認";
  }
  if (store.manualReviewStatus === "needs_review") {
    return "待 GMB/API 複核";
  }
  return "公開資料交叉比對";
}

function boolClass(value) {
  if (value === true) return "confirmed";
  if (value === false) return "none";
  return "pending";
}

function renderMetric(id, value) {
  document.getElementById(id).textContent = formatNumber(value);
}

function calculateStats(stores = state.stores) {
  const deliveryProviderCounts = new Map();
  for (const store of stores) {
    for (const provider of unique(store.deliveryProviders || [])) {
      deliveryProviderCounts.set(provider, (deliveryProviderCounts.get(provider) || 0) + 1);
    }
  }
  return {
    storeCount: stores.length,
    gmbFoundCount: stores.filter((store) => store.gmbStatus === "confirmed" && store.gmbUrl).length,
    takeoutCount: stores.filter((store) => store.takeoutAvailable === true).length,
    deliveryCount: stores.filter((store) => store.deliveryAvailable === true).length,
    unknownCount: stores.filter((store) => store.takeoutAvailable == null || store.deliveryAvailable == null).length,
    deliveryProviderCounts,
  };
}

function renderBarChart(node, rows, maxValue) {
  node.innerHTML = "";
  if (!rows.length || maxValue === 0) {
    node.innerHTML = '<p class="small">目前沒有符合條件的資料。</p>';
    return;
  }
  for (const row of rows) {
    const width = Math.max(4, (row.value / maxValue) * 100);
    const element = document.createElement("div");
    element.className = "bar-row";
    element.innerHTML = `
      <span class="bar-label">${row.label}</span>
      <span class="bar-track"><span class="bar-fill" style="width:${width}%; background:${row.color}"></span></span>
      <span class="bar-value">${formatNumber(row.value)}</span>
    `;
    node.appendChild(element);
  }
}

function renderCharts() {
  const stats = calculateStats(state.filtered);
  const overallStats = calculateStats();
  renderMetric("storeCount", overallStats.storeCount);
  renderMetric("gmbFoundCount", overallStats.gmbFoundCount);
  renderMetric("takeoutCount", overallStats.takeoutCount);
  renderMetric("deliveryCount", overallStats.deliveryCount);
  renderMetric("unknownCount", overallStats.unknownCount);

  const serviceRows = [
    { label: "外帶可用", value: stats.takeoutCount, color: "var(--teal)" },
    { label: "外送可用", value: stats.deliveryCount, color: "var(--indigo)" },
    { label: "待複核", value: stats.unknownCount, color: "var(--amber)" },
  ];
  renderBarChart(document.getElementById("serviceChart"), serviceRows, Math.max(...serviceRows.map((row) => row.value)));

  const deliveryProviders = [...stats.deliveryProviderCounts.entries()]
    .map(([label, value]) => ({ label, value, color: providerColors[label] || "var(--muted)" }))
    .sort((a, b) => b.value - a.value || a.label.localeCompare(b.label, "zh-Hant"));
  renderBarChart(
    document.getElementById("deliveryProviderChart"),
    deliveryProviders,
    Math.max(...deliveryProviders.map((row) => row.value), 0),
  );
}

function fillFilters() {
  const districtFilter = document.getElementById("districtFilter");
  const providerFilter = document.getElementById("providerFilter");
  for (const district of unique(state.stores.map((store) => store.district))) {
    const option = document.createElement("option");
    option.value = district;
    option.textContent = district;
    districtFilter.appendChild(option);
  }
  for (const provider of unique(state.stores.flatMap((store) => store.providerNames || []))) {
    const option = document.createElement("option");
    option.value = provider;
    option.textContent = provider;
    providerFilter.appendChild(option);
  }
}

function matchesFilters(store) {
  const query = document.getElementById("searchInput").value.trim().toLowerCase();
  const district = document.getElementById("districtFilter").value;
  const service = document.getElementById("serviceFilter").value;
  const provider = document.getElementById("providerFilter").value;
  const confidence = document.getElementById("confidenceFilter").value;
  const haystack = [
    store.storeName,
    store.district,
    store.address,
    store.phone,
    ...(store.providerNames || []),
    store.verificationNote,
    store.evidenceNotes,
  ]
    .join(" ")
    .toLowerCase();

  if (query && !haystack.includes(query)) return false;
  if (district && store.district !== district) return false;
  if (provider && !(store.providerNames || []).includes(provider)) return false;
  if (confidence && store.confidence !== confidence) return false;
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

function renderTags(values, fallback = "無") {
  if (!Array.isArray(values) || !values.length) {
    return `<span class="small">${fallback}</span>`;
  }
  return `<span class="tag-list">${values.map((value) => `<span class="tag">${value}</span>`).join("")}</span>`;
}

function evidenceText(store) {
  const items = [];
  if (store.gmbEvidence?.takeout === "Google Places API" || store.gmbEvidence?.delivery === "Google Places API") {
    items.push("Google Places API");
  }
  if (store.nidinEvidence?.matched) items.push("Nidin 官方點餐");
  if ((store.deliveryPlatformEvidence || []).some((entry) => entry.provider === "foodpanda" || entry.provider === "Uber Eats")) {
    items.push("Footinder 平台交叉比對");
  }
  if (store.manualReviewStatus === "needs_review") items.push("待人工複核");
  if (items.length) return items.join("、");
  return "公開資料交叉比對";
}

function providerEvidenceNote(store) {
  if (!Array.isArray(store.providerNames) || !store.providerNames.length) {
    return "尚未確認供應商";
  }
  if (store.gmbEvidence?.takeout === "Google Places API" || store.gmbEvidence?.delivery === "Google Places API") {
    return "供應商仍需點開 GMB 點餐流程確認";
  }
  return "供應商來自 Nidin / 外部平台證據，非 GMB 直接欄位";
}

function evidenceLinks(store) {
  const links = [];
  if (store.gmbUrl) links.push(`<a href="${store.gmbUrl}" target="_blank" rel="noreferrer">GMB</a>`);
  if (store.nidinEvidence?.url) links.push(`<a href="${store.nidinEvidence.url}" target="_blank" rel="noreferrer">Nidin</a>`);
  if (store.officialSourceUrl) links.push(`<a href="${store.officialSourceUrl}" target="_blank" rel="noreferrer">官網</a>`);
  return links.join("");
}

function renderRows() {
  state.filtered = state.stores.filter(matchesFilters).sort(sortStores);
  document.getElementById("rowCount").textContent = `${formatNumber(state.filtered.length)} 筆`;
  const body = document.getElementById("storeRows");
  body.innerHTML = "";

  for (const store of state.filtered) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>
        <div class="store-name">${store.storeName}</div>
        <div class="small">${store.phone || "未提供電話"}</div>
      </td>
      <td>
        <div>${store.district || "未判讀"}</div>
        <div class="small">${store.address || "未提供地址"}</div>
      </td>
      <td>
        <span class="tag ${boolClass(store.takeoutAvailable)}">${boolLabel(store.takeoutAvailable)}</span>
        <div class="small">${serviceSourceLabel(store)}</div>
        ${renderTags(store.takeoutProviders, "服務商待確認")}
      </td>
      <td>
        <span class="tag ${boolClass(store.deliveryAvailable)}">${boolLabel(store.deliveryAvailable)}</span>
        <div class="small">${serviceSourceLabel(store)}</div>
        ${renderTags(store.deliveryProviders, "服務商待確認")}
      </td>
      <td>
        ${renderTags(store.providerNames, "待確認")}
        <div class="small">${providerEvidenceNote(store)}</div>
      </td>
      <td>
        <div>${evidenceText(store)}</div>
        <div class="small">${store.verificationNote || ""}</div>
      </td>
      <td><span class="tag confidence-${store.confidence || "low"}">${confidenceLabels[store.confidence] || "低"}</span></td>
      <td class="links">${evidenceLinks(store)}</td>
    `;
    body.appendChild(row);
  }
  renderCharts();
}

function bindEvents() {
  for (const id of ["searchInput", "districtFilter", "serviceFilter", "providerFilter", "confidenceFilter"]) {
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
  document.getElementById("generatedAt").textContent = payload.generatedAt || "-";
  document.getElementById("googleApiStatus").textContent = payload.summary?.sources?.googlePlacesApi || "not configured";
  fillFilters();
  bindEvents();
  renderRows();
}

init().catch((error) => {
  console.error(error);
  document.getElementById("rowCount").textContent = "資料載入失敗";
});
