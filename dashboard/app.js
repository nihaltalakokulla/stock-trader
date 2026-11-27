const config = window.STOCK_TRADER_CONFIG ?? {};
const statusEl = document.getElementById("status");

function headers() {
  return {
    apikey: config.supabaseAnonKey,
    authorization: `Bearer ${config.supabaseAnonKey}`,
  };
}

async function query(path) {
  const response = await fetch(`${config.supabaseUrl}/rest/v1/${path}`, {
    headers: headers(),
  });
  if (!response.ok) {
    throw new Error(`${path}: ${response.status}`);
  }
  return response.json();
}

function cell(text) {
  const td = document.createElement("td");
  td.textContent = text ?? "—";
  return td;
}

function renderRows(bodyId, emptyId, rows, buildCells) {
  const body = document.getElementById(bodyId);
  const empty = document.getElementById(emptyId);
  body.replaceChildren();
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    buildCells(row).forEach((td) => tr.appendChild(td));
    body.appendChild(tr);
  });
  empty.classList.toggle("hidden", rows.length > 0);
}

function money(value) {
  return Number(value).toFixed(2);
}

function stamp(value) {
  return new Date(value).toLocaleString();
}

async function load() {
  if (!config.supabaseUrl || !config.supabaseAnonKey) {
    statusEl.textContent = "Add dashboard/config.local.js";
    statusEl.className = "status error";
    return;
  }

  const [positions, signals, proposals, alerts, settings] = await Promise.all([
    query("dashboard_positions?select=*&order=opened_at.desc"),
    query("dashboard_signals?select=*&order=created_at.desc&limit=20"),
    query("dashboard_proposals?select=*&order=created_at.desc&limit=20"),
    query("dashboard_alerts?select=*&order=created_at.desc&limit=20"),
    query("settings?select=key,value&key=eq.trading_paused"),
  ]);

  const pending = proposals.filter((item) => item.state === "PROPOSED");
  document.getElementById("position-count").textContent = positions.length;
  document.getElementById("pending-symbol").textContent =
    pending.length > 0 ? pending[0].symbol : "None";
  document.getElementById("latest-signal").textContent =
    signals.length > 0 ? `${signals[0].symbol} ${Math.round(signals[0].probability * 100)}%` : "—";

  const paused = settings.some(
    (row) => row.key === "trading_paused" && row.value === true,
  );
  document.getElementById("paused-banner").classList.toggle("hidden", !paused);

  renderRows("positions-body", "positions-empty", positions, (row) => [
    cell(row.symbol),
    cell(row.qty),
    cell(money(row.avg_price)),
    cell(money(row.stop_price)),
    cell(stamp(row.opened_at)),
  ]);

  renderRows("signals-body", "signals-empty", signals, (row) => [
    cell(stamp(row.created_at)),
    cell(row.symbol),
    cell(`${Math.round(row.probability * 100)}%`),
    cell(row.rationale),
  ]);

  renderRows("proposals-body", "proposals-empty", proposals, (row) => [
    cell(stamp(row.created_at)),
    cell(row.symbol),
    cell(row.qty),
    cell(money(row.entry_price)),
    cell(money(row.stop_price)),
    cell(row.state),
    cell(stamp(row.expires_at)),
  ]);

  const alertList = document.getElementById("alerts-list");
  alertList.replaceChildren();
  alerts.forEach((row) => {
    const li = document.createElement("li");
    li.textContent = `${stamp(row.created_at)} — ${row.message}`;
    alertList.appendChild(li);
  });
  document.getElementById("alerts-empty").classList.toggle(
    "hidden",
    alerts.length > 0,
  );

  statusEl.textContent = `Updated ${new Date().toLocaleTimeString()}`;
  statusEl.className = "status ok";
}

load().catch((error) => {
  statusEl.textContent = `Connection problem: ${error.message}`;
  statusEl.className = "status error";
});
