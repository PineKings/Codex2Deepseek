"""路由注册入口

参照 PineSoundDesktop 项目结构，通过 register_routes() 统一注册所有路由。
"""

from .proxy import router


def register_routes(app):
    """注册所有 API 路由"""
    app.include_router(router)
