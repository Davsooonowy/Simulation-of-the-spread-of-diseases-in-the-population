"""Real-time SEIRD simulation — individual agent dots + live SEIRD curves.

Uruchomienie:
    uv run streamlit run scripts/realtime.py
"""
import sys
import pathlib
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src"))

import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import streamlit as st

from simulation.agents import State
from simulation.model import EpidemicModel
from simulation.space import POIType

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Pandemic Simulation — Real Time",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(
    """<style>
    [data-testid="stMetricValue"] { font-size: 1.6rem; }
    .block-container { padding-top: 1rem; }
    </style>""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_POI_POS: dict[POIType, tuple[float, float]] = {
    POIType.HOUSEHOLD:  (-3.0,  0.0),
    POIType.SCHOOL:     (-0.8,  2.6),
    POIType.OFFICE:     ( 1.5,  2.6),
    POIType.SHOP:       ( 3.0,  0.0),
    POIType.PARK:       ( 1.5, -2.6),
    POIType.HEALTHCARE: (-1.0, -2.6),
}

_POI_LABEL: dict[POIType, str] = {
    POIType.HOUSEHOLD:  "Domy",
    POIType.SCHOOL:     "Szkola",
    POIType.OFFICE:     "Biuro",
    POIType.SHOP:       "Sklep",
    POIType.PARK:       "Park",
    POIType.HEALTHCARE: "Szpital",
}

STATE_DOT_COLORS: dict[State, str] = {
    State.S: "#4da6ff",
    State.E: "#ffa64d",
    State.I: "#e63946",
    State.R: "#52b788",
    State.D: "#555555",
}

SEIRD_COLORS: dict[str, str] = {
    "S": "#4da6ff",
    "E": "#ffa64d",
    "I": "#e63946",
    "R": "#52b788",
    "D": "#888888",
}

_POI_RADIUS = 0.78

# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------


def _snapshot(model: EpidemicModel) -> dict:
    agents = model.schedule.agents
    return {
        "S": sum(1 for a in agents if a.state == State.S),
        "E": sum(1 for a in agents if a.state == State.E),
        "I": sum(1 for a in agents if a.state == State.I),
        "R": sum(1 for a in agents if a.state == State.R),
        "D": sum(1 for a in agents if a.state == State.D),
    }


def _reset(params: dict) -> None:
    st.session_state.model = EpidemicModel(**params)
    st.session_state.running = False
    st.session_state.step_count = 0
    st.session_state.history: list[dict] = [_snapshot(st.session_state.model)]
    st.session_state.params = params


if "model" not in st.session_state:
    _reset(dict(
        n_agents=150,
        initial_infected_frac=0.05,
        mask_coverage=0.0,
        social_distancing_coverage=0.0,
        vaccination_coverage=0.0,
        lockdown=False,
        p_base_multiplier=0.6,
        p_transit=0.05,
    ))

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("Parametry")

    n_agents    = st.slider("Liczba agentow", 50, 500, 150, step=50)
    init_inf    = st.slider("Startowe zakazenia (%)", 1, 20, 5) / 100
    max_steps   = st.slider("Maks. krokow", 50, 300, 150)
    speed_ms    = st.slider("Predkosc (ms/krok)", 50, 1000, 400, step=50)
    p_mult      = st.slider("Zakaznosc (mnoznik)", 0.1, 2.0, 0.6, step=0.1)
    p_transit   = st.slider("Transmisja w transporcie", 0.00, 0.20, 0.05, step=0.01)

    st.divider()
    st.subheader("Interwencje")
    mask_pct    = st.slider("Maseczki (%)", 0, 100, 0) / 100
    sd_pct      = st.slider("Dystans spoleczny (%)", 0, 100, 0) / 100
    vacc_pct    = st.slider("Szczepienia (%)", 0, 100, 0) / 100
    lockdown    = st.checkbox("Lockdown")

    st.divider()
    params = dict(
        n_agents=n_agents,
        initial_infected_frac=init_inf,
        mask_coverage=mask_pct,
        social_distancing_coverage=sd_pct,
        vaccination_coverage=vacc_pct,
        lockdown=lockdown,
        p_base_multiplier=p_mult,
        p_transit=p_transit,
    )

    col_play, col_pause = st.columns(2)
    with col_play:
        play_btn  = st.button("Play",  use_container_width=True, type="primary")
    with col_pause:
        pause_btn = st.button("Pause", use_container_width=True)
    reset_btn = st.button("Reset", use_container_width=True)

    if reset_btn:
        _reset(params)
    if play_btn:
        if st.session_state.params != params:
            _reset(params)
        st.session_state.running = True
    if pause_btn:
        st.session_state.running = False

    st.divider()
    st.caption("**Legenda stanow**")
    for state, color in STATE_DOT_COLORS.items():
        st.markdown(
            f'<span style="color:{color}; font-size:1.2rem;">&#9679;</span> **{state.name}**',
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
# Header metrics
# ---------------------------------------------------------------------------

model = st.session_state.model
step  = st.session_state.step_count
snap  = st.session_state.history[-1]

st.markdown(f"## Symulacja pandemii — krok **{step}** / {max_steps}")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Podatni (S)",   snap["S"])
c2.metric("Inkubacja (E)", snap["E"])
c3.metric("Zakazni (I)",   snap["I"])
c4.metric("Wyleczeni (R)", snap["R"])
c5.metric("Zgony (D)",     snap["D"])

# ---------------------------------------------------------------------------
# Visualisation helpers
# ---------------------------------------------------------------------------


def _sunflower(cx: float, cy: float, radius: float, slot: int, max_slots: int) -> tuple[float, float]:
    """Stable Fibonacci-spiral position for slot within a circle."""
    phi = (1.0 + 5.0 ** 0.5) / 2.0
    r = radius * np.sqrt((slot + 0.5) / max_slots)
    theta = 2.0 * np.pi * slot / phi ** 2
    return cx + r * np.cos(theta), cy + r * np.sin(theta)


def draw_poi_map(model: EpidemicModel, step: int) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(7, 6.2))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1117")
    ax.set_xlim(-4.5, 4.5)
    ax.set_ylim(-4.0, 4.0)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")

    n_slots = max(len(model.schedule.agents), 50)

    # --- Aggregate agents per POI type (deduplicated per type) ---
    type_agents: dict[POIType, set] = {pt: set() for pt in POIType}
    for node in model.city.all_nodes():
        for agent in node.agents:
            type_agents[node.poi_type].add(agent)

    # --- Transit edge arrows ---
    hx, hy = _POI_POS[POIType.HOUSEHOLD]
    for (_, dst_type), info in getattr(model, "transit_log", {}).items():
        if dst_type not in _POI_POS:
            continue
        count = info["count"]
        if count == 0:
            continue
        infec_frac = info["infectious"] / count if count else 0.0
        dx, dy = _POI_POS[dst_type]
        lw = 1.2 + min(count / 5.0, 5.0)
        # blue (safe) → red (dangerous)
        c = (0.1 + infec_frac * 0.85, 0.15 * (1.0 - infec_frac), 0.9 * (1.0 - infec_frac))
        ax.annotate(
            "",
            xy=(dx, dy),
            xytext=(hx, hy),
            arrowprops=dict(arrowstyle="-|>", color=c, lw=lw, mutation_scale=14),
            zorder=2,
        )
        mx, my = (hx + dx) / 2.0, (hy + dy) / 2.0
        ax.text(
            mx, my, str(count),
            ha="center", va="center", color="white", fontsize=7, zorder=4,
            path_effects=[pe.withStroke(linewidth=2, foreground="#0d1117")],
        )

    # --- POI circles + agent dots ---
    for pt, (cx, cy) in _POI_POS.items():
        r = _POI_RADIUS

        # Background circle
        ax.add_patch(mpatches.Circle(
            (cx, cy), r,
            facecolor="#111827", edgecolor="#334466", linewidth=1.5, zorder=3,
        ))

        agents_here = list(type_agents[pt])

        if agents_here:
            xs, ys, cs = [], [], []
            for agent in agents_here:
                slot = agent.unique_id % n_slots
                x, y = _sunflower(cx, cy, r * 0.88, slot, n_slots)
                xs.append(x)
                ys.append(y)
                cs.append(STATE_DOT_COLORS[agent.state])
            ax.scatter(xs, ys, c=cs, s=22, zorder=5, linewidths=0, alpha=0.92)

        # Label above circle
        ax.text(
            cx, cy + r + 0.12, _POI_LABEL[pt],
            ha="center", va="bottom", color="white",
            fontsize=9, fontweight="bold", zorder=6,
            path_effects=[pe.withStroke(linewidth=2, foreground="#0d1117")],
        )

        # State summary below circle
        if agents_here:
            counts = {s: sum(1 for a in agents_here if a.state == s) for s in State}
            parts = []
            if counts[State.I]:
                parts.append(f"I:{counts[State.I]}")
            if counts[State.E]:
                parts.append(f"E:{counts[State.E]}")
            parts.append(f"S:{counts[State.S]}")
            ax.text(
                cx, cy - r - 0.12, "  ".join(parts),
                ha="center", va="top",
                color="#ff9999" if counts[State.I] > 0 else "#aaaacc",
                fontsize=7, zorder=6,
                path_effects=[pe.withStroke(linewidth=2, foreground="#0d1117")],
            )
        else:
            ax.text(
                cx, cy - r - 0.12, "pusty",
                ha="center", va="top", color="#445566", fontsize=7, zorder=6,
            )

    status = "dziala" if st.session_state.running else "pauza"
    ax.set_title(
        f"Mapa POI — krok {step}  [{status}]",
        color="white", fontsize=11, pad=8,
    )
    fig.tight_layout(pad=0.3)
    return fig


def draw_curves(history: list[dict]) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#111827")

    xs = list(range(len(history)))
    for key, color in SEIRD_COLORS.items():
        ys = [h[key] for h in history]
        ax.plot(xs, ys, label=key, color=color, linewidth=2.2)
        ax.fill_between(xs, ys, alpha=0.07, color=color)

    ax.set_xlabel("Dzien", color="#aaaacc")
    ax.set_ylabel("Agenci", color="#aaaacc")
    ax.set_title("Krzywe SEIRD (na zywo)", color="white", fontsize=11)
    ax.tick_params(colors="#888888")
    ax.spines[:].set_color("#334466")
    ax.legend(fontsize=10, framealpha=0.2, labelcolor="white", facecolor="#1a1a2e")
    ax.grid(alpha=0.15, color="#334466")
    fig.tight_layout(pad=0.5)
    return fig


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

col_map, col_curve = st.columns([3, 2], gap="medium")
map_slot   = col_map.empty()
curve_slot = col_curve.empty()

fig_map   = draw_poi_map(model, step)
fig_curve = draw_curves(st.session_state.history)
map_slot.pyplot(fig_map)
curve_slot.pyplot(fig_curve)
plt.close("all")

# ---------------------------------------------------------------------------
# Auto-play loop
# ---------------------------------------------------------------------------

if st.session_state.running and step < max_steps:
    time.sleep(speed_ms / 1000.0)
    st.session_state.model.step()
    st.session_state.step_count += 1
    st.session_state.history.append(_snapshot(st.session_state.model))
    if st.session_state.step_count >= max_steps:
        st.session_state.running = False
    st.rerun()

elif st.session_state.running and step >= max_steps:
    st.session_state.running = False
    st.success(f"Symulacja zakonczona po {max_steps} krokach.")
