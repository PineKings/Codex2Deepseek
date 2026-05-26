import rtoml
import json
from pathlib import Path
from typing import Any, Dict
import os

# ==================== 安全嵌套读取 ====================
class _SafeNested:
    def __init__(self, data):
        self._data = data

    def __getattr__(self, key):
        if isinstance(self._data, dict) and key in self._data:
            return _SafeNested(self._data[key])
        return _SafeNested(None)

    def __str__(self):
        return str(self._data) if self._data is not None else "None"

    def __repr__(self):
        return str(self)

    def __bool__(self):
        return self._data is not None

# ==================== 核心配置类 ====================
class TomlConfig:
    def __init__(self, file_path: str | Path):
        self._path = Path(file_path)
        self._data: Dict[str, Any] = self._load_file()

    def _load_file(self) -> Dict[str, Any]:
        if not self._path.exists():
            return {}
        with open(self._path, "r", encoding="utf-8") as f:
            return rtoml.load(f)

    def save(self) -> None:
        """ ✅ 终极：保留所有格式、空章节、原样输出 """
        with open(self._path, "w", encoding="utf-8") as f:
            rtoml.dump(self._data, f, pretty=True)

    def all(self) -> Dict[str, Any]:
        return self._data.copy()

    def keys(self) -> list:
        return list(self._data.keys())

    def get(self, path: str, default: Any = None) -> Any:
        keys = path.split(".")
        current = self._data
        try:
            for k in keys:
                current = current[k]
            return current
        except (KeyError, TypeError):
            return default

    def set(self, path: str, value: Any, auto_save: bool = True) -> None:
        keys = path.split(".")
        current = self._data
        for k in keys[:-1]:
            current = current.setdefault(k, {})
        current[keys[-1]] = value
        if auto_save:
            self.save()

    # 点访问（只读）
    def __getattr__(self, key):
        return _SafeNested(self._data.get(key))

    def __getitem__(self, key):
        return self.__getattr__(key)

# ==================== JSON 认证/配置工具类====================
class JsonAuth:
    def __init__(self, file_path: str | Path):
        self._path = Path(file_path)
        self._data: Dict[str, Any] = self._load_file()

    def _load_file(self) -> Dict[str, Any]:
        """加载 JSON 文件，不存在返回空字典"""
        if not self._path.exists():
            return {}
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    def save(self) -> None:
        """保存（格式化输出、中文不乱码、结构完全保留）"""
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(
                self._data,
                f,
                ensure_ascii=False,
                indent=4
            )

    def all(self) -> Dict[str, Any]:
        """获取全部数据"""
        return self._data.copy()

    def keys(self) -> list:
        """获取顶层键"""
        return list(self._data.keys())

    def get(self, path: str, default: Any = None) -> Any:
        """支持 a.b.c 格式安全获取"""
        keys = path.split(".")
        current = self._data
        try:
            for k in keys:
                current = current[k]
            return current
        except (KeyError, TypeError):
            return default

    def set(self, path: str, value: Any, auto_save: bool = True) -> None:
        """支持 a.b.c 格式设置，自动创建层级"""
        keys = path.split(".")
        current = self._data
        for k in keys[:-1]:
            current = current.setdefault(k, {})
        current[keys[-1]] = value
        if auto_save:
            self.save()

    # ==================== 点访问（只读，永不报错）====================
    def __getattr__(self, key):
        return _SafeNested(self._data.get(key))

    def __getitem__(self, key):
        return self.__getattr__(key)

# ==================== 工具函数 ====================
def get_user_home():
    return os.path.expanduser("~")

def check_codex_dir():
    codex_dir = Path(get_user_home()) / ".codex"
    if not codex_dir.exists():
        raise FileNotFoundError(f"{codex_dir} 不存在")
    return codex_dir

def get_config():
    codex_dir = check_codex_dir()
    config_path = codex_dir / "config.toml"
    if not config_path.exists():
        raise FileNotFoundError(f"{config_path} 不存在")
    return TomlConfig(config_path)

def get_auth():
    codex_dir = check_codex_dir()
    auth_path = codex_dir / "auth.json"
    if not auth_path.exists():
        raise FileNotFoundError(f"{auth_path} 不存在")
    return JsonAuth(auth_path)

# ==================== 测试 ====================
if __name__ == "__main__":
    cfg = get_config()

    print("不存在的键:", cfg.a.b.c)
    print("model =", cfg.get("model"))
    print("mcp_servers =", cfg.mcp_servers)

    print("\n\n")

    auth = get_auth()

    print("不存在的键:", auth.a.b.c)
    print("auth_mode =", auth.get("auth_mode"))
    print("OPENAI_API_KEY =", auth.OPENAI_API_KEY)
    
    auth.set("auth_mode", "apikey")
