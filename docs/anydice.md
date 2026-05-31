<!---
  Copyright and other protections apply.
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
<!-- BEGIN MONKEY PATCH --
>>> import warnings
>>> from dyce import TruncationWarning
>>> from dyce.lifecycle import ExperimentalWarning
>>> warnings.filterwarnings("ignore", category=ExperimentalWarning)
>>> warnings.filterwarnings("ignore", category=TruncationWarning)

  -- END MONKEY PATCH -->

# `anydyce`’s *Mostly*-Compatible AnyDice Interpreter

`anydyce` provides a pure Python cleanroom implementation of Jasper Flick’s [AnyDice Dice Probability Calculator](https://anydice.com/) via its [`anydyce.anydice`][anydyce.anydice] subpackage.

    >>> from anydyce.anydice import format_results, run
    >>> program = r"""
    ...     output 3d6
    ... """
    >>> results = run(program)
    >>> print(format_results(results))
    ==== output 1 ====
    avg |   10.50
    std |    2.96
    var |    8.75
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

The interpreter strives to be a working replacement in all meaningful aspects, but it is ***not*** 100% compatible, favoring fundamental correctness over producing identical results.
This document focuses on two categories of behaviors:

1. **AnyDice idiosyncrasies**, meaning surprising or inconsistent behaviors that appear intended that our `anydyce` interpreter faithfully replicates; and
2. **Excluded AnyDice bugs**, meaning behaviors we have evidence are unintended defects, that our interpreter deliberately avoids.

It should be noted that until now, many of these behaviors weren’t well documented or widely understood, but were implicated in many of the real world programs we examined.
We found the inconsistencies collectively to be unintuitive and difficult to remember, making non-trivial programs hard to author, reason about, and debug.
We also discovered several latent “foot guns” likely to silently result in mathematical errors in real world programs.
Some foundation necessary to our analysis of AnyDice behaviors is present below, but familiarity with AnyDice’s documentation[^1] is helpful for gleaning a complete picture.

[^1]: See the “[Documentation](https://anydice.com/docs/)”, “[Function Library](https://anydice.com/docs/function-library/)”, and “[Articles](https://anydice.com/articles/)” sections of the AnyDice website.

## Background

AnyDice appears to have been around in some form or another since 2009, receiving a handful of updates between then and 2026.
It is free to use by anyone, likely funded by the author who invites others to offset costs through donations.
It has amassed over a quarter million “saved” programs[^2] during its tenure.
It enjoys substantial popularity among loyal users, many of whom post on [rpg.stackexchange.com](https://rpg.stackexchange.com/questions/tagged/anydice) providing volunteer edication and support.

Its most typical use involves typing or pasting a program conforming to a [proprietary syntax](https://anydice.com/docs/) into a text field on a [hosted website](https://anydice.com/).
The user submits the program by activating a “Calculate” button in the interface, which transmits the program text via HTTP POST to a [PHP handler](https://anydice.com/calculator_limited.php).
The returned JSON results are then interpreted and displayed for the user.
All interpretation and computation appears to be performed server-side.

AnyDice remains closed source, and its author seldom makes updates.
While the author provides a [human readable version of the AnyDice grammar](http://anydice.com/ebnf.txt), the actual implementation if its parser and interpreter are not publicly available.
While AnyDice provides documentation, it does not constitute a complete specification from which to replicate or validate its interpreter.
Many meaningful details important to more sophisticated computations are left to the discovery of the user.

[^2]: At a user’s request, AnyDice has ability to save a program in its own proprietary, server-side database, providing a link with a hexadecimal ID which can later be used to load the same program.
      As of this writing, AnyDice’s ability to save new programs or retrieve existing ones seems to be offline.
      The highest program ID known to this author prior to this reduction in functionality was [`4327d`](https://raw.githubusercontent.com/posita/anydice-data/refs/heads/main/anydice.com/program/32/7d/4327d.txt).

### Prior art

- [PyDice](https://pdice.arkareem.com/) is a pure Python implementation of an AnyDice interpreter that both interprets AnyDice programs as well as transpiles them into [PythonDice](https://github.com/Ar-Kareem/PythonDice/) Python code (which is pretty darn cool)
- [anydice.js](https://github.com/dlom/anydice) claims to provide a low level interface for retrieving results from AnyDice’s interpreter for use in JavaScript programs (untested)
- [anydieparser](https://www.npmjs.com/package/anydieparser) claims to provide an AnyDice interpreter in JavaScript (untested)
- [anydice](https://git.paco.to/nick/anydice) claims to provide an AnyDice interpreter implemented in C and Rust (untested)

## Reverse-engineering methodology

AnyDice is a closed source, remote execution environment without a complete specification.
Based on the available documentation, an initial [Lark grammar](https://lark-parser.readthedocs.io/en/latest/grammar.html) was created along with a transformer for generating an AST and corresponding interpreter.
While the documentation was a helpful starting point, it was fairly high level, so claims and implications had to be validated, and additional detail needed to be surfaced.

The general workflow to iterate toward a working implementation was as follows:

1. Form a hypothesis about a particular aspect of the AnyDice inpreter (e.g., structure or contextual behavior);
2. Design a probe (program) whose results would surface details of that particular aspect;
3. Execute the probe with AnyDice, interpret the results, refining our own implementation as necessary; and, finally,
4. Validate our implementation would produce similar results of the most recent probe as well as all prior probes.[^3]

Additionally, periodic comparison of our interpreter’s results with AnyDice’s across the entire corpus of unique[^4] saved programs surfaced additional details and nuances not identified by the above loop.
While 100% completeness is not guaranteed, based on experimentation and the behavior observed by processing that corpus, our interpreter should be appropriate for most uses.
In some cases, our interpreter supersedes AnyDice’s where AnyDice’s behavioral inconsistencies or bugs produce incorrect results.

[^3]: Validation probes were captured as unit tests, important for avoiding regressions as our interpreter evolved.

[^4]: AnyDice’s save functionality implements a rudimenatry de-duplication filter.
      Where a user requests a program be saved that is byte-for-byte identical to a prior saved program, AnyDice often provides a link with the ID of the previously saved program.
      This still affords duplication where, e.g., the only difference is whitespace use or comment text.
      We considered two programs to be equivalent if they resulted in the same AST from our parser and transformer.
      De-duping based on AST resulted in a corpus just shy of 160,000 distinct programs.

      As an aside, some of those programs mirrored our own probes (e.g., [`39567`](https://raw.githubusercontent.com/posita/anydice-data/refs/heads/main/anydice.com/program/95/67/39567.txt) saved by the author of [PythonDice](https://github.com/Ar-Kareem/PythonDice/)), suggesting areas where users tripped over unintuitive “hot spots” of the interpreter, surfacing and resolve questions likely very similar to our own.

## AnyDice as our reference implementation

Some basics foundationally necessary to our discussion of AnyDice is present below, but familiarity with AnyDice’s documentation[^2] is helpful for gleaning a complete picture.

### Types: numbers, sequences of numbers, and dice whose faces are numbers

AnyDice programs operate on three distinct object types:

1. Integers (which AnyDice calls “numbers”)
2. Sequences of numbers
3. Dice whose faces are numbers
    - Depending on the context, this can mean a pool of one or more dice, a single die, or the “empty die”

Objects are ***immutable***, but [variables](#variables) can be reassigned, including for derivative construction.
Types can be implicitly coerced, collapsed, or expanded, depending on the context, as we’ll explore.
Floating point numbers can be presented in output data, and double strings are used for interpreter configuration and labeling outputs, but AnyDice programs do not support arbitrary use or manipulation of floating point numbers or strings.

The syntax for numbers is straightforward: `0`, `1`, `+100`, `-273`, etc.

The syntax for sequences are braces containing lists of numbers, inclusive ranges of numbers, subsequences, or repetitions of numbers or subsequences, all of which are expanded and flattened: `{-3..-1:2, {4..6, {7, 8}:3}}` is equivalent to `{-3, -2, -1, -3, -2, -1, 4, 5, 6, 7, 8, 7, 8, 7, 8}`.
Order is preserved, as illustrated by the following program:

```c
S: {-3..-1:2, {4..6, {7, 8}:3}}         \ assign the expanded and flattened sequence to S \
loop N over {1..#S} {                   \ loop over values in a contiguous range from 1, to the length of S, inclusive, assigning each value to N \
  output N@S named "S at position [N]"  \ output the value of S at position N for each iteration of the loop \
}
```

Dice are created with the `d` operator, which has both unary and binary forms.
More complicated forms are explored later, but the simplest forms are `d<num>`, `d<seq>`, `<num>d<num>`, and `<num>d<seq>`.
The first and second (unary) forms create a single die.
The third and forth (binary) forms create a pool of like dice.

Where `<num>` is positive, `d<num>` is shorthand for `d{1..<num>}`.
Where `<num>` is negative, it’s shorthand for `d{<num>..-1}`.
Where `<num>` is zero, it’s shorthand for `d{0}`, which is a single-sided die whose sole face is `0`.

Weighted dice are constructed by providing an appropriately-constructed sequence for the right-hand operand.
The expression `d{1, 2, 3, 1, 2, 1}` creates a six-sided die where three faces are `1`, two faces are `2`, and one face is `3`.

In binary form, the left side operand provides the number of dice in the pool.
For example, `2d6` creates a pool of two six-sided dice.

#### The empty die - `d{}`

The empty die is a die with zero faces.
In AnyDice, it deserves special attention because it is fraught with inconsistencies, which we call out below.
(See [this](#certain-operators-and-the-empty-die), [this](#dice-pool-width), and this.)

### Variables

Variables have uppercase letter names, optionally with underscores.
Digits are not allowed.
In AnyDice, variables are dynamically typed, which means that a variable’s type is determined by the object it points to.
After an assignment `A: 1`, `A` points to a number.
If one later reassigns `A: {}`, `A` then points to the empty sequence.

With the exception of two very strange behaviors described below that are deliberately not reproduced by our interpreter, AnyDice objects are ***immutable***, and variables behave as pointers to those immutable objects.
This is illustrated by the following program:

```c
I: 1       \ I points to a number object with the value 1 \
J: I       \ J points to the same number object as I \
I: {3..5}  \ I now points to a new sequence object containing the values 3, 4, and 5 \
output J   \ J still points to the number object with the value 1 \
```

### Operators

Similar to other programming languages, AnyDice provides:

- Binary arithmetic operators `+`, `-`, `*`, `/`, and `^` (exponential);
    - Note the absence of a modulo operator
- Binary boolean[^5] operators `&` (boolean and) and `|` (boolean or);
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

[^5]: By “boolean”, we mean an operator that evaluates each operand as falsy (the number zero) or truthy (a number other than zero), and which resolves to either `0` or `1`.

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
    This means that `2@3d6` will intuitively select the middle die when rolling a pool of three six-sided dice without the use of additional parentheses, but `#20d6` will rarely provide what is intended, as authors almost always mean `#(20d6)`, not `(#20)d6`.

#### Operand interpretation and collapse

For the most part, arithmetic operators behave as expected, with some notable exceptions.
These frustrate reliance on mathematical equivalence, or even consistency among operator behavior.

Arithmetic and boolean operators convert sequence operands to numbers by summing the sequence’s members.
The expression `{1, 2, 3} - {}` becomes `6 - 0`, or `6`.
The expression `d6 - {4, 5, 6}` becomes `d6 - 15`.
This is also true of the left-hand operand of the `d` operator.
The expression `{1. 2, 3}d{2, 4, 6}` becomes `6d{2, 4, 6}`, or a pool of 6 dice, each with three faces, `2`, `4`, and `6`.

!!! warning "`<num> / 0` is ***always*** `0`, even though `{0}^-1` is `-9223372036854776000`"

    A number divided by `0` is `0`, ***even if the dividend is also `0`***.

    Also, where the base is a sequence or die, AnyDice ***mostly*** produces anticipated results.
    For example, `{-1} ^ -2` resolves to `1`.

    But when the base ***collapses*** to the number `0` and the exponent is a negative number, AnyDice resolves the expression as `-9223372036854776000` (or `-0x80000000000000c0`).
    The expression `d{-2, -1, 0, 1, 2} ^ -2` produces resolves to `d{0, 1, -9223372036854776000, 1, 0}`.
    The large negative number was perhaps intended a sentinel value of some kind, but it remains inconsistent with AnyDice’s divide-by-zero behavior.
    Our interpreter preserves the sentinel behavior with a zero base and negative exponent, so the expression`0^-1` resolves to `-9223372036854776000`.

!!! bug "`<num>^-1` is an error, even though `{<num>}^-1` is not"

    Confusingly, a negative exponent in AnyDice results in an error where the base is a number.
    Our interpreter resolves negative exponents with number bases consistently with other values as well as integer division that truncates toward zero.
    The expression `(-1)^-1` resolves to `-1`, `(-1)^-2` resolves to `1`, etc.

Unary `-` collapses sequences into numbers.
As mentioned above, unary `+`, acts as a no-op.
This presents an asymmetry where `-{1..4}` resolves to `-10`, while `+{1..4}` resolves to `{1..4}`.

!!! bug "`<non-empty-die> <= {}` always returns `1`"

    A comparison with `<=` always resolves to `1` where the left-hand operand is a non-empty die and the right-hand operand is the empty sequence (e.g., `d{1000} <= {}`).
    Our interpreter deliberately avoids this behavior, instead treating `<=` comparisons consistently with others.

Where `d`’s left-hand operand resolves to a negative number, the expression is treated as if the negative applies to the right-hand operand.
In other words, `-<num>d<expr>` is treated as `<num>d(-(<expr>))`.
In fact, `(-N)dX`, `Nd(-X)`, and `-(NdX)` are generally equivalent.
Where `d`’s left-hand operand resolves to `0`, the result is `d0`, except where the right-hand operand resolves to `d{}`, [discussed](#certain-operators-and-the-empty-die) below.
The expression `0d1000` resolves to `d0`.

!!! warning "`<die>d<die>` probably doesn’t do what you think or want"

    In addition to the basic forms above, the binary `d` operator also accepts a die as its left-hand operator.
    To figure out what this does, it is important to understand that the `d` operator is basically equivalent to:

    ```c
    function: roll N:n of the die D:d { result: NdD }
    output [roll 4 of the die d3]                        \ output 4d3 \
    output [roll d2 of the die d3]                       \ output d2d3 \
    output [roll 2d4 of the die d3]                      \ output 2d4d3 \
    output [roll [roll d2 of the die d4] of the die d3]  \ output d2d4d3 \
    output [roll 2 of the die 4d3]                       \ output 2d(4d3) \
    output [roll d2 of the die 4d3]                      \ output d2d(4d3) \
    ```

    In lay terms, where the left-hand operand is a die, this means, “roll a first die, then whatever number comes up, roll that many of a second die, then collapse the whole thing down into a single die.”
    This isn’t incredibly useful in practice, and is often the source of confusion
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

!!! bug "`d{} + {}` does not equal `{} + d{}`, even though `d{} - {}` equals `{} - d{}`"

    The ***specific*** exception to this exception is that AnyDice resolves `d{} + {}` and `d{} | {}` specifically to `d{}`, even though `{} | d{}`, `{} | d{}`, `d{} - {}`, and `{} - d{}` all resolve to `0`.
    Our interpreter does not reproduce this inconsistency.

Operations involving ***multiplicative*** and ***comparative*** operators, `*`, `\`, `^`, `&`, `=`, `!=`, `<`, `<=`, `>=`, and `>` follow set convolution conventions.
The expressions `d{} * 1`, `1 / d{}`, `8 ^ d{}`, `d{} & 8`, etc. all resolve to `d{}`.
Likewise, where the binary `d` operator’s left-hand or right-hand operand resolves to `d{}`, the result is `d{}`, irrespective of the value of the other operand.
The expression `1000d{}` resolves to `d{}`.
The unary expressions `-d{}` and `!d{}` also resolve to the empty die.

#### Dice pool width

The `#` operator reveals the number of dice in a pool.

!!! warning "`#` is unreliable for zero-length pools or pools involving the empty die"

    Some results are perplexing, however.
    For example, `#(4d{})` is `0`, but `#(0d0)` and `#(d{}d{})` are `1`.
    This inconsistency reveals an underlying implementation detail that likely affects the AnyDice interpreter in additional ways we’ll explore below.

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

While technically accurate, it is difficult to form a mental model of what AnyDice does and why from that description.
We’ll attempt to be more explicit here.

Where an argument is passed that matches the conversion specifier, nothing special happens.
The argument is passed without conversion.
Beyond that, we can think of two distinct flavors of conversion: *coercion* and *expansion*.

#### Coercion

*Coercion* happens when an object is collapsed or “promoted” to that of another type (e.g., as a container).
Where a number is passed as an argument to a function expecting a sequence or die, that number is “wrapped” by the conversion specifier type.
A `3` becomes `{3}` with `:s` or `d{3}` with `:d`.
Where a sequence is passed as an argument to a function expecting a number or die, that sequence is collapsed (summed) to a number and treated accordingly.

Where a function is passed arguments that either match conversion specifiers exactly or produce only type coercions, the value returned by calling the function will be exactly that defined by its `result:` statement.

```c
function: add die M:d and die N:d { result: M + N  \ a number \ }
output [add die 3 and die 4]  \ only coercion, no expansion, so result remains a number \
```

#### Expansion

*Expansion* happens when a function is called with a die or pool as an argument that has a number or sequence as a its conversion specification.
Where a parameter expects a number, a single die is expanded into its faces, with the function being called once for each face.
A pool is first flattened to a single die, and that flattened die’s faces are used.

This can be seen from the following probe:

```c
ITER_COUNT: 0
function: N:n th face from FACE:n {
  ITER_COUNT: ITER_COUNT + 1  \ We get a copy of the global ITER_COUNT that survives across the expanded calls \
  if ITER_COUNT = N { result: FACE } \ else { result: d{} } \
}
D: 3d6 output D             \ The distribution of 3d6 \
output [4 th face from D]   \ The face submitted to the 4th iteration of the function from the collapsed 3d6 (i.e., 6) \
output [12 th face from D]  \ The face submitted to the 12th iteration of the function from the collapsed 3d6 (i.e., 14) \
```

As one of its comment suggests, this program works because of the way that variables are “scoped” in AnyDice, which we’ll [explore in detail](variable-scope) further on.

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

If a function call has more than one parameter to which expansion applies, it will be called with the Cartesian product of those values:

```c
function: add each of N:n to each of V:n { result: N + V }
output [add each of d6 to each of (d3 * 100)]
```

If any expansion occurs, the result from each function call is weighted in accordance with the face(s) or roll(s) submitted for that call.
Weighted results are aggregated into a single die, which becomes the final result.
Where the result from one of the function iterations is a die, that die is “folded in”, taking on the weight associated with that call’s arguments, as demonstrated by the following program:

```c
function: replace with weird die where FACE:n shows three {
  if FACE = 3 { result: d{44, 44, 55, 66} } else { result: FACE }
}
output [replace with weird die where d10 shows three]
```

#### Variable scope

AnyDice’s [function documentation](https://anydice.com/docs/functions/) notes:

> The variables that are defined inside a function only exist while that function is being invoked.
> If a variable with the same name already existed, then its old value will become available again after the function invocation is finished.

This dances around a scoping behavior that allows our [iteration probe above](#expansion) to work.
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

But there's another more subtle behavior not mentioned ***at all*** in AnyDice’s documentation.

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

    That tells us two things:

    1. Faces are provided to function calls from lowest-to-highest, regardless of the setting of `"position order"`.
       If they weren’t, our function would crash, since `VAR` is not defined until we see `N = 1`.
    2. Our changes to `VAR` persist between function calls for a particular expansion, but not beyond.

That behavior might have useful applications beyond our [expansion probe](#expansion) above, but what follows does not.

#### Modifications ***to parameters*** are durable across expansion calls

!!! bug "Modifications ***to parameters*** are durable across expansion calls"

    This behavior is only [vaguely alluded to](https://anydice.com/docs/functions/), almost in passing:

    > While it is possible to assign a value to a variable used as a parameter, you should not do so yourself.

    No explanation of motivation or consequences is provided, but it teaches away from a common idiom among many programming languages, such as recursive counters or default overrides.
    The behavior it fails to properly identify is that modifications to a non-expanded parameter value remain modified across all remaining function calls during expansion.
    In effect, it means that parameters are passed by-reference from its internal expansion machinery.
    Our interpreter does not reproduce this behavior.


Many users are (reasonably) completely unaware of this trap and often fall into it with more complicated programs. Consider the following (simplified from AnyDice program [`9010`](https://raw.githubusercontent.com/posita/anydice-data/refs/heads/main/anydice.com/program/90/10/9010.txt)) as an illustration:

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

The intent of that program is clear:
Roll a `d6`, and if it's under `4`, re-roll it up to `3` times.
The author provides `DEPTH` to parameterize a recursion cap and decrements it each time the function is called.
This is a common pattern for recursion among many programming environments.

What goes wrong with AnyDice is as follows.
`N` is a `:n` parameter expanded over the outer `1d6` outcomes, meaning the function will be called six times.
Theoretically, this ***should*** be with arguments `N=1, THRESHOLD=4, DEPTH=3`, `N=2, THRESHOLD=4, DEPTH=3`, ...,`N=6, THRESHOLD=4, DEPTH=3`.

But this isn’t what happens.

After the first outcome iteration triggers a re-roll (decrementing `DEPTH` from `3` to `2`), AnyDice fails to reset `DEPTH` back to `3` for the next `N`'s iteration.
The second outcome iteration starts with `DEPTH=2`, the third starts with `DEPTH=1`, and the fourth with `DEPTH=0`.
From then onward, no re-rolls happen at all because the depth-budget remains perpetually exhausted at `DEPTH=0` for all remaining iterations.

It’s hard to imagine a purpose for this “parameter leakage” because expansion calls are alternative branches of a single combination of faces or rolls, not sequential events.
It’s quite possible errors like these go unnoticed where programs are sufficiently complicated or where outputs look “close” to those expected.
But, as we’ll see, it gets ***even stranger***.

#### Modifications to ***some*** expanded parameters are durable across expansion calls

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

In that probe, the iteration number occupies the `XX0000` digits of each outcome, faces from `A` occupy the `00XX00` digits of each outcome, and faces from `B` occupy the `0000XX` digits of each outcome.
Because the iteration number is most significant, iteration order is preserved during outcome sorting, and we can see that values of `A` vary fastest, looping around for each value of `B`.

What happens if we write back to `A` during expansion?
Consider a small modification to our probe:

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

Both our interpreter and AnyDice produces the same output for both of the above programs.
`A`’s value is reset to the next value in its inner loop for every iteration.
But what happens if we write back to `B` during expansion?
Consider another small modification to our probe:

```c
I: 0
function: A:n then B:n {
  I: I + 10000
  V: A + B + I
  B: B + 1
  result: V
}
output [(d6 * 100) then d6]
```

Our interpreter correctly produces the same output as the prior two programs.
With AnyDice, however, the first six outputs are `10101`, `20202`, ..., `60606`.
The second six outputs are `70102`, `80203`, ..., `120607`.
As we can see, `B`’s modifications last through `A`’s inner cycle until `B` is reset in its own outer cycle.

```c
function: remove all N:n s from S:s {
  RESULT: {}
  loop V over S { if V != N { RESULT: { RESULT, V } } }
  result: RESULT
}
function: process S:s {
  S: [remove all 3 s from S]
  result: dS
}
output [process 5d{2, 3, 4}]
```

<!-- BEGIN MONKEY PATCH --
>>> warnings.resetwarnings()

   -- END MONKEY PATCH -->
