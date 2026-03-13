import subprocess
import re

def test_curl_login():
    gateway = "192.168.16.1"
    
    # 1. Get tokens via curl.exe
    cmd_get = f'curl.exe -s http://{gateway}/api/webserver/SesTokInfo'
    res = subprocess.check_output(cmd_get, shell=True).decode()
    print("SesTokInfo Response:", res)
    
    session_id_match = re.search(r'<SesInfo>(.*?)</SesInfo>', res)
    token_match = re.search(r'<TokInfo>(.*?)</TokInfo>', res)
    
    if not session_id_match or not token_match:
        print("Lỗi parse XML!")
        return
        
    session_id = session_id_match.group(1)
    token = token_match.group(1)
    
    print(f"SessionID: {session_id}")
    print(f"Token: {token}")
    
    # 2. Login via curl.exe
    login_xml = f'<request><Username>admin</Username><Password>YWRtaW4=</Password></request>'
    
    # Matching the user's curl exactly
    cmd_login = (
        f'curl.exe -v -X POST "http://{gateway}/api/user/login" '
        f'-H "Cookie: {session_id}" '
        f'-H "__RequestVerificationToken: {token}" '
        f'-H "Content-Type: text/xml" '
        f'-d "{login_xml}"'
    )
    
    print("Running Login command...")
    try:
        # We use -v to see headers
        login_res = subprocess.check_output(cmd_login, shell=True, stderr=subprocess.STDOUT).decode()
        print("Login Output:")
        print(login_res)
    except subprocess.CalledProcessError as e:
        print("Curl failed!")
        print(e.output.decode())

if __name__ == "__main__":
    test_curl_login()
