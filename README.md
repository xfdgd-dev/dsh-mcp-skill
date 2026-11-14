# dsh-mcp-setup

给 [DeepSeek Harness](https://github.com/deepseek-ai)（DSH）接入 MCP 服务器的 skill。

一句话：**让 DSH 能调用外部工具**——Blender、浏览器、数据库、自家后端的私有协议——不用每次从头摸坑。

## 为什么有这个东西

DSH 接 MCP 的配置只有 20 行 YAML，但里面埋了几个**静默失败**的坑。最要命的一个：

> 在 `cordis.patch.yml` 里顶层写 `- id: xxx / name: xxx / config: ...` 是「按 id 覆盖已有插件」的语义。
> `id` 不存在时，代码只 `warn` 一句就 `continue`——**不报错、不生效、什么都不提示**。

这个结论不是从文档里抄的，是把 `app.asar` 解开读 `applyEntryPatches()` 源码确认的。本仓库把这些坑固化成了可复用的流程。

## 安装

skill 就是两个文件，放到 DSH 的 skill 目录即可（Windows 默认 `%USERPROFILE%\.dsh\skills`）：

```powershell
git clone https://github.com/<you>/dsh-mcp-setup "$env:USERPROFILE\.dsh\skills\mcp-setup"
```

或者用自带的安装脚本（不用 git）：

```powershell
.\install.ps1
```

装完**不用重启 DSH**——它的 skill provider 带文件监听，热加载。

## 用法

装好后在 DSH 里直接说：

> 装个 MCP 插件，把 xxx 接进来

或者显式调用：

```
/mcp-setup
```

DSH 的可用 skill 目录里会多出一项 `mcp-setup`，说明加载成功。

## 里面有什么

```
SKILL.md                          # 主指令：6 条硬事实 + 四步流程 + 排错表
scripts/stdio_bridge_template.py  # stdio 桥接器骨架，改 2 个 TODO 就能用
scripts/asar_extract.py           # Electron app.asar 解包器（查 DSH 真实 schema 用）
install.ps1                       # 复制到 ~/.dsh/skills/mcp-setup
```

## 覆盖的核心知识点

| # | 事实 |
|---|---|
| 1 | 配置在 `<DSH_HOME>\profiles\<DSH_PROFILE>\cordis.patch.yml` |
| 2 | 新增插件**必须**包在 `- insert:` 里，否则静默跳过 |
| 3 | 插件名 `@deepseek-ai/dsh-mcp-client` 随 DSH 已装，不需要 npm install |
| 4 | `serverName` 必须匹配 `^[A-Za-z0-9_-]{1,32}$`，同一 Agent 内不能重复 |
| 5 | 保存后热重载，通常不用重启应用 |
| 6 | 工具名是 `mcp__<serverName>__<tool>` |

外加：stdio 桥接器必须**延迟连接后端**（DSH 启动时会先起临时探测进程做 initialize，早连必炸）、Windows 管道要强制 UTF-8（否则中文乱码）、`toolCallTimeoutMs` 默认只有 60 秒。

## 适用环境

- Windows 10/11 上的 DSH 桌面版（路径、代码页相关的坑都按 Windows 写的）
- DSH 的 `stdio` 与 `streamable-http` 两种 transport
- 桥接器模板用 Python 3.9+（仅标准库，无第三方依赖）

## License

MIT
