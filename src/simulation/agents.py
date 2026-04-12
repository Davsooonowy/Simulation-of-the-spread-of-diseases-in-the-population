from enum import IntEnum
import mesa


class State(IntEnum):
    S = 0  # Susceptible
    E = 1  # Exposed (incubation)
    I = 2  # Infectious
    R = 3  # Recovered
    D = 4  # Dead


class HumanAgent(mesa.Agent):
    """A single human agent in the SEIRD epidemic simulation."""

    def __init__(self, unique_id: int, model: "EpidemicModel", state: State = State.S) -> None:
        super().__init__(unique_id, model)
        self.state = state
        self.days_in_state: int = 0

    # ------------------------------------------------------------------
    # Mesa step
    # ------------------------------------------------------------------

    def step(self) -> None:
        if self.state == State.D:
            return

        self._move()

        if self.state == State.I:
            self._try_infect_neighbors()

        self._progress_disease()
        self.days_in_state += 1

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _move(self) -> None:
        """Random walk to a neighbouring cell (Moore neighbourhood)."""
        neighbours = self.model.grid.get_neighborhood(
            self.pos, moore=True, include_center=False
        )
        new_pos = self.random.choice(neighbours)
        self.model.grid.move_agent(self, new_pos)

    def _try_infect_neighbors(self) -> None:
        """Infectious agent attempts to infect every susceptible neighbour."""
        cell_mates = self.model.grid.get_neighbors(
            self.pos, moore=True, include_center=False
        )
        for other in cell_mates:
            if other.state == State.S:
                if self.random.random() < self.model.p_inf:
                    other.state = State.E
                    other.days_in_state = 0

    def _progress_disease(self) -> None:
        """Advance clinical state based on elapsed days."""
        if self.state == State.E:
            if self.days_in_state >= self.model.incubation_period:
                self.state = State.I
                self.days_in_state = 0

        elif self.state == State.I:
            if self.days_in_state >= self.model.infectious_period:
                if self.random.random() < self.model.p_death:
                    self.state = State.D
                else:
                    self.state = State.R
                self.days_in_state = 0
