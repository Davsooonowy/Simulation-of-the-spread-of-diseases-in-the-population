from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING

import mesa

if TYPE_CHECKING:
    from .model import EpidemicModel


class State(IntEnum):
    S = 0
    E = 1
    I = 2
    R = 3
    D = 4


class HumanAgent(mesa.Agent):
    """SEIRD agent with demographic, clinical, and behavioural attributes."""

    def __init__(
        self,
        unique_id: int,
        model: EpidemicModel,
        state: State = State.S,
        age: int = 30,
        household_id: int = 0,
        workplace_id: int | None = None,
        wears_mask: bool = False,
        social_distancing: bool = False,
        vaccinated: bool = False,
        immunity: float = 0.0,
        hygiene_score: float = 0.5,
        contact_rate: float = 1.0,
    ) -> None:
        super().__init__(unique_id, model)
        self.state = state
        self.days_in_state: int = 0
        self.age = age
        self.age_group = self._age_group(age)
        self.household_id = household_id
        self.workplace_id = workplace_id
        self.wears_mask = wears_mask
        self.social_distancing = social_distancing
        self.vaccinated = vaccinated
        self.immunity = immunity
        self.hygiene_score = hygiene_score
        self.contact_rate = contact_rate
        self.viral_load: float = 0.0

    @staticmethod
    def _age_group(age: int) -> str:
        if age < 18:
            return "child"
        if age <= 65:
            return "adult"
        return "senior"

    # ------------------------------------------------------------------
    # Called by EpidemicModel.step() before schedule.step()
    # ------------------------------------------------------------------

    def update_viral_load(self) -> None:
        """Update viral_load based on current clinical state and days elapsed."""
        if self.state == State.E:
            self.viral_load = self.days_in_state / self.model.incubation_period
        elif self.state == State.I:
            self.viral_load = max(
                0.0, 1.0 - self.days_in_state / self.model.infectious_period
            )
        else:
            self.viral_load = 0.0

    def _plan_day(self) -> list[int]:
        """Return list of node_ids to visit today (household always first)."""
        destinations = [self.household_id]
        if self.workplace_id is not None and not self.model.lockdown:
            destinations.append(self.workplace_id)
        if not self.social_distancing and self.random.random() < 0.3:
            shop = self.random.choice(self.model.city.shops)
            destinations.append(shop.node_id)
        return destinations

    # ------------------------------------------------------------------
    # Mesa step — called by RandomActivation.step()
    # ------------------------------------------------------------------

    def step(self) -> None:
        if self.state == State.D:
            return
        self._progress_disease()
        self.days_in_state += 1

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _progress_disease(self) -> None:
        if self.state == State.E:
            if self.days_in_state >= self.model.incubation_period:
                self.state = State.I
                self.days_in_state = 0

        elif self.state == State.I:
            if self.days_in_state >= self.model.infectious_period:
                p_death = self.model.p_death * (0.2 if self.vaccinated else 1.0)
                if self.random.random() < p_death:
                    self.state = State.D
                else:
                    self.state = State.R
                self.days_in_state = 0
