"""
代理路由模块

提供 OpenAI Responses API ↔ DeepSeek Chat API 的流式转发端点。
"""

import uuid

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.config import MODEL_DEFAULT, DEEPSEEK_DEBUG
from services.converter import extract_messages
from services.stream import create_sse_generator, _log_debug

router = APIRouter()


async def _handle_proxy(request: Request):
    """处理 /responses 系列请求的核心逻辑"""
    req_data = await request.json()
    messages, tools, tool_choice = extract_messages(req_data)
    # 中间件 resolve_model 已解析的模型优先级最高
    effective_model = (
        getattr(request.state, "resolved_model", None)
        or req_data.get("model")
        or MODEL_DEFAULT
    )
    response_id = f"resp_{uuid.uuid4().hex[:12]}"

    if DEEPSEEK_DEBUG:
        _log_debug(req_data, messages, tools, tool_choice, request.url.path)

    stream_gen = create_sse_generator(
        messages, tools, tool_choice, effective_model, response_id, debug_path=request.url.path
    )

    return StreamingResponse(
        stream_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/responses")
async def route_responses(request: Request):
    """OpenAI Responses API 格式的流式代理端点"""
    return await _handle_proxy(request)


@router.post("/v1/responses")
async def route_v1_responses(request: Request):
    """OpenAI Responses API (v1) 格式的流式代理端点"""
    return await _handle_proxy(request)


@router.post("/v1/chat/completions")
async def route_v1_chat(request: Request):
    """Chat Completions API 格式的流式代理端点（兼容模式）"""
    return await _handle_proxy(request)
