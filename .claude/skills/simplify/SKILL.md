---
name: simplify
description: Before finishing any function, apply the five simplification questions. Rewrite until all five pass.
---

# /simplify

Before finishing any function or module, answer these five questions.
Rewrite until the answer to every question is yes.

1. **Does the stdlib or an installed library already do this?**
   If yes, delete the code and call that instead.

2. **Can it be fewer lines?**
   Remove redundant assignments, intermediate variables that are used once,
   and conditions that the type system already guarantees.

3. **Can the nesting go down?**
   Invert conditions for early returns. Extract inner loops only if they get a meaningful name.
   Maximum nesting depth: 3.

4. **Is every comment a "why"?**
   Delete comments that say what the code does. Keep comments that say why a non-obvious
   choice was made. Delete docstrings that restate the signature.

5. **Would a stranger read it in one pass?**
   If you need to re-read a line to understand it, rewrite it. If a name requires
   context to decode, rename it.

Only when all five are yes is the function done.

See also `docs/CODING_STANDARDS.md` — slop list section.
