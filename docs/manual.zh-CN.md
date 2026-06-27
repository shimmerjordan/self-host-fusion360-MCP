# 使用手册（简体中文）

> English version: [manual.en.md](manual.en.md)

安装、连接、使用 **self-host-fusion360-mcp** 的完整指南。内部原理见
[架构](ARCHITECTURE.md)；工具清单见 [TOOLS](TOOLS.md)；遇到问题见
[故障排查](TROUBLESHOOTING.zh-CN.md)。

---

## 1. 前置条件

- **Autodesk Fusion 360**（付费订阅**或**免费的个人使用版均可）。
- PATH 中有 **Python 3.10+**（用于 MCP 服务器；加载项用 Fusion 自带的 Python）。
- 一个 MCP 客户端——**Claude Desktop**、**Claude Code**，或任意支持 MCP 的客户端。
- （仅 Docker 路线）**Docker Desktop**。

---

## 2. 安装

### A. Windows 一键（推荐）

```powershell
# 在仓库根目录，双击 install\windows-install.bat，或运行：
powershell -ExecutionPolicy Bypass -File install\windows-install.ps1
```

它做了什么（幂等，可重复运行）：
1. 查找 Python ≥ 3.10。
2. 把 `addin\Fusion360MCP` 复制到 `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns`。
3. 在 `~\.fusion-mcp\token` 生成共享令牌，并写入 `~\.fusion-mcp\addin.json`。
4. 创建 `.venv` 并安装服务器。
5. 把 `fusion360` 条目合并进 `%APPDATA%\Claude\claude_desktop_config.json`（保留你的其他服务器，并留带时间戳的备份）。

常用参数：`-Port 9000`、`-Python "C:\路径\python.exe"`、`-NoClaude`（跳过 Claude 配置）、`-Http`（配置 HTTP 启动器）。

### B. 手动 / 跨平台

```bash
# 1. 安装服务器
pip install -e .            # 需要 streamable-http 传输则加 ",[http]"

# 2. 安装加载项：把文件夹复制进 Fusion 的 AddIns 目录
#    Windows: %APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\Fusion360MCP
#    macOS:   ~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/Fusion360MCP

# 3. （可选）预先生成令牌；加载项首次运行也会自动生成
python install/gen_token.py
```

### C. Docker（仅服务器）

加载项仍在宿主（B-2 步）。然后：

```bash
cp .env.example .env        # 把 FUSION_MCP_TOKEN 设为 ~/.fusion-mcp/token 的内容
docker compose up -d        # 提供 http://localhost:8765/mcp
docker compose run --rm fusion-mcp fusion-mcp doctor
```

---

## 3. 在 Fusion 中启用加载项

1. 启动 Fusion 360，打开或新建一个**设计**。
2. **实用程序 → 加载项 → 脚本和加载项**（或按 `Shift+S`）。
3. 在 **加载项** 选项卡选择 **Fusion360MCP** → **运行**。
   勾选 **启动时运行**，以后自动启动。
4. 日志写入 `~/.fusion-mcp/addin.log`；桥监听 `127.0.0.1:9000`。

---

## 4. 连接 MCP 客户端

### Claude Desktop

安装器会自动写好。手动配置则编辑
`%APPDATA%\Claude\claude_desktop_config.json`（Windows）或
`~/Library/Application Support/Claude/claude_desktop_config.json`（macOS）：

```json
{
  "mcpServers": {
    "fusion360": {
      "command": "C:\\路径\\self-host-fusion360-mcp\\.venv\\Scripts\\fusion-mcp.exe"
    }
  }
}
```

（跨平台写法：`"command": "/路径/.venv/bin/python", "args": ["-m", "fusion_mcp"]`。）
完全退出并重开 Claude Desktop，输入框会出现工具图标。

### Claude Code

```bash
# stdio（本地）
claude mcp add fusion360 -- /路径/.venv/bin/fusion-mcp
# 或 HTTP（例如 Docker 服务器）
claude mcp add --transport http fusion360 http://localhost:8765/mcp
```

### 远程 / HTTP 连接器（Docker、claude.ai）

用 `--transport http`（或 Docker 镜像）运行，在 Claude 里添加**自定义连接器**，
地址 `http://<主机>:8765/mcp`。注意 Claude 云端需能访问该地址（暴露与安全见故障排查）。

---

## 5. 验证

```bash
fusion-mcp doctor          # 双语诊断
fusion-mcp tools           # 列出所有已注册工具
fusion-mcp doctor --mock   # 无 Fusion 的健全性检查
```

全部通过意味着：桥可达、令牌一致、核心算子齐全、且有活动设计。然后对 Claude 说：
*"在 Fusion 里创建一个 20×20×10 毫米的盒子，给顶部边倒 2 毫米圆角，然后截图。"*

---

## 6. 用法

**工具内置的约定：**
- 所有距离单位为**毫米**，角度为**度**。
- 用**索引或名称**引用实体/草图（`fusion_summary`、`fusion_list_bodies`）。
- 典型流程：`草图 → 拉伸/旋转 → 圆角/倒角/抽壳/阵列 → 截图 → 导出`。
- 可能修改的尺寸优先用**参数**（`fusion_create_parameter`、`fusion_set_parameter`）。

**示例提示语：**
- "做一个 40×40×40 毫米的立方体，抽壳成 2 毫米壁厚，导出 STL 到桌面。"
- "做一个参数化法兰：直径 80 毫米、厚 10 毫米的圆盘，在 60 毫米圆周上开六个 6 毫米螺栓孔。"
- "把 `width` 参数设为 50 毫米，给我看结果。"
- "把这个轮廓绕 Z 轴旋转 360°。"

**让它"看见"：** `fusion_screenshot` 返回 Claude 能查看的图片——信任尺寸前先让它"给我看看模型"。

---

## 7. 工具

约 46 个工具，覆盖：文档、查询、参数、草图、特征（拉伸、旋转、圆角、倒角、抽壳、
阵列、镜像）、实体、基准面、材质/外观、导出（STL/STEP/IGES/F3D/3MF）、视口、单位，
以及受控的 `fusion_run_script`。带参数的完整参考见 [TOOLS.md](TOOLS.md)
（用 `python scripts/gen_tools_doc.py` 重新生成）。

---

## 8. 配置

| 变量 | 默认值 | 含义 |
|---|---|---|
| `FUSION_ADDIN_URL` | `http://127.0.0.1:9000` | 服务器 → 加载项地址（Docker 用 `http://host.docker.internal:9000`） |
| `FUSION_MCP_TOKEN` / `FUSION_MCP_TOKEN_FILE` | `~/.fusion-mcp/token` | 共享令牌（解析顺序） |
| `FUSION_MCP_TIMEOUT` | `30` | 单次调用超时（秒） |
| `FUSION_MCP_TRANSPORT` | `stdio` | `stdio` 或 `http` |
| `FUSION_MCP_HTTP_HOST` / `_PORT` | `0.0.0.0` / `8765` | HTTP 监听 |
| `FUSION_MCP_ALLOW_ARBITRARY_CODE` | `0` | 暴露 `fusion_run_script` |
| `FUSION_MCP_MOCK` | `0` | 无 Fusion 运行 |
| `FUSION_MCP_LOG_LEVEL` | `INFO` | 日志级别（始终输出到 stderr） |

**加载项**读取 `~/.fusion-mcp/addin.json`（`port`、`bind`、`allow_arbitrary_code`、`request_timeout`）。

---

## 9. 安全与任意代码

- 桥默认仅回环 + 令牌鉴权。
- `fusion_run_script` 在 Fusion 内执行任意 Python。要启用，必须**同时**：用
  `--allow-arbitrary-code` 启动服务器，**并**在 `~/.fusion-mcp/addin.json` 设
  `"allow_arbitrary_code": true`。不需要就别开。
- 连接器会改动你的实时模型。批量编辑前先存版本；信任 AI 生成的几何前先复核/打印
  （0.1mm 误差就会让配合失效）。

---

## 10. 更新 / 卸载

```bash
git pull && pip install -e .                       # 更新服务器
# 重新把 addin/Fusion360MCP 复制进 AddIns 目录，或重跑安装器

powershell -File install\windows-uninstall.ps1     # 移除加载项 + Claude 条目
powershell -File install\windows-uninstall.ps1 -Purge   # 同时删除 venv + ~/.fusion-mcp
```
