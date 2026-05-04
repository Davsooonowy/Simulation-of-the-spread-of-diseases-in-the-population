"""Analiza wrażliwości modelu na p_base_multiplier i eta_m.

Uruchomienie:
    uv run python scripts/sensitivity_analysis.py

Wynik: data/output/sensitivity_heatmap.png
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src"))

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from simulation.model import EpidemicModel

P_BASE_MULTIPLIERS = [0.5, 0.75, 1.0, 1.25, 1.5]
ETA_M_VALUES = [0.3, 0.4, 0.5, 0.6, 0.7]
N_RUNS = 3
STEPS = 100
N_AGENTS = 500
MASK_COVERAGE = 0.5

n_rows = len(ETA_M_VALUES)
n_cols = len(P_BASE_MULTIPLIERS)

peak_i_grid = np.zeros((n_rows, n_cols))
attack_rate_grid = np.zeros((n_rows, n_cols))

total = n_rows * n_cols
done = 0

print(f"Analiza wrażliwości: {total} kombinacji × {N_RUNS} uruchomień = {total * N_RUNS} symulacji")
print(f"mask_coverage={MASK_COVERAGE*100:.0f}%, N={N_AGENTS}, {STEPS} kroków\n")

for j, mult in enumerate(P_BASE_MULTIPLIERS):
    for i, eta_m in enumerate(ETA_M_VALUES):
        peaks, attacks = [], []
        for run in range(N_RUNS):
            model = EpidemicModel(
                n_agents=N_AGENTS,
                mask_coverage=MASK_COVERAGE,
                p_base_multiplier=mult,
                eta_m=eta_m,
            )
            for _ in range(STEPS):
                model.step()
            df = model.datacollector.get_model_vars_dataframe()
            peaks.append(df["I"].max())
            attacks.append(
                (df["R"].iloc[-1] + df["D"].iloc[-1]) / N_AGENTS * 100
            )

        peak_i_grid[i, j] = float(np.mean(peaks))
        attack_rate_grid[i, j] = float(np.mean(attacks))
        done += 1
        print(
            f"  [{done:2d}/{total}] mult={mult:.2f}  eta_m={eta_m:.1f}"
            f"  →  peak_I={peak_i_grid[i,j]:.0f}  attack={attack_rate_grid[i,j]:.1f}%"
        )

x_labels = [f"{m:.2f}" for m in P_BASE_MULTIPLIERS]
y_labels = [f"{e:.1f}" for e in ETA_M_VALUES]

fig, axes = plt.subplots(1, 2, figsize=(14, 5))

sns.heatmap(
    peak_i_grid,
    ax=axes[0],
    xticklabels=x_labels,
    yticklabels=y_labels,
    annot=True,
    fmt=".0f",
    cmap="YlOrRd",
    cbar_kws={"label": "Agenci"},
)
axes[0].set_xlabel("p_base multiplier")
axes[0].set_ylabel("η_M (skuteczność maseczki)")
axes[0].set_title("Szczyt zakaźnych (Peak I)")

sns.heatmap(
    attack_rate_grid,
    ax=axes[1],
    xticklabels=x_labels,
    yticklabels=y_labels,
    annot=True,
    fmt=".1f",
    cmap="YlOrRd",
    cbar_kws={"label": "%"},
)
axes[1].set_xlabel("p_base multiplier")
axes[1].set_ylabel("η_M (skuteczność maseczki)")
axes[1].set_title("Attack Rate (%)")

fig.suptitle(
    f"Analiza wrażliwości — mask_coverage={MASK_COVERAGE*100:.0f}%, "
    f"N={N_AGENTS}, {N_RUNS} runs/cell"
)
fig.tight_layout()

out = pathlib.Path(__file__).parent.parent / "data" / "output" / "sensitivity_heatmap.png"
plt.savefig(out, dpi=150)
print(f"\nHeatmapa zapisana do: {out}")
plt.show()
