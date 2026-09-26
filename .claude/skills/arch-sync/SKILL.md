---
name: arch-sync
description: Diff ARCHITECTURE.md claims vs src/ and update to current state. Moves unbuilt items to an explicit Deferred list.
---

# /arch-sync

1. Read `docs/ARCHITECTURE.md` in full.
2. For each claim in sections §3–§12, check whether the corresponding code exists in `src/`:
   - `grep -r` for class names, function names, endpoints, table names mentioned in the doc.
   - Check for the relevant modules in `src/bas_assistant/`.
3. Build two lists:
   - **Stale claims**: things ARCHITECTURE.md says exist but don't.
   - **Undocumented code**: modules or endpoints in `src/` that ARCHITECTURE.md doesn't mention.
4. Update ARCHITECTURE.md:
   - Move stale claims to the "Deferred" section at the bottom of the relevant section.
   - Add undocumented code to the appropriate section.
   - Update the Build Status table at the top.
5. Run `make lint` to confirm the file is valid.

The doc must always be current-state truthful.
Never delete a deferred item — move it to a `## Deferred` subsection with the reason.
