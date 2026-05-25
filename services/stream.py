"""
SSE 流式生成模块

将 DeepSeek Chat Completions API 的流式响应转换为
OpenAI Responses API 格式的 SSE 事件流。
"""

import json
import uuid
from datetime import datetime

import requests

from app.config import DEEPSEEK_API_KEY, DEEPSEEK_URL, DEEPSEEK_DEBUG, DEBUG_LOG


def _log_debug(req_data, messages, tools, tool_choice, debug_path):
    """记录调试日志到文件"""
    with open(DEBUG_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n--- [{datetime.now()}] PATH={debug_path} ---\n")
        f.write(f"Request body:\n{json.dumps(req_data, indent=2, ensure_ascii=False)}\n")
        f.write(f"Messages:\n{json.dumps(messages, indent=2, ensure_ascii=False)}\n")
        if tools:
            f.write(f"Tools count: {len(tools)}\n")
            f.write(f"Tool choice: {tool_choice}\n")


def _log_debug_error(payload, messages, tools, err_msg, status_code, body):
    """记录错误调试日志"""
    with open(DEBUG_LOG, "a", encoding="utf-8") as f:
        f.write(f"ERROR: {err_msg}\n")
        f.write(f"Payload sent (tools={len(tools)}, msgs={len(messages)}):\n")
        payload_copy = dict(payload)
        payload_copy.pop("messages", None)
        payload_copy.pop("tools", None)
        f.write(json.dumps(payload_copy, indent=2, ensure_ascii=False) + "\n")
        f.write(f"Messages ({len(messages)}):\n")
        f.write(json.dumps(messages, indent=2, ensure_ascii=False)[:3000] + "\n")
        f.write(f"Tools ({len(tools)}):\n")
        tools_str = json.dumps(tools, indent=2, ensure_ascii=False)
        f.write(tools_str[:5000] + ("...(truncated)" if len(tools_str) > 5000 else "") + "\n")
        total_size = len(json.dumps(payload, ensure_ascii=False))
        f.write(f"Total payload size: {total_size} bytes ({total_size/1024:.1f} KB)\n")


def create_sse_generator(messages, tools, tool_choice, effective_model, response_id, debug_path=""):
    """创建 SSE 流式事件生成器

    Args:
        messages: 转换后的 Chat Completions 格式消息列表
        tools: 转换后的工具定义列表
        tool_choice: 工具选择策略
        effective_model: 使用的模型名称
        response_id: 响应 ID
        debug_path: 请求路径（用于调试日志）

    Returns:
        生成 SSE 事件字符串的生成器函数
    """

    def generate():
        if not messages:
            yield "event: response.completed\n"
            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "response.completed",
                        "response": {
                            "id": response_id,
                            "object": "response",
                            "status": "completed",
                            "model": effective_model,
                            "output": [],
                            "usage": {
                                "input_tokens": 0,
                                "output_tokens": 0,
                                "total_tokens": 0,
                            },
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )
            return

        # response.created
        yield "event: response.created\n"
        yield (
            "data: "
            + json.dumps(
                {
                    "type": "response.created",
                    "response": {
                        "id": response_id,
                        "object": "response",
                        "status": "in_progress",
                        "model": effective_model,
                        "output": [],
                        "usage": None,
                    },
                },
                ensure_ascii=False,
            )
            + "\n\n"
        )

        # response.in_progress
        yield "event: response.in_progress\n"
        yield (
            "data: "
            + json.dumps(
                {
                    "type": "response.in_progress",
                    "response": {
                        "id": response_id,
                        "object": "response",
                        "status": "in_progress",
                        "model": effective_model,
                        "output": [],
                        "usage": None,
                    },
                },
                ensure_ascii=False,
            )
            + "\n\n"
        )

        # 构建 DeepSeek 请求
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": effective_model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
            "thinking": {"type": "disabled"},
        }
        if tools:
            payload["tools"] = tools
            if tool_choice != "auto":
                payload["tool_choice"] = tool_choice

        # 状态跟踪
        text_item_id = f"item_{uuid.uuid4().hex[:12]}"
        full_text = ""
        full_reasoning = ""
        has_text = False
        text_started = False

        # 工具调用累积: index → {id, name, arguments, item_id, started}
        tool_calls_acc = {}

        input_tokens = 0
        output_tokens = 0
        seq = 0

        upstream = None
        try:
            upstream = requests.post(
                DEEPSEEK_URL,
                headers=headers,
                json=payload,
                stream=True,
                timeout=120,
            )
            upstream.raise_for_status()
            for line in upstream.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8")
                if not line.startswith("data: "):
                    continue
                raw = line[6:].strip()
                if raw == "[DONE]":
                    continue
                try:
                    chunk = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                usage = chunk.get("usage")
                if usage:
                    input_tokens = usage.get("prompt_tokens", 0)
                    output_tokens = usage.get("completion_tokens", 0)

                if "error" in chunk:
                    err = chunk["error"]
                    raise Exception(
                        f"DeepSeek API error: {err.get('message', str(err))}"
                    )

                if "choices" not in chunk or not chunk["choices"]:
                    continue

                delta = chunk["choices"][0].get("delta", {})

                # ---- 捕获 reasoning_content ----
                reasoning_delta = delta.get("reasoning_content", "")
                if reasoning_delta:
                    full_reasoning += reasoning_delta

                # ---- 处理文本内容 ----
                content = delta.get("content", "")
                if content:
                    if not text_started:
                        text_started = True
                        has_text = True
                        yield "event: response.output_item.added\n"
                        yield (
                            "data: "
                            + json.dumps(
                                {
                                    "type": "response.output_item.added",
                                    "output_index": 0,
                                    "item": {
                                        "id": text_item_id,
                                        "type": "message",
                                        "status": "in_progress",
                                        "role": "assistant",
                                        "content": [],
                                    },
                                },
                                ensure_ascii=False,
                            )
                            + "\n\n"
                        )
                        yield "event: response.content_part.added\n"
                        yield (
                            "data: "
                            + json.dumps(
                                {
                                    "type": "response.content_part.added",
                                    "item_id": text_item_id,
                                    "output_index": 0,
                                    "content_index": 0,
                                    "part": {"type": "text", "text": ""},
                                },
                                ensure_ascii=False,
                            )
                            + "\n\n"
                        )
                    full_text += content
                    seq += 1
                    yield "event: response.output_text.delta\n"
                    yield (
                        "data: "
                        + json.dumps(
                            {
                                "type": "response.output_text.delta",
                                "delta": content,
                                "item_id": text_item_id,
                                "output_index": 0,
                                "content_index": 0,
                                "sequence_number": seq,
                            },
                            ensure_ascii=False,
                        )
                        + "\n\n"
                    )

                # ---- 处理工具调用 ----
                for tc in delta.get("tool_calls", []):
                    idx = tc.get("index", 0)
                    if idx not in tool_calls_acc:
                        item_id = f"item_{uuid.uuid4().hex[:12]}"
                        tool_calls_acc[idx] = {
                            "id": "",
                            "name": "",
                            "arguments": "",
                            "item_id": item_id,
                            "started": False,
                        }

                    acc = tool_calls_acc[idx]
                    if tc.get("id"):
                        acc["id"] = tc["id"]
                    func = tc.get("function", {})
                    if func.get("name"):
                        acc["name"] = func["name"]

                    args_delta = func.get("arguments", "")
                    if args_delta:
                        acc["arguments"] += args_delta
                        out_idx = (
                            1 if has_text else 0
                        ) + sorted(tool_calls_acc.keys()).index(idx)

                        if not acc["started"]:
                            acc["started"] = True
                            yield "event: response.output_item.added\n"
                            yield (
                                "data: "
                                + json.dumps(
                                    {
                                        "type": "response.output_item.added",
                                        "output_index": out_idx,
                                        "item": {
                                            "id": acc["item_id"],
                                            "type": "function_call",
                                            "status": "in_progress",
                                            "call_id": acc["id"],
                                            "name": acc["name"],
                                            "arguments": "",
                                        },
                                    },
                                    ensure_ascii=False,
                                )
                                + "\n\n"
                            )

                        yield "event: response.function_call_arguments.delta\n"
                        yield (
                            "data: "
                            + json.dumps(
                                {
                                    "type": "response.function_call_arguments.delta",
                                    "item_id": acc["item_id"],
                                    "output_index": out_idx,
                                    "delta": args_delta,
                                },
                                ensure_ascii=False,
                            )
                            + "\n\n"
                        )

            # ===== 流结束后发出完成事件 =====

            # 文本完成
            if has_text:
                yield "event: response.output_text.done\n"
                yield (
                    "data: "
                    + json.dumps(
                        {
                            "type": "response.output_text.done",
                            "text": full_text,
                            "item_id": text_item_id,
                            "output_index": 0,
                            "content_index": 0,
                        },
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )
                yield "event: response.content_part.done\n"
                yield (
                    "data: "
                    + json.dumps(
                        {
                            "type": "response.content_part.done",
                            "item_id": text_item_id,
                            "output_index": 0,
                            "content_index": 0,
                            "part": {"type": "text", "text": full_text},
                        },
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )
                text_output_item = {
                    "id": text_item_id,
                    "type": "message",
                    "status": "completed",
                    "role": "assistant",
                    "content": [{"type": "text", "text": full_text}],
                }
                if full_reasoning:
                    text_output_item["reasoning_content"] = full_reasoning
                yield "event: response.output_item.done\n"
                yield (
                    "data: "
                    + json.dumps(
                        {
                            "type": "response.output_item.done",
                            "output_index": 0,
                            "item": text_output_item,
                        },
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )

            # 工具调用完成
            output_items = []
            if has_text:
                output_items.append({
                    "id": text_item_id,
                    "type": "message",
                    "status": "completed",
                    "role": "assistant",
                    "content": [{"type": "text", "text": full_text}],
                    **({"reasoning_content": full_reasoning} if full_reasoning else {}),
                })

            for idx in sorted(tool_calls_acc.keys()):
                acc = tool_calls_acc[idx]
                out_idx = (1 if has_text else 0) + sorted(tool_calls_acc.keys()).index(
                    idx
                )

                yield "event: response.function_call_arguments.done\n"
                yield (
                    "data: "
                    + json.dumps(
                        {
                            "type": "response.function_call_arguments.done",
                            "item_id": acc["item_id"],
                            "output_index": out_idx,
                            "arguments": acc["arguments"],
                        },
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )

                func_item = {
                    "id": acc["item_id"],
                    "type": "function_call",
                    "status": "completed",
                    "call_id": acc["id"],
                    "name": acc["name"],
                    "arguments": acc["arguments"],
                }
                if full_reasoning:
                    func_item["reasoning_content"] = full_reasoning
                yield "event: response.output_item.done\n"
                yield (
                    "data: "
                    + json.dumps(
                        {
                            "type": "response.output_item.done",
                            "output_index": out_idx,
                            "item": func_item,
                        },
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )

                output_items.append({
                    "id": acc["item_id"],
                    "type": "function_call",
                    "status": "completed",
                    "call_id": acc["id"],
                    "name": acc["name"],
                    "arguments": acc["arguments"],
                    **({"reasoning_content": full_reasoning} if full_reasoning else {}),
                })

            # response.completed
            yield "event: response.completed\n"
            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "response.completed",
                        "response": {
                            "id": response_id,
                            "object": "response",
                            "status": "completed",
                            "model": effective_model,
                            "output": output_items,
                            "usage": {
                                "input_tokens": input_tokens
                                or max(1, len(json.dumps(messages)) // 4),
                                "output_tokens": output_tokens
                                or max(1, len(full_text) // 4),
                                "total_tokens": (input_tokens + output_tokens)
                                or max(
                                    1,
                                    len(json.dumps(messages)) // 4 + len(full_text) // 4,
                                ),
                            },
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )

        except requests.exceptions.HTTPError as e:
            body = ""
            try:
                if upstream is not None:
                    body = upstream.text[:2000]
            except Exception:
                body = "(unable to read error body)"
            err_msg = f"DeepSeek API {e.response.status_code}: {body}"
            if DEEPSEEK_DEBUG:
                _log_debug_error(payload, messages, tools, err_msg, e.response.status_code, body)
            yield "event: response.failed\n"
            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "response.failed",
                        "response": {
                            "id": response_id,
                            "object": "response",
                            "status": "failed",
                            "model": effective_model,
                            "error": {
                                "message": err_msg,
                                "type": "upstream_error",
                            },
                            "output": [],
                            "usage": None,
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )

        except requests.exceptions.RequestException as e:
            yield "event: response.failed\n"
            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "response.failed",
                        "response": {
                            "id": response_id,
                            "object": "response",
                            "status": "failed",
                            "model": effective_model,
                            "error": {
                                "message": str(e),
                                "type": "upstream_error",
                            },
                            "output": [],
                            "usage": None,
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )

        finally:
            if upstream is not None:
                try:
                    upstream.close()
                except Exception:
                    pass

    return generate
