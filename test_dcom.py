import asyncio
import logging
import json
import os
from dcom_manager import DcomManager

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("TestDCOM")

async def test_reset_ip():
    config_path = "config.json"
    if not os.path.exists(config_path):
        logger.error(f"Không tìm thấy file {config_path}")
        return

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    gateway = config.get("dcom_gateway", "192.168.16.1")
    modem_type = config.get("dcom_type", "huawei")
    username = config.get("dcom_username", "admin")
    password = config.get("dcom_password", "admin")
    interface_name = config.get("interface_name", "Ethernet 2")
    wait_seconds = config.get("dcom_wait_seconds", 15)

    logger.info("--- [TEST] Khởi tạo DcomManager với bản mới ---")
    logger.info(f"Gateway: {gateway}, Interface: {interface_name}")
    
    dcom = DcomManager(
        gateway=gateway,
        modem_type=modem_type,
        username=username,
        password=password,
        interface_name=interface_name
    )

    # 1. Lấy IP hiện tại
    logger.info("1. Đang lấy IP hiện tại...")
    old_ip = await asyncio.to_thread(dcom.get_current_ip)
    logger.info(f"IP trước khi reset: {old_ip}")

    # 2. Thực hiện Reset (Đổi IP)
    # Bản mới này gọi reset_connection sẽ tự lo login và disconnect/connect
    logger.info(f"2. Thực hiện reset_connection (chờ {wait_seconds}s)...")
    success = await asyncio.to_thread(dcom.reset_connection, wait_seconds)

    if success:
        logger.info("✅ KẾT QUẢ: Reset IP THÀNH CÔNG!")
    else:
        logger.error("❌ KẾT QUẢ: Reset IP THẤT BẠI!")

    # 3. Kiểm tra IP sau khi reset
    new_ip = await asyncio.to_thread(dcom.get_current_ip)
    logger.info(f"IP sau khi reset: {new_ip}")
    
    if new_ip and new_ip != old_ip:
        logger.info("🎉 XÁC NHẬN: IP ĐÃ THAY ĐỔI!")
    else:
        logger.warning("⚠️ CẢNH BÁO: IP KHÔNG THAY ĐỔI.")

if __name__ == "__main__":
    asyncio.run(test_reset_ip())
