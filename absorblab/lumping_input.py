"""Labeled raw-chain aggregation contract, independent of analysis."""

import re
from .input import validate as validate_chain

LIMITS = [
    "One to six supplied finite Markov states and exact positive rational transitions; supplied probabilities, not learned or calibrated behavior.",
    "Each state has one supplied observation tag and a derived success/failure/nonterminal status. Both must be preserved by every allowed partition.",
    "Strong lumpability tests the original transition matrix, not the first-hit stopped matrix. Original outgoing terminal transitions remain visible for this stronger equivalence.",
    "Every same-block pair must send exactly equal mass to every block. Matching only immediate goal probabilities or averaging unequal rows does not meet this criterion.",
    "The final partition is the coarsest observation/status-respecting stable refinement, checked against all set partitions. No tolerance, nearest-state heuristic, weak or approximate lumpability.",
    "Exact quotient identities preserve block distributions for any starting state and all step counts. Displayed finite forecasts and first-hit moments are additional bounded checks, not the reason for the all-step guarantee.",
    "Finite exhaustive evidence, not a scalable reduction tool, a complete PCTL model checker, reward-preservation claim, causal intervention or verified real-world agent guarantee.",
]


def validate(data):
    if type(data) is not dict or set(data) != {"chain", "observations"}:
        raise ValueError("lumping request needs exactly chain and observations")
    chain = validate_chain(data["chain"])
    obs = data["observations"]
    if type(obs) is not list or len(obs) != len(chain["states"]):
        raise ValueError("one observation tag per state is required")
    if any(
        type(x) is not str or not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]{0,23}", x)
        for x in obs
    ):
        raise ValueError("observation tags must be short ASCII identifiers")
    return {"chain": chain, "observations": obs[:]}
