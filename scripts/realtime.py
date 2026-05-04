"""Real-time SEIRD simulation — mapa POI + krzywe na żywo.

Uruchomienie:
    uv run streamlit run scripts/realtime.py
"""
import sys
import pathlib
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src"))

import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import numpy as np
import streamlit as st

from simulation.agents import State
from simulation.model import EpidemicModel
from simulation.space import POIType

# ---------------------------------------------------------------------------
# Layout config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Pandemic Simulation — Real Time",
    layout="wide",
    initial_sidebar_state="expanded",
)

_CSS = """
<style>
[data-testid="stMetricValue"] { font-size: 1.6rem; }
.block-container { padding-top: 1rem; }
</style>
"""
st.markdown(_CSS, unsafe_allow_html=True)

# Fixed city-map positions for each POI type
_POI_POS: dict[POIType, tuple[float, float]] = {
    POIType.HOUSEHOLD:  (-2.8,  0.0),
    POIType.SCHOOL:     (-0.8,  2.2),
    POIType.OFFICE:     ( 1.0,  2.2),
    POIType.SHOP:       ( 2.8,  0.5),
    POIType.PARK:       ( 1.8,  2.8),
    POIType.HEALTHCARE: ( 1.2, -2.2),
}

_POI_LABEL = {
    POIType.HOUSEHOLD:  "Domy",
    POIType.SCHOOL:     "Szkoła",
    POIType.OFFICE:     "Biuro",
    POIType.SHOP:       "Sklep",
    POIType.PARK:       "Park",
    POIType.HEALTHCARE: "Szpital",
}

_POI_ICON = {
    POIType.HOUSEHOLD:  "🏠",
    POIType.SCHOOL:     "🏫",
    POIType.OFFICE:     "🏢",
    POIType.SHOP:       "🛒",
    POIType.PARK:       "🌳",
    POIType.HEALTHCARE: "🏥",
}

SEIRD_COLORS = {
    "S": "#4da6ff",
    "E": "#ffa64d",
    "I": "#e63946",
    "R": "#52b788",
    "D": "#888888",
}

EDGES = [
    (POIType.HOUSEHOLD, POIType.SCHOOL),
    (POIType.HOUSEHOLD, POIType.OFFICE),
    (POIType.HOUSEHOLD, POIType.SHOP),
    (POIType.HOUSEHOLD, POIType.PARK),
    (POIType.HOUSEHOLD, POIType.HEALTHCARE),
]

# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------

def _reset(params: dict) -> None:
    st.session_state.model = EpidemicModel(**params)
    st.session_state.running = False
    st.session_state.step_count = 0
    st.session_state.history: list[dict] = [_snapshot(st.session_state.model)]
    st.session_state.params = params


def _snapshot(model: EpidemicModel) -> dict:
    agents = model.schedule.agents
    return {
        "S": sum(1 for a in agents if a.state == State.S),
        "E": sum(1 for a in agents if a.state == State.E),
        "I": sum(1 for a in agents if a.state == State.I),
        "R": sum(1 for a in agents if a.state == State.R),
        "D": sum(1 for a in agents if a.state == State.D),
    }


if "model" not in st.session_state:
    _reset(dict(
        n_agents=300,
        initial_infected_frac=0.05,
        mask_coverage=0.0,
        social_distancing_coverage=0.0,
        vaccination_coverage=0.0,
        lockdown=False,
    ))

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("⚙️ Parametry")

    n_agents = st.slider("Liczba agentów", 50, 1000, 300, step=50)
    initial_infected = st.slider("Startowe zakażenia (%)", 1, 20, 5) / 100
    max_steps = st.slider("Maks. kroków", 50, 300, 150)
    speed = st.slider("Prędkość (ms/krok)", 50, 1000, 200, step=50)

    st.divider()
    st.subheader("Interwencje")
    mask_pct = st.slider("Maseczki (%)", 0, 100, 0) / 100
    sd_pct = st.slider("Dystans społeczny (%)", 0, 100, 0) / 100
    vacc_pct = st.slider("Szczepienia (%)", 0, 100, 0) / 100
    lockdown = st.checkbox("Lockdown")

    st.divider()

    params = dict(
        n_agents=n_agents,
        initial_infected_frac=initial_infected,
        mask_coverage=mask_pct,
        social_distancing_coverage=sd_pct,
        vaccination_coverage=vacc_pct,
        lockdown=lockdown,
    )

    col_play, col_pause = st.columns(2)
    with col_play:
        play_btn = st.button("▶ Play", use_container_width=True, type="primary")
    with col_pause:
        pause_btn = st.button("⏸ Pause", use_container_width=True)
    reset_btn = st.button("↺ Reset", use_container_width=True)

    if reset_btn:
        _reset(params)
    if play_btn:
        if st.session_state.params != params:
            _reset(params)
        st.session_state.running = True
    if pause_btn:
        st.session_state.running = False

    st.divider()
    st.caption("**Legenda stanów**")
    for label, color in SEIRD_COLORS.items():
        st.markdown(
            f'<span style="color:{color}; font-size:1.1rem;">■</span> **{label}**',
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
# Header row
# ---------------------------------------------------------------------------

model = st.session_state.model
step = st.session_state.step_count
snap = st.session_state.history[-1] if st.session_state.history else _snapshot(model)

st.markdown(f"## 🦠 Symulacja pandemii — krok **{step}** / {max_steps}")

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Podatni (S)", snap["S"], delta=None)
m2.metric("Inkubacja (E)", snap["E"])
m3.metric("Zakaźni (I)", snap["I"])
m4.metric("Wyleczeni (R)", snap["R"])
m5.metric("Zgony (D)", snap["D"])

# ---------------------------------------------------------------------------
# Main visualisation area
# ---------------------------------------------------------------------------

col_map, col_curve = st.columns([3, 2], gap="medium")

map_slot   = col_map.empty()
curve_slot = col_curve.empty()


def _node_color(i_count: int, e_count: int, total: int) -> tuple:
    """Return RGB node colour: safe=dark-blue, exposed=amber, infectious=crimson."""
    if total == 0:
        return (0.15, 0.15, 0.25)
    i_f = i_count / total
    e_f = e_count / total
    r = min(1.0, i_f * 2.5 + e_f * 0.6)
    g = max(0.0, 0.55 - i_f * 1.5 + e_f * 0.1)
    b = max(0.0, 0.85 - i_f * 2.0 - e_f * 0.8)
    return (r, g, b)


def draw_poi_map(model: EpidemicModel, step: int) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(7, 5.5))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1117")
    ax.set_xlim(-4.2, 4.2)
    ax.set_ylim(-3.5, 3.8)
    ax.axis("off")

    # Aggregate agents per POI type
    type_data: dict[POIType, dict] = {}
    for pt in POIType:
        nodes = model.city.get_nodes_by_type(pt)
        agents = [a for nd in nodes for a in nd.agents]
        c = {s: 0 for s in State}
        for a in agents:
            c[a.state] += 1
        type_data[pt] = {"counts": c, "total": sum(c.values())}

    max_total = max(d["total"] for d in type_data.values()) or 1

    # Draw edges
    hx, hy = _POI_POS[POIType.HOUSEHOLD]
    for a_type, b_type in EDGES:
        ax_pos, ay_pos = _POI_POS[a_type]
        bx_pos, by_pos = _POI_POS[b_type]
        active = type_data[b_type]["total"] > 0
        ax.plot(
            [ax_pos, bx_pos], [ay_pos, by_pos],
            color="#334466" if active else "#1a2233",
            linewidth=1.5 if active else 0.8,
            linestyle="--", alpha=0.7, zorder=1,
        )

    # Draw nodes
    for pt, pos in _POI_POS.items():
        d = type_data[pt]
        total = d["total"]
        counts = d["counts"]

        size = 1200 + 2800 * (total / max_total)
        color = _node_color(counts[State.I], counts[State.E], total)

        # Glow effect for infectious nodes
        if counts[State.I] > 0:
            ax.scatter(*pos, s=size * 1.6, c=["#e63946"], alpha=0.18, zorder=2)

        ax.scatter(
            *pos, s=size, c=[color], zorder=3,
            edgecolors="white", linewidths=1.2, alpha=0.95,
        )

        # Icon + name label (above node)
        label = f"{_POI_ICON[pt]}  {_POI_LABEL[pt]}"
        ax.text(
            pos[0], pos[1] + 0.42, label,
            ha="center", va="bottom", color="white",
            fontsize=9, fontweight="bold", zorder=5,
            path_effects=[pe.withStroke(linewidth=2, foreground="#0d1117")],
        )

        # Agent counts (below node)
        if total > 0:
            info_parts = []
            if counts[State.I]:
                info_parts.append(f"I:{counts[State.I]}")
            if counts[State.E]:
                info_parts.append(f"E:{counts[State.E]}")
            info_parts.append(f"S:{counts[State.S]}")
            info = "  ".join(info_parts)
            ax.text(
                pos[0], pos[1] - 0.42, info,
                ha="center", va="top",
                color="#ff9999" if counts[State.I] > 0 else "#aaaacc",
                fontsize=8, zorder=5,
                path_effects=[pe.withStroke(linewidth=2, foreground="#0d1117")],
            )
        else:
            ax.text(
                pos[0], pos[1] - 0.42, "pusty",
                ha="center", va="top", color="#555577", fontsize=8, zorder=5,
            )

    status = "▶ działa" if st.session_state.running else "⏸ pauza"
    ax.set_title(
        f"Mapa POI — krok {step}  {status}",
        color="white", fontsize=11, pad=8,
        path_effects=[pe.withStroke(linewidth=2, foreground="#0d1117")],
    )
    fig.tight_layout(pad=0.5)
    return fig


def draw_curves(history: list[dict]) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(5.5, 5))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#111827")

    xs = list(range(len(history)))
    for key, color in SEIRD_COLORS.items():
        ys = [h[key] for h in history]
        ax.plot(xs, ys, label=key, color=color, linewidth=2.2)
        if ys:
            ax.fill_between(xs, ys, alpha=0.07, color=color)

    ax.set_xlabel("Dzień", color="#aaaacc")
    ax.set_ylabel("Agenci", color="#aaaacc")
    ax.set_title("Krzywe SEIRD (na żywo)", color="white", fontsize=11)
    ax.tick_params(colors="#888888")
    ax.spines[:].set_color("#334466")
    ax.legend(
        fontsize=10, framealpha=0.2,
        labelcolor="white", facecolor="#1a1a2e",
    )
    ax.grid(alpha=0.15, color="#334466")
    fig.tight_layout(pad=0.5)
    return fig


# Initial draw
fig_map = draw_poi_map(model, step)
fig_curve = draw_curves(st.session_state.history)
map_slot.pyplot(fig_map)
curve_slot.pyplot(fig_curve)
plt.close("all")

# ---------------------------------------------------------------------------
# Auto-play loop
# ---------------------------------------------------------------------------

if st.session_state.running and step < max_steps:
    time.sleep(speed / 1000)

    st.session_state.model.step()
    st.session_state.step_count += 1
    st.session_state.history.append(_snapshot(st.session_state.model))

    # Stop automatically at end
    if st.session_state.step_count >= max_steps:
        st.session_state.running = False

    st.rerun()

elif st.session_state.running and step >= max_steps:
    st.session_state.running = False
    st.success(f"✅ Symulacja zakończona po {max_steps} krokach.")
