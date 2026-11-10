# Labeled strong lumpability, exactly

AbsorbLab 0.2 implements established finite-chain strong lumpability with supplied observation tags and success/failure/nonterminal status. It does not introduce a new equivalence, a learned similarity, weak lumpability or an approximate reduction. "Exact" describes rational arithmetic, not the different technical notion called exact lumpability in parts of the literature.

## Contract

Input is `{ "chain": <the existing first-hit chain>, "observations": [one tag per state] }`. The original chain's one-to-six-state, exact-positive-rational row, ASCII identifier, disjoint-terminal and horizon 0-12 rules remain in force. Observation tags use the same ASCII identifier rule. State order fixes certificate order. A color is `(observation, terminal status)`; supplied names are not colors. Duplicate JSON keys, decimal JSON spellings, nonfinite tokens, extra keys and stale invalid input are rejected.

Use the original transition matrix P, including outgoing terminal edges. First-hit analysis stops at success/failure, but raw-chain equivalence is stronger. Two states with identical stopped first-hit records may still split because their original terminal outgoing rows differ. Empty terminal sets are allowed. With one observation and no terminal distinction, the one-block partition is always a valid strong lumping.

## Refinement and its guarantee

Begin with equal-color blocks. At each synchronous round, a state's signature is its exact mass into each current block. Split each existing block by equal signatures, retaining all distinctions from earlier rounds. Stop at an unchanged partition. Every nonfixed round increases the number of blocks, so this terminates on a finite chain.

Why coarsest: let R be any stable color-respecting partition. Initially R refines the color partition. If R refines the current partition, every current destination block is a union of R-blocks. R-equivalent states send equal mass into each R-block, hence into each such union; a signature split cannot separate them. Induction shows R refines every round and the final partition. The final partition itself is stable and color-respecting, so it is the unique coarsest allowed partition, not merely a partition with few blocks.

The certificate also enumerates every set partition using restricted-growth words, retaining one-block, discrete and noncontiguous cases. At six states there are 203. Every candidate records its full state-to-block mass matrix, color and mass conditions separately, first conflicts, and whether it refines the final partition. The independent checker builds partitions by recursive subset insertion instead of restricted-growth words, finds the unique coarsest allowed partition globally, and reconstructs each round from a direct pair-equivalence relation rather than signature grouping.

## Quotient and all-step preservation

For blocks B,D, define Q(B,D)=sum(P(s,t), t in D), choosing any s in B. Stability makes this representative-independent. If C is the state-to-block indicator matrix, every certificate cell explicitly checks `PC=CQ`. Thus `P^k C=C Q^k` for every nonnegative k by induction. For any initial row distribution alpha, `alpha P^k C=alpha C Q^k`. All-step preservation follows from this identity, not from matching a finite list of forecasts.

Because colors preserve terminal status, replacing terminal rows by identity yields the corresponding stopped-chain intertwining identity too. The block process therefore preserves terminal first-hit distributions. Displayed success/failure/never probabilities and time moments are additional bounded implementation checks, computed by the existing first-hit engines. Undefined conditional times stay undefined; infinite unconditional times stay infinite. A finite horizon of zero does not disable refinement or weaken the equivalence. This inspector does not implement a PCTL parser, full model checker, reward preservation, continuous time, nondeterministic action choices or infinite-state reduction.

## Default counterexample

Six states: s0 goes to s2; s1 goes to s3; s2 goes to goal s4; s3 stays at itself or reaches s4, each with probability 1/2; s4 self-loops; s5 goes to s2. All nonterminals share tag `work`; s4 has tag `goal` and success status.

Initial `{0,1,2,3,5}|{4}` becomes `{0,1,5}|{2}|{3}|{4}`, then `{0,5}|{1}|{2}|{3}|{4}`. s0 and s1 initially have equal immediate goal mass, but after their successors split, s0 sends one unit to block `{2}` and s1 sends zero. s0 and s5 genuinely remain merged despite being noncontiguous indices. All s0/s1/s5 eventually succeed with probability one, which alone does not settle state equivalence or timing.

Twelve original synthetic controls cover this cascade, different full rows with equal block masses, a 1/1,000,000 difference, terminal-status mismatch, raw terminal outgoing distinctions, a valid one-block reduction, a closed nonterminal class, zero horizon, one success state, success/failure branches, distinct tags, and a further rational split. No benchmark or example from a source is copied.

## Reproduce and interpret the evidence

```sh
python -m pip install .
absorblab-lump examples/lumping.json --output /tmp/lumping.json
absorblab-lump /tmp/lumping.json --verify
python -m unittest discover -s tests -v
npm test
bash tools/check_wheel.sh
python -m pip install sympy==1.14.0  # optional development reference only
python tools/check_sympy.py
python tools/check_lumping_sympy.py
```

Thirty Python tests retain the 16 original first-hit tests and add 14 lumping tests. The new differential set has 527 complete reports: 435 exhaustive small cases, 80 seeded rational chains (seed 91073), and 12 authored controls. Native generator, independent replay and browser BigInt output agree on 6,448 partitions, 637 refinement states and 4,038 quotient cells. The set includes all 3 one-state statuses, all 162 two-state nonempty uniform support/status cases under two tag patterns, and 270 deterministic three-state cases under ten tag/status arrangements. This is bounded evidence, not an exhaustive claim for six-state rational chains.

All 255 noninput primitive leaves of a selected full report are separately mutated and rejected. Tests retain permutation, no-input-mutation, wrong-schema, import isolation, strict JSON, byte cap, CLI generation/replay and atomic failure coverage. The independent checker shares the schema parser and exact scalar comparison, and reuses the prior independent simple-path/cofactor first-hit checker; it is independent of the new generator's grouping and vector forecasts, not independent of the written mathematical specification.

The optional SymPy 1.14.0 script genuinely constructs rational matrices for all 527 requests. It checks all 6,448 partition mass matrices, 4,038 intertwining cells and 2,038 matrix powers against the supplied certificate. It imports the generator to obtain reports and the test corpus to obtain requests; it is a matrix reference, not an independent input corpus, full schema replay or theorem prover. It is not a runtime dependency. The existing 213-request SymPy first-hit reference remains separate.

Seven Node tests retain all prior browser/engine checks and add lumping engine and actual Chrome checks. The new Chrome test exercises 36 reports at 1280/390/320 pixels: 48 refinement states, 138 pair selections, 816 partition selections, 618 forecast selections, 345 edge records and 12 trusted completed browser downloads independently replayed. Screenshots supplement behavioral checks; layout is inspected separately. The wheel check runs outside the checkout, confirms ten installed module origins, compares all 12 lumping controls via console and module entrypoints, and rejects 24 forged CLI reports while preserving existing destination bytes, plus 24 direct checker forgeries. Existing first-hit wheel checks remain intact.

## Foundations and source boundaries

- John G. Kemeny and J. Laurie Snell, *Finite Markov Chains*, Chapter 6.3, definition and Theorem 6.3.2: all-initial-distribution lumpability and equal block probability sums. [Inspected chapter](https://math.pku.edu.cn/teachers/yaoy/Fall2011/Kemeny-Snell_Chapter6.3-4.pdf). The chapter is used for the theorem, not its example data.
- [PRISM probabilistic model checking lectures, ESSLLI 2010, part 4](https://www.prismmodelchecker.org/lectures/esslli10/esslli10pmc-part4.pdf): label equality, block probability equality, quotient and preservation. Teaching reference, not a solver invoked by this project.
- N. Kamaleson, D. Parker and J. Rowe, *Finite-Horizon Bisimulation Minimisation for Probabilistic Systems* (2016), section 2.3 definitions 4-5. [Paper](https://www.prismmodelchecker.org/papers/spin16fh.pdf). The standard strong bisimulation definition is used. The paper's distinct finite-horizon/on-the-fly methods are not implemented or claimed here.
- Christian Dehnert, Joost-Pieter Katoen and David Parker, *SMT-Based Bisimulation Minimisation of Markov Models* (2013), section 2 definitions 2-4. [Paper](https://www.prismmodelchecker.org/papers/vmcai13.pdf). Supports coarsest labeled quotient semantics. No SMT or symbolic scalability claim is borrowed.
- [Amy Pang, paper on lifting Markov chains](https://amypang.github.io/papers/lift.pdf), Definition 2.5 and Theorem 2.6: strong lumping is independent of initial distribution, with Dynkin's equal-sum criterion and representative-independent quotient.
- Peter Buchholz, *Exact and Ordinary Lumpability in Finite Markov Chains*, [publisher abstract](https://www.cambridge.org/core/journals/journal-of-applied-probability/article/abs/exact-and-ordinary-lumpability-in-finite-markov-chains/2DC748F09D80BEEB03CCF18036E149D7): terminology caveat. Exact rational arithmetic here must not be confused with the separately named exact-lumpability condition.
- [PyDTMC properties documentation](https://pydtmc.readthedocs.io/markov_chain_properties.html) and [implementation documentation](https://pydtmc.readthedocs.io/_modules/pydtmc/markov_chain.html): `lumping_partitions` explicitly considers contiguous blocks and excludes the one-block/discrete extremes. It is not used as an all-partition oracle, and no PyDTMC result is claimed.

All authored implementation and controls are MIT licensed. No external solver source is vendored. Chrome lifecycle/download plumbing adapts the author's existing test helper; it is not a domain algorithm. See [METHOD.md](METHOD.md) for the retained first-hit methods and sources.
