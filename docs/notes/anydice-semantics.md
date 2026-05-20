# AnyDice semantics: what we preserve, what we don't, and what we fixed

A living catalog of:

1. **Preserved AnyDice idiosyncrasies** -- behaviors that are surprising or inconsistent but appear to be intended, that anydyce faithfully replicates.
2. **Excluded AnyDice bugs** -- behaviors we have evidence are unintended defects, that anydyce deliberately does *not* replicate (and that we annotate corpus mismatches with so AnyDice is not used as an oracle for them).
3. **Fixed our-side bugs** -- correctness defects we discovered in our own interpreter during corpus triage and have since fixed.

Each entry should carry a concrete reference (a test name, a probe id, a commit, or a corpus program id) so the claim is verifiable. AnyDice is closed-source; everything here is the result of empirical reverse-engineering against the live `anydice.com` and the cached corpus output.

Maintenance: update this as new behaviors are characterized. The auditor (when it lands) should be able to auto-generate parts of section 2 from the corpus DB's `annotations` table.

---

## 1. Preserved AnyDice idiosyncrasies

### Type coercion and value semantics

- **Sequence in numeric / die context is *uniform over elements*, not the sum.**
  `output {1,2,3}` yields `{1:33.3%, 2:33.3%, 3:33.3%}` (uniform over the three values), *not* `{6:100%}` (the sum). Verified by probes -21 / -22 against AnyDice. Both anydyce and AnyDice produce the uniform distribution.

- **`output` collapses any pool / H to its sum.**
  This is `output`'s behavior, not a property of the dice or the operators that produced the value. So `output 2d10` produces the triangular sum 2..20; `output -(2d10)` collapses the negated pool to -20..-2. The pool / H structure survives every operator that doesn't itself collapse; `output` is the universal collapse site.

- **`d0` shows 0.**
  A die with zero faces produces the constant 0 (one outcome). `_make_die` line ~630. AnyDice convention.

- **Outer-`d` over an empty operand still has cardinality 1 *if the count is die-typed*.**
  For an `NdM` construction, AnyDice's cardinality rule depends on whether `N` is die-typed. If `N` came from a `d`-form (so its evaluation goes through the die-counted expansion path), `#X = 1` even when `M` and/or `N` evaluate to the empty die. If `N` is a scalar or sequence literal, the emptiness propagates and `#X = 0`. So `d{}d{}`, `d{}d2`, and `d2d{}` all give `#X = 1` (with the distribution itself remaining `{}`), while `0d{}`, `{}d{}`, and the bare `d{}` all give `#X = 0`. We preserve this via `_EmptyPoolOfOne` -- a `P` subclass constructed at `_expand_dice_count` (the only construction site for die-counted `NdM`) when the result would otherwise be empty. Its `__len__` returns 1, its `.h()` returns `H({})`, and `[0]` returns `H({})`, so downstream pool operators (`#`, `@`, ...) see a one-element pool whose only die is the empty distribution. The class docstring carries the Rod Serling rationale for future readers. Verified by probe `-0x29` in `tmp-probes.db` (and corpus probe `-0xe`).

- **Strings are not real values.**
  Strings are only valid in `set` argument positions and in `output ... named ...`. They never appear in arithmetic, comparison, sequence, or dice context. See commit `STRINGS. ARE. NOT. REAL. VALUES. IN. ANYDICE.`

### Operators

- **`a / 0` returns 0; division truncates toward zero.**
  No exception is raised; the substitution applies per-outcome inside H-iterated dispatch. `_OP_FUNCS["/"]`.

- **`^` truncates fractional results toward zero.**
  So `2^-1 == 0`, `(-1)^-1 == -1`. Implemented in `_anydice_pow_strict` / `_anydice_pow_lenient`.

- **`0^<negative>` splits by context.**
  In a *scalar^scalar* form AnyDice raises an error; in any H-iterated form (one or both operands are dice/pools) AnyDice substitutes a sentinel value (`-9223372036854776000`, almost certainly a PHP `(int)(-INF)` artifact) per offending per-outcome computation so the surrounding distribution survives. We mirror the split.

- **`&` / `|` have equal precedence.**
  Per commit `Give equal precedence to & and |`.

- **Sequence arithmetic** (when a seq is used in numeric / comparison context):
  - `seq op number` -- each element compared, results summed.
  - `seq op die` -- `sum(seq) op die`.
  - `seq op seq` -- element-by-element lex compare (Python tuple compare).

- **AnyDice has no modulo operator.**
  Design choice; not a divergence.

### Unary operators

- **`-<seq>` collapses, `+<seq>` does not.**
  Asymmetric and known-weird, but consistent in AnyDice. We codify both with our own tests.

- **`-` on a pool is per-die (pool-preserving).**
  `(-N)dX`, `Nd(-X)`, `Nd(-dX)`, and `-(NdX)` all produce a pool of |N| negative-faced dice. Downstream pool consumers (`highest of`, `1@`, ...) see N dice, not a single collapsed-then-negated H. The bare `output` then collapses via the `output`-collapse rule above. See `TestNegativeDiceCountPreservesPoolStructure`. (Two of our `_apply_neg` / `_roll_n` paths used to collapse the pool; both fixed -- see section 3.)

- **`+` on a pool is identity** -- pool preserved. No `_apply_pos` function; PosOp just returns its operand. AnyDice agrees (probe -0x28).

- **`!` collapses through to the sum** on both sides -- `!(2d{0,1})` evaluates as `!(sum(2d{0,1}))`, not as a per-die negation. Faithful. (Probe -0x28.)

- **`#<pool>` returns the dice count as a scalar** -- by design, not a pool operation. (Probe -0x28.)

### Function expansion and scoping (todo-53 family)

- **`:n` / `:s` parameters are iteration-local.**
  When a function call expands across the outcomes of a die-typed argument, each iteration starts with the parameter reset to its entry-bound value. In-body mutations to a parameter do not carry across iterations. Verified via 5fec (`SEQUENCE:s` mutated by `SEQUENCE:[remove X from SEQUENCE]` must *not* compound across X-iterations or draw-without-replacement breaks).

- **Non-parameter variables are call-local.**
  In contrast to parameters, non-parameter variables persist across iterations within a single function call. Probe -7 (`[weird d6]` cumulative `d{1,3,6,10,15,21}`) demonstrates the necessary persistence.

- **First parameter varies fastest in expansion enumeration (little-endian).**
  For a function with multiple expanding `:n`/`:s` params, AnyDice enumerates the first argument as the innermost loop. Codified by `TestExpansionEnumerationOrder` (corpus 0x40389).

- **Function-body sequence return is sum-coerced.**
  If an iteration's `result:` is a tuple, it is `sum()`-ed to a single int before being added to the LCM-normalizing accumulator. Distributing the seq elements as separate outcomes (the prior buggy behavior) double-counts. Verified via 405c6.

- **LCM normalization across iterations.**
  If different iterations of an expanded call return values with different totals (e.g. an H of total 6 vs an H of total 1), the accumulator LCM-normalizes them before merging so per-outcome relative probabilities survive.

- **First-occurrence-wins for duplicate-named function parameters.**
  In `function: f X:n X:n {...}`, the first `X` binding takes effect; subsequent same-named params are bound but their values are discarded for body reads. See commit `Take first like-named parameter, not last`.

- **Built-in functions are looked up after user-defined functions** -- but currently dispatch through a distinct execution path from user-defined functions. Consolidation is queued.

---

## 2. Excluded AnyDice bugs (we deliberately do not replicate)

These are behaviors we have evidence are unintended defects in AnyDice's implementation. Our interpreter remains mathematically correct on these; corpus mismatches caused by them get annotated `divergence:anydice-bug` so AnyDice is not used as the oracle for the affected program.

### Parameter leakage across expansion iterations (per-outcome slot mutation)

AnyDice fails to reset later-position `:n`/`:s` parameters between iterations of an earlier parameter's expansion. The leak is *per-outcome*: each outcome of the later parameter has its own mutable state cell that AnyDice carries forward as the earlier parameter sweeps its values, instead of resetting per `(P_outer, P_inner)` combo. The signature is exactly cumulative-leak across the inner-loop slots; probe -0x26 nails the model exactly (results, including weights, predicted to the last decimal).

This single mechanism is responsible for the entire `divergence:anydice-bug` cluster around param-reassignment-under-expansion: roughly 60+ corpus programs, including the long-parked program `0x1102` (`pentastar dice with penalty dice`). Our interpreter's faithful "params iteration-local / non-params call-local" implementation (5fec / 7f1) is what AnyDice *intends*; AnyDice's implementation of that intent has a missing isolation boundary between params and the shared per-outcome state structure used (correctly) for non-params.

Evidence: probe -0x26 in `tmp-probes.db`; `TestCorpus1102SExpansionAggregationDivergence` (strict-xfail sentinel asserting the AnyDice oracle as a wrong-direction marker).

### int64 overflow on outcome values

AnyDice's computation appears to evaluate in signed int64; large outcome values wrap around to `INT64_MIN` or other artifacts. The `^` / power family is the canonical case: e.g., `2^d1024` produces wrap-around outcomes; `1d100^1d100` produces an outcome of exactly `-9223372036854775808` (= `INT64_MIN`). The huge-integer-literal sub-family (`3d6+9190283...`, `922340-9999999999999999999/100000`) is the same class.

Roughly 30+ corpus programs are in this class. Our exact-bigint computation produces the mathematically correct result; AnyDice is an unusable oracle for these.

Evidence: minimal reproducers in the corpus and `notes/`; deferred-annotate set (the original "32 overflow").

### int64 overflow on H counts (weights)

A related but distinct class: AnyDice's `^` is not the only path that produces huge integers. Big damage-calculator-style programs with many independent random sources produce H weight integers (denominators of outcome probabilities) that easily exceed int64. AnyDice truncates the counts, distorting the normalization for the larger outputs. Our exact-bigint counts are mathematically correct.

Examples: `0x19a58`, `0x25d0d` (substantially similar programs by the same author -- different toggles, both overflow). Our counts reach `~10^47`.

### `_SelectionPrefix` / `_SelectionSuffix` multiplicity (dyce-side, *fixed upstream*)

Listed here for completeness even though the fix is upstream. dyce's `P.h(*selectors)` previously dropped per-position multiplicity when the duplicate-selection covered only a *subset* of pool positions (e.g. `.h(-2,-2)` on a 2-die pool). The Prefix/Suffix selection types were multiplicity-blind; selections with `count>1` over a partial subset fell through to them, silently de-duplicating. AnyDice preserves multiplicity here; we did not. Fixed in dyce `0.7.0rc4`; anydyce pinned to that release.

Evidence: dyce's `tests/test_p.py::test_analyze_selection_single_pos`; corpus `0x11caf` cleared by the upstream fix.

---

## 3. Fixed our-side bugs

Our own correctness improvements discovered during corpus triage. Git is the source of truth; this list exists for transparency.

### Expansion enumeration order (little-endian)

Our `_invoke` used `itertools.product(*expansion)` directly, making the first param the *outermost* loop (big-endian). AnyDice enumerates the first argument as the innermost loop (varies fastest / little-endian). This was invisible until a non-parameter variable persisted across iterations and the per-iteration computation became order-sensitive; corpus `0x40389` was the canonical case. Commit: *Enumerate expansion parameters little-endian, matching AnyDice* (interpreter.py:1002). Fixed corpus programs: `0x40389`, `0x1122e`, `0x12426`, `0x12427`, `0x7bee`.

Built-in dispatch (`_call_builtin`) has the same big-endian pattern but is left for separate investigation; existing builtin tests pass possibly because builtins are order-insensitive in the cases covered.

### Pool-preserving negation

Two paths in our interpreter were both collapsing the pool for unary `-`: `_roll_n` for the `(-N)dX` / `Nd(-X)` / `Nd(-dX)` family, and `_apply_neg` for the explicit unary `-(NdX)` form. Both produced a flat negated H, so downstream pool consumers received the wrong shape. Both now return `P` directly. Commit: *Preserve pool structure through negation* (interpreter.py:380-390 and :656). Fixed corpus programs: `0x30d3a`, `0x30d3b`, `0x34534`, `0x388d2`, `0x34196`, `0x418c8`. Probe -0x28 confirms `+` / `!` / `#` are already faithful.

### `1d(<pool>)` is a no-op

`1d(<pool>)` should yield `<pool>` unchanged so downstream pool consumers (`highest of`, `1@`, ...) see N dice rather than a single H produced by collapsing the pool and re-rolling it as a one-element pool. Previously `_eval`'s `DiceBinOp` path went straight to `_roll_n(1, _make_die(faces))`, and `_make_die(P)` invoked `.h()` on the pool, flattening it. The fix short-circuits when the count is the literal 1 and the faces evaluate to a P. Commit: *Treat 1d(<pool>) as a no-op* (interpreter.py:339-344). Canonical corpus fix: `0x41073` (`[highest 1 of 1d(2d6)]`); cleared roughly 6 corpus programs in the dynamic-sided `1d(<expr>)` family.

### `preserve_zero_counts` in dyce-core (0.7.0rc3)

A dyce-core change re-ported into the dyce-cleanroom branch to support our interpreter's `H.lowest_terms(preserve_zero_counts=...)` use. Not strictly an anydyce bug but called out because the integration unblocked the corpus triage.

---

## Backlog of known opens

These are characterized but not yet fixed / annotated:

- **Built-in expansion enumeration order** (`_call_builtin`, interpreter.py:1144) -- has the same big-endian pattern as `_invoke`; not yet fixed. Whether to converge on one execution path for user-defined + built-in calls is a separate design question.
- **`!` on a pool** -- known to collapse on both sides (faithful), but the deeper question of whether AnyDice would *intend* per-die `!` on a pool isn't resolved. Tracked only as "collapses on both sides today."
- **The 128-program corpus residual** (`mismatch:values` after rc4 + per-die-neg) -- mostly param-leakage / overflow per the existing classification; final annotation pass via the auditor is still ahead.
- **Auditor tooling** -- the re-runnable verifier that regenerates Tier-2 sisters, re-checks the equivalence + `AnyDice(S) == ours(S)` differential, and emits / re-validates `divergence:anydice-bug` annotations against the corpus DB. Not yet built.
