"""
Browser Setup - Camoufox (Anti-Detect Browser)
=================================================
AsyncCamoufox trả về một BrowserContext (không phải Browser như Playwright thông thường).
Nên ta gọi context.new_page() trực tiếp.
"""

import os
import shutil
import tempfile
import logging

logger = logging.getLogger('BROWSER')


class TikTokBrowser:
    """
    Wrapper Camoufox giữ tên TikTokBrowser để tương thích với api_registration.py cũ.
    """

    def __init__(self, proxy_dict=None, headless=False):
        self.proxy = proxy_dict
        self.headless = headless
        self._cam_instance = None  # AsyncCamoufox context manager
        self.context = None        # BrowserContext Playwright
        self.page = None
        self.profile_dir = tempfile.mkdtemp(prefix="fb_profile_")

    async def launch(self):
        from camoufox.async_api import AsyncCamoufox # Chuẩn bị tham số Camoufox
        camoufox_opts = {
            "headless": self.headless,
            "humanize": 1.5,            
            "geoip": True,              
            "os": "macos",              # Chuyển sang macOS để GPU Fingerprint đồng nhất hơn
            "locale": "vi-VN",          
            "block_webrtc": True,       
            "proxy": self.proxy,
            # Cấu hình chuyên sâu chống detect (Senior Config)
            "firefox_user_prefs": {
                "browser.search.update": False,
                "browser.search.region": "VN",
                "intl.accept_languages": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
                "network.dns.disableIPv6": True,
            }
        }

        logger.info(f"🦊 [CAMOUFOX] Launching: headless={self.headless} | os=macos | locale=vi-VN")

        # AsyncCamoufox là async context manager → dùng __aenter__
        # Nó trả về BrowserContext (không phải Browser)
        self._cam_instance = AsyncCamoufox(**camoufox_opts)
        self.context = await self._cam_instance.__aenter__()

        # Tạo trang mới từ context
        self.page = await self.context.new_page()

        logger.info("✅ [CAMOUFOX] Browser & Page ready.")
        return self.page

    async def close(self):
        try:
            if self._cam_instance:
                await self._cam_instance.__aexit__(None, None, None)
                logger.info("🔒 [CAMOUFOX] Browser closed.")
        except Exception as e:
            logger.warning(f"[CAMOUFOX] Error on close: {e}")

        try:
            if self.profile_dir and os.path.exists(self.profile_dir):
                shutil.rmtree(self.profile_dir)
        except Exception:
            pass
