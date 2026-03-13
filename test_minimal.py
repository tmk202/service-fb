import requests
import base64
import xml.etree.ElementTree as ET

def test_minimal_login():
    gateway = "192.168.16.1"
    
    # 1. Get info
    res = requests.get(f"http://{gateway}/api/webserver/SesTokInfo")
    root = ET.fromstring(res.text)
    cookie = root.find('SesInfo').text
    token = root.find('TokInfo').text
    
    print(f"Cookie: {cookie}")
    print(f"Token: {token}")
    
    # 2. Login
    # Using admin / admin -> YWRtaW4=
    login_xml = '<request><Username>admin</Username><Password>YWRtaW4=</Password></request>'
    
    # Precise headers
    headers = {
        'Cookie': cookie,
        '__RequestVerificationToken': token,
        'Content-Type': 'text/xml'
    }
    
    res_login = requests.post(f"http://{gateway}/api/user/login", data=login_xml, headers=headers)
    print(f"Response: {res_login.text}")

if __name__ == "__main__":
    test_minimal_login()
