# self-host-fusion360-mcp

**一个自托管、统一的 MCP 服务器，让 Claude（或任意 MCP 客户端）在你自己的电脑上驱动 Autodesk Fusion 360。**

[English](README.md) · [完整手册](docs/manual.zh-CN.md) · [工具参考](docs/TOOLS.md) · [故障排查](docs/TROUBLESHOOTING.zh-CN.md)

![通过本 MCP，由 Claude 对话端到端在 Fusion 360 中建出的 L 形支架](docs/images/bracket.png)

<sub>完全由一段 Claude 对话通过本 MCP 建出的 L 形支架——底板 + 立板 + 布尔合并 + 圆角 + 4 个安装孔 + 质量核算 + 导出。见 [scripts/demo_conversation.py](scripts/demo_conversation.py)。</sub>

它把社区各个 Fusion-MCP 项目的优点整合进一个**文档齐全、防呆**的包里：**中英双语文档、Windows 一键安装、Docker 一条命令、毫米优先、自动生成的共享令牌、约 100 个工具(外加全覆盖的通用 API 直通)、自动建文档、以及能精确告诉你哪里出错的 `doctor`。** 无需 Fusion 订阅——免费的个人使用版也能用。

> ✅ **已在真实 Fusion 360 上验证**（2026 年 1 月版本，Python 3.14）：一套 57 步全覆盖测试 + 一个完整的螺栓圆法兰建模都端到端通过，质量/体积经数值核对无误。详见[开发与测试](#开发与测试)。

---

## 工作原理（务必先读）

Fusion 的 `adsk.*` API **只能在 Fusion 内部、主线程上调用**——外部进程无法直接碰它。所以本项目分**两部分**：

```
┌────────────────┐   MCP (stdio / http)   ┌─────────────────────┐  HTTP + 令牌   ┌──────────────────────────┐
│ Claude          │ ─────────────────────▶ │  MCP 服务器           │ ──────────────▶ │  Fusion 加载项（进程内）    │
│ Desktop / Code  │ ◀───────────────────── │ （本仓库 server/）     │ ◀────────────── │ （本仓库 addin/）          │
└────────────────┘                         │  裸跑 或 Docker        │                 │  127.0.0.1，主线程执行      │
                                            └─────────────────────┘                 └─────────────┬────────────┘
                                                                                                  │ adsk.* API
                                                                                            ┌─────▼─────┐
                                                                                            │ Fusion 360 │
                                                                                            └───────────┘
```

> ⚠️ **Fusion 无法跑在 Docker 里。** 它是桌面 GUI 程序。Docker 只容器化 **MCP 服务器**；**加载项必须装在宿主机、跑在 Fusion 进程内**。Docker 中服务器通过 `host.docker.internal` 连回宿主加载项。这是最常见的困惑点——安装器和 `doctor` 会反复提醒。

---

## 特性

- **两种传输**——`stdio`（Claude Desktop / Claude Code）与 `streamable-http`（Docker / 远程）。
- **约 100 个工具**——一键基本体（box/cylinder/sphere）、草图（矩形/圆/线/弧/多边形/样条,可在基准面**或实体表面**上)**含几何约束与标注**(稳健参数化)、拉伸/旋转/扫掠/放样、圆角/倒角/抽壳/钻孔/拔模/缩放、分割/偏移面、螺纹、矩形与环形阵列、镜像、布尔合并、参数、实体操作、构造面、外观、曲面(patch/thicken/ruled/stitch)、检查(物性/最小距离/夹角/干涉/面列表)、时间线编辑(撤销/重做/抑制)、导出(STL/STEP/F3D/DXF)、Claude 能"看见"的视口截图、单位、**装配**(组件、关节、刚性组)、**CAM**(setup、工序、自动选刀、刀路、G 代码后处理)。
- **通用 API 直通**——`fusion_api_call` / `fusion_api_introspect` / `fusion_api_docs` 可按路径调用**任意 `adsk.*`** 方法(curated 工具未覆盖的全部能力,如钣金)。受 `allow_arbitrary_code` 门控。
- **自动建文档**——建模工具在没有打开文档时会自动新建设计；这是社区项目都没有的。
- **毫米优先**——所有尺寸都是毫米；厘米换算只在边界做一次（杜绝 10× 错误）。
- **工具注解**——只读/破坏性/幂等提示，客户端可自动批准安全调用。
- **防呆搭建**——自动生成共享令牌（无需手动拷贝）、安全合并 Claude 配置（保留你的其他服务器）、安装器可重复运行、为中文 Windows 处理 UTF-8/GBK 编码。
- **Web 配置面板**——`fusion-mcp webui` 打开本地浏览器界面:看状态、改设置、管理令牌、并为多种 AI(Claude Desktop/Code、Cursor、VS Code、通用、远端 HTTP)生成或一键写入 MCP 客户端配置。仅回环、零新依赖。
- **`doctor` 自检**——双语诊断，精确定位连接/令牌/版本问题。
- **mock 模式**——**无需安装 Fusion** 也能跑服务器、测试、Docker 镜像。
- **双语文档**——全部提供英文与简体中文。
- **默认安全**——任意代码执行工具**默认关闭**，需显式开启。

---

## 快速开始

### 方式 A — Windows 一键（推荐）

1. 安装 Fusion 360 与 [Python 3.10+](https://www.python.org/downloads/)（勾选 *Add to PATH*）。
2. 双击 **`install/windows-install.bat`**（或在 PowerShell 里运行 `install/windows-install.ps1`）。
   它会把加载项复制进 Fusion、生成令牌、安装服务器、并合并你的 Claude Desktop 配置。
3. 启动 Fusion 360，打开一个设计，进入 **实用程序 → 加载项 → 脚本和加载项**，选择 **Fusion360MCP**，点 **运行**（设为"启动时运行"即可一劳永逸）。
4. 完全退出并重新打开 **Claude Desktop**。试着说：*"在 Fusion 里创建一个 20×20×10 毫米的盒子，并加 2 毫米圆角。"*

### 方式 B — Docker（服务器在容器里）

加载项仍需装在宿主（上面的 1–3 步，或直接把 `addin/Fusion360MCP/` 复制进 Fusion 的 `API/AddIns` 目录）。然后：

```bash
cp .env.example .env          # 把 FUSION_MCP_TOKEN 设为宿主令牌（~/.fusion-mcp/token 的内容）
docker compose up -d          # 服务器监听 http://localhost:8765/mcp
docker compose run --rm fusion-mcp fusion-mcp doctor   # 自检
```

在 Claude 里把它作为**自定义（远程/HTTP）连接器**添加，地址 `http://localhost:8765/mcp`。

### 方式 C — 手动 / 跨平台

```bash
pip install -e .                         # 或： pip install -e ".[http,dev]"
# 把 addin/Fusion360MCP 文件夹复制到 <Fusion>/API/AddIns/
fusion-mcp doctor                        # 诊断
fusion-mcp run                           # stdio（让客户端启动这个命令）
```

精确的 Claude 配置 JSON 与 Fusion AddIns 路径见[完整手册](docs/manual.zh-CN.md)。

### Web 配置面板

```bash
fusion-mcp webui          # 自动打开 http://127.0.0.1:8088
```

一个本地、仅回环的页面:查看桥接状态、编辑加载项设置、查看/重新生成令牌,并为
Claude Desktop、Claude Code、Cursor、VS Code、通用客户端或远端/HTTP 连接器
**生成或一键写入** MCP 配置。以后接入新 AI,只需在 `fusion_mcp.clientconfig.CONNECTORS`
里加一条目。

![fusion-mcp webui 本地配置面板](docs/images/webui.png)

---

## 配置

均为可选，下表为默认值。详见 [.env.example](.env.example)。

| 变量 | 默认值 | 含义 |
|---|---|---|
| `FUSION_ADDIN_URL` | `http://127.0.0.1:9000` | 服务器连加载项的地址（Docker 用 `http://host.docker.internal:9000`） |
| `FUSION_MCP_TOKEN` / `FUSION_MCP_TOKEN_FILE` | `~/.fusion-mcp/token` | 共享令牌（按此顺序解析） |
| `FUSION_MCP_TRANSPORT` | `stdio` | `stdio` 或 `http` |
| `FUSION_MCP_HTTP_HOST` / `_PORT` | `0.0.0.0` / `8765` | HTTP 监听地址（http 传输） |
| `FUSION_MCP_ALLOW_ARBITRARY_CODE` | `0` | 暴露 `fusion_run_script`（有风险） |
| `FUSION_MCP_MOCK` | `0` | 无 Fusion 运行 |

---

## 安全与限制

- **务必复核。** Claude 擅长棱柱/参数化零件与重复性编辑，对有机/自由曲面较弱。0.1mm 的偏差就会让配合失效——信任输出前请复核（最好打印验证）。
- 连接器会**改动你的实时模型**。批量操作前先存一个版本。
- `fusion_run_script` 在 Fusion 内执行任意 Python，默认关闭，需显式开启。
- 桥绑定在 `127.0.0.1` 并要求 bearer 令牌。在暴露给 Docker/其他主机前请先读[故障排查](docs/TROUBLESHOOTING.zh-CN.md)。
- **许可限制：** IGES/SAT 导出在**个人使用版**许可下被禁用（桥会返回清晰提示）；STEP/STL/F3D 在所有许可下都可用。3MF 没有 Fusion API、未暴露——3D 打印请用 STL。
- **CAM 前置条件：** `cam_*` 工具需要先在 Fusion 里打开过一次**「制造」工作区**（CAM 产品才会存在），否则返回清晰提示。多数工序策略还需先指定刀具,刀路才能生成。

---

## 开发与测试

以下脚本就是用来在真实 Fusion 上验证本项目的。

```bash
# 1) 直接对实时桥调用任意算子（自动读取 ~/.fusion-mcp/token）
python scripts/rpc.py health
python scripts/rpc.py primitive.box '{"width":20,"depth":20,"height":20}'

# 2) 全覆盖测试（新建文档 → 约 57 项检查，覆盖每个工具）
python scripts/smoketest.py

# 3) 真实零件端到端：螺栓圆法兰（含检查与导出）
python scripts/demo_flange.py        # 生成 screenshots/flange.png

# 4) mock 单元测试（无需 Fusion）
python -m pytest -q
```

**热重载循环（无需重启 Fusion）。** 加载项入口在 Stop→Run 时清除本包模块缓存,
并提供一个开发用算子 `system.reload`——它会就地重新导入**全部**算子代码(含
`_common`)。于是"改→测"循环是:

```bash
cp -r addin/Fusion360MCP/. "$APPDATA/Autodesk/Autodesk Fusion 360/API/AddIns/Fusion360MCP/"
python scripts/rpc.py system.reload   # 热载改动后的加载项代码
python scripts/smoketest.py           # 重测
```

只有改动 HTTP/桥层（`bridge/`、`config.py`、`__init__.py`）才需要在 Fusion 里
**Stop→Run**；算子改动用 `system.reload` 即可生效。

---

## 状态与路线图

**已完成(v0.5.0)** —— 下列每个工具都已在**真实 Fusion 360**(2026/01 版本,Python 3.14)上验证:

- **活动零部件** —— 多零件模型在**一个文档**里完成:`assembly.activate_component` 让后续 sketch/feature/primitive 等算子建到该零部件(各零件隔离、不动现有物件);默认仍是根部件。
- **自动关闭挡路弹窗** —— 外部守护进程关掉 保存/恢复/服务器验证/误弹 等会冻结 Fusion 的模态(它们独占 GIL,进程内看门狗无效);WM_CLOSE 优先(=取消,不保存、不丢数据),仅在算子卡住或标题命中滋扰白名单时动作。
- **`system.restart`** —— 通过 RPC 在**进程内**整体重载(含 bridge/`__init__`),改代码**无需手动 Stop→Run**。


- 两段式架构(Fusion 进程内加载项桥 + 外部 MCP 服务器);**stdio** 与 **streamable-http** 两种传输;**mock 模式**(无需 Fusion)。
- **约 100 个工具**:基本体;草图**含几何约束与标注**;拉伸/旋转/扫掠/放样;圆角/倒角/抽壳/钻孔/拔模/分割/偏移面/螺纹/缩放;矩形与环形阵列;镜像;布尔合并;曲面(patch/thicken/ruled/stitch);参数;实体操作;构造面;外观;检查(质量、最小距离、夹角、干涉、面列表);时间线编辑(撤销/重做/抑制);导出(STL/STEP/F3D/DXF);视口截图;单位;**装配**(组件、关节含按面定位、刚性组);**CAM**(setup、工序、自动选刀、刀路、G 代码后处理)。
- **通用 API** 直通(`api.call`/`introspect`/`docs`,受控)实现全覆盖。
- 自动建文档、毫米优先、变更 `_delta` 反馈、双语错误提示。
- 防呆 **Windows 安装器**、**Docker**、`doctor`、**热重载**开发循环。
- **Web 配置面板**(`fusion-mcp webui`)+ 多 AI 连接器注册表。
- 28 个 mock 测试;中英双语文档。

**后续 TODO / 路线图:**

- [ ] CAM 端到端验证(需制造工作区 + 刀具库):setup → 工序 → 刀路 → G 代码。
- [ ] curated **钣金创建** —— 目前受 Fusion API 限制(FlangeFeatures/BendFeatures 无创建方法),待 Autodesk 开放后再补。(现仅 `create_flat_pattern` 对已有钣金体可用。)
- [ ] 关节**按边/轴**定位、关节限位与运动。
- [ ] **工程图**(2D 图纸文档、自动视图)+ 更完整的 DXF/PDF 导出。
- [ ] 「一键写入」扩展到 **Cursor / VS Code** 的实际配置文件(目前仅 Claude Desktop)。
- [ ] Web 面板**一键启动器**(`.bat`)+ 可选系统托盘。
- [ ] **macOS 安装器**(`.command`)与 Windows 安装器对齐。
- [ ] 发布到 **PyPI**(`uvx fusion-mcp`)+ 签名发布。
- [ ] **webui API** 的测试 + 更多算子级 mock。
- [ ] 随生态发展接入**更多 AI 连接器**。

## 目录结构

```
addin/Fusion360MCP/   Fusion 进程内加载项（纯标准库）：HTTP 桥 + 主线程分发 + 算子
server/fusion_mcp/    MCP 服务器：FastMCP 应用、工具、客户端、doctor、CLI
install/              Windows 安装器、令牌生成、安全合并 Claude 配置
docs/                 双语手册、架构、工具参考、故障排查
scripts/              开发辅助：rpc.py、smoketest.py、demo_flange.py、doctor、gen_tools_doc
tests/                mock 驱动的测试（无需 Fusion）
```

## 许可

MIT，见 [LICENSE](LICENSE)。本项目与 Autodesk、Anthropic 无任何隶属或背书关系。
