import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src"))

import pytest
from simulation.model import EpidemicModel
from simulation.agents import State


def make_model(**kwargs) -> EpidemicModel:
    defaults = dict(
        n_agents=10,
        incubation_period=4,
        infectious_period=8,
        p_death=0.02,
        initial_infected_frac=0.0,
        mask_coverage=0.0,
        social_distancing_coverage=0.0,
        vaccination_coverage=0.0,
    )
    defaults.update(kwargs)
    return EpidemicModel(**defaults)


class TestDeadAgent:
    def test_dead_agent_stays_dead(self):
        model = make_model()
        agent = model.schedule.agents[0]
        agent.state = State.D
        agent.days_in_state = 0
        for _ in range(5):
            model.step()
        assert agent.state == State.D

    def test_dead_agent_viral_load_stays_zero(self):
        model = make_model()
        agent = model.schedule.agents[0]
        agent.state = State.D
        model.step()
        assert agent.viral_load == 0.0


class TestExposedToInfectious:
    def test_e_becomes_i_after_incubation_period(self):
        """E→I transition after incubation_period+1 steps (check before increment)."""
        model = make_model(incubation_period=3)
        agent = model.schedule.agents[0]
        agent.state = State.E
        agent.days_in_state = 0
        for _ in range(4):  # incubation_period + 1
            model.step()
        assert agent.state == State.I

    def test_e_stays_e_before_threshold(self):
        model = make_model(incubation_period=5)
        agent = model.schedule.agents[0]
        agent.state = State.E
        agent.days_in_state = 0
        for _ in range(4):
            model.step()
        assert agent.state == State.E

    def test_viral_load_grows_in_e(self):
        model = make_model(incubation_period=4)
        agent = model.schedule.agents[0]
        agent.state = State.E
        agent.days_in_state = 0
        model.step()
        assert agent.viral_load > 0.0


class TestInfectiousOutcome:
    def test_i_recovers_with_p_death_zero(self):
        model = make_model(infectious_period=4, p_death=0.0)
        agent = model.schedule.agents[0]
        agent.state = State.I
        agent.days_in_state = 0
        for _ in range(5):  # infectious_period + 1
            model.step()
        assert agent.state == State.R

    def test_i_dies_with_p_death_one(self):
        model = make_model(infectious_period=4, p_death=1.0)
        agent = model.schedule.agents[0]
        agent.state = State.I
        agent.days_in_state = 0
        for _ in range(5):
            model.step()
        assert agent.state == State.D

    def test_vaccinated_reduces_death_rate(self):
        """Vaccinated p_death = base × 0.2, so vaccinated agents die far less often."""
        deaths_vacc = 0
        deaths_unvacc = 0
        for seed in range(200):
            for vaccinated, counter in [(True, "v"), (False, "u")]:
                m = make_model(infectious_period=4, p_death=0.5)
                m.random.seed(seed)
                a = m.schedule.agents[0]
                a.state = State.I
                a.vaccinated = vaccinated
                a.days_in_state = 0
                for _ in range(5):
                    m.step()
                if a.state == State.D:
                    if vaccinated:
                        deaths_vacc += 1
                    else:
                        deaths_unvacc += 1

        assert deaths_vacc < deaths_unvacc


class TestSocialDistancing:
    def test_social_distancing_agent_skips_shop(self):
        model = make_model(n_agents=1, social_distancing_coverage=1.0)
        agent = model.schedule.agents[0]
        assert agent.social_distancing is True

        model.step()

        for shop in model.city.shops:
            assert agent not in shop.agents

    def test_lockdown_prevents_workplace_visits(self):
        model = make_model(n_agents=20, lockdown=True)
        model.step()

        for office in model.city.offices:
            assert len(office.agents) == 0
        for school in model.city.schools:
            assert len(school.agents) == 0


class TestFromConfig:
    def test_from_config_loads_base_params(self):
        config_path = (
            pathlib.Path(__file__).parent.parent / "configs" / "pathogen_base.yaml"
        )
        model = EpidemicModel.from_config(str(config_path), n_agents=20)
        assert model.incubation_period == 4
        assert model.infectious_period == 8
        assert model.lockdown is False

    def test_from_config_lockdown_scenario(self):
        config_path = (
            pathlib.Path(__file__).parent.parent / "configs" / "scenario_lockdown.yaml"
        )
        model = EpidemicModel.from_config(str(config_path), n_agents=20)
        assert model.lockdown is True
        from simulation.space import POIType
        override = model.city.get_nodes_by_type(POIType.OFFICE)
        assert all(n.p_base == 0.0 for n in override)
