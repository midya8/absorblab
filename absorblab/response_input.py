"""Strict one-row probability-transfer contract, independent of analysis."""
from fractions import Fraction as F
import re
from .input import validate as validate_chain

LIMITS = [
    "One to six supplied finite states and exact rational probabilities, not learned or calibrated behavior.",
    "One nonterminal row transfers mass between two distinct destinations; other rows are fixed.",
    "First success or failure stops the chain. Terminal outgoing transitions do not affect these first-hit quantities.",
    "The open transfer interval has fixed positive support. Endpoints are solved separately and may disagree with interior limits.",
    "Restricted expected visits concern the displayed concrete chain's terminal-reachable nonterminal set; visits in excluded closed classes are not claimed finite.",
    "Success-conditioned traffic is undefined at zero success probability; terminal success roots have zero traffic.",
    "Derivatives describe the supplied row family, not causal intervention effects, robustness, learned model uncertainty or optimal policies.",
    "Classical finite-chain and rank-one inverse formulas, not new theory, a general parametric model checker or a scaling benchmark.",
]

def validate(data):
    keys = {"chain", "row", "donor", "receiver", "at"}
    if type(data) is not dict or set(data) != keys:
        raise ValueError("response request needs exactly chain, row, donor, receiver and at")
    chain = validate_chain(data["chain"])
    names = [s["name"] for s in chain["states"]]
    for key in ("row", "donor", "receiver"):
        if type(data[key]) is not str or data[key] not in names:
            raise ValueError(key + " must be a declared state")
    if data["row"] in chain["success"] + chain["failure"]:
        raise ValueError("the transferred row must be nonterminal")
    if data["donor"] == data["receiver"]:
        raise ValueError("donor and receiver must be distinct")
    raw = data["at"]
    if type(raw) is not str or not re.fullmatch(r"-?(?:0|[1-9][0-9]{0,6})(?:/[1-9][0-9]{0,6})?", raw):
        raise ValueError("at must be a bounded exact signed rational string")
    if any(abs(int(v)) > 1000000 for v in raw.split("/")):
        raise ValueError("at numerator/denominator exceeds 1000000")
    t = F(raw)
    state = chain["states"][names.index(data["row"])]
    row = {v["to"]: F(v["prob"]) for v in state["transitions"]}
    lower, upper = -row.get(data["receiver"], F(0)), row.get(data["donor"], F(0))
    if lower == upper:
        raise ValueError("the varied destinations need positive combined mass")
    if not lower <= t <= upper:
        raise ValueError("at is outside the admissible probability-transfer interval")
    return {"chain": chain, "row": data["row"], "donor": data["donor"], "receiver": data["receiver"], "at": str(t)}
