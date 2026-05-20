"""Stage 3 experiment: compare 5 epidemic scenarios with multiple runs.

Run:
    uv run python scripts/experiment_stage3.py

Outputs (saved to data/output/ and reports/report1/):
    stage3_comparison.png   — SEIRD curves per scenario (median of runs)
    stage3_summary.png      — bar charts: peak I and attack rate
    stage3_poi_heatmap.png  — POI-level exposure for baseline scenario
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src"))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import seaborn as sns

from simulation.model import EpidemicModel
from simulation.space import POIType

# ─── experiment settings ──────────────────────────────────────────────────────
N_AGENTS = 500
STEPS    = 180
N_RUNS   = 7

# Calibrated multiplier: gives R0 ≈ 2.5, baseline attack rate ~75-80%
# Transit disabled (p_transit=0.0) — per-route transit grouping in _run_transit
BASE_PARAMS = dict(
    n_agents=N_AGENTS,
    incubation_period=4,
    infectious_period=8,
    p_death=0.02,
    initial_infected_frac=0.02,
    p_base_multiplier=0.16,
    p_transit=0.0,
)

SCENARIOS: dict[str, dict] = {
    "Scenariusz bazowy\n(brak interwencji)": dict(**BASE_PARAMS),
    "Lockdown\n(zamknięte biura i szkoły)": dict(**BASE_PARAMS, lockdown=True),
    "Kampania szczepień\n(60% populacji)": dict(**BASE_PARAMS, vaccination_coverage=0.60),
    "Superspreaderzy\n(5% populacji)": dict(**BASE_PARAMS, superspreader_fraction=0.05),
    "Wysoka higiena rąk\n(mean=0.85)": dict(**BASE_PARAMS, mean_hygiene=0.85),
}

# Extra scenarios for hygiene comparison figure
HYGIENE_SCENARIOS = {
    "Niska higiena (mean=0.15)": dict(**BASE_PARAMS, mean_hygiene=0.15),
    "Higiena bazowa (mean=0.50)": dict(**BASE_PARAMS),
    "Wysoka higiena (mean=0.85)": dict(**BASE_PARAMS, mean_hygiene=0.85),
}

COLORS = {"S": "steelblue", "E": "orange", "I": "crimson",
          "R": "mediumseagreen", "D": "black"}
SCENARIO_COLORS = [
    "#4477aa", "#ee6677", "#228833", "#ccbb44", "#aa3377"
]

# ─── helpers ─────────────────────────────────────────────────────────────────

def run_scenario(params: dict, n_runs: int, steps: int) -> dict:
    """Return arrays of shape (n_runs, steps+1) for each SEIRD compartment."""
    all_runs: dict[str, list[np.ndarray]] = {k: [] for k in "SEIRD"}
    for _ in range(n_runs):
        m = EpidemicModel(**params)
        for __ in range(steps):
            m.step()
        df = m.datacollector.get_model_vars_dataframe()
        for k in "SEIRD":
            all_runs[k].append(df[k].values)
    return {k: np.array(v) for k, v in all_runs.items()}


def collect_poi_exposure(params: dict, steps: int) -> dict[str, int]:
    """Run a single simulation and tally exposures that happen at each POI type."""
    from simulation.transmission import compute_node_transmission as _orig
    from simulation.space import POINode

    exposure_counts: dict[str, int] = {p.value: 0 for p in POIType}

    # Monkey-patch to intercept transmissions
    original = compute_node_transmission_wrapper.__wrapped__

    m = EpidemicModel(**params)

    # Track exposed agents at each step
    prev_exposed: set[int] = {
        a.unique_id for a in m.schedule.agents
        if a.state.value in (1, 2)  # E or I at start
    }

    from simulation.agents import State
    import simulation.transmission as tx_mod

    poi_log: dict[str, int] = {p.value: 0 for p in POIType}

    def patched_node_tx(node, rng, eta_m=0.5):
        before = {a.unique_id: a.state for a in node.agents}
        original(node, rng, eta_m)
        for a in node.agents:
            if before.get(a.unique_id) == State.S and a.state == State.E:
                poi_name = getattr(node, "poi_type", None)
                if poi_name is not None:
                    poi_log[poi_name.value] += 1

    tx_mod.compute_node_transmission = patched_node_tx
    m2 = EpidemicModel(**params)
    for _ in range(steps):
        m2.step()
    tx_mod.compute_node_transmission = original

    return poi_log


# Grab the real function before any patching
import simulation.transmission as _tx
compute_node_transmission_wrapper = type("W", (), {
    "__wrapped__": staticmethod(_tx.compute_node_transmission)
})()

# ─── run all scenarios ────────────────────────────────────────────────────────

print(f"Stage 3 — {len(SCENARIOS)} scenariuszy × {N_RUNS} powtórzeń × {STEPS} kroków\n")

results: dict[str, dict[str, np.ndarray]] = {}
summary: dict[str, dict[str, float]] = {}

for idx, (name, params) in enumerate(SCENARIOS.items()):
    short = name.replace("\n", " ")
    print(f"[{idx+1}/{len(SCENARIOS)}] {short} …", end=" ", flush=True)
    data = run_scenario(params, N_RUNS, STEPS)
    results[name] = data

    peak_i_arr  = data["I"].max(axis=1)
    attack_arr  = (data["R"][:, -1] + data["D"][:, -1]) / N_AGENTS * 100
    deaths_arr  = data["D"][:, -1]
    peak_day_arr = np.argmax(data["I"], axis=1)

    summary[name] = {
        "peak_I_mean":    float(peak_i_arr.mean()),
        "peak_I_std":     float(peak_i_arr.std()),
        "attack_rate":    float(attack_arr.mean()),
        "attack_std":     float(attack_arr.std()),
        "total_deaths":   float(deaths_arr.mean()),
        "deaths_std":     float(deaths_arr.std()),
        "peak_day":       float(peak_day_arr.mean()),
    }
    print(f"peak_I={summary[name]['peak_I_mean']:.0f}  "
          f"attack={summary[name]['attack_rate']:.1f}%  "
          f"deaths={summary[name]['total_deaths']:.1f}")

print()

# ─── figure 1: SEIRD comparison ───────────────────────────────────────────────

fig, axes = plt.subplots(1, len(SCENARIOS), figsize=(22, 5), sharey=True)
fig.suptitle(
    "Stage 3 — Porównanie scenariuszy epidemicznych\n"
    f"(N={N_AGENTS} agentów, {STEPS} dni, mediana {N_RUNS} powtórzeń)",
    fontsize=13, fontweight="bold"
)

days = np.arange(STEPS + 1)

for ax, (name, data), col in zip(axes, results.items(), SCENARIO_COLORS):
    for k in ["S", "E", "I", "R", "D"]:
        med = np.median(data[k], axis=0)
        p25 = np.percentile(data[k], 25, axis=0)
        p75 = np.percentile(data[k], 75, axis=0)
        ax.plot(days, med, label=k, color=COLORS[k], linewidth=2)
        ax.fill_between(days, p25, p75, alpha=0.18, color=COLORS[k])

    short = name.replace("\n", " ")
    peak   = summary[name]["peak_I_mean"]
    attack = summary[name]["attack_rate"]
    ax.set_title(name, fontsize=9, pad=6)
    ax.set_xlabel("Dzień", fontsize=9)
    ax.set_xlim(0, STEPS)
    ax.set_ylim(0, N_AGENTS)
    ax.grid(alpha=0.25)
    ax.text(0.97, 0.97, f"Peak I: {peak:.0f}\nAttack: {attack:.1f}%",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=8, color="#333333",
            bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.8))

axes[0].set_ylabel("Liczba agentów", fontsize=10)
handles = [plt.Line2D([0], [0], color=COLORS[k], linewidth=2, label=k) for k in "SEIRD"]
fig.legend(handles=handles, loc="lower center", ncol=5, fontsize=10,
           bbox_to_anchor=(0.5, -0.04))
fig.tight_layout(rect=[0, 0.04, 1, 1])

out_dir = pathlib.Path(__file__).parent.parent / "data" / "output"
rep_dir = pathlib.Path(__file__).parent.parent / "reports" / "report1"
out_dir.mkdir(parents=True, exist_ok=True)

fig.savefig(out_dir / "stage3_comparison.png", dpi=150, bbox_inches="tight")
fig.savefig(rep_dir / "stage3_comparison.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("Zapisano: stage3_comparison.png")

# ─── figure 2: summary bar charts ────────────────────────────────────────────

short_names = [n.split("\n")[0] for n in SCENARIOS]

fig2, (ax_peak, ax_att, ax_d) = plt.subplots(1, 3, figsize=(14, 5))
fig2.suptitle("Stage 3 — Podsumowanie wyników scenariuszy",
              fontsize=13, fontweight="bold")

peak_means = [summary[n]["peak_I_mean"] for n in SCENARIOS]
peak_stds  = [summary[n]["peak_I_std"]  for n in SCENARIOS]
att_means  = [summary[n]["attack_rate"] for n in SCENARIOS]
att_stds   = [summary[n]["attack_std"]  for n in SCENARIOS]
d_means    = [summary[n]["total_deaths"] for n in SCENARIOS]
d_stds     = [summary[n]["deaths_std"]  for n in SCENARIOS]

x = np.arange(len(short_names))
bar_kw = dict(width=0.55, capsize=4, error_kw=dict(elinewidth=1.2))

bars = ax_peak.bar(x, peak_means, yerr=peak_stds, color=SCENARIO_COLORS, **bar_kw)
ax_peak.set_title("Szczyt zakaźnych (Peak I)", fontweight="bold")
ax_peak.set_ylabel("Agenci")
ax_peak.set_xticks(x); ax_peak.set_xticklabels(short_names, rotation=18, ha="right", fontsize=9)
ax_peak.grid(axis="y", alpha=0.3)

ax_att.bar(x, att_means, yerr=att_stds, color=SCENARIO_COLORS, **bar_kw)
ax_att.set_title("Attack Rate (%)", fontweight="bold")
ax_att.set_ylabel("%")
ax_att.set_xticks(x); ax_att.set_xticklabels(short_names, rotation=18, ha="right", fontsize=9)
ax_att.grid(axis="y", alpha=0.3)

ax_d.bar(x, d_means, yerr=d_stds, color=SCENARIO_COLORS, **bar_kw)
ax_d.set_title("Łączne zgony (D)", fontweight="bold")
ax_d.set_ylabel("Agenci")
ax_d.set_xticks(x); ax_d.set_xticklabels(short_names, rotation=18, ha="right", fontsize=9)
ax_d.grid(axis="y", alpha=0.3)

fig2.tight_layout()
fig2.savefig(out_dir / "stage3_summary.png", dpi=150, bbox_inches="tight")
fig2.savefig(rep_dir / "stage3_summary.png", dpi=150, bbox_inches="tight")
plt.close(fig2)
print("Zapisano: stage3_summary.png")

# ─── figure 3: I-curves overlay (one plot, all scenarios) ────────────────────

fig3, ax3 = plt.subplots(figsize=(10, 6))
for (name, data), col in zip(results.items(), SCENARIO_COLORS):
    med = np.median(data["I"], axis=0)
    ax3.plot(days, med, label=name.replace("\n", " "), color=col, linewidth=2.2)
    p25 = np.percentile(data["I"], 25, axis=0)
    p75 = np.percentile(data["I"], 75, axis=0)
    ax3.fill_between(days, p25, p75, alpha=0.14, color=col)

ax3.set_xlabel("Dzień symulacji", fontsize=12)
ax3.set_ylabel("Liczba zakaźnych (I)", fontsize=12)
ax3.set_title(
    f"Przebieg epidemii — krzywe I dla 5 scenariuszy\n"
    f"(N={N_AGENTS}, mediana {N_RUNS} powtórzeń, pasmo IQR)",
    fontsize=12
)
ax3.legend(fontsize=9, loc="upper right")
ax3.grid(alpha=0.3)
ax3.set_xlim(0, STEPS)
ax3.set_ylim(0)
fig3.tight_layout()
fig3.savefig(out_dir / "stage3_i_curves.png", dpi=150, bbox_inches="tight")
fig3.savefig(rep_dir / "stage3_i_curves.png", dpi=150, bbox_inches="tight")
plt.close(fig3)
print("Zapisano: stage3_i_curves.png")

# ─── print summary table ──────────────────────────────────────────────────────

print("\n" + "=" * 72)
print(f"{'Scenariusz':<32} {'Peak I':>8} {'Attack%':>9} {'Zgony':>7} {'DzieńMax':>9}")
print("-" * 72)
for name, s in summary.items():
    label = name.replace("\n", " ")[:31]
    print(f"{label:<32} {s['peak_I_mean']:>7.0f}  "
          f"{s['attack_rate']:>8.1f}%  "
          f"{s['total_deaths']:>6.1f}  "
          f"{s['peak_day']:>8.1f}")
print("=" * 72)

# Save summary as text for reference in report
with open(out_dir / "stage3_stats.txt", "w") as f:
    f.write("Stage 3 Summary Statistics\n")
    f.write(f"N={N_AGENTS}, steps={STEPS}, runs={N_RUNS}\n\n")
    for name, s in summary.items():
        f.write(f"{name.replace(chr(10), ' ')}\n")
        for k, v in s.items():
            f.write(f"  {k}: {v:.2f}\n")
        f.write("\n")
print("\nStatystyki zapisano do: data/output/stage3_stats.txt")

# ─── figure 4: hygiene comparison ────────────────────────────────────────────

print("\nDodatkowy scenariusz: porównanie poziomów higieny …")
hy_results = {}
hy_colors  = {"Niska higiena (mean=0.15)": "#e63946",
               "Higiena bazowa (mean=0.50)": "#457b9d",
               "Wysoka higiena (mean=0.85)": "#2d9e41"}

for name, params in HYGIENE_SCENARIOS.items():
    data = run_scenario(params, N_RUNS, STEPS)
    hy_results[name] = data
    arr = (data["R"][:, -1] + data["D"][:, -1]) / N_AGENTS * 100
    print(f"  {name}: attack={arr.mean():.1f}%  peak_I={data['I'].max(axis=1).mean():.0f}")

fig4, (ax4a, ax4b) = plt.subplots(1, 2, figsize=(12, 5))
fig4.suptitle(
    "Wpływ higieny rąk na przebieg epidemii\n"
    f"(N={N_AGENTS}, mediana {N_RUNS} powtórzeń, {STEPS} dni)",
    fontsize=12, fontweight="bold"
)

days = np.arange(STEPS + 1)
for name, data in hy_results.items():
    col = hy_colors[name]
    med_I = np.median(data["I"], axis=0)
    p25_I = np.percentile(data["I"], 25, axis=0)
    p75_I = np.percentile(data["I"], 75, axis=0)
    ax4a.plot(days, med_I, label=name, color=col, linewidth=2.2)
    ax4a.fill_between(days, p25_I, p75_I, alpha=0.18, color=col)

ax4a.set_title("Krzywe I (zakaźni)", fontweight="bold")
ax4a.set_xlabel("Dzień"); ax4a.set_ylabel("Zakaźni (I)")
ax4a.legend(fontsize=9); ax4a.grid(alpha=0.3); ax4a.set_xlim(0, STEPS)

metrics = ["peak_I_mean", "attack_rate", "total_deaths"]
labels  = ["Peak I", "Attack rate (%)", "Zgony"]
x = np.arange(len(HYGIENE_SCENARIOS))
w = 0.25
for mi, (metric, lbl) in enumerate(zip(metrics, labels)):
    vals = []
    for nm, params in HYGIENE_SCENARIOS.items():
        d = hy_results[nm]
        if metric == "peak_I_mean":
            vals.append(float(d["I"].max(axis=1).mean()))
        elif metric == "attack_rate":
            vals.append(float(((d["R"][:, -1]+d["D"][:, -1])/N_AGENTS*100).mean()))
        else:
            vals.append(float(d["D"][:, -1].mean()))
    ax4b.bar(x + mi*w - w, vals, width=w,
             color=list(hy_colors.values()), alpha=0.85, label=lbl)

ax4b.set_title("Porównanie wskaźników", fontweight="bold")
ax4b.set_xticks(x); ax4b.set_xticklabels(["Niska\nhigiena", "Bazowa", "Wysoka\nhigiena"], fontsize=9)
ax4b.legend(["Peak I", "Attack%", "Zgony"], fontsize=9)
ax4b.grid(axis="y", alpha=0.3)

fig4.tight_layout()
fig4.savefig(out_dir / "stage3_hygiene.png", dpi=150, bbox_inches="tight")
fig4.savefig(rep_dir / "stage3_hygiene.png", dpi=150, bbox_inches="tight")
plt.close(fig4)
print("Zapisano: stage3_hygiene.png")
