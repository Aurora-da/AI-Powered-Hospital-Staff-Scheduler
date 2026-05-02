#!/usr/bin/env python3
"""启动 Web 管理界面 - http://localhost:8000"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False)
