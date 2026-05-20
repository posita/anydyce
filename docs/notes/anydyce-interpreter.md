<!---
Design and status notes for the dyce.anydyce AnyDice interpreter.
Captured from conversations 2026-04-25/26. Ephemeral — not intended for publication.
-->

# dyce.anydyce Interpreter Notes

## What it is

A tree-walking interpreter for the [AnyDice](https://anydice.com) language.
Takes AnyDice source text, returns a list of `(name, H)` pairs — one per
`output` statement in the program.
Public API: `dyce.anydyce.run(source: str) -> list[tuple[str | None, H]]`.

## Files

```
dyce/anydyce/
  __init__.py        public run() entry point
  grammar.lark       Lark LALR(1) grammar
  ast_.py            pure dataclass AST nodes
  transformer.py     Lark Transformer → AST nodes
  interpreter.py     tree-walking interpreter (~970 lines)
  builtins_.py       built-in function registry (parking lot for unwired impls)
  settings.py        runtime settings (position order, max depth)
  unparser.py        AST → canonical source text (used for dedup in helpers)

helpers/
  anydice-programs.py   multi-subcommand: fetch / link / recanon / compute /
                        show / verify (with --builtins-report). Stores
                        programs + reference outputs in SQLite.
  anydice-programs.db   small DB (~1k rows, doc examples + spot-check probes)
  anydice-programs-all.db  full corpus DB being assembled out-of-band
```

Module-name suffix convention: `ast_` and `builtins_` end with an underscore
to avoid clashing with stdlib `ast` and `builtins`. The other modules don't
need suffixes; the `_`-prefix convention used in earlier drafts has been
dropped.

The small reference corpus (`anydice-programs.db`) has ~1080 programs as of
2026-05-04. Reference outputs are the JSON payloads returned by AnyDice's
own evaluator (via `compute --allow-remote`).

## Value domain

Every expression evaluates to one of:

| Type             | Meaning |
|------------------|---------|
| `int`            | AnyDice number |
| `H`              | single die / probability distribution |
| `P`              | dice pool (preserves structure for `@`) |
| `tuple[int, ...]`| explicit sequence (sorted highest-first by default) |
| `str`            | string literal (only used for output names and `set` values) |

Sequences (`tuple`) exist as a distinct type so that functions with `:s`
parameters receive per-roll sequences, not collapsed distributions.

## Grammar notes

- `d` as a single character is a string literal in the grammar, not an
  identifier, so it always beats `LOWERNAME` for the token `d`.
  `double`, `draw`, etc. still lex as `LOWERNAME` because they're longer.
- Reserved words (`output`, `loop`, `if`, `function`, etc.) may appear as
  parts of user function names in definitions and calls.
  The grammar handles this by keeping all lowercase tokens in `fname_word` /
  `call_word` rules with the `!` prefix (keep anonymous tokens).
- Operator precedence tightest-first:
  unary `+/-` > `!` > `#` > `d` > `@` > `^` > `*/÷` > `+/-` > comparisons > `&` > `|`
- Unary `-/+/!` bind *looser* than `d` so `-d6` parses as `-(d6)`.
- `#` binds *tighter* than `d` so `#3d6` parses as `(#3)d6 = 1d6`.

## Interpreter structure

### Statement execution (`_exec`)

`LoopStmt` — iterates a sequence in ascending order.
Runs the body in a *child* environment (copy of parent env), then copies
*all* child variables back to the parent, not just pre-existing ones.
H values are compressed on copy-back (see `_compress_h` below) to prevent
weight explosion across iterations.

`FunctionDef` — appends `(word_slots, params, body)` to `self._functions`.
Most-recently-defined function wins on a match.

`VarAssign` — just stores `env[name] = eval(expr)`.
No compression here; compression happens at loop copy-back.

`IfStmt` — evaluates each branch condition in order, executes first truthy body.
Dice (`H`/`P`) are always truthy.

### Expression evaluation (`_eval`)

Most cases are mechanical.  Key ones:

`BinOp "@"` — routed to `_eval_at()` before arithmetic coercion.
Everything else — `_coerce_for_arith()` (sequences → sum int, pools → H),
then `_apply_h_binop()`.

`_apply_h_binop` — distributes a 2-arg lambda over all `(int|H) × (int|H)`
combinations by explicit cross-product iteration.

`Call` — `_eval_call()`.  Evaluates expression arguments, leaves word parts as
strings, then tries user functions (reversed order) then builtins.
Matching is positional: length must match, words must match, arg slots accept
any non-string value.

### The @ operator (`_eval_at`)

Right operand governs dispatch:

- `P` or `H` → `_pool_h_select(pool, positions)` → H distribution.
  Uses `pool.h(*selectors)` with `slice` objects built from 1-based positions.
  In highest-first mode position 1 is the highest die (`slice(-1, None)`),
  position 2 is second-highest (`slice(-2, -1)`), etc.
- `tuple` (sequence) → deterministic index: position 1 → last element in a
  lowest-to-highest tuple (index `-1`), etc.
- `int` → digit access (1-based into decimal digits of the integer).

Left operand becomes the position list:
- `int` → single position.
- `tuple` → list of positions.
- `H` → expand outcomes (used when positions come from another die).

### Function dispatch and probabilistic expansion (`_dispatch_coercion`)

This is the heart of the interpreter.  It scans parameters left-to-right for
the first one that needs "expansion" — calling the body multiple times and
aggregating results into a new H:

**`:n` with `H`** — `_expand_over_h`: calls body once per outcome of the die,
collects `(outcome_weight, result)` pairs, passes to `_expand_normalized`.

**`:n` with `P`** — collapses pool to H via `_h_from_pool`, then same as above.

**`:n` with `tuple`** — converts to `sum(tuple)`, continues scanning.

**`:d` with `int` or `tuple`** — wraps in `H({val: 1})` or `H({sum: 1})`, continues.

**`:s` with `H`/`P`/`int`** — `_expand_over_s`: enumerates all sorted rolls from
the pool via `pool.rolls_with_counts()`, calls body once per roll with the
sequence as the argument, collects `(count, result)` pairs, passes to
`_expand_normalized`.

**No expansion needed** — `_exec_function_body`.

`_dispatch_coercion` is called recursively by `_expand_over_h` / `_expand_over_s`
so that multi-parameter functions with multiple expansions are handled correctly.

### LCM normalization (`_expand_normalized`)

When a function body returns `int` for some inputs and `H` for others (or H
values with different weight totals), naively doing `outer_weight * inner_weight`
gives wrong relative probabilities because the inner totals are different scales.

`_expand_normalized` collects all `(outer_weight, result)` pairs, computes the
LCM of all inner totals, and scales each contribution by `lcm / inner_total`
before calling `_accumulate`.  This puts everything on a common denominator.

For the common case where all inner results are the same type (all int, or all H
with the same total), LCM normalization is a no-op and the result is identical
to the naive approach.

### Function body execution (`_exec_function_body`)

Creates a new env: start from globals, overlay `caller_env` (dynamic scoping —
AnyDice functions can read variables from the calling scope), then bind params.
Runs body statements; a `result:` statement raises `_Result` to break out.
If no `result:` is hit, returns `H({})` (empty die).

### Dynamic scoping

AnyDice is dynamically scoped: a called function can read variables from
its caller's local environment.  `_exec_function_body` takes an optional
`caller_env` and does `env.update(caller_env)` before binding params.
`_dispatch_coercion` passes through `caller_env` to ensure it is preserved
across the expansion loop.

### Built-in expansion (`_coerce_args`)

Same expand-and-aggregate pattern as user functions, but uses
`_expand_builtin_over_h` / `_expand_builtin_over_s` which call `_accumulate`
directly (no LCM normalization — builtins always return int, so all inner
totals are 1 and LCM would be a no-op anyway).

### Weight compression (`_compress_h`)

Two-stage:
1. GCD-reduce all weights (lossless — same probabilities, smaller numbers).
2. If total still exceeds `_MAX_H_TOTAL = 10**12`, apply lossy scaling via
   `round(v / scale)` where `scale = total / _MAX_H_TOTAL`.

Currently called in two places:
- `LoopStmt` copy-back: prevents weight explosion when a loop updates a die
  variable on each iteration (e.g. 45 iterations each squaring the total).
- `_pool_h_select`: prevents OOM on program 140338, which does `1@2d[H]` inside
  a 23-level recursion, squaring H's total weight on each level.

The lossy scaling means the `_pool_h_select` compression can introduce tiny
errors.  For programs that stay under 10¹² without it the compression is a
lossless GCD reduction and the results are exact.

## Corpus validation

`helpers/validate_anydyce.py` reads programs from the DB, runs each through
the interpreter, converts both our distribution and AnyDice's reference to
`{outcome: pct}` dicts, and diffs them with a tolerance of `1e-4` percentage
points.

Reference outputs occasionally have totals that deviate from 100% (AnyDice
rounding artifact); `ref_to_pct` normalizes these when the deviation exceeds
0.5 pp.

Programs whose reference output is not valid JSON (AnyDice timeout) are
silently skipped (`status="skip"`).

### Current results (2026-04-26)

```
Results: 411/654 passed
  pass: 411
  skip: 13
  runtime_error: 18
  value_mismatch: 212
```

The first full-corpus run that completed without OOM was with `_compress_h`
applied in `_pool_h_select` (required to get past program 140338 at position
315/654 in processing order).  All earlier runs were OOM-killed and the "Results:"
line was never printed, so any pass count cited from earlier sessions should be
considered unverified.

### Known remaining failure categories

**Runtime errors (18):**
- Programs 108377, 119473-475: `TypeError: expected int, got H` or `got P` —
  likely a builtin receiving an unexpected distribution type.
- Programs 43706, 58639-43, 176079, 176166, 194293, 232746, 250447, 270450-56:
  various runtime errors not yet investigated.

**Value mismatches (212):**  Not fully categorized.  Known-difficult patterns include:
- Building sequences in loops (`R: {}`, then `R: {R, P@ROLL}` per iteration)
  — these accumulate sequences whose semantics interact with `@` indexing in
  non-obvious ways.
- `ROLL = I` where ROLL is a sequence and I is an integer — should return the
  *count* of elements equal to I, but this goes through `_coerce_for_arith`
  which converts sequences to their sum before the comparison.
- Dynamic scoping programs that reference multiple levels of caller env
  (e.g. program 25893).
- Programs using `1@POOL` inside a function body that itself receives a `:s`
  sequence — the pool selection creates an H inside a deterministic sequence
  context.

## Semantic decisions (2026-05-04 / 2026-05-05)

A batch of AnyDice oracle-driven fixes landed, codifying behaviors that had
been wrong or undefined in the interpreter. These supersede earlier
sections where they conflict.

### Multi-position `@` (seq-on-left)

A seq on the left of `@` selects multiple positions; results sum. Same
semantic uniformly across right operands:
- `{1, 4} @ {10, 20, 30, 40}` = 10 + 40 = 50 (positions 1 and 4 in source order).
- `{1, 3} @ 3d6` = top-of-pool + bottom-of-pool sum distribution. Out-of-range
  positions silently contribute 0.
- `{1, 3} @ 4567` = digit-extract at positions 1 and 3, summed.

Implementation: `_at_seq` and `_at_pool` recognize a tuple-left and dispatch
to multi-position selection (using `pool.h(*selectors)` for pools so
correlated positions are summed jointly, not as independent draws). Verified
against AnyDice (program 42ad5).

### `N @ H` treats H as a 1-element pool

A non-empty H on the right of `@` is treated as a 1-element pool:
- `1 @ d6` returns the d6 distribution (the sole position).
- `2 @ d6` returns `H({0:1})` (out of range on a 1-pool).
- Empty `H({})` propagates as `H({})`.

Implementation: `_apply_at` wraps `H` as `P(H)` and forwards to `_at_pool`,
reusing the 1-based-position logic. Verified via 405c6 (`[ex H]` chain
producing `H({0:1})`) and `1@d6` displaying as label `"d6"`.

### `:d` parameter is lossless on pools

A `:d` parameter binds a P argument as the actual pool (no `arg.h()`
collapse). The body's pool-aware ops (`@`, future builtins, etc.) see the
real pool, not its summed H. Arithmetic and comparison ops collapse P → H
at the operator site, so keeping P in the env doesn't break those.

The `:d` branch does *not* short-circuit on empty H/P: the body runs once
regardless, and the body's conditionals (`if X { result: REROLL }` with
REROLL = `d{}`) decide which iterations produce empty (eliminated branches)
versus values. Verified via 17b65 (`[[highest 3 of 4d6] reroll {3..9} as
d{}]` produces the [highest 3 of 4d6] distribution restricted to outcomes
10..18) and 428fb (`[pick 1 and 3 from pool 3d6]` correctly multi-positions
the pool).

### Bare/untyped function parameters: pass-through, no coercion

When `function: f X { ... }` has no `:n` / `:d` / `:s` / `:?` annotation, the
argument is bound to the parameter as-is, with no coercion or expansion. The
body sees the value with its original type — int as int, seq as seq, die as
die, pool as pool.

This is *different* from any of the explicit types:
- `:n` would sum-coerce seqs to ints, expand H/P across outcomes per
  iteration, and bind a scalar inside the body.
- `:d` would coerce ints/seqs to a 1-outcome H, keep P as P, and bind a
  die-shape inside the body.
- `:s` would coerce ints/seqs to seqs, expand pools per roll, and bind a
  seq inside the body.
- The bare/untyped form does *none* of those.

Verified against AnyDice via probes (42ace and the `[f {1,2,3}]` / `#X`
round-trip).

For AnyDice NG, the recommendation is to make untyped a parse error and
require explicit `:n`/`:d`/`:s` everywhere.

### `#` operator on dies and pools

- `#int` → digit count of `abs(int)`; `#0 = 1`.
- `#seq` → length (with duplicates).
- `#H` → 1 (a die is a 1-position pool); empty `H({})` → 0.
- `#P` → `len(P)`; empty pool → 0.

Earlier impl returned 0 for any non-empty H/P with the comment "always
returns 0 for any die in AnyDice." That was wrong. Verified via 42af3 and
65d9 (`(#DICE) d NEW` with DICE bound to a 2d6 pool requires `#DICE = 2` to
produce the correct distribution).

### Chained `d` is left-associative

`2d2d2` parses as `(2d2)d2`, NOT `2d(2d2)`. The left-assoc form takes the
first dice expression as the *count* of the next roll, and `_expand_dice_count`
LCM-normalizes across the count's outcomes. The right-assoc form (with
explicit parens) is just nested pools. Verified via 42af2:
- `2d2d2` = `(2d2)d2` = `H({2:4, 3:12, 4:17, 5:16, 6:10, 7:4, 8:1})`.
- `2d(2d2)` = `4d2` = `H({4:1, 5:4, 6:6, 7:4, 8:1})`.
- `4d3d2d1` parses as `((4d3)d2)d1`.

### Die-in-seq block-repeats outcomes

When a die appears in a sequence literal with a repeat count, the *block of
distinct outcomes* is repeated, not each outcome individually:

`{d4:2}` → `(1, 2, 3, 4, 1, 2, 3, 4)`, NOT `(1, 1, 2, 2, 3, 3, 4, 4)`.

This makes die-in-seq semantically equivalent to seq-in-seq: `{d4:2}` and
`{{1,2,3,4}:2}` produce identical sequences. Verified via 42971/42974/42975
(positional lookups disambiguate). The H output of `output {2d4:2}` is
identical under either interpretation (because `output` collapses to a
count dict regardless of order), which is why this bug survived our
existing test coverage.

### Function body sequence returns under expansion: sum-coerced

When a function with explicit n-typed (or s-typed) parameters expands across
argument outcomes and the body returns a sequence per iteration, AnyDice
sum-coerces the seq to a single number before accumulating. Our prior impl
distributed seq elements as separate outcomes, which double-counted.

Implementation: `_invoke` and `_call_builtin` per-iteration accumulators
check `isinstance(r, tuple)` and replace with `sum(r)` before
`_coerce_to_h`. `_coerce_to_h` itself still distributes seqs as multi-
outcome H — it's the right thing for `output {1, 2, 3}` and other
non-iteration contexts.

Verified against AnyDice via 405c6 (`[roll 1d6 1d6]` with body `result:
{A+B, C}` produces an H over `A+B+C`, not over `{A+B, C}` elements).

### Per-iteration LCM normalization

Already-known but worth noting alongside the seq-coerce fix: `_invoke`,
`_call_builtin`, and `_expand_dice_count` each LCM-normalize per-iteration
return totals before accumulating. Without this, an iteration that returns a
die (sum=k) contributes k× as much weight as an iteration returning a
scalar (sum=1), which is wrong.

The three sites currently duplicate this logic. A future cleanup is to
extract a single `aggregate_weighted_lcm` primitive into `dyce.h` (todo 32
in the cleanroom todo list); the existing `aggregate_weighted` uses
product-of-totals as its scalar, which is correct but produces astronomical
big-int counts for many iterations.

### Sub-sequences flatten in seq literals

When a sub-sequence appears as an element of an outer sequence literal, its
elements concatenate into the outer sequence rather than sum-coercing. The
common idiom `NEW: {NEW, val}` (extending a running list) depends on this.
Verified via 663d (a `set element` function building a 7-element list one
loop iteration at a time).

### Division by zero: substitute 0 per-outcome

`_OP_FUNCS["/"]` returns `0` when the divisor is `0` rather than raising.
For distributions, this happens per-outcome inside the cross-product in
`_h_binop`. Verified against AnyDice (`output 1 / 0` → 0, `output (1/0)+5` →
5, `output 1 / d{0, 1, 2}` → H({0:2, 1:1})).

AnyDice does *not* support a modulo operator, so the same question doesn't
arise there.

### Builtins wiring policy

`builtins_.py` has implementations for ~13 AnyDice builtins. Wiring policy:
enable one family at a time, with dedicated TDD coverage per family verified
against AnyDice oracle programs before flipping the entry on.

Currently wired (2026-05-05):
- `[highest of A and B]`, `[highest N of P]`
- `[lowest of A and B]`, `[lowest N of P]`
- `[count A in B]` (multiset semantic, not set; verified via `[count {6, 6} in {6}]` = 2)
- `[sort SEQ]` (direction depends on position-order setting -- see below)
- `[explode DIE]` (with `set "explode depth"` validation; see below)

Pending in the parking lot (impl present, not wired): `absolute`, `contains`,
`maximum of`, `reverse`, `middle of`.

### `[sort SEQ]` direction

AnyDice's `[sort SEQ]` returns a seq whose source-order position 1 is the
"most prominent" element under the current position-order setting:
- Under "highest first" (default): position 1 = HIGHEST, so the seq sorts
  DESCENDING.
- Under "lowest first": position 1 = LOWEST, so the seq sorts ASCENDING.

Verified via `output 1 @ [sort {3, 1, 2}]` and `output 3 @ [sort {3, 1, 2}]`
under each setting (program 42afc). With a die or pool argument, `:s`
expansion + per-iteration sum-coerce makes `[sort <pool>]` ≡ `<pool> sum`
(observationally; no real ordering survives the accumulator). Optimizable
in a future transpiler peephole pass (todo 38) but not in the legacy
interpreter.

### `[explode DIE]` and the `set` settings validators

AnyDice's `[explode DIE]` rerolls when the max face is rolled, summing
rerolls; default depth is 2 (up to 2 extra rolls past the original).
`[explode 2d6]` collapses the pool to its sum H first, then explodes when
the *sum* hits max (12). Verified via 42b00.

`set "explode depth" to V` and `set "maximum function depth" to V` only
accept positive integers (≥ 1). Setting to 0, a negative value, or a string
errors with "<key> can only be set to a positive integer (the default is N)"
in AnyDice. Floats parse-error (no float syntax). Mirrored in
`Settings.set` via the `_POSITIVE_INT_KEYS` allowlist. Verified via 42aff.

Explode and `maximum function depth` are independent budgets (verified
42b05): the explode-depth budget consumes its own counter, not the function
recursion depth. AnyDice's at-recursion-limit return value is `H({})` (the
empty die), matching our impl exactly (verified 42b06).

### `[count A in B]` is multiset, not set membership

The builtin counts how many *occurrences* of each element of B appear in A
treated as a multiset, not just set membership. `[count {6, 6} in {6}]` = 2
(verified via single-shot AnyDice oracle). Earlier impl used `set(values)`
which silently collapsed duplicates and gave 1 for the same input. The
existing oracle 42ad4 (`[count {1, 2} in {1, 2, 2, 3}]` = 3) didn't
disambiguate because VALS had no duplicates.

Implementation: `_count_in(values, seq) = sum(values.count(v) for v in seq)`
in `builtins_.py`.

### `code block (inside function)` mirrors AnyDice's EBNF

AnyDice's EBNF (in `/home/matt/dev/sandbox/anydice/anydice.com/ebnf.txt`)
defines:

```
code block (inside function) = '{' , { statement } , [ result definition ] , '}' ;
```

This rule is reused by function definitions, conditional blocks (inside
function bodies), and loop blocks (inside function bodies). Mirroring it in
our grammar as a `_code_block` filter rule (Lark's `_` prefix inlines
children into the parent) gives:

```
_code_block      : "{" body_stmt* result_stmt? "}"
function_def     : "function" ":" funcname _code_block
body_loop_stmt   : "loop" UPPERNAME "over" expr _code_block -> loop_stmt
body_if_stmt     : "if" expr _code_block body_elseif* body_else_clause? -> if_stmt
body_elseif      : "else" "if" expr _code_block -> elseif
body_else_clause : "else" _code_block -> else_clause
```

The `result_stmt?` placement enforces "result: must be the last statement
in its block" — verified via 2f5ce, which AnyDice rejects with "I was
expecting a }" because of `loop THROW` after `result: NIX` in a function
body. AnyDice DOES allow function definitions inside top-level loops/ifs
(verified via 24c93); only intra-body result-position is restricted.

A future audit (todo 37) should walk the rest of AnyDice's EBNF and identify
other places we diverge.

### Helper-side defenses against AnyDice quirks

`helpers/anydice-programs.py` accumulates a small library of defenses
against AnyDice's various non-standard response shapes:

- **HTML-prefixed JSON.** AnyDice's PHP layer occasionally emits `<br />
  <b>Fatal error</b>: ...<br />` before the structured timeout JSON. The
  `_extract_json` helper finds the first `{` and slices from there before
  `json.loads`. Stored at compute time and applied again at verify/show
  time so existing dirty rows reclassify correctly.
- **Empty 500 body** (resource exhaustion, e.g. `1d200000000`). Stored as
  empty string; surfaced by show/verify as a distinct category.
- **Bad UTF-8** (raw request bytes echoed back). `decode("utf-8",
  errors="replace")` keeps the body parseable; structural JSON is ASCII so
  only string contents take U+FFFD substitutions.
- **Calculation error with literal control chars in the message string**
  (e.g. embedded newline). `json.loads(..., strict=False)` accepts them.
- **Empty result `{}`** when a program completes without firing any
  `output`. Treated as a legitimate result, distinct from `error`.
- **No-such-program returns 200 + placeholder.** AnyDice returns a 200 OK
  with `var loadedProgram = "output 0 \ Sorry, AnyDice does not have the
  program you requested. \"`. Detected by exact program-text match,
  with an allowlist of program IDs that legitimately saved the placeholder
  text (`_NOT_FOUND_PLACEHOLDER_LEGIT_IDS = {0x790, 0x1AF0}`).

### Verify subcommand

`helpers/anydice-programs.py verify` runs every program through
`dyce.anydyce.run`, compares the result to the stored AnyDice JSON, and
buckets each row as match / match:approximate / mismatch:* / interp-error:*
/ interp-timeout / anydice-* / unrun. `match:approximate` covers
distributions whose proportions agree within `1e-8 %` absolute tolerance
(comfortably above `_pct_to_counts` recovery noise floor of ~`1e-9 %`,
comfortably below the smallest real-bug magnitude — e.g. a one-count
error in a 12d4 distribution produces ~`6e-6 %`).

`--timeout SECONDS` bounds the per-program interpreter wall clock via
`signal.SIGALRM`. `--show-max N` controls per-bucket sample output (0 =
unlimited). `--builtins-report` skips verification and instead prints a
frequency table of non-user-defined call shapes across the corpus.

### Compare subcommand

`helpers/anydice-programs.py compare HEX_ID...` does a side-by-side dump of
every distribution from our interpreter vs the stored AnyDice output for one
or more programs. Unlike `verify`, this does NOT short-circuit on the first
mismatch -- all dists are printed in order with a per-dist match indicator
(`match` / `match:approx` / `DIFF`). Useful when investigating multi-output
programs where the interesting divergence isn't dist[0].

### Two-stage `_pct_to_counts` recovery

Strategy 1 estimates `T = round(100 / p_min)` (handles common case in
microseconds; bounded at `T = 10^15` for float-arithmetic safety). Strategy
2 (fallback) walks `Fraction.limit_denominator` bounds 1e3..1e9. The
Fraction-based proportion comparison in `_proportions_close` then bridges
recovery noise vs real divergence at 1e-8 % tolerance.

### AnyDice's joint `:n`-expansion bug for non-uniform dies (programs 4123a / 42b16-23)

Programs 4123a et al. expose a bug in AnyDice's joint `:n`-expansion when both
arguments are non-uniformly-weighted dies (e.g. `d{1:5, 10:2, 100:3}`). The
isolation probes 42b20/42b21/42b23 strip the function body to just `result:
TRUMP_CONTROLS` (or TRUMP_LOSSES) -- expressions that depend ONLY on CARDS, so
the DICE expansion is ineffectual at the marginal-distribution level. Yet
AnyDice's aggregate doesn't match the clean Cartesian-product weighting:

| body | clean Cartesian | AnyDice |
|---|---|---|
| TRUMP_CONTROLS | 0: 85.71%, 1: 14.29% | 0: 73.275%, 1: 26.725% |
| TRUMP_LOSSES   | 0: 64.29%, 1: 35.71% | 0: 71.749%, 1: 28.251% |

Independently confirmed via a pure-dyce reference implementation (no anydyce
interpreter) using `expand(callback, 4 @ P(die), 1 @ P(card))`:

```python
from dyce import H, P, PResult, expand

def alchemist(dice: PResult, cards: PResult, *, return_which="trump_ctrls"):
    dice_ = 1000 + sum(dice.roll)
    cards_ = 1000 + sum(cards.roll)
    effects = int(str(dice_)[1])
    trump_ctrls = int(str(cards_)[2])
    trump_losses = int(str(cards_)[3])
    return locals()[return_which]

die = H({1:5, 10:2, 100:3})
card = H({1:5, 10:2, 100:7})
expand(alchemist, 4 @ P(die), 1 @ P(card), return_which="trump_ctrls").format_short()
# {avg: 0.14, 0: 85.71%, 1: 14.29%}    -- matches our anydyce interpreter
```

So our interpreter is consistent with the dyce-native reference (which has no
shared code with the AnyDice interpreter), and AnyDice's output is the
outlier. There is no consistent mental model under which AnyDice's per-call
results (verified scalar-by-scalar via 42b13) AND its aggregate would both
be right; the bug is in AnyDice's joint-expansion path.

Filed under "AnyDice-side bugs we deliberately don't reproduce" (todo 35).

### Implicit-collapse pile-up (NG design driver)

A small program like `D: [number of 2d6 excluding 4d6]; output #D` exposes
how many implicit-coercion steps stack up in legacy AnyDice:

1. `EXCL:s` with a P arg → expansion across `rolls_with_counts()`.
2. Body executes once per roll, producing a per-roll value.
3. The per-iteration accumulator merges heterogeneous returns by collapsing
   pools to their summed H — there's no way to keep P-shape across
   iterations that return different shapes, so the result is *always* an H.
4. So the function call's return is an H, not a P.
5. The caller binds `D` to that H, then `#D = 1` per the "die is a
   1-position pool" rule.

Each step is documented somewhere in the surface area; the cumulative
behavior is opaque without tracing. This is the kind of implicit-coercion
chain that AnyDice NG should eliminate, though *which* steps to expose is
still open. Candidates:
- Functions declare their return type explicitly, OR the caller wraps the
  call in an `expand X:T over <pool> [...]` form. (Strong consensus.)
- Pool-shape is preserved when the function says so; otherwise an explicit
  `sum` or analogous coercion is required. (Open.)
- Whether H and 1-pool should remain interchangeable to users is *not*
  settled. The unified "die is a die" model is convenient and matches
  decades of AnyDice idiom. The decision is binary:
  - **Unified (status quo / lean):** `H` is a 1-pool, `#H = 1`, `1@H = H`.
    No new syntax, the existing legacy idiom keeps working. Internal
    representation may still distinguish for efficiency.
  - **Distinct:** make histograms a first-class surface type with their
    own annotation (e.g. `:h` alongside `:p`). Then the distinction is
    visible *and* declarable, not just imposed at coercion sites. Don't
    half-implement — exposing the distinction without giving users a way
    to declare and reason about it makes the surface worse, not better.

  Defer; status-quo unified looks like the right default unless a concrete
  semantic gap argues for splitting them.

### Bare/untyped function parameters: pass-through, no coercion

When `function: f X { ... }` has no `:n` / `:d` / `:s` / `:?` annotation, the
argument is bound to the parameter as-is, with no coercion or expansion. The
body sees the value with its original type — int as int, seq as seq, die as
die, pool as pool.

This is *different* from any of the explicit types:
- `:n` would sum-coerce seqs to ints, expand H/P across outcomes per
  iteration, and bind a scalar inside the body.
- `:d` would coerce ints/seqs to a 1-outcome H, collapse P to H, and bind a
  die inside the body.
- `:s` would coerce ints/seqs to seqs, expand pools per roll, and bind a
  seq inside the body.
- The bare/untyped form does *none* of those.

Verified against AnyDice via probes:
- `function: f X { result: X + X }; output [f d6]` → 2d6 sum (not 2 * d6),
  confirming X is the die. (Program 42ace.)
- `function: f X { result: # X }; output [f {1, 2, 3}]` → H({3:1}),
  confirming X is the seq (not sum-coerced).

Implementation: `_invoke` and `_call_builtin` both treat `param.type is None`
as "bind `arg` directly, do not append to the expansion list." Earlier
drafts defaulted untyped to `"n"`; that was wrong.

For AnyDice NG, the recommendation is to make untyped a parse error and
require explicit `:n`/`:d`/`:s` everywhere.

### `N@H`: H is a 1-element pool

For the `@` operator, a non-empty `H` (a die-shaped distribution) is treated
as a 1-element pool:
- `1@H` returns the die unchanged (its full distribution).
- `N@H` for `N != 1` is out-of-range on a 1-pool and returns 0.
- `0@H` and negative N likewise return 0.
- Empty `H({})` propagates as `H({})`.

Implementation: `_apply_at` wraps `H` as `P(H)` and forwards to `_at_pool`,
which already has 1-based-position semantics with the correct
position-order interaction.

Verified via probes (`output 1 @ d6` → d6 distribution, even labeled `"d6"`
in AnyDice's output) and via 405c6 (`[ex H]` where ex computes `2 @ A` →
`H({0: 1})`).

### Function body sequence returns under expansion: sum-coerced

When a function with explicit n-typed (or s-typed) parameters expands across
argument outcomes and the body returns a sequence per iteration, AnyDice
sum-coerces the seq to a single number before accumulating. Our prior impl
distributed seq elements as separate outcomes via `_coerce_to_h(tuple)` =
`H(Counter(tuple))`, which double-counted.

Implementation: `_invoke` and `_call_builtin` per-iteration accumulators
check `isinstance(r, tuple)` and replace with `sum(r)` before
`_coerce_to_h`. `_coerce_to_h` itself still distributes seqs as multi-
outcome H — it's the right thing for `output {1, 2, 3}` and other
non-iteration contexts.

Verified against AnyDice via 405c6 (`[roll 1d6 1d6]` with body `result:
{A+B, C}` produces an H over `A+B+C`, not over `{A+B, C}` elements).

### Per-iteration LCM normalization

Already-known but worth noting alongside the seq-coerce fix: `_invoke`,
`_call_builtin`, and `_expand_dice_count` each LCM-normalize per-iteration
return totals before accumulating. Without this, an iteration that returns a
die (sum=k) contributes k× as much weight as an iteration returning a
scalar (sum=1), which is wrong.

The three sites currently duplicate this logic. A future cleanup is to
extract a single `aggregate_weighted_lcm` primitive into `dyce.h` (todo 32
in the cleanroom todo list); the existing `aggregate_weighted` uses
product-of-totals as its scalar, which is correct but produces astronomical
big-int counts for many iterations.

### Division by zero: substitute 0 per-outcome

`_OP_FUNCS["/"]` returns `0` when the divisor is `0` rather than raising.
For distributions, this happens per-outcome inside the cross-product in
`_h_binop`. Verified against AnyDice (`output 1 / 0` → 0, `output (1/0)+5` →
5, `output 1 / d{0, 1, 2}` → H({0:2, 1:1})).

AnyDice does *not* support a modulo operator, so the same question doesn't
arise there.

### `^` (power): strict in scalar context, lenient in H context

`0^negative` is mathematically undefined.
AnyDice splits behavior by operand types:

- **Scalar^scalar** (no H/P involved): raises an explicit error.
  E.g. `output 0^-1` errors out.
- **Any H-involving form** (`scalar^H`, `H^scalar`, `H^H`, etc.): substitutes the sentinel value `-9223372036854776000` (= `-(2^63 + 192)` = `-0x80000000000000C0`) for every offending per-outcome result, so the surrounding distribution survives.
  E.g. `output 0^d{-1}` produces `H({-9223372036854776000: 1})`, and `output 0^d{-1, -2, -100}` produces `H({-9223372036854776000: 3})` (constant sentinel regardless of exponent).

The split principle: errors don't compose probabilistically -- erroring on one outcome would kill the whole distribution.
We mirror it via two `_anydice_pow_*` functions registered in parallel op tables (`_OP_FUNCS` for the scalar path, `_OP_FUNCS_H_ITER` for the H-iteration loop in `_h_binop`).
The sentinel's specific value is almost certainly an artifact of PHP's `(int)(-INF)` cast on AnyDice's server; we adopt their exact value for verify-fidelity.

Note that all other negative-exponent results (e.g. `2^-1 = 0`, `(-2)^-1 = 0`, `(-1)^-1 = -1`) come out via `int(a**b)` truncating toward zero, in both strict and lenient variants.
The strict/lenient split only matters for the `0^negative` case.

### Builtins wiring policy

`builtins_.py` has implementations for all AnyDice builtins we've identified, and all are currently wired into the `BUILTINS` registry.
Originally the policy was to enable one family at a time with dedicated TDD coverage per family verified against AnyDice oracle programs before flipping the entry on; that gating is now complete.
New families should still land under the same TDD pattern when they're added.

### Undocumented `[highest/lowest N of A and B [and C]]` builtins

AnyDice exposes four undocumented patterns that are NOT user-definable via the function-definition syntax (you can't write `function: highest N:n of A:d and B:d`; the parser would treat that as a same-shape user function only callable with a specific dispatch shape, but AnyDice's builtin preempts).
They construct a heterogeneous pool from the listed dice and select the N highest / N lowest:

- `[highest N of FIRST and SECOND]` ≡ `P(FIRST, SECOND).h(slice(-N, None))`
- `[lowest N of FIRST and SECOND]` ≡ `P(FIRST, SECOND).h(slice(0, N))`
- `[highest N of FIRST and SECOND and THIRD]` ≡ `P(FIRST, SECOND, THIRD).h(slice(-N, None))`
- `[lowest N of FIRST and SECOND and THIRD]` ≡ `P(FIRST, SECOND, THIRD).h(slice(0, N))`

There is NO four-or-more-die variant; the family is exactly 2-die and 3-die.
Scalar arguments are valid (coerce to single-face dice via `:d` semantics) and pool arguments are valid too (dyce's `P()` flattens nested pools so `P(2d6, 1d4)` correctly yields a 3-die pool).
171 corpus programs use these patterns; without them we got `NameError: undefined function for call` on dispatch shape mismatches.

### `&` and `|` share precedence level (NOT C-style)

Per AnyDice's EBNF (level 7) and verified empirically (`output 1 | 1 & 0` produces `0`), `&` and `|` are at the **same** precedence level and left-associative across both operators.
So `1 | 1 & 0` parses as `(1 | 1) & 0` (= 0), not C-style `1 | (1 & 0)` (= 1).

Our grammar reflects this with a single `bool_expr` rule listing both operators as alternatives.
This is a real semantic divergence from most programming languages and silently affects any corpus program that combines `&` and `|` in a single expression with `|` on the left.

### Verify subcommand

`helpers/anydice-programs.py verify` runs every program through
`dyce.anydyce.run`, compares the result to the stored AnyDice JSON, and
buckets each row as match / mismatch:values / mismatch:dist-count /
parse-fail / interp-error:&lt;ExcType&gt; / interp-timeout / anydice-error /
anydice-empty / anydice-resource / anydice-bad-json / anydice-bad-shape /
unrun. Comparison normalizes both sides by gcd-reduction.

`--timeout SECONDS` bounds the per-program interpreter wall clock via
`signal.SIGALRM` (Linux/macOS only). `--show-max N` controls per-bucket
sample output (0 = unlimited). `--builtins-report` skips verification and
instead prints a frequency table of non-user-defined call shapes across the
corpus — useful for prioritizing which builtin to wire next.

Current isolation model is in-process: `verify` and `compare` enforce only
a wall-clock budget. An OOM on a single program crashes the helper. This
is fine for the small DB (~1100 programs) but doesn't scale to the full
corpus (~159804 de-duped programs as of 2026-05-05, ~74580 AnyDice results
collected so far, complete in a few days). Hardening plan tracked as todo
40: `multiprocessing.Pool(forkserver)` with per-worker
`resource.setrlimit(RLIMIT_AS, ...)`, per-job `pool.apply_async().get(
timeout=...)`, new `interp-oom` (clean `MemoryError`) and `interp-killed`
(kernel SIGKILL / `BrokenProcessPool`) buckets, `maxtasksperchild` to
recycle workers, parallelism via `Pool(processes=os.cpu_count())`. Pool
overhead at full-corpus scale is negligible vs. ~75ms-per-program of
`subprocess.run` cold-start (~3.3 hours of pure overhead at 160k).

### Performance gap on deep-recursion programs (2026-05-05)

Nine small-DB programs time out where AnyDice returns instantly (22432,
42074, 286e0, 183de, 183d4, 183b0, 149c7, 149bf, 149bd). Root-cause
investigation refined the diagnosis twice:

1. **First framing — exact vs approximate fundamental tradeoff.** Wrong.
   The user wrote a dyce-native translation of 22432's `function: highest
   of N:n x D:d` (`test_highest.py` at the repo root) using
   `dyce.evaluation.expand`; it runs in ~2 seconds and emits a
   `TruncationWarning`. So dyce can do it.
2. **Second framing — `expand`'s opt-in branch truncation is the
   speedup.** Also incomplete. User tested `precision=Fraction(1, 2**8192)`
   (a threshold so absurdly small that no path probability at recursion
   depth ~23 over a d6 should ever fall below it), and the program *still*
   ran fast and *still* emitted the `TruncationWarning`. So truncation is
   firing but it's trimming a tail that's tiny either way -- it isn't the
   dominant speedup.
3. **Working hypothesis — structural optimization in `expand`.** Most
   likely outcome-grouping (merging branches with identical outcomes
   before recursing, so work scales with distinct outcomes per d6 face,
   not paths) and/or memoization on `(callable, args-as-H-tuple)`. In
   `highest_among(half_h, half_h)` the two arguments are identical at every
   recursion level; a cache would collapse the recursion massively. Need to
   read `dyce/evaluation.py` end-to-end to confirm before designing the
   mitigation.

Our `_invoke` / `_call_builtin` accumulators have no equivalent of either
optimization. Mitigation tracked as todo 39 -- gated on the
`expand`-internals investigation since the fix shape depends on what
`expand` actually does.

#### Why the `TruncationWarning` displays the source line twice

Cosmetic, surfaced during investigation: a single top-level `expand` call
emits *two* distinct warnings, both with `stacklevel=2` pointing at the
user's `return expand(...)` line:

- `dyce/evaluation.py:422` -- `ExperimentalWarning` once per outermost
  `expand` call (when no `_expand_ctxt` is in scope yet).
- `dyce/evaluation.py:462` -- `TruncationWarning` if any branches were
  dropped.

Each renders as `header\n  source-line\n`. Adjacent emissions look like
the source line is printed twice, but it's two different warnings whose
tails happen to be the same source. `explode_n` at `evaluation.py:587`
already wraps internal `expand` calls in
`warnings.catch_warnings()` with `filterwarnings("ignore",
category=ExperimentalWarning)` to suppress the noise from a public API
that itself uses `expand`.

### Two-stage `_pct_to_counts` recovery

Previously, AnyDice's percentage strings were converted to integer counts
via `Fraction.limit_denominator(10**9)` per outcome and an LCM combine.
That produces spurious large-denominator fits when AnyDice's printed
precision (~13 sig figs) doesn't pin the true rational uniquely.

New algorithm:
1. **Estimate-T strategy.** Compute `T_est = round(100 / p_min)` where
   `p_min` is the smallest non-zero percentage. This typically nails the
   natural total (4^12 for 12d4, 7776 for 5d6 binomial, etc.) directly.
   Try `T_est * k` for `k = 1..32` to handle the edge case where the
   smallest count is > 1.
2. **Fallback: `limit_denominator` walk.** For pathological distributions
   (or distributions with `T > 10^15`), walk denominator bounds 1e3..1e9
   and accept the first whose round-trip is within tight tolerance.

Bounded at `T = 10^15` for float-arithmetic safety. Distributions with
larger natural totals fall through to the fallback path with bloated but
proportionally-correct counts.

### AnyDice's empty-die-with-seq operator bugs (program 42aa4)

Probed 2026-05-06 via `notes/probe-seq-arith.txt` / `probe-seq-arith-results.txt`.
The probe walks all combinations of `{d{}, 0d6, 1d6, 2d6}` × `{1, 2, 3}` (seq) ×
`{+, -, *, /, &, |, ^}` × `{LHS, RHS}` to characterize AnyDice's empty-die handling.

Two distinct AnyDice bugs surfaced; we deliberately don't reproduce either.

**Bug 1: `d{} + seq` returns the seq as a discrete distribution.** AnyDice
special-cases this single operator/position combination: when LHS is empty die
and RHS is a sequence, AnyDice expands the seq per-element instead of
sum-coercing or propagating emptiness:

| input | AnyDice | our impl | "correct" bool/arith semantic |
|---|---|---|---|
| `d{} + {1, 2, 3}` | `{1: 33%, 2: 33%, 3: 33%}` | `{6: 100%}` | sum-coerce + treat d{} as 0 → 6 |
| `{1, 2, 3} + d{}` | `{6: 100%}` | `{6: 100%}` | sum-coerce + treat d{} as 0 → 6 |
| `d{} - {1, 2, 3}` | `{-6: 100%}` | `{-6: 100%}` | sum-coerce + treat d{} as 0 → -6 |
| `{1, 2, 3} - d{}` | `{6: 100%}` | `{6: 100%}` | sum-coerce + treat d{} as 0 → 6 |

`-` is consistent in both directions; only `+` has the LHS asymmetry.

**Bug 2: `seq | d{}` returns the sum-coerced seq instead of bool-OR with 0.**
AnyDice's `|` is otherwise consistent bool-OR (`{1, 2, 3} | 0d6` returns
`{1: 100%}` via `6 | 0 = 1`). Only the empty-die-RHS case breaks this -- looks
like AnyDice fails to substitute d{} as 0 on RHS for `|`:

| input | AnyDice | our impl | "correct" bool semantic |
|---|---|---|---|
| `d{} | 1` | `{1: 100%}` | `{1: 100%}` | 0 \| 1 = 1 |
| `1 | d{}` | `{1: 100%}` | `{1: 100%}` | 1 \| 0 = 1 |
| `d{} | {1, 2, 3}` | `{}` (empty propagates) | `{1: 100%}` | 0 \| 6 = 1 |
| `{1, 2, 3} | d{}` | `{6: 100%}` (sum-coerce, NOT bool-OR!) | `{1: 100%}` | 6 \| 0 = 1 |
| `d{} & {1, 2, 3}` | `{}` | `{}` | empty propagates |
| `{1, 2, 3} & d{}` | `{}` | `{}` | empty propagates |

`&` is symmetric (both sides propagate emptiness); `|` is asymmetric and
buggy in both directions.

**Our design**: `_EMPTY_DIE_AS_ZERO = {"+", "-", "|"}` and `_apply_arith` /
`_apply_bool` apply uniform "treat empty die as scalar 0" semantics for these
three operators in both positions. `*`, `/`, `^`, `&` propagate emptiness from
either side. This produces internally consistent semantics across the operator
matrix and matches AnyDice on all non-empty-die cases. The two bugs above are
on todo 35's annotation list.

## Things tried, outcomes

| Change | Outcome |
|--------|---------|
| `_compress_h` in `VarAssign` | 229 regressions (restored) |
| `_compress_h` in `LoopStmt` copy-back only | Fixed weight explosion in program 99248 (45-iter loop) |
| `_compress_h` in `_pool_h_select` | Fixed OOM on program 140338; no other programs affected |
| LCM normalization in `_expand_over_h`/`_expand_over_s` | Fixed programs 235 (L5R) and 2619 (nWoD) — mixed int/H returns |
| Loop copy-back: propagate ALL child vars (not just pre-existing) | Fixed programs 99475/76/78 — loop-defined variables not visible after loop |
| Dynamic scoping (`caller_env`) | Fixed program 25893 partially (runtime_error → value_mismatch) |

# Appendix

## From [PyDice](https://pdice.arkareem.com/)

Source repo: [Ar-Kareem/PythonDice](https://github.com/Ar-Kareem/PythonDice)

Translates this ...

    \ example code \
    output 1d20 named "Just D20"
    output 3 @ 4d20 named "3rd of 4D20"

    function: dmg D:n saveroll S:n savetarget T:n {
      if S >= T {
        result: D/2
      } else {
        result: D
      }
    }

    output [dmg 4d6 saveroll d20+4 savetarget 16] named "Lvl 4 Fireball, +4DEX vs 16DC"

... to this ...

    # example code
    output(roll(1, 20), named=f"Just D20")
    output((3 @ roll(4, 20)), named=f"3rd of 4D20")
    @anydice_casting()
    def dmg_X_saveroll_X_savetarget_X(D: T_N, S: T_N, T: T_N):
      if S >= T:
        return D // 2
      else:
        return D

    output(dmg_X_saveroll_X_savetarget_X(roll(4, 6), roll(20) + 4, 16), named=f"Lvl 4 Fireball, +4DEX vs 16DC")

From the [README](https://github.com/Ar-Kareem/PythonDice/#complex-example):

### Complex Example:

Let's try calculating the total damage of the following attack on a boss in an RPG:
- TO HIT: 1d20 + 7 against 22 AC (less than 22 is a miss. rolling a 20 is a CRITICAL so double the damage die)
- DAMAGE: 2d8 + 4 blunt damange
- \+ 1d4 thunder damage
- \+ 1d10 + 3 radiant damange (half damage if the target succeeds a 16 DC wisdom saving throw, boss has +5 wis saving throw)

```python
from dice_calc import roll, anydice_casting, T_N, T_S, T_D

# In anydice we have (:N, :S, and :D) which are (T_N, T_S, and T_D) in here
# read: https://anydice.com/docs/functions for more information
@anydice_casting()
def calculate(to_hit_roll: T_N, save_roll: T_N):  # type hinting as T_N REQUIRED!!!
    if to_hit_roll + 7 < 22:  # miss
        return 0
    is_crit = (to_hit_roll == 20)
    dmg_die_mult = 2 if is_crit else 1
    blung_dmg = roll(2 * dmg_die_mult, 8) + 4
    thund_dmg = roll(1 * dmg_die_mult, 4)
    radiant_dmg = roll(1 * dmg_die_mult, 10) + 3
    if save_roll + 5 >= 16:  # save success
        radiant_dmg = radiant_dmg // 2
    return blung_dmg + thund_dmg + radiant_dmg

X = calculate(roll(20), roll(20))

# plotting code
from matplotlib import pyplot as plt
vals, probs = zip(*X.get_vals_probs())
plt.bar(vals, probs); plt.xlabel('Damage'); plt.ylabel('Probability');
```

![png](https://github.com/Ar-Kareem/PythonDice/blob/master/README_files/./README_18_0.png)

Notice how we used the decorator `@anydice_casting` to use `if` conditions on dice inside of a custom function. Typehinting the input to `int` is required, the engine knows that you want to calculate the function many times based on all possible combinations of the input random variable.

The three valid typehints that the decorator `@anydice_casting` looks for are `: int`, `: Seq`, `: RV` which are equivalent to the 3 types `:n`, `:s`, and `:d` respectively in `anydice`. The casting done by `@anydice_casting` is exactly how casting is done in the `anydice` language. For more info on that please read the [documentation `functions -> Parameter types` in the `anydice` docs](https://anydice.com/docs/functions/) .

Note: `Seq` and `RV` are imported from `dice_calc.randvar`

### Observations

**The key insight is separable from the mechanism.**
`@anydice_casting()` shifts the "combinatorial expansion over outcomes" problem
out of the function body and into the call site.
The function body always operates on scalars, so Python's native `if`,
arithmetic, and control flow just work.
This is the same semantics our AST-walking interpreter needs to implement —
the machinery just lives in a different place (the eval loop's function call
handler rather than a Python decorator).

**`if` conditions are always scalar.**
AnyDice `if` requires its condition to resolve to an `int` at runtime (0 =
false, nonzero = true); using a die expression as a condition is a type error
in any context, including top-level.
Inside a function body, this is not a problem in practice because the call
handler has already coerced `:n` arguments to scalars before the body runs —
the `if` never sees a die.

**PyDice requires `exec` to run the generated code.**
Because it transpiles AnyDice to Python source strings, execution requires
`exec`.
This carries real costs: security exposure for untrusted programs, harder error
attribution (stack traces point into generated strings), and the indirection of
building valid Python source just to evaluate it immediately.
Our AST-walking approach gets the same coerce/iterate/combine semantics without
any code generation or `exec`.

**We already have everything needed.**
`Param.type` in our AST captures `:n`/`:s`/`:d` for every parameter.
The interpreter's function call handler can read those types and apply the same
expansion logic the decorator applies — coerce arguments by type, iterate over
outcome combinations for `:n` params backed by distributions, weight and combine
results into a new `H`.

----

# Design discussions (2026-04-27)

NOTE: most of the body of this file describes a prior interpreter that was
subsequently removed and rebuilt; the current implementation lives in
`dyce/anydyce/interpreter.py` (no underscore prefix; modules were renamed in a
2026-04-27 cleanup pass). Stale sections above (file paths, line counts,
corpus pass counts, `_compress_h`/`_dispatch_coercion` references) describe
the previous implementation. Treat the notes below as authoritative when they
conflict.

## Current implementation summary

Public API is unchanged: `dyce.anydyce.run(source) -> list[(name, H)]`.

Module layout after rename:

```
dyce/anydyce/
  __init__.py        public parse/run/unparse
  grammar.lark       Lark LALR(1) grammar
  ast_.py            AST dataclasses (suffix _ to avoid stdlib `ast`)
  builtins_.py       AnyDice builtins (suffix _ to avoid stdlib `builtins`)
  interpreter.py     tree-walking interpreter (~570 lines)
  transformer.py     Lark Transformer -> AST
  unparser.py        AST -> canonical source
  settings.py        runtime settings (position order, max depth, explode depth)
```

Test count: 305+ (`tests/anydyce/test_interpreter.py`); five type checkers
(mypy, pyright, ty, pyrefly) and ruff all clean.

`_Val` type alias unions `int | H[int] | P[int] | tuple[int,...] | str`.
P retains positional info needed by `@`-selection on multi-die rolls. Once a
P participates in arithmetic / comparisons / bool ops, dyce's `HableOpsMixin`
collapses it to H automatically. `_h_binop` and `_apply_cmp` are the only
sites that build outcome maps by hand; everywhere else flows through Python
operators and the collapse is implicit.

## H/P duality

Verified design after recent pass:

- `DiceUnary` (`d6`) returns bare H (single die has no positional info).
- `DiceBinOp` (`3d6`) returns P (multi-die pool).
- Arithmetic and comparisons consume H or P interchangeably; results are H.
- `@` requires P (or int / tuple) on the right; bare H on the right raises.

The defensive "bare H on right of `@`" branch we briefly added was removed
because no real program path produces a bare H in that position.

## Naming

- **AnyDice** -- the AnyDice-compatible variant we have today, in
  `dyce/anydyce/`. Accepts AnyDice programs, reproduces AnyDice's outputs
  (warts and all). Default name with no qualifier; "AnyDice Legacy" only
  when disambiguation is needed.
- **AnyDice NG** -- the new variant being designed, target package
  `dyce/anydyce_ng/`. Forked language with strict types, no implicit
  coercions, principled error handling. "NG" = Next Generation; it's a
  fork, not a deprecation of AnyDice.

Both ship as first-class siblings under `dyce.`; they share the parser,
AST, transformer, and unparser.

## (1) / (3) factoring (the "two-variant" architecture)

Reference for "the (1)/(3) factoring" mentioned earlier:

- **(1)** **AnyDice NG** -- a sibling interpreter in `dyce.anydyce_ng`.
  Same parser, same AST, same transformer, same unparser. Replacement
  `_apply_*` dispatch that drops AnyDice's surprising coercions.

- **(3)** Documented split between H (distribution) and P (pool) in the
  current AnyDice variant -- "keep both, document the rationale". This is
  what we have; the comment on `_Val` explains it.

(Earlier we sketched **(2)**, an AnyDice-to-dyce-Python *transpiler*: a new
`_codegen.py` plus a `dyce.anydyce_runtime` helper module containing the
operator dispatch. Whether (1) and (2) coexist is an open question; the
natural prerequisite is extracting the operator dispatch into a runtime
helper so both AnyDice NG and any codegen back-end can call it.)

The factoring summary:

| Variant | Reuses | New |
|---------|--------|-----|
| AnyDice NG (1) | grammar, AST, transformer, unparser | `dyce.anydyce_ng` with replacement `_apply_*` methods |
| Transpiler (2) | grammar, AST, transformer | `_codegen.py`; runtime helpers in `dyce.anydyce_runtime` |
| AnyDice (current) | (everything we have) | none |

## AnyDice NG coercion principles

Distilled from the 2026-04-27 discussion. These describe AnyDice NG, NOT
the current AnyDice interpreter.

1. **Operators don't coerce.** Sequences in arithmetic, comparisons, or
   boolean ops are an error. Users write `5 + sum({1,2,3})` explicitly. The
   AnyDice rule "compared to a number -> count, compared to a die -> sum,
   compared to a seq -> lex" is the single biggest source of confusion;
   replacing it with "sequences aren't operands" cuts it cleanly.

2. **Single die type, surface-wise.** AnyDice's user model is one die type
   ("a die is a die"). H/P is implementation-only and shouldn't leak into
   the language. Don't introduce an explicit "pool vs distribution"
   distinction at the language surface even though the implementation uses
   one. (User pushback on the original phrasing.)

3. **Sequence comparison is lex tuple compare, full stop.** `<seq> <cmp>
   <seq>` is the only shape where sequences appear in comparisons (per
   principle 1). Lex compare matches Python; transitive; total. As a
   consequence, "position order" should be lowest-to-highest internally,
   period -- no user-facing setting. Also: kill `#` and `@` where the right
   operand is a number (i.e. raise like `<die>` on the left of `@`).
   AnyDice's "digit-of-int" semantics for those is just a footgun.

4. **Empty-die handling -- open.** AnyDice silently returns `H({})` from many
   places (`+/-` "act as 0", `|` anomaly, recursion-depth exhaustion).
   dyce's defaults are stricter and more explicit. Compromise sketch:
   uniform propagation by default, with a `set "implicit return value"` knob
   for users coming from AnyDice who relied on `H({})` propagation
   heavily.

5. **Param types are constraints, not coercion shims.** `:n` requires a
   number; passing a die requires explicit expansion syntax at the call
   site (`[double *d6]` or similar). `:d` requires a die. `:s` requires a
   seq. No silent int->die wrap, no silent die->1-elem-seq wrap.
   Auto-expansion of `:n` over a die outcomes is nice and worth keeping,
   but only with explicit user opt-in at the call site.

6. **Function dispatch by exact pattern match, not definition order.**
   Param type annotations participate in dispatch (unlike AnyDice Legacy,
   where they don't). With principle 5's strict types and no coercion, the
   relevant cases for two same-shape definitions are:

   | Two definitions | NG behavior |
   |---|---|
   | `f X:n` then `f X:n` (same shape, same types) | redefinition; last wins, like any normal language |
   | `f X:n` then `f X:d` (same shape, disjoint types) | both coexist; dispatch by argument type. Each accepts arguments the other rejects, so no ambiguity. |
   | `f X:n` then `f X:?` (same shape, overlapping types) | register-time error: a number argument matches both, so the call is ambiguous |
   | `f X:?` then `f X:n` (specific defined later) | register-time error for the same reason -- definition order doesn't help |

   Plain redefinition (row 1) is allowed because there is no ambiguity to
   resolve. Disjoint overloads (row 2) coexist because strict types
   partition the input space. Overlapping types (rows 3-4) are the
   ambiguity case, and we error at registration time rather than picking
   silently.

   AnyDice Legacy collapses all four cases into "last definition with this
   shape replaces", because its types don't participate in dispatch.

## Grammar question (parsing strict vs permissive)

If we add AnyDice NG, **keep the grammar permissive and surface errors at
runtime**. Two reasons:

- **Legacy programs should parse and fail with descriptive errors.** A user
  pasting `5 + {1,2}` should see a TypeError saying `+ does not accept a
  sequence; use sum({1,2})`, not a parse error. The error message is the
  migration documentation.
- **Coercion rules are runtime concerns, not grammatical ones.** Coercion
  is "what types this operator accepts" -- semantic, not syntactic. Mixing
  it into the grammar would couple the parser to the type system and force
  us to ship two grammars for the two interpreters.

The architectural payoff is that both interpreters share the same
parse/AST/transformer/unparser. Fork point is the interpreter only.

## `:?` parameter type

Verified by user with program `0x433fa`: `:?` is the default / bare type.
Bare param `function: f X { ... }` and `function: f X:? { ... }` are
identical. Currently our grammar's `param_type` regex is `[nds]`, so we
reject `:?`. Cheapest parity fix: extend to `[nds?]` and treat `:?`
identically to a missing type in the AST (i.e. `Param.type = None`).
Defer until a real program needs it.

## AnyDice EBNF gaps (2026-04-27 review)

Reference: `/home/matt/dev/sandbox/anydice/anydice.com/ebnf.txt` (~80 lines,
informal).

Differences from our grammar:

- AnyDice has `:?` data type (wildcard). We don't. Identical to bare param
  in practice (verified by user); see above.
- AnyDice has a `legacy = 'legacy', string` value form. We don't. No real
  program uses it; ignored.
- AnyDice EBNF restricts `output ... named <string>` and
  `set <string> to <op|string>` to string literals. Our grammar accepts
  arbitrary expressions. We're strictly more permissive; harmless. User
  noted that narrowing `output ... named` to a string literal would be
  fine since strings have no operators (no concatenation needed). For
  `set ... to`, current behavior accepts arithmetic expressions that
  evaluate to int -- confirmed by user as desired (e.g. `set "max function
  depth" to 0 + {1..2}` should parse but raise at runtime since seq->int
  coercion is not auto).
- AnyDice's EBNF folds `else if` into nested `else <conditional block>`.
  We have an explicit `elseif` rule. Same accepted strings, different tree
  shape. Fine.

Mechanical check option: parse each program in
`helpers/anydice-programs.db` (~765 entries) through our parser and report
parse failures. Each failure is a real syntactic divergence.

We already have an indirect signal of this: `_canonicalize()` falls back to
returning the original program text when parsing fails, so any DB row where
`program == canonical` is either a parse failure or a program that already
happens to be in canonical form. For non-trivial programs the latter is
rare (the unparser strips comments and normalizes whitespace), so a query
like `SELECT program_id FROM programs WHERE program = canonical` is mostly
indicative. The `recanon` subcommand also implicitly tests parseability
across the whole DB. A purpose-built parse-only helper is still worth
adding eventually because it cleanly distinguishes "parse failed" from
"already canonical". Not urgent.

## AnyDice NG: modulo operator

AnyDice has no `%`. Users are forced to write `X - (X / 5) * 5`, which
combined with AnyDice's truncated-toward-zero division is a footgun for
negative numbers. AnyDice NG should add a sign-preserving `%` operator
(Python-style remainder, where `(-7) % 3 == 2`). Open question: should `/`
also become floor-division to match? Python does both consistently;
AnyDice's truncated `/` exists for parity with C-like languages. If we're
breaking other AnyDice conventions for sanity, breaking division too may
be worth it.

## Warnings handling

Open design item. AnyDice surfaces conditions like "the maximum function
depth was exceeded, results are truncated" as warnings the user sees in
addition to the result. We currently have no story for this -- truncation
silently returns `H({})` and propagates per the empty-die rules.

Proposed sketch:

- Define `AnyDiceWarning(UserWarning)` in `dyce.anydyce`.
- Interpreter calls `warnings.warn("...", AnyDiceWarning)` at guard points
  (recursion-depth exhaustion first; later: explode depth, any other
  truncation).
- Inside `run()`, use `warnings.catch_warnings()` with a filter that
  suppresses other `UserWarning`s from dyce's internals (e.g. the
  `@experimental` decorator) but lets `AnyDiceWarning` through.
- Users get warnings via standard Python machinery: `catch_warnings(record=
  True)` to capture, `-W error::dyce.anydyce.AnyDiceWarning` to promote.

Keeps the interface tiny, reuses stdlib mechanisms, and cleanly separates
"the AnyDice program produced a notable behavior" from "dyce internals
warned about something".

Not urgent; revisit when we have a concrete reason to surface a runtime
condition (recursion-depth truncation is the canonical first case).

## AnyDice NG: enumerate-and-aggregate via `expand`

Refinement of principle 5 (param types as constraints, not coercion shims).
The earlier sketch left a gap: if `:s` strictly requires a sequence, there
is no clean way to call `[top2 3d6]` -- the pool is not a sequence, and
banning the implicit coercion makes that call a type error.

The hybrid resolution: introduce an explicit `expand` construct that owns
the enumerate-and-aggregate semantic AnyDice currently bakes into param
expansion. Param types stay strict; iteration is expressed at the call
site.

Sketch:

```
function: top2 X:s { result: 1@X + 2@X }      # X must be a seq, period
[top2 {3,4,5}]                                # OK: literal seq
[top2 3d6]                                    # type error: pool != seq
expand X:s over 3d6 [top2 X]                  # explicit roll enumeration

function: double X:n { result: X * 2 }
[double 5]                                    # OK: literal number
[double d6]                                   # type error: die != number
expand X:n over d6 [double X]                 # explicit outcome enumeration
```

Rules:

- `expand X:n over <die-or-pool> EXPR` -- iterate distinct outcomes of the
  summed distribution, weighted by counts; bind `X` to each outcome (int);
  evaluate `EXPR` once per outcome; combine results into a weighted `H`.
- `expand X:s over <pool> EXPR` -- iterate possible rolls of the pool,
  weighted by multiplicities; bind `X` to each roll (sorted tuple);
  evaluate `EXPR` once per roll; combine results.

What this buys us:

- **Functions become pure.** No built-in expansion machinery in call
  dispatch. `:s`/`:n`/`:d` are pure type constraints; argument-vs-param
  type mismatch is a runtime error.
- **Function dispatch simplifies dramatically.** Exact type match; no
  coercion, no last-defined-wins; ambiguity (e.g. `f X:d` vs `f X:?`)
  resolves by most-specific (per principle 6).
- **One enumerate-and-aggregate rule, not three.** AnyDice has separate
  expansion semantics for `:n` over die, `:s` over die, `:s` over pool;
  in this model they're all the same construct keyed by the binding type
  annotation.

Cost: verbosity for the common case. AnyDice's `[top2 3d6]` becomes
`expand X:s over 3d6 [top2 X]`. Maybe 20 extra chars per call site that
iterates. Worth it for the semantic clarity.

Open design questions:

- Body shape: restrict to a single `[call_expr]`. Grammar:
  `expand_expr : "expand" param "over" expr "[" call_expr "]"`. Keeps
  `expand` from growing into a mini-language; users define a function
  for compound logic. Easy to relax later if proven restrictive.
- Interaction with `loop`. They're orthogonal: `loop` is
  sequential/deterministic over a known sequence; `expand` is
  parallel/probabilistic over a die or pool. Both keywords coexist.
- Higher-order use: `expand X over <thing> [some fn X another-arg]` works
  unchanged -- the call_expr is just an expression that happens to use
  `X`; multiple words and other args slot in normally.

Iteration mode by binding type:

- `expand X:n over POOL [...]` -- collapse pool to summed H (same auto-
  collapse dyce does at any operator boundary), iterate distinct outcomes.
- `expand X:n over DIE  [...]` -- iterate distinct outcomes of the die.
- `expand X:s over POOL [...]` -- iterate sorted rolls of the pool.
- `expand X:s over DIE  [...]` -- single die: iterate over each outcome
  with X bound to a 1-element tuple `(outcome,)`. (This matches AnyDice's
  current `:s` with a bare die, but explicit at the call site.)
- `expand X:d over ...`  -- error. `:d` has no meaningful iteration mode.
- `expand X:? over ...`  -- error. The wildcard fails to disambiguate
  outcome-iteration from roll-iteration; users must pick one.
- `expand X over ...`    -- error. The annotation is *required*, not
  optional. Without it, `expand` doesn't know which mode to apply.

(In other words: function-param annotations are optional sugar for
documentation/dispatch; `expand` annotations are load-bearing.)

## AnyDice NG: variables are untyped

A separate observation, but worth recording: with explicit conversions
everywhere, **variables themselves never need type annotations**. A
variable's type is whatever the last assignment puts there; subsequent
reads see that type. AnyDice already works this way (no `X:n: 5` -- only
`X: 5`).

The only places type annotations have meaning are:

1. **Function parameter types** (used for dispatch and call-site type
   checking against actual arg types).
2. **`expand` binding types** (used to select iteration mode).

Both are "how do I interpret the value at this boundary?" sites, not
"what type does this name remember?" sites. The grammar reflects that:
`param` is the only construct carrying a type annotation, and it's reused
for both function definitions and `expand` bindings.

## AnyDice NG: `if` truthiness rules

`if` accepts ONLY number-shaped conditions. Sequences are NOT sum-coerced.

- `int` -> falsy iff 0.
- seq (including empty seq) -> **TypeError** at evaluation time. Verified
  via program 42aac: `if {} { ... }` errors on AnyDice with "Boolean
  values can only be numbers, but you provided '{?}'". Sum-coercion does
  NOT happen in condition position even though it does in arithmetic
  contexts.
- dice (`H`, `P`) -> **TypeError** at evaluation time. Probabilistic
  conditions aren't deterministic, so the user must spell out their
  intent (e.g. `if (#{die}) > 0 { ... }` or `if (die-cmp) > 0 { ... }`).
- strings -> **parse error**. Strings are not first-class values in either
  Legacy or NG; they only appear as STRING terminals in `output ... named`
  and `set ... to`. The grammar should refuse STRING in condition position
  if practical.

This matches Legacy's documented behavior. Our `_is_truthy` previously
sum-coerced sequences; this was too permissive even for Legacy and has
been tightened to int-only.

The earlier "probabilistic NG" idea (where `if d6 { A } else { B }` would
weight body A by P(d6 truthy)) is rejected: not what Legacy does, not
syntactically intuitive, conflates an `if` with an `expand` over the die's
outcomes. If a user wants probabilistic branching, they should build it
explicitly with `expand` plus a function whose body returns A or B.
