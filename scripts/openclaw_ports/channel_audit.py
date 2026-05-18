"""Ported from clawdbot-main/scripts/tools — run via: py -3 scripts/openclaw_ports/<name>"""

import os
import requests
import json
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("ChannelAudit")

def audit_telegram(token):
    logger.info("Auditing Telegram Bot Token...")
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"  [SUCCESS] Telegram Bot: @{data['result']['username']} ({data['result']['first_name']})")
            return True
        else:
            logger.error(f"  [FAILURE] Telegram API returned {response.status_code}: {response.text}")
    except Exception as e:
        logger.error(f"  [ERROR] Telegram connection failed: {e}")
    return False

def audit_line(access_token):
    logger.info("Auditing LINE Channel Access Token...")
    url = "https://api.line.me/v2/bot/info"
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"  [SUCCESS] LINE Bot: {data['displayName']} ({data['userId']})")
            return True
        else:
            logger.error(f"  [FAILURE] LINE API returned {response.status_code}: {response.text}")
    except Exception as e:
        logger.error(f"  [ERROR] LINE connection failed: {e}")
    return False

def main():
    load_dotenv()
    
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
    line_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    
    logger.info("--- Sovereign Channel Audit Pulse ---")
    
    tg_ok = audit_telegram(tg_token) if tg_token else logger.warning("TELEGRAM_BOT_TOKEN not found in .env")
    line_ok = audit_line(line_token) if line_token else logger.warning("LINE_CHANNEL_ACCESS_TOKEN not found in .env")
    
    if tg_ok and line_ok:
        logger.info("--- [COMPLETE] Both channels are VALID. The issue is likely in OpenClaw Gateway registration/routing. ---")
    else:
        logger.warning("--- [COMPLETE] One or more channels failed validation. Check .env tokens. ---")

if __name__ == "__main__":
    main()
