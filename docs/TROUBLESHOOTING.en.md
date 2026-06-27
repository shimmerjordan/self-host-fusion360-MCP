# Troubleshooting

> 简体中文：[TROUBLESHOOTING.zh-CN.md](TROUBLESHOOTING.zh-CN.md)

**First, always run:** `fusion-mcp doctor` — it checks the bridge, token, ops, and
whether a design is open, and prints the fix.

---

### Claude doesn't show the Fusion tools

- Did you **fully quit and reopen** Claude Desktop after editing the config? (Not just close the window.)
- Is the config valid JSON at `%APPDATA%\Claude\claude_desktop_config.json`? Re-run the installer to merge it safely.
- Check `command` points at a real path, e.g. `...\.venv\Scripts\fusion-mcp.exe`. Run that path with `version` in a terminal to confirm.
- Claude Desktop MCP logs: `%APPDATA%\Claude\logs\` (`mcp.log`, `mcp-server-fusion360.log`).

### "Cannot reach the Fusion add-in bridge at http://127.0.0.1:9000"

In order of likelihood:
1. **Fusion isn't running**, or no Design is open. Start Fusion, open a design.
2. **The add-in isn't started.** Utilities → ADD-INS → Scripts and Add-Ins → Fusion360MCP → Run. Set *Run on Startup*.
3. **Port mismatch.** The add-in port (in `~/.fusion-mcp/addin.json`) must equal the port in `FUSION_ADDIN_URL`. Default 9000 on both.
4. **The add-in crashed on start.** Check `~/.fusion-mcp/addin.log`. Re-run the add-in.

### 401 / "Authentication failed"

The server token ≠ the add-in token. Both should read `~/.fusion-mcp/token`.
- Native: make sure you didn't set a different `FUSION_MCP_TOKEN` env var.
- **Docker**: the container can't read your home folder. Copy the token from
  `~/.fusion-mcp/token` into `.env` as `FUSION_MCP_TOKEN=...`, then `docker compose up -d` again.

### Docker: server can't connect to Fusion on the host

- `FUSION_ADDIN_URL` must be `http://host.docker.internal:9000` (set in `docker-compose.yml`).
- The add-in binds to `127.0.0.1` by default, which may not be reachable from the
  container. If so, set `bind` to `0.0.0.0` in `~/.fusion-mcp/addin.json` and
  restart the add-in. **Security:** keep the token enabled and consider a firewall
  rule limiting port 9000 to local/container traffic.
- On Linux, `host.docker.internal` is provided by the `extra_hosts: host-gateway` mapping (already in the compose file).
- Remember **Fusion cannot run in the container** — only the server does.

### Calls time out / "Operation timed out"

The add-in runs ops on Fusion's **main thread**, which is blocked while a modal
command dialog is open. Close any open dialog/command in Fusion and retry. Very
heavy operations may exceed `FUSION_MCP_TIMEOUT` (raise it).

### Garbled text / mojibake in the console (Chinese Windows)

The console code page is GBK. The `.bat` installer runs `chcp 65001`; the CLI
reconfigures stdout to UTF-8 for `doctor`/`tools`/`version`. If you still see
mojibake, run `chcp 65001` before the command, or use Windows Terminal.

### "No active Fusion design"

Open or create a Design document in Fusion. Many tools also accept being told to
create one first — ask Claude to "create a new document".

### Dimensions are 10× off

You shouldn't see this — all tools take **millimetres** and convert internally. If
you do, you likely passed centimetres expecting cm; restate the value in mm. The
document's *display* unit (`fusion_set_units`) does not change tool inputs.

### `fusion_run_script` is missing or refuses to run

It is gated for safety. Enable **both**: start the server with
`--allow-arbitrary-code`, and set `"allow_arbitrary_code": true` in
`~/.fusion-mcp/addin.json`, then restart the add-in.

### Port 9000 already in use

Change `port` in `~/.fusion-mcp/addin.json`, restart the add-in, and set
`FUSION_ADDIN_URL=http://127.0.0.1:<newport>` for the server.

### Installer can't find Python

Install Python 3.10+ from python.org (tick *Add to PATH*), reopen the terminal,
or pass `-Python "C:\full\path\python.exe"` to `windows-install.ps1`.

### Screenshot fails

Needs an active viewport. Make sure Fusion is in the Design workspace with the
model visible. Lower the resolution if memory is constrained.

### IGES export fails with "the user is restricted"

IGES (and SAT) export is **blocked on personal-use Fusion licenses** — this is an
Autodesk limitation, not a bug. Use **STEP** (the better interchange format), STL,
or F3D, which work on all licenses. 3MF is not offered (Fusion's API has no 3MF
exporter); use STL for 3D printing.

### My add-in code changes don't take effect

Fusion caches imported modules. How to reload depends on what you changed:
- **Op files** (`ops/*.py`): run `python scripts/rpc.py system.reload` — it
  re-imports all op code in place, no Fusion restart needed.
- **Bridge/transport** (`bridge/*.py`, `config.py`, `__init__.py`): do a Fusion
  **Stop→Run** (Scripts and Add-Ins → Fusion360MCP → Stop, then Run). The entry
  purges cached package modules on start, so Stop→Run reloads from disk.
- If anything seems stale after that, fully **restart Fusion**.

Remember to copy your edits into the live AddIns folder first:
`cp -r addin/Fusion360MCP/. "$APPDATA/Autodesk/Autodesk Fusion 360/API/AddIns/Fusion360MCP/"`

### Free personal license vs subscription

This project does **not** require a subscription — it drives Fusion through the
public scripting API, which the free personal-use license includes. (Autodesk's
*own* official Claude connector is separate and does require a subscription.)
