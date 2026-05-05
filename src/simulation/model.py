from __future__ import annotations

from types import SimpleNamespace

import mesa
import yaml

from .agents import HumanAgent, State
from .space import CityGraph, POIType
from .transmission import compute_node_transmission


def _count(state: State):
    return lambda m: sum(1 for a in m.schedule.agents if a.state == state)


class EpidemicModel(mesa.Model):
    """
    SEIRD epidemic model on a POI graph.

    Each step represents one day. Agents visit: household (always),
    workplace/school (unless lockdown), and shop (30%, skipped when
    social_distancing=True). Transmission is computed per-node.

    Parameters
    ----------
    n_agents : int
    incubation_period : int
        Days in state E before becoming I.
    infectious_period : int
        Days in state I before recovering or dying.
    p_death : float
        Base probability of death at end of infectious period.
    initial_infected_frac : float
        Fraction of agents initialised as Infectious.
    mask_coverage : float
        Fraction of population wearing masks [0–1].
    social_distancing_coverage : float
        Fraction of population practising social distancing [0–1].
    vaccination_coverage : float
        Fraction of population vaccinated [0–1].
    lockdown : bool
        When True, agents skip their workplace/school node.
    p_base_override : dict[POIType, float] | None
        Override p_base for specific POI types.
    p_base_multiplier : float
        Scale all p_base values by this factor.
    eta_m : float
        Mask effectiveness coefficient (default 0.5 per report).
    p_transit : float
        Transmission probability on transit edges (default 0.05).
    """

    def __init__(
        self,
        n_agents: int = 500,
        incubation_period: int = 4,
        infectious_period: int = 8,
        p_death: float = 0.02,
        initial_infected_frac: float = 0.05,
        mask_coverage: float = 0.0,
        social_distancing_coverage: float = 0.0,
        vaccination_coverage: float = 0.0,
        lockdown: bool = False,
        p_base_override: dict[POIType, float] | None = None,
        p_base_multiplier: float = 1.0,
        eta_m: float = 0.5,
        p_transit: float = 0.05,
    ) -> None:
        super().__init__()

        self.incubation_period = incubation_period
        self.infectious_period = infectious_period
        self.p_death = p_death
        self.lockdown = lockdown
        self.eta_m = eta_m
        self.p_transit = p_transit
        self.transit_log: dict[tuple[POIType, POIType], dict] = {}

        self.city = CityGraph(n_agents, p_base_override, p_base_multiplier)
        self.schedule = mesa.time.RandomActivation(self)

        n_households = len(self.city.households)

        for i in range(n_agents):
            state = State.I if self.random.random() < initial_infected_frac else State.S
            age = self.random.randint(0, 80)

            household = self.city.households[i % n_households]

            if age < 18:
                workplace = self.random.choice(self.city.schools)
            elif age <= 65:
                workplace = self.random.choice(self.city.offices)
            else:
                workplace = None

            vaccinated = self.random.random() < vaccination_coverage
            immunity = 0.5 if vaccinated else 0.0

            agent = HumanAgent(
                unique_id=i,
                model=self,
                state=state,
                age=age,
                household_id=household.node_id,
                workplace_id=workplace.node_id if workplace else None,
                wears_mask=self.random.random() < mask_coverage,
                social_distancing=self.random.random() < social_distancing_coverage,
                vaccinated=vaccinated,
                immunity=immunity,
            )
            self.schedule.add(agent)

        self.datacollector = mesa.DataCollector(
            model_reporters={
                "S": _count(State.S),
                "E": _count(State.E),
                "I": _count(State.I),
                "R": _count(State.R),
                "D": _count(State.D),
            }
        )
        self.datacollector.collect(self)

    def step(self) -> None:
        # 1. Clear previous day's POI assignments
        self.city.clear_agents()

        # 2. Update viral loads and plan destinations
        agent_destinations: dict[int, list[int]] = {}
        for agent in self.schedule.agents:
            if agent.state != State.D:
                agent.update_viral_load()
                agent_destinations[agent.unique_id] = agent._plan_day()

        # 3. Transmit during transit (before arriving at destinations)
        self._run_transit(agent_destinations)

        # 4. Place agents in their destination nodes
        for agent in self.schedule.agents:
            if agent.state != State.D:
                for node_id in agent_destinations.get(agent.unique_id, []):
                    self.city.get_node(node_id).agents.append(agent)

        # 5. Transmit within each POI node
        for node in self.city.all_nodes():
            compute_node_transmission(node, self.random, self.eta_m)

        # 6. Progress disease states (calls agent.step() in random order)
        self.schedule.step()

        # 7. Refresh viral loads to reflect post-progression state
        for agent in self.schedule.agents:
            agent.update_viral_load()

        self.datacollector.collect(self)

    def _run_transit(self, agent_destinations: dict[int, list[int]]) -> None:
        """Simulate transmission between agents sharing a transit edge."""
        edge_agents: dict[tuple[POIType, POIType], list[HumanAgent]] = {}
        for agent in self.schedule.agents:
            if agent.state == State.D:
                continue
            dests = agent_destinations.get(agent.unique_id, [])
            for dest_id in dests[1:]:
                dest_type = self.city.get_node(dest_id).poi_type
                key = (POIType.HOUSEHOLD, dest_type)
                edge_agents.setdefault(key, []).append(agent)

        self.transit_log = {
            k: {"count": len(v), "infectious": sum(1 for a in v if a.state == State.I)}
            for k, v in edge_agents.items()
        }

        if self.p_transit > 0.0:
            for agents_on_edge in edge_agents.values():
                if len(agents_on_edge) >= 2:
                    transit_node = SimpleNamespace(
                        p_base=self.p_transit, agents=agents_on_edge
                    )
                    compute_node_transmission(transit_node, self.random, self.eta_m)

    @classmethod
    def from_config(cls, config_path: str, **overrides) -> EpidemicModel:
        """Create model from a YAML config file with optional parameter overrides."""
        with open(config_path) as f:
            config = yaml.safe_load(f)

        pathogen = config.get("pathogen", {})
        transmission = config.get("transmission", {})

        p_base_yaml = transmission.get("p_base", {})
        p_base_override: dict[POIType, float] = {
            POIType[name.upper()]: float(val)
            for name, val in p_base_yaml.items()
        }

        params: dict = {
            "incubation_period": pathogen.get("incubation_period", 4),
            "infectious_period": pathogen.get("infectious_period", 8),
            "p_death": pathogen.get("p_death", 0.02),
            "initial_infected_frac": pathogen.get("initial_infected_frac", 0.05),
            "eta_m": transmission.get("eta_m", 0.5),
            "lockdown": config.get("lockdown", False),
            "p_base_override": p_base_override or None,
        }
        params.update(overrides)
        return cls(**params)
