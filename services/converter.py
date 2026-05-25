"""
消息格式转换模块

将 OpenAI Responses API 请求格式转换为 DeepSeek Chat Completions API 格式。
"""


def _clean_schema(obj):
    """递归清除 JSON Schema 中 DeepSeek 不支持的字段"""
    if not isinstance(obj, dict):
        return obj
    cleaned = {}
    for k, v in obj.items():
        if k in ("additionalProperties", "strict"):
            continue
        if isinstance(v, dict):
            cleaned[k] = _clean_schema(v)
        elif isinstance(v, list):
            cleaned[k] = [_clean_schema(i) if isinstance(i, dict) else i for i in v]
        else:
            cleaned[k] = v
    return cleaned


def _convert_tools(tools: list) -> list:
    """将工具定义从 Responses API 格式转换为 Chat Completions API 格式"""
    result = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        if tool.get("type") != "function":
            continue
        func = {
            "name": tool.get("name", ""),
            "description": tool.get("description", ""),
        }
        if "parameters" in tool:
            func["parameters"] = _clean_schema(tool["parameters"])
        result.append({"type": "function", "function": func})
    return result


def _convert_tool_choice(tc):
    """将 tool_choice 从 Responses API 格式转换为 Chat Completions 格式"""
    if tc is None:
        return "auto"
    if isinstance(tc, str):
        return tc
    if isinstance(tc, dict) and tc.get("type") == "function":
        return {"type": "function", "function": {"name": tc.get("name", "")}}
    return "auto"


def extract_messages(data: dict):
    """
    从 Responses API 请求中提取 messages 列表、tools 列表和 tool_choice。

    支持两种输入格式：
      - Responses API（input/instructions 字段）
      - Chat Completions API（messages 字段）

    Returns:
        (messages, tools, tool_choice)
    """
    ROLE_MAP = {"developer": "system"}
    raw_tools = data.get("tools", [])
    tools = _convert_tools(raw_tools)
    tool_choice = _convert_tool_choice(data.get("tool_choice"))

    if "input" not in data:
        if "messages" in data:
            return data["messages"], tools, tool_choice
        return [], tools, tool_choice

    inp = data["input"]
    if isinstance(inp, str):
        messages = []
        if "instructions" in data and data["instructions"]:
            messages.append({"role": "system", "content": data["instructions"]})
        messages.append({"role": "user", "content": inp})
        return messages, tools, tool_choice

    if not isinstance(inp, list):
        return [], tools, tool_choice

    messages = []
    if "instructions" in data and data["instructions"]:
        messages.append({"role": "system", "content": data["instructions"]})

    pending_tool_calls = []
    pending_reasoning = ""

    def _flush_tool_calls():
        nonlocal pending_tool_calls, pending_reasoning
        if pending_tool_calls:
            msg = {
                "role": "assistant",
                "content": "",
                "tool_calls": pending_tool_calls,
            }
            if pending_reasoning:
                msg["reasoning_content"] = pending_reasoning
            messages.append(msg)
            pending_tool_calls = []
            pending_reasoning = ""

    for item in inp:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")

        if item_type == "message":
            _flush_tool_calls()
            role = item.get("role", "user")
            role = ROLE_MAP.get(role, role)
            content = item.get("content", "")
            if isinstance(content, list):
                texts = []
                tool_calls = []
                for c in content:
                    if not isinstance(c, dict):
                        continue
                    c_type = c.get("type")
                    if c_type in ("text", "input_text", "output_text"):
                        t = c.get("text", "")
                        if t.strip():
                            texts.append(t)
                    elif c_type == "tool_call":
                        tool_calls.append({
                            "id": c.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": c.get("name", ""),
                                "arguments": c.get("arguments", ""),
                            },
                        })
                text_content = "\n".join(texts)
                if tool_calls:
                    msg = {"role": role, "content": text_content or ""}
                    msg["tool_calls"] = tool_calls
                    if item.get("reasoning_content"):
                        msg["reasoning_content"] = item["reasoning_content"]
                    messages.append(msg)
                elif text_content:
                    msg = {"role": role, "content": text_content}
                    if item.get("reasoning_content"):
                        msg["reasoning_content"] = item["reasoning_content"]
                    messages.append(msg)
            elif isinstance(content, str) and content.strip():
                msg = {"role": role, "content": content.strip()}
                if item.get("reasoning_content"):
                    msg["reasoning_content"] = item["reasoning_content"]
                messages.append(msg)

        elif item_type == "function_call":
            pending_tool_calls.append({
                "id": item.get("call_id", ""),
                "type": "function",
                "function": {
                    "name": item.get("name", ""),
                    "arguments": item.get("arguments", ""),
                },
            })
            if item.get("reasoning_content") and not pending_reasoning:
                pending_reasoning = item["reasoning_content"]

        elif item_type == "function_call_output":
            _flush_tool_calls()
            messages.append({
                "role": "tool",
                "tool_call_id": item.get("call_id", ""),
                "content": item.get("output", ""),
            })

    _flush_tool_calls()

    # ---- 重排消息：确保 tool 消息紧跟对应的 assistant 消息 ----
    reordered = []
    i = 0
    while i < len(messages):
        msg = messages[i]
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            expected_ids = {tc["id"] for tc in msg["tool_calls"]}
            tool_msgs = []
            non_tool_msgs = []
            j = i + 1
            while j < len(messages) and expected_ids:
                nxt = messages[j]
                if nxt.get("role") == "tool" and nxt.get("tool_call_id") in expected_ids:
                    expected_ids.remove(nxt["tool_call_id"])
                    tool_msgs.append(nxt)
                elif nxt.get("role") in ("system", "developer"):
                    non_tool_msgs.append(nxt)
                else:
                    break
                j += 1
            reordered.extend(non_tool_msgs)
            reordered.append(msg)
            reordered.extend(tool_msgs)
            i = j
        else:
            reordered.append(msg)
            i += 1

    return reordered, tools, tool_choice
