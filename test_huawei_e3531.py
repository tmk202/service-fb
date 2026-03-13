import requests
import base64
import xml.etree.ElementTree as ET
import time

def test_huawei_login():
    gateway = "192.168.16.1"
    base_url = f"http://{gateway}/api"
    
    print(f"--- Đang test Modem tại {gateway} ---")
    
    # 1. Get SesTokInfo
    try:
        res = requests.get(f"{base_url}/webserver/SesTokInfo", timeout=5)
        print("1. SesTokInfo Status:", res.status_code)
        if res.status_code != 200:
            print("Lỗi: Không thể kết nối tới modem.")
            return

        root = ET.fromstring(res.text)
        cookie = root.find('SesInfo').text
        token = root.find('TokInfo').text
        print(f"   Cookie: {cookie[:30]}...")
        print(f"   Token: {token}")
    except Exception as e:
        print(f"Lỗi bước 1: {e}")
        return

    # 2. Login
    # E3531 usually uses admin/admin
    username = "admin"
    password = "admin"
    encoded_pass = base64.b64encode(password.encode()).decode()
    
    # User's exact XML structure from curl example
    login_xml = f"<request><Username>{username}</Username><Password>{encoded_pass}</Password></request>"
    
    headers = {
        "Cookie": cookie,
        "__RequestVerificationToken": token,
        "Content-Type": "text/xml",
        "X-Requested-With": "XMLHttpRequest"
    }
    
    print(f"2. Đang thử Login với {username}/{password}...")
    try:
        res_login = requests.post(f"{base_url}/user/login", data=login_xml, headers=headers, timeout=5)
        print("   Login Response Code:", res_login.status_code)
        print("   Login Response Text:", res_login.text)
        
        if "OK" in res_login.text:
            print("✅ LOGIN THÀNH CÔNG!")
            # After login, we usually need NEW tokens for further requests
            time.sleep(1)
            res_new = requests.get(f"{base_url}/webserver/SesTokInfo", timeout=5)
            root_new = ET.fromstring(res_new.text)
            new_cookie = root_new.find('SesInfo').text
            new_token = root_new.find('TokInfo').text
            
            # 3. Test basic information
            headers_info = {
                "Cookie": new_cookie,
                "__RequestVerificationToken": new_token
            }
            res_info = requests.get(f"{base_url}/device/basic_information", headers=headers_info, timeout=5)
            print("3. Basic Information:", res_info.text)
            
            # 4. Test Dialup Status
            res_status = requests.get(f"{base_url}/dialup/status", headers=headers_info, timeout=5)
            print("4. Dialup Status:", res_status.text)
            
        else:
            print("❌ LOGIN THẤT BẠI!")
            if "100006" in res_login.text:
                print("   Gợi ý: Lỗi 100006 là Wrong Token. Có thể modem yêu cầu password hash (XOR/SHA256) thay vì Base64?")
                print("   Hoặc modem yêu cầu Referer header.")
    except Exception as e:
        print(f"Lỗi bước 2: {e}")

if __name__ == "__main__":
    test_huawei_login()
