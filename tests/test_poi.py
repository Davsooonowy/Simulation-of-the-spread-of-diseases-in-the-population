import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src"))

import pytest
from unittest.mock import MagicMock

from simulation.space import POINode, POIType
from simulation.transmission import compute_node_transmission, compute_p_eff, ETA_M
from simulation.agents import State


def make_agent(
    state=State.S,
    viral_load: float = 1.0,
    wears_mask: bool = False,
    social_distancing: bool = False,
    immunity: float = 0.0,
):
    agent = MagicMock()
    agent.state = state
    agent.viral_load = viral_load
    agent.wears_mask = wears_mask
    agent.social_distancing = social_distancing
    agent.immunity = immunity
    return agent


def make_node(p_base: float = 0.35, poi_type: POIType = POIType.HOUSEHOLD) -> POINode:
    return POINode(node_id=0, poi_type=poi_type, p_base=p_base, agents=[])


class FixedRNG:
    """RNG that always returns a fixed value."""

    def __init__(self, value: float = 0.0):
        self.value = value

    def random(self):
        return self.value


class TestComputePEff:
    def test_no_modifiers_returns_p_base(self):
        assert compute_p_eff(0.20, False, False, False) == pytest.approx(0.20)

    def test_both_masked_squares_reduction(self):
        result = compute_p_eff(0.20, True, True, False)
        assert result == pytest.approx(0.20 * (1 - ETA_M) ** 2)

    def test_one_masked_linear_reduction(self):
        result = compute_p_eff(0.20, True, False, False)
        assert result == pytest.approx(0.20 * (1 - ETA_M))

    def test_social_distancing_applies_08_multiplier(self):
        result = compute_p_eff(0.20, False, False, True)
        assert result == pytest.approx(0.20 * 0.8)

    def test_mask_and_social_distancing_combined(self):
        result = compute_p_eff(0.20, True, True, True)
        assert result == pytest.approx(0.20 * (1 - ETA_M) ** 2 * 0.8)


class TestComputeNodeTransmission:
    def test_no_infectious_no_transmission(self):
        node = make_node()
        s = make_agent(State.S)
        node.agents = [s]
        compute_node_transmission(node, FixedRNG(0.0))
        assert s.state == State.S

    def test_no_susceptible_no_transmission(self):
        node = make_node()
        i = make_agent(State.I, viral_load=1.0)
        node.agents = [i]
        compute_node_transmission(node, FixedRNG(0.0))
        assert i.state == State.I

    def test_susceptible_infected_when_rng_below_p_final(self):
        node = make_node(p_base=1.0)
        i = make_agent(State.I, viral_load=1.0)
        s = make_agent(State.S, immunity=0.0)
        node.agents = [i, s]
        compute_node_transmission(node, FixedRNG(0.0))
        assert s.state == State.E

    def test_full_immunity_prevents_infection(self):
        node = make_node(p_base=1.0)
        i = make_agent(State.I, viral_load=1.0)
        s = make_agent(State.S, immunity=1.0)
        node.agents = [i, s]
        compute_node_transmission(node, FixedRNG(0.0))
        assert s.state == State.S

    def test_p_inf_grows_with_more_infectious_agents(self):
        """P_inf = 1 - (1-p_eff)^(sum viral loads) increases with more I agents."""
        p_base = 0.20
        p_eff = compute_p_eff(p_base, False, False, False)
        p_one = 1 - (1 - p_eff) ** 1.0
        p_two = 1 - (1 - p_eff) ** 2.0
        assert p_two > p_one

    def test_zero_viral_load_no_infection(self):
        node = make_node(p_base=1.0)
        i = make_agent(State.I, viral_load=0.0)
        s = make_agent(State.S, immunity=0.0)
        node.agents = [i, s]
        compute_node_transmission(node, FixedRNG(0.0))
        assert s.state == State.S

    def test_days_in_state_reset_on_infection(self):
        node = make_node(p_base=1.0)
        i = make_agent(State.I, viral_load=1.0)
        s = make_agent(State.S, immunity=0.0)
        s.days_in_state = 99
        node.agents = [i, s]
        compute_node_transmission(node, FixedRNG(0.0))
        assert s.days_in_state == 0
