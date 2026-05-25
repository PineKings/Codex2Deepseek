"""
配置管理模块

职责：
  - .env 文件加载（不覆盖已有系统环境变量）
  - DEEPSEEK_API_KEY 交互式输入与持久化
  - 导出全局配置常量
"""

import os
import sys
import getpass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_dotenv():
    """加载 .env 文件到 os.environ（不覆盖已有的系统环境变量）"""
    env_file = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_file):
        return
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip("\"'")
            if key and key not in os.environ:
                os.environ[key] = val


def ensure_api_key() -> str:
    """确保 DEEPSEEK_API_KEY 已设置：系统环境变量 > .env > 交互输入

    Returns:
        API Key 字符串，若用户取消输入则退出进程。
    """
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        return key

    print("=" * 60)
    print("  未检测到 DEEPSEEK_API_KEY")
    print("=" * 60)
    print()
    print("  从 https://platform.deepseek.com/api_keys 获取 API Key")
    print()
    print("  你也可以设置系统环境变量 DEEPSEEK_API_KEY 后重启")
    print()

    try:
        key = getpass.getpass("  请输入你的 DeepSeek API Key: ").strip()
    except (EOFError, KeyboardInterrupt):
        key = ""

    if not key:
        print()
        print("  ERROR: 未输入 API Key，程序退出。")
        print()
        print("  支持以下方式设置 API Key（按优先级排列）:")
        print("    1. 系统环境变量: DEEPSEEK_API_KEY=sk-your-key")
        print("    2. 脚本同目录 .env 文件: DEEPSEEK_API_KEY=sk-your-key")
        print()
        input("  按 Enter 退出...")
        sys.exit(1)

    env_file = os.path.join(BASE_DIR, ".env")
    existing = {}
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                existing[k.strip()] = line
    existing["DEEPSEEK_API_KEY"] = f"DEEPSEEK_API_KEY={key}"

    with open(env_file, "w", encoding="utf-8") as f:
        for line in existing.values():
            f.write(line + "\n")
        if "DEFAULT_MODEL" not in existing:
            f.write("DEFAULT_MODEL=deepseek-v4-pro\n")

    os.environ["DEEPSEEK_API_KEY"] = key
    print()
    print(f"  API Key 已保存到: {env_file}")
    print()
    return key


# ===================== 模块导入时自动加载 =====================
load_dotenv()

# ===================== 全局配置常量 =====================
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "").strip()
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "deepseek-v4-flash").strip()
DEEPSEEK_URL = os.environ.get(
    "DEEPSEEK_URL", "https://api.deepseek.com/v1/chat/completions"
).strip()
DEEPSEEK_DEBUG = os.environ.get("DEEPSEEK_DEBUG", "0").strip() in (
    "1",
    "true",
    "True",
    "yes",
)
DEBUG_LOG = os.path.join(BASE_DIR, "proxy_debug.log")

# ===================== 模型映射表 =====================
# 将客户端请求中的模型名称映射为 DeepSeek 实际模型名称
# 默认模型名称（可被环境变量覆盖），当请求中未指定模型或指定的模型不在 MODEL_MAP 中时使用
MODEL_DEFAULT = os.environ.get("MODEL_DEFAULT", "deepseek-v4-flash")

## codex模型对应,为空则使用默认模型
MODEL_GTP5_5 = os.environ.get("MODEL_GTP5_5", "").strip() or MODEL_DEFAULT
MODEL_GTP5_4 = os.environ.get("MODEL_GTP5_4", "").strip() or MODEL_DEFAULT
MODEl_GPT5_4_MINI = os.environ.get("MODEl_GPT5_4_MINI", "").strip() or MODEL_DEFAULT
MODEL_GTP5_3_CODEX = os.environ.get("MODEL_GTP5_3_CODEX", "").strip() or MODEL_DEFAULT
MODEL_GTP5_2 = os.environ.get("MODEL_GTP5_2", "").strip() or MODEL_DEFAULT

MODEL_MAP = {
    "gpt-5.5": MODEL_GTP5_5,
    "gpt-5.4": MODEL_GTP5_4,
    "gpt-5.4-mini": MODEl_GPT5_4_MINI,
    "gpt-5.3-codex": MODEL_GTP5_3_CODEX,
    "gpt-5.2": MODEL_GTP5_2,
    
}

def ensure_my_api_key() -> str:
    """确保 MY_API_KEY 已设置：系统环境变量 > .env > 交互输入

    Returns:
        授权密钥字符串，若用户取消输入则退出进程。
    """
    key = os.environ.get("MY_API_KEY", "").strip()
    if key:
        return key

    print("=" * 60)
    print("  未检测到 MY_API_KEY（授权密钥）")
    print("=" * 60)
    print()
    print("  MY_API_KEY 用于验证请求来源是否合法，请设置一个自定义密钥。")
    print()

    try:
        key = getpass.getpass("  请输入你的 MY_API_KEY: ").strip()
    except (EOFError, KeyboardInterrupt):
        key = ""

    if not key:
        print()
        print("  ERROR: 未输入 MY_API_KEY，程序退出。")
        print()
        print("  你可以在 .env 文件中设置: MY_API_KEY=你的密钥")
        print()
        input("  按 Enter 退出...")
        sys.exit(1)

    env_file = os.path.join(BASE_DIR, ".env")
    existing = {}
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                existing[k.strip()] = line
    existing["MY_API_KEY"] = f"MY_API_KEY={key}"

    with open(env_file, "w", encoding="utf-8") as f:
        for line in existing.values():
            f.write(line + "\n")

    os.environ["MY_API_KEY"] = key
    # 更新模块级变量，使后续 import 能拿到最新值
    globals()["MY_API_KEY"] = key
    print()
    print(f"  MY_API_KEY 已保存到: {env_file}")
    print()
    return key


# ===================== 全局配置常量 =====================
# 简单防护，使用固定API Key 验证请求来源是否合法
MY_API_KEY = os.environ.get("MY_API_KEY", "").strip()

