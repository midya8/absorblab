# First-hit analysis and success conditioning

## Contract and boundary conditions

Let `S` and `F` be disjoint supplied success and failure sets. The first hit of either stops the chain; an already-terminal root has hitting time zero. The stopped transition matrix replaces each terminal row with a self-loop and leaves other rows unchanged. Time to **stopped success** is infinity if failure occurs first or neither terminal is ever hit. This is not a return-time calculation and does not allow leaving failure to find success later.

Let `h(i)` and `f(i)` be the success-first and failure-first probabilities. They take boundary values `(1,0)` on success and `(0,1)` on failure. On nonterminal states they are harmonic. Without the least-nonnegative condition, harmonic equations alone may be ambiguous: a closed nonterminal self-loop satisfies `x=x` for every constant.

Reverse positive-support reachability starts with `S ∪ F`. Every state outside its fixed point has `h=f=0`. Let `U` be the reached nonterminal states and `Q=P[U,U]`. The complement is boundary evidence, not an unknown arbitrary constant.

Every state of `U` has a finite positive-probability path to a terminal. Finite `U` permits a common finite block length and a strictly positive minimum terminal-hit probability over these chosen paths. Therefore the probability of remaining in `U` decays at least geometrically in blocks, `Q^k → 0`, and `A=I-Q` is invertible. The inverse sums the visit series. Boundary transitions to terminals define `bS` and `bF`; transitions outside the reverse-reachable set contribute zero. Then:

```
A hU = bS
A fU = bF
never(i) = 1 - h(i) - f(i)
```

These restricted solutions are the least nonnegative first-hit probabilities. The geometric block argument is local to this finite supplied chain; no minimum-probability, mixing or scalability guarantee is claimed across arbitrary inputs. Closed nonterminal components are explicitly labeled in the stopped support; nonclosed components may still eventually enter one.

## Weighted timing moments

Define `g(i)=E[T 1success]` and `m(i)=E[T² 1success]`, with zero boundary values. The notation means a successful-path moment numerator, equivalently the sum over finite successful hitting times; it does **not** multiply an infinite random variable by zero. First-step conditioning gives:

```
g = h + Qg
m = h + 2Qg + Qm
A g = h
A m = 2g - h
```

Here the last two equations are restricted to `U`. Consequently for `h(i)>0`:

```
E[T | success] = g(i)/h(i)
E[T² | success] = m(i)/h(i)
Var(T | success) = m(i)/h(i) - (g(i)/h(i))²
```

They are undefined, represented by `null`, when `h=0`. Success terminals have conditional mean and variance zero. The same calculation with `h+f` gives the weighted any-terminal first moment and its conditional mean. Unconditional stopped-success time is finite exactly when `h=1` in this finite model; unconditional any-terminal time is finite exactly when `h+f=1`. Otherwise the corresponding extended expectation is infinite. Almost-sure hitting alone does not imply finite expectation in general countably infinite chains; the finite-chain argument above matters.

## Global conditioning

For every positive-success state:

```
P^h(i,j) = Pstop(i,j) h(j) / h(i)
```

Harmonicity makes each row sum to one. The factor `h(j)` accounts for eventual success after the next edge. A zero-success destination gets weight zero, while undefined rows at `h(i)=0` remain undefined rather than invented distributions. Already-successful roots remain stopped. The display retains all original and stopped probabilities, future success weights, joint masses and conditional probabilities so changed terminal behavior cannot be hidden.

The finite path product telescopes to original stopped-path probability times the final `h` divided by initial `h`. This is conditioning on eventual success, not deleting only the next failure edge, optimizing a policy, an intervention or learning new probabilities. In the default example it changes the equal initial branches to `4/5` direct and `1/5` risky.

## Forecasts and replay

The generator propagates active nonterminal mass, collecting first-success and first-failure mass at each step. Time-zero terminal mass is counted immediately. Cumulative success + cumulative failure + still-active mass is exactly one. Remaining successful mass equals `h(start) - success_by_step`; dividing by positive `h(start)` gives the conditional remaining tail.

The checker and browser instead multiply the dense stopped-chain distribution. Terminal coordinate increments give the same first-hit increments; terminal coordinates are removed from active mass. Every forecast row is checked, not just the last horizon value.

The generator's Gauss-Jordan operation trace is canonical and replayed exactly. The native checker does not trust its inverse: it derives a separate permutation-determinant/cofactor inverse, checks identities, and derives the full report using independent support and power calculations. Full equality also rejects extra keys, changed booleans, forged denominators and stale metadata. This is replay validation under a shared input specification, not a formally verified proof assistant or independence from Python's standard library.

## Sources and attribution

The mathematical methods below are established. Sources informed the derivation; no source code or worked example text is copied into the domain implementation. The twelve controls are original small examples.

1. Jim Pitman, Berkeley Statistics 205 lecture 2, first-hit probabilities and minimal nonnegative harmonic solutions. In particular, nonuniqueness outside the minimality condition motivates support restriction rather than choosing an arbitrary harmonic solution. https://www.stat.berkeley.edu/~pitman/s205s03/lecture2.pdf
2. Berkeley Statistics 150 lecture 6, first-step equations for hitting probabilities and means, with attention to nonunique solutions. https://www.stat.berkeley.edu/~aldous/150/Lectures/lecture_6_post.pdf
3. Matthew Aldridge, MATH2750 section 8, hitting time versus return time, infinity conventions and the qualification that probability one does not alone ensure finite mean in unrestricted state spaces. https://mpaldridge.github.io/math2750/S08-hitting-times.html
4. Grinstead and Snell, absorbing chains, fundamental matrix and finite transient-tail argument. Its transient/absorbing assumptions apply to the restricted subsystem here, not an unqualified inverse of every supplied nonterminal block. https://stats.libretexts.org/Bookshelves/Probability_Theory/Introductory_Probability_(Grinstead_and_Snell)/11%3A_Markov_Chains/11.02%3A_Absorbing_Markov_Chains
5. Pierre Bellec, Doob h-transform exposition, positive-h conditional transition formula. Undefined zero-h rows are not extended by assumption. https://bellecp.github.io/doob_h.html
6. Levin and Peres with Wilmer, *Markov Chains and Mixing Times*, second edition, section 17.6.1, printed pages 255-256, Doob transform and path-conditioning identity. The author-hosted PDF was inspected at this section. https://pages.uoregon.edu/dlevin/MARKOV/markovmixing.pdf

Optional external arithmetic cross-check operator documentation:

- SymPy matrices: `inv(method='ADJ')` uses the adjugate method; this is not the runtime's Gauss-Jordan implementation. https://docs.sympy.org/latest/modules/matrices/matrices.html
- SymPy matrix-equation guide: `LUsolve` solves the separately formed conditioned-chain moment equations. https://docs.sympy.org/latest/guides/solving/solve-matrix-equation.html

The check pins SymPy 1.14.0 and prints the actual version. The probability reference uses independent Boolean Floyd closure and adjugate inversion. Conditional moments are independently formed from the positive-success Doob chain and solved by LU. Exact agreement on the reported 213 finite inputs is external numerical/algebraic evidence, not certification of every field, performance or universal correctness. No external executable reference is claimed beyond this explicitly run check.

## Limits

Six-state caps keep determinant permutation work and readable certificates bounded. No floating-point approximations enter probabilities, moments or row evidence. Forecast horizon is capped at twelve; eventual probabilities and moments are not truncated to that horizon. Input rows have only positive supplied entries, with missing destinations interpreted as zero. All terminal outgoing rows are validated even though stopped analysis overrides them.

Input is capped at 65,536 bytes; CLI verification input and output at 16 MiB. The browser duplicate-key parser enforces integer numeric spelling for its only numeric schema field, horizon; probability values must be rational strings. No privacy or production security claims are made about running untrusted software in a user's own application. AbsorbLab performs local computation and does not upload model inputs.
