import requests
import json
import os

def check_raw():
    gateway = "192.168.16.1"
    url = f"http://{gateway}/api/webserver/SesTokInfo"
    res = requests.get(url)
    print("Raw Response:")
    print(res.text)
    print("-" * 20)
    print("Headers:")
    print(res.headers)

if __name__ == "__main__":
    check_raw()
