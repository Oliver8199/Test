const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const yen = (v) => (v == null || v === "" ? "—" : Math.round(v).toLocaleString("ja-JP") + "円");
const num = (v) => (v == null ? "—" : Number(v).toLocaleString("ja-JP"));
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const PLATFORM = { crowdworks: "クラウドワークス", coconala: "ココナラ", manual: "手動" };
const PTYPE = { fixed: "固定", hourly: "時給", writing: "記事", task: "タスク", unknown: "—" };
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

let currentTab = "home";
const charts = {};

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || res.statusText);
  return body;
}
const kw = () => $("#kw").value;
const qs = (o) => new URLSearchParams(Object.entries(o).filter(([, v]) => v !== "" && v != null)).toString();

function drawChart(id, config) {
  charts[id]?.destroy();
  Chart.defaults.color = css("--muted");
  Chart.defaults.borderColor = css("--border");
  charts[id] = new Chart($("#" + id), { ...config, options: { responsive: true, maintainAspectRatio: false, ...config.options } });
}

// ---- tabs ----
$$("#tabs button").forEach((b) =>
  b.addEventListener("click", () => {
    $$("#tabs button").forEach((x) => x.classList.toggle("active", x === b));
    $$(".tab").forEach((t) => t.classList.toggle("active", t.id === "tab-" + b.dataset.tab));
    currentTab = b.dataset.tab;
    refresh();
  })
);
$("#kw").addEventListener("change", refresh);

async function loadOverview() {
  const o = await api("/api/overview");
  $("#overview").textContent = `案件 ${num(o.jobs)}件 / サービス ${num(o.services)}件 / 出品者 ${num(o.sellers)}人` +
    (o.last_collected ? ` / 最終収集 ${o.last_collected.replace("T", " ").slice(0, 16)}` : "");
  const sel = $("#kw"), cur = sel.value;
  sel.innerHTML = '<option value="">（すべて）</option>' + o.keywords.map((k) => `<option>${esc(k)}</option>`).join("");
  sel.value = o.keywords.includes(cur) ? cur : "";
}

// ---- 収集 ----
function log(id, msg) { const el = $(id); el.textContent = msg + "\n" + el.textContent; }

$("#collect-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  const platforms = f.get("platform") === "both" ? ["crowdworks", "coconala"] : [f.get("platform")];
  const btn = e.target.querySelector("button[type=submit]");
  btn.disabled = true;
  for (const platform of platforms) {
    log("#collect-log", `${PLATFORM[platform]}「${f.get("keyword")}」を収集中…（数秒〜数十秒）`);
    try {
      const r = await api("/api/collect", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ platform, keyword: f.get("keyword"), pages: Number(f.get("pages")) }) });
      log("#collect-log", `✔ ${PLATFORM[platform]}: ${r.saved}件保存（検索結果 総数 ${num(r.total_count)}件、${r.pages_fetched}ページ）`);
    } catch (err) { log("#collect-log", `✖ ${PLATFORM[platform]}: ${err.message}`); }
  }
  btn.disabled = false;
  await loadOverview();
  $("#kw").value = f.get("keyword").trim();
});

$("#add-watch").addEventListener("click", async () => {
  const f = new FormData($("#collect-form"));
  if (!f.get("keyword")) return;
  const platforms = f.get("platform") === "both" ? ["crowdworks", "coconala"] : [f.get("platform")];
  for (const platform of platforms)
    await api("/api/watchlist", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform, keyword: f.get("keyword"), pages: Number(f.get("pages")) }) });
  loadWatch(); loadOverview();
});

$("#run-watch").addEventListener("click", async (e) => {
  e.target.disabled = true;
  log("#collect-log", "ウォッチリストを一括収集中…");
  try {
    const rs = await api("/api/watchlist/run", { method: "POST" });
    rs.forEach((r) => log("#collect-log", r.error ? `✖ ${PLATFORM[r.platform]}「${r.keyword}」: ${r.error}` : `✔ ${PLATFORM[r.platform]}「${r.keyword}」: ${r.saved}件`));
  } catch (err) { log("#collect-log", "✖ " + err.message); }
  e.target.disabled = false;
  loadOverview();
});

async function loadWatch() {
  const rows = await api("/api/watchlist");
  $("#watch-table tbody").innerHTML = rows.length ? rows.map((w) => `<tr><td>${PLATFORM[w.platform] || esc(w.platform)}</td>
    <td>${esc(w.keyword)}</td><td>${w.pages}</td><td><button class="secondary small-btn" data-del="${w.id}">削除</button></td></tr>`).join("")
    : '<tr><td colspan="4" class="muted">まだありません</td></tr>';
  $$("[data-del]").forEach((b) => b.addEventListener("click", async () => {
    await api("/api/watchlist/" + b.dataset.del, { method: "DELETE" }); loadWatch();
  }));
}

// ---- 案件 ----
$("#jobs-form").addEventListener("submit", (e) => { e.preventDefault(); loadJobs(); });
async function loadJobs() {
  const f = Object.fromEntries(new FormData($("#jobs-form")));
  const [jobs, clients] = await Promise.all([
    api("/api/jobs?" + qs({ ...f, keyword: kw() })),
    api("/api/stats/clients?" + qs({ keyword: kw() })),
  ]);
  const budget = (j) => j.budget_min && j.budget_max && j.budget_min !== j.budget_max
    ? `${yen(j.budget_min)}〜${yen(j.budget_max)}` : yen(j.budget_max || j.budget_min);
  $("#jobs-table tbody").innerHTML = jobs.map((j) => `<tr>
    <td class="small">${esc((j.posted_at || "").slice(0, 10))}</td>
    <td><a href="${esc(j.url)}" target="_blank" rel="noopener">${esc(j.title)}</a></td>
    <td>${PTYPE[j.payment_type] || esc(j.payment_type)}</td>
    <td class="num">${budget(j)}</td>
    <td class="num">${j.num_contracts ?? "—"} / ${j.hope_contracts ?? "—"}</td>
    <td>${esc(j.client_name)}</td></tr>`).join("") || '<tr><td colspan="6" class="muted">データがありません。「収集」タブで集めてください。</td></tr>';
  $("#clients-table tbody").innerHTML = clients.map((c) => `<tr><td>${esc(c.client_name)}</td>
    <td class="num">${c.jobs}</td><td class="num">${yen(c.avg_budget)}</td><td class="small">${esc((c.latest_post || "").slice(0, 10))}</td></tr>`).join("");
}

// ---- 相場 ----
function summaryHtml(s) {
  if (!s.count) return '<span class="muted">データがありません</span>';
  const items = [["件数", num(s.count)], ["中央値", yen(s.median)], ["平均", yen(s.mean)],
    ["下位25%", yen(s.q1)], ["上位25%", yen(s.q3)], ["最安", yen(s.min)], ["最高", yen(s.max)]];
  return items.map(([k, v]) => `<div><span>${k}</span><b>${v}</b></div>`).join("");
}
function histChart(id, hist, color) {
  drawChart(id, { type: "bar",
    data: { labels: hist.map((h) => `${h.from.toLocaleString()}〜`), datasets: [{ label: "件数", data: hist.map((h) => h.count), backgroundColor: color, borderRadius: 3 }] },
    options: { plugins: { legend: { display: false }, tooltip: { callbacks: {
      title: (it) => { const h = hist[it[0].dataIndex]; return `${yen(h.from)} 〜 ${yen(h.to)}`; } } } },
      scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } } });
}
$("#job-ptype").addEventListener("change", loadPrices);
async function loadPrices() {
  const [s, j] = await Promise.all([
    api("/api/stats/prices?" + qs({ kind: "service", keyword: kw() })),
    api("/api/stats/prices?" + qs({ kind: "job", keyword: kw(), payment_type: $("#job-ptype").value })),
  ]);
  $("#svc-summary").innerHTML = summaryHtml(s.summary);
  $("#job-summary").innerHTML = summaryHtml(j.summary);
  histChart("svc-hist", s.histogram, css("--s2"));
  histChart("job-hist", j.histogram, css("--s1"));
}

// ---- 競合 ----
$("#svc-sort").addEventListener("change", loadSellers);
async function loadSellers() {
  const [sellers, services] = await Promise.all([
    api("/api/stats/sellers?" + qs({ keyword: kw() })),
    api("/api/services?" + qs({ keyword: kw(), sort: $("#svc-sort").value })),
  ]);
  $("#sellers-table tbody").innerHTML = sellers.map((s) => `<tr>
    <td><a href="#" data-seller="${esc(s.seller_name)}">${esc(s.seller_name)}</a></td><td>${esc(s.seller_level)}</td>
    <td class="num">${s.services}</td><td class="num">${yen(s.avg_price)}</td>
    <td class="num">${yen(s.min_price)}〜${yen(s.max_price)}</td><td class="num">${num(s.total_reviews)}</td>
    <td class="num">${s.avg_rating ?? "—"}</td><td class="num">${num(s.review_growth)}</td><td class="num">${yen(s.est_revenue)}</td></tr>`).join("")
    || '<tr><td colspan="9" class="muted">データがありません</td></tr>';
  $$("[data-seller]").forEach((a) => a.addEventListener("click", async (e) => {
    e.preventDefault();
    renderServices(await api("/api/services?" + qs({ seller: a.dataset.seller, sort: $("#svc-sort").value })));
    $("#services-table").scrollIntoView({ behavior: "smooth" });
  }));
  renderServices(services);
  const top = sellers.slice(0, 15);
  drawChart("seller-chart", { type: "bar",
    data: { labels: top.map((s) => s.seller_name), datasets: [
      { label: "レビュー数（累計）", data: top.map((s) => s.total_reviews), backgroundColor: css("--s1"), borderRadius: 3 },
      { label: "平均価格(円)", data: top.map((s) => s.avg_price), backgroundColor: css("--s2"), borderRadius: 3, xAxisID: "x2" } ] },
    options: { indexAxis: "y", scales: { y: { ticks: { autoSkip: false } }, x: { position: "bottom", beginAtZero: true }, x2: { position: "top", beginAtZero: true, grid: { drawOnChartArea: false } } } } });
}
function renderServices(rows) {
  $("#services-table tbody").innerHTML = rows.map((s) => `<tr>
    <td><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title)}</a></td><td>${esc(s.seller_name)}</td>
    <td class="num">${yen(s.price)}</td><td class="num">${s.rating ?? "—"}</td><td class="num">${num(s.review_count)}</td>
    <td>${(s.labels || "").split(",").filter(Boolean).map((l) => `<span class="tag">${esc(l)}</span>`).join("")}</td></tr>`).join("")
    || '<tr><td colspan="6" class="muted">データがありません</td></tr>';
}

// ---- トレンド ----
async function loadTrends() {
  const rows = await api("/api/stats/trends?" + qs({ keyword: kw() }));
  const groups = {};
  rows.forEach((r) => { (groups[`${PLATFORM[r.platform] || r.platform}「${r.keyword}」`] ??= []).push(r); });
  const palette = [css("--s1"), css("--s2"), "#3aa17e", "#a35bd6", "#d6455b", "#8a8f2a"];
  const ds = (field) => Object.entries(groups).map(([label, pts], i) => ({
    label, data: pts.map((p) => ({ x: p.collected_at, y: p[field] })), borderColor: palette[i % palette.length],
    backgroundColor: palette[i % palette.length], tension: 0.2, spanGaps: true }));
  const opts = { scales: { x: { type: "category", labels: [...new Set(rows.map((r) => r.collected_at))],
    ticks: { callback(v) { return String(this.getLabelForValue(v)).slice(5, 16).replace("T", " "); } } }, y: { beginAtZero: true } } };
  drawChart("trend-count", { type: "line", data: { datasets: ds("total_count") }, options: opts });
  drawChart("trend-price", { type: "line", data: { datasets: ds("price_median") }, options: opts });
}

// ---- 取込/出力 ----
$("#import-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const r = await api("/api/import", { method: "POST", body: new FormData(e.target) });
    log("#import-log", `✔ ${r.imported}件取り込み、${r.skipped}件スキップ` + (r.errors.length ? "\n" + r.errors.join("\n") : ""));
    loadOverview();
  } catch (err) { log("#import-log", "✖ " + err.message); }
});
$$("[data-export]").forEach((a) => a.addEventListener("click", () => {
  a.href = "/api/export?" + qs({ kind: a.dataset.export, keyword: kw() });
}));

function refresh() {
  ({ home: loadWatch, jobs: loadJobs, prices: loadPrices, sellers: loadSellers, trends: loadTrends }[currentTab] || (() => {}))();
}
loadOverview().then(refresh);
