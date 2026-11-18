# Changelog

All notable changes to this skill are documented here.

## [1.0.0] - 2026-11-14

首次发布。

### 包含

- **SKILL.md** —— 6 条硬事实、四步接入流程、排错对照表、回滚步骤、禁止事项
- **scripts/stdio_bridge_template.py** —— stdio 桥接器骨架，带「延迟连接后端」和「强制 UTF-8」两处关键实现
- **scripts/asar_extract.py** —— Electron `app.asar` 解包器，用来查 DSH 未写进文档的插件 schema
- **install.ps1** —— 一步装进 `%DSH_HOME%\skills`
- **docs/hero.png** —— README 首屏图（一行安装 + 三条卖点 + 实测命令）

### 背景

由一次真实的 MCP 接入总结而成：把 Blender 的数字孪生桥接进 DeepSeek Harness。

过程中踩到的、已写进 skill 的坑：

1. `cordis.patch.yml` 顶层条目是「按 id 覆盖」，`id` 不存在时只 warn 一句就跳过——**新增插件必须用 `- insert:`**。这个结论是解开 `app.asar` 读 `applyEntryPatches()` 源码确认的。
2. stdio server 若在启动时就去连后端，DSH 的临时探测进程会连不上，导致整个插件静默不激活。必须延迟连接。
3. Windows 管道默认走系统代码页（中文机 cp936），不强制 UTF-8 会把中文参数变成乱码甚至 JSON 解析失败。
4. `toolCallTimeoutMs` 默认只有 60000，长任务会被截断。
5. 改完 profile 会热重载，不必重启应用。
