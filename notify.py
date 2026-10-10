# -*- coding: utf-8 -*-
"""Free phone notifications (Telegram) so you spend <5 min/week supervising.
Setup (once, 5 minutes): chat with @BotFather -> /newbot -> copy token,
then send any message to your bot and open:
  https://api.telegram.org/bot<TOKEN>/getUpdates  -> copy chat id.
Set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID as env vars / GitHub Secrets.
If unset, everything still works - notifications are silently skipped.
"""
import os
import logging

logger = logging.getLogger(__name__)


def send_telegram(text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        return False
    try:
        import requests
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": text},
            timeout=15,
        )
        return bool(r.ok)
    except Exception as e:
        logger.warning(f"Telegram notify failed: {e}")
        return False


def uploads_today(history, day_str):
    """Counts successful uploads (video_id set) for a YYYY-MM-DD day string."""
    n = 0
    for h in history or []:
        try:
            if h.get("video_id") and str(h.get("date", ""))[:10] == day_str:
                n += 1
        except Exception:
            continue
    return n
