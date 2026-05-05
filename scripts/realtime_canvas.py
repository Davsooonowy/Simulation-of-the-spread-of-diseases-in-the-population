"""Continuous real-time SEIRD simulation on a browser canvas.

Run:
    uv run streamlit run scripts/realtime_canvas.py
"""
from __future__ import annotations

import json
import time

import streamlit as st


DEFAULT_PARAMS = {
    "n_agents": 180,
    "initial_infected_frac": 0.04,
    "day_duration": 16,
    "p_base_multiplier": 0.55,
    "p_transit": 0.035,
    "mask_coverage": 0.0,
    "social_distancing_coverage": 0.0,
    "vaccination_coverage": 0.0,
    "lockdown": False,
    "incubation_period": 4,
    "infectious_period": 10,
    "p_death": 0.015,
}


def build_canvas_html(params: dict) -> str:
    """Return the standalone HTML/JS canvas simulation."""
    params_json = json.dumps(params)
    return CANVAS_TEMPLATE.replace("__PARAMS_JSON__", params_json)


def main() -> None:
    st.set_page_config(
        page_title="Pandemic - Real Time Canvas",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        .block-container { padding-top: .7rem; padding-bottom: .5rem; }
        [data-testid="stSidebar"] { min-width: 330px; }
        iframe { border-radius: 8px; box-shadow: 0 16px 42px rgba(15, 23, 42, .18); }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.title("Parametry")
        with st.form("params_form"):
            n_agents = st.slider("Liczba agentow", 50, 500, DEFAULT_PARAMS["n_agents"], step=10)
            init_inf = st.slider("Startowe zakazenia (%)", 1, 20, 4) / 100
            day_dur = st.slider("Czas dnia (sekundy)", 6, 40, DEFAULT_PARAMS["day_duration"], step=2)
            p_mult = st.slider("Zakaznosc (mnoznik)", 0.10, 2.00, DEFAULT_PARAMS["p_base_multiplier"], step=0.05)
            p_transit = st.slider("Transmisja w trasie", 0.00, 0.20, DEFAULT_PARAMS["p_transit"], step=0.005)
            incubation = st.slider("Inkubacja (dni)", 2, 10, DEFAULT_PARAMS["incubation_period"])
            infectious = st.slider("Okres zakazny (dni)", 5, 24, DEFAULT_PARAMS["infectious_period"])
            p_death = st.slider("Smiertelnosc (%)", 0.0, 8.0, DEFAULT_PARAMS["p_death"] * 100, step=0.1) / 100

            st.divider()
            st.subheader("Interwencje")
            mask_pct = st.slider("Maseczki (%)", 0, 100, 0) / 100
            sd_pct = st.slider("Dystans spoleczny (%)", 0, 100, 0) / 100
            vacc_pct = st.slider("Szczepienia (%)", 0, 100, 0) / 100
            lockdown = st.checkbox("Lockdown")
            submitted = st.form_submit_button("Apply & Start", type="primary")

        if submitted or "active_params" not in st.session_state:
            st.session_state.active_params = {
                "n_agents": n_agents,
                "initial_infected_frac": init_inf,
                "day_duration": day_dur,
                "p_base_multiplier": p_mult,
                "p_transit": p_transit,
                "mask_coverage": mask_pct,
                "social_distancing_coverage": sd_pct,
                "vaccination_coverage": vacc_pct,
                "lockdown": lockdown,
                "incubation_period": incubation,
                "infectious_period": infectious,
                "p_death": p_death,
            }
            st.session_state.sim_started_at = time.time()

        st.divider()
        st.caption("Zmien parametry i kliknij **Apply & Start**, aby uruchomic nowa symulacje.")
        st.caption("Ruch i zakazenia licza sie w przegladarce w petli animacji, bez krokowego rerenderu Streamlit.")

    st.markdown("## Symulacja pandemii - plynny canvas")
    st.components.v1.html(
        build_canvas_html(st.session_state.active_params),
        height=720,
        scrolling=False,
    )


CANVAS_TEMPLATE = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
:root {
  color-scheme: dark;
  --bg: #071014;
  --panel: #0d1820;
  --line: #203848;
  --text: #e6edf3;
  --muted: #8aa0ad;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: 100%; height: 100%; overflow: hidden; background: var(--bg); }
body {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
}
canvas { display: block; width: 100%; height: auto; background: var(--bg); }
#toolbar {
  position: fixed; top: 10px; right: 12px; z-index: 3;
  display: flex; align-items: center; gap: 8px;
}
button {
  min-width: 38px; height: 30px; padding: 0 11px;
  border: 1px solid #315067; border-radius: 6px;
  background: rgba(13,24,32,.92); color: #e6edf3;
  font: 12px/1 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  cursor: pointer;
}
button:hover { background: #162a37; }
#speed {
  accent-color: #74c69d; width: 112px;
}
#hud {
  position: fixed; top: 10px; left: 12px; z-index: 3;
  display: grid; grid-template-columns: repeat(6, auto); gap: 10px;
  color: var(--text); font-size: 12px; pointer-events: none;
}
#hud span {
  padding: 6px 8px; border: 1px solid rgba(49,80,103,.8);
  background: rgba(13,24,32,.82); border-radius: 6px;
}
</style>
</head>
<body>
<div id="hud">
  <span id="day">Dzien 0.0</span>
  <span id="S">S 0</span>
  <span id="E">E 0</span>
  <span id="I">I 0</span>
  <span id="R">R 0</span>
  <span id="D">D 0</span>
</div>
<div id="toolbar">
  <button id="play" title="Play">Play</button>
  <button id="pause" title="Pause">Pause</button>
  <button id="reset" title="Reset">Reset</button>
  <input id="speed" title="Predkosc symulacji" type="range" min="0.4" max="3" step="0.1" value="1">
</div>
<canvas id="sim"></canvas>
<script>
const PARAMS = __PARAMS_JSON__;

const CW = 1180;
const CH = 680;
const MAP_W = 770;
const CHART_X = 810;
const CHART_Y = 112;
const CHART_W = 320;
const CHART_H = 420;
const canvas = document.getElementById("sim");
const ctx = canvas.getContext("2d");
canvas.width = CW;
canvas.height = CH;

function resizeCanvas() {
  const width = window.innerWidth;
  canvas.style.width = width + "px";
  canvas.style.height = Math.round(width * CH / CW) + "px";
}
resizeCanvas();
window.addEventListener("resize", resizeCanvas);

const COLORS = {
  S: "#55aaff",
  E: "#f6b352",
  I: "#ef476f",
  R: "#74c69d",
  D: "#5b6670"
};

const POI = {
  HOUSEHOLD: { x: 145, y: 345, r: 78, label: "Domy", pBase: 0.22, dwell: 0.18 },
  SCHOOL: { x: 340, y: 170, r: 58, label: "Szkola", pBase: 0.24, dwell: 0.20 },
  OFFICE: { x: 555, y: 178, r: 62, label: "Biuro", pBase: 0.16, dwell: 0.20 },
  SHOP: { x: 660, y: 360, r: 52, label: "Sklep", pBase: 0.08, dwell: 0.11 },
  HEALTHCARE: { x: 352, y: 552, r: 58, label: "Szpital", pBase: 0.18, dwell: 0.22 },
  PARK: { x: 560, y: 540, r: 58, label: "Park", pBase: 0.025, dwell: 0.14 }
};
for (const poi of Object.values(POI)) {
  poi.pBase *= PARAMS.p_base_multiplier;
}
if (PARAMS.lockdown) {
  POI.OFFICE.pBase = 0;
  POI.SCHOOL.pBase *= 0.25;
  POI.SHOP.pBase *= 0.35;
}

const ROUTES = [
  ["HOUSEHOLD", "SCHOOL"],
  ["HOUSEHOLD", "OFFICE"],
  ["HOUSEHOLD", "SHOP"],
  ["HOUSEHOLD", "HEALTHCARE"],
  ["HOUSEHOLD", "PARK"],
  ["SCHOOL", "OFFICE"],
  ["OFFICE", "SHOP"],
  ["SHOP", "PARK"],
  ["HEALTHCARE", "PARK"]
];

let agents = [];
let day = 0;
let running = true;
let lastTs = performance.now();
let history = [];
let nextHistoryDay = 0;

function rand(min, max) {
  return min + Math.random() * (max - min);
}

function pick(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function insidePoiPosition(poiName) {
  const poi = POI[poiName];
  const theta = rand(0, Math.PI * 2);
  const radius = poi.r * Math.sqrt(Math.random()) * 0.78;
  return { x: poi.x + Math.cos(theta) * radius, y: poi.y + Math.sin(theta) * radius };
}

function ageGroup(age) {
  if (age < 18) return "child";
  if (age <= 65) return "adult";
  return "senior";
}

function plannedDay(agent) {
  const route = ["HOUSEHOLD"];
  if (!agent.hospitalized) {
    if (!PARAMS.lockdown && agent.group === "child") route.push("SCHOOL");
    if (!PARAMS.lockdown && agent.group === "adult") route.push("OFFICE");
    if (!agent.socialDistancing && Math.random() < 0.26) route.push("SHOP");
    if (agent.state !== "I" && Math.random() < (agent.socialDistancing ? 0.10 : 0.26)) route.push("PARK");
  }
  if (agent.state === "I") {
    const hospitalRisk = agent.group === "senior" ? 0.32 : agent.group === "adult" ? 0.16 : 0.07;
    agent.hospitalized = agent.hospitalized || Math.random() < hospitalRisk;
    if (agent.hospitalized) route.splice(1, route.length - 1, "HEALTHCARE");
  } else {
    agent.hospitalized = false;
  }
  route.push("HOUSEHOLD");
  return route;
}

function setRoute(agent, route) {
  agent.route = route;
  agent.routeIndex = 0;
  agent.currentPOI = route[0];
  agent.targetPOI = route[0];
  agent.dwellUntil = day + 0.05;
  const p = insidePoiPosition(route[0]);
  agent.x = p.x;
  agent.y = p.y;
  agent.tx = p.x;
  agent.ty = p.y;
  agent.isMoving = false;
}

function createAgents() {
  agents = [];
  day = 0;
  history = [];
  nextHistoryDay = 0;
  const n = PARAMS.n_agents;
  for (let i = 0; i < n; i++) {
    const age = Math.floor(rand(1, 88));
    const state = Math.random() < PARAMS.initial_infected_frac ? "I" : "S";
    const vaccinated = Math.random() < PARAMS.vaccination_coverage;
    const p = insidePoiPosition("HOUSEHOLD");
    const agent = {
      id: i,
      x: p.x,
      y: p.y,
      tx: p.x,
      ty: p.y,
      vx: 0,
      vy: 0,
      radius: n > 320 ? 2.5 : n > 220 ? 3.0 : 3.6,
      state,
      age,
      group: ageGroup(age),
      vaccinated,
      immunity: vaccinated ? 0.52 : 0,
      wearsMask: Math.random() < PARAMS.mask_coverage,
      socialDistancing: Math.random() < PARAMS.social_distancing_coverage,
      infectedAt: state === "I" ? -PARAMS.incubation_period : null,
      exposedAt: null,
      viralLoad: state === "I" ? rand(0.35, 0.9) : 0,
      contactCooldown: 0,
      hospitalized: false,
      currentPOI: "HOUSEHOLD",
      targetPOI: "HOUSEHOLD",
      route: [],
      routeIndex: 0,
      dwellUntil: 0,
      isMoving: false,
      alive: true
    };
    setRoute(agent, plannedDay(agent));
    agents.push(agent);
  }
  recordHistory();
}

function infectiousness(agent) {
  if (agent.state === "E") {
    const t = Math.max(0, day - agent.exposedAt);
    const frac = t / PARAMS.incubation_period;
    return frac > 0.55 ? Math.min(0.35, (frac - 0.55) * 0.8) : 0;
  }
  if (agent.state === "I") {
    const t = Math.max(0, day - agent.infectedAt);
    const frac = t / PARAMS.infectious_period;
    return Math.max(0.12, 1 - frac * 0.72);
  }
  return 0;
}

function progressDisease(agent) {
  if (agent.state === "E" && day - agent.exposedAt >= PARAMS.incubation_period) {
    agent.state = "I";
    agent.infectedAt = day;
    agent.viralLoad = 1;
    agent.route = plannedDay(agent);
    agent.routeIndex = 0;
  } else if (agent.state === "I" && day - agent.infectedAt >= PARAMS.infectious_period) {
    const deathRisk = PARAMS.p_death * (agent.group === "senior" ? 3.2 : agent.group === "adult" ? 1.0 : 0.25) * (agent.vaccinated ? 0.2 : 1);
    if (Math.random() < deathRisk) {
      agent.state = "D";
      agent.alive = false;
      agent.isMoving = false;
    } else {
      agent.state = "R";
      agent.hospitalized = false;
      agent.immunity = Math.max(agent.immunity, 0.82);
      agent.route = plannedDay(agent);
      agent.routeIndex = 0;
    }
  }
  agent.viralLoad = infectiousness(agent);
}

function advanceRoute(agent) {
  if (!agent.alive) return;
  if (day >= Math.floor(day) + 0.995) return;
  if (!agent.isMoving && day >= agent.dwellUntil) {
    agent.routeIndex += 1;
    if (agent.routeIndex >= agent.route.length) {
      setRoute(agent, plannedDay(agent));
      return;
    }
    agent.targetPOI = agent.route[agent.routeIndex];
    const p = insidePoiPosition(agent.targetPOI);
    agent.tx = p.x;
    agent.ty = p.y;
    agent.isMoving = true;
  }
}

function moveAgent(agent, dtDays) {
  if (!agent.alive) return;
  advanceRoute(agent);
  if (agent.isMoving) {
    const dx = agent.tx - agent.x;
    const dy = agent.ty - agent.y;
    const dist = Math.hypot(dx, dy);
    const speed = agent.socialDistancing ? 260 : 310;
    const step = speed * dtDays;
    if (dist <= step || dist < 1) {
      agent.x = agent.tx;
      agent.y = agent.ty;
      agent.currentPOI = agent.targetPOI;
      agent.isMoving = false;
      const dwell = POI[agent.currentPOI].dwell * rand(0.72, 1.25);
      agent.dwellUntil = day + dwell;
    } else {
      agent.x += dx / dist * step;
      agent.y += dy / dist * step;
    }
  } else {
    const poi = POI[agent.currentPOI];
    const jitter = agent.socialDistancing ? 10 : 18;
    agent.x += (poi.x - agent.x) * 0.004 + rand(-jitter, jitter) * dtDays;
    agent.y += (poi.y - agent.y) * 0.004 + rand(-jitter, jitter) * dtDays;
  }
  if (agent.contactCooldown > 0) agent.contactCooldown -= dtDays;
}

function localRiskAt(agent) {
  let base = agent.isMoving ? PARAMS.p_transit : POI[agent.currentPOI].pBase;
  if (agent.wearsMask) base *= 0.55;
  if (agent.socialDistancing) base *= 0.68;
  if (agent.vaccinated) base *= 0.48;
  return base * (1 - agent.immunity);
}

function exposeAgent(s, source) {
  if (s.state !== "S") return;
  s.state = "E";
  s.exposedAt = day;
  s.infectedAt = null;
  s.viralLoad = 0;
  s.contactCooldown = 0.2;
  source.contactCooldown = 0.07;
}

function resolveContactTransmission(dtDays) {
  const active = agents.filter(a => a.alive && a.state !== "D");
  const cellSize = 24;
  const grid = new Map();
  for (const a of active) {
    const key = Math.floor(a.x / cellSize) + "," + Math.floor(a.y / cellSize);
    if (!grid.has(key)) grid.set(key, []);
    grid.get(key).push(a);
  }
  for (const a of active) {
    if (a.state !== "S" || a.contactCooldown > 0) continue;
    const cx = Math.floor(a.x / cellSize);
    const cy = Math.floor(a.y / cellSize);
    for (let gx = cx - 1; gx <= cx + 1; gx++) {
      for (let gy = cy - 1; gy <= cy + 1; gy++) {
        const list = grid.get(gx + "," + gy);
        if (!list) continue;
        for (const b of list) {
          if (b.id === a.id || b.contactCooldown > 0) continue;
          const inf = infectiousness(b);
          if (inf <= 0) continue;
          const dist = Math.hypot(a.x - b.x, a.y - b.y);
          const radius = (a.radius + b.radius) * (a.socialDistancing ? 2.2 : 2.8);
          if (dist > radius) continue;
          const samePlace = a.isMoving === b.isMoving && (a.isMoving || a.currentPOI === b.currentPOI);
          const routeBonus = a.isMoving && b.isMoving ? 0.7 : 1.0;
          const p = localRiskAt(a) * inf * routeBonus * dtDays * 0.95;
          if (samePlace && Math.random() < p) {
            exposeAgent(a, b);
            return;
          }
        }
      }
    }
  }
}

function ambientPoiTransmission(dtDays) {
  for (const poiName of Object.keys(POI)) {
    const present = agents.filter(a => a.alive && !a.isMoving && a.currentPOI === poiName);
    const pressure = present.reduce((sum, a) => sum + infectiousness(a), 0);
    if (pressure <= 0) continue;
    for (const s of present) {
      if (s.state !== "S" || s.contactCooldown > 0) continue;
      const density = Math.min(2.5, present.length / 42);
      const p = localRiskAt(s) * pressure * density * dtDays * 0.16;
      if (Math.random() < p) exposeAgent(s, pick(present.filter(a => infectiousness(a) > 0)));
    }
  }
}

function counts() {
  const out = { S: 0, E: 0, I: 0, R: 0, D: 0 };
  for (const a of agents) out[a.state] += 1;
  return out;
}

function recordHistory() {
  history.push({ day, ...counts() });
  if (history.length > 180) history.shift();
}

function updateHud() {
  const c = counts();
  document.getElementById("day").textContent = "Dzien " + day.toFixed(1);
  for (const k of ["S", "E", "I", "R", "D"]) {
    document.getElementById(k).textContent = k + " " + c[k];
  }
}

function drawBackground() {
  ctx.fillStyle = "#071014";
  ctx.fillRect(0, 0, CW, CH);
  const grd = ctx.createLinearGradient(0, 0, MAP_W, CH);
  grd.addColorStop(0, "rgba(38, 70, 83, .18)");
  grd.addColorStop(0.55, "rgba(7, 16, 20, .02)");
  grd.addColorStop(1, "rgba(7, 16, 20, 0)");
  ctx.fillStyle = grd;
  ctx.fillRect(0, 0, MAP_W, CH);
  ctx.strokeStyle = "#18303d";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(MAP_W + 10, 42);
  ctx.lineTo(MAP_W + 10, CH - 26);
  ctx.stroke();
}

function drawRoutes() {
  for (const [a, b] of ROUTES) {
    const pa = POI[a];
    const pb = POI[b];
    ctx.strokeStyle = a === "HOUSEHOLD" ? "rgba(70, 112, 145, .34)" : "rgba(70, 112, 145, .18)";
    ctx.lineWidth = a === "HOUSEHOLD" ? 8 : 3;
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(pa.x, pa.y);
    ctx.lineTo(pb.x, pb.y);
    ctx.stroke();
    ctx.strokeStyle = "rgba(151, 196, 219, .12)";
    ctx.lineWidth = 1;
    ctx.stroke();
  }
}

function drawPoi() {
  for (const [name, poi] of Object.entries(POI)) {
    const present = agents.filter(a => a.alive && !a.isMoving && a.currentPOI === name);
    const inf = present.reduce((s, a) => s + (a.state === "I" ? 1 : 0), 0);
    if (inf > 0) {
      const glow = ctx.createRadialGradient(poi.x, poi.y, poi.r * 0.45, poi.x, poi.y, poi.r * 1.8);
      glow.addColorStop(0, "rgba(239, 71, 111, .18)");
      glow.addColorStop(1, "rgba(239, 71, 111, 0)");
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(poi.x, poi.y, poi.r * 1.8, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.fillStyle = "#0d1820";
    ctx.strokeStyle = inf > 0 ? "#ef476f" : "#315067";
    ctx.lineWidth = inf > 0 ? 2.2 : 1.3;
    ctx.beginPath();
    ctx.arc(poi.x, poi.y, poi.r, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "#e6edf3";
    ctx.font = "700 15px ui-monospace, monospace";
    ctx.textAlign = "center";
    ctx.fillText(poi.label, poi.x, poi.y - poi.r - 12);
    ctx.fillStyle = inf > 0 ? "#ffb3c1" : "#7f97a5";
    ctx.font = "11px ui-monospace, monospace";
    const exposed = present.filter(a => a.state === "E").length;
    ctx.fillText("I:" + inf + " E:" + exposed + " N:" + present.length, poi.x, poi.y + poi.r + 18);
  }
}

function drawAgents() {
  for (const a of agents) {
    ctx.globalAlpha = a.state === "D" ? 0.55 : 0.95;
    ctx.fillStyle = COLORS[a.state];
    ctx.beginPath();
    ctx.arc(a.x, a.y, a.radius, 0, Math.PI * 2);
    ctx.fill();
    if (a.hospitalized && a.state === "I") {
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 1;
      ctx.stroke();
    }
  }
  ctx.globalAlpha = 1;
}

function roundedPanel(x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

function drawChart() {
  const c = counts();
  ctx.fillStyle = "#0d1820";
  ctx.strokeStyle = "#274559";
  ctx.lineWidth = 1;
  roundedPanel(CHART_X - 22, 58, CHART_W + 44, 560, 8);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = "#e6edf3";
  ctx.font = "700 17px ui-monospace, monospace";
  ctx.textAlign = "left";
  ctx.fillText("Krzywe SEIRD", CHART_X, 86);

  ctx.strokeStyle = "#203848";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = CHART_Y + CHART_H * i / 4;
    ctx.beginPath();
    ctx.moveTo(CHART_X, y);
    ctx.lineTo(CHART_X + CHART_W, y);
    ctx.stroke();
  }
  ctx.strokeStyle = "#34546a";
  ctx.strokeRect(CHART_X, CHART_Y, CHART_W, CHART_H);

  const maxN = PARAMS.n_agents;
  for (const k of ["S", "E", "I", "R", "D"]) {
    ctx.strokeStyle = COLORS[k];
    ctx.lineWidth = 2;
    ctx.beginPath();
    history.forEach((h, i) => {
      const x = CHART_X + (history.length <= 1 ? 0 : i / (history.length - 1) * CHART_W);
      const y = CHART_Y + CHART_H - h[k] / maxN * CHART_H;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  }

  const legendY = CHART_Y + CHART_H + 38;
  ["S", "E", "I", "R", "D"].forEach((k, i) => {
    ctx.fillStyle = COLORS[k];
    ctx.fillRect(CHART_X + i * 58, legendY, 18, 3);
    ctx.fillStyle = "#b8c7d0";
    ctx.font = "12px ui-monospace, monospace";
    ctx.fillText(k + " " + c[k], CHART_X + i * 58, legendY + 22);
  });
}

function draw() {
  drawBackground();
  drawRoutes();
  drawPoi();
  drawAgents();
  drawChart();
}

function tick(dtSeconds) {
  const speed = Number(document.getElementById("speed").value);
  const dtDays = Math.min(0.035, dtSeconds / PARAMS.day_duration * speed);
  day += dtDays;
  const crossedDay = Math.floor(day) > Math.floor(day - dtDays);
  for (const agent of agents) {
    if (crossedDay && agent.alive) {
      agent.route = plannedDay(agent);
      agent.routeIndex = 0;
      agent.dwellUntil = day + rand(0.02, 0.08);
    }
    progressDisease(agent);
    moveAgent(agent, dtDays);
  }
  resolveContactTransmission(dtDays);
  ambientPoiTransmission(dtDays);
  if (day >= nextHistoryDay) {
    recordHistory();
    nextHistoryDay += 0.2;
  }
  updateHud();
}

function frame(ts) {
  const dt = Math.min(0.05, (ts - lastTs) / 1000);
  lastTs = ts;
  if (running) tick(dt);
  draw();
  requestAnimationFrame(frame);
}

document.getElementById("play").addEventListener("click", () => { running = true; });
document.getElementById("pause").addEventListener("click", () => { running = false; });
document.getElementById("reset").addEventListener("click", () => { createAgents(); running = true; });

createAgents();
requestAnimationFrame(frame);
</script>
</body>
</html>"""


if __name__ == "__main__":
    main()
