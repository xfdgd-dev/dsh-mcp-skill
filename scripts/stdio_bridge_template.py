#!/usr/bin/env python3
"""MCP stdio 桥接器骨架 —— 复制走，改 TODO 就行。

要点（都是踩过坑总结出来的，别改）：
1. stdout 只放 JSON-RPC，一行一条；日志全部走 stderr。
2. 强制 UTF-8：Windows 管道默认是系统代码页（中文机 cp936），不改就会乱码。
3. 延迟连接后端：每次工具调用才连，后端不在也不影响 MCP 客户端启动。
   （DSH 启动时会先起一个临时探测进程做 initialize，早连必炸。）
4. stdin 读到 EOF 就退出，别留常驻僵尸进程。
"""

from __future__ import annotations

import json
import sys
import traceback

PROTOCOL_FALLBACK = "2025-06-18"
SERVER_NAME = "my-backend"
SERVER_VERSION = "0.1.0"


def log(*args: object) -> None:
    print("[bridge]", *args, file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# TODO(1): 把这里换成你后端的调用方式。
# 返回一个 dict，可以是任意 JSON 可序列化的结果；抛异常即视为工具失败。
# 注意：每次调用才建连接，不要在这做模块级连接。

def call_backend(tool: str, args: dict) -> dict:
    raise NotImplementedError(
        f"还没接后端：tool={tool!r} args={args!r}\n"
        "改 call_backend()，常见两种形态：\n"
        "  - TCP：socket.create_connection((host, port)) 发自定义协议\n"
        "  - 子进程：subprocess.run([...], capture_output=True)\n"
    )


# ---------------------------------------------------------------------------
# TODO(2): 换成本后端的真实工具清单。inputSchema 必须是合法 JSON Schema。

TOOLS = [
    {
        "name": "ping",
        "description": "连通性检查：确认桥接器和后端都活着。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "do_thing",
        "description": "示例工具：换成你要暴露的能力，描述写给模型看。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "参数说明"},
            },
            "required": ["query"],
        },
    },
]


def run_tool(name: str, args: dict) -> dict:
    if name == "ping":
        return {"content": [{"type": "text", "text": "pong"}], "isError": False}
    try:
        payload = call_backend(name, args)
    except Exception:  # noqa: BLE001 - 错误要回给模型，不是崩掉进程
        return {
            "content": [{"type": "text", "text": "调用后端失败：\n" + traceback.format_exc()}],
            "isError": True,
        }
    return {
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}],
        "isError": False,
    }


# ---------------------------------------------------------------------------
# JSON-RPC over stdio（这部分基本不用改）

def handle(msg: dict) -> dict | None:
    method = msg.get("method")
    msg_id = msg.get("id")
    params = msg.get("params") or {}

    if msg_id is None:  # 通知：不回包
        return None

    if method == "initialize":
        requested = params.get("protocolVersion")
        version = requested if isinstance(requested, str) and requested else PROTOCOL_FALLBACK
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        if not isinstance(args, dict):
            return {"jsonrpc": "2.0", "id": msg_id,
                    "error": {"code": -32602, "message": "arguments 必须是对象"}}
        return {"jsonrpc": "2.0", "id": msg_id, "result": run_tool(str(name), args)}

    if method in ("resources/list", "resources/templates/list"):
        return {"jsonrpc": "2.0", "id": msg_id,
                "result": {"resources": [], "resourceTemplates": []}}

    if method == "prompts/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"prompts": []}}

    return {"jsonrpc": "2.0", "id": msg_id,
            "error": {"code": -32601, "message": f"未实现的方法：{method}"}}


def main() -> int:
    # 关键：Windows 管道默认 ANSI 代码页，不设 UTF-8 会毁中文
    for stream in (sys.stdin, sys.stdout):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass

    log(f"ready: {SERVER_NAME} {SERVER_VERSION}")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as ex:
            log("bad json:", ex)
            continue
        try:
            reply = handle(msg)
        except Exception:  # noqa: BLE001
            reply = {"jsonrpc": "2.0", "id": msg.get("id"),
                     "error": {"code": -32603, "message": "内部错误：\n" + traceback.format_exc()}}
        if reply is not None:
            sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    log("stdin closed, exiting")
    return 0


if __name__ == "__main__":
    sys.exit(main())
