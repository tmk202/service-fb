"""
dcom_manager.py
================
Quản lý kết nối DCOM (USB Modem 4G/5G) thay thế cho proxy_manager.py.

Thay vì dùng HTTP proxy từ proxyxoay.shop, module này:
  - Đọc IP thật hiện tại của máy (qua card mạng DCOM)
  - Reset kết nối modem để lấy IP mới từ nhà mạng
  - Hỗ trợ nhiều loại modem phổ biến tại VN (Huawei HiLink, ZTE, ...)

Cách hoạt động:
  Browser (Camoufox) sẽ chạy KHÔNG CÓ PROXY — dùng thẳng IP của DCOM.
  Để "đổi IP", ta reset kết nối modem → nhà mạng cấp IP mới.

Cài đặt modem trong config_dcom.json:
  "dcom_gateway"   : IP admin của modem, thường là "192.168.8.1" (Huawei)
                     hoặc "192.168.0.1" (ZTE/generic)
  "dcom_type"      : "huawei" | "zte" | "generic"
  "dcom_username"  : Tên đăng nhập vào trang admin (thường "admin")
  "dcom_password"  : Mật khẩu trang admin (thường "admin" hoặc "1234")
"""

import requests
import time
import logging
import hashlib
import base64
import re

# Tắt cảnh báo SSL (modem thường dùng self-signed cert)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


import subprocess

class DcomManager:
    """
    Quản lý USB Modem 4G (DCOM) để thay thế proxy.
    Hỗ trợ: Huawei HiLink, ZTE, Generic HTTP Reset, Windows Interface Toggle.
    """

    def __init__(self, gateway: str = "192.168.8.1", modem_type: str = "huawei",
                 username: str = "admin", password: str = "admin",
                 interface_name: str = "Ethernet 5"):
        """
        Args:
            gateway    : IP của trang admin modem
            modem_type : "huawei" | "zte" | "generic" | "windows"
            username   : Tên đăng nhập admin modem
            password   : Mật khẩu admin modem
            interface_name: Tên card mạng DCOM trên Windows (ví dụ: "Ethernet 5")
        """
        self.gateway = gateway.rstrip('/')
        self.modem_type = modem_type.lower()
        self.username = username
        self.password = password
        self.interface_name = interface_name
        self.session = requests.Session()
        self.session.verify = False 

    def get_current_ip(self) -> str | None:
        """
        Lấy IP public hiện tại của máy qua card mạng DCOM.
        Ép request đi qua đúng giao diện mạng để log chính xác.
        """
        try:
            # Tìm IP nội bộ của card mạng DCOM trước
            local_ip = None
            import psutil, socket
            addrs = psutil.net_if_addrs()
            if self.interface_name in addrs:
                for addr in addrs[self.interface_name]:
                    if addr.family == socket.AF_INET:
                        local_ip = addr.address
                        break

            # --- ƯU TIÊN LẤY IP TRỰC TIẾP TỪ MODEM HUAWEI (Nếu là IP thật) ---
            if self.modem_type == "huawei":
                wan_ip = self._get_huawei_wan_ip()
                if wan_ip:
                    # Kiểm tra xem có phải IP Private không (10.x, 172.x, 192.x, 100.x)
                    is_private = wan_ip.startswith("10.") or wan_ip.startswith("192.168.") or \
                                 wan_ip.startswith("172.") or wan_ip.startswith("100.")
                    
                    if not is_private:
                        logging.info(f"[DCOM] Lấy IP Public từ Modem Huawei: {wan_ip}")
                        return wan_ip
                    else:
                        logging.info(f"[DCOM] Modem báo IP Private ({wan_ip}), sẽ check Public IP từ External...")

            import urllib3
            
            # Sử dụng HTTP thay cho HTTPS để tránh timeout SSL handshake qua DCOM
            check_urls = ["http://api.ipify.org", "http://checkip.amazonaws.com", "http://ifconfig.me/ip"]
            
            if not local_ip:
                for url in check_urls:
                    try:
                        return requests.get(url, timeout=5).text.strip()
                    except:
                        pass
                return None

            # Ép bind source address
            pool = urllib3.PoolManager(source_address=(local_ip, 0))
            for url in check_urls:
                try:
                    resp = pool.request('GET', url, timeout=10.0)
                    ip = resp.data.decode('utf-8').strip()
                    if "." in ip and len(ip) < 20:
                        logging.info(f"[DCOM] IP hiện tại trên {self.interface_name}: {ip}")
                        return ip
                except:
                    continue
                    
            return None
        except Exception as e:
            logging.error(f"[DCOM] Không lấy được IP qua {self.interface_name}: {e}")
            return None

    def _get_huawei_wan_ip(self) -> str | None:
        """Lấy WanIPAddress trực tiếp từ API của modem Huawei."""
        try:
            base = f"http://{self.gateway}"
            # Lấy token nhanh
            r_tok = self.session.get(f"{base}/api/webserver/token", timeout=5)
            tok = re.search(r'<token>(.*?)</token>', r_tok.text)
            headers = {}
            if tok:
                headers["__RequestVerificationToken"] = tok.group(1)

            r = self.session.get(f"{base}/api/monitoring/status", headers=headers, timeout=5)
            ip_match = re.search(r'<WanIPAddress>(.*?)</WanIPAddress>', r.text)
            if ip_match:
                ip = ip_match.group(1).strip()
                if ip and ip != "0.0.0.0" and "." in ip:
                    return ip
        except:
            pass
        return None

    def _get_dcom_gateway(self) -> str | None:
        """Lấy gateway IP của card mạng DCOM từ bảng route."""
        try:
            result = subprocess.run(
                ["route", "print", "0.0.0.0"],
                capture_output=True, text=True, timeout=5
            )
            import psutil
            addrs = psutil.net_if_addrs()
            dcom_ips = set()
            for addr in addrs.get(self.interface_name, []):
                import socket as _socket
                if addr.family == _socket.AF_INET:
                    dcom_ips.add(addr.address)
            
            # Tìm dòng route có interface là DCOM
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 5 and parts[0] == "0.0.0.0":
                    gateway = parts[2]
                    interface_ip = parts[3]
                    if interface_ip in dcom_ips:
                        return gateway, interface_ip
        except Exception as e:
            logging.debug(f"[DCOM] Không lấy được gateway: {e}")
        return None, None

    def _set_interface_priority(self) -> bool:
        """
        Ép toàn bộ traffic đi qua DCOM bằng cách thao tác
        bảng định tuyến Windows (route command) trực tiếp.
        Cần quyền Administrator.
        """
        try:
            dcom_gw, dcom_iface_ip = self._get_dcom_gateway()
            if not dcom_gw or not dcom_iface_ip:
                logging.warning("[DCOM] Không tìm thấy route DCOM trong bảng định tuyến. Bỏ qua ưu tiên.")
                return False

            logging.info(f"[DCOM] Bảng route: DCOM gateway={dcom_gw} | iface={dcom_iface_ip}")

            # Đọc bảng route hiện tại để tìm các default route KHÔNG phải DCOM
            result = subprocess.run(
                ["route", "print", "0.0.0.0"],
                capture_output=True, text=True, timeout=5
            )
            
            routes_to_delete = []
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 5 and parts[0] == "0.0.0.0":
                    gw = parts[2]
                    iface = parts[3]
                    if iface != dcom_iface_ip:  # Không phải DCOM → đánh dấu xóa
                        routes_to_delete.append((gw, iface))

            # Dùng PowerShell với -Verb RunAs để yêu cầu UAC nếu cần Admin
            def run_route_cmd(args: list) -> bool:
                try:
                    # Thử chạy trực tiếp trước (nếu đã là Admin)
                    res = subprocess.run(args, capture_output=True, text=True, timeout=5)
                    if res.returncode == 0:
                        return True
                    # Nếu lỗi elevation → dùng ShellExecuteW (UAC popup)
                    logging.warning(f"[DCOM] route cần quyền Admin, đang yêu cầu UAC...")
                    import ctypes
                    cmd_string = " ".join(args)
                    ret = ctypes.windll.shell32.ShellExecuteW(
                        None, "runas", "cmd.exe", f"/c {cmd_string}", None, 0
                    )
                    import time; time.sleep(1)
                    return ret > 32  # > 32 = thành công
                except Exception as e:
                    logging.warning(f"[DCOM] run_route_cmd error: {e}")
                    return False

            # Xóa tất cả default route không phải DCOM
            for gw, iface in routes_to_delete:
                ok = run_route_cmd(["route", "delete", "0.0.0.0", "mask", "0.0.0.0", gw])
                logging.info(f"[DCOM] Xóa route {gw} ({iface}): {'OK' if ok else 'FAILED'}")

            # Đặt lại route DCOM với metric = 1
            ok = run_route_cmd(["route", "add", "0.0.0.0", "mask", "0.0.0.0", dcom_gw, "metric", "1"])
            logging.info(f"[DCOM] Thêm route DCOM via {dcom_gw} metric=1: {'OK' if ok else 'FAILED'}")

            # Xác nhận lại bằng cách đọc route table sau khi set
            verify = subprocess.run(["route", "print", "0.0.0.0"], capture_output=True, text=True, timeout=5)
            logging.info(f"[DCOM] Bảng route sau khi set:\n{verify.stdout.strip()}")

            logging.info(f"[DCOM] ✅ Đã ép toàn bộ traffic qua DCOM ({dcom_iface_ip})")
            return True

        except Exception as e:
            logging.error(f"[DCOM] ❌ Không thể set routing (Cần quyền Admin): {e}")
            return False

    def reset_connection(self, wait_seconds: int = 15) -> bool:
        """
        Reset kết nối để lấy IP mới.
        """
        # KHÔNG thao tác route hệ thống nữa — việc ép IP cho Camoufox
        # được xử lý qua SOCKS5 proxy riêng (dcom_proxy.py)
        # self._set_interface_priority()
        
        old_ip = self.get_current_ip()
        logging.info(f"[DCOM] IP cũ: {old_ip} — Đang reset kết nối ({self.modem_type})...")

        success = False
        if self.modem_type == "windows":
            success = self._reset_windows_interface()
        elif self.modem_type == "huawei":
            success = self._reset_huawei()
        elif self.modem_type == "zte":
            success = self._reset_zte()
        else:
            success = self._reset_generic()

        if not success:
            logging.error("[DCOM] Lệnh reset thất bại.")
            return False

        logging.info(f"[DCOM] Đã gửi lệnh reset. Chờ {wait_seconds}s để modem kết nối lại...")
        time.sleep(wait_seconds)

        # Thử lấy IP mới, tối đa 3 lần
        for attempt in range(3):
            new_ip = self.get_current_ip()
            if new_ip and new_ip != old_ip:
                logging.info(f"[DCOM] ✅ Đổi IP thành công: {old_ip} → {new_ip}")
                return True
            logging.warning(f"[DCOM] IP chưa thay đổi (lần {attempt+1}/3). Chờ thêm 10s...")
            time.sleep(10)

        logging.error(f"[DCOM] ❌ Đổi IP thất bại sau {old_ip} và các lần thử.")
        return False

    def _reset_windows_interface(self) -> bool:
        """
        Dùng lệnh netsh để tắt/bật card mạng Windows.
        Yêu cầu quyền Administrator.
        """
        try:
            logging.info(f"[DCOM/Windows] Đang tắt interface: {self.interface_name}")
            subprocess.run(["netsh", "interface", "set", "interface", self.interface_name, "disable"], check=True)
            time.sleep(5)
            logging.info(f"[DCOM/Windows] Đang bật lại interface: {self.interface_name}")
            subprocess.run(["netsh", "interface", "set", "interface", self.interface_name, "enable"], check=True)
            return True
        except Exception as e:
            logging.error(f"[DCOM/Windows] Lỗi khi thực hiện netsh: {e}")
            return False

    # ---------------------------------------------------------
    #  Huawei HiLink (E3372, E8372, E5573, ...)
    #  Web admin: http://192.168.8.1
    # ---------------------------------------------------------
    def _reset_huawei(self) -> bool:
        """
        Đổi IP Huawei bằng cách ngắt và kết nối lại dữ liệu di động (Dataswitch).
        Hỗ trợ cả 2 dạng API cũ (token) và mới (SesTokInfo).
        """
        import hashlib, base64
        base_url = f"http://{self.gateway}"
        
        token_val = None
        session_val = None
        headers = {
            "Content-Type": "application/xml; charset=UTF-8"
        }
        
        try:
            # Bước 0: Thử dùng /api/webserver/token trước (DCOM đời cũ 192.168.8.1)
            r0 = self.session.get(f"{base_url}/api/webserver/token", timeout=10)
            tok0 = re.search(r'<token>(.*?)</token>', r0.text)
            
            if tok0 and "125002" not in r0.text:
                token_val = tok0.group(1).strip()
                logging.info(f"[DCOM/Huawei] Token lấy được (webserver/token): {token_val[:15]}...")
                headers["__RequestVerificationToken"] = token_val
            else:
                # Fallback: API đời mới hơn (SesTokInfo)
                r0_ses = self.session.get(f"{base_url}/api/webserver/SesTokInfo", timeout=10)
                tok0_ses = re.search(r'<TokInfo>(.*?)</TokInfo>', r0_ses.text)
                ses0_ses = re.search(r'<SesInfo>(.*?)</SesInfo>', r0_ses.text)
                
                if tok0_ses and ses0_ses:
                    token_val = tok0_ses.group(1).strip()
                    session_val = ses0_ses.group(1).strip()
                    logging.info(f"[DCOM/Huawei] Token lấy được (SesTokInfo): {token_val[:15]}...")
                    headers["__RequestVerificationToken"] = token_val
                    headers["Cookie"] = session_val
                    headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
                else:
                    logging.error("[DCOM/Huawei] Không lấy được token từ cả 2 API!")
                    return False

            # Bước 1: Request ngắt kết nối (Dataswitch OFF)
            off_xml = '<?xml version="1.0" encoding="UTF-8"?><request><dataswitch>0</dataswitch></request>'
            off_resp = self.session.post(f"{base_url}/api/dialup/mobile-dataswitch", data=off_xml, headers=headers, timeout=10)
            logging.info(f"[DCOM/Huawei] Dataswitch OFF -> HTTP {off_resp.status_code} | {off_resp.text[:100]}")
            
            if "100002" in off_resp.text or "125002" in off_resp.text:
                logging.warning("[DCOM/Huawei] API từ chối lệnh, có thể cần Đăng Nhập trước. Đang thử login...")
                pw_sha256 = hashlib.sha256(self.password.encode()).hexdigest()
                pw_b64    = base64.b64encode(pw_sha256.encode()).decode()
                login_xml = f'<?xml version="1.0" encoding="UTF-8"?><request><Username>{self.username}</Username><Password>{pw_b64}</Password><password_type>4</password_type></request>'
                
                # Bắt buộc cập nhật Type = form cho chuẩn API Mới khi Login
                login_headers = headers.copy()
                login_headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
                login_resp = self.session.post(f"{base_url}/api/user/login", data=login_xml, headers=login_headers, timeout=10)
                logging.info(f"[DCOM/Huawei] Đăng nhập: {login_resp.status_code} | {login_resp.text[:100]}")
                
                # Cập nhật lại Token sau login
                if session_val:
                    r_tok2 = self.session.get(f"{base_url}/api/webserver/SesTokInfo", timeout=10)
                    tok2_ses = re.search(r'<TokInfo>(.*?)</TokInfo>', r_tok2.text)
                    ses2_ses = re.search(r'<SesInfo>(.*?)</SesInfo>', r_tok2.text)
                    if tok2_ses: headers["__RequestVerificationToken"] = tok2_ses.group(1).strip()
                    if ses2_ses: headers["Cookie"] = ses2_ses.group(1).strip()
                else:
                    r_tok2 = self.session.get(f"{base_url}/api/webserver/token", timeout=10)
                    tok2 = re.search(r'<token>(.*?)</token>', r_tok2.text)
                    if tok2: headers["__RequestVerificationToken"] = tok2.group(1).strip()
                
                # Thử gửi OFF lần 2
                headers["Content-Type"] = "application/xml; charset=UTF-8"
                off_resp = self.session.post(f"{base_url}/api/dialup/mobile-dataswitch", data=off_xml, headers=headers, timeout=10)
                logging.info(f"[DCOM/Huawei] Dataswitch OFF (Lần 2) -> HTTP {off_resp.status_code}")

            time.sleep(5)

            # Bước 2: Request kết nối lại (Dataswitch ON)
            # Token thường chỉ dùng được 1 lần, lấy lại trước khi gửi request tiếp theo
            if session_val:
                r_tok3 = self.session.get(f"{base_url}/api/webserver/SesTokInfo", timeout=10)
                tok3_ses = re.search(r'<TokInfo>(.*?)</TokInfo>', r_tok3.text)
                ses3_ses = re.search(r'<SesInfo>(.*?)</SesInfo>', r_tok3.text)
                if tok3_ses: headers["__RequestVerificationToken"] = tok3_ses.group(1).strip()
                if ses3_ses: headers["Cookie"] = ses3_ses.group(1).strip()
            else:
                r_tok3 = self.session.get(f"{base_url}/api/webserver/token", timeout=10)
                tok3 = re.search(r'<token>(.*?)</token>', r_tok3.text)
                if tok3: headers["__RequestVerificationToken"] = tok3.group(1).strip()
            
            headers["Content-Type"] = "application/xml; charset=UTF-8"
            on_xml = '<?xml version="1.0" encoding="UTF-8"?><request><dataswitch>1</dataswitch></request>'
            on_resp = self.session.post(f"{base_url}/api/dialup/mobile-dataswitch", data=on_xml, headers=headers, timeout=10)
            logging.info(f"[DCOM/Huawei] Dataswitch ON -> HTTP {on_resp.status_code} | {on_resp.text[:100]}")

            return True
        except Exception as e:
            logging.error(f"[DCOM/Huawei] Lỗi khi gửi lệnh reset: {e}")
            return False
    def _reboot_huawei(self) -> bool:
        """Reboot toàn bộ modem Huawei (chậm hơn ~30-60s)."""
        base = f"http://{self.gateway}"
        try:
            r = self.session.get(f"{base}/api/webserver/SesTokInfo", timeout=10)
            tok = re.search(r'<TokInfo>(.*?)</TokInfo>', r.text)
            ses = re.search(r'<SesInfo>(.*?)</SesInfo>', r.text)

            headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
            if tok and ses:
                headers["__RequestVerificationToken"] = tok.group(1)
                headers["Cookie"] = ses.group(1)

            reboot_xml = """<?xml version="1.0" encoding="UTF-8"?><request><Control>1</Control></request>"""
            self.session.post(f"{base}/api/device/control",
                              data=reboot_xml, headers=headers, timeout=10)
            logging.info("[DCOM/Huawei] Đã gửi lệnh reboot modem.")
            return True
        except Exception as e:
            logging.error(f"[DCOM/Huawei] Reboot thất bại: {e}")
            return False

    # ---------------------------------------------------------
    #  ZTE (MF79U, MF833, ...)
    #  Web admin: http://192.168.0.1
    # ---------------------------------------------------------
    def _reset_zte(self) -> bool:
        """
        Reset kết nối ZTE qua GoForm API.
        Không cần đăng nhập trên một số model.
        """
        base = f"http://{self.gateway}"
        try:
            # Đăng nhập ZTE
            pwd_hash = hashlib.md5(self.password.encode()).hexdigest()
            pwd_b64  = base64.b64encode(pwd_hash.encode()).decode()
            self.session.post(f"{base}/goform/goform_set_cmd_process",
                              data={"isTest": "false", "goformId": "LOGIN",
                                    "password": pwd_b64}, timeout=10)
            time.sleep(1)

            # Ngắt kết nối
            self.session.post(f"{base}/goform/goform_set_cmd_process",
                              data={"isTest": "false", "goformId": "DISCONNECT_NETWORK"},
                              timeout=10)
            time.sleep(3)

            # Kết nối lại
            self.session.post(f"{base}/goform/goform_set_cmd_process",
                              data={"isTest": "false", "goformId": "CONNECT_NETWORK"},
                              timeout=10)
            logging.info("[DCOM/ZTE] Đã gửi lệnh disconnect → connect.")
            return True
        except Exception as e:
            logging.error(f"[DCOM/ZTE] Lỗi reset: {e}")
            return False

    # ---------------------------------------------------------
    #  Generic: Reboot modem qua trang admin thông thường
    # ---------------------------------------------------------
    def _reset_generic(self) -> bool:
        """
        Cách generic: đăng nhập vào admin page và nhấn reboot/reconnect.
        Phù hợp với các modem không xác định rõ loại.
        """
        base = f"http://{self.gateway}"
        try:
            # Thử đăng nhập basic
            self.session.get(f"{base}/", timeout=5, auth=(self.username, self.password))

            # Thử các endpoint reboot phổ biến
            reboot_endpoints = [
                "/reboot.cgi",
                "/goform/SysToolReboot",
                "/cgi-bin/reboot.sh",
                "/api/device/control",
            ]
            for ep in reboot_endpoints:
                try:
                    resp = self.session.post(f"{base}{ep}", timeout=5)
                    if resp.status_code < 400:
                        logging.info(f"[DCOM/Generic] Reboot qua {ep} thành công.")
                        return True
                except Exception:
                    continue

            logging.error("[DCOM/Generic] Không tìm được endpoint reboot phù hợp.")
            return False
        except Exception as e:
            logging.error(f"[DCOM/Generic] Lỗi: {e}")
            return False


# =========================================================
#  Test standalone
# =========================================================
if __name__ == "__main__":
    import json
    import sys

    # Set UTF-8 for Windows console
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except AttributeError:
            pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Đọc config
    try:
        with open("config_dcom.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        print("[!] Khong tim thay config_dcom.json - su dung gia tri mac dinh.")
        cfg = {}

    dcom = DcomManager(
        gateway    = cfg.get("dcom_gateway",  "192.168.8.1"),
        modem_type = cfg.get("dcom_type",     "huawei"),
        username   = cfg.get("dcom_username", "admin"),
        password   = cfg.get("dcom_password", "admin"),
        interface_name = cfg.get("interface_name", "Ethernet 5")
    )

    print("=" * 50)
    print("  TEST DCOM MANAGER")
    print("=" * 50)

    print("\n[1] Dang lay IP hien tai...")
    ip = dcom.get_current_ip()
    print(f"    -> IP: {ip}")

    print("\n[2] Thu reset ket noi...")
    result = dcom.reset_connection(wait_seconds=cfg.get("dcom_wait_seconds", 20))
    print(f"    -> Ket qua: {'[OK]' if result else '[FAILED]'}")

    print("\nTest hoan tat.")
