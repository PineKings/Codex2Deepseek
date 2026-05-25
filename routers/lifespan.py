"""
应用生命周期管理

通过 FastAPI lifespan 机制处理启动和关闭事件。
"""

from contextlib import asynccontextmanager


@asynccontextmanager
async def create_lifespan(app):
    """应用生命周期上下文管理器"""
    # ==================== 启动事件 ====================
    print("codex_deepseek_proxy starting ...")

    yield

    # ==================== 关闭事件 ====================
    print("codex_deepseek_proxy shutting down ...")
