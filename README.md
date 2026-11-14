# AbsorbLab

AbsorbLab works out exact first-hit probabilities, conditional times, and Doob transforms for small Markov chains you supply yourself.

Think of a workflow that retries a tool call, wanders into a risky branch, reaches its goal, fails outright, or gets stuck in a closed cycle. Those outcomes are easy to conflate, so AbsorbLab keeps them apart:

- What's the probability of first success, first failure, or never reaching either one?
- If success happens, how long does it take — conditional on it happening at all?
- Once you condition the whole trajectory on eventual success, what happens to the next-step distribution?
- By a given deadline, how much mass has finished, and how much successful mass is still out there?

There's no trained model here, no service account, no network inference, and no paid API. The Python side does its arithmetic with `Fraction`; the browser side uses reduced `BigInt` fractions. There are no runtime dependencies.

## Three questions, three pages

| Question | Page | What you'll see there |
| --- | --- | --- |
| Will the chain reach success, fail, or stay in a closed cycle? | [First hit](https://midya8.github.io/absorblab/) | First-hit mass, conditional time, support and elimination steps, finite-horizon forecasts. |
| Can states be grouped without changing block-transition probabilities? | [Strong lumping](https://midya8.github.io/absorblab/lumping.html) | Refinement splits, every set partition, same-block obligations and the quotient identity `PC=CQ`. |
| What happens when probability moves within one row? | [Row response and traffic](https://midya8.github.io/absorblab/response.html) | Exact rational interior curves, derivatives, separately solved endpoints and successful-path visits and edge counts. |

A couple of things worth getting straight up front. Conditioning picks out the successful trajectories; it doesn't make the original workflow any better. Strong lumping is a statement about the original transition matrix, while first-hit analysis stops at the terminals you supplied. And "exact" here means rational arithmetic — it's not the distinct condition called exact lumpability.

### An exit can disappear

The row-response default has a self-loop and a goal edge, each with probability `1/2`. Shift mass from the loop to the goal and, as long as the goal edge stays positive, eventual success is one — even when the wait gets very long. But once the last exit is gone, actual success drops to zero. The one-sided interior limit is still one; that isn't the endpoint answer.

A second retry control has success probability `(1/4+t)/(1/2+t)`, so its curve bends instead of sitting flat. Conditional traffic counts retries plus the final transition into success. It leaves out terminal outgoing edges and is undefined when success has probability zero. The plot joins sampled points; the rational formula shown is what defines the full interior response. [RESPONSE.md](RESPONSE.md) has the derivation, the input domain, and the limits.

### When grouping is safe

The aggregation inspector finds the coarsest observation/status-respecting strong lumping. Its default takes two refinement rounds. You can look at noncontiguous blocks, every partition, and each cell of `PC=CQ`. The all-step identity follows by induction — it isn't just a few forecasts that happen to match. [LUMPING.md](LUMPING.md) states the contract and the proof. This isn't weak or approximate aggregation, a finite-horizon equivalence, or a full model checker.

## A counterexample you can inspect

In the default chain, `start` picks `goal` or `risky` with probability `1/2` each. `risky` reaches `goal` with probability `1/4` and otherwise fails.

| Quantity from start | Exact value |
| --- | --- |
| Eventual first success | `5/8` |
| Eventual first failure | `3/8` |
| Direct goal, given eventual success | `4/5` |
| Risky branch, given eventual success | `1/5` |
| Mean time given success | `6/5` |
| Variance given success | `4/25` |
| Unconditional time to either terminal | `3/2` |
| Unconditional time to stopped success | infinite |

There's no immediate failure edge out of `start`. If you just delete the failure edges locally, the original `1/2 : 1/2` choice at `start` doesn't change. Condition globally on eventual success instead and you get `4/5 : 1/5`. Conditioning is selection, not an intervention that improves the original workflow.

## Running it yourself

Python 3.10–3.13:

```sh
python -m pip install .
absorblab examples/conditioning.json --output /tmp/absorblab-certificate.json
absorblab /tmp/absorblab-certificate.json --verify
absorblab-lump examples/lumping.json --output /tmp/lumping.json
absorblab-lump /tmp/lumping.json --verify
absorblab-response examples/response.json --output /tmp/response.json
absorblab-response /tmp/response.json --verify
# Module entrypoints: python -m absorblab,
# python -m absorblab.lumping_cli, python -m absorblab.response_cli
python -m unittest discover -s tests -v
bash tools/check_wheel.sh
```

For the browser, serve the `docs` folder locally rather than opening it as `file://`:

```sh
python -m http.server 8000 --directory docs
# Open http://localhost:8000/
```

Node 22+ and actual Chrome:

```sh
npm test
# Optional environment overrides: PYTHON, CHROME_BIN.
# ABSORBLAB_SCREEN_DIR=/tmp/absorblab-screens saves full-page captures.
# ABSORBLAB_URL targets the same harness at a deployed page.
```

The Chrome test drives the real rendered controls and certificate. It changes every starting state, horizon row, support round, and elimination stage, and exports twelve files with trusted pointer clicks. It waits for each browser download to finish, reads the actual downloaded bytes, and replays each certificate through the native checker. DOM anchors alone don't count as an export.

## What a certificate actually contains

Every certificate carries the normalized input; the original and stopped transition matrices; reverse-support rounds; a positive-support terminal path, or its absence, from every root; closed and nonclosed strongly connected components; the restricted `I-Q` system, boundary vectors, and inverse; canonical Gauss-Jordan row-operation evidence; weighted success moments; every original and conditioned destination, including zeros; and finite-horizon active mass and first-hit increments for every root.

The native generator uses reverse support, Tarjan components, exact Gauss-Jordan inversion, and active-flow propagation. The native replay checker imports neither the generator nor the elimination module: it works from explicit simple paths, mutual reachability, a permutation-determinant/cofactor inverse, and dense stopped-chain powers. It derives the full expected report and checks every key, type, value, and ordering, including the operation evidence. The browser engine was written separately, with BigInt cofactor algebra and stopped-chain powers. The implementations share a mathematical specification — not an independent mathematical truth.

`tools/make_controls.py` reproduces twelve controls byte for byte: global conditioning; geometric retry; competing terminals; closed traps; terminal override; no terminals; all terminals; rare success; a five-transition chain; multiple goals; an unreachable goal; and a cyclic transient block.

## Tests

The current suite has **42 Python tests and 11 Node tests**, including actual Chrome checks for all three inspectors. The Python total keeps the original 16 first-hit tests, adds 14 lumping tests, and adds 12 response tests. Node runs engine comparisons and actual browser interactions; those are test cases, not 11 separate browser suites.

| Workflow | Native/browser full-report comparison | Actual Chrome checks |
| --- | --- | --- |
| First hit | 213 reports: 12 controls, 81 two-state cases and 120 seeded rational chains. | 36 reports across 320/390/1280 pixels; all state, horizon, support and elimination selections; 12 trusted completed downloads. |
| Strong lumping | 527 reports: 435 exhaustive small cases, 80 seeded chains and 12 controls; 6,448 partitions and 4,038 quotient cells. | 36 reports; 48 refinement states, 138 pair selections, 816 partition selections, 618 forecast selections and 12 trusted completed downloads. |
| Row response | 146 reports: 12 controls, 54 two-state combinations and 80 seeded chains; 1,909 samples, 61,255 conditional edge cells and 15,435 derivative pairs. | 36 control reports, 1,293 root/sample selections and 12 trusted completed downloads, plus 12 dense six-state views at desktop/320 pixels. |

These are finite descriptive checks — not performance benchmarks, not exhaustive coverage of six-state rational chains, and not a proof of the shared specification. The native replay checkers use alternate support and algebra calculations, but they still share schema and some helpers. The browser uses separate BigInt engines. [METHOD.md](METHOD.md), [LUMPING.md](LUMPING.md), and [RESPONSE.md](RESPONSE.md) separate those dependencies and numerical checks from the mathematical arguments.

The first-hit tests cover all 81 two-state uniform nonempty-support/status cases; all 729 deterministic three-state/status cases with a separate unique-path oracle; all 9,261 three-state uniform nonempty-support/status cases; 120 seeded rational chains; 120 acyclic weighted chains with a separate full-path moment oracle; state/edge permutation; schema caps; exact mass and moment equations; checker import isolation; atomic CLI output; and twenty full-report forged-field changes plus type failures.

The browser-engine differential set has 213 full reports: twelve controls, 81 two-state cases, 120 seeded rational chains. All 682 state records, 4,284 forecast rows, and 191 elimination stages agree exactly with Python. That's bounded descriptive agreement, not a proof or a performance benchmark. The actual Chrome set runs twelve controls at 320, 390, and 1280 pixels: 36 reports, 120 state selections, 456 conditioned destination rows, 1,068 forecast rows, 75 support rounds, 45 elimination stages, twelve actual downloaded reports, and stale/invalid input checks. Integer JSON spelling and trailing-name/probability whitespace are rejected consistently with Python's input contract.

Fresh wheel checks run outside the checkout and assert all fourteen package module origins in `site-packages`. Each of the three workflows compares its twelve controls through both console and module entrypoints. First-hit checks reject 20 forged CLI reports; lumping and response each reject 24 CLI and 24 direct-checker forgeries, with atomic output preservation for CLI failures. Python 3.10, 3.11, 3.12, and 3.13 are separate CI jobs.

### Optional external exact references

```sh
uv run --no-project --with sympy==1.14.0 --python 3.13 python tools/check_sympy.py
uv run --no-project --with sympy==1.14.0 --python 3.13 python tools/check_lumping_sympy.py
uv run --no-project --with sympy==1.14.0 --python 3.13 python tools/check_response_sympy.py
```

The first script invokes SymPy 1.14.0 on 213 requests, comparing 682 success/failure probability pairs and 351 conditional mean/second-moment/variance triplets. The reference uses Boolean transitive closure, SymPy `inv(method='ADJ')`, and an independently formed success-conditioned chain whose moments are solved with `LUsolve`. It's development-only and not installed as a runtime dependency. It checks these finite examples — not every possible chain, all certificate fields, or an independently certified theorem. Its seed differs from the browser/native seeded sets. [METHOD.md](METHOD.md) lists the operator and probability sources. The lumping reference checks 527 requests, 6,448 partition mass matrices, 4,038 quotient cells, and 2,038 matrix-power equalities. It imports the native generator and test corpus, so it's a matrix reference rather than independent full-report replay. The response reference checks 146 requests, 928 symbolic success/failure curves, and 10,290 derivative pairs. It uses the reported transient indices and checks algebra, not independent support analysis. [LUMPING.md](LUMPING.md) and [RESPONSE.md](RESPONSE.md) spell out those limits.

## Limits

One to six states; one to six positive rational transitions per row; each numerator/denominator at most 1,000,000; exact row sum one; horizon 0–12. State names are 1–24 ASCII identifier characters. `success` and `failure` are disjoint, may be empty, and stop on first hit. A root already terminal stops at time zero. Supplied terminal outgoing rows are still validated and preserved as original evidence, then replaced by identity rows for stopped-chain analysis.

A closed nonterminal class can carry positive never-terminal probability. No conditioning is defined at success probability zero. Unconditional time to stopped success is infinite below probability one, even if every run reaches some terminal. Mean given a terminal hit is a different reported quantity.

This is an educational model for supplied probabilities — not an estimator, fairness model, adversarial game, learned calibration system, scalable probabilistic model checker, or real-agent guarantee. The classical methods and public sources are credited in [METHOD.md](METHOD.md). The work here is the bounded implementation, evidence format, checker, tests, and interactive explanation, not a claim of new Markov-chain theory.

MIT licensed. No external assets or vendored solver code. The strict duplicate-key JSON parser and Chrome launch/debugger/download plumbing adapt the author's existing ShieldLab test infrastructure; the AbsorbLab domain engines and controls are separately written.
