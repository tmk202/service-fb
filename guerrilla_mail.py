import requests
import time
import re
import logging

logger = logging.getLogger('GuerrillaMail')

class GuerrillaMail:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01"
        })
        self.base_url = "https://www.guerrillamail.com/ajax.php"
        self.email_address = None
        self.sid_token = None

    def get_email_address(self, domain="guerrillamail.com"):
        """Khởi tạo session và lấy địa chỉ email với domain tùy chọn"""
        try:
            # 1. Lấy email mặc định trước (không truyền site để tránh lỗi 400)
            res = self.session.get(self.base_url, params={'f': 'get_email_address'}, timeout=30)
            if res.status_code != 200:
                logger.error(f"API Guerrilla (get) trả về lỗi HTTP {res.status_code}")
                return None
                
            data = res.json()
            email_now = data.get('email_addr')
            self.sid_token = data.get('sid_token')
            
            if not email_now: return None
            
            # 2. Đổi sang domain mong muốn (guerrillamail.org)
            user = email_now.split("@")[0]
            res_set = self.session.get(self.base_url, params={
                'f': 'set_email_user', 
                'email_user': user, 
                'site': domain,
                'lang': 'en'
            }, timeout=30)
            
            if res_set.status_code == 200:
                self.email_address = f"{user}@{domain}"
                # Cập nhật sid_token mới nếu có
                try: self.sid_token = res_set.json().get('sid_token') or self.sid_token
                except: pass
            else:
                self.email_address = email_now # Fallback
                
            logger.info(f"Lấy email thành công: {self.email_address}")
            return self.email_address
        except Exception as e:
            logger.error(f"Lỗi lấy email: {e}")
            return None

    def check_inbox(self, timeout=120):
        """Kiểm tra hộp thư để lấy mã OTP (mã 5-6 chữ số)"""
        start_time = time.time()
        logger.info(f"Đang quét hộp thư cho {self.email_address}...")
        
        while time.time() - start_time < timeout:
            try:
                res = self.session.get(self.base_url, params={'f': 'check_email', 'seq': '0'}, timeout=30)
                data = res.json()
                emails = data.get('list', [])
                
                for mail in emails:
                    subject = mail.get('mail_subject', '')
                    content = mail.get('mail_excerpt', '')
                    full_text = f"{subject} {content}"
                    
                    # Tìm mã OTP (thường là 5 hoặc 6 chữ số trên FB/TikTok)
                    codes = re.findall(r'\b\d{5,6}\b', full_text)
                    if codes:
                        return codes[0]
                
                # In dấu chấm để báo hiệu đang đợi
                time.sleep(10)
            except Exception as e:
                logger.error(f"Lỗi check inbox: {e}")
                time.sleep(5)
                
        return None
