import asyncio
import logging
import time
import random
import string
import csv
import re
from datetime import datetime
import json
import re
import os
import ctypes
try:
    import win32gui
    import win32con
    import win32process
    import win32api
except ImportError:
    win32gui = None
    win32con = None
    win32process = None
    win32api = None
try:
    import psutil
except ImportError:
    psutil = None
from browser_setup import TikTokBrowser
from guerrilla_mail import GuerrillaMail
from dcom_manager import DcomManager # Thêm DcomManager

import sys
os.makedirs("logs", exist_ok=True)
log_filename = f"logs/api_registration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

def xor_encode(text: str) -> str:
    """Thuật toán mã hóa mix_mode=1 của TikTok (XOR 0x05)"""
    return ''.join([hex(ord(c) ^ 5)[2:].zfill(2) for c in text])

def xor_decode(encoded_hex: str) -> str:
    """Giải mã mảng hex từ TikTok"""
    return ''.join([chr(int(encoded_hex[i:i+2], 16) ^ 5) for i in range(0, len(encoded_hex), 2)])

def generate_random_password(length=12):
    characters = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        password = ''.join(random.choice(characters) for i in range(length))
        if (any(c.islower() for c in password)
                and any(c.isupper() for c in password)
                and any(c.isdigit() for c in password)
                and any(c in "!@#$%^&*" for c in password)):
            return password

# ---------- HUMAN-LIKE INTERACTION HELPERS ----------

async def human_click(page, locator):
    """Mô phỏng click chuột thật: Tối ưu tọa độ để không bị văng khỏi màn hình"""
    try:
        # 1. Đảm bảo phần tử tồn tại và visible
        await locator.wait_for(state="attached", timeout=5000)
        
        # 2. Cuộn phần tử vào giữa màn hình (nếu có thể) để lấy tọa độ chuẩn nhất
        await locator.evaluate("node => node.scrollIntoView({block: 'center', inline: 'center'})")
        await asyncio.sleep(0.2)
        
        box = await locator.bounding_box()
        if not box:
            # Fallback nếu bounding_box vẫn trả về None dù đã cuộn
            await locator.scroll_into_view_if_needed()
            box = await locator.bounding_box()
        
        if box:
            viewport = page.viewport_size or {'width': 1280, 'height': 720}
            
            # Tính toán tọa độ trung tâm + rải ngẫu nhiên (tránh click mép)
            target_x = box['x'] + box['width'] / 2 + random.uniform(-2, 2)
            target_y = box['y'] + box['height'] / 2 + random.uniform(-2, 2)
            
            # GIỚI HẠN TỌA ĐỘ: Đảm bảo không click ra ngoài cửa sổ trình duyệt
            target_x = max(10, min(viewport['width'] - 10, target_x))
            target_y = max(10, min(viewport['height'] - 10, target_y))
            
            # Di chuyển chuột đến (với tốc độ CỰC CHẬM)
            await page.mouse.move(target_x, target_y, steps=random.randint(10, 20))
            await asyncio.sleep(random.uniform(0.1, 0.3))
            
            # Rung nhẹ (jitter)
            await page.mouse.move(target_x + 2, target_y - 1, steps=5)
            await page.mouse.move(target_x, target_y, steps=5)
            
            # Click
            logging.info(f"🖱️ [HUMAN] Clicking at ({target_x:.1f}, {target_y:.1f})...")
            await page.mouse.down()
            await asyncio.sleep(random.uniform(0.1, 0.25))
            await page.mouse.up()
            return True
    except Exception as e:
        logging.warning(f"human_click failed for locator: {locator}. Error: {e}")
        # Thử click bằng evaluate như cứu cánh cuối cùng
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
    
    # Gõ từng ký tự với delay ngẫu nhiên
    logging.info(f"⌨️ [HUMAN] Typing text (length: {len(text)})...")
    for char in text:
        await page.keyboard.type(char)
        await asyncio.sleep(random.uniform(0.05, 0.2)) # Gõ nhanh hơn
        if random.random() < 0.05: # 5% dừng lại suy nghĩ
            await asyncio.sleep(random.uniform(0.5, 1.2))
    logging.info("⌨️ [HUMAN] Typing finished.")

async def warm_up(page):
    """Lướt TikTok Explore để tạo dấu vân tay thật."""
    try:
        logging.info("--- [BEHAVIOR] Đang lướt xem video (Warm-up)... ---")
        
        # Thêm listener để kiểm tra lỗi 429/403
        response_status = {"code": 200}
        def check_response(response):
            if response.status in [403, 429]:
                response_status["code"] = response.status
                logging.error(f"🚨 [DETECTION] Warm-up detected HTTP {response.status} (Blocked/Throttled). Aborting warm-up.")
        
        page.on("response", check_response)

        for i in range(random.randint(2, 4)):
            if response_status["code"] in [403, 429]:
                break # Abort warm-up early
            
            logging.info(f"--- [WARM-UP] Vòng lặp {i+1}... ---")
            # Cuộn xuống ngẫu nhiên
            scroll_amount = random.randint(300, 700)
            logging.info(f"Cuộn xuống {scroll_amount}px...")
            try:
                # Thêm timeout cho mouse wheel để tránh treo
                await asyncio.wait_for(page.mouse.wheel(0, scroll_amount), timeout=5.0)
            except asyncio.TimeoutError:
                logging.warning("Warm-up: Mouse wheel timeout.")
            
            await asyncio.sleep(random.uniform(1.0, 2.5))
            
            # Thỉnh thoảng rê chuột
            if random.random() > 0.6:
                 try:
                     await asyncio.wait_for(
                         page.mouse.move(random.randint(100, 1080), random.randint(100, 720), steps=random.randint(10, 20)),
                         timeout=3.0
                     )
                 except: pass
                 
        logging.info("--- [BEHAVIOR] Warm-up hoàn tất! ---")
        page.remove_listener("response", check_response) # Remove listener after warm-up
        if response_status["code"] in [403, 429]:
            return False # Indicate failure due to blocking
        return True # Indicate success
    except Exception as e:
        logging.error(f"Lỗi trong warm_up: {e}")
        return False

async def browser_heartbeat(page, stop_event):
    """Giữ trình duyệt 'Active' bằng mọi giá (EXTREME Mode)"""
    logging.info("💓 [WATCHDOG] Kích hoạt EXTREME Anti-Throttling (1s pulse)...")
    
    # 1. Ép Priority lên mức Vừa phải (Không gây giật máy)
    if psutil:
        try:
            p = psutil.Process(os.getpid())
            p.nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS)
            for child in p.children(recursive=True):
                try: child.nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS)
                except: pass
            logging.info("🚀 [SYSTEM] Silent Priority: ABOVE_NORMAL.")
        except: pass

    # 2. Ngăn Windows Sleep/Throttling process
    try:
        # ES_SYSTEM_REQUIRED | ES_CONTINUOUS | ES_AWAYMODE_REQUIRED
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001 | 0x00000040)
    except: pass

    # 3. Interaction siêu nhẹ bên trong trang (Giảm spam Control key để tránh mess-up Typing)
    try:
        await page.evaluate("""
            setInterval(() => {
                // Chỉ gửi ping nhẹ để giữ loop, không dispatch key liên tục 100ms
                window.dispatchEvent(new CustomEvent('heartbeat-ping'));
            }, 1000);
        """)
    except: pass

    try:
        while not stop_event.is_set():
            start_time = time.time()
            
            # 1. Định kỳ Ép Priority cho toàn bộ cây process (Để bắt các process con mới sinh)
            if psutil:
                try:
                    p = psutil.Process(os.getpid())
                    # p.nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS) # Python process boost
                    for child in p.children(recursive=True):
                        try:
                            # Nếu process con là Camoufox/Firefox, ưu tiên nó
                            child.nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS)
                        except: pass
                except: pass

            if win32gui:
                try:
                    def callback(hwnd, extra):
                        title = win32gui.GetWindowText(hwnd).lower()
                        if "camoufox" in title or "tiktok" in title:
                            # Chỉ gửi tin nhắn rỗng (Ping) để giữ App loop không bị đóng băng
                            # Tuyệt đối không dùng WM_ACTIVATE để tránh cướp Focus của User
                            win32gui.PostMessage(hwnd, win32con.WM_NULL, 0, 0)
                    win32gui.EnumWindows(callback, None)
                except: pass

            try:
                # Interaction siêu nhẹ bên trong trang
                await page.evaluate("1") 
                
                # Thi thoảng rung chuột cực nhẹ (1-2 pixel)
                if random.random() < 0.3:
                    await page.mouse.move(random.randint(0, 100), random.randint(0, 100), steps=2)
            except: pass
            
            end_time = time.time()
            proc_time = end_time - start_time
            
            if proc_time > 1.0:
                logging.warning(f"⚠️ [WATCHDOG] Slow Pulse ({proc_time:.2f}s).")
            elif random.random() < 0.05: # Giảm log nữa cho sạch
                logging.info(f"💓 [WATCHDOG] Silent Heartbeat OK.")
            
            # Tần suất 3 giây (Nhanh hơn một chút nhưng nhẹ hơn)
            await asyncio.sleep(3)
    except Exception as e:
        logging.debug(f"Heartbeat stopped: {e}")

async def extract_did_and_tokens(page):
    """Lấy did từ cookie và các token bảo mật khác"""
    cookies = await page.context.cookies()
    did = ""
    for c in cookies:
        if c['name'] == 'ttwid' or c['name'] == 'tt_webid':
            # did thường là phần ID sau dấu | trong ttwid: 1%7C...%7Cdid
            if "%7C" in c['value']:
                parts = c['value'].split("%7C")
                if len(parts) >= 3:
                    did = parts[-1]
            if not did:
                did = c['value']
            break
    
    if not did:
        # Fallback: Thực thi JS để lấy từ window variable nếu có
        did = await page.evaluate("() => window._commonConfig?.did || ''")
    
    return did

async def run_api_cracking_flow(browser, mail, email, stop_heartbeat, heartbeat_task):
    page = browser.page
    password = generate_random_password()
    pending_tasks = []
    
    logging.info(f"[API_CRACK] --- 🚀 KHỞI ĐỘNG LUỒNG ĐỤC API TIKTOK ---")
    logging.info(f"[API_CRACK] Email mục tiêu: {email}")
    
    # Đợi 1 chút để TikTok Set-Cookie ttwid (quan trọng cho did)
    logging.info("[API_CRACK] Chờ load cookie ttwid/did...")
    await asyncio.sleep(2)
    did = await extract_did_and_tokens(page)
    logging.info(f"[API_CRACK] Extracted Device ID (did): {did}")
    
    encoded_email = xor_encode(email)
    encoded_password = xor_encode(password)

    try:
        # ---------- BƯỚC 1: SEND CODE (Gửi qua UI) ----------
        logging.info("[API_CRACK] 1️⃣ Điền form và Click Send Code qua UI...")
    
        def check_redirect():
            if page.url.strip("/") == "https://www.tiktok.com":
                logging.error("🚨 [DETECTION] TikTok tự động văng về trang chủ! Blocked flow.")
                return True
            return False
        
        # 1. Các thẻ chọn Ngày sinh
        try:
            logging.info("Chọn ngày sinh...")
            
            # Hybrid selection: Thử select_option trước, nếu không được thì dùng human_click trên combobox
            month = random.randint(1, 12)
            day = random.randint(1, 28)
            year = random.randint(1990, 2005)

            month_combos = page.locator('div[role="combobox"]')
            if await month_combos.count() >= 3:
                # Cách 1: Click trên custom combobox
                for idx, val in enumerate([month, day, year]):
                    await human_click(page, month_combos.nth(idx))
                    await asyncio.sleep(random.uniform(0.3, 0.6))
                    # Tìm option có chứa giá trị hoặc text tương ứng
                    opt = page.locator('div[role="option"]').filter(has_text=re.compile(rf"^{val}$" if idx > 0 else "")).first
                    if await opt.count() == 0:
                        opt = page.locator('div[role="option"]').nth(val if idx < 2 else 20)
                    await human_click(page, opt)
                    await asyncio.sleep(random.uniform(0.5, 1.0))
            else:
                # Cách 2: Try standard select if available
                try:
                    await page.select_option('select[aria-label="Month"]', str(month))
                    await asyncio.sleep(0.5)
                    await page.select_option('select[aria-label="Day"]', str(day))
                    await asyncio.sleep(0.5)
                    await page.select_option('select[aria-label="Year"]', str(year))
                except:
                    logging.warning("Failed to select DOB via standard select.")
            
            await asyncio.sleep(random.uniform(0.5, 1.5)) 
        except Exception as e:
            logging.warning(f"Lỗi khi tick ngày sinh: {e}")

        if check_redirect(): return False, 7

        try:
            # 2. Điền Email & Mật khẩu
            email_inp = page.locator('input[type="email"], input[name="email"]')
            await email_inp.wait_for(state="visible", timeout=5000)
            await human_type(page, email_inp, email)
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            if check_redirect(): return False, 7

            await page.keyboard.press("Escape") 
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            # Click ra ngoài ngẫu nhiên để xóa popup
            await page.mouse.click(random.randint(100, 300), random.randint(100, 300)) 

            if check_redirect(): return False, 7

            pass_inp = page.locator('input[type="password"]')
            if await pass_inp.count() > 0:
                await pass_inp.first.wait_for(state="visible", timeout=5000)
                await human_type(page, pass_inp.first, password)
                await asyncio.sleep(random.uniform(0.5, 1.0))
                
            # 3. Click nút Gửi mã (RETRY tối đa 3 lần - xử lý trường hợp UI bị lệch)
            send_code_res = None
            max_send_attempts = 3

            for send_attempt in range(max_send_attempts):
                logging.info(f"[API_CRACK] Lần thử gửi Code #{send_attempt + 1}/{max_send_attempts}...")
                
                # Cuộn về đầu trang để đảm bảo nút luôn hiển thị đúng vị trí
                await page.evaluate("window.scrollTo(0, 0)")
                await asyncio.sleep(1.0)

                send_btn = page.locator('button[data-e2e="send-code-button"]')
                
                try:
                    await send_btn.wait_for(state="visible", timeout=5000)
                except Exception:
                    logging.warning("Nút Gửi mã không hiển thị.")
                    break

                is_enabled = await send_btn.is_enabled()
                if not is_enabled:
                    # Kiểm tra xem có phải do nút đã chuyển sang trạng thái "Gửi lại mã" không
                    has_resend_text = await send_btn.evaluate("el => el.textContent.toLowerCase().includes('gửi lại') || el.textContent.toLowerCase().includes('resend') || el.textContent.match(/\\d+s/)")
                    if has_resend_text:
                        logging.info("[API_CRACK] 🎉 Nút đang ở trạng thái Resend (đếm ngược), coi như mã đã gửi thành công trước đó!")
                        send_code_res = {"message": "success"}  # Đánh lừa logic để break vòng lặp
                        break
                        
                    logging.warning("Nút Gửi mã đang bị disabled. Chờ thêm...")
                    await asyncio.sleep(2)
                    is_enabled = await send_btn.is_enabled()
                    
                    if not is_enabled:
                        has_resend_text = await send_btn.evaluate("el => el.textContent.toLowerCase().includes('gửi lại') || el.textContent.toLowerCase().includes('resend') || el.textContent.match(/\\d+s/)")
                        if has_resend_text:
                            logging.info("[API_CRACK] 🎉 Nút đang ở trạng thái Resend, coi như mã đã gửi thành công!")
                            send_code_res = {"message": "success"}
                            break
                            
                        logging.warning("Vẫn disabled sau khi đợi. Chụp ảnh debug...")
                        await page.screenshot(path=f"debug_disabled_btn_{send_attempt}.png")
                        return False, -2

                # Chuẩn bị task bắt network response trước khi click
                async def wait_for_send_code():
                    try:
                        async with page.expect_response(
                            lambda r: "/passport/web/email/send_code/" in r.url,
                            timeout=8000
                        ) as response_info:
                            response = await response_info.value
                            return await response.json()
                    except Exception as e:
                        return {"error_code": -1, "description": str(e), "message": "timeout"}

                send_btn_task = asyncio.create_task(wait_for_send_code())
                await asyncio.sleep(0.5)

                # Click nút
                await human_click(page, send_btn)
                logging.info("Đã click nút Gửi mã (Human Style)!")

                # Đợi kết quả mạng
                send_code_res = await send_btn_task

                logging.info(f"[API_CRACK] Send Code Response #{send_attempt + 1}: {json.dumps(send_code_res, ensure_ascii=False)}")

                if send_code_res.get("message") == "success":
                    logging.info("[API_CRACK] 🎉 Đã gửi code thành công!")
                    break
                elif send_code_res.get("message") == "timeout":
                    # Network response không đến = click bị lệch, thử lại
                    logging.warning(f"[SEND_CODE] Không nhận được response mạng (click lệch?). Thử lại sau 3s...")
                    await asyncio.sleep(3)
                else:
                    # Server trả về lỗi rõ ràng (Error 7, captcha, ...)
                    err_data = send_code_res.get("data", {})
                    err_code = err_data.get("error_code", -1)
                    err_desc = err_data.get("description", str(send_code_res))
                    logging.error(f"[SEND_CODE] Server trả lỗi: code={err_code}, msg={err_desc}")
                    if err_code == 7:
                        return False, 7
                    # Lỗi khác, thử lại
                    await asyncio.sleep(3)
            
            # Done send_code loop
            pass

            # Kiểm tra sau toàn bộ retry
            if not send_code_res or send_code_res.get("message") != "success":
                # Kiểm tra lỗi UI
                err_locator = page.locator('div[role="alert"], span:has-text("thường xuyên"), p:has-text("thường xuyên")')
                if await err_locator.count() > 0 and await err_locator.first.is_visible():
                    logging.error(f"[API_CRACK] Lỗi UI sau retry: {await err_locator.first.inner_text()}")
                    return False, 7
                logging.error("[API_CRACK] Gửi code thất bại sau tất cả các lần thử!")
                return False, -1
                
        except Exception as e:
            logging.error(f"UI Lỗi điền Form: {e}")
            return False, -1
        
        # ---------- BƯỚC 2: NHẬN CODE TỪ GUERRILLA MAIL ----------
        logging.info("[API_CRACK] 2️⃣ Đang chờ mã xác minh từ email (timeout 2 phút)...")
        # Bước 5: Kiểm tra Mail lấy OTP
        logging.info("[API_CRACK] Đang đợi Guerrilla Mail nhận mã OTP...")
        # GuerrillaMail check_inbox is sync, run in thread to avoid blocking heartbeat
        code = await asyncio.to_thread(mail.check_inbox, timeout=120)
            
        if not code:
            logging.error("[API_CRACK] Không lấy được mã code từ email.")
            return False, "TIMEOUT_MAIL"
             
        logging.info(f"[API_CRACK] 🎉 Mã xác minh nhận được: {code}")
        # encoded_code = xor_encode(code) # UI không cần xor_encode, UI điền code ròng
        
        # ---------- BƯỚC 3: SUBMIT REGISTER TRÊN UI ----------
        logging.info("[API_CRACK] 3️⃣ Gửi Request Đăng ký qua UI...")
        
        try:
            # 3. Nhập mã code gồm 6 chữ số
            code_inp = page.locator('input[placeholder*="mã"], input[placeholder*="digit"], [placeholder*="6-digit"]').first
            
            if await code_inp.count() == 0:
                code_inp = page.locator('input[type="text"]').last
                
            await human_type(page, code_inp, code)
            logging.info(f"Đã điền mã xác nhận: {code}")
            
            # Giả lập thời gian suy nghĩ sau khi điền code (Dài hơn và di chuyển chuột để lấy Trust)
            await asyncio.sleep(random.uniform(2.5, 4.5))
            try:
                await page.mouse.move(random.randint(100, 500), random.randint(100, 500), steps=15)
            except: pass
            
            # Chuẩn bị Promise để bắt kết quả mạng
            async def wait_for_register():
                try:
                    # Bắt cả register_verify_login (thường là cái này)
                    async with page.expect_response(lambda r: "/passport/web/email/register_verify_login/" in r.url or "/passport/web/email/register" in r.url, timeout=45000) as response_info:
                        response = await response_info.value
                        return await response.json()
                except Exception as e:
                    return {"error_code": -1, "description": str(e), "message": "error"}

            reg_btn_task = asyncio.create_task(wait_for_register())
            
            # Click nút Tiếp (Next)
            next_btn = page.locator('button').filter(has_text=re.compile(r"Tiếp|Next", re.IGNORECASE))
            if await next_btn.count() > 0:
                # Hover trước khi click
                await next_btn.first.hover()
                await asyncio.sleep(0.5)
                await human_click(page, next_btn.first)
                logging.info("Đã click nút Tiếp (Register - Human Style)!")
            else:
                logging.warning("Không tìm thấy nút Tiếp.")
                reg_btn_task.cancel()
                return False, -2
                
            # Kiểm tra lỗi UI sau khi click Tiếp
            await asyncio.sleep(2)
            err_reg_locator = page.locator('div[role="alert"], span:has-text("thường xuyên"), p:has-text("thường xuyên"), p:has-text("tần số")')
            if await err_reg_locator.count() > 0 and await err_reg_locator.first.is_visible():
                 err_txt = await err_reg_locator.first.inner_text()
                 logging.error(f"[API_CRACK] Phát hiện lỗi UI (Register): {err_txt}")
                 await page.screenshot(path="debug_register_error_ui.png")
                 return False, 7 # IP block
                
            reg_res = await reg_btn_task
            logging.info(f"[API_CRACK] Register Response: {json.dumps(reg_res, ensure_ascii=False)}")
            
            # Trích xuất thông tin tài khoản để trả về
            reg_res_data = reg_res.get("data", {})
            user_id_final = str(reg_res_data.get("user_id_str") or reg_res_data.get("user_id") or "N/A")
            username_final = str(reg_res_data.get("username") or "N/A")
            
            # Chụp ảnh kết quả
            await page.screenshot(path="debug_register_result.png")
            
            if reg_res.get("message") == "success":
                logging.info("[API_CRACK] 🏆 ĐĂNG KÝ THÀNH CÔNG (Giai đoạn 1)!")
                
                # Đợi trang chuyển hướng sang create-username hoặc foryou
                try:
                    await page.wait_for_url(re.compile(r"create-username|foryou|discover"), timeout=15000)
                    logging.info(f"[API_CRACK] Đã chuyển hướng sang: {page.url}")
                except:
                    logging.warning("[API_CRACK] Timeout chờ chuyển hướng sau register.")

                # Nếu bị bắt tạo Username
                if "create-username" in page.url:
                    logging.info("[API_CRACK] 4️⃣ Xử lý chọn Nickname/Username...")
                    await asyncio.sleep(random.uniform(1.0, 2.5)) # Thời gian suy nghĩ chọn tên
                    
                    try:
                        # Thử tìm các gợi ý sẵn (Với timeout)
                        suggestions = page.locator('div[class*="SuggestionItem"]')
                        s_count = await asyncio.wait_for(suggestions.count(), timeout=5.0)
                        
                        if s_count > 0:
                            logging.info("Chọn username gợi ý...")
                            await human_click(page, suggestions.first)
                        else:
                            # Tự điền nếu không thấy gợi ý
                            name_inp = page.locator('input[placeholder*="TikTok ID"], input[name*="unique_id"]').first
                            if await name_inp.count() > 0:
                                random_name = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
                                await human_type(page, name_inp, random_name)
                        
                        await asyncio.sleep(random.uniform(0.5, 1.5))
                        
                        # Nút xác nhận cuối cùng (Đăng ký / Bỏ qua / Tiếp)
                        finish_btn = page.locator('button[data-e2e="signup-button"], button:has-text("Đăng ký"), button:has-text("Tiếp"), button:has-text("Skip")').first
                        if await finish_btn.count() > 0:
                            await human_click(page, finish_btn)
                            logging.info("Đã click nút hoàn tất Đăng ký!")
                        
                        await asyncio.sleep(5) # Đợi load sang Foryou
                    except Exception as e:
                        logging.warning(f"Lỗi khi xử lý Username (Có thể đã tự qua): {e}")
                
                return True, {
                    "email": email,
                    "password": password,
                    "username": username_final,
                    "user_id": user_id_final
                }
                
            # Kiểm tra nếu URL đã thay đổi sang trang chủ (đôi khi response bị miss nhưng vẫn log in được)
            if "foryou" in page.url or "discover" in page.url or "create-username" in page.url:
                logging.info(f"[API_CRACK] 🏆 ĐĂNG KÝ THÀNH CÔNG (Detected by URL: {page.url})!")
                return True, {
                    "email": email,
                    "password": password,
                    "username": "N/A",
                    "user_id": "N/A"
                }

            return False, reg_res.get("data", {}).get("error_code")
            
        except Exception as e:
            logging.error(f"UI Lỗi điền Code Xác Nhận: {e}")
            return False, -1

    except Exception as e:
        logging.error(f"Lỗi không xác định trong luồng API Crack: {e}")
        return False, -1
    finally:
        for t in pending_tasks:
            if not t.done():
                t.cancel()

async def main():
    import json
    import os
    
    # Ưu tiên load config_dcom.json nếu có
    config_file = "config_dcom.json" if os.path.exists("config_dcom.json") else "config.json"
    
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        logging.error(f"Không thể đọc file cấu hình {config_file}: {e}")
        return

    # Khởi tạo DcomManager
    dcom = DcomManager(
        gateway=cfg.get("dcom_gateway", "192.168.8.1"),
        modem_type=cfg.get("dcom_type", "huawei"),
        username=cfg.get("dcom_username", "admin"),
        password=cfg.get("dcom_password", "admin"),
        interface_name=cfg.get("interface_name", "Ethernet 5")
    )
    
    max_retries = cfg.get("max_retries", 5)
    wait_seconds = cfg.get("dcom_wait_seconds", 15)

    # Vòng lặp đăng ký vô hạn
    cycle_count = 0
    while True:
        cycle_count += 1
        logging.info(f"--- 🔄 KHỞI ĐỘNG CHU KỲ ĐĂNG KÝ MỚI (#{cycle_count}) ---")
        
        # 1. ĐỔI IP QUA DCOM (Bắt buộc để pass block TikTok)
        logging.info(f"--- [CHUYỂN IP] Đang thực hiện đổi IP cho Chu kỳ #{cycle_count}... ---")
        # DcomManager methods are sync, run in thread to keep asyncio heartbeat alive
        success_ip = await asyncio.to_thread(dcom.reset_connection, wait_seconds=wait_seconds)
        
        if not success_ip:
            logging.warning("Tín hiệu DCOM có vẻ không ổn định hoặc Reset thất bại. Tiếp tục thử...")
        
        # Lấy IP hiện tại để log
        current_ip = await asyncio.to_thread(dcom.get_current_ip)
        logging.info(f"🚀 IP Hiện Tại: {current_ip}")
        
        # Đợi mạng ổn định hoàn toàn sau khi reset (Rất quan trọng cho Trust)
        logging.info("Đợi mạng ổn định hoàn toàn (10s)...")
        await asyncio.sleep(10)

        browser = None
        error_code = -1
        try:

            # 2. KHỞI CHẠY TRÌNH DUYỆT (KHÔNG PROXY - Dùng thẳng mạng DCOM)
            mail = GuerrillaMail()
            logging.info("--- [SETUP] ĐANG LẤY EMAIL TỪ GUERRILLA (Vui lòng chờ)... ---")
            email = mail.get_email_address()
            if not email:
                logging.error("Không lấy được email. Chờ 30s rồi thử lại chu kỳ mới...")
                await asyncio.sleep(30)
                continue

            browser = TikTokBrowser(proxy_dict=None, headless=cfg.get("headless_mode", False))
            await browser.launch()

            # --- [WATCHDOG] START HEARTBEAT EARLY ---
            stop_heartbeat = asyncio.Event()
            heartbeat_task = asyncio.create_task(browser_heartbeat(browser.page, stop_heartbeat))
            heartbeat_task_ref = heartbeat_task

            # --- [USER INTERACTION DETECTOR] ---
            try:
                await browser.page.evaluate("""() => {
                    window.addEventListener('mousedown', () => console.log("[USER-INT] Phát hiện người dùng click chuột!"));
                    window.addEventListener('keydown', () => console.log("[USER-INT] Phát hiện người dùng gõ phím!"));
                }""")
            except:
                pass
            
            # 3. THỰC HIỆN WARM-UP (Quan trọng để tránh bị suspension ngay lập tức)
            logging.info(f"--- [NAV] TRUY CẬP TRANG CHỦ ĐỂ LẤY TRUST (IP: {current_ip}) ---")
            await warm_up(browser.page)

            # Kiểm tra xem có bị block ngay từ vòng gửi xe không
            if hasattr(browser, 'last_error_message') and browser.last_error_message:
                logging.error(f"🛑 Hủy chu kỳ do phát hiện Block sớm: {browser.last_error_message}")
                return False # Sẽ nhảy vào finally và reset IP

            # 4. TÌM VÀ CLICK NÚT ĐĂNG KÝ (Thay vì vào link trực tiếp)
            logging.info("Tìm nút Đăng ký từ trang chủ...")
            signup_btn = browser.page.locator('button:has-text("Đăng ký"), button:has-text("Sign up"), a:has-text("Sign up")').first
            if await signup_btn.count() > 0:
                await human_click(browser.page, signup_btn)
                await asyncio.sleep(random.uniform(2.0, 4.0))
            else:
                logging.warning("Không tìm thấy nút đăng ký trên homepage. Navigating trực tiếp...")
                try:
                    await browser.page.goto("https://www.tiktok.com/signup/phone-or-email/email", wait_until="load", timeout=30000)
                except: pass
            
            # Đôi khi mở popup, ta chọn "Sử dụng điện thoại hoặc email"
            email_option = browser.page.locator('div:has-text("Sử dụng số điện thoại hoặc email"), div:has-text("Use phone or email")').first
            if await email_option.count() > 0:
                await human_click(browser.page, email_option)
                await asyncio.sleep(2)

            success, reg_data_or_error = await run_api_cracking_flow(browser, mail, email, stop_heartbeat, heartbeat_task)
            
            if success:
                reg_data = reg_data_or_error
                logging.info(f"🏆 [DCOM SUCCESS] Hoàn tất đăng ký thành công cho: {reg_data['email']}")
                
                # LƯU VÀO CSV
                csv_file = "accounts.csv"
                file_exists = os.path.isfile(csv_file)
                
                try:
                    with open(csv_file, mode="a", newline="", encoding="utf-8") as f:
                        fieldnames = ["email", "password", "username", "user_id", "ip", "time"]
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        
                        if not file_exists:
                            writer.writeheader()
                        
                        writer.writerow({
                            "email": reg_data["email"],
                            "password": reg_data["password"],
                            "username": reg_data["username"],
                            "user_id": reg_data["user_id"],
                            "ip": current_ip,
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                    logging.info(f"✅ Đã lưu thông tin tài khoản vào {csv_file}")
                except Exception as e:
                    logging.error(f"❌ Không thể lưu vào CSV: {e}")
            else:
                error_code = reg_data_or_error
                if error_code == 7:
                    logging.warning("Phát hiện chặn IP (Error 7).")
                else:
                    logging.error(f"Đăng ký thất bại. Error Code: {error_code}")

        except Exception as e:
            logging.error(f"Lỗi hệ thống trong luồng chính: {e}")
        finally:
            if browser:
                try: 
                    stop_heartbeat.set()
                    # Đợi heartbeat_task hoàn tất dọn dẹp để tránh TargetClosedError
                    if 'heartbeat_task' in locals():
                        await asyncio.wait_for(asyncio.gather(heartbeat_task, return_exceptions=True), timeout=5.0)
                except: pass
                
                await browser.close()
                logging.info("Browser closed.")
                if hasattr(browser, 'profile_dir') and os.path.exists(browser.profile_dir):
                    import shutil
                    try: shutil.rmtree(browser.profile_dir)
                    except: pass
            
            # Nghỉ ngơi giữa các chu kỳ để tránh bị scan
            cooldown = 0
            logging.info(f"--- 💤 Chu kỳ #{cycle_count} kết thúc. Chuyển sang lượt mới ngay lập tức... ---")
            await asyncio.sleep(cooldown)

if __name__ == "__main__":
    asyncio.run(main())

