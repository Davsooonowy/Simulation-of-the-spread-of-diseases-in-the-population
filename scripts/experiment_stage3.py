"""Stage 3 experiment: compare epidemic scenarios with multiple reproducible runs.

Scenarios
---------
1. Baseline                — brak interwencji
2. Lockdown natychmiastowy — lockdown od dnia 0
3. Lockdown reaktywny      — lockdown gdy I >= 5% populacji
4. Szczepienia 60%
5. Superspreaderzy 5%
6. Wysoka higiena (Θ = 0.85)
7. Interwencje łączone     — maski 50% + higiena 0.70 + szczepienia 40%  ← NOWY

Reproducibility
---------------
Każdy bieg używa stałego ziarna (BASE_SEED + indeks biegu), więc cały
eksperyment jest w pełni odtwarzalny.

Run:
    uv run python scripts/experiment_stage3.py

Outputs (saved to data/output/ and reports/report1/):
    stage3_comparison.png        — siatka krzywych SEIRD
    stage3_summary.png           — słupkowe porównanie wskaźników
    stage3_i_curves.png          — nałożone krzywe I
    stage3_hygiene.png           — porównanie poziomów higieny
    stage3_lockdown_compare.png  — porównanie strategii lockdownu
    stage3_rt.png                — efektywne R(t) dla scenariuszy   ← NOWY
    stage3_hospital.png          — popyt na łóżka + osobodni > pojemności  ← NOWY
    stage3_stats.txt             — pełne statystyki + empiryczne R0
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src"))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from simulation.model import EpidemicModel
from simulation.agents import State

# ─── experiment settings ──────────────────────────────────────────────────────
N_AGENTS           = 500
STEPS              = 180
N_RUNS             = 7
BASE_SEED          = 12345                  # ziarno bazowe — pełna odtwarzalność
LOCKDOWN_THRESHOLD = int(0.05 * N_AGENTS)   # 25 agentów = 5% populacji

# Pojemność systemu ochrony zdrowia (ilustracyjna, dla N=500)
HOSP_RATE     = 0.15   # frakcja aktywnie zakaźnych wymagających łóżka szpitalnego
HOSP_CAPACITY = 8      # liczba dostępnych łóżek (16 / 1000 mieszkańców)

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
    "Interwencje łączone\n(maski+higiena+szczep.)":   dict(
        **BASE_PARAMS, mask_coverage=0.50, mean_hygiene=0.70, vaccination_coverage=0.40
    ),
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
    "#009988",   # interwencje łączone
]

# ─── helpers ─────────────────────────────────────────────────────────────────

def run_scenario(params: dict, n_runs: int, steps: int, seed0: int) -> dict:
    """Return arrays (n_runs, steps+1) for each SEIRD compartment (reproducible)."""
    all_runs: dict[str, list] = {k: [] for k in "SEIRD"}
    for i in range(n_runs):
        m = EpidemicModel(**params, seed=seed0 + i)
        for __ in range(steps):
            m.step()
        df = m.datacollector.get_model_vars_dataframe()
        for k in "SEIRD":
            all_runs[k].append(df[k].values)
    return {k: np.array(v) for k, v in all_runs.items()}


def run_delayed_lockdown(
    params: dict, n_runs: int, steps: int, threshold: int, seed0: int
) -> tuple[dict, float]:
    """Lockdown aktywuje się gdy I >= threshold.

    Returns
    -------
    data : dict  — SEIRD arrays (n_runs, steps+1)
    avg_ld_day : float — średni dzień aktywacji lockdownu
    """
    all_runs: dict[str, list] = {k: [] for k in "SEIRD"}
    ld_days: list[int] = []

    for i in range(n_runs):
        m = EpidemicModel(**params, seed=seed0 + i)
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


def _smooth(x: np.ndarray, window: int = 9) -> np.ndarray:
    """Centred moving average (edge-padded) — smooths noisy daily series."""
    if window <= 1:
        return x
    pad = window // 2
    xp = np.pad(x, pad, mode="edge")
    kernel = np.ones(window) / window
    return np.convolve(xp, kernel, mode="valid")[: len(x)]


def compute_rt(data: dict, infectious_period: int,
               min_infectious: float = 5.0) -> np.ndarray:
    """Estimate the effective reproduction number R_e(t) from median trajectories.

    Each infectious agent produces, on average, ``incidence(t) / I(t)`` new
    infections per day; over its whole infectious period of ``T_I`` days this
    yields ``R_e(t) = incidence(t) / I(t) * T_I``.  incidence(t)=S(t-1)-S(t)
    because S only ever flows to E.  Values where the (smoothed) infectious pool
    is below ``min_infectious`` are masked (NaN) to avoid division noise as I→0.
    """
    S_med = np.median(data["S"], axis=0)
    I_med = np.median(data["I"], axis=0)

    incidence = np.clip(-np.diff(S_med, prepend=S_med[0]), 0, None)
    inc_s = _smooth(incidence)
    I_s = _smooth(I_med)

    with np.errstate(divide="ignore", invalid="ignore"):
        rt = inc_s / I_s * infectious_period
    rt[I_s < min_infectious] = np.nan
    return rt


def hospital_metrics(data: dict, hosp_rate: float, capacity: float) -> dict:
    """Hospital bed demand and overload metrics derived from the I curve.

    Bed demand(t) = hosp_rate * I(t); overload(t) = max(0, demand - capacity).
    ``person_days_over`` is the time-integral of the overload (pole nad linią
    pojemności) — how much *and* how long the system is overwhelmed.
    """
    demand = hosp_rate * data["I"]                     # (n_runs, steps+1)
    overload = np.clip(demand - capacity, 0.0, None)
    person_days = overload.sum(axis=1)                 # per run
    return {
        "demand_median":   np.median(demand, axis=0),
        "peak_demand":     float(demand.max(axis=1).mean()),
        "pdays_mean":      float(person_days.mean()),
        "pdays_std":       float(person_days.std()),
        "any_overload":    bool((demand.max(axis=1) > capacity).any()),
    }


def empirical_r0(data: dict, infectious_period: int,
                 n_agents: int, max_attack: float = 0.15) -> float:
    """Empirical R0 = mean R_e over the early phase (before S depletion)."""
    rt = compute_rt(data, infectious_period)
    S_med = np.median(data["S"], axis=0)
    cumulative_attack = (n_agents - S_med) / n_agents
    early = (cumulative_attack < max_attack) & np.isfinite(rt)
    early[:2] = False                      # skip the first noisy days
    return float(np.nanmean(rt[early])) if early.any() else float("nan")

# ─── run all scenarios ────────────────────────────────────────────────────────

print(f"Stage 3 — {len(SCENARIOS)} scenariuszy × {N_RUNS} powtórzeń × {STEPS} kroków")
print(f"(ziarno bazowe={BASE_SEED}, w pełni odtwarzalne)\n")

results: dict[str, dict] = {}
summary: dict[str, dict] = {}
lockdown_trigger_day: float | None = None

DELAYED_KEY = f"Lockdown reaktywny\n(gdy I ≥ {LOCKDOWN_THRESHOLD} ag.)"

for idx, (name, params) in enumerate(SCENARIOS.items()):
    short = name.replace("\n", " ")
    print(f"[{idx+1}/{len(SCENARIOS)}] {short} …", end=" ", flush=True)
    seed0 = BASE_SEED + idx * 1000          # rozłączne pule ziaren per scenariusz

    if params is None:
        data, avg_ld = run_delayed_lockdown(
            BASE_PARAMS, N_RUNS, STEPS, LOCKDOWN_THRESHOLD, seed0
        )
        lockdown_trigger_day = avg_ld
    else:
        data = run_scenario(params, N_RUNS, STEPS, seed0)

    results[name] = data
    s = compute_summary(data, N_AGENTS)
    summary[name] = s

    extra = f"  [lockdown: dzień {avg_ld:.1f}]" if params is None else ""
    print(f"peak_I={s['peak_I_mean']:.0f}  "
          f"attack={s['attack_rate']:.1f}%  "
          f"deaths={s['total_deaths']:.1f}{extra}")

# empirical R0 from the baseline scenario
R0_EMP = empirical_r0(
    results["Scenariusz bazowy\n(brak interwencji)"],
    BASE_PARAMS["infectious_period"], N_AGENTS
)
print(f"\nEmpiryczne R0 (baseline, wczesna faza) = {R0_EMP:.2f}\n")

out_dir = pathlib.Path(__file__).parent.parent / "data" / "output"
rep_dir = pathlib.Path(__file__).parent.parent / "reports" / "report1"
out_dir.mkdir(parents=True, exist_ok=True)

days = np.arange(STEPS + 1)

# ─── figure 1: SEIRD comparison (2×4 grid; last panel hidden) ─────────────────

n_sc = len(SCENARIOS)
fig, axes = plt.subplots(2, 4, figsize=(22, 9), sharey=True)
axes_flat = axes.flatten()
fig.suptitle(
    "Stage 3 — Porównanie scenariuszy epidemicznych\n"
    f"(N={N_AGENTS} agentów, {STEPS} dni, mediana {N_RUNS} powtórzeń, ziarno={BASE_SEED})",
    fontsize=13, fontweight="bold"
)

for ax, (name, data), col in zip(axes_flat, results.items(), SCENARIO_COLORS):
    for k in ["S", "E", "I", "R", "D"]:
        med = np.median(data[k], axis=0)
        p25 = np.percentile(data[k], 25, axis=0)
        p75 = np.percentile(data[k], 75, axis=0)
        ax.plot(days, med, label=k, color=COLORS[k], linewidth=2)
        ax.fill_between(days, p25, p75, alpha=0.18, color=COLORS[k])

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

for ax in axes_flat[n_sc:]:          # hide unused panels
    ax.axis("off")
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

fig2, (ax_peak, ax_att, ax_d) = plt.subplots(1, 3, figsize=(17, 5))
fig2.suptitle("Stage 3 — Podsumowanie wyników scenariuszy",
              fontsize=13, fontweight="bold")

x = np.arange(len(short_names))
bar_kw = dict(width=0.6, capsize=4, error_kw=dict(elinewidth=1.2))

ax_peak.bar(x, [summary[n]["peak_I_mean"] for n in SCENARIOS],
            yerr=[summary[n]["peak_I_std"] for n in SCENARIOS],
            color=SCENARIO_COLORS, **bar_kw)
ax_peak.set_title("Szczyt zakaźnych (Peak I)", fontweight="bold")
ax_peak.set_ylabel("Agenci")
ax_peak.set_xticks(x); ax_peak.set_xticklabels(short_names, rotation=25, ha="right", fontsize=7.5)
ax_peak.grid(axis="y", alpha=0.3)

ax_att.bar(x, [summary[n]["attack_rate"] for n in SCENARIOS],
           yerr=[summary[n]["attack_std"] for n in SCENARIOS],
           color=SCENARIO_COLORS, **bar_kw)
ax_att.set_title("Attack Rate (%)", fontweight="bold")
ax_att.set_ylabel("%")
ax_att.set_xticks(x); ax_att.set_xticklabels(short_names, rotation=25, ha="right", fontsize=7.5)
ax_att.grid(axis="y", alpha=0.3)

ax_d.bar(x, [summary[n]["total_deaths"] for n in SCENARIOS],
         yerr=[summary[n]["deaths_std"] for n in SCENARIOS],
         color=SCENARIO_COLORS, **bar_kw)
ax_d.set_title("Łączne zgony (D)", fontweight="bold")
ax_d.set_ylabel("Agenci")
ax_d.set_xticks(x); ax_d.set_xticklabels(short_names, rotation=25, ha="right", fontsize=7.5)
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
    ax3.fill_between(days, p25, p75, alpha=0.12, color=col)

if lockdown_trigger_day is not None:
    ax3.axvline(lockdown_trigger_day, color="#ff9900", linestyle="--",
                linewidth=1.5, alpha=0.8, label=f"Reaktywny LD: dzień {lockdown_trigger_day:.0f}")

ax3.set_xlabel("Dzień symulacji", fontsize=12)
ax3.set_ylabel("Liczba zakaźnych (I)", fontsize=12)
ax3.set_title(
    f"Przebieg epidemii — krzywe I dla {n_sc} scenariuszy\n"
    f"(N={N_AGENTS}, mediana {N_RUNS} powtórzeń, pasmo IQR)",
    fontsize=12
)
ax3.legend(fontsize=8, loc="upper right")
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

for hidx, (name, params) in enumerate(HYGIENE_SCENARIOS.items()):
    data = run_scenario(params, N_RUNS, STEPS, BASE_SEED + 90000 + hidx * 1000)
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

# ─── figure 6: effective reproduction number R_e(t) ──────────────────────────

print("\nObliczanie efektywnego R(t) …")
RT_SHOW = [
    "Scenariusz bazowy\n(brak interwencji)",
    "Lockdown natychmiastowy\n(od dnia 0)",
    DELAYED_KEY,
    "Kampania szczepień\n(60% populacji)",
    "Interwencje łączone\n(maski+higiena+szczep.)",
]
rt_colors = {
    "Scenariusz bazowy\n(brak interwencji)":         "#4477aa",
    "Lockdown natychmiastowy\n(od dnia 0)":          "#ee6677",
    DELAYED_KEY:                                      "#ff9900",
    "Kampania szczepień\n(60% populacji)":           "#228833",
    "Interwencje łączone\n(maski+higiena+szczep.)":  "#009988",
}

fig6, ax6 = plt.subplots(figsize=(11, 6))
for name in RT_SHOW:
    rt = compute_rt(results[name], BASE_PARAMS["infectious_period"])
    ax6.plot(days, rt, label=name.replace("\n", " "),
             color=rt_colors[name], linewidth=2.2)

ax6.axhline(1.0, color="black", linestyle="--", linewidth=1.3, alpha=0.8)
ax6.text(STEPS * 0.7, 1.06, "próg epidemiczny $R_e = 1$", fontsize=9, color="black")

if lockdown_trigger_day is not None:
    ax6.axvline(lockdown_trigger_day, color="#ff9900", linestyle=":",
                linewidth=1.4, alpha=0.7)

ax6.set_xlabel("Dzień symulacji", fontsize=12)
ax6.set_ylabel("Efektywne $R_e(t)$", fontsize=12)
ax6.set_title(
    f"Efektywny współczynnik reprodukcji $R_e(t)$ — empiryczne $R_0 \\approx {R0_EMP:.1f}$\n"
    f"(mediana {N_RUNS} powtórzeń; maskowane przy I < 5)",
    fontsize=12
)
ax6.legend(fontsize=9, loc="upper right")
ax6.grid(alpha=0.3)
ax6.set_xlim(0, STEPS)
ax6.set_ylim(0, 4)
fig6.tight_layout()
fig6.savefig(out_dir / "stage3_rt.png", dpi=150, bbox_inches="tight")
fig6.savefig(rep_dir / "stage3_rt.png", dpi=150, bbox_inches="tight")
plt.close(fig6)
print("Zapisano: stage3_rt.png")

# ─── figure 7: hospital capacity & person-days over capacity ──────────────────

print("\nAnaliza pojemności szpitala "
      f"(łóżek={HOSP_CAPACITY}, odsetek hospitalizacji={HOSP_RATE:.0%}) …")

hosp = {name: hospital_metrics(data, HOSP_RATE, HOSP_CAPACITY)
        for name, data in results.items()}

name_color = dict(zip(SCENARIOS.keys(), SCENARIO_COLORS))

# scenariusze pokazane na wykresie krzywych popytu (gradient skuteczności)
HOSP_SHOW = [
    "Superspreaderzy\n(5% populacji)",
    "Scenariusz bazowy\n(brak interwencji)",
    "Wysoka higiena rąk\n(mean=0.85)",
    "Kampania szczepień\n(60% populacji)",
    "Interwencje łączone\n(maski+higiena+szczep.)",
]

fig7, (ax7a, ax7b) = plt.subplots(1, 2, figsize=(13, 5))
fig7.suptitle(
    f"Obciążenie systemu ochrony zdrowia (pojemność = {HOSP_CAPACITY} łóżek, "
    f"{HOSP_RATE:.0%} zakaźnych wymaga hospitalizacji)",
    fontsize=12, fontweight="bold"
)

ymax = max(hosp[n]["demand_median"].max() for n in HOSP_SHOW) * 1.1
ax7a.axhspan(HOSP_CAPACITY, ymax, color="red", alpha=0.07)
for name in HOSP_SHOW:
    ax7a.plot(days, hosp[name]["demand_median"],
              label=name.replace("\n", " "), color=name_color[name], linewidth=2.2)
ax7a.axhline(HOSP_CAPACITY, color="red", linestyle="--", linewidth=1.6)
ax7a.text(STEPS * 0.5, HOSP_CAPACITY + ymax * 0.02,
          f"pojemność = {HOSP_CAPACITY} łóżek", color="red", fontsize=9)
ax7a.set_title("Zapotrzebowanie na łóżka szpitalne", fontweight="bold")
ax7a.set_xlabel("Dzień"); ax7a.set_ylabel("Łóżka (popyt)")
ax7a.set_xlim(0, STEPS); ax7a.set_ylim(0, ymax)
ax7a.legend(fontsize=8); ax7a.grid(alpha=0.3)

x7 = np.arange(len(SCENARIOS))
ax7b.bar(x7, [hosp[n]["pdays_mean"] for n in SCENARIOS],
         yerr=[hosp[n]["pdays_std"] for n in SCENARIOS],
         color=SCENARIO_COLORS, width=0.6, capsize=4,
         error_kw=dict(elinewidth=1.2))
ax7b.set_title("Osobodni ponad pojemnością", fontweight="bold")
ax7b.set_ylabel("osobodni (łóżko·dzień)")
ax7b.set_xticks(x7)
ax7b.set_xticklabels([n.split("\n")[0] for n in SCENARIOS],
                     rotation=25, ha="right", fontsize=7.5)
ax7b.grid(axis="y", alpha=0.3)

fig7.tight_layout()
fig7.savefig(out_dir / "stage3_hospital.png", dpi=150, bbox_inches="tight")
fig7.savefig(rep_dir / "stage3_hospital.png", dpi=150, bbox_inches="tight")
plt.close(fig7)
print("Zapisano: stage3_hospital.png")

# ─── summary table ────────────────────────────────────────────────────────────

print("\n" + "=" * 92)
print(f"{'Scenariusz':<38} {'Peak I':>7} {'Attack%':>9} {'Zgony':>7} "
      f"{'DzieńMax':>9} {'Osobodni>cap':>13}")
print("-" * 92)
for name, s in summary.items():
    label = name.replace("\n", " ")[:37]
    extra = f" [LD d.{lockdown_trigger_day:.0f}]" if name == DELAYED_KEY else ""
    print(f"{label:<38} {s['peak_I_mean']:>6.0f}  "
          f"{s['attack_rate']:>8.1f}%  "
          f"{s['total_deaths']:>6.1f}  "
          f"{s['peak_day']:>8.1f}  "
          f"{hosp[name]['pdays_mean']:>11.1f}{extra}")
print("=" * 92)
print(f"Empiryczne R0 (baseline) = {R0_EMP:.2f}")
print(f"Pojemność szpitala = {HOSP_CAPACITY} łóżek, odsetek hospitalizacji = {HOSP_RATE:.0%}")

with open(out_dir / "stage3_stats.txt", "w") as f:
    f.write(f"Stage 3 Summary Statistics\n")
    f.write(f"N={N_AGENTS}, steps={STEPS}, runs={N_RUNS}, base_seed={BASE_SEED}\n")
    f.write(f"Empirical R0 (baseline, early phase): {R0_EMP:.3f}\n")
    f.write(f"Hospital: capacity={HOSP_CAPACITY} beds, hosp_rate={HOSP_RATE}\n")
    if lockdown_trigger_day is not None:
        f.write(f"Reactive lockdown threshold: I >= {LOCKDOWN_THRESHOLD} agents\n")
        f.write(f"Average lockdown trigger day: {lockdown_trigger_day:.1f}\n")
    f.write("\n")
    for name, s in summary.items():
        f.write(f"{name.replace(chr(10), ' ')}\n")
        for k, v in s.items():
            f.write(f"  {k}: {v:.2f}\n")
        f.write(f"  peak_bed_demand: {hosp[name]['peak_demand']:.2f}\n")
        f.write(f"  person_days_over_capacity: {hosp[name]['pdays_mean']:.2f}"
                f" (std {hosp[name]['pdays_std']:.2f})\n")
        if name == DELAYED_KEY and lockdown_trigger_day is not None:
            f.write(f"  avg_lockdown_day: {lockdown_trigger_day:.1f}\n")
        f.write("\n")

print("\nStatystyki zapisano do: data/output/stage3_stats.txt")
