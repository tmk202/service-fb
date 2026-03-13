import asyncio
import base64
import os
import sys
import logging
from facebook_registration import AudioCaptchaSolver

# Setup logging to see what's happening
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def test_stt(audio_file_path):
    if not os.path.exists(audio_file_path):
        print(f"❌ File không tồn tại: {audio_file_path}")
        return

    print(f"🚀 Đang kiểm tra giải mã Audio STT cho file: {audio_file_path}")
    
    try:
        solver = AudioCaptchaSolver()
        # Gọi method mới đã thêm vào facebook_registration.py
        result = solver.solve_audio_file(audio_file_path)
        
        if result:
            print(f"\n✅ KẾT QUẢ GIẢI MÃ: {result}")
            print(f"✨ Hãy so sánh với mã bạn đã biết xem có khớp không nhé!")
        else:
            print(f"\n❌ KHÔNG GIẢI ĐƯỢC MÃ.")
            print(f"ℹ️ Có thể file bị lỗi hoặc FFmpeg không nhận dạng được format này.")
            
    except Exception as e:
        print(f"💥 Lỗi trong quá trình test: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Sử dụng: python test_audio_stt.py <đường_dẫn_file_audio>")
        print("Ví dụ: python test_audio_stt.py logs/captchas/audio_1773370137898.mp4")
    else:
        file_path = sys.argv[1]
        asyncio.run(test_stt(file_path))
