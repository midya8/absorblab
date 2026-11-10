# One row, an entire response, and a disappearing exit

AbsorbLab 0.3 adds a bounded exact probability-transfer inspector to the existing first-hit and strong-lumpability workflows. These are classical finite Markov-chain, Doob-transform and rank-one inverse calculations, not new probability theory. Supplied transition probabilities are not learned, calibrated, causal effects or nondeterministic policy choices.

## Contract and support

Input has exactly `chain`, `row`, `donor`, `receiver` and `at`. `chain` uses the existing one-to-six-state first-hit schema, with positive rational transitions, disjoint success/failure sets and a horizon from zero to twelve. `row` must be nonterminal. Donor and receiver must be different declared states. `at` is a signed rational string, with numerator and denominator bounded by 1,000,000. Extra fields, duplicate JSON keys, noninteger JSON number spellings and nonfinite tokens are rejected. The CLI limits requests to 65,536 bytes and certificates to 16 MiB.

Write a=P(i,donor), b=P(i,receiver), allowing either to be zero if its edge is absent. The family removes t from the donor and adds t to the receiver. Its complete admissible interval is [-b,a]. Positive combined mass is required. Every interior point has both varied edges positive and the same support. Each endpoint may remove an edge. State order determines output order. The other rows stay fixed. First success or failure stops the run, overriding supplied outgoing terminal transitions.

The interior anchor is t0=(a-b)/2, which is the interval midpoint. It need not be zero. The certificate uses delta=t-t0. Selected concrete samples include the thirteen grid points of twelve equal subintervals, the anchor, zero and the requested `at`, deduplicated and sorted. Samples support inspection and independent reproduction; they do not establish the interval identity.

## The exact interior response

Use the anchor's stopped matrix P. Let U be its nonterminal states with a positive-support path to success or failure. States outside U have zero success/failure probabilities. They may be recurrent, so their block must not be inverted. On U define Q=P[U,U], A=I-Q and N=A^-1. The existing finite-path argument establishes transience of this restricted block: each U state has a finite positive-probability exit path, so Q powers decay geometrically in blocks.

Let i be the varied row. If i belongs to U, let c=N e_i, extended by zero outside U. Otherwise c is zero. Let v have +1 in the receiver position and -1 in the donor position, restricted to U, and k=v^T c. A changed restricted matrix is A(delta)=A-delta e_i v^T. Sherman-Morrison gives

```text
N(delta) = N + delta c v^T N / (1-delta k)
```

when the denominator is nonzero. It cannot vanish in the open transfer interval: its positive-support graph is fixed, every state of U still has a path to a terminal, and the restricted matrix is invertible there. This is a support-and-finiteness argument, not an empirical observation from a grid.

Let h be anchor success-first probability, extended with boundary values one on success and zero on failure and unreachable states. Define z=h(receiver)-h(donor). The success response for every state r is

```text
h_r(delta) = h_r + delta c_r z / (1-delta k)
          = [h_r + delta(c_r z-h_r k)] / (1-delta k).
```

The right-hand-side boundary change is included in z, so this formula also covers transfer to a terminal or an excluded state. The analogous failure response uses its own boundary values. Never-terminal probability is one minus those two responses. If the varied row lies outside U, its destinations cannot reach a terminal in the interior graph, and all first-hit responses are constant.

The certificate exposes all affine numerators, the common affine denominator, the anchor inverse, its row-visit column and feedback k. Substitution into each nonterminal harmonic equation gives a quadratic polynomial with all three coefficients zero. Boundary values are fixed separately. The independent checker reconstructs the denominator and numerator coefficients using Cramer's determinants at two algebraic delta values. Those evaluation values recover affine polynomial coefficients; they are not claimed to be admissible probability chains. A determinant is affine here because only one matrix row varies. The checker does not import the rank-one generator or its Gauss-Jordan inverse.

For numerator B0+B1 delta and denominator 1+D1 delta,

```text
first derivative  = (B1-B0 D1) / (1+D1 delta)^2
second derivative = -2 D1 (B1-B0 D1) / (1+D1 delta)^3.
```

Derivatives are reported only at interior samples. An interior derivative is not automatically a derivative of the actual endpoint probability function.

## Endpoints are different chains

Each endpoint gets a new support analysis and exact direct first-hit solve. The interior one-sided probability limit is computed separately. At a zero common denominator, bounded probability implies a removable affine numerator/denominator factor; the limit is the ratio of their slopes. A finite probability limit need not equal the endpoint's least first-hit solution.

The original default control has one nonterminal s with self-loop probability 1/2 and goal probability 1/2. Transfer t from the loop to the goal. For every t>-1/2, eventual success is one and conditional duration is 1/(1/2+t). At t=-1/2 the only exit disappears: actual success is zero, never-terminal probability is one and conditional duration is undefined. The interior success limit is still one. A derivative of the flat interior success curve cannot recover that missing exit.

A separate retry control has self-loop 1/2, success 1/4 and failure 1/4. Transferring t from loop to success yields success (1/4+t)/(1/2+t). At t=0 its first derivative is one and its second derivative is minus four. This nonflat rational control prevents every demonstration from reducing to the default's flat probability curve. Other original controls cover absent varied edges, dead components, empty terminal/success sets, multiple successes, unreachable varied rows, detours and a 1/1,000,000 exit. No benchmark or example is copied from a source.

## What conditional traffic counts

For a concrete chain, recompute its U and restricted N. For a nonterminal start r, N[r,j] is the expected number of visits to j in U before leaving U. It includes time zero. It does not claim finite visits to excluded closed nonterminal states. Zero rows for excluded starts mean zero visits to U, not a finite total lifetime.

For h(r)>0, successful paths have conditional expected nonterminal visits and directed edge traversals

```text
visits(r,j | success) = N[r,j] h(j) / h(r)
edges(r,j,k | success) = N[r,j] P(j,k) h(k) / h(r).
```

Terminal visits and terminal outgoing edges are excluded. Edge counts include the final transition into success. Zero-success roots have undefined conditional records, represented by null, not zero. A root already in success has zero visits, zero edges and zero time.

Conditional visits sum to conditional mean success time. Total edge traversals equal that mean. At each nonterminal, outgoing count equals visits; outgoing minus incoming is one at the starting state and zero elsewhere. Success arrivals sum to one for a successful nonterminal root and zero for an already-terminal root. The independent checker obtains traffic by inverting the transient part of the success-conditioned transition matrix, not by rescaling the original visit matrix. This is an alternate computation of established Doob conditioning, not independent evidence for a different mathematical model.

## Reproduction and current evidence

```sh
python -m unittest discover -s tests -v
npm test
bash tools/check_wheel.sh
absorblab-response examples/response.json --output /tmp/response.json
absorblab-response /tmp/response.json --verify
python -m absorblab.response_cli examples/response.json
python -m pip install sympy==1.14.0  # optional development reference only
python tools/check_response_sympy.py
```

The 42 Python tests retain all 30 previous tests and add twelve response tests. The response corpus has twelve authored controls, 54 uniform-support two-state/status/varied-row combinations and 80 seeded rational chains (seed 62719). Native generator, independent native replay and browser BigInt engine agree on 146 complete reports, 1,909 concrete samples, 464 state curves, 61,255 conditional edge cells and 15,435 derivative pairs. These are bounded checks, not exhaustive coverage of all six-state rational inputs.

All 774 noninput primitive leaves of a chosen complete report are separately changed and rejected. Tests include no input mutation, transfer reversal, exact geometric retry/traffic references, horizon independence, checker import isolation, twenty forged CLI certificates and strict/oversized input refusal with atomic output preservation. The checker shares schema/equality helpers and the earlier determinant routine, but not the new response generator, Gauss-Jordan routine or rank-one construction.

Actual Chrome tests exercise twelve controls at 1280/390/320 pixels and all 1,293 root/sample selections. Every displayed probability, visit count, edge count, coefficient, first derivative and endpoint actual value is checked, alongside containment and 44-pixel controls. Twelve distinct trusted downloads complete and replay natively; trusted edits hide stale results, invalid input stays rejected and a valid edited request runs through the real button. Separate download gestures are paced to avoid Chrome's rapid-download burst limit. Failed content or completion assertions are not retried.

An optional genuinely invoked SymPy 1.14.0 reference checks all 146 requests, 928 symbolic success/failure curves and 10,290 derivative pairs. It uses the reported interior transient indices, so its scope is algebra, not independent support verification. The simple-path native checker owns that check. A separate dense six-state rational request agrees with native generation/replay and checks twelve additional nonterminal/success/failure root views at desktop and 320 pixels, including long exact fractions. Fresh isolated wheels confirm all fourteen package module origins, twelve controls through the installed script and module entrypoints, and 24 direct plus 24 CLI forgeries with atomic output preservation, retaining both earlier workflow installation checks.

The plot rounds coordinates and joins sampled interior values with line segments. Its rational formula, not those segments, defines the full response. Raw certificate details stay available. There are no network inference calls, accounts, analytics or paid services. This is not weak/approximate aggregation, general multivariate parameter synthesis, policy optimization, a learned model, a causal analysis, a scalable solver or a guarantee about real AI agents.

## Inspected foundations and attribution

All seven sources were inspected as full text during development on November 10, 2026. The implementation and authored controls are original; the theory is established.

1. Grinstead and Snell, *Introduction to Probability*, absorbing chains, textbook section reproduced by LibreTexts. Fundamental matrix, expected visits, absorption probabilities and time. https://stats.libretexts.org/Bookshelves/Probability_Theory/Introductory_Probability_(Grinstead_and_Snell)/11%3A_Markov_Chains/11.02%3A_Absorbing_Markov_Chains
2. Massimiliano Gubinelli, *Note 9: Discrete Markov chains and ergodicity. Doob's h-transform*, 2021 lecture notes. Harmonic change of measure and exclusion of zero-h states. https://mgubi.github.io/store/iam/stochastic-processes-ss21/sp-note-9.pdf
3. Nick Higham, *What Is the Sherman-Morrison-Woodbury Formula?*, September 29, 2020. Rank-one inverse update and nonzero denominator condition. https://nhigham.com/2020/09/29/what-is-the-sherman-morrison-woodbury-formula/
4. Storm, *Running Storm on Parametric Models*, official documentation. Solution functions and graph-preserving assumptions; cited for scope, not a capability or performance comparison. https://www.stormchecker.org/documentation/usage/running-storm-on-parametric-models.html
5. *Parameter Synthesis in Markov Models: A Gentle Survey*, arXiv 2207.06801, research survey. Graph-preserving valuations, rational solution functions and boundary continuity distinctions. https://ar5iv.labs.arxiv.org/html/2207.06801
6. *Accelerating Parametric Probabilistic Verification*, arXiv 1312.3979, primary research. Graph-preserving evaluations and rational reachability functions. Its algorithmic speed claims are not claims for this project. https://arxiv.org/html/1312.3979
7. Wang He, *Stochastic Processes*, section 6, educational notes. Supplemental derivation of the fundamental matrix and visit/time identities. https://wanghemath.github.io/Book-StochasticProcesses/chapters/section-06-ergodic-reversible.html
