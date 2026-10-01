# Handoff: fix/starter-questions

Branch `fix/starter-questions` off `main` (`752f889`), Oct 1 2026.

The fourth starter on the Chat page, "What Modbus slave address does the UNOnext start from?",
abstained for every visitor. That was by design: it is golden row 20, its only source is
engineer-only, and Chat asks as Support. A suggested question that returns "I couldn't find this"
reads as a failure, so the starter list now holds only questions Support gets an answer to.

## Built

- `web/src/components/chat/StarterQuestions.tsx`: the UNOnext starter is replaced with golden
  row 5, "What enteliVAULT editions are available?" (`expect.support: "answer"`).
- Same file: the caption "The last one comes from an engineer-only document, so Support gets an
  abstain." is replaced with "Each one is answered from the ingested documents, with page
  citations."
- Same file: `STARTERS` is exported.
- `web/src/tests/chat.test.tsx`: new test "every starter question is a golden case that support
  gets an answer to". It reads `eval/golden.jsonl` with `?raw`, as `GoldenTable.tsx` does.
- No change to `App.tsx`, roles, ACLs, the corpus, the golden set or the role switch tests.
- No doc change: `README.md` and `docs/` never mentioned the old starter or its caption.

## Verified

Docs grep, no hits:

```
$ grep -rn -i "Modbus slave address\|engineer-only document, so Support" README.md docs/
(grep exit 1)
```

Golden expectations for the old and the new starter (the new test fails on the old one):

```
20 {'support': 'abstain', 'engineer': 'answer'} What Modbus slave address does the UNOnext start from?
5 {'support': 'answer'} What enteliVAULT editions are available?
```

Web tests and build:

```
$ cd web && npm test
 Test Files  8 passed (8)
      Tests  34 passed (34)
   Duration  4.60s (environment 55%, tests 22%, setup 11%, transform 9%, import 3%)

$ npm run build
> tsc -b && vite build
✓ 76 modules transformed.
dist/index.html                   0.56 kB │ gzip:  0.34 kB
dist/assets/index-B8oUHZek.css   21.36 kB │ gzip:  5.09 kB
dist/assets/index-D21_8uFP.js   288.30 kB │ gzip: 89.37 kB
✓ built in 259ms
```

Lint and unit tests:

```
$ make lint
uv run ruff check src/ tests/ eval/ .claude/hooks/
All checks passed!
uv run ruff format --check src/ tests/ eval/ .claude/hooks/
127 files already formatted
uv run mypy src/ tests/ eval/ .claude/hooks/
Success: no issues found in 122 source files

$ make test
273 passed, 63 deselected, 8 warnings in 31.60s
```

Stack healthy:

```
$ make up
 Container bas-assistant-app-1 Healthy
grafana-db-user: OK
[exited with code 0]

$ docker ps -a --format 'table {{.Names}}\t{{.Status}}'
bas-assistant-app-1          Up 23 seconds (healthy)
bas-assistant-grafana-1      Up 40 seconds (healthy)
bas-assistant-litellm-1      Up 44 seconds (healthy)
bas-assistant-migrate-1      Exited (0) 42 seconds ago
bas-assistant-redis-1        Up 50 seconds (healthy)
bas-assistant-postgres-1     Up 50 seconds (healthy)
bas-assistant-prometheus-1   Up 50 seconds (healthy)
```

All four starters as Support on the local stack, first (uncached) run. Each was
`POST http://localhost:8000/ask` with `X-Demo-Role: support`:

```
Q: How many inputs and outputs does the eZNT-T331 network thermostat have?
decision: answered | cache_hit: False | route: fast
answer: The eZNT-T331 network thermostat has 3 universal inputs and 3 analog outputs, along with 1 binary output.

Q: What is the power draw of the Red5-PLUS-1180?
decision: answered | cache_hit: False | route: fast
answer: The power draw of the Red5-PLUS-1180 is 24 VDC (20 W max) or 24 VAC at 50 VA, with a maximum of 100 VA when fully loaded with internally powered triac outputs.

Q: What browsers does enteliWEB support?
decision: answered | cache_hit: False | route: fast
answer: enteliWEB supports the following browsers: Google Chrome 80+, Microsoft Edge 80+, Mozilla Firefox 73+, and Apple Safari 13+.

Q: What enteliVAULT editions are available?
decision: answered | cache_hit: False | route: fast
answer: enteliVAULT is available in the following editions: eW200-VLT (200 I/O), eW500-VLT (500 I/O), eW1000-VLT (1,000 I/O), eW2500-VLT (2,500 I/O), eWEnt-VLT (5,000 I/O), and additional options for more I/O points including eWEnt-VLT2500IO (+2,500), eWEnt-VLT25kIO (+25,000), and eWEnt-VLTUnLtd (+Unlimited). It is also available as an enteliCLOUD add-on with editions for 25, 50, 100, 200, 500, 1,000, 2,500, 5,000, 10,000, and 20,000 site I/O points.
```

Citations, from the second run of the same four requests (`cache_hit: true`, same answers),
trimmed to title, page and source:

```
eZNT-T331 network thermostat
  eZNT-T331  p1  https://deltacontrols.com/wp-content/uploads/eZNT-T331_Catalog_Sheet.pdf
  eZNT-T331  p1  https://deltacontrols.com/wp-content/uploads/eZNT-T331_Catalog_Sheet.pdf
Red5-PLUS-1180 power draw
  Red5-PLUS-1180  p1  https://deltacontrols.com/wp-content/uploads/Red5-PLUS-1180_Catalog-Sheet.pdf
enteliWEB browsers
  enteliWEB    p1  https://deltacontrols.com/wp-content/uploads/enteliWEB-Catalog-Sheet.pdf
  enteliVAULT  p1  https://deltacontrols.com/wp-content/uploads/enteliVAULT_Catalog_Sheet.pdf
enteliVAULT editions
  enteliVAULT  p3  https://deltacontrols.com/wp-content/uploads/enteliVAULT_Catalog_Sheet.pdf
  enteliVAULT  p1  https://deltacontrols.com/wp-content/uploads/enteliVAULT_Catalog_Sheet.pdf
```

Skipped: clicking the starters in a browser, and any check against the live site. The live site
does not change until this is deployed.

## Deferred

None.

## Known gaps

None new.

## Merge notes

- No migrations, env vars or dependency changes. Two web files and this handoff.
- The enteliWEB starter cites the enteliVAULT sheet (p1) as its second source, so the new
  starter's document is not entirely uncited by the other three. Its expected document
  (enteliVAULT p3) is still distinct from theirs. Golden row 12 (eZNS ports) is the alternative
  with no overlap.
- The live site changes only after a deploy. No Redis flush is needed: the UNOnext question is
  no longer offered, and its cached abstain expires within 24 hours.
- Access control is unchanged. Row 20 still abstains for Support and answers for Engineer, and
  the Evals tab and How I built this still show it.
