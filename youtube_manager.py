# -*- coding: utf-8 -*-
"""
YouTube Manager Module
Handles OAuth2 credentials verification, intelligent Islamic title & description generation,
and reliable video uploading via YouTube Data API v3.
"""

import os
import sys
import json
import logging
import random
import socket
import time
from pathlib import Path

# --- FIX WinError 10060 on Etisalat/WE routers: broken IPv6 blocks googleapis ---
# Windows prefers IPv6 (DNS returns IPv6 first) but the router drops IPv6 traffic,
# so httplib2 times out after ~21s on sock.connect(). Force IPv4-first globally.
try:
    _orig_getaddrinfo = socket.getaddrinfo

    def _ipv4_first_getaddrinfo(*args, **kwargs):
        try:
            responses = _orig_getaddrinfo(*args, **kwargs)
            # Sort: AF_INET (IPv4=2) first, everything else later
            return sorted(responses, key=lambda r: r[0] != socket.AF_INET)
        except Exception:
            return _orig_getaddrinfo(*args, **kwargs)

    socket.getaddrinfo = _ipv4_first_getaddrinfo
except Exception:
    pass

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from quran_data import SURAH_NAMES, is_makki

logger = logging.getLogger(__name__)

if getattr(sys, 'frozen', False):
    _exe_dir = Path(sys.executable).parent.resolve()
    _cands = (_exe_dir, *list(_exe_dir.parents)[:4])
    BASE_DIR = next((c for c in _cands
                     if (c / "templates").is_dir() and (c / "fonts").is_dir()), _exe_dir)
else:
    BASE_DIR = Path(__file__).parent.resolve()
TOKEN_FILE = BASE_DIR / "token.json"
CLIENT_SECRET_FILE = BASE_DIR / "client_secret.json"

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

TITLE_TEMPLATES_FULL = [
    "سورة {surah} كاملة بصوت باكي من الزمن الجميل | {reciter} 🌿 تلاوة خاشعة جداً",
    "تلاوة نادرة تأسر القلوب | سورة {surah} كاملة | {reciter} (تسجيلات الستينات) 🤲",
    "سورة {surah} كاملة راحة نفسية لا توصف | {reciter} 🕊️ روائع التلاوات الخالدة",
    "استمع وعش مع آيات الله | سورة {surah} كاملة بتلاوة تاريخية | {reciter} 🌿",
    "من روائع قراء مصر والزمن الجميل | سورة {surah} كاملة | {reciter} 🎙️",
    "صوت كان بيجمع العيلة على الراديو | سورة {surah} كاملة | {reciter} 📻 ذكريات الزمن الجميل",
    "رجعنا لأيام البركة | سورة {surah} كاملة بصوت من ذهب | {reciter} 🤲",
    "تلاوة تفكرك بأحلى أيام | سورة {surah} كاملة | {reciter} 🌙 نوستالجيا قرآنية"
]

TITLE_TEMPLATES_SHORTS = [
    "تلاوة خاشعة تريح القلوب | سورة {surah} ({ayahs}) | {reciter} 🌿 #shorts",
    "آيات سكينة وطمأنينة من سورة {surah} | {reciter} (الزمن الجميل) 🤲 #shorts",
    "«ألا بذكر الله تطمئن القلوب» | سورة {surah} | {reciter} 🕊️ #shorts",
    "صوت يأخذك إلى عالم آخر | سورة {surah} | {reciter} 🌿 #shorts",
    "فاكر الصوت ده؟ | سورة {surah} | {reciter} 📻 ذكريات لا تنسى #shorts"
]

def get_active_client_info():
    """Extracts client_id and client_secret from client_secret.json."""
    if not CLIENT_SECRET_FILE.exists():
        return None, None
    try:
        with open(CLIENT_SECRET_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        info = data.get("installed") or data.get("web") or {}
        return info.get("client_id"), info.get("client_secret")
    except Exception:
        return None, None

def check_youtube_auth():
    """Returns True if YouTube credentials exist and are valid.
    Supports BOTH: token.json (local studio) AND env vars (GitHub Actions / cloud)."""
    # Cloud mode: env vars present = ready (used by auto_generate + workflow)
    env_id = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
    env_sec = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
    env_ref = os.environ.get("YOUTUBE_REFRESH_TOKEN", "").strip()
    if env_id and env_sec and env_ref:
        return True, "قناة يوتيوب متصلة عبر مفاتيح البيئة وجاهزة للنشر ✅"

    active_client_id, _ = get_active_client_info()
    if not active_client_id:
        return False, "لم يتم العثور على ملف client_secret.json"
        
    if not TOKEN_FILE.exists():
        return False, f"المفتاح الجديد ({active_client_id[:12]}...) بحاجة للربط مع يوتيوب"
        
    try:
        with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        token_client_id = data.get("client_id")
        if token_client_id != active_client_id:
            return False, f"تم تغيير المفتاح إلى ({active_client_id[:12]}...) - انقر لربط القناة بالمفتاح الجديد"

        creds = Credentials(
            token=data.get("token"),
            refresh_token=data.get("refresh_token"),
            token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=data.get("client_id"),
            client_secret=data.get("client_secret"),
            scopes=SCOPES,
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    "token": creds.token,
                    "refresh_token": creds.refresh_token,
                    "token_uri": creds.token_uri,
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret,
                    "scopes": list(creds.scopes) if creds.scopes else SCOPES
                }, f, indent=2)
        return True, "قناة يوتيوب متصلة وجاهزة للنشر المباشر بالمفتاح الجديد ✅"
    except Exception as e:
        return False, f"رمز يوتيوب بحاجة للتحديث: {str(e)}"

def run_oauth_flow_interactive():
    """Runs interactive OAuth local server to generate a fresh token.json."""
    from google_auth_oauthlib.flow import InstalledAppFlow
    
    if not CLIENT_SECRET_FILE.exists():
        raise FileNotFoundError("ملف client_secret.json غير موجود.")
        
    flow = InstalledAppFlow.from_client_secrets_file(
        str(CLIENT_SECRET_FILE),
        scopes=SCOPES,
    )
    
    credentials = flow.run_local_server(
        port=8080,
        prompt="consent",
        access_type="offline",
    )
    
    token_data = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes),
    }
    
    with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
        json.dump(token_data, f, indent=2)
        
    return token_data

def get_authenticated_service():
    """Build and return authenticated YouTube API service."""
    if not TOKEN_FILE.exists():
        raise RuntimeError("ملف token.json غير موجود. يرجى إكمال إعداد يوتيوب أولاً.")
        
    with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    creds = Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        scopes=SCOPES,
    )
    
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": list(creds.scopes) if creds.scopes else SCOPES
            }, f, indent=2)
            
    return build("youtube", "v3", credentials=creds)

def generate_video_metadata(surah_num, reciter_name, mode="full", start_ayah=1, end_ayah=7, is_shorts=False):
    """Generates engaging, SEO-optimized title, description, and tags."""
    surah_name = SURAH_NAMES[surah_num - 1]
    rev_type = "مكية" if is_makki(surah_num) else "مدنية"
    
    ayah_label = "كاملة" if mode == "full" else f"الآيات {start_ayah}-{end_ayah}"
    
    # Title
    if is_shorts or mode != "full":
        template = random.choice(TITLE_TEMPLATES_SHORTS)
        title = template.format(surah=surah_name, ayahs=ayah_label, reciter=reciter_name)
    else:
        template = random.choice(TITLE_TEMPLATES_FULL)
        title = template.format(surah=surah_name, reciter=reciter_name)
        
    if len(title) > 95:
        title = title[:92] + "..."
        
    # Description
    description = f"""📖 سورة {surah_name} ({ayah_label}) - {rev_type}
🎙️ القارئ: {reciter_name}
🕰️ من روائع تلاوات الزمن الجميل وعمالقة التلاوة

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌿 فضل تلاوة القرآن الكريم:
قال رسول الله ﷺ: «خيركم من تعلم القرآن وعلمه»
وقال تعالى: ﴿الَّذِينَ آمَنُوا وَتَطْمَئِنُّ قُلُوبُهُم بِذِكْرِ اللَّهِ ۗ أَلَا بِذِكْرِ اللَّهِ تَطْمَئِنُّ الْقُلُوبُ﴾

🤲 نية الصدقة الجارية:
هذا المقطع صدقة جارية لوجه الله تعالى، نسألكم صالح الدعاء بالمغفرة والرحمة لجميع موتى المسلمين، وأن يجعله الله في ميزان حسنات كل من استمع إليه وشاركه.

اللهم اجعل القرآن العظيم ربيع قلوبنا، ونور صدورنا، وجلاء أحزاننا، وذهاب همومنا وغمومنا.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

#القرآن_الكريم
#quran
#سورة_{surah_name.replace(' ', '_')}
#{reciter_name.replace(' ', '_')}
#تلاوة_خاشعة
#الزمن_الجميل
#صدقة_جارية
"""

    tags = [
        "القرآن الكريم", "quran", f"سورة {surah_name}", reciter_name,
        "تلاوة خاشعة", "تلاوات نادرة", "الزمن الجميل", "قرآن كريم",
        "صدقة جارية", "تلاوة تبكي", "سورة كاملة"
    ]
    if is_shorts:
        tags.extend(["shorts", "شورتس", "ريلز"])

    return {
        'title': title,
        'description': description,
        'tags': tags
    }

def upload_to_youtube(video_path, title, description, tags, privacy_status="public", progress_cb=None):
    """Uploads video to YouTube with chunked progress + auto-retry on network errors."""
    import httplib2
    from googleapiclient.errors import HttpError

    if not os.path.exists(video_path):
        raise FileNotFoundError(f"ملف الفيديو غير موجود: {video_path}")

    youtube = get_authenticated_service()
    
    body = {
        "snippet": {
            "title": title[:98],
            "description": description[:4990],
            "tags": tags,
            "categoryId": "22",
            "defaultLanguage": "ar",
            "defaultAudioLanguage": "ar"
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
            "embeddable": True,
            "publicStatsViewable": True
        }
    }
    
    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=2 * 1024 * 1024  # 2MB chunks: أنسب للإنترنت البطيء/غير المستقر
    )

    logger.info(f"Uploading to YouTube: {title}")
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    # Resumable upload with retries: نفس كائن request يكمل من حيث توقف
    # (مهم لملفات 300+MB على إنترنت ضعيف + مشكلة IPv6 في راوترات WE/اتصالات)
    RETRIABLE = (TimeoutError, ConnectionError, ConnectionResetError,
                 BrokenPipeError, socket.timeout, socket.gaierror,
                 httplib2.ServerNotFoundError)
    response = None
    consecutive_errors = 0
    max_errors = 10

    while response is None:
        try:
            status, response = request.next_chunk()
            consecutive_errors = 0  # نجح chunk -> صفّر العداد
            if status and progress_cb:
                progress = int(status.progress() * 100)
                progress_cb(progress, f"جاري رفع الفيديو إلى يوتيوب ({progress}%)...")
        except HttpError as e:
            # أخطاء 500/502/503/504 قابلة لإعادة المحاولة، غيرها (مثل 403 quota) لا
            if e.resp is not None and e.resp.status in (500, 502, 503, 504):
                consecutive_errors += 1
                if consecutive_errors > max_errors:
                    raise
                wait = min(2 ** consecutive_errors, 60)
                logger.warning(f"⚠️ YouTube server {e.resp.status}, retry {consecutive_errors}/{max_errors} in {wait}s...")
                time.sleep(wait)
                continue
            raise
        except RETRIABLE as e:
            consecutive_errors += 1
            if consecutive_errors > max_errors:
                logger.error(f"❌ فشل الرفع بعد {max_errors} محاولات: {e}")
                raise ConnectionError(
                    f"تعذر الاتصال بسيرفرات يوتيوب بعد {max_errors} محاولات ({e}). "
                    "تأكد من: 1) الإنترنت مستقر 2) لا يوجد VPN يعطل الاتصال "
                    "3) عطّل IPv6 من إعدادات الواي فاي مؤقتاً 4) أعد المحاولة."
                ) from e
            wait = min(5 * consecutive_errors, 60)
            logger.warning(f"⚠️ انقطاع شبكة ({e}) - إعادة المحاولة {consecutive_errors}/{max_errors} بعد {wait}s (الرفع سيكمل من حيث توقف)...")
            time.sleep(wait)
            continue

    video_id = response.get("id")
    video_url = f"https://youtu.be/{video_id}"
    logger.info(f"Upload complete: {video_url}")
    return video_id, video_url


def diagnose_upload_connection():
    """Professional pre-upload check: IPv4 vs IPv6 reachability to Google APIs.

    Returns a dict with per-host results so the user can verify the network
    BEFORE rendering the next video.
    """
    import socket as _sock

    try:
        _addrs = _sock.getaddrinfo("www.googleapis.com", 443)
        _first_is_v4 = bool(_addrs) and _addrs[0][0] == _sock.AF_INET
    except Exception as e:
        return {"ok": False, "error": f"DNS failed: {e}", "ipv4_first": False, "hosts": {}}

    hosts = ["www.googleapis.com", "oauth2.googleapis.com", "www.youtube.com"]
    results = {}
    for h in hosts:
        item = {"ipv4": None, "ipv6": None}
        for fam, label in ((_sock.AF_INET, "ipv4"), (_sock.AF_INET6, "ipv6")):
            try:
                infos = [a for a in _sock.getaddrinfo(h, 443) if a[0] == fam]
                if not infos:
                    item[label] = "no-address"
                    continue
                ip = infos[0][4][0]
                s = _sock.socket(fam, _sock.SOCK_STREAM)
                s.settimeout(6)
                try:
                    s.connect((ip, 443))
                    item[label] = "ok"
                except Exception as e:
                    item[label] = f"fail: {type(e).__name__}"
                finally:
                    try:
                        s.close()
                    except Exception:
                        pass
            except Exception as e:
                item[label] = f"fail: {type(e).__name__}"
        results[h] = item

    ok = any(v.get("ipv4") == "ok" for v in results.values())
    advice = None
    if ok and any(v.get("ipv6", "").startswith("fail") for v in results.values()):
        advice = ("IPv4 يعمل وIPv6 مكسور (حالة راوترات WE/اتصالات الشائعة). "
                  "الكود الجديد يجبر IPv4 تلقائياً، ويفضل أيضاً تعطيل IPv6 من إعدادات الواي فاي.")
    elif not ok:
        advice = ("لا يوجد اتصال بسيرفرات جوجل حتى عبر IPv4. تحقق من الإنترنت والـ VPN وجدار الحماية ثم أعد الفحص.")
    return {"ok": ok, "ipv4_first": _first_is_v4, "hosts": results, "advice": advice}


def generate_ruqyah_metadata(ruqyah_name, reciter_name, hook=""):
    """SEO metadata for ruqyah videos."""
    title = f"{ruqyah_name} بصوت {reciter_name} | رقية شرعية مكررة بخشوع 🤲"
    if len(title) > 95:
        title = f"{ruqyah_name} | {reciter_name} | رقية شرعية 🤲"
    description = f"""🤲 {ruqyah_name}
🎙️ القارئ: {reciter_name}

{(hook + chr(10) + chr(10)) if hook else ""}آيات الرقية الشرعية من كتاب الله وسنة رسوله ﷺ، نسأل الله الشفاء والعافية لكل مريض ومبتلى.

قال تعالى: ﴿وَنُنَزِّلُ مِنَ الْقُرْآنِ مَا هُوَ شِفَاءٌ وَرَحْمَةٌ لِّلْمُؤْمِنِينَ﴾ [الإسراء: 82]

🤲 نية الصدقة الجارية:
هذا المقطع صدقة جارية لوجه الله تعالى، شاركه لينتفع به غيرك، ونسألكم صالح الدعاء.

#الرقية_الشرعية
#ruqyah
#رقية_شرعية
#{reciter_name.replace(' ', '_')}
#الحسد_والعين
#صدقة_جارية
"""
    tags = ["الرقية الشرعية", "ruqyah", "رقية شرعية", reciter_name,
            "رقية الحسد", "رقية السحر", "تحصين", "صدقة جارية", "quran"]
    return {'title': title, 'description': description, 'tags': tags}


def generate_compilation_metadata(surah_labels, reciter_name, hook=""):
    """SEO metadata for multi-surah compilation videos."""
    joined = " + ".join(surah_labels[:4]) + ("..." if len(surah_labels) > 4 else "")
    title = f"القرآن الكريم | {joined} | {reciter_name} 🌿 بدون إعلانات"
    if len(title) > 95:
        title = f"القرآن الكريم | {joined} 🌿"
    description = f"""📖 تلاوة مجمّعة: {joined}
🎙️ القارئ: {reciter_name}

{(hook + chr(10) + chr(10)) if hook else ""}تلاوة خاشعة متصلة لكلام الله، اسمع وتدبر كصدقة جارية لوجه الله تعالى.

قال رسول الله ﷺ: «خيركم من تعلم القرآن وعلمه»

#القرآن_الكريم
#quran
#تلاوة_خاشعة
#{reciter_name.replace(' ', '_')}
#صدقة_جارية
"""
    tags = ["القرآن الكريم", "quran", "تلاوة خاشعة", reciter_name,
            "سور مجمعة", "تلاوة متصلة", "صدقة جارية"] + surah_labels[:5]
    return {'title': title, 'description': description, 'tags': tags}

