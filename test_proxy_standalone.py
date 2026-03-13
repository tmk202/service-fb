import socket
import requests
import time
import logging

logging.basicConfig(level=logging.DEBUG)

def test_proxy():
    proxy = "socks5://127.0.0.1:51843"
    proxies = {
        "http": proxy,
        "https": proxy
    }
    try:
        print(f"Testing proxy: {proxy}")
        resp = requests.get("http://api.ipify.org", proxies=proxies, timeout=10)
        print(f"IP via Proxy: {resp.text}")
    except Exception as e:
        print(f"Proxy test failed: {e}")

if __name__ == "__main__":
    test_proxy()
