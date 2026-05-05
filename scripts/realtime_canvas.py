"""Continuous real-time SEIRD simulation — 60 fps browser canvas.

Run:
    uv run streamlit run scripts/realtime_canvas.py
"""
import json
import time

import streamlit as st

st.set_page_config(
    page_title="Pandemic — Real Time Canvas",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(
    "<style>.block-container{padding-top:.8rem}</style>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar — params collected in a form so sliders don't restart simulation
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("Parametry")
    with st.form("params_form"):
        n_agents     = st.slider("Liczba agentow",          50,  500,  150,  step=50)
        init_inf     = st.slider("Startowe zakazenia (%)",   1,   20,    5) / 100
        day_dur      = st.slider("Czas dnia (sekundy)",      4,   30,   12,  step=2)
        p_mult       = st.slider("Zakaznosc (mnoznik)",    0.1,  2.0,  0.4, step=0.1)
        p_transit    = st.slider("Transmisja w transporcie", 0.0, 0.3, 0.06, step=0.01)
        mask_pct     = st.slider("Maseczki (%)",             0,  100,    0) / 100
        sd_pct       = st.slider("Dystans spoleczny (%)",    0,  100,    0) / 100
        vacc_pct     = st.slider("Szczepienia (%)",          0,  100,    0) / 100
        lockdown     = st.checkbox("Lockdown")
        incubation   = st.slider("Inkubacja (dni)",          2,   10,    4)
        infectious   = st.slider("Zakazny okres (dni)",      4,   20,    8)
        p_death      = st.slider("Smiertelnosc (%)",         0,   10,    2) / 100
        submitted    = st.form_submit_button("Apply & Start", type="primary")

    if submitted or "active_params" not in st.session_state:
        st.session_state.active_params = dict(
            n_agents=n_agents,
            initial_infected_frac=init_inf,
            day_duration=day_dur,
            p_base_multiplier=p_mult,
            p_transit=p_transit,
            mask_coverage=mask_pct,
            social_distancing_coverage=sd_pct,
            vaccination_coverage=vacc_pct,
            lockdown=lockdown,
            incubation_period=incubation,
            infectious_period=infectious,
            p_death=p_death,
        )
        # Unique key forces iframe reload (= simulation restart)
        st.session_state.sim_key = str(time.time())

    st.divider()
    st.caption("Zmien parametry i kliknij **Apply & Start** aby zrestartowac symulacje.")

params_json = json.dumps(st.session_state.active_params)

# ---------------------------------------------------------------------------
# Canvas component — full JS simulation
# ---------------------------------------------------------------------------

CANVAS_HTML = f"""<!DOCTYPE html>
<html>
<head>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:#0d1117; overflow:hidden; font-family:monospace; }}
canvas {{ display:block; width:100%; height:auto; }}
#hud {{
  position:fixed; top:8px; left:10px;
  color:#aaaacc; font-size:12px; line-height:1.7; pointer-events:none;
}}
#btns {{
  position:fixed; top:8px; right:10px;
  display:flex; gap:6px;
}}
button {{
  background:#1a2233; color:#ccd; border:1px solid #334466;
  padding:5px 13px; border-radius:4px; cursor:pointer; font-size:12px;
}}
button:hover {{ background:#2a3a55; }}
</style>
</head>
<body>
<div id="hud">
  <span id="day-label">Dzien 0</span>
</div>
<div id="btns">
  <button id="btn-play">&#9654; Play</button>
  <button id="btn-pause">&#9646;&#9646; Pause</button>
  <button id="btn-reset">&#8635; Reset</button>
</div>
<canvas id="sim"></canvas>
<script>
const PARAMS = {params_json};
// JS simulation goes here (Tasks 2-7)
const CW = 1050, CH = 640, MAP_W = 690;
const canvas = document.getElementById('sim');
const ctx = canvas.getContext('2d');
canvas.width = CW; canvas.height = CH;

function draw() {{
  ctx.fillStyle = '#0d1117';
  ctx.fillRect(0, 0, CW, CH);
  ctx.fillStyle = '#334466';
  ctx.font = '18px monospace';
  ctx.textAlign = 'center';
  ctx.fillText('Canvas loaded — n_agents=' + PARAMS.n_agents, CW/2, CH/2);
}}
draw();
document.getElementById('btn-play').addEventListener('click', () => {{}});
document.getElementById('btn-pause').addEventListener('click', () => {{}});
document.getElementById('btn-reset').addEventListener('click', () => {{}});
</script>
</body>
</html>"""

st.components.v1.html(
    CANVAS_HTML,
    height=670,
    scrolling=False,
    key=st.session_state.get("sim_key", "sim"),
)
