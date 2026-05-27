"""Stage 3 experiment: compare 6 epidemic scenarios with multiple runs.

Scenarios
---------
1. Baseline          — brak interwencji
2. Lockdown natychmiastowy — lockdown od dnia 0
3. Lockdown reaktywny     — lockdown gdy I >= 5% populacji  ← NOWY
4. Szczepienia 60%
5. Superspreaderzy 5%
6. Wysoka higiena (Θ = 0.85)

Run:
    uv run python scripts/experiment_stage3.py

Outputs (saved to data/output/ and reports/report1/):
    stage3_comparison.png
    stage3_summary.png
    stage3_i_curves.png
    stage3_hygiene.png
    stage3_lockdown_compare.png   ← nowy wykres porównania lockdownów
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

from simulation.model import EpidemicModel
from simulation.agents import State

# ─── experiment settings ──────────────────────────────────────────────────────
N_AGENTS          = 500
STEPS             = 180
N_RUNS            = 7
LOCKDOWN_THRESHOLD = int(0.05 * N_AGENTS)   # 25 agentów = 5% populacji

BASE_PARAMS = dict(
    n_agents=N_AGENTS,
    incubation_period=4,
    infectious_period=8,
    p_death=0.02,
    initial_infected_frac=0.02,
    p_base_multiplier=0.16,
    p_transit=0.0,
)

# None = scenariusz obsługiwany przez run_delayed_lockdown()
SCENARIOS: dict[str, dict | None] = {
    "Scenariusz bazowy\n(brak interwencji)":           dict(**BASE_PARAMS),
    "Lockdown natychmiastowy\n(od dnia 0)":            dict(**BASE_PARAMS, lockdown=True),
    f"Lockdown reaktywny\n(gdy I ≥ {LOCKDOWN_THRESHOLD} ag.)": None,
    "Kampania szczepień\n(60% populacji)":             dict(**BASE_PARAMS, vaccination_coverage=0.60),
    "Superspreaderzy\n(5% populacji)":                 dict(**BASE_PARAMS, superspreader_fraction=0.05),
    "Wysoka higiena rąk\n(mean=0.85)":                dict(**BASE_PARAMS, mean_hygiene=0.85),
}

HYGIENE_SCENARIOS = {
    "Niska higiena (mean=0.15)": dict(**BASE_PARAMS, mean_hygiene=0.15),
    "Higiena bazowa (mean=0.50)": dict(**BASE_PARAMS),
    "Wysoka higiena (mean=0.85)": dict(**BASE_PARAMS, mean_hygiene=0.85),
}

COLORS = {"S": "steelblue", "E": "orange", "I": "crimson",
          "R": "mediumseagreen", "D": "black"}

SCENARIO_COLORS = [
    "#4477aa",   # baseline
    "#ee6677",   # lockdown natychmiastowy
    "#ff9900",   # lockdown reaktywny
    "#228833",   # szczepienia
    "#ccbb44",   # superspreaderzy
    "#aa3377",   # higiena
]

# ─── helpers ─────────────────────────────────────────────────────────────────

def run_scenario(params: dict, n_runs: int, steps: int) -> dict:
    """Return arrays (n_runs, steps+1) for each SEIRD compartment."""
    all_runs: dict[str, list] = {k: [] for k in "SEIRD"}
    for _ in range(n_runs):
        m = EpidemicModel(**params)
        for __ in range(steps):
            m.step()
        df = m.datacollector.get_model_vars_dataframe()
        for k in "SEIRD":
            all_runs[k].append(df[k].values)
    return {k: np.array(v) for k, v in all_runs.items()}


def run_delayed_lockdown(
    params: dict, n_runs: int, steps: int, threshold: int
) -> tuple[dict, float]:
    """Lockdown aktywuje się gdy I >= threshold.

    Returns
    -------
    data : dict  — SEIRD arrays (n_runs, steps+1)
    avg_ld_day : float — średni dzień aktywacji lockdownu
    """
    all_runs: dict[str, list] = {k: [] for k in "SEIRD"}
    ld_days: list[int] = []

    for _ in range(n_runs):
        m = EpidemicModel(**params)
        locked = False
        for day in range(steps):
            if not locked:
                n_i = sum(1 for a in m.schedule.agents if a.state == State.I)
                if n_i >= threshold:
                    m.lockdown = True
                    locked = True
                    ld_days.append(day)
            m.step()
        df = m.datacollector.get_model_vars_dataframe()
        for k in "SEIRD":
            all_runs[k].append(df[k].values)

    avg_ld_day = float(np.mean(ld_days)) if ld_days else float("nan")
    return {k: np.array(v) for k, v in all_runs.items()}, avg_ld_day


def compute_summary(data: dict, n_agents: int) -> dict:
    peak_i_arr   = data["I"].max(axis=1)
    attack_arr   = (data["R"][:, -1] + data["D"][:, -1]) / n_agents * 100
    deaths_arr   = data["D"][:, -1]
    peak_day_arr = np.argmax(data["I"], axis=1)
    return {
        "peak_I_mean":  float(peak_i_arr.mean()),
        "peak_I_std":   float(peak_i_arr.std()),
        "attack_rate":  float(attack_arr.mean()),
        "attack_std":   float(attack_arr.std()),
        "total_deaths": float(deaths_arr.mean()),
        "deaths_std":   float(deaths_arr.std()),
        "peak_day":     float(peak_day_arr.mean()),
    }

# ─── run all scenarios ────────────────────────────────────────────────────────

print(f"Stage 3 — {len(SCENARIOS)} scenariuszy × {N_RUNS} powtórzeń × {STEPS} kroków\n")

results: dict[str, dict] = {}
summary: dict[str, dict] = {}
lockdown_trigger_day: float | None = None

DELAYED_KEY = f"Lockdown reaktywny\n(gdy I ≥ {LOCKDOWN_THRESHOLD} ag.)"

for idx, (name, params) in enumerate(SCENARIOS.items()):
    short = name.replace("\n", " ")
    print(f"[{idx+1}/{len(SCENARIOS)}] {short} …", end=" ", flush=True)

    if params is None:
        # Delayed / reactive lockdown
        data, avg_ld = run_delayed_lockdown(
            BASE_PARAMS, N_RUNS, STEPS, LOCKDOWN_THRESHOLD
        )
        lockdown_trigger_day = avg_ld
    else:
        data = run_scenario(params, N_RUNS, STEPS)

    results[name] = data
    s = compute_summary(data, N_AGENTS)
    summary[name] = s

    extra = f"  [lockdown aktywowany: dzień {avg_ld:.1f}]" if params is None else ""
    print(f"peak_I={s['peak_I_mean']:.0f}  "
          f"attack={s['attack_rate']:.1f}%  "
          f"deaths={s['total_deaths']:.1f}{extra}")

print()

out_dir = pathlib.Path(__file__).parent.parent / "data" / "output"
rep_dir = pathlib.Path(__file__).parent.parent / "reports" / "report1"
out_dir.mkdir(parents=True, exist_ok=True)

days = np.arange(STEPS + 1)

# ─── figure 1: SEIRD comparison (2×3 grid) ───────────────────────────────────

fig, axes = plt.subplots(2, 3, figsize=(18, 9), sharey=True)
axes_flat = axes.flatten()
fig.suptitle(
    "Stage 3 — Porównanie scenariuszy epidemicznych\n"
    f"(N={N_AGENTS} agentów, {STEPS} dni, mediana {N_RUNS} powtórzeń)",
    fontsize=13, fontweight="bold"
)

for ax, (name, data), col in zip(axes_flat, results.items(), SCENARIO_COLORS):
    for k in ["S", "E", "I", "R", "D"]:
        med = np.median(data[k], axis=0)
        p25 = np.percentile(data[k], 25, axis=0)
        p75 = np.percentile(data[k], 75, axis=0)
        ax.plot(days, med, label=k, color=COLORS[k], linewidth=2)
        ax.fill_between(days, p25, p75, alpha=0.18, color=COLORS[k])

    # Mark lockdown trigger day for reactive scenario
    if name == DELAYED_KEY and lockdown_trigger_day is not None:
        ax.axvline(lockdown_trigger_day, color="black", linestyle="--",
                   linewidth=1.2, alpha=0.7)
        ax.text(lockdown_trigger_day + 2, N_AGENTS * 0.82,
                f"Lockdown\ndzień {lockdown_trigger_day:.0f}",
                fontsize=7, color="black", alpha=0.8)

    peak   = summary[name]["peak_I_mean"]
    attack = summary[name]["attack_rate"]
    ax.set_title(name, fontsize=8.5, pad=5)
    ax.set_xlabel("Dzień", fontsize=9)
    ax.set_xlim(0, STEPS)
    ax.set_ylim(0, N_AGENTS)
    ax.grid(alpha=0.25)
    ax.text(0.97, 0.97, f"Peak I: {peak:.0f}\nAttack: {attack:.1f}%",
            transform=ax.transAxes, ha="right", va="top", fontsize=8,
            bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.8))

for ax in axes[:, 0]:
    ax.set_ylabel("Liczba agentów", fontsize=10)

handles = [plt.Line2D([0], [0], color=COLORS[k], linewidth=2, label=k) for k in "SEIRD"]
fig.legend(handles=handles, loc="lower center", ncol=5, fontsize=10,
           bbox_to_anchor=(0.5, -0.02))
fig.tight_layout(rect=[0, 0.04, 1, 1])

fig.savefig(out_dir / "stage3_comparison.png", dpi=150, bbox_inches="tight")
fig.savefig(rep_dir / "stage3_comparison.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("Zapisano: stage3_comparison.png")

# ─── figure 2: summary bar charts ────────────────────────────────────────────

short_names = [n.split("\n")[0] for n in SCENARIOS]

fig2, (ax_peak, ax_att, ax_d) = plt.subplots(1, 3, figsize=(16, 5))
fig2.suptitle("Stage 3 — Podsumowanie wyników scenariuszy",
              fontsize=13, fontweight="bold")

x = np.arange(len(short_names))
bar_kw = dict(width=0.55, capsize=4, error_kw=dict(elinewidth=1.2))

ax_peak.bar(x, [summary[n]["peak_I_mean"] for n in SCENARIOS],
            yerr=[summary[n]["peak_I_std"] for n in SCENARIOS],
            color=SCENARIO_COLORS, **bar_kw)
ax_peak.set_title("Szczyt zakaźnych (Peak I)", fontweight="bold")
ax_peak.set_ylabel("Agenci")
ax_peak.set_xticks(x); ax_peak.set_xticklabels(short_names, rotation=20, ha="right", fontsize=8)
ax_peak.grid(axis="y", alpha=0.3)

ax_att.bar(x, [summary[n]["attack_rate"] for n in SCENARIOS],
           yerr=[summary[n]["attack_std"] for n in SCENARIOS],
           color=SCENARIO_COLORS, **bar_kw)
ax_att.set_title("Attack Rate (%)", fontweight="bold")
ax_att.set_ylabel("%")
ax_att.set_xticks(x); ax_att.set_xticklabels(short_names, rotation=20, ha="right", fontsize=8)
ax_att.grid(axis="y", alpha=0.3)

ax_d.bar(x, [summary[n]["total_deaths"] for n in SCENARIOS],
         yerr=[summary[n]["deaths_std"] for n in SCENARIOS],
         color=SCENARIO_COLORS, **bar_kw)
ax_d.set_title("Łączne zgony (D)", fontweight="bold")
ax_d.set_ylabel("Agenci")
ax_d.set_xticks(x); ax_d.set_xticklabels(short_names, rotation=20, ha="right", fontsize=8)
ax_d.grid(axis="y", alpha=0.3)

fig2.tight_layout()
fig2.savefig(out_dir / "stage3_summary.png", dpi=150, bbox_inches="tight")
fig2.savefig(rep_dir / "stage3_summary.png", dpi=150, bbox_inches="tight")
plt.close(fig2)
print("Zapisano: stage3_summary.png")

# ─── figure 3: I-curves overlay ──────────────────────────────────────────────

fig3, ax3 = plt.subplots(figsize=(11, 6))
for (name, data), col in zip(results.items(), SCENARIO_COLORS):
    med = np.median(data["I"], axis=0)
    p25 = np.percentile(data["I"], 25, axis=0)
    p75 = np.percentile(data["I"], 75, axis=0)
    ax3.plot(days, med, label=name.replace("\n", " "), color=col, linewidth=2.2)
    ax3.fill_between(days, p25, p75, alpha=0.14, color=col)

if lockdown_trigger_day is not None:
    ax3.axvline(lockdown_trigger_day, color="#ff9900", linestyle="--",
                linewidth=1.5, alpha=0.8, label=f"Reaktywny LD: dzień {lockdown_trigger_day:.0f}")

ax3.set_xlabel("Dzień symulacji", fontsize=12)
ax3.set_ylabel("Liczba zakaźnych (I)", fontsize=12)
ax3.set_title(
    f"Przebieg epidemii — krzywe I dla 6 scenariuszy\n"
    f"(N={N_AGENTS}, mediana {N_RUNS} powtórzeń, pasmo IQR)",
    fontsize=12
)
ax3.legend(fontsize=8.5, loc="upper right")
ax3.grid(alpha=0.3)
ax3.set_xlim(0, STEPS)
ax3.set_ylim(0)
fig3.tight_layout()
fig3.savefig(out_dir / "stage3_i_curves.png", dpi=150, bbox_inches="tight")
fig3.savefig(rep_dir / "stage3_i_curves.png", dpi=150, bbox_inches="tight")
plt.close(fig3)
print("Zapisano: stage3_i_curves.png")

# ─── figure 4: lockdown comparison (immediate vs reactive vs none) ────────────

LOCKDOWN_COMPARE = {
    "Brak lockdownu\n(scenariusz bazowy)":   "Scenariusz bazowy\n(brak interwencji)",
    f"Lockdown reaktywny\n(dzień {lockdown_trigger_day:.0f} śr.)": DELAYED_KEY,
    "Lockdown natychmiastowy\n(od dnia 0)":  "Lockdown natychmiastowy\n(od dnia 0)",
}
lc_colors = ["#4477aa", "#ff9900", "#ee6677"]

fig4, (ax4a, ax4b) = plt.subplots(1, 2, figsize=(13, 5))
fig4.suptitle(
    "Porównanie strategii lockdownu: brak / reaktywny / natychmiastowy\n"
    f"(N={N_AGENTS}, mediana {N_RUNS} powtórzeń)",
    fontsize=12, fontweight="bold"
)

for (label, sc_key), col in zip(LOCKDOWN_COMPARE.items(), lc_colors):
    data = results[sc_key]
    med_I = np.median(data["I"], axis=0)
    p25_I = np.percentile(data["I"], 25, axis=0)
    p75_I = np.percentile(data["I"], 75, axis=0)
    ax4a.plot(days, med_I, label=label.replace("\n", " "), color=col, linewidth=2.2)
    ax4a.fill_between(days, p25_I, p75_I, alpha=0.18, color=col)

if lockdown_trigger_day is not None:
    ax4a.axvline(lockdown_trigger_day, color="#ff9900", linestyle="--",
                 linewidth=1.4, alpha=0.75)
    ax4a.text(lockdown_trigger_day + 1.5, ax4a.get_ylim()[1] * 0.9 if ax4a.get_ylim()[1] > 0 else 80,
              f"Aktywacja\nreaktywnego LD\ndzień {lockdown_trigger_day:.0f}",
              fontsize=8, color="#cc7700")

ax4a.set_title("Krzywe zakaźnych (I)", fontweight="bold")
ax4a.set_xlabel("Dzień"); ax4a.set_ylabel("Zakaźni (I)")
ax4a.legend(fontsize=9); ax4a.grid(alpha=0.3); ax4a.set_xlim(0, STEPS); ax4a.set_ylim(0)

lc_keys = [LOCKDOWN_COMPARE[l] for l in LOCKDOWN_COMPARE]
lc_labels_short = ["Brak\nlockdownu", f"Reaktywny\n(dzień {lockdown_trigger_day:.0f})", "Natychmiastowy\n(dzień 0)"]
metrics = [
    ([summary[k]["peak_I_mean"] for k in lc_keys], [summary[k]["peak_I_std"] for k in lc_keys], "Peak I", "Agenci"),
    ([summary[k]["attack_rate"] for k in lc_keys], [summary[k]["attack_std"] for k in lc_keys], "Attack rate", "%"),
    ([summary[k]["total_deaths"] for k in lc_keys], [summary[k]["deaths_std"] for k in lc_keys], "Zgony", "Agenci"),
]
x4 = np.arange(len(lc_keys))
w = 0.22
for mi, (vals, errs, lbl, unit) in enumerate(metrics):
    ax4b.bar(x4 + (mi - 1) * w, vals, yerr=errs, width=w,
             color=lc_colors, alpha=0.85, capsize=3,
             label=lbl, error_kw=dict(elinewidth=1.2))

ax4b.set_title("Wskaźniki epidemiczne", fontweight="bold")
ax4b.set_xticks(x4); ax4b.set_xticklabels(lc_labels_short, fontsize=9)
ax4b.legend(["Peak I", "Attack%", "Zgony"], fontsize=9)
ax4b.grid(axis="y", alpha=0.3)

fig4.tight_layout()
fig4.savefig(out_dir / "stage3_lockdown_compare.png", dpi=150, bbox_inches="tight")
fig4.savefig(rep_dir / "stage3_lockdown_compare.png", dpi=150, bbox_inches="tight")
plt.close(fig4)
print("Zapisano: stage3_lockdown_compare.png")

# ─── figure 5: hygiene comparison ────────────────────────────────────────────

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

fig5, (ax5a, ax5b) = plt.subplots(1, 2, figsize=(12, 5))
fig5.suptitle(
    "Wpływ higieny rąk na przebieg epidemii\n"
    f"(N={N_AGENTS}, mediana {N_RUNS} powtórzeń, {STEPS} dni)",
    fontsize=12, fontweight="bold"
)

for name, data in hy_results.items():
    col = hy_colors[name]
    med_I = np.median(data["I"], axis=0)
    p25_I = np.percentile(data["I"], 25, axis=0)
    p75_I = np.percentile(data["I"], 75, axis=0)
    ax5a.plot(days, med_I, label=name, color=col, linewidth=2.2)
    ax5a.fill_between(days, p25_I, p75_I, alpha=0.18, color=col)

ax5a.set_title("Krzywe I (zakaźni)", fontweight="bold")
ax5a.set_xlabel("Dzień"); ax5a.set_ylabel("Zakaźni (I)")
ax5a.legend(fontsize=9); ax5a.grid(alpha=0.3); ax5a.set_xlim(0, STEPS)

x5 = np.arange(len(HYGIENE_SCENARIOS))
w = 0.25
for mi, (metric, lbl) in enumerate(zip(
    ["peak_I_mean", "attack_rate", "total_deaths"],
    ["Peak I", "Attack rate (%)", "Zgony"]
)):
    vals = []
    for nm in HYGIENE_SCENARIOS:
        d = hy_results[nm]
        if metric == "peak_I_mean":
            vals.append(float(d["I"].max(axis=1).mean()))
        elif metric == "attack_rate":
            vals.append(float(((d["R"][:, -1]+d["D"][:, -1])/N_AGENTS*100).mean()))
        else:
            vals.append(float(d["D"][:, -1].mean()))
    ax5b.bar(x5 + mi*w - w, vals, width=w, color=list(hy_colors.values()),
             alpha=0.85, label=lbl)

ax5b.set_title("Porównanie wskaźników", fontweight="bold")
ax5b.set_xticks(x5); ax5b.set_xticklabels(["Niska\nhigiena", "Bazowa", "Wysoka\nhigiena"], fontsize=9)
ax5b.legend(["Peak I", "Attack%", "Zgony"], fontsize=9)
ax5b.grid(axis="y", alpha=0.3)

fig5.tight_layout()
fig5.savefig(out_dir / "stage3_hygiene.png", dpi=150, bbox_inches="tight")
fig5.savefig(rep_dir / "stage3_hygiene.png", dpi=150, bbox_inches="tight")
plt.close(fig5)
print("Zapisano: stage3_hygiene.png")

# ─── summary table ────────────────────────────────────────────────────────────

print("\n" + "=" * 76)
print(f"{'Scenariusz':<35} {'Peak I':>7} {'Attack%':>9} {'Zgony':>7} {'DzieńMax':>9}")
print("-" * 76)
for name, s in summary.items():
    label = name.replace("\n", " ")[:34]
    extra = f" [LD dzień {lockdown_trigger_day:.0f}]" if name == DELAYED_KEY else ""
    print(f"{label:<35} {s['peak_I_mean']:>6.0f}  "
          f"{s['attack_rate']:>8.1f}%  "
          f"{s['total_deaths']:>6.1f}  "
          f"{s['peak_day']:>8.1f}{extra}")
print("=" * 76)

with open(out_dir / "stage3_stats.txt", "w") as f:
    f.write(f"Stage 3 Summary Statistics\nN={N_AGENTS}, steps={STEPS}, runs={N_RUNS}\n")
    if lockdown_trigger_day is not None:
        f.write(f"Reactive lockdown threshold: I >= {LOCKDOWN_THRESHOLD} agents\n")
        f.write(f"Average lockdown trigger day: {lockdown_trigger_day:.1f}\n")
    f.write("\n")
    for name, s in summary.items():
        f.write(f"{name.replace(chr(10), ' ')}\n")
        for k, v in s.items():
            f.write(f"  {k}: {v:.2f}\n")
        if name == DELAYED_KEY and lockdown_trigger_day is not None:
            f.write(f"  avg_lockdown_day: {lockdown_trigger_day:.1f}\n")
        f.write("\n")

print("\nStatystyki zapisano do: data/output/stage3_stats.txt")
