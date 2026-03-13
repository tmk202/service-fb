"""
test_huawei_reset.py
====================
Test script to reset Huawei DCOM using the DcomManager logic.
"""

import logging
import sys
import os

# Set up logging to see details
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add current dir to path to find dcom_manager
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dcom_manager import DcomManager

def test_reset():
    dcom = DcomManager(
        gateway="192.168.16.1",
        modem_type="huawei",
        username="admin",
        password="admin",
        interface_name="Ethernet 2"
    )
    
    print("--- STARTING HUAWEI RESET TEST ---")
    success = dcom.reset_connection(wait_seconds=10)
    
    if success:
        print("✅ SUCCESS: DCOM reset completed.")
        new_ip = dcom.get_current_ip()
        print(f"🚀 NEW IP: {new_ip}")
    else:
        print("❌ FAILED: Could not reset DCOM.")

if __name__ == "__main__":
    test_reset()
