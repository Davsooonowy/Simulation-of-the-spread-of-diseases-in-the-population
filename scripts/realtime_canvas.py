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
    "p_base_multiplier": 0.9,
    "p_transit": 0.05,
    "mask_coverage": 0.0,
    "social_distancing_coverage": 0.0,
    "vaccination_coverage": 0.0,
    "lockdown": False,
    "incubation_period": 4,
    "infectious_period": 10,
    "p_death": 0.015,
}


def build_canvas_html(params: dict) -> str:
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
        [data-testid="stSidebar"] { min-width: 310px; }
        iframe { border-radius: 8px; box-shadow: 0 16px 42px rgba(15,23,42,.18); }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.title("Parametry startu")
        with st.form("params_form"):
            n_agents  = st.slider("Liczba agentow", 50, 500, DEFAULT_PARAMS["n_agents"], step=10)
            init_inf  = st.slider("Startowe zakazenia (%)", 1, 20, 4) / 100
            day_dur   = st.slider("Czas dnia (sekundy)", 6, 40, DEFAULT_PARAMS["day_duration"], step=2)
            p_mult    = st.slider("Zakaznosc (mnoznik)", 0.10, 2.00, DEFAULT_PARAMS["p_base_multiplier"], step=0.05)
            p_transit = st.slider("Transmisja w trasie", 0.00, 0.20, DEFAULT_PARAMS["p_transit"], step=0.005)
            incubation = st.slider("Inkubacja (dni)", 2, 10, DEFAULT_PARAMS["incubation_period"])
            infectious = st.slider("Okres zakazny (dni)", 5, 24, DEFAULT_PARAMS["infectious_period"])
            p_death   = st.slider("Smiertelnosc (%)", 0.0, 8.0, DEFAULT_PARAMS["p_death"] * 100, step=0.1) / 100
            vacc_pct  = st.slider("Szczepienia (%) — przy starcie", 0, 100, 0) / 100

            st.divider()
            st.caption("Interwencje (lockdown, maseczki, dystans) mozna zmieniac **na zywo** w panelu wewnątrz symulacji — bez restartu.")
            submitted = st.form_submit_button("Apply & Start", type="primary")

        if submitted or "active_params" not in st.session_state:
            st.session_state.active_params = {
                "n_agents": n_agents,
                "initial_infected_frac": init_inf,
                "day_duration": day_dur,
                "p_base_multiplier": p_mult,
                "p_transit": p_transit,
                "mask_coverage": 0.0,
                "social_distancing_coverage": 0.0,
                "vaccination_coverage": vacc_pct,
                "lockdown": False,
                "incubation_period": incubation,
                "infectious_period": infectious,
                "p_death": p_death,
            }
            st.session_state.sim_started_at = time.time()

    st.markdown("## Symulacja pandemii — plynny canvas")
    st.components.v1.html(
        build_canvas_html(st.session_state.active_params),
        height=760,
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
  --border: #203848;
  --text: #e6edf3;
  --muted: #7f97a5;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: 100%; height: 100%; overflow: hidden; background: var(--bg); }
body { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
canvas { display: block; width: 100%; height: auto; background: var(--bg); }

#toolbar {
  position: fixed; top: 10px; right: 12px; z-index: 4;
  display: flex; align-items: center; gap: 8px;
}
button {
  min-width: 38px; height: 30px; padding: 0 11px;
  border: 1px solid #315067; border-radius: 6px;
  background: rgba(13,24,32,.92); color: var(--text);
  font: 12px/1 ui-monospace, monospace; cursor: pointer;
}
button:hover { background: #162a37; }
#speed { accent-color: #74c69d; width: 100px; }

#hud {
  position: fixed; top: 10px; left: 12px; z-index: 4;
  display: flex; gap: 7px; flex-wrap: wrap;
  color: var(--text); font-size: 12px; pointer-events: none;
}
#hud span {
  padding: 5px 8px; border: 1px solid rgba(49,80,103,.8);
  background: rgba(13,24,32,.85); border-radius: 6px;
}
#reff { font-weight: 700; }

/* Live intervention panel — lives inside the iframe */
#live-panel {
  position: fixed; bottom: 14px; right: 14px; z-index: 4;
  background: rgba(10,20,28,.94); border: 1px solid #2a4a60;
  border-radius: 10px; padding: 12px 16px; width: 218px;
  color: var(--text); font-size: 11px;
}
#live-panel .lp-title {
  font-size: 12px; font-weight: 700; color: #a8c8d8;
  margin-bottom: 10px; letter-spacing: .03em;
}
.lp-row { display: flex; flex-direction: column; gap: 3px; margin-bottom: 9px; }
.lp-row:last-child { margin-bottom: 0; }
.lp-label { display: flex; justify-content: space-between; }
.lp-label b { color: #74c69d; }
.lp-row input[type="range"] { width: 100%; accent-color: #74c69d; cursor: pointer; }
.lp-row input[type="checkbox"] { accent-color: #ef476f; cursor: pointer; width: 14px; height: 14px; }
.lp-check { display: flex; align-items: center; gap: 7px; cursor: pointer; }
.lp-check span { color: var(--text); }
#lk-indicator {
  display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  background: #555; margin-left: 4px; transition: background .3s;
}
#lk-indicator.on { background: #ef476f; box-shadow: 0 0 6px #ef476f; }
</style>
</head>
<body>

<div id="hud">
  <span id="day">Dzien 0.0</span>
  <span id="hS" style="color:#55aaff">S 0</span>
  <span id="hE" style="color:#f6b352">E 0</span>
  <span id="hI" style="color:#ef476f">I 0</span>
  <span id="hR" style="color:#74c69d">R 0</span>
  <span id="hD" style="color:#8899aa">D 0</span>
  <span id="reff">R&#8337; —</span>
</div>

<div id="toolbar">
  <button id="btn-play">Play</button>
  <button id="btn-pause">Pause</button>
  <button id="btn-reset">Reset</button>
  <input id="speed" type="range" min="0.4" max="3" step="0.1" value="1" title="Predkosc">
</div>

<div id="live-panel">
  <div class="lp-title">Interwencje — na zywo <span id="lk-indicator"></span></div>
  <label class="lp-row lp-check">
    <input type="checkbox" id="lk-cb">
    <span>Lockdown (zamknij biura i szkoly)</span>
  </label>
  <div class="lp-row">
    <div class="lp-label"><span>Maseczki</span><b id="mk-val">0%</b></div>
    <input type="range" id="mk-sl" min="0" max="100" step="5" value="0">
  </div>
  <div class="lp-row">
    <div class="lp-label"><span>Dystans spoleczny</span><b id="sd-val">0%</b></div>
    <input type="range" id="sd-sl" min="0" max="100" step="5" value="0">
  </div>
</div>

<canvas id="sim"></canvas>

<script>
const PARAMS = __PARAMS_JSON__;

// ─── canvas setup ─────────────────────────────────────────────────────────────
const CW = 1180, CH = 720;
const MAP_W = 770;
const CHART_X = 810, CHART_Y = 108, CHART_W = 320, CHART_H = 390;

const canvas = document.getElementById("sim");
const ctx = canvas.getContext("2d");
canvas.width = CW;
canvas.height = CH;

function resizeCanvas() {
  const w = window.innerWidth;
  canvas.style.width = w + "px";
  canvas.style.height = Math.round(w * CH / CW) + "px";
}
resizeCanvas();
window.addEventListener("resize", resizeCanvas);

// ─── live intervention readers (read DOM every tick) ─────────────────────────
function getLockdown()  { return document.getElementById("lk-cb").checked; }
function getMaskCov()   { return Number(document.getElementById("mk-sl").value) / 100; }
function getSDCov()     { return Number(document.getElementById("sd-sl").value) / 100; }

// Update value labels
function bindSlider(slId, valId) {
  const sl = document.getElementById(slId);
  const vl = document.getElementById(valId);
  const upd = () => { vl.textContent = sl.value + "%"; };
  sl.addEventListener("input", upd);
  upd();
}
bindSlider("mk-sl", "mk-val");
bindSlider("sd-sl", "sd-val");
document.getElementById("lk-cb").addEventListener("change", () => {
  document.getElementById("lk-indicator").className =
    getLockdown() ? "on" : "";
});

// ─── colors & POI definitions ─────────────────────────────────────────────────
const COLORS = { S:"#55aaff", E:"#f6b352", I:"#ef476f", R:"#74c69d", D:"#5b6670" };

// pBase = base transmission probability at this location (before multipliers)
const POI_BASE = {
  HOUSEHOLD:  { x:145, y:345, r:78,  label:"Domy",    pBase:0.22, dwell:0.20 },
  SCHOOL:     { x:340, y:170, r:58,  label:"Szkola",   pBase:0.26, dwell:0.22 },
  OFFICE:     { x:555, y:178, r:62,  label:"Biuro",    pBase:0.15, dwell:0.22 },
  SHOP:       { x:660, y:360, r:52,  label:"Sklep",    pBase:0.08, dwell:0.12 },
  HEALTHCARE: { x:352, y:552, r:58,  label:"Szpital",  pBase:0.05, dwell:0.25 },
  PARK:       { x:560, y:540, r:58,  label:"Park",     pBase:0.02, dwell:0.15 },
};
// Scale by user multiplier once at load
const POI = {};
for (const [k, v] of Object.entries(POI_BASE)) {
  POI[k] = { ...v, pBase: v.pBase * PARAMS.p_base_multiplier };
}

// Effective pBase — called every time, respects live lockdown
function poiEffBase(poiName) {
  if (poiName === "HOUSEHOLD") return 0;  // handled per-family below
  const base = POI[poiName].pBase;
  if (!getLockdown()) return base;
  if (poiName === "OFFICE" || poiName === "SCHOOL" || poiName === "PARK") return 0;
  if (poiName === "SHOP")       return base * 0.20;
  if (poiName === "HEALTHCARE") return base * 0.35;
  return base;
}

// ─── household clusters (one circle per family) ───────────────────────────────
const FAMILY_SIZE  = 5;
const HH_CX = 145, HH_CY = 345;       // neighbourhood center on canvas
const HH_RADIUS    = 12;               // radius of each family circle
// pBase for in-home transmission — highest (enclosed, prolonged contact)
const HH_P_BASE    = 0.35 * PARAMS.p_base_multiplier;

let households = [];   // filled by createAgents()

function buildHouseholds(n) {
  const nHH  = Math.ceil(n / FAMILY_SIZE);
  const cols = Math.ceil(Math.sqrt(nHH * 1.4));  // slightly wider than tall
  const sp   = 26;                               // spacing between circles
  const offX = -((cols - 1) * sp) / 2;
  const rows = Math.ceil(nHH / cols);
  const offY = -((rows - 1) * sp) / 2;
  const hh   = [];
  for (let i = 0; i < nHH; i++) {
    const col = i % cols, row = Math.floor(i / cols);
    hh.push({
      id: i,
      x: HH_CX + offX + col * sp + rand(-2, 2),
      y: HH_CY + offY + row * sp + rand(-2, 2),
    });
  }
  return hh;
}

function insideHousehold(agent) {
  const hh = households[agent.householdId];
  const th = rand(0, Math.PI * 2);
  const r  = HH_RADIUS * Math.sqrt(Math.random()) * 0.82;
  return { x: hh.x + Math.cos(th) * r, y: hh.y + Math.sin(th) * r };
}

const ROUTES = [
  ["HOUSEHOLD","SCHOOL"],["HOUSEHOLD","OFFICE"],["HOUSEHOLD","SHOP"],
  ["HOUSEHOLD","HEALTHCARE"],["HOUSEHOLD","PARK"],
  ["SCHOOL","OFFICE"],["OFFICE","SHOP"],["SHOP","PARK"],["HEALTHCARE","PARK"],
];

// ─── state ────────────────────────────────────────────────────────────────────
let agents = [];
let day = 0;
let running = true;
let lastTs = performance.now();
let history = [];
let nextHistoryDay = 0;
// Ring buffer for R_eff: store (day, new_exposures)
let exposureLog = [];   // { d: day }

// ─── helpers ──────────────────────────────────────────────────────────────────
function rand(a, b)  { return a + Math.random() * (b - a); }
function pick(arr)   { return arr[Math.floor(Math.random() * arr.length)]; }

function insidePOI(name) {
  const p = POI[name];
  const th = rand(0, Math.PI * 2);
  const r  = p.r * Math.sqrt(Math.random()) * 0.78;
  return { x: p.x + Math.cos(th) * r, y: p.y + Math.sin(th) * r };
}

function ageGroup(age) {
  return age < 18 ? "child" : age <= 65 ? "adult" : "senior";
}

// ─── route planning (reads live lockdown / SD) ────────────────────────────────
function plannedDay(agent) {
  const lockdown = getLockdown();
  const sdCov    = getSDCov();
  const effSD    = agent.socialDistancing || sdCov > 0.5;

  // Self-isolating symptomatic → stay home (or go to hospital if severe)
  if (agent.selfIsolating && agent.state === "I") {
    const hospRisk = agent.group === "senior" ? 0.38 : agent.group === "adult" ? 0.18 : 0.07;
    agent.hospitalized = agent.hospitalized || Math.random() < hospRisk;
    if (agent.hospitalized) return ["HOUSEHOLD", "HEALTHCARE", "HOUSEHOLD"];
    return ["HOUSEHOLD", "HOUSEHOLD"];
  }

  const route = ["HOUSEHOLD"];

  if (!agent.hospitalized) {
    // Work / school (blocked by lockdown)
    if (!lockdown) {
      if (agent.group === "child")  route.push("SCHOOL");
      else if (agent.group === "adult") {
        // Seniors never go to office; some adults WFH under high SD
        if (!(effSD && Math.random() < 0.45)) route.push("OFFICE");
      }
    }
    // Shop — children don't go alone; lockdown restricts heavily
    const shopP = lockdown ? 0.04 : (effSD ? 0.10 : 0.28);
    if (agent.group !== "child" && Math.random() < shopP) route.push("SHOP");
    // Park — completely blocked during lockdown
    const parkP = lockdown ? 0.0 : (agent.group === "senior" ? 0.30 : effSD ? 0.08 : 0.20);
    if (agent.state !== "I" && Math.random() < parkP) route.push("PARK");
  }

  // Infectious agents: hospitalization decision
  // During lockdown only seniors go to hospital (others isolate at home)
  if (agent.state === "I") {
    const hospRisk = lockdown
      ? (agent.group === "senior" ? 0.40 : 0.0)
      : (agent.group === "senior" ? 0.38 : agent.group === "adult" ? 0.18 : 0.07);
    agent.hospitalized = agent.hospitalized || (!agent.selfIsolating && Math.random() < hospRisk);
    if (agent.hospitalized) route.splice(1, route.length - 1, "HEALTHCARE");
  } else {
    agent.hospitalized = false;
  }

  route.push("HOUSEHOLD");
  return route;
}

function poiPosition(agent, poiName) {
  return poiName === "HOUSEHOLD" ? insideHousehold(agent) : insidePOI(poiName);
}

function setRoute(agent, route) {
  agent.route = route;
  agent.routeIndex = 0;
  agent.currentPOI = route[0];
  agent.targetPOI  = route[0];
  agent.dwellUntil = day + 0.05;
  const p = poiPosition(agent, route[0]);
  agent.x = p.x; agent.y = p.y;
  agent.tx = p.x; agent.ty = p.y;
  agent.isMoving = false;
}

// ─── agent creation ───────────────────────────────────────────────────────────
function createAgents() {
  agents = [];
  day = 0;
  history = [];
  exposureLog = [];
  nextHistoryDay = 0;

  const n = PARAMS.n_agents;
  households = buildHouseholds(n);

  for (let i = 0; i < n; i++) {
    const age = Math.floor(rand(1, 88));
    const r0  = Math.random();
    const state = r0 < PARAMS.initial_infected_frac * 0.6 ? "I" :
                  r0 < PARAMS.initial_infected_frac       ? "E" : "S";
    const vaccinated = Math.random() < PARAMS.vaccination_coverage;

    const householdId = i % households.length;
    // Temporarily stub so insideHousehold works before agent is fully built
    const tmpAgent = { householdId };
    const p = insideHousehold(tmpAgent);
    const agent = {
      id: i,
      x: p.x, y: p.y, tx: p.x, ty: p.y,
      radius: n > 320 ? 2.5 : n > 220 ? 3.0 : 3.6,
      state,
      age,
      group: ageGroup(age),
      vaccinated,
      immunity: vaccinated ? 0.55 : 0,
      // Mask / SD are now population-level (read from sliders), not per-agent
      // We keep socialDistancing as individual trait for movement speed only
      socialDistancing: false,
      infectedAt:  state === "I" ? -(Math.random() * PARAMS.infectious_period * 0.7) : null,
      exposedAt:   state === "E" ? -(Math.random() * PARAMS.incubation_period  * 0.85) : null,
      viralLoad:   state === "I" ? rand(0.3, 0.95) : 0,
      contactCooldown: 0,
      hospitalized: false,
      selfIsolating: false,
      asymptomatic:  false,
      infPeriodMult: rand(0.82, 1.22),
      householdId,
      currentPOI: "HOUSEHOLD",
      targetPOI:  "HOUSEHOLD",
      route: [], routeIndex: 0,
      dwellUntil: rand(0.05, 0.5),
      isMoving: false,
      alive: true,
    };
    setRoute(agent, plannedDay(agent));
    agents.push(agent);
  }
  recordHistory();
}

// ─── disease model ────────────────────────────────────────────────────────────
function infectiousness(agent) {
  if (agent.state === "E") {
    const frac = Math.max(0, day - agent.exposedAt) / PARAMS.incubation_period;
    // Pre-symptomatic shedding starts at 55% of incubation
    return frac > 0.55 ? Math.min(0.30, (frac - 0.55) * 0.75) : 0;
  }
  if (agent.state === "I") {
    const period = PARAMS.infectious_period * (agent.infPeriodMult || 1);
    const frac = Math.max(0, day - agent.infectedAt) / period;
    const base = Math.max(0.08, 1 - frac * 0.76);
    return agent.asymptomatic ? base * 0.55 : base;
  }
  return 0;
}

function progressDisease(agent) {
  if (agent.state === "E" && day - agent.exposedAt >= PARAMS.incubation_period) {
    agent.state = "I";
    agent.infectedAt = day;
    agent.viralLoad  = 1;
    // Determine symptomatic profile at onset
    agent.asymptomatic  = Math.random() < 0.35;          // 35% asymptomatic
    agent.selfIsolating = !agent.asymptomatic && Math.random() < 0.62; // 62% of sympt. isolate
    agent.route = plannedDay(agent);
    agent.routeIndex = 0;

  } else if (agent.state === "I" &&
             day - agent.infectedAt >= PARAMS.infectious_period * (agent.infPeriodMult || 1)) {
    const deathMult = agent.group === "senior" ? 3.5 : agent.group === "adult" ? 1.0 : 0.18;
    const deathRisk = PARAMS.p_death * deathMult * (agent.vaccinated ? 0.15 : 1);
    if (!agent.asymptomatic && Math.random() < deathRisk) {
      agent.state    = "D";
      agent.alive    = false;
      agent.isMoving = false;
    } else {
      agent.state         = "R";
      agent.hospitalized  = false;
      agent.selfIsolating = false;
      agent.asymptomatic  = false;
      agent.immunity      = Math.max(agent.immunity, 0.85);
      agent.route         = plannedDay(agent);
      agent.routeIndex    = 0;
    }
  }
  agent.viralLoad = infectiousness(agent);
}

// ─── movement ─────────────────────────────────────────────────────────────────
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
    const p = poiPosition(agent, agent.targetPOI);
    agent.tx = p.x; agent.ty = p.y;
    agent.isMoving = true;
  }
}

function moveAgent(agent, dtDays) {
  if (!agent.alive) return;
  advanceRoute(agent);
  if (agent.isMoving) {
    const dx = agent.tx - agent.x, dy = agent.ty - agent.y;
    const dist = Math.hypot(dx, dy);
    // Self-isolating / SD agents move slower (more cautious)
    const speed = (agent.selfIsolating || getSDCov() > 0.6) ? 900 : 1250;
    const step  = speed * dtDays;
    if (dist <= step || dist < 1) {
      agent.x = agent.tx; agent.y = agent.ty;
      agent.currentPOI = agent.targetPOI;
      agent.isMoving   = false;
      agent.dwellUntil = day + POI[agent.currentPOI].dwell * rand(0.75, 1.30);
    } else {
      agent.x += dx / dist * step;
      agent.y += dy / dist * step;
    }
  } else {
    // Gentle jitter while dwelling
    const poi    = POI[agent.currentPOI];
    const jitter = 16;
    agent.x += (poi.x - agent.x) * 0.005 + rand(-jitter, jitter) * dtDays;
    agent.y += (poi.y - agent.y) * 0.005 + rand(-jitter, jitter) * dtDays;
  }
  if (agent.contactCooldown > 0) agent.contactCooldown -= dtDays;
}

// ─── transmission ─────────────────────────────────────────────────────────────
// localRiskAt reads LIVE mask & SD coverage every call
function localRiskAt(agent) {
  let base;
  if (agent.isMoving) {
    base = PARAMS.p_transit;
  } else if (agent.currentPOI === "HOUSEHOLD") {
    base = HH_P_BASE;  // per-family pBase — higher than public places
  } else {
    base = poiEffBase(agent.currentPOI);
  }
  const maskR = getMaskCov() * 0.46;
  const sdR   = getSDCov()   * 0.30;
  let p = base * (1 - maskR) * (1 - sdR);
  if (agent.vaccinated) p *= 0.28;
  return p * (1 - agent.immunity);
}

function exposeAgent(s, source) {
  if (s.state !== "S") return;
  s.state          = "E";
  s.exposedAt      = day;
  s.infectedAt     = null;
  s.viralLoad      = 0;
  s.contactCooldown = 0.18;
  source.contactCooldown = 0.06;
  exposureLog.push({ d: day });
}

// Transit transmission (moving agents that pass close to each other)
function resolveContactTransmission(dtDays) {
  const active   = agents.filter(a => a.alive && a.state !== "D" && a.isMoving);
  const cellSize = 28;
  const grid     = new Map();
  for (const a of active) {
    const key = `${Math.floor(a.x / cellSize)},${Math.floor(a.y / cellSize)}`;
    if (!grid.has(key)) grid.set(key, []);
    grid.get(key).push(a);
  }
  for (const a of active) {
    if (a.state !== "S" || a.contactCooldown > 0) continue;
    const cx = Math.floor(a.x / cellSize);
    const cy = Math.floor(a.y / cellSize);
    outer: for (let gx = cx - 1; gx <= cx + 1; gx++) {
      for (let gy = cy - 1; gy <= cy + 1; gy++) {
        const list = grid.get(`${gx},${gy}`);
        if (!list) continue;
        for (const b of list) {
          if (b.id === a.id || b.contactCooldown > 0) continue;
          const inf = infectiousness(b);
          if (inf <= 0) continue;
          if (Math.hypot(a.x - b.x, a.y - b.y) > 38) continue;
          const p = localRiskAt(a) * inf * dtDays * 5.5;
          if (Math.random() < p) { exposeAgent(a, b); break outer; }
        }
      }
    }
  }
}

// Ambient transmission for agents co-dwelling at the same POI
function ambientPoiTransmission(dtDays) {
  // ── Public POIs: all present agents can interact ──────────────────────────
  for (const poiName of Object.keys(POI)) {
    if (poiName === "HOUSEHOLD") continue;   // handled per-family below
    const present    = agents.filter(a => a.alive && !a.isMoving && a.currentPOI === poiName);
    const infectious = present.filter(a => infectiousness(a) > 0);
    if (!infectious.length) continue;
    const pressure = infectious.reduce((s, a) => s + infectiousness(a), 0);
    for (const s of present) {
      if (s.state !== "S" || s.contactCooldown > 0) continue;
      const density = Math.min(4.0, present.length / 22);
      const p = localRiskAt(s) * pressure * density * dtDays * 0.48;
      if (Math.random() < p) exposeAgent(s, pick(infectious));
    }
  }

  // ── Household: transmission only within the same family ──────────────────
  const byHH = new Map();
  for (const a of agents) {
    if (!a.alive || a.isMoving || a.currentPOI !== "HOUSEHOLD") continue;
    if (!byHH.has(a.householdId)) byHH.set(a.householdId, []);
    byHH.get(a.householdId).push(a);
  }
  for (const present of byHH.values()) {
    const infectious = present.filter(a => infectiousness(a) > 0);
    if (!infectious.length) continue;
    const pressure = infectious.reduce((s, a) => s + infectiousness(a), 0);
    for (const s of present) {
      if (s.state !== "S" || s.contactCooldown > 0) continue;
      // Small closed group → no density scaling needed, just pressure × base risk
      const p = localRiskAt(s) * pressure * dtDays * 0.60;
      if (Math.random() < p) exposeAgent(s, pick(infectious));
    }
  }
}

// ─── statistics ───────────────────────────────────────────────────────────────
function counts() {
  const c = { S:0, E:0, I:0, R:0, D:0 };
  for (const a of agents) c[a.state]++;
  return c;
}

function calcReff() {
  if (day < 2) return null;
  const window = Math.min(day, 7);   // 7-day rolling window
  const cutoff = day - window;
  const recent = exposureLog.filter(e => e.d >= cutoff).length;
  const avgI   = history
    .filter(h => h.day >= cutoff)
    .reduce((s, h) => s + h.I, 0) / Math.max(1, history.filter(h => h.day >= cutoff).length);
  if (avgI < 0.5) return null;
  return (recent / window) * (PARAMS.infectious_period / avgI);
}

function recordHistory() {
  history.push({ day, ...counts() });
  if (history.length > 200) history.shift();
}

// ─── HUD ─────────────────────────────────────────────────────────────────────
function updateHud() {
  const c = counts();
  document.getElementById("day").textContent = "Dzien " + day.toFixed(1);
  document.getElementById("hS").textContent  = "S " + c.S;
  document.getElementById("hE").textContent  = "E " + c.E;
  document.getElementById("hI").textContent  = "I " + c.I;
  document.getElementById("hR").textContent  = "R " + c.R;
  document.getElementById("hD").textContent  = "D " + c.D;
  const reff = calcReff();
  const rEl  = document.getElementById("reff");
  if (reff === null) {
    rEl.textContent = "Rₗ —";
    rEl.style.color = "";
  } else {
    rEl.textContent = "Rₗ " + reff.toFixed(2);
    rEl.style.color = reff > 1.5 ? "#ef476f" : reff > 1 ? "#f6b352" : "#74c69d";
  }
}

// ─── drawing ─────────────────────────────────────────────────────────────────
function drawBackground() {
  ctx.fillStyle = "#071014";
  ctx.fillRect(0, 0, CW, CH);
  const grd = ctx.createLinearGradient(0, 0, MAP_W, CH);
  grd.addColorStop(0,    "rgba(38,70,83,.15)");
  grd.addColorStop(0.6,  "rgba(7,16,20,.02)");
  grd.addColorStop(1,    "rgba(7,16,20,0)");
  ctx.fillStyle = grd;
  ctx.fillRect(0, 0, MAP_W, CH);
  // divider line
  ctx.strokeStyle = "#18303d"; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(MAP_W + 10, 40); ctx.lineTo(MAP_W + 10, CH - 20); ctx.stroke();
}

function drawRoutes() {
  const lk = getLockdown();
  for (const [a, b] of ROUTES) {
    const pa = POI[a], pb = POI[b];
    const isBlocked = lk && (b === "OFFICE" || b === "SCHOOL" || b === "PARK" || b === "HEALTHCARE");
    const alpha  = isBlocked ? 0.04 : (a === "HOUSEHOLD" ? 0.32 : 0.15);
    ctx.strokeStyle = `rgba(70,112,145,${alpha})`;
    ctx.lineWidth   = a === "HOUSEHOLD" ? 7 : 3;
    ctx.lineCap     = "round";
    ctx.beginPath(); ctx.moveTo(pa.x, pa.y); ctx.lineTo(pb.x, pb.y); ctx.stroke();
  }
}

function drawPoi() {
  const lk = getLockdown();

  // ── Household neighbourhood: one small circle per family ─────────────────
  // Neighbourhood background halo
  ctx.fillStyle = "rgba(10,22,30,0.55)";
  ctx.beginPath(); ctx.arc(HH_CX, HH_CY, 88, 0, Math.PI*2); ctx.fill();
  ctx.strokeStyle = "#1a3040"; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.arc(HH_CX, HH_CY, 88, 0, Math.PI*2); ctx.stroke();

  for (const hh of households) {
    const hhAgents = agents.filter(a => a.alive && !a.isMoving &&
                                        a.currentPOI === "HOUSEHOLD" &&
                                        a.householdId === hh.id);
    const hasI = hhAgents.some(a => a.state === "I");
    const hasE = hhAgents.some(a => a.state === "E");
    if (hasI) {
      const glow = ctx.createRadialGradient(hh.x, hh.y, 0, hh.x, hh.y, HH_RADIUS * 2.5);
      glow.addColorStop(0, "rgba(239,71,111,.22)");
      glow.addColorStop(1, "rgba(239,71,111,0)");
      ctx.fillStyle = glow;
      ctx.beginPath(); ctx.arc(hh.x, hh.y, HH_RADIUS * 2.5, 0, Math.PI*2); ctx.fill();
    }
    ctx.fillStyle   = hhAgents.length ? "#0d1820" : "#080f14";
    ctx.strokeStyle = hasI ? "#ef476f" : (hasE ? "#f6b352" : "#2a4456");
    ctx.lineWidth   = hasI ? 1.8 : (hhAgents.length ? 0.9 : 0.4);
    ctx.beginPath(); ctx.arc(hh.x, hh.y, HH_RADIUS, 0, Math.PI*2); ctx.fill(); ctx.stroke();
  }
  // Neighbourhood label
  ctx.fillStyle = "#e6edf3"; ctx.font = "700 14px ui-monospace,monospace";
  ctx.textAlign = "center";
  ctx.fillText("Domy", HH_CX, HH_CY - 94);
  // Summary counts for the neighbourhood
  const hhAll = agents.filter(a => a.alive && !a.isMoving && a.currentPOI === "HOUSEHOLD");
  const hhI = hhAll.filter(a => a.state === "I").length;
  const hhE = hhAll.filter(a => a.state === "E").length;
  if (hhAll.length) {
    ctx.fillStyle = hhI > 0 ? "#ffb3c1" : "#6a8a9a";
    ctx.font = "10px ui-monospace,monospace";
    ctx.fillText(`I:${hhI} E:${hhE} N:${hhAll.length}`, HH_CX, HH_CY + 96);
  }

  // ── Public POIs ───────────────────────────────────────────────────────────
  for (const [name, poi] of Object.entries(POI)) {
    if (name === "HOUSEHOLD") continue;
    const present = agents.filter(a => a.alive && !a.isMoving && a.currentPOI === name);
    const nI      = present.filter(a => a.state === "I").length;
    const nE      = present.filter(a => a.state === "E").length;
    const closed  = lk && (name === "OFFICE" || name === "SCHOOL" || name === "PARK" || name === "HEALTHCARE");

    if (nI > 0 && !closed) {
      const glow = ctx.createRadialGradient(poi.x, poi.y, poi.r * 0.4, poi.x, poi.y, poi.r * 1.9);
      glow.addColorStop(0, "rgba(239,71,111,.16)");
      glow.addColorStop(1, "rgba(239,71,111,0)");
      ctx.fillStyle = glow;
      ctx.beginPath(); ctx.arc(poi.x, poi.y, poi.r * 1.9, 0, Math.PI*2); ctx.fill();
    }
    ctx.fillStyle   = closed ? "#060e14" : "#0d1820";
    ctx.strokeStyle = closed ? "#1a2a38" : (nI > 0 ? "#ef476f" : "#315067");
    ctx.lineWidth   = nI > 0 ? 2.2 : 1.3;
    if (closed) ctx.setLineDash([4, 4]);
    ctx.beginPath(); ctx.arc(poi.x, poi.y, poi.r, 0, Math.PI*2); ctx.fill(); ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = closed ? "#3a5060" : "#e6edf3";
    ctx.font = "700 14px ui-monospace,monospace";
    ctx.textAlign = "center";
    ctx.fillText(closed ? poi.label + " [X]" : poi.label, poi.x, poi.y - poi.r - 10);
    if (present.length) {
      ctx.fillStyle = nI > 0 ? "#ffb3c1" : "#6a8a9a";
      ctx.font = "10px ui-monospace,monospace";
      ctx.fillText(`I:${nI} E:${nE} N:${present.length}`, poi.x, poi.y + poi.r + 16);
    }
  }
}

function drawAgents() {
  for (const a of agents) {
    ctx.globalAlpha = a.state === "D" ? 0.45 : 0.93;
    ctx.fillStyle   = COLORS[a.state];
    ctx.beginPath(); ctx.arc(a.x, a.y, a.radius, 0, Math.PI*2); ctx.fill();
    // White ring for hospitalised; dashed for self-isolating
    if (a.state === "I") {
      if (a.hospitalized) {
        ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 1.2; ctx.stroke();
      } else if (a.selfIsolating) {
        ctx.strokeStyle = "#f6b352"; ctx.lineWidth = 0.8; ctx.stroke();
      }
    }
  }
  ctx.globalAlpha = 1;
}

function roundedRect(x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x+r, y);
  ctx.lineTo(x+w-r, y); ctx.quadraticCurveTo(x+w, y, x+w, y+r);
  ctx.lineTo(x+w, y+h-r); ctx.quadraticCurveTo(x+w, y+h, x+w-r, y+h);
  ctx.lineTo(x+r, y+h); ctx.quadraticCurveTo(x, y+h, x, y+h-r);
  ctx.lineTo(x, y+r); ctx.quadraticCurveTo(x, y, x+r, y);
  ctx.closePath();
}

function drawChart() {
  // Panel background
  ctx.fillStyle = "#0b1922"; ctx.strokeStyle = "#203848"; ctx.lineWidth = 1;
  roundedRect(CHART_X - 24, 54, CHART_W + 48, CH - 66, 10);
  ctx.fill(); ctx.stroke();

  // Title + R_eff badge
  ctx.fillStyle = "#c8dce8"; ctx.font = "700 15px ui-monospace,monospace";
  ctx.textAlign = "left";
  ctx.fillText("Krzywe SEIRD", CHART_X, 80);

  const reff = calcReff();
  if (reff !== null) {
    const rc = reff > 1.5 ? "#ef476f" : reff > 1 ? "#f6b352" : "#74c69d";
    ctx.fillStyle = rc;
    ctx.font = "12px ui-monospace,monospace";
    ctx.fillText("Rₗ = " + reff.toFixed(2), CHART_X + CHART_W - 60, 80);
  }

  // Grid lines
  ctx.strokeStyle = "#16303f"; ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = CHART_Y + CHART_H * i / 4;
    ctx.beginPath(); ctx.moveTo(CHART_X, y); ctx.lineTo(CHART_X + CHART_W, y); ctx.stroke();
    if (i < 4) {
      ctx.fillStyle = "#3a5562"; ctx.font = "9px ui-monospace,monospace";
      ctx.textAlign = "right";
      ctx.fillText(Math.round(PARAMS.n_agents * (4-i) / 4), CHART_X - 4, y + 3);
    }
  }
  ctx.strokeStyle = "#2a4a5f";
  ctx.strokeRect(CHART_X, CHART_Y, CHART_W, CHART_H);

  // SEIRD curves
  const maxN = PARAMS.n_agents;
  for (const k of ["S","E","I","R","D"]) {
    if (history.length < 2) continue;
    ctx.strokeStyle = COLORS[k]; ctx.lineWidth = k === "S" ? 1.5 : 2.2;
    ctx.beginPath();
    history.forEach((h, i) => {
      const x = CHART_X + i / (history.length - 1) * CHART_W;
      const y = CHART_Y + CHART_H - h[k] / maxN * CHART_H;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.stroke();
  }

  // Day cursor line
  if (history.length > 1) {
    const cx2 = CHART_X + CHART_W;
    ctx.strokeStyle = "rgba(200,220,230,.25)"; ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath(); ctx.moveTo(cx2, CHART_Y); ctx.lineTo(cx2, CHART_Y + CHART_H); ctx.stroke();
    ctx.setLineDash([]);
  }

  // Legend
  const c = counts();
  const legY = CHART_Y + CHART_H + 28;
  ["S","E","I","R","D"].forEach((k, i) => {
    const lx = CHART_X + i * 58;
    ctx.fillStyle = COLORS[k]; ctx.fillRect(lx, legY, 18, 3);
    ctx.fillStyle = "#8aa8b8"; ctx.font = "11px ui-monospace,monospace";
    ctx.textAlign = "left";
    ctx.fillText(k + " " + c[k], lx, legY + 18);
  });

  // Lockdown / intervention status indicators below legend
  const indY = legY + 36;
  const lk = getLockdown(), mc = getMaskCov(), sd = getSDCov();
  ctx.font = "10px ui-monospace,monospace"; ctx.textAlign = "left";
  ctx.fillStyle = lk ? "#ef476f" : "#3a5562";
  ctx.fillText(lk ? "LOCKDOWN ON" : "lockdown off", CHART_X, indY);
  ctx.fillStyle = mc > 0 ? "#74c69d" : "#3a5562";
  ctx.fillText("Maski " + Math.round(mc*100) + "%", CHART_X, indY + 14);
  ctx.fillStyle = sd > 0 ? "#74c69d" : "#3a5562";
  ctx.fillText("Dystans " + Math.round(sd*100) + "%", CHART_X + 90, indY + 14);

  // Isolation / asymptomatic breakdown
  const nIso   = agents.filter(a => a.state === "I" && a.selfIsolating).length;
  const nAsymp = agents.filter(a => a.state === "I" && a.asymptomatic).length;
  if (nIso + nAsymp > 0) {
    ctx.fillStyle = "#5a7a8a"; ctx.font = "9px ui-monospace,monospace";
    ctx.fillText(`Izol:${nIso}  Asympt:${nAsymp}`, CHART_X, indY + 28);
  }
}

function draw() {
  drawBackground();
  drawRoutes();
  drawPoi();
  drawAgents();
  drawChart();
}

// ─── main loop ────────────────────────────────────────────────────────────────
function tick(dtSeconds) {
  const speed  = Number(document.getElementById("speed").value);
  const dtDays = Math.min(0.035, dtSeconds / PARAMS.day_duration * speed);
  day += dtDays;

  const prevFloor  = Math.floor(day - dtDays);
  const crossedDay = Math.floor(day) > prevFloor;

  for (const agent of agents) {
    if (crossedDay && agent.alive && !(agent.state === "I" && agent.hospitalized)) {
      agent.route      = plannedDay(agent);
      agent.routeIndex = 0;
      agent.dwellUntil = day + rand(0.04, 0.50);
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
  // Trim exposure log older than 10 days
  const cutoff10 = day - 10;
  while (exposureLog.length && exposureLog[0].d < cutoff10) exposureLog.shift();

  updateHud();
}

function frame(ts) {
  const dt = Math.min(0.05, (ts - lastTs) / 1000);
  lastTs = ts;
  if (running) tick(dt);
  draw();
  requestAnimationFrame(frame);
}

// ─── controls ─────────────────────────────────────────────────────────────────
document.getElementById("btn-play").addEventListener("click",  () => { running = true; });
document.getElementById("btn-pause").addEventListener("click", () => { running = false; });
document.getElementById("btn-reset").addEventListener("click", () => { createAgents(); running = true; });

createAgents();
requestAnimationFrame(frame);
</script>
</body>
</html>"""


if __name__ == "__main__":
    main()
