"""
dcom_proxy.py
=============
SOCKS5 Proxy using Socket Binding (No Admin Rights Needed).
This proxy forces connections through a specific network interface (DCOM)
by binding the outgoing sockets to the interface's local IP address.
"""

import socket
import threading
import struct
import logging
import psutil
import time

logger = logging.getLogger("DCOMProxy")

def get_interface_info(interface_name: str) -> tuple[str | None, str | None]:
    """Gets the local IP and default gateway of a specific interface."""
    try:
        addrs = psutil.net_if_addrs()
        if interface_name not in addrs:
            logger.error(f"[DCOMProxy] Interface '{interface_name}' not found.")
            return None, None
            
        local_ip = None
        for addr in addrs[interface_name]:
            if addr.family == socket.AF_INET:
                local_ip = addr.address
                break
        
        if not local_ip:
            logger.error(f"[DCOMProxy] Could not find IPv4 for {interface_name}")
            return None, None

        # Gateway detection (optional for binding, but good for reference)
        gateway = None
        import subprocess
        result = subprocess.run(["route", "print", "0.0.0.0"], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[0] == "0.0.0.0":
                if parts[3] == local_ip:
                    gateway = parts[2]
                    break
                    
        return str(local_ip), str(gateway) if gateway else None
    except Exception as e:
        logger.error(f"[DCOMProxy] Failed to get interface info: {e}")
    return None, None

def resolve_dns_via_interface(domain: str, local_ip: str) -> str | None:
    """Resolves a domain name using a UDP socket bound to a specific local IP (prevent leaks)."""
    if not local_ip:
        return socket.gethostbyname(domain)
        
    try:
        # Simple DNS Query (Standard A Record)
        # 8.8.8.8 is Google DNS. Using a socket bound to DCOM interface.
        dns_server = "8.8.8.8"
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(4)
        sock.bind((local_ip, 0))
        
        # Construct DNS Query for 'A' record
        # Transaction ID: 0x1234, Flags: 0x0100 (Standard Query)
        # Questions: 1, Answer RRs: 0, Authority RRs: 0, Additional RRs: 0
        header = b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00"
        query = b""
        for part in domain.split("."):
            query += bytes([len(part)]) + part.encode()
        query += b"\x00" # Terminator
        query += b"\x00\x01\x00\x01" # Type A, Class IN
        
        sock.sendto(header + query, (dns_server, 53))
        data, _ = sock.recvfrom(512)
        
        # Very basic parsing of the response to get the first IPv4 address
        # Response starts with header (12 bytes) + query (same as above)
        # Then comes the Answer section
        offset = 12 + len(query)
        # Answer format: Name (2 bytes if pointer), Type (2), Class (2), TTL (4), DataLength (2), Data (DataLength)
        # We look for Type 0x0001 (A record)
        if len(data) >= offset + 12:
            # Dùng bytearray hoặc slicing an toàn
            ans_section = data[offset:]
            if len(ans_section) >= 12:
                ans_data_len = struct.unpack("!H", ans_section[10:12])[0]
                if ans_data_len == 4 and len(ans_section) >= 16:
                    ip_bytes = ans_section[12:16]
                    return socket.inet_ntoa(ip_bytes)
                
        return socket.gethostbyname(domain) # Fallback if parsing fails
    except Exception as e:
        logger.warning(f"[DCOMProxy] DNS via interface failed for {domain}: {e}. Using fallback.")
        try: return socket.gethostbyname(domain)
        except: return None

def handle_client(client_sock: socket.socket, local_ip: str):
    """Handles SOCKS5 from browser."""
    logger.info(f"[DCOMProxy] 📥 Incoming connection (local_ip={local_ip})")
    try:
        # Handshake
        data = client_sock.recv(256)
        if not data or data[0] != 0x05:
            return
        client_sock.sendall(b"\x05\x00")

        data = client_sock.recv(256)
        if len(data) < 7 or data[1] != 0x01:
            return

        addr_type = data[3]
        if addr_type == 0x01:  # IPv4
            target_ip = socket.inet_ntoa(data[4:8])
            target_port = struct.unpack("!H", data[8:10])[0]
        elif addr_type == 0x03:  # Domain
            domain_len = data[4]
            domain = data[5:5 + domain_len].decode()
            target_port = struct.unpack("!H", data[5 + domain_len:7 + domain_len])[0]
            target_ip = resolve_dns_via_interface(domain, local_ip)
            if not target_ip:
                client_sock.sendall(b"\x05\x04\x00\x01\x00\x00\x00\x00\x00\x00")
                return
        else:
            return

        # Connect
        remote_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote_sock.settimeout(15)
        
        # BIND TO DCOM INTERFACE (The "Senior" Way)
        try:
            if local_ip:
                remote_sock.bind((local_ip, 0))
                logger.info(f"[DCOMProxy] ✅ Connecting to {target_ip}:{target_port} via {local_ip}")
        except Exception as e:
            logger.error(f"[DCOMProxy] ❌ Failed to bind to {local_ip}: {e}")
            client_sock.sendall(b"\x05\x01\x00\x01\x00\x00\x00\x00\x00\x00")
            return

        try:
            remote_sock.connect((target_ip, target_port))
            logger.info(f"[DCOMProxy] 🔗 Established: {target_ip}:{target_port}")
        except Exception as e:
            logger.error(f"[DCOMProxy] ❌ Connection failed: {target_ip}:{target_port} | {e}")
            client_sock.sendall(b"\x05\x05\x00\x01\x00\x00\x00\x00\x00\x00")
            remote_sock.close()
            return

        client_sock.sendall(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")

        def relay(src, dst):
            try:
                while True:
                    chunk = src.recv(8192)
                    if not chunk: break
                    dst.sendall(chunk)
            except: pass
            finally:
                try: src.close()
                except: pass
                try: dst.close()
                except: pass

        t1 = threading.Thread(target=relay, args=(client_sock, remote_sock), daemon=True)
        t2 = threading.Thread(target=relay, args=(remote_sock, client_sock), daemon=True)
        t1.start()
        t2.start()
        # No need to join if daemon=True and we want high concurrency
    except Exception as e:
        logger.debug(f"[DCOMProxy] handle_client error: {e}")
    finally:
        # Note: relay handles closing
        pass

class DcomSocks5Proxy:
    def __init__(self, interface_name: str = "Ethernet 2", listen_port: int = 0):
        self.interface_name = interface_name
        self.listen_port = listen_port
        self.local_ip: str | None = None
        self._server_sock = None
        self._thread = None
        self.running = False
        self.actual_port = None

    def start(self) -> dict | None:
        self.local_ip, _ = get_interface_info(self.interface_name)
        if not self.local_ip:
            logger.error(f"[DCOMProxy] Could not find local IP for {self.interface_name}")
            return None

        try:
            self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_sock.bind(("127.0.0.1", self.listen_port))
            self._server_sock.listen(128)
            self.actual_port = self._server_sock.getsockname()[1]
            self.running = True

            self._thread = threading.Thread(target=self._accept_loop, daemon=True)
            self._thread.start()

            logger.info(f"[DCOMProxy] ✅ SOCKS5 Proxy active at 127.0.0.1:{self.actual_port}")
            logger.info(f"[DCOMProxy] 🔗 Forcing traffic through {self.interface_name} ({self.local_ip})")

            return {
                "server": f"socks5://127.0.0.1:{self.actual_port}",
                "username": "",
                "password": "",
            }
        except Exception as e:
            logger.error(f"[DCOMProxy] Start failed: {e}")
            return None

    def _accept_loop(self):
        while self.running:
            try:
                self._server_sock.settimeout(1.0)
                client, _ = self._server_sock.accept()
                threading.Thread(target=handle_client, args=(client, self.local_ip), daemon=True).start()
            except socket.timeout: continue
            except: break

    def stop(self):
        self.running = False
        try: self._server_sock.close()
        except: pass

_proxy_instance: DcomSocks5Proxy | None = None
_proxy_config: dict | None = None

def get_or_start_proxy(interface_name: str = "Ethernet 2") -> dict | None:
    global _proxy_instance, _proxy_config
    if _proxy_instance and _proxy_instance.running:
        # Check if interface IP changed (DCOM reset)
        new_ip, _ = get_interface_info(interface_name)
        if new_ip != _proxy_instance.local_ip:
            logger.info(f"[DCOMProxy] Interface IP changed ({_proxy_instance.local_ip} -> {new_ip}). Updating...")
            _proxy_instance.local_ip = new_ip
        return _proxy_config
        
    _proxy_instance = DcomSocks5Proxy(interface_name=interface_name)
    _proxy_config = _proxy_instance.start()
    return _proxy_config

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    cfg = get_or_start_proxy("Ethernet 5") # Example
    if cfg:
        print(f"Proxy config: {cfg}")
        try:
            while True: time.sleep(1)
        except KeyboardInterrupt:
            _proxy_instance.stop()
