import mesa
from .agents import HumanAgent, State


def _count(state: State):
    return lambda m: sum(1 for a in m.schedule.agents if a.state == state)


class EpidemicModel(mesa.Model):
    """
    SEIRD agent-based epidemic model on a MultiGrid.

    Parameters
    ----------
    n_agents : int
        Total number of human agents.
    width, height : int
        Grid dimensions (torus topology).
    p_inf : float
        Probability that an Infectious agent infects a Susceptible
        neighbour in one step.
    incubation_period : int
        Steps (days) an agent spends in state E before becoming I.
    infectious_period : int
        Steps (days) an agent spends in state I before recovering/dying.
    p_death : float
        Probability of death at the end of the infectious period.
    initial_infected_frac : float
        Fraction of agents initialised as I (index cases).
    """

    def __init__(
        self,
        n_agents: int = 500,
        width: int = 50,
        height: int = 50,
        p_inf: float = 0.20,
        incubation_period: int = 4,
        infectious_period: int = 8,
        p_death: float = 0.02,
        initial_infected_frac: float = 0.05,
    ) -> None:
        super().__init__()

        self.n_agents = n_agents
        self.p_inf = p_inf
        self.incubation_period = incubation_period
        self.infectious_period = infectious_period
        self.p_death = p_death

        self.grid = mesa.space.MultiGrid(width, height, torus=True)
        self.schedule = mesa.time.RandomActivation(self)

        for i in range(n_agents):
            state = State.I if self.random.random() < initial_infected_frac else State.S
            agent = HumanAgent(i, self, state=state)
            self.schedule.add(agent)
            x = self.random.randrange(width)
            y = self.random.randrange(height)
            self.grid.place_agent(agent, (x, y))

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
        self.schedule.step()
        self.datacollector.collect(self)
