# Architecture / 架构

## Overview / 概览

Two processes, one contract.

- **The add-in** (`addin/Fusion360MCP/`) runs *inside* Fusion 360, in Fusion's
  bundled Python (3.14), using only the standard library. It exposes a tiny
  local HTTP server and executes `adsk.*` calls on Fusion's main thread.
- **The MCP server** (`server/fusion_mcp/`) is an ordinary process that speaks
  MCP to Claude and forwards each tool call to the add-in over HTTP.

两个进程，一份契约。加载项跑在 Fusion 内（仅用标准库），MCP 服务器在外部把工具调用转发给加载项。

```
Claude  ──MCP(stdio|http)──▶  MCP server  ──HTTP+token──▶  Add-in  ──adsk.*──▶  Fusion
(client)                      (server/)                    (addin/, main thread)
```

### Why two parts? / 为什么分两部分？

Fusion's API is **single-threaded and in-process only**. No external program can
call `adsk.*` directly, and you must not call it from a worker thread. The only
robust pattern is an in-process add-in that marshals work onto the main thread.
Every serious community project converges on this same shape; we just make it
clean, documented, and foolproof.

Fusion 的 API **单线程且仅限进程内**。外部程序无法直接调用，必须由进程内加载项把工作编组到主线程。

## Request flow / 请求流程

1. Claude calls a tool, e.g. `fusion_extrude(sketch=0, distance=10)`.
2. The tool (`server/fusion_mcp/tools/feature.py`) calls
   `client.call("feature.extrude", {...})`.
3. `AddinClient` (`client.py`) POSTs `{"op","params"}` to
   `http://127.0.0.1:9000/rpc` with `Authorization: Bearer <token>`.
4. The add-in HTTP handler (`bridge/http_server.py`, worker thread) authenticates,
   then calls `Dispatcher.submit(op, params)`.
5. `Dispatcher` (`bridge/dispatcher.py`) stores the job under a `request_id`,
   fires a Fusion **custom event** with that id, and blocks on a per-request
   `threading.Event`.
6. Fusion runs the custom-event handler **on the main thread**, which looks up
   the job, terminates any active command, runs the op
   (`ops/feature.py::extrude`), stores the result, and sets the event.
7. The worker thread wakes, returns JSON; the server returns it to Claude.

```
worker thread                main (UI) thread
submit(op,params)
  store pending[id]
  fireCustomEvent(id) ─────▶ notify(id)
  event.wait() ............    terminate active command
                               ops[op](ctx, params)
                               result/err -> box
  read box  ◀────────────────  event.set()
```

## The wire contract / 通信契约

```
POST /rpc   {"op": "feature.extrude", "params": {...}}
            -> 200 {"ok": true,  "result": {...}}
            -> 200 {"ok": false, "error": {"code","message","detail"}}   (op-level failure)
            -> 401 (bad token) / 400 (bad JSON)
GET  /health  -> liveness + flags (no auth, no adsk.* calls)
GET  /ops     -> ["document.new", ...] + metadata (no auth)
```

Op names are the contract between the two halves. `doctor` fetches `/ops` and
reconciles it against the server's expected core ops to catch version drift.

算子名是两端之间的契约。`doctor` 拉取 `/ops` 与服务器预期的核心算子对账，发现版本漂移。

## Units / 单位

Fusion's database unit is **centimetres**. Every public tool takes
**millimetres** and the conversion happens once, in `ops/_common.py`
(`len_mm`, `point_mm`, `mm2cm`). This is the single most common bug in community
tools, isolated to one place here.

Fusion 内部单位是**厘米**；所有对外工具用**毫米**，换算只在 `ops/_common.py` 做一次。

## Security model / 安全模型

- The bridge binds to `127.0.0.1` by default and requires a bearer token.
- The token is generated automatically (`secrets.token_urlsafe(32)`) and stored
  at `~/.fusion-mcp/token`, readable by both halves — never copied by hand.
- `fusion_run_script` (arbitrary Python) is **not registered** unless the server
  is started with `--allow-arbitrary-code`, and the add-in independently refuses
  it unless `allow_arbitrary_code: true` in `~/.fusion-mcp/addin.json`.
- For Docker, the add-in must accept connections from the container; see
  [TROUBLESHOOTING](TROUBLESHOOTING.en.md) for the bind-host / token trade-offs.

## Extending: add a new operation / 扩展：新增一个算子

1. **Add-in side** — write a handler in the relevant `addin/.../ops/*.py`:
   ```python
   @op("feature.loft", summary="...", )
   def loft(ctx, params):
       ...
       return {...}
   ```
   It is auto-registered via `ops/__init__.py`.
2. **Server side** — add a thin tool in `server/fusion_mcp/tools/*.py`:
   ```python
   @mcp.tool(annotations=anno())
   def fusion_loft(...): 
       return client.call("feature.loft", {...})
   ```
3. Regenerate docs: `python scripts/gen_tools_doc.py`. Add a test if useful.

两步：在加载项 `ops/` 写 `@op` 处理函数（自动注册），在服务器 `tools/` 加一个薄工具转发即可，然后重新生成工具文档。

## File map / 文件地图

| Path | Role |
|---|---|
| `addin/Fusion360MCP/Fusion360MCP.py` | Add-in entry (`run`/`stop`) |
| `addin/.../bridge/dispatcher.py` | Main-thread marshaling via custom event |
| `addin/.../bridge/http_server.py` | Local HTTP bridge (`/rpc`, `/health`, `/ops`) |
| `addin/.../ops/*.py` | Operation implementations (`@op`) |
| `server/fusion_mcp/app.py` | FastMCP app + instructions |
| `server/fusion_mcp/client.py` | HTTP client + mock mode |
| `server/fusion_mcp/tools/*.py` | MCP tools (thin forwarders) |
| `server/fusion_mcp/doctor.py` | Bilingual diagnostics |
| `install/` | Windows installer, token, config merge |
