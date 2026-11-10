"""Strict bounded public-data schema; no analysis code."""

from fractions import Fraction
import json
import re

LIMITS = [
    "One to six supplied finite Markov states; one to six positive rational transitions per row.",
    "Probabilities are supplied, not learned, calibrated or adversarial choices.",
    "Success and failure are disjoint terminal sets; first hit overrides outgoing transitions.",
    "Closed nonterminal classes can prevent any terminal hit; equations alone need not identify the least solution.",
    "Success conditioning is undefined when its probability is zero, never an invented zero conditional mean.",
    "Unconditional time to success is infinite if stopped success has probability below one.",
    "Finite exact coverage is not a proof, scaling benchmark, runtime guarantee or new algorithm.",
]


def validate(data):
    if type(data) is not dict or set(data) != {
        "states",
        "success",
        "failure",
        "horizon",
    }:
        raise ValueError(
            "request requires exactly states, success, failure and horizon"
        )
    states = data["states"]
    if type(states) is not list or not 1 <= len(states) <= 6:
        raise ValueError("states must have length 1..6")
    names = []
    for s in states:
        if type(s) is not dict or set(s) != {"name", "transitions"}:
            raise ValueError("each state requires name and transitions")
        n = s["name"]
        if type(n) is not str or not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]{0,23}", n):
            raise ValueError("state names must be short ASCII identifiers")
        if n in names:
            raise ValueError("state names must be unique")
        names.append(n)
    normalized = []
    for s in states:
        ts = s["transitions"]
        seen = set()
        out = []
        total = Fraction(0)
        if type(ts) is not list or not 1 <= len(ts) <= 6:
            raise ValueError("each row requires 1..6 transitions")
        for t in ts:
            if type(t) is not dict or set(t) != {"to", "prob"}:
                raise ValueError("transition requires to and prob")
            n = t["to"]
            raw = t["prob"]
            if type(n) is not str or n not in names or n in seen:
                raise ValueError("targets must be declared and unique per row")
            if type(raw) is not str or not re.fullmatch(
                r"[1-9][0-9]{0,6}(?:/[1-9][0-9]{0,6})?", raw
            ):
                raise ValueError("prob must be a positive rational string")
            parts = list(map(int, raw.split("/")))
            if max(parts) > 1000000:
                raise ValueError("prob numerator/denominator exceeds 1000000")
            p = Fraction(raw)
            if not 0 < p <= 1:
                raise ValueError("probability must be in (0,1]")
            seen.add(n)
            total += p
            out.append({"to": n, "prob": str(p)})
        if total != 1:
            raise ValueError("each transition row must sum exactly to one")
        normalized.append({"name": s["name"], "transitions": out})
    sets = []
    for key in ["success", "failure"]:
        xs = data[key]
        if (
            type(xs) is not list
            or any(type(n) is not str or n not in names for n in xs)
            or len(xs) != len(set(xs))
        ):
            raise ValueError(key + " must be unique declared names")
        sets.append([n for n in names if n in xs])
    if set(sets[0]) & set(sets[1]):
        raise ValueError("success and failure must be disjoint")
    h = data["horizon"]
    if type(h) is not int or not 0 <= h <= 12:
        raise ValueError("horizon must be an integer in 0..12")
    return {"states": normalized, "success": sets[0], "failure": sets[1], "horizon": h}


def load(raw):
    def obj(pairs):
        d = {}
        for k, v in pairs:
            if k in d:
                raise ValueError("duplicate JSON key")
            d[k] = v
        return d

    def bad(s):
        raise ValueError("nonfinite JSON is not accepted")

    return json.loads(raw, object_pairs_hook=obj, parse_constant=bad)


def equal(expected, actual, path="$"):
    if type(expected) is not type(actual):
        raise ValueError("type mismatch at " + path)
    if type(expected) is dict:
        if set(expected) != set(actual):
            raise ValueError("keys mismatch at " + path)
        for k in expected:
            equal(expected[k], actual[k], path + "." + k)
    elif type(expected) is list:
        if len(expected) != len(actual):
            raise ValueError("length mismatch at " + path)
        for i, (a, b) in enumerate(zip(expected, actual)):
            equal(a, b, path + "[" + str(i) + "]")
    elif expected != actual:
        raise ValueError("value mismatch at " + path)
