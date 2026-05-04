"""Interaktywny dashboard Streamlit dla symulacji SEIRD — Etap 2."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src"))

import matplotlib.pyplot as plt
import streamlit as st

from simulation.model import EpidemicModel

COLORS = {
    "S": "steelblue",
    "E": "orange",
    "I": "crimson",
    "R": "mediumseagreen",
    "D": "black",
}

st.set_page_config(page_title="Pandemic Simulation — Etap 2", layout="wide")
st.title("SEIRD Pandemic Simulation")
st.caption("Wieloskalowy model agentowy z grafem POI — Etap 2")

with st.sidebar:
    st.header("Parametry populacji")
    n_agents = st.slider("Liczba agentów", 100, 2000, 500, step=100)
    steps = st.slider("Liczba dni symulacji", 50, 200, 100)
    initial_infected_frac = st.slider("Startowe zakażenia (%)", 1, 20, 5) / 100

    st.header("Interwencje")
    mask_coverage = st.slider("Maseczki (% populacji)", 0, 100, 0) / 100
    social_distancing_coverage = (
        st.slider("Dystans społeczny (% populacji)", 0, 100, 0) / 100
    )
    vaccination_coverage = st.slider("Szczepienia (% populacji)", 0, 100, 0) / 100
    lockdown = st.checkbox("Lockdown (zamknięte biura i sklepy)")

run = st.button("▶ Uruchom symulację", type="primary")

if run:
    with st.spinner("Symulacja w toku…"):
        model = EpidemicModel(
            n_agents=n_agents,
            initial_infected_frac=initial_infected_frac,
            mask_coverage=mask_coverage,
            social_distancing_coverage=social_distancing_coverage,
            vaccination_coverage=vaccination_coverage,
            lockdown=lockdown,
        )
        for _ in range(steps):
            model.step()

        data = model.datacollector.get_model_vars_dataframe()

    col_chart, col_stats = st.columns([2, 1])

    with col_chart:
        st.subheader("Krzywe epidemiczne SEIRD")
        fig, ax = plt.subplots(figsize=(10, 5))
        for col, color in COLORS.items():
            ax.plot(data.index, data[col], label=col, color=color, linewidth=2)
        ax.set_xlabel("Dzień")
        ax.set_ylabel("Liczba agentów")
        ax.legend()
        ax.grid(alpha=0.3)
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    with col_stats:
        peak_i = int(data["I"].max())
        peak_day = int(data["I"].idxmax())
        final_r = int(data["R"].iloc[-1])
        total_d = int(data["D"].iloc[-1])
        attack_rate = (final_r + total_d) / n_agents * 100

        st.subheader("Statystyki końcowe")
        st.metric("Szczyt zakażonych (I)", peak_i, help=f"Dzień {peak_day}")
        st.metric("Wyleczeni łącznie (R)", final_r)
        st.metric("Zgony łącznie (D)", total_d)
        st.metric("Attack rate", f"{attack_rate:.1f}%")

        st.subheader("Rozkład stanów (dzień końcowy)")
        final = data.iloc[-1]
        fig2, ax2 = plt.subplots(figsize=(5, 3))
        ax2.bar(final.index, final.values, color=[COLORS[c] for c in final.index])
        ax2.set_ylabel("Agenci")
        ax2.tick_params(axis="x", rotation=0)
        fig2.tight_layout()
        st.pyplot(fig2)
        plt.close(fig2)

    st.subheader("Dane surowe")
    st.dataframe(data.style.format("{:.0f}"), use_container_width=True)
