import json
import requests
import urllib.parse
import base64
import re
from des import des
from verify import verify

def extract_login_params(response):
    parsed_url = urllib.parse.urlparse(response.url)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    goto = query_params.get("goto", [""])[0]
    realm = query_params.get("realm", ["/"])[0]
    service = query_params.get("service", ["initService"])[0]
    
    state = None
    
    # 1. Try to find state in response.url
    url_unquoted = urllib.parse.unquote(urllib.parse.unquote(response.url))
    state_match = re.search(r'state=([a-f0-9]{32})', url_unquoted)
    if state_match:
        state = state_match.group(1)
        
    # 2. Try to find state inside decoded goto parameter
    if not state and goto:
        try:
            padding_needed = len(goto) % 4
            goto_padded = goto + "=" * (4 - padding_needed) if padding_needed else goto
            decoded_goto = base64.b64decode(goto_padded).decode('utf-8', errors='ignore')
            decoded_unquoted = urllib.parse.unquote(urllib.parse.unquote(decoded_goto))
            state_match = re.search(r'state=([a-f0-9]{32})', decoded_unquoted)
            if state_match:
                state = state_match.group(1)
        except Exception:
            pass
            
    # 3. Fallback: search history
    if not state:
        for hist in response.history:
            hist_unquoted = urllib.parse.unquote(urllib.parse.unquote(hist.url))
            state_match = re.search(r'state=([a-f0-9]{32})', hist_unquoted)
            if state_match:
                state = state_match.group(1)
                break
                
    # 4. If still not found, search inside history's decoded goto
    if not state:
        for hist in response.history:
            try:
                parsed_hist = urllib.parse.urlparse(hist.url)
                hist_params = urllib.parse.parse_qs(parsed_hist.query)
                hist_goto = hist_params.get("goto", [""])[0]
                if hist_goto:
                    padding_needed = len(hist_goto) % 4
                    goto_padded = hist_goto + "=" * (4 - padding_needed) if padding_needed else hist_goto
                    decoded_goto = base64.b64decode(goto_padded).decode('utf-8', errors='ignore')
                    decoded_unquoted = urllib.parse.unquote(urllib.parse.unquote(decoded_goto))
                    state_match = re.search(r'state=([a-f0-9]{32})', decoded_unquoted)
                    if state_match:
                        state = state_match.group(1)
                        break
            except Exception:
                pass
                
    return goto, realm, service, state

def get_token(username: str, password: str, timeout=15):
    from playwright.sync_api import sync_playwright
    import ddddocr

    cas_url = (
        "https://of.swu.edu.cn/cas/oauth/login/SWU_CAS2_FEDERAL"
        "?service=https%3A%2F%2Fof.swu.edu.cn%2Fgateway%2Ffighter-middle"
        "%2Fapi%2Fintegrate%2Fuaap%2Fcas%2Fresolve-cas-return"
        "%3Fnext%3Dhttps%253A%252F%252Fof.swu.edu.cn"
        "%252F%2523%252FcasLogin%253Ffrom%253D%25252FappCenter"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            page.goto(cas_url, wait_until="networkidle", timeout=timeout * 1000)

            # Click "统一认证登录"
            page.locator('img[src*="unified_button"]').click()

            # Wait for loginName
            page.wait_for_selector('input#loginName', timeout=timeout * 1000)

            success = False
            # Try up to 3 times to solve captcha and submit
            for attempt in range(3):
                # Fill credentials
                page.locator('input#loginName').fill(username)
                page.locator('input#password').fill(password)

                # Capture captcha image bytes
                captcha_el = page.locator('img#kaptchaImage')
                img_bytes = captcha_el.screenshot()

                # Solve captcha
                ocr = ddddocr.DdddOcr(show_ad=False)
                code = ocr.classification(img_bytes)

                page.locator('input[type="text"]#validateCode').fill(code)

                # Click login
                page.locator('input#button').click()

                # Wait to check result
                redirected = False
                for _ in range(5):
                    page.wait_for_timeout(1000)
                    if "of.swu.edu.cn" in page.url:
                        redirected = True
                        break

                if redirected:
                    success = True
                    break

                # Check for visible error message
                error_msg = ""
                try:
                    error_msg = page.evaluate("() => { const el = document.querySelector('.error, #error, .errorMessage, #errorMessage, .messager-body'); return el ? el.innerText : ''; }")
                except Exception:
                    pass

                if error_msg:
                    error_msg = error_msg.strip()
                    if any(k in error_msg for k in ["密码", "账户", "用户名", "密码错误", "不正确"]):
                        if "验证码" not in error_msg:
                            raise Exception(f"登录失败: {error_msg}")

                # If not redirected and no explicit credential error, refresh captcha and try again
                try:
                    captcha_el.click()
                    page.wait_for_timeout(1000)
                except Exception:
                    pass

            if not success:
                raise Exception("登录失败: 无法跳转到 of.swu.edu.cn (验证码多次识别失败或服务不可用)")

            # Extract token from localStorage
            page.wait_for_timeout(2000)
            local_storage = page.evaluate("() => JSON.stringify(localStorage)")
            ls_dict = json.loads(local_storage)

            token = None
            for k, v in ls_dict.items():
                if k == 'access_token':
                    token = v
                    break
                if 'token' in k.lower() or 'auth' in k.lower():
                    token = v
                if 'vuex' in k.lower():
                    try:
                        vx = json.loads(v)
                        def search_dict(dct):
                            for vk, vv in dct.items():
                                if isinstance(vv, dict):
                                    t = search_dict(vv)
                                    if t: return t
                                elif isinstance(vv, str) and ('token' in vk.lower() or 'auth' in vk.lower()):
                                    if len(vv) > 5:
                                        return vv
                            return None
                        t = search_dict(vx)
                        if t:
                            token = t
                    except Exception:
                        pass

            if not token:
                raise Exception("无法从 localStorage 中提取登录 Token")

            return token

        except Exception as e:
            raise Exception(f"获取令牌失败：{str(e)}")
        finally:
            browser.close()

def get_student_id(token, timeout=10):
    url = "https://of.swu.edu.cn/gateway/fighter-middle/api/auth/user?appType=fighter-portal"
    headers = {"fighter-auth-token": token}
    student_id = requests.get(url, headers=headers, timeout=timeout).json()["data"]["subject"]["username"]
    return student_id

def get_dormitory(token, timeout = 10):
    url = "https://of.swu.edu.cn/gateway/fighter-baida/api/cqlc/getDormitory"
    headers = {"fighter-auth-token": token, "Content-Type": "application/json;charset=UTF-8"}
    response = requests.post(url, headers=headers, data=json.dumps({}), timeout=timeout)
    return response.json()

def get_transition_today(token, timeout=10):
    url = "https://of.swu.edu.cn//gateway/fighter-baida/api/cqtj/getTransitionByToday"
    headers = {"fighter-auth-token": token}
    data = {"pageNum": 1,"pageSize": 1,}
    response = requests.post(url, headers=headers, data=data,timeout=timeout).json()["data"]["records"]
    return response[0] if response else None