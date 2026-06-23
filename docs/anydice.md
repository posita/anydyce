<!---
  Copyright other protections apply.
  Please see the accompanying LICENSE file for rights and restrictions governing use of this software.
  All rights not expressly waived or licensed are reserved.
  If that file is missing or appears to be modified from its original, then please contact the author before viewing or using this software in any capacity.

  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !!!!!!!!!!!!!!! IMPORTANT: READ THIS BEFORE EDITING! !!!!!!!!!!!!!!!
  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  Please keep each sentence on its own unwrapped line.
  It looks like crap in a text editor, but it has no effect on rendering, and it allows much more useful diffs.
  Thank you!
-->

# `anydyce`’s *Mostly*-Compatible AnyDice Interpreter

`anydyce` now includes an Open Source, pure Python, cleanroom implementation of Jasper Flick’s [AnyDice Dice Probability Calculator](https://anydice.com/).

An interactive version can be found here: [![Try the AnyDice-compatible playground](anydice-playground.svg)](../playground/)

You can also [host your own or run it locally](index.md#running-locally).

The `anydyce` interpreter strives to be a working replacement in all meaningful aspects, but it is ***not*** 100% compatible, favoring fundamental correctness over producing identical results.
Besides [detailing features](#features) and [enumerating goals](#conclusion), this document primarily focuses on two categories of behaviors:

1. **AnyDice idiosyncrasies**, meaning surprising or inconsistent behaviors that appear intended that the `anydyce` interpreter faithfully replicates; and
2. **Excluded AnyDice bugs**, meaning behaviors that are likely unintended defects, that the `anydyce` interpreter deliberately avoids.

It should be noted that until now, many of these behaviors weren’t well documented or widely understood, but were implicated in many of the real world programs examined during this effort.
Inconsistencies, both individually and collectively were unintuitive and difficult to remember, making non-trivial programs hard to author, reason about, and debug.
Also discovered were several latent “foot guns” likely to silently result in mathematical errors in real world programs.
Some foundation necessary to an analysis of AnyDice behaviors is present below, but familiarity with AnyDice’s documentation[^1] is helpful for gleaning a complete picture.

[^1]: See the “[Documentation](https://anydice.com/docs/)”, “[Function Library](https://anydice.com/docs/function-library/)”, and “[Articles](https://anydice.com/articles/)” sections of the AnyDice website.

## Features

The `anydyce` interpreter is primarily broken up into two major components:

1. A portable, pure Python back end that relies on [`dyce`](https://github.com/posita/dyce/) for computation; and
2. A user interface implemented in HTML, CSS, and plain JavaScript that uses [Plotly](https://plotly.com/) for visualizations and [Pyodide](https://pyodide.org/en/stable/) to run everything (including the Python interpreter) directly in-browser.

### No server required

The included web interface is loaded from a static site and runs in the user’s browser.
The only infrastructure needed to run a local instance is a simple web server (e.g., the one that ships with Python’s standard library: `python3 -m http.server 8000`).

### The URL ***is*** the program

Similar to other browser-based sandboxes and playgrounds, the included web interface allows programs to be preserved and shared solely by creating and copying a URL that encodes the entire program in the URL itself.
As long as you have access to the URL (e.g., via a bookmark), you have the program.
No reliance on accessing another’s database is needed.

### Loading programs saved to anydice.com by program IDs

The web interface allows loading of programs previously saved to AnyDice by way of a [publicly available partial program cache](https://github.com/posita/anydice-data) that was retrieved prior to [AnyDice being compromised](#background-purpose).
Be advised, however, that as of June, 2026, about 100,000 programs are still absent from the cache.

For any AnyDice URL containing a program ID, you can create an alternate URL using that same ID to load that program and run it with the `anydyce` interpreter.
For example, consider the URL [`https://anydice.com/program/18106`](https://anydice.com/program/18106).
You can run the same program by visiting [`https://posita.github.io/anydyce/latest/playground/#id=18106`](https://posita.github.io/anydyce/latest/playground/#id=18106).
Alternatively, you can [run your own copy locally](index.md#running-locally) and adapt the same pattern to the URL of your local web server (e.g.,`https://127.0.0.1:8000/playground/#id=18106`).

### No `float`s

The [`dyce` library](https://github.com/posita/dyce/)’s [`H` object](/dyce/latest/dyce/#dyce.H)s on which this interpreter is based do not use floating point arithmetic:

> `H` objects encode finite discrete probability distributions as integer counts without any denominator.

Truncations occur (when and how [can be tuned](#proprietary-extensions)), but `dyce` does not use typical primitives like 64-bit `int`s or `float`s.
As such, calculations are not subject to the same limitations and errors.
(See the [discussion on overflows below](#overflows).)

Instead, whenever any `H` object is created during execution (e.g., as the result of a operation like `20d20`) where the largest count would exceed the number of bits allowed by a contextual maximum, all counts are *quantized*.
More specifically, the least significant bits are truncated and all counts are rounded off such that they all fit within that maximum.
This does not eliminate errors, but it does allow authors to arbitrarily tune precision as needed (e.g., where performance takes priority).

### Proprietary extensions

In addition to supporting (almost[^2]) all AnyDice features, settings, library functions, etc., the `anydyce` interpreter provides two additional settings configurable via the `set ... to ...` syntax:

1. `"anydyce: calculation precision"` -
   This is either a non-negative integer indicating the maximum number of bits to allow for outcome counts within a die before quantization occurs, or one of: `"default"` (equivalent to `256`), `"low"` (`64`), `"medium"` (`256`), `"high"` (`1024`), and `"exact"` (`0`, meaning do not quantize).
   This setting affects computations that follow it and can be changed multiple times.
   Note that `"exact"` or `0` ***never*** quantizes, ***even where numbers and computations would exhaust all available resources***, so use those values with caution.
   (See [the note on performance below](#note-on-performance).)
2. `"anydyce: display precision"` -
   This is either a non-negative integer indicating how many decimal places to show when displaying results, or one of: `"default"` (equivalent to `2`), `"low"` (`0`), `"medium"` (`2`), `"high"` (`6`), and `"exact"` (`13`, which isn’t ***really*** exact, but it’s probably far more detailed than you’ll ever need).
   Only the most recent value is applied to all display outputs once a program completes.

```c
\ This illustrates quantization in action. Note especially the tails
  of the distribution. More detail can be seen in the text output. \
loop P over {4, 8} {
  set "anydyce: calculation precision" to P
  output 20d6 named "20d6 with computations quantized at [P] bits"
}
set "anydyce: calculation precision" to "exact"
output 20d6 named "20d6 without any quantization"
set "anydyce: display precision" to "exact"
```

Open in playground: [![Try the AnyDice-compatible playground](anydice-playground.svg)](../playground/#p=XCBUaGlzIGlsbHVzdHJhdGVzIHF1YW5pdHphdGlvbiBpbiBhY3Rpb24uIE5vdGUgZXNwZWNpYWxseSB0aGUgdGFpbHMKICBvZiB0aGUgZGlzdHJpYnV0aW9uLiBNb3JlIGRldGFpbCBjYW4gYmUgc2VlIGluIHRoZSB0ZXh0IG91dHB1dC4gXApsb29wIFAgb3ZlciB7NCwgOH0gewogIHNldCAiYW55ZHljZTogY2FsY3VsYXRpb24gcHJlY2lzaW9uIiB0byBQCiAgb3V0cHV0IDIwZDYgbmFtZWQgIjIwZDYgd2l0aCBjb21wdXRhdGlvbnMgcXVhbnRpemVkIGF0IFtQXSBiaXRzIgp9CnNldCAiYW55ZHljZTogY2FsY3VsYXRpb24gcHJlY2lzaW9uIiB0byAiZXhhY3QiCm91dHB1dCAyMGQ2IG5hbWVkICIyMGQ2IHdpdGhvdXQgYW55IHF1YW50aXphdGlvbiIKc2V0ICJhbnlkeWNlOiBkaXNwbGF5IHByZWNpc2lvbiIgdG8gImV4YWN0Igo)

[^2]: Deliberately omitted is AnyDice’s [“legacy” syntax](#legacy-programs).

### Portable Python implementation

The back-end can be incorporated into other projects via the [`anydyce.anydice`][anydyce.anydice] subpackage.

    >>> from anydyce.anydice import format_results, run
    >>> program = r"""
    ...     output 3d6
    ... """
    >>> results = run(program)
    >>> print(format_results(results))
    ==== output 1 ====
    avg |   10.50
    std |    2.96
      3 |   0.46% |
      4 |   1.39% |
      5 |   2.78% |#
      6 |   4.63% |##
      7 |   6.94% |###
      8 |   9.72% |####
      9 |  11.57% |#####
     10 |  12.50% |######
     11 |  12.50% |######
     12 |  11.57% |#####
     13 |   9.72% |####
     14 |   6.94% |###
     15 |   4.63% |##
     16 |   2.78% |#
     17 |   1.39% |
     18 |   0.46% |

### A note on performance

In some cases, the `anydyce` interpreter outperforms anydice.com.
This can be hard to gauge, since the `anydyce` interpreter runs in the user’s browser, and is subject to the limitations of that execution environment.
For example, on modest hardware, the following program completes in under 2s in the `anydyce` interpreter, but times out before producing results on anydice.com.

```c
output 300@(1000d100)
```

Open in playground: [![Try the AnyDice-compatible playground](anydice-playground.svg)](../playground/#p=b3V0cHV0IDMwMEAoMTAwMGQxMDApCg)

In other cases, the `anydyce` interpreter under-performs anydice.com, sometimes by an order of magnitude or more (e.g., programs [`26da9`](../playground/#id=26da9) and [`286e0`](../playground/#id=286e0)).
This is usually because the `anydyce` interpreter attempts to be unhelpfully precise with math, which becomes ***very*** laborious as integers become huge.
That can often be mitigated by selecting a [lower quantization threshold](#proprietary-extensions).
By way of illustration, trying to run programs [`183b0`](../playground/#id=183b0) or [`282d6`](../playground/#id=282d6) with [`"anydyce: calculation precision"` set to `"exact"`](#proprietary-extensions) will likely fail to complete within several minutes (if ever).

The `anydyce` interpreter and the underlying [`dyce` library](https://github.com/posita/dyce/) on which it is built are very much works in progress, and performance improvements are a high priority item on their road maps, so this is likely to improve as time goes on.

## Background &amp; purpose

AnyDice appears to have been around in some form or another since 2009, receiving a handful of updates between then and 2026.
It is free to use by anyone, likely funded entirely by the author who invites others to offset costs through donations.
It has amassed over a quarter million “saved” programs[^3] during its tenure.
It enjoys substantial popularity among loyal users, many of whom post on [rpg.stackexchange.com](https://rpg.stackexchange.com/questions/tagged/anydice) providing volunteer education and support.

Its most typical use involves typing or pasting a program conforming to a [proprietary syntax](https://anydice.com/docs/) into a text field on a [hosted website](https://anydice.com/).
The user submits the program by activating a “Calculate” button in the interface, which transmits the program text via HTTP POST to a [PHP handler](https://anydice.com/calculator_limited.php).
The returned JSON results are then interpreted and displayed for the user.
All interpretation and computation appears to be performed server-side.

AnyDice remains closed source, and its author seldom makes updates.
The author provides a [human readable version of the AnyDice grammar](http://anydice.com/ebnf.txt), but the actual implementation of its parser and interpreter are not publicly available.
While AnyDice provides documentation, it does not constitute a complete specification from which to replicate or validate its interpreter.
Many meaningful details important to more sophisticated computations are left to the discovery of the user.

In early 2026, AnyDice became completely unavailable for a week or two due to a system compromise.
The site was eventually restored, but programs saved to its proprietary database by users over the preceding several weeks were permanently lost.

The purpose of this effort is to provide a publicly-accessible reference implementation to avoid future loss of user investment.
For convenience, a usable instance resides at [`https://posita.github.io/anydyce/latest/playground/`](https://posita.github.io/anydyce/latest/playground/).
However, merely relying on a single alternate site is insufficient, as no site guarantees access in perpetuity.
Therefore, users are encouraged to clone [this implementation’s source code](https://github.com/posita/anydyce) and run or host instances of their own.

The [AnyDice program cache](https://github.com/posita/anydice-data) is intended to preserve intellectual property of program authors who assigned no royalties or rights to their programs, and who reasonably relied on the ongoing availability of an interpreter and storage mechanism to preserve each program’s accessibility and value.
If you are the author of a particular program in the cache that you want removed, please [file an issue](https://github.com/posita/anydice-data/issues).

Accesses required to create the cache were rate limited and consistent with AnyDice’s longstanding availability and encouraged use.
anydice.com implicitly permits anyone anywhere in the world to: visit the site; create and execute programs; save programs and share links to those programs with others; and use links to retrieve saved programs for examination, execution, illustration, etc.
As of this writing, no limitations are presented or appear to be enforced.

[^3]: At a user’s request, AnyDice has ability to save a program in its own proprietary, server-side database, providing a link with a hexadecimal ID which can later be used to load the same program.
      As of this writing, AnyDice’s ability to save new programs or retrieve existing ones seems to be offline.
      The highest program ID known to this author prior to this reduction in functionality was [`4327d`](../playground/#id=4327d).

## Reverse-engineering methodology

AnyDice is a closed source, remote execution environment without a complete specification.
Based on the available documentation, an initial [Lark grammar](https://lark-parser.readthedocs.io/en/latest/grammar.html) was created along with a transformer for generating an AST and corresponding interpreter.
While the documentation was a helpful starting point, it was fairly high level, so claims and implications had to be validated, and additional detail needed to be surfaced.

The general workflow to iterate toward a working implementation was as follows:

1. Form a hypothesis about a particular aspect of the AnyDice interpreter (e.g., structure or contextual behavior);
2. Design a probe (program) whose results would surface details of that particular aspect;
3. Execute the probe with AnyDice, interpret the results, refining this implementation as necessary; and, finally,
4. Validate this implementation produces similar results of the most recent probe as well as all prior probes.[^4]

Additionally, periodic comparison of the `anydyce` interpreter’s results with AnyDice’s across the entire corpus of unique[^5] saved programs surfaced additional details and nuances not identified by the above loop.
While 100% completeness is not guaranteed, based on experimentation and the behavior observed by processing that corpus, the `anydyce` interpreter should be appropriate for most uses.
In some cases, the `anydyce` interpreter supersedes AnyDice’s where AnyDice’s behavioral inconsistencies or bugs produce incorrect results.

[^4]: Validation probes were captured as unit tests, important for avoiding regressions as the `anydyce` interpreter evolved.

[^5]: AnyDice’s save functionality implements a rudimentary de-duplication filter.
      Where a user requests a program be saved that is byte-for-byte identical to a prior saved program, AnyDice often provides a link with the ID of the previously saved program.
      This still affords duplication where, e.g., the only difference is whitespace use or comment text.
      Two programs were considered equivalent if they resulted in the same AST from the parser and transformer.
      De-duping based on AST resulted in a corpus just shy of 160,000 distinct programs.

      As an aside, some of those programs mirrored our own probes (e.g., AnyDice program [`39567`](../playground/#id=39567) saved by the author of [PythonDice](https://github.com/Ar-Kareem/PythonDice/)), suggesting areas where users tripped over unintuitive “hot spots” of the interpreter, surfacing and resolving questions likely very similar to our own.

### Prior art

- [PyDice](https://pdice.arkareem.com/) is a pure Python implementation of an AnyDice interpreter that both interprets AnyDice programs as well as transpiles them into [PythonDice](https://github.com/Ar-Kareem/PythonDice/) Python code (which is pretty darn cool)
- [anydice.js](https://github.com/dlom/anydice) claims to provide a low level interface for retrieving results from AnyDice’s interpreter for use in JavaScript programs (untested)
- [anydieparser](https://www.npmjs.com/package/anydieparser) claims to provide an AnyDice interpreter in JavaScript (untested)
- [anydice](https://git.paco.to/nick/anydice) claims to provide an AnyDice interpreter implemented in C and Rust (untested)

## Notes on the anydice.com implementation

Some basics foundationally necessary to a discussion of AnyDice are presented below, but familiarity with AnyDice’s documentation[^1] is helpful for gleaning a complete picture.

### Types: numbers, sequences of numbers, and dice whose faces are numbers

AnyDice programs operate on three distinct object types:

1. Integers (which AnyDice calls “numbers”)
2. Sequences of numbers
3. Dice whose faces are numbers
    - Depending on the context, this can mean a pool of one or more dice, a single die, or the “[empty die](#the-empty-die-d)”

Objects are ***immutable***, but [variables](#variables) can be reassigned, including for derivative construction.
Types can be implicitly coerced, collapsed, or expanded, depending on the context, as we’ll explore.
Floating point numbers can be presented in output data, and double-quoted strings are used for interpreter configuration and labeling outputs, but AnyDice programs do not support arbitrary use or manipulation of floating point numbers or strings.

The syntax for numbers is straightforward: `0`, `1`, `+100`, `-273`, etc.

The syntax for sequences are braces containing lists of numbers, inclusive ranges of numbers, subsequences, or repetitions of numbers or subsequences, all of which are expanded and flattened: `{-3..-1:2, {4..6, {7, 8}:3}}` is equivalent to `{-3, -2, -1, -3, -2, -1, 4, 5, 6, 7, 8, 7, 8, 7, 8}`.
Order is preserved, as illustrated by the following program:

```c
S: {-3..-1:2, {4..6, {7, 8}:3}}         \ assign the expanded and flattened sequence to S \
loop N over {1..#S} {                   \ loop over values in a contiguous range from 1, to the length of S, inclusive, assigning each value to N \
  output N@S named "S at position [N]"  \ output the value of S at position N for each iteration of the loop \
}
```

Open in playground: [![Try the AnyDice-compatible playground](anydice-playground.svg)](../playground/#p=Uzogey0zLi4tMToyLCB7NC4uNiwgezcsIDh9OjN9fSAgICAgICAgIFwgYXNzaWduIHRoZSBleHBhbmRlZCBhbmQgZmxhdHRlbmVkIHNlcXVlbmNlIHRvIFMgXApsb29wIE4gb3ZlciB7MS4uI1N9IHsgICAgICAgICAgICAgICAgICAgXCBsb29wIG92ZXIgdmFsdWVzIGluIGEgY29udGlndW91cyByYW5nZSBmcm9tIDEsIHRvIHRoZSBsZW5ndGggb2YgUywgaW5jbHVzaXZlLCBhc3NpZ25pbmcgZWFjaCB2YWx1ZSB0byBOIFwKICBvdXRwdXQgTkBTIG5hbWVkICJTIGF0IHBvc2l0aW9uIFtOXSIgIFwgb3V0cHV0IHRoZSB2YWx1ZSBvZiBTIGF0IHBvc2l0aW9uIE4gZm9yIGVhY2ggaXRlcmF0aW9uIG9mIHRoZSBsb29wIFwKfQo)

Dice are created with the `d` operator, which has both unary and binary forms.
More complicated forms are explored later, but the simplest forms are `d<num>`, `d<seq>`, `<num>d<num>`, and `<num>d<seq>`.
The first and second (unary) forms create a single die.
The third and forth (binary) forms create a pool of like dice.

Where `<num>` is positive, `d<num>` is shorthand for `d{1..<num>}`.
Where `<num>` is negative, it is shorthand for `d{<num>..-1}`.
Where `<num>` is zero, it is shorthand for `d{0}`, which is a single-sided die whose sole face is `0`.
Note, this notation deviates from [`dyce`](https://github.com/posita/dyce/), where `dyce.d.d0` or `H(0)` means the [empty die](#the-empty-die-d).

Weighted dice are constructed by providing an appropriately-constructed sequence for the right-hand operand.
The expression `d{1, 2, 3, 1, 2, 1}` creates a six-sided die where three faces are `1`, two faces are `2`, and one face is `3`.

In binary form, the left side operand provides the number of dice in the pool.
For example, `2d6` creates a pool of two six-sided dice.

#### The empty die - `d{}`

The empty die is a die with zero faces.
In AnyDice, it deserves special attention because it is fraught with inconsistencies, which are called out below.
(See [this](#certain-operators-and-the-empty-die), [this](#dice-pool-sizes), and [this](#phantom-mass).)

#### On ordering

AnyDice exposes a `"position order"` setting that takes one of `"lowest first"` and `"highest first"` (the default).
This ordering ***only*** affects the order of sequences representing rolls from pools during [expansion](#functions-variable-scope-type-coercion-and-type-expansion) as well as the order in which outcomes appear in those rolls during each expansion call.
Rolls are not repeated during expansion.

For example, for highest first, rolls enumerated from a pool `2d3` would be: `{3, 3}`, `{3, 2}`, `{3, 1}`, `{2, 2}`, `{2, 1}`, `{1, 1}`.
For lowest first, they would be: `{1, 1}`, `{1, 2}`, `{1, 3}`, `{2, 2}`, `{2, 3}`, `{3, 3}`.

Order in sequences is preserved, meaning `output 2@{3, 5, 1}` yields `5`.
Order of the outcomes of a single die are always lowest-to-highest.
Where expansion occurs over multiple parameters, ordering is even more subtle, as [discussed below](#modifications-to-some-expanded-parameters-are-durable-across-expansion-calls), as illustrated by the following program:

```c
set "position order" to "highest first"
N: 0
function: N_FROM_D:n S_FROM_P:s {
  N: N + 1
  result: N_FROM_D * 10 ^ (N - 1) + 1@S_FROM_P * 10 ^ N + 2@S_FROM_P * 10 ^ (N + 1)
}
output [2d3 2d3]
```

Open in playground: [![Try the AnyDice-compatible playground](anydice-playground.svg)](../playground/#p=c2V0ICJwb3NpdGlvbiBvcmRlciIgdG8gImhpZ2hlc3QgZmlyc3QiCk46IDAKZnVuY3Rpb246IE5fRlJPTV9EOm4gU19GUk9NX1A6cyB7CiAgTjogTiArIDEKICByZXN1bHQ6IE5fRlJPTV9EICogMTAgXiAoTiAtIDEpICsgMUBTX0ZST01fUCAqIDEwIF4gTiArIDJAU19GUk9NX1AgKiAxMCBeIChOICsgMSkKfQpvdXRwdXQgWzJkMyAyZDJd)

The `anydyce` interpreter faithfully reproduces these various ordering behaviors.

### Variables

Variables have uppercase letter names, optionally with underscores.
Digits are not allowed.
In AnyDice, variables are dynamically typed, which means that a variable’s type is determined by the object it points to.
After an assignment `A: 1`, `A` points to the number `1`.
If one later reassigns `A: {}`, `A` then points to the empty sequence.

With the exception of two very strange behaviors described below that are deliberately not reproduced by the `anydyce` interpreter, AnyDice objects are ***immutable***, and variables behave as pointers to those immutable objects.
This is illustrated by the following program:

```c
I: 1       \ I points to a number object with the value 1 \
J: I       \ J points to the same number object as I \
I: {3..5}  \ I now points to a new sequence object containing the values 3, 4, and 5 \
output J   \ J still points to the number object with the value 1 \
```

Open in playground: [![Try the AnyDice-compatible playground](anydice-playground.svg)](../playground/#p=STogMSAgICAgICBcIEkgcG9pbnRzIHRvIGEgbnVtYmVyIG9iamVjdCB3aXRoIHRoZSB2YWx1ZSAxIFwKSjogSSAgICAgICBcIEogcG9pbnRzIHRvIHRoZSBzYW1lIG51bWJlciBvYmplY3QgYXMgSSBcCkk6IHszLi41fSAgXCBJIG5vdyBwb2ludHMgdG8gYSBuZXcgc2VxdWVuY2Ugb2JqZWN0IGNvbnRhaW5pbmcgdGhlIHZhbHVlcyAzLCA0LCBhbmQgNSBcCm91dHB1dCBKICAgXCBKIHN0aWxsIHBvaW50cyB0byB0aGUgbnVtYmVyIG9iamVjdCB3aXRoIHRoZSB2YWx1ZSAxIFwK)

### Operators

Similar to other programming languages, AnyDice provides:

- Binary arithmetic operators `+`, `-`, `*`, `/`, and `^` (exponential);
    - Note, however, the absence of a modulo operator
- Binary boolean[^6] operators `&` (boolean and) and `|` (boolean or);
- Binary comparison operators `=`, `!=`, `<`, `<=`, `>=`, and `>`;
- A unary arithmetic negation operator `-`; and
- A unary boolean negation operator `!` (boolean not).

!!! warning "`+` is a no-op, but `-` is not"

    AnyDice allows for a unary positive `+` in its syntax, but treats it as a no-op.
    This is subtle but important as we’ll see, because `-` ***can*** trigger a type collapse, while `+` never does.

In addition, AnyDice provides domain-specific operators:

- A unary die operator `d` and binary pool operator `d` as introduced above;
- A binary `@` position selection operator; and
- A unary `#` length or size operator.

The `@` and `#` operators mean different things depending on their operands and global settings, as [described in AnyDice’s documentation](https://anydice.com/docs/introspection/).

[^6]: “Boolean” in this context means an operator that evaluates each operand as falsy (the number zero) or truthy (a number other than zero), and which resolves to either `0` or `1`.

#### Precedence

Operator precedence is as follows:

| Level | Operators | Associativity |
|---|---|---|
| 1 **(loosest)** | `&`, `|` (boolean and/or) | left, equal precedence |
| 2 | `=`, `!=`, `<`, `<=`, `>`, `>=` (comparisons) | left |
| 3 | `+`, `-` (binary additive) | left |
| 4 | `*`, `/` (multiplicative) | left |
| 5 | `^` (exponentiation) | left |
| 6 | `@` (position selection) | left |
| 7 | `d` (binary dice) | left |
| 8 | `#`, `-`, `+`, `!`, `d` (all prefix unaries) | right, all at same level |
| 9 **(tightest)** | atoms: NUMBER, UPPERNAME, (expr), {...}, [call] | — |

!!! warning "Order precedence is atypical"

    Note that, unlike other programming languages, boolean operators `&` and `|` share precedence, so `A & B | C` is ***not*** equivalent to `C | A & B`.
    Also note that, despite `@` having a lower precedence than `d`, the precedence of `#` supersedes `d`’s.
    This means that `2@3d6` will intuitively select the middle die when rolling a pool of three six-sided dice without the use of additional parentheses, but `#20d6` will rarely provide what is intended, as authors almost always mean `#(20d6)`, not `(#20)d6`, which is how `#20d6` is interpreted.

#### Operand interpretation and collapse

For the most part, arithmetic operators behave as expected, with some notable exceptions.
These frustrate reliance on mathematical equivalence, or even consistency among operator behavior.

Arithmetic and boolean operators convert sequence operands to numbers by summing the sequence’s members.
The expression `{1, 2, 3} - {}` becomes `6 - 0`, or `6`.
The expression `d6 - {4, 5, 6}` becomes `d6 - 15`.
This is also true of the left-hand operand of the `d` operator.
The expression `{1, 2, 3}d{2, 4, 6}` becomes `6d{2, 4, 6}`, or a pool of 6 dice, each with three faces, `2`, `4`, and `6`.

!!! warning "`<num> / 0` is ***always*** `0`, even though `{0}^-1` is `-9223372036854776000`"

    A number divided by `0` is `0`, ***even if the dividend is also `0`***.

    Also, where the base is a sequence or die, AnyDice ***mostly*** produces anticipated results.
    For example, `{-1} ^ -2` resolves to `1`.

    But when the base ***collapses*** to the number `0` and the exponent is a negative number, AnyDice resolves the expression as `-9223372036854776000` (or `-0x80000000000000c0`).
    The expression `d{-2, -1, 0, 1, 2} ^ -2` resolves to `d{0, 1, -9223372036854776000, 1, 0}`.
    The large negative number was perhaps intended a sentinel value of some kind, but it remains inconsistent with AnyDice’s divide-by-zero behavior.
    The `anydyce` interpreter preserves the sentinel behavior with a zero base and negative exponent, so the expression `0^-1` resolves to `-9223372036854776000`.

!!! bug "`<num>^-1` is an error, even though `<seq>^-1` is not"

    Confusingly, a negative exponent in AnyDice results in an error where the base is a number.
    The `anydyce` interpreter resolves negative exponents with number bases consistently with other values as well as integer division that truncates toward zero.
    The expression `(-1)^-1` resolves to `-1`, `(-1)^-2` resolves to `1`, etc.

Unary `-` collapses sequences into numbers.
As mentioned above, unary `+`, acts as a no-op.
This presents an asymmetry where `-{1..4}` resolves to `-10`, while `+{1..4}` resolves to `{1..4}`.

!!! bug "`<non-empty-die> <= <seq>` is broken"

    On anydice.com, `output d8 <= {1,2}` is treated as equivalent to `output d8 > {1,2}` rather than `output {1,2} >= d8`.
    Further, a comparison with `<=` always resolves to `1` where the left-hand operand is a non-empty die and the right-hand operand is the empty sequence (e.g., `d{-1000} <= {}`).
    The `anydyce` interpreter deliberately avoids these behaviors, instead treating `<=` comparisons consistently with others.

Where `d`’s left-hand operand resolves to a negative number, the expression is treated as if the negative applies to the right-hand operand.
In other words, `-<num>d<expr>` is treated as `<num>d(-(<expr>))`.
In fact, `(-N)dX`, `Nd(-X)`, and `-(NdX)` are generally equivalent.
Where `d`’s left-hand operand resolves to `0`, the result is `d0`, except where the right-hand operand resolves to `d{}`, [discussed below](#certain-operators-and-the-empty-die).
The expression `0d1000` resolves to `d0`.

!!! warning "`<die>d<die>` probably doesn’t do what you think or want"

    In addition to the basic forms above, the binary `d` operator also accepts a die as its left-hand operator.
    To figure out what this does, it is important to understand that the `d` operator is basically equivalent to:

    ```c
    function: roll N:n of the die D:d { result: NdD }
    output [roll 4 of the die d3]                       named "same as output 4d3"
    output [roll d2 of the die d3]                      named "same as output d2d3"
    output [roll 2d4 of the die d3]                     named "same as output 2d4d3"
    output [roll [roll d2 of the die d4] of the die d3] named "same as output d2d4d3"
    output [roll 2 of the die 4d3]                      named "same as output 2d(4d3)"
    output [roll d2 of the die 4d3]                     named "same as output d2d(4d3)"
    ```

    Open in playground: [![Try the AnyDice-compatible playground](anydice-playground.svg)](../playground/#p=ZnVuY3Rpb246IHJvbGwgTjpuIG9mIHRoZSBkaWUgRDpkIHsgcmVzdWx0OiBOZEQgfQpvdXRwdXQgW3JvbGwgNCBvZiB0aGUgZGllIGQzXSAgICAgICAgICAgICAgICAgICAgICAgbmFtZWQgInNhbWUgYXMgb3V0cHV0IDRkMyIKb3V0cHV0IFtyb2xsIGQyIG9mIHRoZSBkaWUgZDNdICAgICAgICAgICAgICAgICAgICAgIG5hbWVkICJzYW1lIGFzIG91dHB1dCBkMmQzIgpvdXRwdXQgW3JvbGwgMmQ0IG9mIHRoZSBkaWUgZDNdICAgICAgICAgICAgICAgICAgICAgbmFtZWQgInNhbWUgYXMgb3V0cHV0IDJkNGQzIgpvdXRwdXQgW3JvbGwgW3JvbGwgZDIgb2YgdGhlIGRpZSBkNF0gb2YgdGhlIGRpZSBkM10gbmFtZWQgInNhbWUgYXMgb3V0cHV0IGQyZDRkMyIKb3V0cHV0IFtyb2xsIDIgb2YgdGhlIGRpZSA0ZDNdICAgICAgICAgICAgICAgICAgICAgIG5hbWVkICJzYW1lIGFzIG91dHB1dCAyZCg0ZDMpIgpvdXRwdXQgW3JvbGwgZDIgb2YgdGhlIGRpZSA0ZDNdICAgICAgICAgICAgICAgICAgICAgbmFtZWQgInNhbWUgYXMgb3V0cHV0IGQyZCg0ZDMpIgo)

    In lay terms, where the left-hand operand is a die, this means, “roll a first die, then whatever number comes up, roll that many of a second die, then collapse the whole thing down into a single die.”
    This isn’t incredibly useful in practice, and is often the source of confusion.
    Many authors try this notation as a flawed means to create heterogeneous pools (i.e., pools of dice of different kinds).

Note that a left-hand sequence is ***not*** collapsed with the `@` operator.
The expression `{2, 3}@{6, 5, 4, 3}` selects the second value `5` and third value `4` from the right-hand sequence, ***then*** collapses (sums) those selected values as `9`.
The expression `{2, 3}@(4d6)` enumerates all unique weighted rolls from four six-sided dice and sums the second and third highest values from those rolls.
The result is a single die with those weighted sums.

Pools collapse to a single die when involved in arithmetic or comparison operations.
The expression `#(2d6)` resolves to `2` where `#(2d6 + 0)`, `#(2d6 | 0)`, `#(2d6 != 7)` all resolve to `1`.
Unary `-` does ***not*** collapse pools like it does with sequences.
The expression `#(-(2d6))` also resolves to `2`.

Unary `!` resolves to a `1` if its operand collapses to zero (e.g., `{}`, `50d0`, etc.).

#### Certain operators and the empty die

Typically, set convolution involving the empty set produces the empty set.
Where A = ∅ or B = ∅, the Cartesian product would be A × B = ∅.
Therefore, an arithmetic comprehension would also produce no elements.
E.g.: A ⊕ B = ∅ where A = ∅ or B = ∅.
AnyDice follows this convention, but only ***some*** of the time, and inconsistently even then.

!!! warning "Additive operators treat `d{}` differently that others"

    With ***additive*** operators `+`, `-`, and `|`, if either the left-hand operand or the right-hand operand (but not both) resolves to the empty die, AnyDice converts it to the number `0`.
    The expressions `4 + d{}`, `d{} - 6`, and `d{} | 1` all behave as if `d{}` were `0`.
    The general exception to this exception is that AnyDice always produces `d{}` if both operands are `d{}`, meaning `d{} - d{}` is not `0`, as one might expect, but `d{}`.

    This can lead to some ***very*** subtle bugs.
    We’ve observed cases where, e.g., `result: [func one] + [func two]` hits a recursion cap from one side, treating the result as `0 + d{} = 0`.
    This results in leaking a spurious `0` into the parent distribution.

    This is visible with the following program:

    ```c
    function: delve N:n {
      if N <= 0 { result: 123 } \ Always return 123 at the bottom \
      result: [delve N - 1]
    }
    function: delve both M:n N:n {
      result: [delve M] + [delve N]  \ Does this return d{}, 123, or 246? It depends! \
    }
    function: delve among M:n N:n {
      result: [delve both M M] + [delve both M N] + [delve both N M] + [delve both N N]
    }
    M: 3 N: 3
    output [delve among M N] named "delve among [M] [N]"
    M: 3 N: 10
    output [delve among M N] named "delve among [M] [N]"
    M: 10 N: 10
    output [delve among M N] named "delve among [M] [N]"
    ```

   Open in playground: [![Try the AnyDice-compatible playground](anydice-playground.svg)](../playground/#p=ZnVuY3Rpb246IGRlbHZlIE46biB7CiAgaWYgTiA8PSAwIHsgcmVzdWx0OiAxMjMgfSBcIEFsd2F5cyByZXR1cm4gMTIzIGF0IHRoZSBib3R0b20gXAogIHJlc3VsdDogW2RlbHZlIE4gLSAxXQp9CmZ1bmN0aW9uOiBkZWx2ZSBib3RoIE06biBOOm4gewogIHJlc3VsdDogW2RlbHZlIE1dICsgW2RlbHZlIE5dICBcIERvZXMgdGhpcyByZXR1cm4gZHt9LCAxMjMsIG9yIDI0Nj8gSXQgZGVwZW5kcyEgXAp9CmZ1bmN0aW9uOiBkZWx2ZSBhbW9uZyBNOm4gTjpuIHsKICByZXN1bHQ6IFtkZWx2ZSBib3RoIE0gTV0gKyBbZGVsdmUgYm90aCBNIE5dICsgW2RlbHZlIGJvdGggTiBNXSArIFtkZWx2ZSBib3RoIE4gTl0KfQpNOiAzIE46IDMKb3V0cHV0IFtkZWx2ZSBhbW9uZyBNIE5dIG5hbWVkICJkZWx2ZSBhbW9uZyBbTV0gW05dIgpNOiAzIE46IDEwCm91dHB1dCBbZGVsdmUgYW1vbmcgTSBOXSBuYW1lZCAiZGVsdmUgYW1vbmcgW01dIFtOXSIKTTogMTAgTjogMTAKb3V0cHV0IFtkZWx2ZSBhbW9uZyBNIE5dIG5hbWVkICJkZWx2ZSBhbW9uZyBbTV0gW05dIgo)

   A much more subtle version of this issue can be found when comparing the second output of [`https://anydice.com/program/1065f`](https://anydice.com/program/1065f) to that [computed by the `anydyce` interpreter](../playground/#id=1065f).
   (See also the section on [“phantom” mass](#phantom-mass).)
   At first glance, the distributions look similar, but a careful inspection will reveal that AnyDice’s results do not sum to 100%, and the values are slightly off.

   Detecting, much less working around this computation error in a real world program is extremely difficult.

!!! bug "`d{} + {}` does not equal `{} + d{}`, even though `d{} - {}` equals `{} - d{}`"

    The ***specific*** exception to this exception is that AnyDice resolves `d{} + {}` and `d{} | {}` specifically to `d{}`, even though `{} + d{}`, `{} | d{}`, `d{} - {}`, and `{} - d{}` all resolve to `0`.
    The `anydyce` interpreter does not reproduce this inconsistency.

Operations involving ***multiplicative*** and ***comparative*** operators, `*`, `/`, `^`, `&`, `=`, `!=`, `<`, `<=`, `>=`, and `>` follow set convolution conventions.
The expressions `d{} * 1`, `1 / d{}`, `8 ^ d{}`, `d{} & 8`, etc. all resolve to `d{}`.
Likewise, where the binary `d` operator’s left-hand or right-hand operand resolves to `d{}`, the result is `d{}`, irrespective of the value of the other operand.
The expression `1000d{}` resolves to `d{}`.
The unary expressions `-d{}` and `!d{}` also resolve to the empty die.

#### Dice pool sizes

The `#` operator reveals the number of dice in a pool.
Some results are perplexing, however.

For some reason, pools with zero dice (e.g., `0d100`) are treated as `1d0`.
So `#(0d0)` is oddly `1`.

Pools where either the left-hand or right-hand operand is the empty die generally collapse to the empty die.
Simple pools involving the empty die as the right-hand operand are of size `0`.
For example, `#(4d{})` is `0`
However, where the left-hand operand is a die, the size of pools involving the empty die perplexingly becomes `1`.
So `#(d100d{})`, `#(d{}d100)`, and `#(d{}d{})` are all `1`.

This is where our implementation of [`<die>d<die>` as a function above](#operand-interpretation-and-collapse) breaks down.
While it produces equivalent ***outputs***, `#([roll d{} of the die d{}])` yields `0`, not `1`.

In its current implementation, the `anydyce` interpreter bends over backwards to reproduce these size inconsistencies for compatibility.
However, it’s quite possible aspects of these behaviors are bugs with anydyce.com, perhaps contributing to things like [“phantom” mass](#phantom-mass).
In the future, the `anydyce` interpreter may diverge from anydice.com by implementing something more coherent.

### Functions, variable scope, type coercion, and type expansion

AnyDice affords user-defined functions that define zero or more named parameters.
Parameters can also bear a *conversion specifier* (which AnyDice’s [function documentation](https://anydice.com/docs/functions/) refers to as “parameter types”).
Specifiers are `:n` for number, `:s` for sequence, and `:d` for die.
Where a conversion specifier is present, the type of the argument ***received*** will be of the designated type for each call of the function.
Specifiers and passed values can also implicitly determine the return type for the function.
AnyDice’s [function documentation](https://anydice.com/docs/functions/) explains:

> **Expecting a number [`:n`]**
>
> If a sequence is provided, then the sequence will be summed. If a die is provided, then the function will be invoked for all numbers on the die – or the sums of a collection of dice – and the result will be a new die.
>
> **Expecting a die [`:d`]**
>
> If a number is provided, then it will be converted to a die that can roll only that number. If a sequence is provided, then the sequence will be summed and treated the same as a number.
>
> **Expecting a sequence [`:s`]**
>
> If a number is provided, then it will be converted to a sequence containing only that number. If dice are provided, then the function will be invoked for all possible sequences that can be made by rolling those dice. In that case the result will be a new die.

While technically accurate, it is difficult to form a mental model of what AnyDice does and its motivations for doing so from that description.
We’ll attempt to be more explicit here.

Where an argument is passed that matches the conversion specifier, nothing special happens.
The argument is passed without conversion.
Beyond that, one can think of two distinct flavors of conversion: *coercion* and *expansion*.

#### Coercion

*Coercion* happens when an object is collapsed or “promoted” to that of another type (e.g., as a container).
Where a number is passed as an argument to a function expecting a sequence or die, that number is “wrapped” by the conversion specifier type.
A `3` becomes `{3}` with `:s` or `d{3}` with `:d`.
Where a sequence is passed as an argument to a function expecting a number or die, that sequence is collapsed (summed) to a number[^7] and treated accordingly.

Where a function is passed arguments that either match conversion specifiers exactly or produce only type coercions, the value returned by calling the function will be exactly that defined by its `result:` statement.

```c
function: add die M:d and die N:d { result: M + N  \ a number \ }
output [add die 3 and die 4]  \ only coercion, no expansion, so result remains a number \
```

Open in playground: [![Try the AnyDice-compatible playground](anydice-playground.svg)](../playground/#p=ZnVuY3Rpb246IGFkZCBkaWUgTTpkIGFuZCBkaWUgTjpkIHsgcmVzdWx0OiBNICsgTiAgXCBhIG51bWJlciBcIH0Kb3V0cHV0IFthZGQgZGllIDMgYW5kIGRpZSA0XSAgXCBvbmx5IGNvZXJjaW9uLCBubyBleHBhbnNpb24sIHNvIHJlc3VsdCByZW1haW5zIGEgbnVtYmVyIFwK)

#### Expansion

*Expansion* happens when a function is called with a die or pool as an argument that has a number or sequence as a its conversion specification.
Where a parameter expects a number, a single die is expanded into its faces, with the function being called once for each face.
A pool is first flattened to a single die, and that flattened die’s faces are used.

This can be seen from the following probe:

```c
ITER_COUNT: 0
function: N:n th face from FACE:n {
  ITER_COUNT: ITER_COUNT + 1  \ Get a copy of the global ITER_COUNT that survives across the expanded calls \
  if ITER_COUNT = N { result: FACE } \ else { result: d{} } \
}
D: 3d6 output D             \ The distribution of 3d6 \
output [4 th face from D]   \ The face submitted to the 4th iteration of the function from the collapsed 3d6 (i.e., 6) \
output [12 th face from D]  \ The face submitted to the 12th iteration of the function from the collapsed 3d6 (i.e., 14) \
```

Open in playground: [![Try the AnyDice-compatible playground](anydice-playground.svg)](../playground/#p=SVRFUl9DT1VOVDogMApmdW5jdGlvbjogTjpuIHRoIGZhY2UgZnJvbSBGQUNFOm4gewogIElURVJfQ09VTlQ6IElURVJfQ09VTlQgKyAxICBcIEdldCBhIGNvcHkgb2YgdGhlIGdsb2JhbCBJVEVSX0NPVU5UIHRoYXQgc3Vydml2ZXMgYWNyb3NzIHRoZSBleHBhbmRlZCBjYWxscyBcCiAgaWYgSVRFUl9DT1VOVCA9IE4geyByZXN1bHQ6IEZBQ0UgfSBcIGVsc2UgeyByZXN1bHQ6IGR7fSB9IFwKfQpEOiAzZDYgb3V0cHV0IEQgICAgICAgICAgICAgXCBUaGUgZGlzdHJpYnV0aW9uIG9mIDNkNiBcCm91dHB1dCBbNCB0aCBmYWNlIGZyb20gRF0gICBcIFRoZSBmYWNlIHN1Ym1pdHRlZCB0byB0aGUgNHRoIGl0ZXJhdGlvbiBvZiB0aGUgZnVuY3Rpb24gZnJvbSB0aGUgY29sbGFwc2VkIDNkNiAoaS5lLiwgNikgXApvdXRwdXQgWzEyIHRoIGZhY2UgZnJvbSBEXSAgXCBUaGUgZmFjZSBzdWJtaXR0ZWQgdG8gdGhlIDEydGggaXRlcmF0aW9uIG9mIHRoZSBmdW5jdGlvbiBmcm9tIHRoZSBjb2xsYXBzZWQgM2Q2IChpLmUuLCAxNCkgXAo)

As one of its comment suggests, this probe works because of the way that variables are “scoped” in AnyDice, which we’ll [explore in detail](#variable-scope) further on.

Where a parameter expects a sequence, a die or pool is expanded into unique rolls, with the function being called once for each roll.
The values in each roll are ordered according to the `"position order"` setting.

```c
set "position order" to "lowest first"
function: smooshify D:s {
  M: 1 \\ V: 0  \ the "\\" is present to break things up visually \
  loop FACE over D { V: FACE * M + V \\ M: M * 100 }
  result: V
}
output [smooshify 5d3]
```

Open in playground: [![Try the AnyDice-compatible playground](anydice-playground.svg)](../playground/#p=c2V0ICJwb3NpdGlvbiBvcmRlciIgdG8gImxvd2VzdCBmaXJzdCIKZnVuY3Rpb246IHNtb29zaGlmeSBEOnMgewogIE06IDEgXFwgVjogMCAgXCB0aGUgIlxcIiBpcyBwcmVzZW50IHRvIGJyZWFrIHRoaW5ncyB1cCB2aXN1YWxseSBcCiAgbG9vcCBGQUNFIG92ZXIgRCB7IFY6IEZBQ0UgKiBNICsgViBcXCBNOiBNICogMTAwIH0KICByZXN1bHQ6IFYKfQpvdXRwdXQgW3Ntb29zaGlmeSA1ZDNdCg)

If a function call has more than one parameter to which expansion applies, it will be called with the Cartesian product of those values:

```c
function: add each of N:n to each of V:n { result: N + V }
output [add each of d6 to each of (d3 * 100)]
```

Open in playground: [![Try the AnyDice-compatible playground](anydice-playground.svg)](../playground/#p=ZnVuY3Rpb246IGFkZCBlYWNoIG9mIE46biB0byBlYWNoIG9mIFY6biB7IHJlc3VsdDogTiArIFYgfQpvdXRwdXQgW2FkZCBlYWNoIG9mIGQ2IHRvIGVhY2ggb2YgKGQzICogMTAwKV0K)

If any expansion occurs, the result from each function call is weighted in accordance with the face(s) or roll(s) submitted for that call.
Weighted results are aggregated into a single die, which becomes the final result.
Where the result from one of the function iterations is a die, that die is “folded in”, taking on the weight associated with that call’s arguments, as demonstrated by the following program:

```c
function: replace with weird die where FACE:n shows three {
  if FACE = 3 { result: d{44, 44, 55, 66} } else { result: FACE }
}
output [replace with weird die where d10 shows three]
```

Open in playground: [![Try the AnyDice-compatible playground](anydice-playground.svg)](../playground/#p=ZnVuY3Rpb246IHJlcGxhY2Ugd2l0aCB3ZWlyZCBkaWUgd2hlcmUgRkFDRTpuIHNob3dzIHRocmVlIHsKICBpZiBGQUNFID0gMyB7IHJlc3VsdDogZHs0NCwgNDQsIDU1LCA2Nn0gfSBlbHNlIHsgcmVzdWx0OiBGQUNFIH0KfQpvdXRwdXQgW3JlcGxhY2Ugd2l0aCB3ZWlyZCBkaWUgd2hlcmUgZDEwIHNob3dzIHRocmVlXQo)

[^7]: Note that for outputs ***only***, a sequence is coerced to a die.
      `output {1, 1, 1, 2, 2, 3}` is equivalent to `output d{1, 1, 1, 2, 2, 3}`, ***not*** `output 10`.
      It is unclear why this coercion discrepancy exists.

#### Variable scope

AnyDice’s [function documentation](https://anydice.com/docs/functions/) notes:

> The variables that are defined inside a function only exist while that function is being invoked.
> If a variable with the same name already existed, then its old value will become available again after the function invocation is finished.

This dances around a scoping behavior that allows the [iteration probe above](#expansion) to work.
Specifically, a function has access to a ***copies*** of each global variable.

```c
function: { GLOBAL: GLOBAL + 10 \\ result: GLOBAL }
GLOBAL: 0
output GLOBAL named "GLOBAL before function call"  \  0 \
output [] named "GLOBAL from function call"        \ 10 \
output GLOBAL named "GLOBAL after function call"   \ *spoiler alert*: 0 \
GLOBAL: 100
output GLOBAL named "GLOBAL before function call"  \ 100 \
output [] named "GLOBAL from function call"        \ 110 \
output GLOBAL named "GLOBAL after function call"   \ 100 \
```

Open in playground: [![Try the AnyDice-compatible playground](anydice-playground.svg)](../playground/#p=ZnVuY3Rpb246IHsgR0xPQkFMOiBHTE9CQUwgKyAxMCBcXCByZXN1bHQ6IEdMT0JBTCB9CkdMT0JBTDogMApvdXRwdXQgR0xPQkFMIG5hbWVkICJHTE9CQUwgYmVmb3JlIGZ1bmN0aW9uIGNhbGwiICBcICAwIFwKb3V0cHV0IFtdIG5hbWVkICJHTE9CQUwgZnJvbSBmdW5jdGlvbiBjYWxsIiAgICAgICAgXCAxMCBcCm91dHB1dCBHTE9CQUwgbmFtZWQgIkdMT0JBTCBhZnRlciBmdW5jdGlvbiBjYWxsIiAgIFwgKnNwb2lsZXIgYWxlcnQqOiAwIFwKR0xPQkFMOiAxMDAKb3V0cHV0IEdMT0JBTCBuYW1lZCAiR0xPQkFMIGJlZm9yZSBmdW5jdGlvbiBjYWxsIiAgXCAxMDAgXApvdXRwdXQgW10gbmFtZWQgIkdMT0JBTCBmcm9tIGZ1bmN0aW9uIGNhbGwiICAgICAgICBcIDExMCBcCm91dHB1dCBHTE9CQUwgbmFtZWQgIkdMT0JBTCBhZnRlciBmdW5jdGlvbiBjYWxsIiAgIFwgMTAwIFwK)

But there’s another more subtle behavior not mentioned ***at all*** in AnyDice’s documentation.

!!! warning "Variables are scoped ***across*** expansion calls"

    If an earlier iteration of a function called as part of an expansion changes the object that a variable points to, a later iteration will see that change.

    Consider:

    ```c
    function: N:n {
      if N = 1 { VAR: 1 }    \ don't call this where the lowest value of a die is not 1 \
      else { VAR: VAR * 2 }  \ double VAR \
      result: VAR
    }
    output [d6]
    \ output [d{2..6}] \  \ this results in an error \
    ```

    Open in playground: [![Try the AnyDice-compatible playground](anydice-playground.svg)](../playground/#p=ZnVuY3Rpb246IE46biB7CiAgaWYgTiA9IDEgeyBWQVI6IDEgfSAgICBcIGRvbid0IGNhbGwgdGhpcyB3aGVyZSB0aGUgbG93ZXN0IHZhbHVlIG9mIGEgZGllIGlzIG5vdCAxIFwKICBlbHNlIHsgVkFSOiBWQVIgKiAyIH0gIFwgZG91YmxlIFZBUiBcCiAgcmVzdWx0OiBWQVIKfQpvdXRwdXQgW2Q2XQpcIG91dHB1dCBbZHsyLi42fV0gXCAgXCB0aGlzIHJlc3VsdHMgaW4gYW4gZXJyb3IgXAo)

    That tells us two things:

    1. As [mentioned above](#on-ordering), faces are provided to function calls from lowest-to-highest, regardless of the setting of `"position order"`.
       If they weren’t, the above function would crash, since `VAR` is not defined until `N = 1`.
    2. Changes to `VAR` persist between function calls for a particular expansion, but not beyond.

That behavior might have useful applications beyond the [expansion probe above](#expansion), but what follows does not.

#### Modifications ***to parameters*** are durable across expansion calls

!!! bug "Modifications ***to parameters*** are durable across expansion calls"

    This behavior is only [vaguely alluded to](https://anydice.com/docs/functions/), almost in passing:

    > While it is possible to assign a value to a variable used as a parameter, you should not do so yourself.

    No explanation of motivation or consequences is provided, but it teaches away from a common idiom among many programming languages, such as recursive counters or default overrides.
    The behavior it fails to properly identify is that modifications to a non-expanded parameter value remain modified across all remaining function calls during expansion.
    In effect, it means that parameters are passed by-reference from its internal expansion machinery.
    The `anydyce` interpreter does not reproduce this behavior.


Many users are reasonably and completely unaware of this trap and often fall into it with more complicated programs. Consider the following (simplified from AnyDice program [`9010`](../playground/#id=9010)) as an illustration:

```c
function: reroll N:n less than THRESHOLD:n depth DEPTH:n {
  if N < THRESHOLD & DEPTH > 0 {
    DEPTH: DEPTH - 1
    result: [reroll 1d6 less than THRESHOLD depth DEPTH]
  }
  result: N
}
output [reroll 1d6 less than 4 depth 3] named "reroll under 4, up to 3 tries"
```

Open in playground: [![Try the AnyDice-compatible playground](anydice-playground.svg)](../playground/#p=ZnVuY3Rpb246IHJlcm9sbCBOOm4gbGVzcyB0aGFuIFRIUkVTSE9MRDpuIGRlcHRoIERFUFRIOm4gewogIGlmIE4gPCBUSFJFU0hPTEQgJiBERVBUSCA-IDAgewogICAgREVQVEg6IERFUFRIIC0gMQogICAgcmVzdWx0OiBbcmVyb2xsIDFkNiBsZXNzIHRoYW4gVEhSRVNIT0xEIGRlcHRoIERFUFRIXQogIH0KICByZXN1bHQ6IE4KfQpvdXRwdXQgW3Jlcm9sbCAxZDYgbGVzcyB0aGFuIDQgZGVwdGggM10gbmFtZWQgInJlcm9sbCB1bmRlciA0LCB1cCB0byAzIHRyaWVzIgo)

The intent of the program is clear:
Roll a `d6`, and if it’s under `4`, re-roll it up to `3` times.
The author provides `DEPTH` to parameterize a recursion cap and decrements it each time the function is called.
This is a common pattern for recursion among many programming environments.
What goes wrong on anydice.com is as follows.

`N` is a `:n` parameter expanded over the outer `1d6` outcomes, meaning the function will be called six times.
Theoretically, this ***should*** be with arguments: `N=1, THRESHOLD=4, DEPTH=3`; `N=2, THRESHOLD=4, DEPTH=3`; ...;`N=6, THRESHOLD=4, DEPTH=3`.

But this isn’t what happens.

After the first outcome iteration triggers a re-roll (decrementing `DEPTH` from `3` to `2`), AnyDice fails to reset `DEPTH` back to `3` for the next `N`’s iteration.
The second outcome iteration starts with `DEPTH=2`, the third starts with `DEPTH=1`, and the fourth with `DEPTH=0`.
From then onward, no re-rolls happen at all because the depth-budget remains perpetually exhausted at `DEPTH=0` for all remaining iterations.

It’s hard to imagine a purpose for these “parameter leaks” because expansion calls are alternative branches of a single combination of faces or rolls, not sequential events.
It’s quite possible errors like these go unnoticed where programs are sufficiently complicated or where outputs look “close” to those expected.
But, as we’ll see, it gets ***even stranger***.

#### Even modifications to some ***expanded*** parameters are durable (visible) across expansion calls

As mentioned above, where a function call has more than one parameter to which expansion applies, it will be called with the Cartesian product of those values.
The ***order*** of those calls iterates the leftmost parameter fastest (i.e., “little-endian” by analogy), as demonstrated by the following probe:

```c
I: 0
function: A:n then B:n {
  I: I + 10000
  V: A + B + I
  result: V
}
output [(d6 * 100) then d6]
```

Open in playground: [![Try the AnyDice-compatible playground](anydice-playground.svg)](../playground/#p=STogMApmdW5jdGlvbjogQTpuIHRoZW4gQjpuIHsKICBJOiBJICsgMTAwMDAKICBWOiBBICsgQiArIEkKICByZXN1bHQ6IFYKfQpvdXRwdXQgWyhkNiAqIDEwMCkgdGhlbiBkNl0K)

In that probe, the iteration number occupies the `XX0000` digits of each outcome, faces from `A` occupy the `00XX00` digits of each outcome, and faces from `B` occupy the `0000XX` digits of each outcome.
Because the iteration number is most significant, iteration order is preserved during outcome sorting, and one can see that values of `A` vary fastest, looping around for each value of `B`.

What happens if one writes back to `A` during expansion?
Consider a small modification to the probe:

```c
I: 0
function: A:n then B:n {
  I: I + 10000
  V: A + B + I
  A: A + 1
  result: V
}
output [(d6 * 100) then d6]
```

Open in playground: [![Try the AnyDice-compatible playground](anydice-playground.svg)](../playground/#p=STogMApmdW5jdGlvbjogQTpuIHRoZW4gQjpuIHsKICBJOiBJICsgMTAwMDAKICBWOiBBICsgQiArIEkKICBBOiBBICsgMQogIHJlc3VsdDogVgp9Cm91dHB1dCBbKGQ2ICogMTAwKSB0aGVuIGQ2XQo)

Both the `anydyce` interpreter and anydice.com produce the same output for both of the above programs.
`A`’s value is reset to the next value in its inner loop for every iteration.
But what happens if one writes back to `B` during expansion?
Consider another small modification to the probe:

```c
I: 0
function: A:n then B:n {
  I: I + 10000
  V: A + B + I
  B: B + 1  \ <- This is different \
  result: V
}
output [(d6 * 100) then d6]
```

Open in playground: [![Try the AnyDice-compatible playground](anydice-playground.svg)](../playground/#p=STogMApmdW5jdGlvbjogQTpuIHRoZW4gQjpuIHsKICBJOiBJICsgMTAwMDAKICBWOiBBICsgQiArIEkKICBCOiBCICsgMSAgXCA8LSBUaGlzIGlzIGRpZmZlcmVudCBcCiAgcmVzdWx0OiBWCn0Kb3V0cHV0IFsoZDYgKiAxMDApIHRoZW4gZDZdCg)

As expected, the `anydyce` interpreter produces the same output as the prior two programs.
On anydice.com, however, the first six outputs are `10101`, `20202`, ..., `60606`.
The second six outputs are `70102`, `80203`, ..., `120607`.
As one can see, `B`’s modifications last through `A`’s inner cycle until `B` is reset in its own outer cycle.

What is even more bizarre is where expansion happens over a sequence, and that sequence parameter is overwritten in the function body.
Consider:

```c
function: add one hundred times N:n to sum of S:s {
  S: S + 0
  result: N * 100 + S
}
output [add one hundred times d3 to sum of 3d6]
```

Open in playground: [![Try the AnyDice-compatible playground](anydice-playground.svg)](../playground/#p=ZnVuY3Rpb246IGFkZCBvbmUgaHVuZHJlZCB0aW1lcyBOOm4gdG8gc3VtIG9mIFM6cyB7CiAgUzogUyArIDAKICByZXN1bHQ6IE4gKiAxMDAgKyBTCn0Kb3V0cHV0IFthZGQgb25lIGh1bmRyZWQgdGltZXMgZDMgdG8gc3VtIG9mIDNkNl0K)

The `anydyce` interpreter produces the expected 54 outcomes: `{103-118, 203-218, 303-318}`.
anydice.com, however, perplexingly, only produces three outcomes: `{118, 218, 318}`.

#### Diagnosing/avoiding parameter leaks on anydice.com

To reiterate, it is entirely safe to write to parameter variable names in the `anydyce` interpreter.
However, when using anydice.com, one can avoid the parameter leak problem with a refactor work-around.
For any function potentially affected, rename all parameters to have new, unique names.
Then assign the new parameter names to the old ones in the body of the function.
For example, consider the following function:

```c
function: overwrite PARAMETER:n {
  PARAMETER: PARAMETER + 1
  \ ... \
}
```

Assuming `_PARAMETER_` is not used anywhere within the body of the same function, refactor it as follows:

```c
function: overwrite _PARAMETER_:n {
  PARAMETER: _PARAMETER_
  \ everything below remains the same as above \
  PARAMETER: PARAMETER + 1
  \ ... \
}
```

Not only does this avoid the anydice.com parameter leak problem, but this approach can be a useful diagnostic as well.
If anydice.com provides different results pre- and post-refactor, there’s a pretty good chance you’re affected by this bug.

#### Function signatures and duplicate parameter names

AnyDice identifies which function to call by a function signature.
This means that a later-defined function will mask or overwrite an earlier-defined one with the same signature.
Signatures do not take parameter names or conversion specifiers.
Nothing prohibits a function from defining more than one parameter with the same name, but only the first is accessible.

For example, the function `function: is it X:n or X:s { result: X }` has a signature `[is it ? or ?]`.
Evaluating `[is it 1 or 2d2]` results in the function being executed three times during [expansion](#functions-variable-scope-type-coercion-and-type-expansion), each time returning the value `1`.

### “Phantom” Mass

Some interactions with the empty die may accumulate “phantom” mass that cannot be explained by floating point error.
It is difficult to predict which programs will trigger this bug, but they are deterministic, meaning that affected programs produce the same erroneous results on anydice.com each time they are run.

The effect can be seen with following probe:

```c
function: f K:n { result: K }
function: g G:n D:d { if G = 1 { result: 5 } else { result: [f D] } }
output [g (d2) (d0)]
D: [g (d2) (d{})]
output D
D: 4dD + 0
output D
```

Open in playground: [![Try the AnyDice-compatible playground](anydice-playground.svg)](../playground/#p=ZnVuY3Rpb246IGYgSzpuIHsgcmVzdWx0OiBLIH0KZnVuY3Rpb246IGcgRzpuIEQ6ZCB7IGlmIEcgPSAxIHsgcmVzdWx0OiA1IH0gZWxzZSB7IHJlc3VsdDogW2YgRF0gfSB9Cm91dHB1dCBbZyAoZDIpIChkMCldCkQ6IFtnIChkMikgKGR7fSldCm91dHB1dCBECkQ6IDRkRCArIDAKb3V0cHV0IEQ)

The `anydyce` interpreter produces expected outputs that all sum to 100%.
anydice.com’s results, however, only sum to 100% for the first output.
The second output has a phantom that occupies 50% of the total weight.
That is compounded to 93.75% for the third output, so the phantom is durable over at least some operations.

Again, the mechanism by which this happens, and the context under which is it triggered is unclear.
[`140df`](../playground/#id=140df) is especially illustrative.
Despite calling the same function with `2d6`, `3d6`, ..., `6d6`, this effect is only visible when the argument is `4d6`, where the total outcome weight only sums to 90.12%.
Additional examples include programs [`455`](../playground/#id=455) (55.56% on anydice.com), [`11182`](../playground/#id=11182) (14.5% on anydice.com).
[`1065f`](../playground/#id=1065f) (also [making an appearance above](#certain-operators-and-the-empty-die)) is an even subtler example where the phantom mass in the second output somehow comes from the default result when exhausting recursion depth.

### Overflows

AnyDice is susceptible to overflow errors in both outcomes and weights.
A trivial example is as follows:

```c
output 1d{9}^(1d10*10)
```

Open in playground: [![Try the AnyDice-compatible playground](anydice-playground.svg)](../playground/#p=b3V0cHV0IDFkezl9XigxZDEwKjEwKQ)

The `anydyce` interpreter correctly handles large integer outcomes.
anydice.com produces four outcomes, two of which are negative, despite being mathematically impossible.

The following stresses weight accumulation (floating point) errors.

```c
D: d{1:99, 0}
loop N over {1..60} {
  D: D * D
  output D named "d{1:99, 0} after loop [N]"
}
output d{} named "================================"
D: d{1:9, 0}
loop N over {1..60} {
  D: D * D
  output D named "d{1:9, 0} after loop [N]"
}
```

Open in playground: [![Try the AnyDice-compatible playground](anydice-playground.svg)](../playground/#p=RDogZHsxOjk5LCAwfQpsb29wIE4gb3ZlciB7MS4uNjB9IHsKICBEOiBEICogRAogIG91dHB1dCBEIG5hbWVkICJkezE6OTksIDB9IGFmdGVyIGxvb3AgW05dIgp9Cm91dHB1dCBke30gbmFtZWQgIj09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09IgpEOiBkezE6OSwgMH0KbG9vcCBOIG92ZXIgezEuLjYwfSB7CiAgRDogRCAqIEQKICBvdXRwdXQgRCBuYW1lZCAiZHsxOjksIDB9IGFmdGVyIGxvb3AgW05dIgp9Cg)

As [described above](#features), the `anydyce` interpreter handles these calculations reasonably, even with truncation.
However, on anydice.com, later loops’ cumulative weights fail to sum to 100% (sometimes approaching zero, sometimes approaching infinity).

### “Legacy” programs

anydice.com allows interpretation and execution of an undocumented “legacy” syntax (e.g., `output legacy "8d6h4-4"` from program [`1f`](../playground/#id=1f)).
The `anydyce` interpreter does not recognize the `legacy` keyword and is incapable of interpreting the corresponding notation.

## Conclusion

The goals of this project are as follows:

1. Present a truly transparent reference implementation for Jasper Flick’s [AnyDice Dice Probability Calculator](https://anydice.com/) subject to independent inspection, validation, and improvement.
   This includes addressing long-standing bugs persistent in the original platform.
1. Preserve existing cognitive investment in the AnyDice platform independently of the author’s ability or willingness to support it, including enabling users to:
    1. share AnyDice programs without relying on a proprietary centralized database; and
    2. execute AnyDice programs independently of accessing specific websites.
1. Preserve the existing corpus of AnyDice programs for all authors who invested time and effort to create and save them.

This is a work in progress.
If you have any feedback on how this project can better meet these goals, please [get in touch](contrib.md).
