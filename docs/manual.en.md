# Manual (English)

> 简体中文版：[manual.zh-CN.md](manual.zh-CN.md)

A complete guide to installing, connecting, and using **self-host-fusion360-mcp**.
For how it works internally, see [ARCHITECTURE](ARCHITECTURE.md). For the full
list of tools, see [TOOLS](TOOLS.md). Stuck? See [TROUBLESHOOTING](TROUBLESHOOTING.en.md).

---

## 1. Prerequisites

- **Autodesk Fusion 360** (subscription *or* the free personal-use license).
- **Python 3.10+** on PATH (the MCP server side; Fusion ships its own Python for the add-in).
- An MCP client — **Claude Desktop**, **Claude Code**, or any MCP-capable client.
- (Docker route only) **Docker Desktop**.

---

## 2. Installation

### A. Windows one-click (recommended)

```powershell
# From the repo root, either double-click install\windows-install.bat, or:
powershell -ExecutionPolicy Bypass -File install\windows-install.ps1
```

What it does (idempotent — safe to re-run):
1. Finds Python ≥ 3.10.
2. Copies `addin\Fusion360MCP` into `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns`.
3. Generates the shared token at `~\.fusion-mcp\token` and writes `~\.fusion-mcp\addin.json`.
4. Creates `.venv` and installs the server.
5. Merges a `fusion360` entry into `%APPDATA%\Claude\claude_desktop_config.json` (your other servers are preserved, a timestamped backup is taken).

Useful flags: `-Port 9000`, `-Python "C:\path\python.exe"`, `-NoClaude` (skip Claude config), `-Http` (configure the HTTP launcher).

### B. Manual / cross-platform

```bash
# 1. Install the server
pip install -e .            # add ",[http]" for the streamable-http transport

# 2. Install the add-in: copy the folder into Fusion's AddIns directory
#    Windows: %APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\Fusion360MCP
#    macOS:   ~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/Fusion360MCP

# 3. (optional) pre-generate the token; the add-in also creates it on first run
python install/gen_token.py
```

### C. Docker (server only)

The add-in still lives on the host (steps B-2). Then:

```bash
cp .env.example .env        # set FUSION_MCP_TOKEN to the contents of ~/.fusion-mcp/token
docker compose up -d        # serves http://localhost:8765/mcp
docker compose run --rm fusion-mcp fusion-mcp doctor
```

---

## 3. Enable the add-in in Fusion

1. Start Fusion 360 and open or create a **Design**.
2. **Utilities → ADD-INS → Scripts and Add-Ins** (or press `Shift+S`).
3. On the **Add-Ins** tab, select **Fusion360MCP** → **Run**.
   Tick **Run on Startup** so it starts automatically next time.
4. A log is written to `~/.fusion-mcp/addin.log`; the bridge listens on `127.0.0.1:9000`.

---

## 4. Connect your MCP client

### Claude Desktop

The installer writes this for you. To do it manually, edit
`%APPDATA%\Claude\claude_desktop_config.json` (Windows) or
`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "fusion360": {
      "command": "C:\\path\\to\\self-host-fusion360-mcp\\.venv\\Scripts\\fusion-mcp.exe"
    }
  }
}
```

(Cross-platform alternative: `"command": "/path/.venv/bin/python", "args": ["-m", "fusion_mcp"]`.)
Fully quit and reopen Claude Desktop. A tools indicator appears in the input box.

### Claude Code

```bash
# stdio (local)
claude mcp add fusion360 -- /path/to/.venv/bin/fusion-mcp
# or HTTP (e.g. the Docker server)
claude mcp add --transport http fusion360 http://localhost:8765/mcp
```

### Remote / HTTP connector (Docker, claude.ai)

Run with `--transport http` (or the Docker image) and add a **custom connector**
pointing at `http://<host>:8765/mcp`. Note Claude's cloud must be able to reach
that URL (see TROUBLESHOOTING for exposure/security).

---

## 5. Verify

```bash
fusion-mcp doctor          # bilingual diagnostics
fusion-mcp tools           # list all registered tools
fusion-mcp doctor --mock   # sanity check without Fusion
```

A green run means: bridge reachable, token matches, core ops present, and a
design is open. Then ask Claude: *"Create a 20×20×10 mm box in Fusion and add 2 mm
fillets to the top edges, then take a screenshot."*

---

## 6. Usage

**Conventions baked into the tools:**
- All distances are **millimetres**; all angles are **degrees**.
- Reference bodies/sketches by **index or name** (`fusion_summary`, `fusion_list_bodies`).
- A typical build: `sketch → extrude/revolve → fillet/chamfer/shell/pattern → screenshot → export`.
- Prefer **parameters** for dimensions you may revise (`fusion_create_parameter`, `fusion_set_parameter`).

**Example prompts:**
- "Make a 40×40×40 mm cube, shell it to 2 mm walls, and export STL to my desktop."
- "Create a parametric flange: a 80 mm disc, 10 mm thick, with six 6 mm bolt holes on a 60 mm circle." *(holes via cut-extrude / pattern)*
- "Set the `width` parameter to 50 mm and show me the result."
- "Revolve this profile 360° around the Z axis."

**See it:** `fusion_screenshot` returns an image Claude can view — ask it to "show me the model" before trusting dimensions.

---

## 7. Tools

~46 tools across: documents, queries, parameters, sketches, features (extrude,
revolve, fillet, chamfer, shell, patterns, mirror), bodies, construction planes,
materials/appearances, export (STL/STEP/IGES/F3D/3MF), viewport, units, and a
gated `fusion_run_script`. Full reference with parameters: [TOOLS.md](TOOLS.md)
(regenerate with `python scripts/gen_tools_doc.py`).

---

## 8. Configuration

| Variable | Default | Meaning |
|---|---|---|
| `FUSION_ADDIN_URL` | `http://127.0.0.1:9000` | Server → add-in URL (`http://host.docker.internal:9000` in Docker) |
| `FUSION_MCP_TOKEN` / `FUSION_MCP_TOKEN_FILE` | `~/.fusion-mcp/token` | Shared bearer token (resolution order) |
| `FUSION_MCP_TIMEOUT` | `30` | Per-call timeout (s) |
| `FUSION_MCP_TRANSPORT` | `stdio` | `stdio` or `http` |
| `FUSION_MCP_HTTP_HOST` / `_PORT` | `0.0.0.0` / `8765` | HTTP bind |
| `FUSION_MCP_ALLOW_ARBITRARY_CODE` | `0` | Expose `fusion_run_script` |
| `FUSION_MCP_MOCK` | `0` | Run without Fusion |
| `FUSION_MCP_LOG_LEVEL` | `INFO` | Log level (always to stderr) |

The **add-in** reads `~/.fusion-mcp/addin.json` (`port`, `bind`, `allow_arbitrary_code`, `request_timeout`).

---

## 9. Security & arbitrary code

- The bridge is loopback-only + token-authenticated by default.
- `fusion_run_script` runs arbitrary Python inside Fusion. To enable it you must
  **both** start the server with `--allow-arbitrary-code` **and** set
  `"allow_arbitrary_code": true` in `~/.fusion-mcp/addin.json`. Leave it off unless you need it.
- The connector mutates your live model. Save a version before batch edits, and
  review/print before trusting any AI-made geometry (a 0.1 mm error breaks fits).

---

## 10. Update / uninstall

```bash
git pull && pip install -e .                       # update the server
# re-copy addin/Fusion360MCP into the AddIns folder, or re-run the installer

powershell -File install\windows-uninstall.ps1     # remove add-in + Claude entry
powershell -File install\windows-uninstall.ps1 -Purge   # also delete venv + ~/.fusion-mcp
```
