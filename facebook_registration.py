import asyncio
import logging
import time
import random
import string
import csv
import re
from datetime import datetime
import json
import os
import ctypes

try:
    import win32gui
    import win32con
except ImportError:
    win32gui = None
    win32con = None
try:
    import psutil
except ImportError:
    psutil = None

# THƯ VIỆN GIẢI CAPTCHA ĐA TẦNG (Senior Action)
import cv2
import numpy as np

class AdvancedOCRSolver:
    def __init__(self):
        self.ddddocr_lib = None
        self.pytesseract_lib = None
        self.easyocr_lib = None
        
        try:
            import ddddocr
            self.ddddocr_lib = ddddocr.DdddOcr(show_ad=False)
        except Exception: pass
        
        try:
            import pytesseract
            self.pytesseract_lib = pytesseract
            # Lưu ý cài Tesseract engine. Đổi đường dẫn tesseract.exe tesseract_cmd nếu mặc định không nhận trên Windows.
            # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        except Exception: pass
        
        try:
            import easyocr
            self.easyocr_lib = easyocr.Reader(['en'], gpu=False, verbose=False)
        except Exception as e: 
            print("🚀[EASYOCR LOAD ERROR]", e)

    def solve_captcha(self, img_bytes: bytes) -> str:
        import time
        import os
        
        # Convert bytes to cv2 image
        np_arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img is None: return ""
        
        # Tiền xử lý (Morphology, Thresholding cho Tesseract + EasyOCR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        dim_scale = (gray.shape[1] * 2, gray.shape[0] * 2)
        gray_upscaled = cv2.resize(gray, dim_scale, interpolation=cv2.INTER_CUBIC)
        # Loại nhiễu cơ bản
        blurred = cv2.GaussianBlur(gray_upscaled, (3,3), 0)
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Lưu ảnh để Debug/Theo dõi
        os.makedirs("logs/captchas", exist_ok=True)
        ts = int(time.time() * 1000)
        raw_path = f"logs/captchas/raw_{ts}.png"
        thresh_path = f"logs/captchas/thresh_{ts}.png"
        cv2.imwrite(raw_path, img)
        cv2.imwrite(thresh_path, thresh)
        
        final_ans = ""
        source = ""
        
        # 1. Thử ddddocr trước (Fast, basic deep learning)
        if self.ddddocr_lib:
            try:
                res1 = self.ddddocr_lib.classification(img_bytes)
                if res1 and len(res1) >= 4:
                    final_ans, source = res1, "ddddocr"
            except: pass

        # 2. Thử Tesseract nếu ddddocr tịt
        if not final_ans and self.pytesseract_lib:
            try:
                res2 = self.pytesseract_lib.image_to_string(thresh, config='--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789').strip()
                res2 = "".join(filter(str.isalnum, res2))
                if res2 and len(res2) >= 4:
                    final_ans, source = res2, "tesseract"
            except: pass

        # 3. Thử EasyOCR (Bắn lên Pytorch, cực mạnh)
        if not final_ans and self.easyocr_lib:
            try:
                results = self.easyocr_lib.readtext(thresh, allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789')
                if results:
                    res3 = results[0][1]
                    res3 = "".join(filter(str.isalnum, res3))
                    if res3 and len(res3) >= 4:
                        final_ans, source = res3, "easyocr"
            except: pass
            
        print(f"🖼️ [DEBUG CAPTCHA] Đã lưu ảnh {raw_path}. Kết quả: '{final_ans}' (bằng {source})")
        
        # Đổi tên file để biết luôn khỏi mở print
        if final_ans:
            try:
                os.rename(raw_path, f"logs/captchas/raw_{ts}_{source}_{final_ans}.png")
                os.rename(thresh_path, f"logs/captchas/thresh_{ts}_{source}_{final_ans}.png")
            except: pass
            
        return final_ans

import speech_recognition as sr
import base64
import pydub

class AudioCaptchaSolver:
    def __init__(self):
        try:
            self.recognizer = sr.Recognizer()
        except:
            self.recognizer = None

    def solve_audio(self, b64_data: str) -> str:
        import time, os
        if not self.recognizer or not b64_data: return ""
        try:
            os.makedirs("logs/captchas", exist_ok=True)
            ts = int(time.time() * 1000)
            raw_path = f"logs/captchas/audio_{ts}.mp4"
            wav_path = f"logs/captchas/audio_{ts}.wav"
            
            with open(raw_path, "wb") as f:
                f.write(base64.b64decode(b64_data))
            
            try:
                sound = pydub.AudioSegment.from_file(raw_path)
                sound.export(wav_path, format="wav")
                target_file = wav_path
            except Exception as pe:
                print(f"⚠️ [Cảnh báo Pydub/FFmpeg]: {pe}. Sẽ cố dùng gốc...")
                target_file = raw_path

            with sr.AudioFile(target_file) as source:
                audio_data = self.recognizer.record(source)
                text = self.recognizer.recognize_google(audio_data, language='en-US')
                
                # Trích xuất số vì mã FB audio toàn số
                final_text = ''.join(filter(str.isdigit, text))
                print(f"🎤 [SPEECH-TO-TEXT] Đã nghe được text thô: '{text}' -> Code chốt: {final_text}")
                return final_text
        except Exception as e:
            print("❌ [LỖI AUDIO SOLVER]:", e)
            return ""

    def solve_audio_file(self, file_path: str) -> str:
        """Hỗ trợ giải mã từ file path trực tiếp (cho việc test)"""
        import time, os
        try:
            os.makedirs("logs/captchas", exist_ok=True)
            ts = int(time.time() * 1000)
            wav_path = f"logs/captchas/test_{ts}.wav"
            
            try:
                sound = pydub.AudioSegment.from_file(file_path)
                sound.export(wav_path, format="wav")
                target_file = wav_path
            except Exception as pe:
                print(f"⚠️ [Cảnh báo Pydub/FFmpeg]: {pe}. Thử dùng gốc...")
                target_file = file_path

            with sr.AudioFile(target_file) as source:
                audio_data = self.recognizer.record(source)
                text = self.recognizer.recognize_google(audio_data, language='en-US')
                return ''.join(filter(str.isdigit, text))
        except Exception as e:
            print("❌ [LỖI AUDIO SOLVER FILE]:", e)
            return ""

OCR_SOLVER = AdvancedOCRSolver()
AUDIO_SOLVER = AudioCaptchaSolver()
# Tái sử dụng base browser setup từ tool
from browser_setup import TikTokBrowser
from guerrilla_mail import GuerrillaMail
from dcom_manager import DcomManager
from dcom_proxy import get_or_start_proxy

import sys
os.makedirs("logs", exist_ok=True)
log_filename = f"logs/facebook_registration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

def generate_random_password():
    """Tạo mật khẩu kiểu Việt Nam: Word1(Cap) + word1(lower) + numbers + special (VD: Huyhuy202!)"""
    prefixes = ["Huy", "Tuan", "Nam", "Binh", "Minh", "Hoang", "Anh", "Dung", "Thanh", "Hung", "Linh", "Phuc", "Gia", "Duc"]
    p1 = random.choice(prefixes)
    p2 = p1.lower()
    num = str(random.randint(100, 999))
    special = random.choice(["!", "@", "#", "$"])
    return f"{p1}{p2}{num}{special}"

def generate_random_name():
    """Họ 1 từ, Tên 2 từ kiểu Việt Nam"""
    ho_list = ["Nguyen", "Tran", "Le", "Pham", "Hoang", "Huynh", "Phan", "Vu", "Vo", "Dang", "Bui", "Do", "Ho", "Ngo", "Duong", "Ly", "Mai", "Dinh"]
    lot_list = ["Van", "Thi", "Duc", "Minh", "Hoang", "Anh", "Quoc", "Dinh", "Kim", "Ngoc", "Thanh", "Cong"]
    ten_list = ["Huy", "Tuan", "Nam", "Binh", "Dung", "Thanh", "Hung", "Long", "Son", "Vinh", "Duc", "An", "Khoa"]
    
    ho = random.choice(ho_list)
    ten = f"{random.choice(lot_list)} {random.choice(ten_list)}"
    return ho, ten # Ho = Last Name, Ten = First Name

# ---------- HUMAN-LIKE INTERACTION HELPERS ----------

async def save_debug_info(page, name):
    """Lưu toàn bộ HTML và ảnh chụp màn hình để debug cực chi tiết"""
    try:
        ts = int(time.time())
        html_path = f"debug_{name}_{ts}.html"
        img_path = f"debug_{name}_{ts}.png"
        
        # Lưu HTML
        content = await page.content()
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        # Lưu Ảnh
        await page.screenshot(path=img_path)
        logging.info(f"📸 Đã lưu debug: {img_path} và {html_path}")
    except: pass

async def log_focused_element(page, step_name=""):
    """Lấy thông tin phần tử đang focus để debug"""
    try:
        info = await page.evaluate('''() => {
            const el = document.activeElement;
            if (!el) return "None";
            return {
                tag: el.tagName,
                text: el.innerText || el.value || "",
                aria: el.getAttribute("aria-label") || "",
                role: el.getAttribute("role") || "",
                class: el.className
            };
        }''')
        logging.info(f"🔍 [DEBUG_FOCUS] {step_name} | Tag: {info['tag']} | Aria: {info['aria']} | Text: {info['text']} | Role: {info['role']}")
        return info
    except Exception as e:
        logging.warning(f"Lỗi khi log focus: {e}")
        return None

async def tab_and_debug(page, step_label):
    await page.keyboard.press("Tab")
    await asyncio.sleep(0.3)
    return await log_focused_element(page, step_label)

async def human_click(page, locator, timeout=5000):
    """Mô phỏng click chuột thật: Tối ưu tọa độ để không bị văng khỏi màn hình"""
    try:
        await locator.wait_for(state="attached", timeout=timeout)
        
        box = await locator.bounding_box()
        if not box:
            await locator.scroll_into_view_if_needed()
            await asyncio.sleep(0.1)
            box = await locator.bounding_box()
        
        if box:
            viewport = page.viewport_size or {'width': 1280, 'height': 720}
            target_x = box['x'] + box['width'] / 2 + random.uniform(-3, 3)
            target_y = box['y'] + box['height'] / 2 + random.uniform(-3, 3)
            
            # Rút gọn: chỉ di chuyển thẳng tới vị trí, ko jitter thêm
            await page.mouse.move(target_x, target_y, steps=random.randint(3, 5))
            await asyncio.sleep(random.uniform(0.05, 0.15))
            
            logging.info(f"🖱️ [HUMAN] Clicking at ({target_x:.1f}, {target_y:.1f})...")
            await page.mouse.down()
            await asyncio.sleep(random.uniform(0.08, 0.15))
            await page.mouse.up()
            return True
    except Exception as e:
        logging.warning(f"human_click failed for locator: {locator}. Error: {e}")
        try:
            await locator.evaluate("node => node.click()")
            return True
        except:
            pass
    return False

async def human_type(page, locator, text):
    """Mô phỏng gõ phím thật: Click -> Gõ tốc độ chậm và không đều"""
    await human_click(page, locator)
    await asyncio.sleep(random.uniform(0.2, 0.5))
    
    logging.info(f"⌨️ [HUMAN] Typing text (length: {len(text)})...")
    for char in text:
        await page.keyboard.type(char)
        await asyncio.sleep(random.uniform(0.05, 0.2))
        if random.random() < 0.05:
            await asyncio.sleep(random.uniform(0.5, 1.2))
    logging.info("⌨️ [HUMAN] Typing finished.")

async def warm_up_facebook(page):
    """Lướt và xem Facebook đang track gì qua console/network (Anti-Tracking Monitor)"""
    try:
        logging.info("--- [MONITOR] Đang kích hoạt chế độ giám sát Tracking của Facebook... ---")
        
        # 1. Bắt các request gửi dữ liệu Log/Tracking của FB (Senior Analysis)
        async def track_monitor(request):
            url = request.url
            if any(k in url for k in ["/ajax/bz", "/tr/", "logging", "pixel", "graph.facebook", "connect.facebook"]):
                # Cố gắng xem payload nếu là POST
                payload = ""
                if request.method == "POST":
                    try: 
                        p_data = request.post_data
                        if p_data: payload = f" | Payload: {p_data[:150]}..."
                    except: pass
                logging.info(f"📡 [FB_TRACKING] {request.method} -> {url[:100]}{payload}")

        page.on("request", track_monitor)

        # 2. Inject JS để bắt FB đọc thông số Browser (Fingerprinting Detection)
        monitor_js = """
            (function() {
                // Monitor Canvas Fingerprinting
                const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
                CanvasRenderingContext2D.prototype.getImageData = function() {
                    console.log('🕵️ [FINGERPRINT] Facebook đang đọc dữ liệu Canvas (Hình ảnh ẩn)!');
                    return originalGetImageData.apply(this, arguments);
                };

                // Monitor Battery API
                if (navigator.getBattery) {
                    const originalGetBattery = navigator.getBattery;
                    navigator.getBattery = function() {
                        console.log('🕵️ [FINGERPRINT] Facebook đang check dung lượng pin!');
                        return originalGetBattery.apply(this, arguments);
                    };
                }
            })();
        """
        await page.add_init_script(monitor_js)

        # Hiển thị log Fingerprint ra terminal
        page.on("console", lambda msg: logging.info(f"🚩 [DETECTED] {msg.text}") if "🕵️" in msg.text else None)
        
        # Truy cập trang chủ để kích hoạt tracker
        await page.goto("https://www.facebook.com/", wait_until="load", timeout=20000)
        await asyncio.sleep(2)
        return True
    except Exception as e:
        logging.error(f"Lỗi trong monitor setup: {e}")
        return False

async def browser_heartbeat(page, stop_event):
    """Giữ trình duyệt 'Active' bằng mọi giá"""
    logging.info("💓 [WATCHDOG] Kích hoạt Heartbeat giữ trình duyệt...")
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001 | 0x00000040)
    except: pass

    try:
        while not stop_event.is_set():
            if win32gui:
                try:
                    def callback(hwnd, extra):
                        title = win32gui.GetWindowText(hwnd).lower()
                        if "camoufox" in title or "facebook" in title:
                            win32gui.PostMessage(hwnd, win32con.WM_NULL, 0, 0)
                    win32gui.EnumWindows(callback, None)
                except: pass

            try:
                await page.evaluate("1") 
                if random.random() < 0.3:
                    await page.mouse.move(random.randint(0, 100), random.randint(0, 100), steps=2)
            except: pass
            
            await asyncio.sleep(3)
    except Exception as e:
        logging.debug(f"Heartbeat stopped: {e}")

async def run_facebook_registration_flow(browser, mail, email, stop_heartbeat, heartbeat_task):
    page = browser.page
    password = generate_random_password()
    last_name, first_name = generate_random_name()
    
    logging.info(f"[FB_REG] --- 🚀 KHỞI ĐỘNG LUỒNG ĐĂNG KÝ FACEBOOK ---")
    logging.info(f"[FB_REG] Email mục tiêu: {email} | Họ: {last_name} | Tên: {first_name}")
    
    try:
        # ---------- BƯỚC 1: TRUY CẬP TRANG ĐĂNG KÝ ----------
        logging.info("[FB_REG] 1️⃣ Truy cập trang đăng ký...")
        # Sử dụng URL đăng ký có entry_point theo yêu cầu để tăng độ tin cậy
        reg_url = "https://www.facebook.com/reg/?entry_point=login&next="
        await page.goto(reg_url, wait_until="load", timeout=30000)
        await asyncio.sleep(random.uniform(2.0, 3.5))
        await page.screenshot(path="debug_step1_loaded.png")

        # ---------- BƯỚC 2: ĐIỀN THÔNG TIN CÁ NHÂN (Họ, Tên, Email, Pass) ----------
        logging.info("[FB_REG] 2️⃣ Điền thông tin cá nhân...")
        
        try:
            # Chờ ít nhất 1 ô input hiện ra
            await page.wait_for_selector('input', timeout=15000)
            await asyncio.sleep(random.uniform(1.0, 2.0))
            
            inputs = page.locator('input')
            
            async def human_fill(locator, text):
                await locator.focus()
                await asyncio.sleep(random.uniform(0.2, 0.4))
                # Gõ từng phím với delay ngẫu nhiên cực độ
                for char in text:
                    await page.keyboard.type(char, delay=random.randint(50, 150))
                    if random.random() < 0.1: await asyncio.sleep(random.uniform(0.1, 0.2))
                # Ép React cập nhật State
                await locator.evaluate("node => { node.dispatchEvent(new Event('input', { bubbles: true })); node.dispatchEvent(new Event('change', { bubbles: true })); node.dispatchEvent(new Event('blur', { bubbles: true })); }")
                await asyncio.sleep(random.uniform(0.3, 0.6))

            # 1. Điền Họ (ô index 0)
            await human_fill(inputs.nth(0), last_name)
            logging.info(f"✅ Đã điền Họ: {last_name}")

            # 2. Điền Tên (ô index 1)
            await human_fill(inputs.nth(1), first_name)
            logging.info(f"✅ Đã điền Tên: {first_name}")

            # ---------- BƯỚC 3: KHÁM PHÁ VÀ ĐIỀN FORM BẰNG TAB (SMART TAB) ----------
            logging.info("[FB_REG] 3️⃣ Bắt đầu SMART TAB để điền thông tin...")
            day   = str(random.randint(1, 28))
            month = str(random.randint(1, 12))
            year  = str(random.randint(1990, 2005))
            
            filled = {
                "Ngày": False, "Tháng": False, "Năm": False, 
                "Giới tính": False, "Email": False, "Pass": False
            }

            prev_focus_text = ""
            for i in range(1, 25): # Tăng lên 25 lần Tab để quét kỹ hơn
                # Đóng mọi popup/tooltip có thể che khuất hoặc bẫy focus
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.2)
                
                focus = await tab_and_debug(page, f"Step_{i}")
                if not focus: continue
                
                tag = focus['tag'].upper()
                aria = (focus['aria'] or "").lower()
                text = (focus['text'] or "").lower()
                role = (focus['role'] or "").lower()
                
                # Tránh bị kẹt lặp đi lặp lại một chỗ (Dùng ID tổng hợp để phân biệt các ô input trống)
                current_focus_id = f"{tag}|{aria}|{role}|{text}"
                if current_focus_id == prev_focus_text and i > 5:
                    logging.warning(f"⚠️ Phát hiện lặp focus ({tag}), thử bấm Tab lần nữa...")
                    await page.keyboard.press("Tab")
                    continue
                prev_focus_text = current_focus_id

                # Biến cờ hiệu: Đây có phải là một ô lựa chọn (Dropdown/Combobox) không?
                is_picker = role == "combobox" or tag == "SELECT" or "chọn" in aria or "chọn" in text

                # Né các link và nút thông tin
                if tag == "A":
                    logging.info(f"⏭️ Bỏ qua link: {text}")
                    continue
                
                if "nhấp để" in aria or "trợ giúp" in aria or "thông tin" in aria:
                    logging.info(f"⏭️ Bỏ qua nút trợ giúp: {aria}")
                    continue

                # Nhận diện Ngày
                if not filled["Ngày"] and is_picker and ("ngày" in aria or "day" in aria or i == 3):
                    logging.info(f"🎯 Đang điền Ngày: {day}")
                    if role == "combobox": await page.keyboard.press("Space")
                    await asyncio.sleep(0.5)
                    await page.keyboard.type(day, delay=100)
                    await asyncio.sleep(0.5)
                    await page.keyboard.press("Enter")
                    filled["Ngày"] = True
                    await asyncio.sleep(0.5)
                    await page.keyboard.press("Escape")
                    continue

                # Nhận diện Tháng
                if not filled["Tháng"] and is_picker and ("tháng" in aria or "month" in aria or i == 4):
                    logging.info(f"🎯 Đang điền Tháng: {month}")
                    if role == "combobox": await page.keyboard.press("Space")
                    await asyncio.sleep(0.5)
                    # Xóa dữ liệu cũ nếu có
                    for _ in range(5): await page.keyboard.press("Backspace")
                    await asyncio.sleep(0.3)
                    
                    # Gõ "Tháng X" - Đây là format chuẩn của FB VN
                    await page.keyboard.type(f"Tháng {month}", delay=150)
                    await asyncio.sleep(0.8)
                    await page.keyboard.press("Enter")
                    
                    filled["Tháng"] = True
                    await asyncio.sleep(0.5)
                    await page.keyboard.press("Escape")
                    continue

                # Nhận diện Năm
                if not filled["Năm"] and is_picker and ("năm" in aria or "year" in aria or i == 5):
                    logging.info(f"🎯 Đang điền Năm: {year}")
                    if role == "combobox": await page.keyboard.press("Space")
                    await asyncio.sleep(0.5)
                    await page.keyboard.type(year, delay=100)
                    await asyncio.sleep(0.5)
                    await page.keyboard.press("Enter")
                    filled["Năm"] = True
                    await asyncio.sleep(0.5)
                    await page.keyboard.press("Escape")
                    continue

                # Nhận diện Giới tính (Dựa vào text nếu aria trống)
                if not filled["Giới tính"] and is_picker and ("giới tính" in aria or "giới tính" in text or "gender" in aria or i == 7):
                    logging.info("🎯 Đang chọn Giới tính: Nam")
                    if role == "combobox": await page.keyboard.press("Space")
                    await asyncio.sleep(1.0) # Đợi menu hiện ra hẳn
                    await page.keyboard.type("Nam", delay=100)
                    await asyncio.sleep(0.5)
                    await page.keyboard.press("Enter")
                    filled["Giới tính"] = True
                    await asyncio.sleep(0.5)
                    await page.keyboard.press("Escape")
                    continue

                # Nhận diện Email (Sau ô giới tính thường là Email)
                if not filled["Email"] and tag == "INPUT" and ("email" in aria or "di động" in aria or (filled["Giới tính"] and i <= 10)):
                    logging.info(f"🎯 Đang điền Email: {email} (Step {i})")
                    # Gõ email với delay thật
                    for char in email:
                        await page.keyboard.type(char, delay=random.randint(40, 120))
                    # Trigger React State
                    await page.evaluate("document.activeElement.dispatchEvent(new Event('input', { bubbles: true }))")
                    filled["Email"] = True
                    await asyncio.sleep(random.uniform(0.5, 0.8))
                    continue

                # Nhận diện Mật khẩu (Sau ô email hoặc có aria password)
                if not filled["Pass"] and tag == "INPUT" and ("mật khẩu" in aria or "password" in aria or (filled["Email"] and i > 8)):
                    logging.info(f"🎯 Đang điền Mật khẩu (Step {i})...")
                    for char in password:
                        await page.keyboard.type(char, delay=random.randint(50, 130))
                    # Trigger React State
                    await page.evaluate("document.activeElement.dispatchEvent(new Event('input', { bubbles: true }))")
                    filled["Pass"] = True
                    await asyncio.sleep(random.uniform(0.6, 1.0))
                    continue

                # Điểm dừng: Nút Submit (GỬI)
                is_submit_text = "gửi" in text or "đăng ký" in text or "tiếp tục" in text
                is_submit_role = role == "button" or tag == "BUTTON"
                
                if is_submit_text and is_submit_role and filled["Email"] and filled["Pass"]:
                    logging.info(f"🏁 Đã đến nút Submit ({text}). Thực hiện chiến thuật 'Nhấn -> Chờ -> Sửa'...")
                    try:
                        # Senior Logic: Nhấn Submit lần 1
                        await page.keyboard.press("Enter")
                        await asyncio.sleep(3)
                        
                        # 2. Kiểm tra nếu có thông báo lỗi hiện ra (Checkpoint sớm)
                        error_msg = await page.evaluate("() => Array.from(document.querySelectorAll('div[role=\"alert\"], ._58mo')).map(e => e.innerText).join(' ')")
                        if error_msg:
                            logging.warning(f"⚠️ Thấy thông báo lỗi: {error_msg}. Thực hiện quay về sửa Tên/Pass...")
                            # Quay lại ô Tên (Step 1)
                            for _ in range(15): await page.keyboard.press("Shift+Tab")
                            await asyncio.sleep(1)
                            # Gõ đè lại Tên
                            new_last, new_first = generate_random_name()
                            await page.keyboard.press("Control+A")
                            await page.keyboard.press("Backspace")
                            await page.keyboard.type(new_last, delay=100)
                            await page.keyboard.press("Tab")
                            await page.keyboard.press("Control+A")
                            await page.keyboard.press("Backspace")
                            await page.keyboard.type(new_first, delay=100)
                            
                            logging.info("♻️ Đã sửa lại Tên. Tiến hành Submit lại...")
                            for _ in range(15): await page.keyboard.press("Tab")
                            await page.keyboard.press("Enter")
                        
                        # Fallback click nếu Enter không nhảy
                        if "reg" in page.url or "r.php" in page.url:
                            logging.info("🖱️ Vẫn ở trang cũ -> Click trực tiếp Submit...")
                            submit_btn = page.locator('button[type="submit"], [role="button"]:has-text("gửi"), [role="button"]:has-text("đăng ký")').first
                            if await submit_btn.count() > 0:
                                await submit_btn.click(force=True, timeout=3000)
                        
                        logging.info("✅ Đã xử lý lệnh Submit. Đợi OTP (10s)...")
                        await asyncio.sleep(10)
                        break 
                    except Exception as e:
                        logging.error(f"Lỗi khi thực hiện Submit: {e}")
                        break
                elif is_submit_text and is_submit_role:
                    logging.warning(f"⚠️ Thấy nút {text} nhưng form chưa đầy đủ ({filled}). Tab tiếp...")
                    continue

            logging.info(f"✅ Kết quả SMART TAB: {filled}")

            logging.info(f"✅ Kết quả SMART TAB: {filled}")

        except Exception as ex:
            logging.error(f"Lỗi trong chuỗi điền form Tab-Sequence: {ex}")
            await save_debug_info(page, "tab_sequence_error")
            return False, "FILL_ERROR"

        # Đã thực hiện Submit trong vòng lặp Tab ở trên.
        logging.info("[FB_REG] Đang chuyển sang Bước 6: Xác thực OTP...")

        # ---------- BƯỚC 6: XÁC THỰC OTP BẰNG SMART TAB ----------
        logging.info("[FB_REG] 6️⃣ Bắt đầu SMART TAB để nhập mã OTP...")
        
        # Đợi một chút để trang tải hẳn (Captcha hoặc OTP)
        await asyncio.sleep(5)

        otp_filled = False
        prev_otp_focus = ""
        
        # 1. LẤY MÃ TRƯỚC (Để sẵn sàng điền khi thấy ô)
        logging.info("[FB_REG] 🔍 Đang check mail lấy mã OTP...")
        code = await asyncio.to_thread(mail.check_inbox, timeout=120)
        
        if not code:
            logging.error("[FB_REG] Không lấy được mã code từ email.")
        else:
            logging.info(f"[FB_REG] 🎉 Đã lấy được mã: {code}")

        for i in range(1, 21):
            # 2. KIỂM TRA TRẠNG THÁI TRANG (Checkpoint / Captcha)
            page_url = page.url.lower()
            # Senior Fix: Kiểm tra an toàn document.body để tránh crash khi trang đang load
            page_text = await page.evaluate("document.body ? document.body.innerText.toLowerCase() : ''")
            
            is_checkpoint = any(k in page_url for k in ["checkpoint", "disabled", "confirminentity"])
            # Tách riêng Captcha để không bị catch nhầm vào Video Selfie
            is_captcha_page = any(k in page_text for k in ["security check", "kiểm tra bảo mật", "văn bản từ hình ảnh", "văn bản trong ô", "text in the box", "nghe mã", "văn bản từ hình"])
            is_video_step = any(k in page_text for k in ["video selfie", "robot", "phải là người", "tải video", "quay video"])
            
            # ƯU TIÊN GIẢI CAPTCHA NẾU CÓ
            if is_captcha_page:
                logging.warning("🧩 [CAPTCHA] Phát hiện trang CAPTCHA!")
                
                # --- AUDIO CAPTCHA SWITCH (3 cách do tab) ---
                switched_to_audio = False
                logging.info("--- BƯỚC 1: Tìm nút 'Nghe mã này' (Thiết kế 3 lớp) ---")
                
                audio_btn = page.locator('a:has-text("Nghe mã này"), a:has-text("Hear"), button:has-text("nghe"), [aria-label*="nghe"], [aria-label*="Nghe mã này"]').first
                try:
                    if await audio_btn.count() > 0:
                        await audio_btn.click(timeout=3000)
                        switched_to_audio = True
                        logging.info("🎧 Đã click nút Nghe Mã (Cách 1 - Locator).")
                except: pass
                
                if not switched_to_audio:
                    logging.info("🎧 Chuyển sang Cách 2: Kỹ thuật Tab dò nút Nghe Mã...")
                    for t in range(25):
                        await page.keyboard.press("Tab")
                        await asyncio.sleep(0.2)
                        el = page.locator(":focus")
                        if await el.count() > 0:
                            text = (await el.text_content() or "").lower()
                            aria = (await el.get_attribute("aria-label") or "").lower()
                            if "nghe mã" in text or "nghe mã" in aria or "hear this" in text or "âm thanh" in text:
                                logging.info(f"🎯 Đã Tab trúng nút Nghe Mã ({text})! Bấm Enter...")
                                await page.keyboard.press("Enter")
                                switched_to_audio = True
                                break
                                
                if not switched_to_audio:
                    logging.info("🎧 Mồi thêm Cách 3: JS Force Click...")
                    try:
                        switched_to_audio = await page.evaluate("""() => {
                            let links = document.querySelectorAll('a, button, div[role="button"]');
                            for (let l of links) {
                                let txt = (l.innerText || '').toLowerCase();
                                let aria = (l.getAttribute('aria-label') || '').toLowerCase();
                                if (txt.includes('nghe mã') || aria.includes('nghe') || txt.includes('hear this code')) {
                                    l.click(); return true;
                                }
                            }
                            return false;
                        }""")
                    except: pass
                
                if switched_to_audio:
                    logging.info("🎧 Chờ 3s để giao diện chuyển sang Audio Captcha...")
                    await asyncio.sleep(3)
                    # Screenshot để xem giao diện thực tế sau khi click nghe mã
                    await page.screenshot(path="debug_audio_captcha_ui.png")
                    logging.info("📸 [AUDIO_DEBUG] Đã chụp màn hình: debug_audio_captcha_ui.png")
                
                # DEBUG: Liệt kê tất cả ảnh trên trang để tìm CAPTCHA
                all_imgs = await page.evaluate("""() => {
                    const imgs = document.querySelectorAll('img');
                    return Array.from(imgs).map(img => ({
                        src: img.src.substring(0, 120),
                        alt: img.alt,
                        w: img.naturalWidth || img.width,
                        h: img.naturalHeight || img.height,
                        cls: img.className.substring(0, 60)
                    }));
                }""")
                logging.info(f"🖼️ [DEBUG] Tìm thấy {len(all_imgs)} ảnh trên trang:")
                for idx, im in enumerate(all_imgs):
                    logging.info(f"   IMG[{idx}]: {im['w']}x{im['h']} | alt='{im['alt']}' | src={im['src']}")
                
                for attempt in range(1, 4):
                    logging.info(f"🔄 [CAPTCHA] Auto-solve lần #{attempt}...")
                    captcha_code = ""
                    
                    if switched_to_audio:
                        logging.info("--- 🔍 [AUDIO DEBUG] PHÂN TÍCH TOÀN BỘ DOM TÌM AUDIO ---")
                        
                        # === DEBUG CỰC KỲ CHI TIẾT: Quét DOM ===
                        audio_debug = await page.evaluate("""() => {
                            let result = {audios: [], sources: [], links: [], iframes: []};
                            
                            // 1. Tìm tất cả thẻ <audio>
                            document.querySelectorAll('audio').forEach((a, i) => {
                                result.audios.push({
                                    index: i,
                                    src: a.src || '',
                                    currentSrc: a.currentSrc || '',
                                    paused: a.paused,
                                    duration: a.duration,
                                    readyState: a.readyState,
                                    html: a.outerHTML.substring(0, 300)
                                });
                            });
                            
                            // 2. Tìm tất cả thẻ <source>
                            document.querySelectorAll('source').forEach((s, i) => {
                                result.sources.push({
                                    index: i,
                                    src: s.src || '',
                                    type: s.type || ''
                                });
                            });
                            
                            // 3. Tìm links có thể là audio
                            document.querySelectorAll('a').forEach((l, i) => {
                                const href = l.href || '';
                                const text = (l.innerText || '').toLowerCase();
                                if (href.includes('audio') || href.includes('captcha') || 
                                    href.includes('.mp3') || href.includes('.ogg') || href.includes('.wav') ||
                                    text.includes('nghe') || text.includes('hear') || text.includes('audio') ||
                                    text.includes('tải') || text.includes('download')) {
                                    result.links.push({href: href.substring(0, 200), text: l.innerText.substring(0, 50)});
                                }
                            });
                            
                            // 4. Tìm iframes (FB thỉnh thoảng nhúng audio qua iframe)
                            document.querySelectorAll('iframe').forEach((f, i) => {
                                result.iframes.push({src: f.src.substring(0, 200), id: f.id});
                            });
                            
                            return result;
                        }""")
                        
                        logging.info(f"🎵 [AUDIO_DEBUG] Thẻ <audio> tìm thấy: {len(audio_debug['audios'])}")
                        for a in audio_debug['audios']:
                            logging.info(f"   audio[{a['index']}]: src={a['src'][:100]} | currentSrc={a['currentSrc'][:100]}")
                            logging.info(f"   audio[{a['index']}]: paused={a['paused']} | readyState={a['readyState']} | duration={a['duration']}")
                            logging.info(f"   audio[{a['index']}]: outerHTML={a['html']}")
                        
                        logging.info(f"🎵 [AUDIO_DEBUG] Thẻ <source> tìm thấy: {len(audio_debug['sources'])}")
                        for s in audio_debug['sources']:
                            logging.info(f"   source: src={s['src'][:150]} | type={s['type']}")
                        
                        logging.info(f"🔗 [AUDIO_DEBUG] Links liên quan audio: {len(audio_debug['links'])}")
                        for l in audio_debug['links']:
                            logging.info(f"   link: text='{l['text']}' | href={l['href'][:150]}")
                        
                        logging.info(f"📦 [AUDIO_DEBUG] Iframes: {len(audio_debug['iframes'])}")
                        for f in audio_debug['iframes']:
                            logging.info(f"   iframe: src={f['src'][:150]} | id={f['id']}")
                        
                        # === Dump toàn bộ HTML để debug ===
                        html_dump_path = f"debug_audio_page_{attempt}.html"
                        page_html = await page.content()
                        with open(html_dump_path, "w", encoding="utf-8") as f:
                            f.write(page_html)
                        logging.info(f"💾 [AUDIO_DEBUG] Đã dump HTML trang: {html_dump_path} ({len(page_html)} bytes)")
                        
                        # === THU THẬP URL TỪ KẾT QUẢ DEBUG ===
                        audio_url = None
                        # Prioritize real audio sources
                        for a in audio_debug['audios']:
                            if a['currentSrc']:
                                audio_url = a['currentSrc']
                                logging.info(f"✅ [AUDIO] Bắt từ <audio> currentSrc: {audio_url[:100]}")
                                break
                            if a['src']:
                                audio_url = a['src']
                                logging.info(f"✅ [AUDIO] Bắt từ <audio> src: {audio_url[:100]}")
                                break
                        
                        if not audio_url:
                            for s in audio_debug['sources']:
                                if s['src']:
                                    audio_url = s['src']
                                    logging.info(f"✅ [AUDIO] Bắt từ <source>: {audio_url[:100]}")
                                    break
                                    
                        if not audio_url:
                            # Only accept links if they look like real audio endpoints
                            current_url_path = page.url.split('#')[0].split('?')[0]
                            for l in audio_debug['links']:
                                href = l['href'].split('#')[0]
                                if not href or href == current_url_path: continue
                                if any(k in href.lower() for k in ['tfbaudio', 'audiocaptcha', '.mp3', '.wav']):
                                    audio_url = l['href']
                                    logging.info(f"✅ [AUDIO] Bắt từ link hợp lệ: {audio_url[:100]}")
                                    break
                        
                        if audio_url:
                            logging.info(f"🎤 Đã bắt được URL Audio hợp lệ. Downloading...")
                            try:
                                b64 = await page.evaluate(f"""async () => {{
                                    try {{
                                        let resp = await fetch("{audio_url}");
                                        if (!resp.ok) throw new Error("Fetch failed with status " + resp.status);
                                        let blob = await resp.blob();
                                        if (blob.size < 100) throw new Error("File too small (" + blob.size + " bytes)");
                                        return new Promise((resolve, reject) => {{
                                            let reader = new FileReader();
                                            reader.onloadend = () => {{
                                                const base64data = reader.result.split(',')[1];
                                                if (!base64data) reject("Empty base64 data");
                                                resolve(base64data);
                                            }};
                                            reader.onerror = reject;
                                            reader.readAsDataURL(blob);
                                        }});
                                    }} catch (e) {{
                                        return "ERROR:" + e.message;
                                    }}
                                }}""")
                                if b64.startswith("ERROR:"):
                                    logging.error(f"❌ [AUDIO FETCH ERROR] {b64[6:]}")
                                    captcha_code = ""
                                else:
                                    captcha_code = AUDIO_SOLVER.solve_audio(b64)
                            except Exception as down_e:
                                logging.warning(f"⚠️ Fetch Audio thất bại: {down_e}")
                        else:
                            logging.warning("⚠️ Không tìm thấy thẻ Audio URL hợp lệ! Lùi về OCR...")
                            
                    # Fallback ảnh (nếu ko audio hoặc audio xịt ko lấy dc url)
                    if not switched_to_audio or not captcha_code:
                        logging.info("--- THỬ GIẢI OCR MẢNH ẢNH ---")
                        # Tìm ảnh CAPTCHA bằng nhiều chiến lược
                    captcha_el = None
                    
                    # Chiến lược 1: Selector mở rộng
                    for sel in [
                        'img[src*="captcha"]', 'img[alt*="captcha"]', 'img[alt*="CAPTCHA"]',
                        'img[src*="security"]', 'img[src*="checkpoint"]',
                        '#captcha_image', '.captcha_image',
                        'img[src*="scont"]', 'img[src*="pixel"]'
                    ]:
                        loc = page.locator(sel).first
                        if await loc.count() > 0:
                            captcha_el = loc
                            logging.info(f"🎯 Tìm thấy ảnh CAPTCHA bằng selector: {sel}")
                            break
                    
                    # Chiến lược 2: Tìm bằng kích thước ảnh (CAPTCHA thường 200-500px rộng)
                    if not captcha_el:
                        logging.info("🔍 Tìm CAPTCHA bằng kích thước ảnh...")
                        captcha_idx = await page.evaluate("""() => {
                            const imgs = document.querySelectorAll('img');
                            for (let i = 0; i < imgs.length; i++) {
                                const w = imgs[i].naturalWidth || imgs[i].width;
                                const h = imgs[i].naturalHeight || imgs[i].height;
                                // CAPTCHA thường có kích thước 200-500 x 50-150
                                if (w >= 150 && w <= 600 && h >= 30 && h <= 200) {
                                    return i;
                                }
                            }
                            return -1;
                        }""")
                        if captcha_idx >= 0:
                            captcha_el = page.locator(f'img').nth(captcha_idx)
                            logging.info(f"🎯 Tìm thấy ảnh CAPTCHA bằng kích thước (index: {captcha_idx})")
                    
                    if captcha_el and await asyncio.wait_for(captcha_el.count(), timeout=3.0) > 0:
                        logging.info("📸 1. Đang lấy kích thước ảnh (bounding_box)...")
                        try:
                            box = await asyncio.wait_for(captcha_el.bounding_box(), timeout=3.0)
                            if box:
                                logging.info("📸 2. Đang di chuột tới ảnh (mouse.move)...")
                                await asyncio.wait_for(page.mouse.move(box['x'] + box['width']/2, box['y'] + box['height']/2, steps=5), timeout=2.0)
                                await asyncio.sleep(0.5)
                        except Exception as e_box:
                            logging.warning(f"⚠️ Bỏ qua bounding_box/mouse.move do lỗi hoặc timeout: {e_box}")
                        
                        try:
                            logging.info("📸 3. Đang tiến hành chụp ảnh CAPTCHA (timeout 8s)...")
                            img_bytes = await asyncio.wait_for(captcha_el.screenshot(timeout=5000), timeout=8.0)
                            logging.info(f"📸 4. Chụp ảnh CAPTCHA thành công ({len(img_bytes)} bytes). Đang giải OCR...")
                            
                            if OCR_SOLVER:
                                captcha_code = OCR_SOLVER.solve_captcha(img_bytes)
                                logging.info(f"🤖 [OCR ĐA TẦNG] Kết quả: '{captcha_code}'")
                        except Exception as capture_err:
                            logging.error(f"❌ Lỗi khi chụp ảnh CAPTCHA hoặc OCR (có thể bị ẩn): {capture_err}")
                    else:
                        logging.warning("⚠️ Không tìm thấy ảnh CAPTCHA trên trang!")
                    
                    if not captcha_code:
                        if attempt < 3:
                            logging.warning("OCR trống. Thử reload mã mới...")
                            try:
                                reload = page.get_by_text("mã mới", exact=False).or_(page.get_by_text("another", exact=False))
                                if await reload.count() > 0:
                                    await reload.click()
                                    await asyncio.sleep(2)
                            except: pass
                            continue
                        else:
                            print("\n" + "?"*60)
                            captcha_code = await asyncio.to_thread(input, "👉 OCR thất bại. NHẬP MÃ: ")
                            print("?"*60 + "\n")
                    
                    if captcha_code:
                        captcha_input = page.locator('input[name="captcha_response"], input[type="text"]').first
                        try:
                            if await captcha_input.count() > 0:
                                box = await captcha_input.bounding_box()
                                if box:
                                    logging.info("🖱️ Đang click vào ô điền CAPTCHA bằng toạ độ...")
                                    await page.mouse.click(box['x'] + box['width']/2, box['y'] + box['height']/2)
                                else:
                                    logging.info("⌨️ Điền CAPTCHA bằng Tab (do ảnh che khuất)...")
                                    await page.keyboard.press("Tab")
                            else:
                                raise Exception("Không tìm thấy Box")
                        except Exception as e:
                            logging.warning(f"⚠️ Locator click bị lỗi: {e}. Dùng Tab fallback...")
                            await page.keyboard.press("Tab")
                            
                        await page.keyboard.press("Control+A")
                        await page.keyboard.press("Backspace")
                        await page.keyboard.type(captcha_code, delay=150)
                        await asyncio.sleep(0.5)
                        
                        old_cap_url = page.url
                        
                        # Dùng Tab để rà soát nút Tiếp tục (Submit) thay vì Enter thủ công
                        logging.info("--- Bắt đầu dò tìm nút Gửi / Tiếp tục bằng Tab ---")
                        submit_clicked = False
                        for t_step in range(1, 15):
                            await page.keyboard.press("Tab")
                            await asyncio.sleep(0.5)
                            el = page.locator(":focus")
                            if await el.count() > 0:
                                tag_name = await el.evaluate("el => el.tagName")
                                text = (await el.text_content() or "").strip()
                                aria = (await el.get_attribute("aria-label") or "").strip()
                                role = (await el.get_attribute("role") or "").strip()
                                
                                combined_text = f"{text} {aria}".lower()
                                logging.info(f"🔎 [TAB_DEBUG CAPTCHA] Step_{t_step} | Tag: {tag_name} | Role: {role} | Text: {text} | Aria: {aria}")
                                
                                if role == "button" or tag_name == "BUTTON":
                                    if any(k in combined_text for k in ["tiếp tục", "gửi", "bắt đầu", "continue", "submit"]):
                                        logging.info("🎯 Tìm thấy nút Submit Captcha! Bấm Enter...")
                                        await page.keyboard.press("Enter")
                                        submit_clicked = True
                                        await asyncio.sleep(1)
                                        break
                        
                        if not submit_clicked:
                            logging.warning("⚠️ Không tìm thấy nút Submit, bấm Enter dự phòng...")
                            await page.keyboard.press("Enter")
                        
                        logging.info(f"✅ Đã xử lý gửi CAPTCHA: {captcha_code}. Đợi 10s để test...")
                        await asyncio.sleep(10) # NGỦ KIỂM TRA MÃ CỦA USER
                        
                        if page.url != old_cap_url:
                            logging.info("🎉 [CAPTCHA] Vượt qua thành công!")
                            break
                        else:
                            cap_check = await page.evaluate("document.body ? document.body.innerText.toLowerCase() : ''")
                            if any(k in cap_check for k in ["văn bản từ hình ảnh", "text in the box"]):
                                logging.warning(f"❌ CAPTCHA sai (#{attempt}). Thử lại...")
                                continue
                            else:
                                logging.info("🎉 [CAPTCHA] Có vẻ đã vượt qua!")
                                break
                continue

            # NẾU LÀ CHECKPOINT: TÌM VÀ BẤM NÚT "TIẾP TỤC" BẰNG LOCATOR (Chính xác hơn Tab)
            if (is_checkpoint or is_video_step) and not is_captcha_page:
                logging.warning(f"🚨 [DETECTION] Phát hiện trang xác minh (Bridge/Video) tại: {page_url}")
                
                # CHIẾN LƯỢC 1: Dùng Locator trực tiếp tìm nút trên trang
                bridge_texts = ["Tiếp tục", "Bắt đầu", "Continue", "Start", "ดำเนินการต่อ"]
                found_bridge = False
                
                for btn_text in bridge_texts:
                    try:
                        # Tìm bằng text chính xác (cả button thường và div[role=button])
                        btn = page.get_by_role("button", name=btn_text, exact=True)
                        if await btn.count() > 0:
                            logging.info(f"🚀 [LOCATOR] Thấy nút '{btn_text}' -> Click trực tiếp!")
                            # Human-like: di chuột đến rồi click
                            box = await btn.bounding_box()
                            if box:
                                await page.mouse.move(box['x'] + box['width']/2, box['y'] + box['height']/2, steps=5)
                                await asyncio.sleep(0.3)
                            await btn.click(timeout=5000)
                            found_bridge = True
                            logging.info(f"✅ Đã click '{btn_text}' thành công! Đợi trang load...")
                            await asyncio.sleep(5)
                            break
                    except Exception as e:
                        logging.debug(f"Không tìm thấy nút '{btn_text}': {e}")
                
                # CHIẾN LƯỢC 2: Nếu Locator không thấy, tìm bằng JS evaluate
                if not found_bridge:
                    try:
                        clicked = await page.evaluate("""() => {
                            const btns = document.querySelectorAll('[role="button"], button');
                            for (const b of btns) {
                                const t = b.innerText.trim().toLowerCase();
                                if (t === 'tiếp tục' || t === 'bắt đầu' || t === 'continue' || t === 'start') {
                                    b.click();
                                    return t;
                                }
                            }
                            return null;
                        }""")
                        if clicked:
                            logging.info(f"🚀 [JS_CLICK] Đã click nút '{clicked}' bằng JS evaluate!")
                            found_bridge = True
                            await asyncio.sleep(5)
                    except Exception as e:
                        logging.error(f"Lỗi JS evaluate: {e}")

                if found_bridge:
                    continue # Quay lại vòng lặp để xử lý trang tiếp theo

                # CHỈ PAUSE NẾU KHÔNG THẤY NÚT ĐỂ BẤM (Trang quay Video thực sự)
                content = await page.content()
                with open("debug_checkpoint_structure.html", "w", encoding="utf-8") as f:
                    f.write(content)
                logging.info("💾 Đã lưu cấu trúc trang vào file: debug_checkpoint_structure.html")
                
                await save_debug_info(page, "checkpoint_stuck")
                print("\n" + "!"*60)
                print("PAUSE MODE: Đã kẹt tại trang xác minh (Không thấy nút 'Tiếp tục').")
                print(f"URL: {page_url}")
                print("Nhấn ENTER tại terminal sau khi đã nghiên cứu xong...")
                print("!"*60 + "\n")
                await asyncio.to_thread(input, "")
                return False, "CHECKPOINT_STUCK"

            focus = await tab_and_debug(page, f"Step_Verification_{i}")
            if not focus: continue
            
            tag = focus['tag'].upper()
            aria = (focus['aria'] or "").lower()
            text = (focus['text'] or "").lower()
            role = (focus['role'] or "").lower()
            
            # Tránh lặp và bỏ qua các thành phần không mong muốn
            current_id = f"{tag}|{aria}|{text}"
            if current_id == prev_otp_focus:
                await page.keyboard.press("Tab")
                continue
            prev_otp_focus = current_id
            
            # Danh sách từ khóa ngôn ngữ dày đặc để tuyệt đối không bấm nhầm
            lang_blacklist = [
                "english", "tiếng việt", "中文", "한국어", "bahasa", "español", "français", 
                "deutsch", "português", "italiano", "日本語", "ภาษาไทย", "türkçe", "polski",
                "română", "русский", "हिन्दी", "bengali", "ਪੰਜਾਬੀ", "తెలుగు", "தமிழ்"
            ]
            
            # Nếu là thành phần ngôn ngữ, hãy bỏ qua ngay
            is_lang_btn = any(k in text or k in aria for k in lang_blacklist)
            if is_lang_btn:
                logging.info(f"⏭️ [GUARD] Bỏ qua nút ngôn ngữ để tránh đổi giao diện: {text or aria}")
                await page.keyboard.press("Tab")
                continue

            # Kiểm tra xem đã thoát khỏi luồng Checkpoint chưa
            if "checkpoint" not in page.url.lower() and "confirm" not in page.url.lower() and i > 5:
                logging.info("🏁 Có vẻ đã thoát khỏi luồng xác minh. Kiểm tra kết quả...")
                break

            # Nhận diện ô nhập mã OTP
            is_otp_input = tag == "INPUT" and (not aria or "mã" in aria or "code" in aria or "xác nhận" in aria)
            if not otp_filled and code and is_otp_input:
                logging.info(f"🎯 Xác định ô nhập mã OTP! Điền: {code}")
                await page.keyboard.type(code, delay=100)
                otp_filled = True
                await asyncio.sleep(0.5)
                continue

            # Nhận diện nút Submit OTP (Tiếp tục) - Ưu tiên Primary Buttons
            is_otp_submit = any(k in text for k in ["tiếp tục", "xác nhận", "continue", "confirm", "확인", "ok", "next", "ดำเนินการต่อ"])
            if (role == "button" or tag == "BUTTON") and is_otp_submit:
                logging.info(f"🎯 Đã thấy nút Submit chính ({text})! Nhấn Enter...")
                old_url = page.url
                await page.keyboard.press("Enter")
                
                # POLLING: Chờ URL thay đổi (tối đa 15 giây)
                logging.info("⏳ Đợi trang chuyển sau khi nhấn Submit...")
                for wait_i in range(10):
                    await asyncio.sleep(1.5)
                    new_url = page.url
                    if new_url != old_url:
                        logging.info(f"🔄 [URL_CHANGED] Trang đã chuyển sau {(wait_i+1)*1.5}s: {new_url}")
                        break
                else:
                    logging.warning("⚠️ URL không thay đổi sau 15s. Tiếp tục kiểm tra...")
                
                # RE-CHECK: Sau khi trang đã chuyển, kiểm tra ngay
                new_url = page.url.lower()
                # Senior Fix: Thêm delay nhỏ và check null để tránh lỗi document.body
                await asyncio.sleep(0.5)
                new_text = await page.evaluate("document.body ? document.body.innerText.toLowerCase() : ''")
                
                # Nếu là trang Checkpoint Bridge -> Tìm và click nút "Tiếp tục"
                if "checkpoint" in new_url or "xác nhận" in new_text or "người thật" in new_text:
                    logging.info("🔄 Đang ở trang Checkpoint Bridge! Tìm nút bằng Locator...")
                    await asyncio.sleep(2) # Chờ trang render hoàn toàn
                    
                    for btn_label in ["Tiếp tục", "Bắt đầu", "Continue", "Start", "ดำเนินการต่อ"]:
                        try:
                            bridge_btn = page.get_by_role("button", name=btn_label, exact=True)
                            if await bridge_btn.count() > 0:
                                logging.info(f"🚀 [BRIDGE] Thấy nút '{btn_label}'!")
                                box = await bridge_btn.bounding_box()
                                if box:
                                    await page.mouse.move(box['x'] + box['width']/2, box['y'] + box['height']/2, steps=5)
                                    await asyncio.sleep(0.3)
                                await bridge_btn.click(timeout=5000)
                                logging.info(f"✅ [BRIDGE] Đã click '{btn_label}' thành công!")
                                await asyncio.sleep(5)
                                break
                        except Exception as be:
                            logging.debug(f"Không thấy '{btn_label}': {be}")
                    
                    # Sau khi click Bridge, check tiếp xem có CAPTCHA không
                    # Sau khi click Bridge, check tiếp xem có CAPTCHA không
                    captcha_text = await page.evaluate("document.body ? document.body.innerText.toLowerCase() : ''")
                    if any(k in captcha_text for k in ["văn bản từ hình ảnh", "security check", "text in the box", "nghe mã", "âm thanh"]):
                        logging.info("🧩 [CAPTCHA] Phát hiện CAPTCHA ngay sau Bridge!")
                        
                        # --- AUDIO CAPTCHA BRIDGE SWITCH (3 cách do tab) ---
                        switched_to_audio_br = False
                        logging.info("--- BƯỚC 1: Tìm nút 'Nghe mã này' Bridge (Stacking 3 lớp) ---")
                        
                        try:
                            audio_btn_br = page.locator('a:has-text("Nghe mã này"), a:has-text("Hear"), button:has-text("nghe"), [aria-label*="nghe"], [aria-label*="Nghe mã này"]').first
                            if await audio_btn_br.count() > 0:
                                await audio_btn_br.click(timeout=3000)
                                switched_to_audio_br = True
                                logging.info("🎧 Đã click nút Nghe Mã Bridge (Cách 1).")
                        except: pass
                        
                        if not switched_to_audio_br:
                            logging.info("🎧 C2: Tab dò nút Nghe Mã Bridge...")
                            for t in range(25):
                                await page.keyboard.press("Tab")
                                await asyncio.sleep(0.2)
                                el = page.locator(":focus")
                                if await el.count() > 0:
                                    t_c = ((await el.text_content() or "") + " " + (await el.get_attribute("aria-label") or "")).lower()
                                    if "nghe mã" in t_c or "hear this" in t_c or "âm thanh" in t_c:
                                        logging.info(f"🎯 Đã Tab trúng nút Nghe Mã Bridge! Enter...")
                                        await page.keyboard.press("Enter")
                                        switched_to_audio_br = True
                                        break
                                        
                        if not switched_to_audio_br:
                            logging.info("🎧 C3: JS click Nghe Mã Bridge...")
                            try:
                                switched_to_audio_br = await page.evaluate("""() => {
                                    let links = document.querySelectorAll('a, button, div[role="button"]');
                                    for (let l of links) {
                                        let txt = ((l.innerText||'') + ' ' + (l.getAttribute('aria-label')||'')).toLowerCase();
                                        if (txt.includes('nghe mã') || txt.includes('hear this')) {
                                            l.click(); return true;
                                        }
                                    } return false;
                                }""")
                            except: pass
                        
                        if switched_to_audio_br:
                            logging.info("🎧 Chờ 3s load Audio Captcha Bridge...")
                            await asyncio.sleep(3)

                        # AUTO-SOLVE LOOP: Thử giải tự động tối đa 3 lần
                        for attempt in range(1, 4):
                            logging.info(f"🔄 [CAPTCHA] Lần thử #{attempt}...")
                            captcha_code = ""

                            if switched_to_audio_br:
                                logging.info("--- BƯỚC 2: Bật công nghệ SpeechToText lấy Audio URL Bridge ---")
                                audio_url_br = None
                                try:
                                    audio_url_br = await page.evaluate("""() => {
                                        let a = document.querySelector('audio source') || document.querySelector('audio');
                                        if (a && a.src) return a.src;
                                        for (let l of document.querySelectorAll('a')) {
                                            let ht = (l.href||'') + ' ' + (l.innerText||'').toLowerCase();
                                            if(ht.includes('audiocaptcha') || ht.includes('tải') || ht.includes('download') || ht.includes('play')) return l.href;
                                        } return null;
                                    }""")
                                except: pass
                                
                                if audio_url_br:
                                    logging.info(f"🎤 Fetching Audio Bridge...")
                                    try:
                                        b64 = await page.evaluate(f"""async () => {{
                                            let resp = await fetch("{audio_url_br}"); let blob = await resp.blob();
                                            return new Promise((r) => {{ let rd = new FileReader(); rd.onloadend = () => r(rd.result.split(',')[1]); rd.readAsDataURL(blob); }});
                                        }}""")
                                        captcha_code = AUDIO_SOLVER.solve_audio(b64)
                                    except Exception as de: logging.warning(f"⚠️ Fetch lỗi: {de}")
                                else:
                                    logging.warning("⚠️ Không thấy nguồn Audio Bridge!")
                            
                            if not switched_to_audio_br or not captcha_code:
                                logging.info("--- THỬ GIẢI OCR ẢNH BRIDGE ---")
                                # Tìm ảnh CAPTCHA bằng nhiều chiến lược
                                captcha_el = None
                            for sel in [
                                'img[src*="captcha"]', 'img[alt*="captcha"]', 'img[alt*="CAPTCHA"]',
                                'img[src*="security"]', 'img[src*="checkpoint"]',
                                '#captcha_image', '.captcha_image',
                                'img[src*="scont"]', 'img[src*="pixel"]'
                            ]:
                                loc = page.locator(sel).first
                                if await loc.count() > 0:
                                    captcha_el = loc
                                    logging.info(f"🎯 Tìm thấy ảnh CAPTCHA bằng selector: {sel}")
                                    break
                            
                            # Chiến lược 2: Tìm bằng kích thước ảnh
                            if not captcha_el:
                                logging.info("🔍 Tìm CAPTCHA bằng kích thước ảnh...")
                                captcha_idx = await page.evaluate("""() => {
                                    const imgs = document.querySelectorAll('img');
                                    for (let i = 0; i < imgs.length; i++) {
                                        const w = imgs[i].naturalWidth || imgs[i].width;
                                        const h = imgs[i].naturalHeight || imgs[i].height;
                                        if (w >= 150 && w <= 600 && h >= 30 && h <= 200) {
                                            return i;
                                        }
                                    }
                                    return -1;
                                }""")
                                if captcha_idx >= 0:
                                    captcha_el = page.locator(f'img').nth(captcha_idx)
                                    logging.info(f"🎯 Tìm thấy ảnh CAPTCHA bằng kích thước (index: {captcha_idx})")
                            
                            if captcha_el and await asyncio.wait_for(captcha_el.count(), timeout=3.0) > 0:
                                logging.info("📸 1. Đang lấy kích thước ảnh Bridge (bounding_box)...")
                                try:
                                    box = await asyncio.wait_for(captcha_el.bounding_box(), timeout=3.0)
                                    if box:
                                        logging.info("📸 2. Đang di chuột tới ảnh Bridge (mouse.move)...")
                                        await asyncio.wait_for(page.mouse.move(box['x'] + box['width']/2, box['y'] + box['height']/2, steps=5), timeout=2.0)
                                        await asyncio.sleep(0.5)
                                except Exception as e_box:
                                    logging.warning(f"⚠️ Bỏ qua bounding_box/mouse.move Bridge do lỗi hoặc timeout: {e_box}")
                                
                                try:
                                    logging.info("📸 3. Đang tiến hành chụp ảnh CAPTCHA Bridge (timeout 8s)...")
                                    img_bytes = await asyncio.wait_for(captcha_el.screenshot(timeout=5000), timeout=8.0)
                                    logging.info(f"📸 4. Chụp ảnh CAPTCHA Bridge thành công ({len(img_bytes)} bytes). Đang giải OCR...")
                                    
                                    if OCR_SOLVER:
                                        captcha_code = OCR_SOLVER.solve_captcha(img_bytes)
                                        logging.info(f"🤖 [OCR ĐA TẦNG] Auto-solve lần #{attempt}: '{captcha_code}'")
                                except Exception as capture_err:
                                    logging.error(f"❌ Lỗi khi chụp ảnh CAPTCHA (Bridge) hoặc OCR: {capture_err}")
                            else:
                                logging.warning("⚠️ Không tìm thấy ảnh CAPTCHA trên trang Bridge!")
                            
                            # 3. Nếu OCR thất bại -> Nhập tay (chỉ ở lần cuối)
                            if not captcha_code:
                                if attempt < 3:
                                    logging.warning("OCR không giải được. Thử tải mã mới...")
                                    # Click "Try another text" nếu có
                                    try:
                                        reload = page.get_by_text("mã mới", exact=False).or_(page.get_by_text("another text", exact=False))
                                        if await reload.count() > 0:
                                            await reload.click()
                                            await asyncio.sleep(2)
                                    except: pass
                                    continue
                                else:
                                    print("\n" + "?"*60)
                                    captcha_code = await asyncio.to_thread(input, "👉 OCR thất bại 3 lần. NHẬP MÃ CAPTCHA: ")
                                    print("?"*60 + "\n")
                            
                            if captcha_code:
                                # 4. Điền mã vào ô input
                                captcha_input = page.locator('input[name="captcha_response"], input[type="text"]').first
                                await captcha_input.click()
                                await page.keyboard.press("Control+A")
                                await page.keyboard.press("Backspace")
                                await page.keyboard.type(captcha_code, delay=150)
                                await asyncio.sleep(0.5)
                                
                                old_captcha_url = page.url
                                
                                logging.info("--- Bắt đầu dò tìm nút Gửi / Tiếp tục (Bridge CAPTCHA) bằng Tab ---")
                                submit_clicked = False
                                for t_step in range(1, 15):
                                    await page.keyboard.press("Tab")
                                    await asyncio.sleep(0.5)
                                    el = page.locator(":focus")
                                    if await el.count() > 0:
                                        tag_name = await el.evaluate("el => el.tagName")
                                        text = (await el.text_content() or "").strip()
                                        aria = (await el.get_attribute("aria-label") or "").strip()
                                        role = (await el.get_attribute("role") or "").strip()
                                        
                                        combined_text = f"{text} {aria}".lower()
                                        logging.info(f"🔎 [TAB_DEBUG BRIDGE] Step_{t_step} | Tag: {tag_name} | Role: {role} | Text: {text} | Aria: {aria}")
                                        
                                        if role == "button" or tag_name == "BUTTON":
                                            if any(k in combined_text for k in ["tiếp tục", "gửi", "bắt đầu", "continue", "submit"]):
                                                logging.info("🎯 Tìm thấy nút Submit Bridge Captcha! Bấm Enter...")
                                                await page.keyboard.press("Enter")
                                                submit_clicked = True
                                                await asyncio.sleep(1)
                                                break
                                
                                if not submit_clicked:
                                    logging.warning("⚠️ Không tìm thấy nút Submit, bấm Enter dự phòng...")
                                    await page.keyboard.press("Enter")

                                logging.info(f"✅ Đã gửi CAPTCHA (Bridge): {captcha_code}. Đợi phản hồi...")
                                await asyncio.sleep(5)
                                
                                # 5. Check kết quả: URL đổi = thành công, URL giữ nguyên = sai mã
                                if page.url != old_captcha_url:
                                    logging.info("🎉 [CAPTCHA] Vượt qua CAPTCHA thành công!")
                                    break
                                else:
                                    check_text = await page.evaluate("document.body ? document.body.innerText.toLowerCase() : ''")
                                    if any(k in check_text for k in ["văn bản từ hình ảnh", "text in the box", "nghe mã"]):
                                        logging.warning(f"❌ CAPTCHA sai (lần #{attempt}). Thử lại...")
                                        continue
                                    else:
                                        logging.info("🎉 [CAPTCHA] Có vẻ đã vượt qua!")
                                        break
                continue
            
            # Dự phòng Submit (Chỉ khi text có nghĩa và không phải ngôn ngữ)
            if otp_filled and role == "button" and i > 5 and len(text) > 1 and len(text) < 15 and not is_lang_btn:
                logging.info(f"🎯 Có vẻ là nút hành động bổ trợ ({text}). Nhấn Enter...")
                await page.keyboard.press("Enter")
                await asyncio.sleep(5)
                continue

        logging.info("--- Đã hoàn tất luồng kiểm tra hậu OTP ---")

        await asyncio.sleep(5)

        await page.screenshot(path="debug_final_result.png")
        
        # Kiểm tra URL cuối cùng
        current_url = page.url
        logging.info(f"[FB_REG] URL hiện tại: {current_url}")
        
        if "facebook.com" in current_url:
            # Các trang không được tính là thành công
            bad_keywords = ["r.php", "login", "confirmemail", "checkpoint", "disabled", "checkpoint"]
            if not any(k in current_url.lower() for k in bad_keywords):
                logging.info("[FB_REG] 🏆 ĐĂNG KÝ FACEBOOK THÀNH CÔNG!")
                return True, {
                    "email": email,
                    "password": password,
                    "first_name": first_name,
                    "last_name": last_name,
                    "url": current_url
                }
        
        logging.warning(f"[FB_REG] ❌ Kết quả KHÔNG thành công. URL: {current_url}")
        return False, "REG_FAILED"

    except Exception as e:
        logging.error(f"Lỗi không xác định trong luồng FB FB: {e}")
        try:
            await page.screenshot(path="debug_final_exception.png")
        except: pass
        return False, "EXCEPTION"

async def main():
    config_file = "config_dcom.json" if os.path.exists("config_dcom.json") else "config.json"
    
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        logging.error(f"Không thể đọc file cấu hình {config_file}, dùng config rỗng: {e}")
        cfg = {}

    dcom = DcomManager(
        gateway=cfg.get("dcom_gateway", "192.168.8.1"),
        modem_type=cfg.get("dcom_type", "huawei"),
        username=cfg.get("dcom_username", "admin"),
        password=cfg.get("dcom_password", "admin"),
        interface_name=cfg.get("interface_name", "Ethernet 5")
    )
    
    wait_seconds = cfg.get("dcom_wait_seconds", 15)

    cycle_count = 0
    while True:
        cycle_count += 1
        logging.info(f"--- 🔄 KHỞI ĐỘNG CHU KỲ FB ĐĂNG KÝ MỚI (#{cycle_count}) ---")
        
        # 1. ĐỔI IP QUA DCOM (Nếu cấu hình yêu cầu)
        use_dcom = cfg.get("use_dcom", True)
        current_ip = "Unknown"
        
        if use_dcom:
            logging.info(f"--- [CHUYỂN IP] Đang thực hiện đổi IP cho Chu kỳ #{cycle_count}... ---")
            success_ip = await asyncio.to_thread(dcom.reset_connection, wait_seconds=wait_seconds)
            
            if not success_ip:
                logging.warning("Tín hiệu DCOM có vẻ không ổn định hoặc Reset thất bại. Tiếp tục thử...")
            
            current_ip = await asyncio.to_thread(dcom.get_current_ip)
            logging.info(f"🚀 IP Hiện Tại: {current_ip}")
            
            logging.info("Đợi mạng ổn định hoàn toàn (10s)...")
            await asyncio.sleep(10)
        else:
            logging.info("--- [CHUYỂN IP] Bỏ qua đổi IP (Cấu hình use_dcom=false) ---")
            try:
                current_ip = await asyncio.to_thread(dcom.get_current_ip)
            except:
                pass
            logging.info(f"🚀 IP Hiện Tại: {current_ip}")

        browser = None
        error_code = -1
        try:
            # DÙNG GUERRILLA_MAIL
            mail = GuerrillaMail()
            logging.info("--- [SETUP] ĐANG LẤY EMAIL TỪ GUERRILLA (Vui lòng chờ)... ---")
            email = mail.get_email_address()
            if not email:
                logging.error("Không lấy được email. Chờ 30s rồi thử lại chu kỳ mới...")
                await asyncio.sleep(30)
                continue

            # KHỞI TẠO BROWSER với DCOM SOCKS5 PROXY bắt buộc
            proxy_config = None
            if use_dcom:
                interface_name = cfg.get("interface_name", "Ethernet 2")
                logging.info(f"[DCOM_PROXY] Khởi động SOCKS5 proxy (Binding to {interface_name})...")
                proxy_config = get_or_start_proxy(interface_name)
                if proxy_config:
                    logging.info(f"[DCOM_PROXY] ✅ Proxy sẵn sàng: {proxy_config['server']}")
                else:
                    logging.warning("[DCOM_PROXY] ⚠️ Không khởi động được proxy! Chạy không proxy.")

            browser = TikTokBrowser(proxy_dict=proxy_config, headless=cfg.get("headless_mode", False))
            await browser.launch()

            stop_heartbeat = asyncio.Event()
            heartbeat_task = asyncio.create_task(browser_heartbeat(browser.page, stop_heartbeat))
            
            # WARM-UP & MONITOR
            await warm_up_facebook(browser.page)
            await asyncio.sleep(2)

            # CHẠY LUỒNG ĐĂNG KÝ CHÍNH
            success, reg_data_or_error = await run_facebook_registration_flow(browser, mail, email, stop_heartbeat, heartbeat_task)
            
            if success:
                reg_data = reg_data_or_error
                logging.info(f"🏆 [DCOM SUCCESS] Hoàn tất đăng ký thành công cho: {reg_data['email']}")
                
                # LƯU VÀO CSV
                csv_file = "facebook_accounts.csv"
                file_exists = os.path.isfile(csv_file)
                
                try:
                    with open(csv_file, mode="a", newline="", encoding="utf-8") as f:
                        fieldnames = ["email", "password", "first_name", "last_name", "ip", "time", "url"]
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        
                        if not file_exists:
                            writer.writeheader()
                        
                        writer.writerow({
                            "email": reg_data["email"],
                            "password": reg_data["password"],
                            "first_name": reg_data["first_name"],
                            "last_name": reg_data["last_name"],
                            "ip": current_ip,
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "url": reg_data.get("url", "")
                        })
                    logging.info(f"✅ Đã lưu thông tin tài khoản vào {csv_file}")
                except Exception as e:
                    logging.error(f"❌ Không thể lưu vào CSV: {e}")
            else:
                error_code = reg_data_or_error
                if error_code == "CHECKPOINT":
                    logging.warning("Phát hiện bị Checkpoint ngay lập tức.")
                else:
                    logging.error(f"Đăng ký thất bại. Error Code: {error_code}")

        except Exception as e:
            logging.error(f"Lỗi hệ thống trong luồng chính: {e}")
        finally:
            if browser:
                try: 
                    stop_heartbeat.set()
                    if 'heartbeat_task' in locals():
                        await asyncio.wait_for(asyncio.gather(heartbeat_task, return_exceptions=True), timeout=5.0)
                except: pass
                
                await browser.close()
                logging.info("Browser closed.")
                if hasattr(browser, 'profile_dir') and os.path.exists(browser.profile_dir):
                    import shutil
                    try: shutil.rmtree(browser.profile_dir)
                    except: pass
            
            logging.info(f"--- 💤 Chu kỳ #{cycle_count} kết thúc. Chuyển sang lượt mới... ---")
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
