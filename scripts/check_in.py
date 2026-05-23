import time
import os
from get_info import *
import requests
from des import des

def check_in(username: str, password: str, timeout: int = 10):
    def vacation_enable(token, timeout):
        headers = {
            "fighter-auth-token": token
        }
        url = 'https://of.swu.edu.cn/gateway/fighter-baida/api/flow-ext/start-process-instance-by-key'
        params = {'processDefinitionKey': 'XSQJXJ'}
        response = requests.post(headers=headers, params=params, json={}, url=url, timeout=timeout)
        if response.json()["code"] == 200 or response.json()["code"] == 1100:
            return 0
        else:
            return 1

    def checkin_post(token, timeout):
        try:
            transition_today = get_transition_today(token)
            if transition_today is None:
                return None
            formid = transition_today["formId"]
            id = transition_today["id"]
            headers = {"fighter-auth-token": token, "Content-Type": "application/json;charset=UTF-8"}
            url = "https://of.swu.edu.cn/gateway/fighter-baida/api/form-instance/save"
            params = {"formId": formid, "isSubmitProcess": False}
            dormitory = get_dormitory(token, timeout)["data"]["columnList"]
            payload = {
                "id": id,
                "formId": formid,
                "tsrq": time.strftime("%Y-%m-%d"),
                "xh": get_student_id(token),
                "qdsj": ["21:00", "23:30"],
                "qsqddd": dormitory[1]["value"],
                "qdbj": dormitory[2]["value"],
                "qddz": {
                    "latitude": dormitory[0]["latitude"],
                    "longitude": dormitory[0]["longitude"],
                    "address": dormitory[1]["value"],
                    "netType": "wifi",
                    "operatorType": "unknown",
                    "imei": "imei",
                    "time": int(time.time() * 1000),
                    "provider": "lbs",
                    "isFromMock": False,
                    "isGpsEnabled": True,
                    "isWifiEnabled": True,
                    "isMobileEnabled": False,
                    "isOffset": True,
                    "cityAdCode": "023",
                    "districtAdCode": "500109",
                    "isArea": True,
                    "tip": "当前在签到范围内"
                }
            }
            response = requests.post(url, headers=headers, params=params, data=json.dumps(payload), timeout=timeout).json()["data"]
            return response
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            return 4

    try:
        token = get_token(username, password, timeout)
    except Exception as e:
        print(e)
        return 3
    if vacation_enable(token, timeout):
        return 5
    transition_today =  get_transition_today(token, timeout)
    if not transition_today:
        return 0
    if transition_today["qdzt"] == "已签到":
        return 2
    post_result = checkin_post(token, timeout)
    if post_result == 4:
        return 4
    return 1


if __name__ == "__main__":
    import json
    
    print("开始执行签到...")
    accounts = []
    
    # 1. 尝试从项目根目录的 users.json 读取
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "users.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                accounts = json.load(f)
            print(f"已从 users.json 读取到 {len(accounts)} 个账号信息。")
        except Exception as e:
            print(f"读取 users.json 失败: {e}")
            
    # 2. 尝试从环境变量 SWU_USERS 读取 (JSON 格式)
    if not accounts:
        swu_users_env = os.getenv("SWU_USERS", "").strip()
        if swu_users_env:
            try:
                accounts = json.loads(swu_users_env)
                print(f"已从环境变量 SWU_USERS 读取到 {len(accounts)} 个账号信息。")
            except Exception as e:
                print(f"解析环境变量 SWU_USERS 失败: {e}")
                
    # 3. 回退到单账号环境变量 SWU_USERNAME / SWU_PASSWORD
    if not accounts:
        user = os.getenv("SWU_USERNAME", "").strip()
        pwd = os.getenv("SWU_PASSWORD", "").strip()
        if user and pwd:
            accounts = [{"username": user, "password": pwd}]
            print("已从单账号环境变量读取账号信息。")
            
    if not accounts:
        print("未配置账号信息！请提供以下之一：")
        print("  1. 项目根目录下创建 users.json")
        print("  2. 设置环境变量 SWU_USERS (JSON 格式)")
        print("  3. 设置环境变量 SWU_USERNAME 和 SWU_PASSWORD")
        raise SystemExit(1)
        
    message_map = {
        0: "今日暂无签到任务。",
        1: "签到成功。",
        2: "今日已签到，无需重复操作。",
        3: "账号或密码验证失败，请检查后重试。",
        4: "连接错误或请求超时，请稍后重试。",
        5: "请假中，请检查是否有打卡任务。"
    }
    
    success_count = 0
    failed_count = 0
    
    for idx, acc in enumerate(accounts, 1):
        username = acc.get("username", "").strip()
        password = acc.get("password", "").strip()
        if not username or not password:
            print(f"[{idx}/{len(accounts)}] 账号配置不完整，跳过。")
            continue
            
        print(f"\n[{idx}/{len(accounts)}] 正在为账号 {username} 执行签到...")
        try:
            result = check_in(username, password)
            print(f"账号 {username} 签到结果: {message_map.get(result, '未知状态')}")
            if result in [0, 1, 2, 5]:
                success_count += 1
            else:
                failed_count += 1
        except Exception as e:
            print(f"账号 {username} 签到执行异常: {e}")
            failed_count += 1
            
    print(f"\n签到任务执行完毕！成功: {success_count} 个，失败: {failed_count} 个。")

