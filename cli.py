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

def custom_init(base_url:str, api_key:str):
    if healthcheck(base_url, api_key):
        try:
            config = get_config()
            auth = get_auth()
            
            # 先设置config
            config.set("model_provider", "custom")
            config.set("model", "gpt-5.4")
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

def openai_init(base_url:str, api_key:str):
    if healthcheck(base_url, api_key):
        try:
            config = get_config()
            auth = get_auth()
            
            # 先设置config
            config.set("model_provider", "OpenAI")
            config.set("model", "gpt-5.4")
            config.set("model_reasoning_effort", "high")
            config.set("disable_response_storage", True)
            
            config.set("model_providers.OpenAI.name", "codex2deepseek")
            config.set("model_providers.OpenAI.base_url", base_url)
            config.set("model_providers.OpenAI.wire_api", "responses")
            config.set("model_providers.OpenAI.experimental_bearer_token", api_key)
            config.set("model_providers.OpenAI.requires_openai_auth", True)

            
            # 设置auth
            auth.set("auth_mode", "chatgpt")
            auth.set("OPENAI_API_KEY", None)
            return True,"初始化成功,请重启Codex以应用新配置."
        except Exception as e:
            return False, f"初始化失败: {str(e)}"
    else:
        return False, "自定义模型提供者不可用,请检查基本URL和API密钥."

if __name__ == "__main__":
    # 运行参数cli：python -u <base_url> -k <api_key>
    import argparse
    parser = argparse.ArgumentParser(description="初始化自定义模型提供者配置。")
    parser.add_argument("-u", "--base_url", type=str, required=False, help="自定义模型提供者的基本URL。")
    parser.add_argument("-k", "--api_key", type=str, required=False, help="用于身份验证的API密钥。")
    parser.add_argument("-t", "--type", type=str, required=False, help="初始化类型，可选值：openai(o),custom(c)")
    args = parser.parse_args()
    parameters = {}
    if not args.base_url or not args.api_key or not args.type:
        print("请选择初始化类型：1. OpenAI（使用OpenAI登录Codex｜可以保留一定的登录后才能使用的功能） 2. Custom（直接输入基本URL和API密钥、无法使用登录后的一些功能）")
        input_type = input("请输入初始化类型（1/2）：").strip().lower()
        if input_type == "1":
            parameters["type"] = "o"
        elif input_type == "2":
            parameters["type"] = "c"
        print("请输入基本URL：")
        parameters["base_url"] = input().strip()
        print("请输入API密钥：")
        parameters["api_key"] = input().strip()
        if parameters["type"] == "o" or parameters["type"] == "openai":
            success, message = openai_init(parameters["base_url"], parameters["api_key"])
        elif parameters["type"] == "c" or parameters["type"] == "custom":
            success, message = custom_init(parameters["base_url"], parameters["api_key"])
        else:
            print("无效的初始化类型。")
            exit(1)
        print(message)
        exit(0)

    if args.type == "o" or args.type == "openai":
        success, message = openai_init(args.base_url, args.api_key)
    elif args.type == "c" or args.type == "custom":
        success, message = custom_init(args.base_url, args.api_key)
    else:
        print("无效的初始化类型。")
        exit(1)
    print(message)