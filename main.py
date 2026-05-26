#!/usr/bin/env python3
"""
OpenAI Responses API ↔ DeepSeek Chat API 流式转发代理
启动:
    python main.py --port 12345
"""

import argparse
import sys

# ===================== 命令行参数 =====================
parser = argparse.ArgumentParser(description="Codex DeepSeek Proxy")
parser.add_argument(
    "--port", type=int, default=12345, help="服务运行端口，默认 12345"
)
parser.add_argument(
    "--host", type=str, default="0.0.0.0", help="绑定地址，默认 0.0.0.0"
)
parser.add_argument(
    "--debug",
    action="store_true",
    help="启用调试日志（覆盖 DEEPSEEK_DEBUG 环境变量）",
)
args = parser.parse_args()

# ===================== 初始化 API Key =====================
# 必须在 FastAPI 应用创建前完成，因为 config 模块在 import 时加载 .env
from app.config import ensure_api_key, ensure_my_api_key

key = ensure_api_key()
if not key:
    sys.exit(1)

my_key = ensure_my_api_key()
if not my_key:
    sys.exit(1)

# ===================== FastAPI 应用创建 =====================
from fastapi import FastAPI

from routers import register_routes
from routers.lifespan import create_lifespan
from routers.middleware import setup_middleware

app = FastAPI(
    title="Codex DeepSeek Proxy",
    description="OpenAI Responses API ↔ DeepSeek Chat API 流式转发代理",
    version="0.2.0",
    lifespan=create_lifespan,
)

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "ok"}

# 配置中间件
setup_middleware(app)

# 注册路由
register_routes(app)

# ===================== 服务启动 =====================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        access_log=True,
    )
