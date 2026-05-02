import os
import sys
import uvicorn
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# 确保能找到 agent 目录下的模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.routes import router as api_router

app = FastAPI(title="医院智能排班与调班助手 API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 路由
app.include_router(api_router)

# 静态文件（前端）
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    print(f"启动服务器: http://localhost:{port}")
    print(f"API 文档: http://localhost:{port}/docs")
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=True)
