from script.tools import get_config, get_auth
import requests

def healthcheck(base_url:str, api_key:str):
    try:
        url = f'{base_url}/health'
        headers = {'Authorization': f'Bearer {api_key}'}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if 'status' in data and data['status'] == 'ok':
                return True
        return False
    except Exception as e:
        print(f"Error occurred while checking health: {e}")
        return False

def init(base_url:str, api_key:str):
    if healthcheck(base_url, api_key):
        try:
            config = get_config()
            auth = get_auth()
            
            # 先设置config
            config.set("model_provider", "custom")
            config.set("model", "gpt-4.4")
            config.set("model_reasoning_effort", "high")
            config.set("disable_response_storage", True)
            
            config.set("model_providers.custom.name", "codex2deepseek")
            config.set("model_providers.custom.wire_api", "responses")
            config.set("model_providers.custom.requires_openai_auth", True)
            config.set("model_providers.custom.base_url", base_url)
            
            # 设置auth
            auth.set("auth_mode", "apikey")
            auth.set("OPENAI_API_KEY", api_key)
            return True,"初始化成功,请重启Codex以应用新配置."
        except Exception as e:
            return False, f"初始化失败: {str(e)}"
    else:
        return False, "自定义模型提供者不可用,请检查基本URL和API密钥."


if __name__ == "__main__":
    # 运行参数cli：python -u <base_url> -k <api_key>
    import argparse
    parser = argparse.ArgumentParser(description="初始化自定义模型提供者配置。")
    parser.add_argument("-u", "--base_url", type=str, required=True, help="自定义模型提供者的基本URL。")
    parser.add_argument("-k", "--api_key", type=str, required=True, help="用于身份验证的API密钥。")
    args = parser.parse_args()
    success, message = init(args.base_url, args.api_key)
    print(message)