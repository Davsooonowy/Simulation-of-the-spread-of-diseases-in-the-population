from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .space import POINode

ETA_M: float = 0.5

# Each susceptible agent has close contact with at most this many infectious
# agents per location per step. Prevents runaway transmission in large nodes
# (e.g. 90 agents sharing one office) while preserving pair-wise calibration.
MAX_INFECTIOUS_CONTACTS: int = 5


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

    Each susceptible contacts at most MAX_INFECTIOUS_CONTACTS infectious agents
    (sampled uniformly), preventing super-spreading artefacts from large nodes.

    Survival probability across sampled contacts:
        survival = prod( (1 - p_eff_i)^viral_load_i  for i in sampled )
        P_inf    = (1 - survival) * (1 - immunity)

    Hygiene reduces transmission: avg_hygiene=0.5 → factor 1.0 (neutral);
    avg_hygiene=1.0 → −30%; avg_hygiene=0.0 → +30%.
    """
    from .agents import State

    infectious = [a for a in node.agents if a.state == State.I]
    susceptible = [a for a in node.agents if a.state == State.S]

    if not infectious or not susceptible:
        return

    for s_agent in susceptible:
        s_hygiene: float = getattr(s_agent, "hygiene_score", 0.5)

        # Limit close contacts to avoid artefactual super-spreading in large nodes
        n_contacts = min(len(infectious), MAX_INFECTIOUS_CONTACTS)
        if len(infectious) > MAX_INFECTIOUS_CONTACTS:
            contacts = rng.sample(infectious, n_contacts)
        else:
            contacts = infectious

        survival_prob = 1.0
        for i_agent in contacts:
            i_hygiene: float = getattr(i_agent, "hygiene_score", 0.5)
            avg_hygiene = (s_hygiene + i_hygiene) / 2.0
            hygiene_factor = 1.0 - 0.6 * (avg_hygiene - 0.5)  # ±30% effect
            p_eff = compute_p_eff(
                node.p_base,
                s_agent.wears_mask,
                i_agent.wears_mask,
                s_agent.social_distancing,
                eta_m,
            ) * hygiene_factor
            p_contact = 1.0 - (1.0 - p_eff) ** i_agent.viral_load
            survival_prob *= 1.0 - p_contact

        p_final = (1.0 - survival_prob) * (1.0 - s_agent.immunity)

        if rng.random() < p_final:
            s_agent.state = State.E
            s_agent.days_in_state = 0
