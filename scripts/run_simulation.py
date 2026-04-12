"""Run a single SEIRD simulation and plot epidemic curves."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src"))

import matplotlib.pyplot as plt
from simulation.model import EpidemicModel

STEPS = 100
PARAMS = dict(
    n_agents=500,
    width=50,
    height=50,
    p_inf=0.20,
    incubation_period=4,
    infectious_period=8,
    p_death=0.02,
    initial_infected_frac=0.05,
)

COLORS = {
    "S": "steelblue",
    "E": "orange",
    "I": "crimson",
    "R": "mediumseagreen",
    "D": "black",
}


def main() -> None:
    model = EpidemicModel(**PARAMS)

    for _ in range(STEPS):
        model.step()

    data = model.datacollector.get_model_vars_dataframe()

    fig, ax = plt.subplots(figsize=(10, 6))
    for col, color in COLORS.items():
        ax.plot(data.index, data[col], label=col, color=color, linewidth=2)

    ax.set_xlabel("Simulation step (day)")
    ax.set_ylabel("Number of agents")
    ax.set_title("SEIRD Epidemic Simulation — Agent-Based Model (Mesa)")
    ax.legend(fontsize=12)
    ax.grid(alpha=0.3)
    fig.tight_layout()

    out_path = pathlib.Path(__file__).parent.parent / "data" / "output" / "epidemic_curve.png"
    plt.savefig(out_path, dpi=150)
    print(f"Plot saved to {out_path}")

    print("\nFinal state counts:")
    print(data.iloc[-1].to_string())
    plt.show()


if __name__ == "__main__":
    main()
