# 故障排查

> English: [TROUBLESHOOTING.en.md](TROUBLESHOOTING.en.md)

**第一步永远是运行：** `fusion-mcp doctor` —— 它会检查桥、令牌、算子、是否有打开的设计，并打印修复建议。

---

### Claude 里看不到 Fusion 工具

- 改完配置后是否**完全退出并重开** Claude Desktop？（不是只关窗口。）
- `%APPDATA%\Claude\claude_desktop_config.json` 是否是合法 JSON？重跑安装器可安全合并。
- `command` 是否指向真实路径，如 `...\.venv\Scripts\fusion-mcp.exe`？在终端用该路径加 `version` 跑一下确认。
- Claude Desktop 的 MCP 日志在 `%APPDATA%\Claude\logs\`（`mcp.log`、`mcp-server-fusion360.log`）。

### "Cannot reach the Fusion add-in bridge at http://127.0.0.1:9000"（连不上加载项）

按可能性排序：
1. **Fusion 没运行**，或没有打开设计。启动 Fusion，打开一个设计。
2. **加载项没启动。** 实用程序 → 加载项 → 脚本和加载项 → Fusion360MCP → 运行。勾选"启动时运行"。
3. **端口不一致。** 加载项端口（`~/.fusion-mcp/addin.json`）必须等于 `FUSION_ADDIN_URL` 的端口，两端默认 9000。
4. **加载项启动时崩溃。** 查看 `~/.fusion-mcp/addin.log`，重新运行加载项。

### 401 / "鉴权失败"

服务器令牌 ≠ 加载项令牌。两端都应读取 `~/.fusion-mcp/token`。
- 裸跑：确认没有设置一个不同的 `FUSION_MCP_TOKEN` 环境变量。
- **Docker**：容器读不到你的家目录。把 `~/.fusion-mcp/token` 的内容复制进 `.env` 的
  `FUSION_MCP_TOKEN=...`，再 `docker compose up -d`。

### Docker：容器连不上宿主的 Fusion

- `FUSION_ADDIN_URL` 必须是 `http://host.docker.internal:9000`（compose 里已设）。
- 加载项默认绑定 `127.0.0.1`，容器可能访问不到。若如此，把 `~/.fusion-mcp/addin.json`
  的 `bind` 改为 `0.0.0.0` 并重启加载项。**安全：** 保持令牌开启，并考虑用防火墙规则把
  9000 端口限制在本地/容器流量。
- Linux 上 `host.docker.internal` 由 compose 里的 `extra_hosts: host-gateway` 提供。
- 记住 **Fusion 无法跑在容器里**——容器里只有服务器。

### 调用超时 / "Operation timed out"

加载项在 Fusion 的**主线程**上执行算子，而当有模态命令对话框打开时主线程被占用。
关闭 Fusion 中打开的对话框/命令再重试。极重的操作可能超过 `FUSION_MCP_TIMEOUT`（调大它）。

### 控制台中文乱码（中文 Windows）

控制台代码页是 GBK。`.bat` 安装器会执行 `chcp 65001`；CLI 在 `doctor`/`tools`/`version`
时把 stdout 重配为 UTF-8。若仍乱码，先 `chcp 65001` 再执行命令，或改用 Windows Terminal。

### "No active Fusion design"（没有活动设计）

在 Fusion 中打开或新建一个设计文档。许多工具也可先让 Claude "新建一个文档"。

### 尺寸差了 10 倍

正常不会出现——所有工具都用**毫米**并在内部换算。若出现，多半是你按厘米给了值；请改用毫米。
文档的*显示*单位（`fusion_set_units`）不影响工具输入。

### `fusion_run_script` 不见了或拒绝执行

出于安全被双重门控。需**同时**开启：用 `--allow-arbitrary-code` 启动服务器，并在
`~/.fusion-mcp/addin.json` 设 `"allow_arbitrary_code": true`，然后重启加载项。

### 9000 端口被占用

改 `~/.fusion-mcp/addin.json` 里的 `port`，重启加载项，并把服务器的
`FUSION_ADDIN_URL` 设为 `http://127.0.0.1:<新端口>`。

### 安装器找不到 Python

从 python.org 安装 Python 3.10+（勾选 *Add to PATH*），重开终端；或给
`windows-install.ps1` 传 `-Python "C:\完整\路径\python.exe"`。

### 截图失败

需要有活动视口。确保 Fusion 处于设计工作区且模型可见。内存紧张时调低分辨率。

### IGES 导出报 "the user is restricted"（用户受限）

IGES（及 SAT）导出在**个人使用版许可**下被禁用——这是 Autodesk 的限制,不是 bug。
请改用 **STEP**(更好的交换格式)、STL 或 F3D,它们在所有许可下都可用。3MF 未提供
(Fusion API 没有 3MF 导出器),3D 打印请用 STL。

### 改了加载项代码却不生效

Fusion 会缓存已导入的模块。如何重载取决于你改了什么:
- **算子文件**(`ops/*.py`):运行 `python scripts/rpc.py system.reload`——就地重新
  导入全部算子代码,无需重启 Fusion。
- **桥/传输层**(`bridge/*.py`、`config.py`、`__init__.py`):在 Fusion 里
  **Stop→Run**(脚本和加载项 → Fusion360MCP → 停止,再运行)。入口会在启动时清除
  本包模块缓存,所以 Stop→Run 会从磁盘重新加载。
- 若仍显示旧行为,**彻底重启 Fusion**。

记得先把改动复制到实时 AddIns 目录:
`cp -r addin/Fusion360MCP/. "$APPDATA/Autodesk/Autodesk Fusion 360/API/AddIns/Fusion360MCP/"`

### 免费个人版 vs 订阅版

本项目**不需要**订阅——它通过公开的脚本 API 驱动 Fusion，而免费个人使用版包含该 API。
（Autodesk *官方*的 Claude 连接器是另一回事，需要订阅。）
