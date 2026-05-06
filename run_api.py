#!/usr/bin/env python3
"""启动 Web 管理界面 - http://localhost:8000"""
import sys
import os
import socket
import argparse

import uvicorn

DEFAULT_PORT = 8000


def _port_in_use(port: int) -> bool:
    """检测端口是否被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def _kill_port_process(port: int):
    """尝试释放被占用的端口（Windows only）"""
    if sys.platform != "win32":
        return
    try:
        import subprocess
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.splitlines():
            if f":{port} " in line and "LISTENING" in line:
                pid = line.strip().split()[-1]
                subprocess.run(
                    ["taskkill", "/F", "/PID", pid],
                    capture_output=True, timeout=10
                )
    except Exception:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="医院智能排班 Web 服务")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"服务端口（默认: {DEFAULT_PORT}）")
    args = parser.parse_args()

    port = int(os.getenv("PORT", str(args.port)))

    if _port_in_use(port):
        print(f"\n  WARNING  端口 {port} 已被占用，尝试释放...")
        _kill_port_process(port)
        if _port_in_use(port):
            print(f"\n  ERROR  端口 {port} 仍被占用，请手动关闭占用进程后重试\n")
            sys.exit(1)
        print(f"  OK  端口 {port} 已释放\n")

    print(f"\n  医院智能排班系统启动中...")
    print(f"  访问地址: http://localhost:{port}")
    print(f"  API 文档: http://localhost:{port}/docs\n")

    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=False)
