"use strict";

const $ = (id) => document.getElementById(id);

function showStatus(msg, kind) {
  const el = $("status");
  el.textContent = msg;
  el.className = "status " + (kind || "");
  el.classList.remove("hidden");
}
function hideStatus() { $("status").classList.add("hidden"); }

function fmtPct(v) {
  if (v === null || v === undefined) return "–";
  const s = v >= 0 ? "+" : "";
  return s + v.toFixed(2) + "%";
}
function pctClass(v) {
  if (v === null || v === undefined) return "";
  return v >= 0 ? "pos" : "neg";
}

async function postJSON(url) {
  const res = await fetch(url, { method: "POST" });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Tuntematon virhe");
  return data;
}

// --- Osto-tulostaulu ---
function renderBuy(entry) {
  $("result-title").textContent = "🌆 Ostosuositukset " + entry.date;
  $("result-meta").innerHTML =
    `Analysoitu ${entry.universe_size} osaketta · luotu ${entry.created_at} · ` +
    `pidä yön yli, myy avauksen jälkeen.`;

  let rows = entry.portfolio.map((p) => `
    <tr>
      <td><span class="ticker">${p.ticker}</span></td>
      <td><span class="score-badge">${p.score.toFixed(1)}</span></td>
      <td>$${p.buy_price.toFixed(2)}</td>
      <td>${p.atr_pct.toFixed(1)}%</td>
      <td class="${pctClass(p.momentum_5d)}">${fmtPct(p.momentum_5d)}</td>
      <td>${p.gap_winrate.toFixed(0)}%</td>
      <td>${p.rel_volume.toFixed(1)}x</td>
      <td class="reason">${p.reason}</td>
    </tr>`).join("");

  $("result-table").innerHTML = `
    <table>
      <thead><tr>
        <th>Osake</th><th>Pisteet</th><th>Hinta</th><th>ATR%</th>
        <th>5pv mom.</th><th>Gap-win</th><th>Vaihto</th><th>Peruste</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
  $("result").classList.remove("hidden");
}

// --- Myynti-tulostaulu ---
function renderSell(entry) {
  $("result-title").textContent = "🌅 Myyntisuositukset " + entry.date;
  const avg = entry.avg_overnight_gap_pct;
  $("result-meta").innerHTML =
    `Eilen ostetut positiot · keskim. yön yli -tuotto: ` +
    `<span class="${pctClass(avg)}">${fmtPct(avg)}</span>`;

  let rows = entry.sells.map((s) => {
    let cls = "neutral";
    if (s.decision && s.decision.includes("voitto")) cls = "profit";
    else if (s.decision && s.decision.includes("stop")) cls = "loss";
    return `
    <tr>
      <td><span class="ticker">${s.ticker}</span></td>
      <td>$${s.buy_price ? s.buy_price.toFixed(2) : "–"}</td>
      <td>${s.current_price ? "$" + s.current_price.toFixed(2) : "–"}</td>
      <td class="${pctClass(s.gap_pct)}">${fmtPct(s.gap_pct)}</td>
      <td class="decision ${cls}">${s.decision}</td>
      <td class="reason">${s.reason}</td>
    </tr>`;
  }).join("");

  $("result-table").innerHTML = `
    <table>
      <thead><tr>
        <th>Osake</th><th>Ostohinta</th><th>Nyt</th>
        <th>Yön yli</th><th>Suositus</th><th>Peruste</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
  $("result").classList.remove("hidden");
}

// --- Historia ---
async function loadHistory() {
  try {
    const res = await fetch("/api/history");
    const hist = await res.json();
    const el = $("history-list");
    if (!hist.length) { el.textContent = "Ei vielä suosituksia."; return; }
    el.innerHTML = hist.map((h) => {
      const tickers = h.portfolio.map((p) => p.ticker).join(", ");
      const statusBadge = h.status === "open"
        ? '<span class="badge open">avoin</span>'
        : '<span class="badge closed">suljettu</span>';
      let gapHtml = "";
      if (h.avg_overnight_gap_pct !== undefined && h.avg_overnight_gap_pct !== null) {
        gapHtml = `<span class="he-gap ${pctClass(h.avg_overnight_gap_pct)}">` +
          `yön yli ${fmtPct(h.avg_overnight_gap_pct)}</span>`;
      }
      return `<div class="history-entry">
          <div class="he-head">
            <span class="he-date">${h.date} ${statusBadge}</span>
            ${gapHtml}
          </div>
          <div class="he-tickers">📦 ${tickers}</div>
        </div>`;
    }).join("");
  } catch (e) {
    $("history-list").textContent = "Historian lataus epäonnistui.";
  }
}

// --- Napit ---
$("btn-buy").addEventListener("click", async () => {
  const btn = $("btn-buy");
  btn.disabled = true;
  showStatus("Analysoidaan Nasdaq-100… (voi kestää 10–30 s)", "loading");
  try {
    const entry = await postJSON("/api/recommend-buy");
    hideStatus();
    renderBuy(entry);
    loadHistory();
  } catch (e) {
    showStatus("Virhe: " + e.message, "error");
  } finally {
    btn.disabled = false;
  }
});

$("btn-sell").addEventListener("click", async () => {
  const btn = $("btn-sell");
  btn.disabled = true;
  showStatus("Haetaan avaushintoja ja arvioidaan positiot…", "loading");
  try {
    const entry = await postJSON("/api/recommend-sell");
    hideStatus();
    renderSell(entry);
    loadHistory();
  } catch (e) {
    showStatus("Virhe: " + e.message, "error");
  } finally {
    btn.disabled = false;
  }
});

loadHistory();
