# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.5.0] - 2026-06-29

### Added — active component (keep multi-part models in ONE document)
- `assembly.activate_component` / `assembly.active_component`, and
  `assembly.create_component` now takes `activate` (default true). Once a
  component is active, **all** build + entity-lookup ops (sketch, feature,
  primitive, construction, surface, body, and the `query.list_*` views) target
  that component instead of the root — so a model with many parts lives in a
  single document, each part isolated in its own component, without disturbing
  existing bodies. Default target is still the root component (fully backwards
  compatible). `primitive.*` also accept a per-call `component` override.
- `_delta` body counting now spans **all** components, so adding a body inside a
  sub-component is reported correctly.

### Added — auto-dismiss blocking dialogs (external guard)
- An **external guard process** (`bridge/dialog_guard.py`) auto-closes modal
  dialogs (save / recover / server-verification / stray message boxes) that
  otherwise freeze Fusion's main thread and stall every op. It must be a separate
  process: such modals hold the Python GIL, freezing any *in-process* watchdog
  (and even the HTTP server) for the whole time the dialog is up. The add-in
  launches it automatically (Windows). It acts when an MCP op is stuck (a busy
  flag the dispatcher writes) after a short grace, or when a dialog title matches
  a configurable nuisance allowlist. Dismissal is WM_CLOSE→Esc→Enter via
  PostMessage (no foreground focus needed; WM_CLOSE = Cancel/[X], so no save, no
  Save-As loop, no data loss). New settings: `dialog_grace_allow`, `dialog_titles`.

### Added — self-reload (no manual Stop→Run)
- `system.restart` does a full **in-process** stop → re-import all modules from
  disk → start, applying changes to bridge/`__init__` code without a manual Fusion
  Stop→Run. It is self-bootstrapping (registers its main-thread restart channel on
  `system.reload`), so even brand-new restart wiring activates over RPC. The
  teardown is deferred off the request thread (avoids deadlocking the HTTP server).

## [0.4.0] - 2026-06-27

### Added — local web config dashboard
- `fusion-mcp webui` launches a **single-page config dashboard** in the browser
  (stdlib `http.server` backend, **zero new dependencies**; loopback-only +
  per-session token to block drive-by CSRF). Sections: live **status** (bridge
  health, version, op count), **add-in settings** editor (writes addin.json),
  **token** view/copy/regenerate, **multi-AI connector** config generator, and
  **remote/HTTP** setup. Bilingual (中/英), dark theme.
- **Multi-AI connector registry** (`fusion_mcp.clientconfig.CONNECTORS`): generates
  ready-to-copy config for Claude Desktop, Claude Code, Cursor, VS Code, a generic
  stdio client, and a remote/HTTP connector — with one-click safe **merge** into
  `claude_desktop_config.json` (auto-backup, preserves your other servers). Future
  AIs = add one registry entry.

### Changed
- The config-merge logic moved to the shared `fusion_mcp.clientconfig` module;
  `install/claude_config_merge.py` is now a thin wrapper that delegates to it.

## [0.3.0] - 2026-06-27

Big coverage push toward "everything the API can do" (~100 tools), all validated
against a real Fusion 360 install.

### Added — generic API (true full coverage)
- `api.call` — invoke ANY `adsk.*` method / read any property by dotted path, with
  `{"$path"}`/`{"$ref"}`/`{"type":...}` argument resolution, object construction
  (Point3D/Vector3D/ValueInput/ObjectCollection + generic `create`), and `store_as`
  for cross-call object reuse. `api.introspect` (live `inspect` of classes/objects
  with cleaned signatures) and `api.docs` (cloudhelp URL). Gated behind
  allow_arbitrary_code; introspect/docs are always available.

### Added — curated tools
- Sketch: `constrain` (coincident/parallel/perpendicular/tangent/equal/horizontal/
  vertical/concentric/collinear/midpoint/symmetry), `dimension` (distance/horizontal/
  vertical/angular/radial/diameter), `spline`, `offset`, `project`.
- Edit/timeline: `undo` (with parametric->direct guard), `redo`, `delete_all`,
  `suppress_feature`, `unsuppress_feature`.
- Inspection: `measure_angle`, `interference`.
- Features: `draft`, `split_body`, `split_face`, `offset_faces`, `thread`
  (proper `createThreadInfo` via `recommendThreadData`).
- Surfaces: `thicken`, `ruled`, `patch`, `stitch`.
- Export: `dxf`. CAM: auto tool-assignment from the local library + `cam.list_tools`.
- Assembly: `joint` now also mates by **planar face** (`face_one`/`face_two` via
  `JointGeometry.createByPlanarFace`), and `primitive.box` can build **into a named
  component** (`component=`) so you can assemble parts and joint them.
- Sheet metal: `create_flat_pattern` for an existing sheet-metal body. NOTE: the
  Fusion API exposes **no creation** of sheet-metal flanges/bends (FlangeFeatures/
  BendFeatures have no create methods) — model those interactively or via api.call.

### Fixed (found via live introspection on real Fusion)
- Interference API: `Design.createInterferenceInput` + `analyzeInterference`, results
  via `InterferenceResults.count/item` (faust's `root.interfere` is wrong).
- `DraftFeatures.createInput(faces, plane, isTangentChain)` + `setSingleAngle(...)`.
- `GeometricConstraints` has no `addFix`; constraints now dispatched via getattr so a
  missing method can't break the whole op.
- `ThreadDataQuery.recommendThreadData` returns `(success, designation, class)`.
- **HTTP client uses `trust_env=False`** so the local bridge bypasses a system proxy
  (a running proxy, e.g. Clash on 127.0.0.1:7897, otherwise returns 502).

### Removed
- Dedicated sheet-metal flange/flat-pattern tools — `FlangeFeatures` has no
  `createInput` in the 2026 API and the flow needs a sheet-metal rule. Sheet metal is
  reachable via `api.call`; curated sheet-metal tools are a future item.

## [0.2.0] - 2026-06-26

### Added — Assembly & CAM (73 tools total)
- **Assembly** (validated on real Fusion): `assembly.create_component`,
  `list_occurrences`, `list_joints`, `move_component`, `ground_component`,
  `joint` (rigid/revolute/slider/cylindrical/planar), `as_built_joint`,
  `rigid_group`. Joints are built from component origin points via
  `JointGeometry.createByPoint(point.createForAssemblyContext(occ))`.
- **CAM / manufacturing**: `cam.list_setups`, `list_operations`, `create_setup`
  (milling/turning/cutting), `create_operation` (by strategy), `generate`
  (toolpaths), `post_process` (G-code). Requires the Manufacturing workspace to
  have been opened once; ops degrade to a clear hint otherwise. Note: most
  operation strategies need a tool assigned before a toolpath will generate.

### Fixed
- `JointGeometry.createByPoint` takes a single point entity in the 2026 API (not
  `(occurrence, point)`); use an assembly-context proxy point.
- CAM `itemByProductType` throws (not returns None) when no CAM product exists —
  wrapped so it surfaces the friendly "open Manufacturing" hint.

## [0.1.1] - 2026-06-26

Validated end-to-end against a **real Fusion 360** install (61 live checks, all
passing except license/security-gated ones).

### Fixed (found via real-Fusion testing)
- Main-thread dispatch: `fireCustomEvent` is on `Application`, not the `CustomEvent`
  object — every mutating op had been failing. Dispatcher now uses a queue-drain
  handler + 250 ms backup timer so a dropped event can't wedge the queue.
- `Sketches.add(plane)` (was the non-existent `addSketch`).
- `feature.fillet`: use `edgeSetInputs.addConstantRadiusEdgeSet(...)` (old
  `addConstantRadiusEdges` was removed from the API).
- `feature.chamfer`: use `createInput2()` + `chamferEdgeSets.addEqualDistanceChamferEdgeSet(...)`.
- `primitive.sphere`: revolve a half-disk (flat edge on the axis) instead of a
  full circle that straddles the axis ("profile intersects revolution axis").
- `units.set`: accept `unit` (and `units`) — parameter-name mismatch.
- PowerShell installers re-saved as UTF-8 **with BOM** (Windows PowerShell 5.1
  mis-decoded the Chinese strings on GBK consoles).

### Added
- `system.reload` op: hot-reload op modules from disk without a Fusion restart
  (dev/test acceleration); add-in entry purges cached modules on Stop→Run.
- Auto-create document, mutation `_delta` feedback, bilingual error hints.
- Primitives (`box`/`cylinder`/`sphere`), `body.combine`, `feature.sweep`/`loft`,
  `sketch.arc`, `parameter.delete`.

### Removed / Notes
- `export.threemf` removed — Fusion's ExportManager has no 3MF option (use STL
  for 3D printing).
- `export.iges` is restricted on **personal-use** Fusion licenses; the bridge now
  returns a clear hint. STEP/STL/F3D work on all licenses.

## [0.1.0] - 2026-06-26

### Added
- Two-part architecture: an in-Fusion **add-in bridge** (pure stdlib) + an external **MCP server**.
- MCP server with **stdio** (Claude Desktop / Claude Code) and **streamable-http** (Docker / remote) transports.
- ~40 CAD tools across `document`, `query`, `sketch`, `feature`, `body`, `construction`, `material`, `export`, `view`, `units`, and a gated `script` op.
- Tool annotations (`readOnlyHint` / `destructiveHint` / `idempotentHint`) so clients can auto-approve safe operations.
- **mm-first** units everywhere (internal cm conversion handled at the boundary) to avoid the classic 10× bug.
- Auto-generated shared **bearer token**; both sides read the same token file — no manual copying.
- `fusion-mcp doctor` bilingual diagnostics with op reconciliation between server and add-in.
- **Mock mode** (`--mock`) so the server, tests, and Docker image work without Fusion installed.
- Foolproof **Windows installer** (PowerShell 5.1 + `.bat`), with UTF-8/GBK handling and safe Claude config merge.
- **Docker** one-command run (`docker compose up`) for the server layer.
- Full **bilingual (中/英) documentation**: README, manual, architecture, tool reference, troubleshooting.
- Test suite (mock-driven) that needs no Fusion install.
