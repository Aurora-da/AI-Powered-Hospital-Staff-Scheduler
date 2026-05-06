import os
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# 使用 __file__ 定位项目根目录 (始终可靠)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
# 也添加 agent 目录到 sys.path (由 routes.py 导入时使用)
_AGENT_DIR = _PROJECT_ROOT / "agent"
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_AGENT_DIR))

from backend.routes import router as api_router
from backend.auth import init_users

app = FastAPI(title="医院智能排班与调班助手 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

# 初始化用户系统
init_users()


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "医院智能排班系统"}


# ---- 前端静态文件服务 ----
FRONTEND_DIR = _PROJECT_ROOT / "frontend"


@app.get("/")
@app.head("/")
async def serve_root():
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return HTMLResponse(index.read_text(encoding="utf-8"))
    return HTMLResponse("Frontend not found", status_code=404)


@app.get("/css/{filepath:path}")
@app.head("/css/{filepath:path}")
async def serve_css(filepath: str):
    file = FRONTEND_DIR / "css" / filepath
    if file.is_file():
        return FileResponse(file, media_type="text/css")
    return HTMLResponse("", status_code=404)


@app.get("/js/{filepath:path}")
@app.head("/js/{filepath:path}")
async def serve_js(filepath: str):
    file = FRONTEND_DIR / "js" / filepath
    if file.is_file():
        return FileResponse(file, media_type="application/javascript")
    return HTMLResponse("", status_code=404)


@app.get("/{filename:path}")
@app.head("/{filename:path}")
async def serve_static(filename: str):
    """处理前端根目录的静态文件，以及 SPA fallback"""
    # 先尝试精确匹配文件
    file = FRONTEND_DIR / filename
    if file.is_file():
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        media_types = {
            "html": "text/html", "css": "text/css", "js": "application/javascript",
            "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "gif": "image/gif", "svg": "image/svg+xml", "ico": "image/x-icon",
            "json": "application/json", "woff2": "font/woff2", "ttf": "font/ttf",
        }
        return FileResponse(file, media_type=media_types.get(ext))
    # SPA fallback
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return HTMLResponse(index.read_text(encoding="utf-8"))
    return HTMLResponse("Not Found", status_code=404)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    print(f"启动服务器: http://localhost:{port}")
    print(f"API 文档: http://localhost:{port}/docs")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=False)
