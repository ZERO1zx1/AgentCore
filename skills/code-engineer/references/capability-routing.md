# Capability routing

Use the smallest route that covers the actual artifacts. Load only relevant content.

| Artifact/domain | Inspect first | Typical verification |
|---|---|---|
| Source repository | manifests, lockfiles, instructions, entry points, tests, Git status | focused test, typecheck/lint, build, smoke run |
| Web/UI | routes, components, styles, state, API calls, accessibility tree | browser flow, screenshot, console/network errors, responsive states |
| Mobile/desktop app | project metadata, platform targets, resources, signing config | platform build, simulator/device smoke test when available |
| API/server | routes, schemas, middleware, auth, services, logs | contract test, health check, failure and permission cases |
| Database/data | schema, migrations, samples, types, lineage | constraints, reconciled counts, query plan, reproducible calculation |
| Container/CI/hosting | Dockerfiles, workflow/config files, environment contract | config validation, local build, dry-run/plan; no live deploy without authorization |
| Document/PDF/slide | structure, fonts/assets, page/slide count, target format | render changed pages and inspect layout/readability |
| Spreadsheet | formulas, types, named ranges, tables, charts | recalc, invariant checks, visible workbook inspection |
| Image/design | dimensions, color/profile, layers/components, target use | visual inspection at intended size and export verification |
| Audio/video | codec, streams, duration, resolution, frame/audio samples | probe output, inspect representative segments, check sync/duration |
| Archive/binary | type signature, manifest/listing, safe extraction plan | integrity/listing and targeted content checks |

## Cross-domain tasks

Map producer → transformation → consumer. Example: design → frontend asset → application bundle → hosted page. Validate each changed boundary, not every unrelated subsystem.

For large inputs, inventory first and select by relevance. Prefer metadata, indexes, search, sampling, and incremental chunks over loading the entire corpus. Preserve originals when conversion may be lossy.
