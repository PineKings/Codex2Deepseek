"""
中间件配置

参照 PineSoundDesktop 项目结构集中管理中间件。
"""

import json

from fastapi import Response
from fastapi.middleware.cors import CORSMiddleware

from app.config import MODEL_MAP, DEFAULT_MODEL, MY_API_KEY


def setup_middleware(app):
    """配置所有中间件

    Args:
        app: FastAPI 应用实例
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def auth_check(request, call_next):
        """验证请求携带的 API Key 是否合法"""
        # OPTIONS 预检请求跳过验证
        if request.method == "OPTIONS":
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
        else:
            token = ""

        if token != MY_API_KEY:
            return Response(
                content=json.dumps({
                    "error": {"message": "Invalid API Key", "type": "auth_error"},
                }),
                status_code=401,
                media_type="application/json",
            )

        return await call_next(request)

    @app.middleware("http")
    async def resolve_model(request, call_next):
        """拦截请求中的模型名称，按 MODEL_MAP 进行替换"""
        if request.method == "POST":
            body = await request.body()
            if body:
                try:
                    data = json.loads(body)
                    original = data.get("model")
                    if original:
                        resolved = MODEL_MAP.get(original, DEFAULT_MODEL)
                        request.state.resolved_model = resolved
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass
        response = await call_next(request)
        return response
