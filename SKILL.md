---
name: mcp-setup
description: 给 DeepSeek Harness（DSH）接入一个 MCP 服务器（俗称「装 MCP 插件」）：复用或手写 stdio 桥接器，在 profile 的 cordis.patch.yml 里用 insert 语法注册 @deepseek-ai/dsh-mcp-client，处理 UTF-8、超时、热重载和排错。用户说「装 MCP 插件」「给 DSH 接个 MCP」「让 DSH 能调用 Blender / 浏览器 / 数据库」「配 mcpServers」「MCP 工具没出现」「mcp__xxx__ 调用失败」「接个 MCP 服务器」时使用。
---

# 给 DSH 装一个 MCP 服务器

本 skill 的全部结论来自一次真机实战（2026-11-14 接 Blender），不是文档推测。**文档和直觉在这件事上会骗你，以本文件和源码为准。**

## 一、先记住这 6 条硬事实

| # | 事实 | 踩错的表现 |
|---|---|---|
| 1 | 配置写在 `<DSH_HOME>\profiles\<DSH_PROFILE>\cordis.patch.yml`（环境变量 `DSH_HOME`、`DSH_PROFILE` 里就有） | 写到别处，永远不生效 |
| 2 | 新增插件**必须**包在 `- insert:` 列表里 | 写了但啥都没发生，**不报错**，只记一条 warn |
| 3 | 插件名固定 `@deepseek-ai/dsh-mcp-client`，随 DSH 已安装，**不需要 npm install** | 去装包、改 package.json，白费 |
| 4 | `serverName` 必须匹配 `^[A-Za-z0-9_-]{1,32}$`，且同一个 Agent 内不能重复 | 插件报错不激活 |
| 5 | 保存后 DSH **热重载** profile，通常不用重启应用 | 白白重启、丢掉会话上下文 |
| 6 | 工具在模型侧叫 `mcp__<serverName>__<tool>` | 找错名字，以为没装上 |

**第 2 条是最大的坑，单独解释**：`cordis.patch.yml` 的顶层条目语义是「按 id 覆盖已有插件配置」（见 `cordis-plugin-include` 的 `applyEntryPatches()`）。`id` 找不到时只 `warn("patch: entry %C not found")` 然后 `continue`——静默跳过。**新增只能走 `insert`。**

## 二、四步流程

### 步骤 1：判断有没有现成的 stdio server

MCP 客户端要的是「能从 stdin 读 JSON-RPC、往 stdout 写」的程序。

- 官方提供的 `xxx-mcp` / `npx -y xxx-mcp` / `uvx xxx-mcp` → 直接用，跳到步骤 3
- 后端是私有协议（比如 Blender 那个 9876 端口）、或者官方只有 HTTP/SSE 而你想本地跑 → 自己写个薄桥接器，见步骤 2

### 步骤 2：写 stdio 桥接器（要有这 5 个特性）

骨架直接抄 `scripts/stdio_bridge_template.py`。必须做到：

1. **逐行 JSON-RPC**：一行一条消息，`stdout` 只放协议消息，日志一律走 `stderr`
2. **实现 initialize / notifications/initialized（不回包）/ tools/list / tools/call / ping**
3. **强制 UTF-8**：Windows 管道默认是系统代码页（中文机是 cp936），不处理就会把中文对象名变成乱码、甚至 JSON 解析失败。在入口 `sys.stdin.reconfigure(encoding="utf-8")`、`sys.stdout.reconfigure(...)`，并在配置里加 `PYTHONUTF8=1` / `PYTHONIOENCODING=utf-8`
4. **延迟连接后端**：DSH 启动 stdio server 时会**先起一个临时探测进程**做 initialize 协商。如果 server 一启动就去连后端，后端没开就会导致探测失败、整个插件不激活。正确做法是「每次工具调用才连」，后端随时能重启
5. **stdin EOF 就退出**，别留僵尸进程

### 步骤 3：写配置

先备份，再追加。**注意 `- insert:` 的缩进是 4 空格**：

```yaml
- insert:
    - id: mcp-<短名>
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        transport: stdio
        serverName: <短名>              # ^[A-Za-z0-9_-]{1,32}$
        command: 'C:\绝对路径\python.exe'   # 必须是绝对路径
        args:
          - 'C:\绝对路径\bridge.py'
        cwd: 'C:\绝对路径'
        env:
          PYTHONUTF8: '1'
          PYTHONIOENCODING: 'utf-8'
        toolCallTimeoutMs: 300000      # 默认只有 60 秒，长任务必须调大
        failOnStartupError: true       # 建议 true，失败会显式报错而不是静默少工具
```

HTTP 型把 `transport: stdio` 换成 `streamable-http`，用 `url` + `headers`，不要 `command`。

**写这个文件在工作区外，正常需要提权**（`sandbox_permissions: danger-full-access`）。

### 步骤 4：验证

1. 等 5–15 秒（热重载），或者让用户重启应用
2. 先打最便宜的那一枪——`mcp__<名字>__<轻量工具>`，不要一上来就跑重活
3. 想确认「插件到底起没起」：看有没有**子进程**在跑（stdio server 是常驻进程）

## 三、排错对照表

| 现象 | 原因 | 处理 |
|---|---|---|
| 工具没出现，配置看着没问题 | ① 没写 `insert` ② `serverName` 不合法 ③ YAML 缩进错 | 逐条核对；改完等热重载 |
| 工具出现了，但调用报「连不上后端」 | 后端没启动 / 端口不通 | 先起后端；桥接器要延迟连接 |
| 中文全变成 `锟斤拷` / `����` | 管道编码没设 | 补 `reconfigure` + 两个环境变量 |
| 长任务总是超时 | `toolCallTimeoutMs` 默认 60000 | 调到需要的值 |
| 插件整个不激活 | `failOnStartupError: true` 且探测失败 | 看 DSH 日志；先把 `failOnStartupError` 改 false 定位 |
| 改了配置没反应 | 只改了 bundle 层，或改错 profile | 确认改的是 `profiles/<DSH_PROFILE>/cordis.patch.yml` |

**手动验桥接器**（不经过 DSH，最快定位是 server 的锅还是配置的锅）：

```powershell
@(
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}',
  '{"jsonrpc":"2.0","method":"notifications/initialized"}',
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
) | & 'C:\绝对路径\python.exe' 'C:\绝对路径\bridge.py'
```

能看到 `initialize` 和 `tools` 的回复，说明 server 没问题，问题在配置。

## 四、想读 DSH 源码怎么办

文档可能过时，真正的 schema 在 DSH 的 `app.asar` 里。本仓库自带解包器 `scripts/asar_extract.py`。

先找到 `app.asar`（Electron 应用一般是 `<安装目录>\resources\app.asar`，看启动快捷方式的属性就知道装在哪），然后：

```powershell
python scripts/asar_extract.py "C:\...\resources\app.asar" dsh-mcp-client
```

它会把匹配到的文件解到 `asar_unpack\`（路径里的 `/` 会换成 `__`，方便直接翻）。打开 `..._dsh-mcp-client__lib__index.js`，搜 `const Config = z.union([` —— 那就是完整字段真源，连默认值和正则约束都在里面。

同理，想搞清楚 patch 的确切语义，就解 `cordis-plugin-include` 看 `applyEntryPatches()`。**本 skill 里那 6 条硬事实就是这么来的。**

## 五、回滚

改之前先 `Copy-Item cordis.patch.yml cordis.patch.yml.bak`。要撤销就把 `.bak` 覆盖回去。删掉 `- insert:` 那一整块后，热重载即可卸载，工具会消失。

## 六、别做的事

- 不要为了「让配置生效」去重启 DSH 之外的东西
- 不要把 `command` 写成 `python`（PATH 里不一定有，DSH spawn 用的是绝对路径规则）
- 不要在 `stdout` 里 `print` 调试信息——会破坏 JSON-RPC 流
- 不要复用同一个 `serverName` 挂两个实例
