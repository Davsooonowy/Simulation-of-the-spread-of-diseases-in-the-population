from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .space import POINode

ETA_M: float = 0.5


def compute_p_eff(
    p_base: float,
    susceptible_wears_mask: bool,
    infectious_wears_mask: bool,
    susceptible_social_distancing: bool,
    eta_m: float = ETA_M,
) -> float:
    """Return effective per-contact transmission probability with behavioural modifiers."""
    p = p_base
    if susceptible_wears_mask and infectious_wears_mask:
        p *= (1 - eta_m) ** 2
    elif susceptible_wears_mask or infectious_wears_mask:
        p *= (1 - eta_m)
    if susceptible_social_distancing:
        p *= 0.8
    return p


def compute_node_transmission(node: POINode, rng, eta_m: float = ETA_M) -> None:
    """Apply one-step within-node transmission for all S–I pairs.

    Survival probability product across infectious agents:
        survival = prod( (1 - p_eff_i)^viral_load_i  for i in infectious )
        P_inf    = (1 - survival) * (1 - immunity)
    """
    from .agents import State

    infectious = [a for a in node.agents if a.state == State.I]
    susceptible = [a for a in node.agents if a.state == State.S]

    if not infectious or not susceptible:
        return

    for s_agent in susceptible:
        survival_prob = 1.0
        for i_agent in infectious:
            p_eff = compute_p_eff(
                node.p_base,
                s_agent.wears_mask,
                i_agent.wears_mask,
                s_agent.social_distancing,
                eta_m,
            )
            p_contact = 1.0 - (1.0 - p_eff) ** i_agent.viral_load
            survival_prob *= 1.0 - p_contact

        p_final = (1.0 - survival_prob) * (1.0 - s_agent.immunity)

        if rng.random() < p_final:
            s_agent.state = State.E
            s_agent.days_in_state = 0
