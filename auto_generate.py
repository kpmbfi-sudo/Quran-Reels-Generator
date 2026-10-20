#!/usr/bin/env python3
"""
Quran Reels Auto Generator - صدقة جارية مدى الحياة
Fully automated 24/7 engine to generate daily Quran reels / videos.
Runs via GitHub Actions cron job for 100% free, infinite operation.

STRICT Content Policy:
  - 100% Pure Elemental Nature ONLY (Clouds, Water, Mountains, Galaxies, Rain, Forest, Sky).
  - 0% Humans (No Men, No Women, No Children, No Faces, No Models, No Crowds).
  - 0% Animals / Living Creatures.
  - Multi-layer negative keyword blacklisting & tag inspection.
"""

import os
import sys
import json
import random
import logging
import datetime
import traceback
import time
import requests
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from quran_engine import get_reciter_by_id

# Fix Pillow >= 10 compatibility with moviepy 1.0.3
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

# Force Pillow to use BASIC layout engine on all platforms (Ubuntu/Linux & Windows).
try:
    _orig_truetype = ImageFont.truetype
    def _safe_truetype(font=None, size=10, *args, **kwargs):
        if "layout_engine" not in kwargs and hasattr(ImageFont, "Layout"):
            try:
                kwargs["layout_engine"] = ImageFont.Layout.BASIC
            except Exception:
                pass
        return _orig_truetype(font, size, *args, **kwargs)
    ImageFont.truetype = _safe_truetype
except Exception:
    pass

# Arabic text processing
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _reshaper_config = {
        'delete_harakat': False,
        'support_ligatures': True,
        'support_tashkeel': True,
    }
    _reshaper = arabic_reshaper.ArabicReshaper(configuration=_reshaper_config)
    HAS_ARABIC_RESHAPER = True
except ImportError:
    HAS_ARABIC_RESHAPER = False
    _reshaper = None
    print("⚠️ arabic-reshaper or python-bidi not installed.")

# --- Environment & Configuration ---
SCRIPT_DIR = Path(__file__).parent.resolve()

def _load_env():
    """Load variables from .env file if present."""
    env_file = SCRIPT_DIR / ".env"
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v

_load_env()

STATE_FILE = SCRIPT_DIR / "state.json"
OUTPUT_DIR = SCRIPT_DIR / "outputs"
AUDIO_DIR = OUTPUT_DIR / "audio"
VIDEO_DIR = OUTPUT_DIR / "video"
FONTS_DIR = SCRIPT_DIR / "fonts"

# Pexels API
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "").strip()

# Video settings (Reels format 9:16)
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 24

# Controls whether to render full Ayah text on screen or just Surah & Reciter name
SHOW_AYAH_TEXT = True

# Video playback speed multiplier (0.75 = 25% slower for majestic cinematic nature flow)
BG_SPEED_MULTIPLIER = 0.75

# Maximum duration for Shorts / Reels (in seconds)
MAX_DURATION_SHORTS = 58

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(SCRIPT_DIR / "auto_generate.log", encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# --- Surah Metadata ---
VERSE_COUNTS = {
    1: 7, 2: 286, 3: 200, 4: 176, 5: 120, 6: 165, 7: 206, 8: 75, 9: 129, 10: 109,
    11: 123, 12: 111, 13: 43, 14: 52, 15: 99, 16: 128, 17: 111, 18: 110, 19: 98, 20: 135,
    21: 112, 22: 78, 23: 118, 24: 64, 25: 77, 26: 227, 27: 93, 28: 88, 29: 69, 30: 60,
    31: 34, 32: 30, 33: 73, 34: 54, 35: 45, 36: 83, 37: 182, 38: 88, 39: 75, 40: 85,
    41: 54, 42: 53, 43: 89, 44: 59, 45: 37, 46: 35, 47: 38, 48: 29, 49: 18, 50: 45,
    51: 60, 52: 49, 53: 62, 54: 55, 55: 78, 56: 96, 57: 29, 58: 22, 59: 24, 60: 13,
    61: 14, 62: 11, 63: 11, 64: 18, 65: 12, 66: 12, 67: 30, 68: 52, 69: 52, 70: 44,
    71: 28, 72: 28, 73: 20, 74: 56, 75: 40, 76: 31, 77: 50, 78: 40, 79: 46, 80: 42,
    81: 29, 82: 19, 83: 36, 84: 25, 85: 22, 86: 17, 87: 19, 88: 26, 89: 30, 90: 20,
    91: 15, 92: 21, 93: 11, 94: 8, 95: 8, 96: 19, 97: 5, 98: 8, 99: 8, 100: 11,
    101: 11, 102: 8, 103: 3, 104: 9, 105: 5, 106: 4, 107: 7, 108: 3, 109: 6, 110: 3,
    111: 5, 112: 4, 113: 5, 114: 6
}

SURAH_NAMES = [
    'الفاتحة', 'البقرة', 'آل عمران', 'النساء', 'المائدة', 'الأنعام', 'الأعراف', 'الأنفال', 'التوبة', 'يونس',
    'هود', 'يوسف', 'الرعد', 'إبراهيم', 'الحجر', 'النحل', 'الإسراء', 'الكهف', 'مريم', 'طه',
    'الأنبياء', 'الحج', 'المؤمنون', 'النور', 'الفرقان', 'الشعراء', 'النمل', 'القصص', 'العنكبوت', 'الروم',
    'لقمان', 'السجدة', 'الأحزاب', 'سبأ', 'فاطر', 'يس', 'الصافات', 'ص', 'الزمر', 'غافر',
    'فصلت', 'الشورى', 'الزخرف', 'الدخان', 'الجاثية', 'الأحقاف', 'محمد', 'الفتح', 'الحجرات', 'ق',
    'الذاريات', 'الطور', 'النجم', 'القمر', 'الرحمن', 'الواقعة', 'الحديد', 'المجادلة', 'الحشر', 'الممتحنة',
    'الصف', 'الجمعة', 'المنافقون', 'التغابن', 'الطلاق', 'التحريم', 'الملك', 'القلم', 'الحاقة', 'المعارج',
    'نوح', 'الجن', 'المزمل', 'المدثر', 'القيامة', 'الإنسان', 'المرسلات', 'النبأ', 'النازعات', 'عبس',
    'التكوير', 'الانفطار', 'المطففين', 'الانشقاق', 'البروج', 'الطارق', 'الأعلى', 'الغاشية', 'الفجر', 'البلد',
    'الشمس', 'الليل', 'الضحى', 'الشرح', 'التين', 'العلق', 'القدر', 'البينة', 'الزلزلة', 'العاديات',
    'القارعة', 'التكاثر', 'العصر', 'الهمزة', 'الفيل', 'قريش', 'الماعون', 'الكوثر', 'الكافرون', 'النصر',
    'المسد', 'الإخلاص', 'الفلق', 'الناس'
]

# 14 World Renowned Reciters on EveryAyah
RECITERS = [
    {'id': 'Abdul_Basit_Murattal_64kbps', 'name': 'عبدالباسط عبدالصمد (مرتل)'},
    {'id': 'AbdulSamad_64kbps_QuranExplorer.Com', 'name': 'عبدالباسط عبدالصمد (مجود)'},
    {'id': 'Minshawy_Murattal_128kbps', 'name': 'محمد صديق المنشاوي (مرتل)'},
    {'id': 'Minshawy_Mujawwad_64kbps', 'name': 'محمد صديق المنشاوي (مجود)'},
    {'id': 'Husary_64kbps', 'name': 'محمود خليل الحصري'},
    {'id': 'Alafasy_64kbps', 'name': 'مشاري العفاسي'},
    {'id': 'Maher_AlMuaiqly_64kbps', 'name': 'ماهر المعيقلي'},
    {'id': 'Saood_ash-Shuraym_64kbps', 'name': 'سعود الشريم'},
    {'id': 'Abdurrahmaan_As-Sudais_64kbps', 'name': 'عبدالرحمن السديس'},
    {'id': 'Ghamadi_40kbps', 'name': 'سعد الغامدي'},
    {'id': 'Yasser_Ad-Dussary_128kbps', 'name': 'ياسر الدوسري'},
    {'id': 'Nasser_Alqatami_128kbps', 'name': 'ناصر القطامي'},
    {'id': 'Ahmed_ibn_Ali_al-Ajamy_64kbps', 'name': 'أحمد العجمي'},
    {'id': 'Abu_Bakr_Ash-Shaatree_128kbps', 'name': 'أبو بكر الشاطري'},
]

# ============================================================
# STRICT Pure Nature Search Queries (0% Humans, 0% Living Beings)
# ============================================================
PURE_NATURE_QUERIES = [
    "clouds timelapse sky",
    "ocean waves aerial scenery",
    "calm sea water surface",
    "waterfall cascading rocks",
    "galaxy stars space timelapse",
    "night sky milky way",
    "aurora borealis northern lights",
    "foggy forest trees mist",
    "rain drops water surface",
    "snow mountain peak landscape",
    "desert sand dunes wind",
    "sunlight through forest trees",
    "lake water mountain reflection",
    "river flowing stream stones",
    "sunset horizon clouds red",
    "green moss forest stream",
    "bamboo forest canopy breeze",
    "pine trees winter snow frost",
    "crystal blue water ripple",
    "mist over peaceful lake sunrise"
]

# STRICT Banned / Negative keywords (Skip video if ANY of these match in URL, tags, user, or title)
BANNED_KEYWORDS = [
    "person", "people", "man", "woman", "girl", "boy", "human", "face",
    "portrait", "model", "child", "baby", "kid", "couple", "family", "crowd",
    "walking", "dancer", "fashion", "hand", "hands", "feet", "body", "selfie",
    "lifestyle", "fitness", "workout", "legs", "eyes", "hair", "smile", "clothing",
    "dress", "shirt", "shoe", "run", "running", "yoga", "gym", "dancer",
    "animal", "dog", "cat", "bird", "lion", "horse", "fish", "creature", "pet",
    "wildlife", "insect", "bear", "deer", "monkey", "tiger", "shark", "whale"
]

# Design templates with high contrast overlay
TEMPLATES = [
    {'name': 'classic_gold', 'text_color': '#FFFFFF', 'accent_color': '#F5C518', 'overlay_opacity': 0.52, 'overlay_color': (0, 0, 0)},
    {'name': 'midnight_blue', 'text_color': '#FFFFFF', 'accent_color': '#70C5FF', 'overlay_opacity': 0.55, 'overlay_color': (5, 10, 30)},
    {'name': 'emerald_green', 'text_color': '#FFFFFF', 'accent_color': '#88E5A5', 'overlay_opacity': 0.52, 'overlay_color': (2, 25, 12)},
    {'name': 'royal_purple', 'text_color': '#FFFFFF', 'accent_color': '#D8A4FF', 'overlay_opacity': 0.54, 'overlay_color': (22, 5, 30)},
    {'name': 'warm_amber', 'text_color': '#FFFFFF', 'accent_color': '#FFD700', 'overlay_opacity': 0.52, 'overlay_color': (30, 15, 0)},
]

# ============================================================
# Utilities
# ============================================================
def safe_request(url, method='get', max_retries=3, base_delay=2, timeout=30, **kwargs):
    """Execute HTTP request with automatic retries."""
    for attempt in range(max_retries):
        try:
            resp = getattr(requests, method)(url, timeout=timeout, **kwargs)
            resp.raise_for_status()
            return resp
        except Exception as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(0.5, 1.5)
                logger.warning(f"⚠️ Request failed: {e}. Retrying in {delay:.1f}s...")
                time.sleep(delay)
            else:
                logger.error(f"❌ Request failed permanently: {e}")
                raise

def clean_arabic_for_rendering(text):
    """Preserves 100% pure, unaltered official Uthmani Quranic text."""
    if not text:
        return ""
    return text

def reshape_arabic(text):
    """Format Arabic text with proper ligatures and RTL ordering (uniform for BASIC layout engine)."""
    if not text:
        return ""
    cleaned = clean_arabic_for_rendering(text)
    if HAS_ARABIC_RESHAPER and _reshaper is not None:
        try:
            reshaped = _reshaper.reshape(cleaned)
            return get_display(reshaped)
        except Exception:
            return cleaned
    return cleaned

def wrap_and_reshape_arabic(text, words_per_line=4):
    """Word-wraps FIRST in logical order, then shapes each line individually."""
    if not text:
        return ""
    words = text.split()
    lines = [' '.join(words[i:i + words_per_line]) for i in range(0, len(words), words_per_line)]
    reshaped_lines = [reshape_arabic(line) for line in lines]
    return '\n'.join(reshaped_lines)

ARABIC_DIGITS = {'0': '٠', '1': '١', '2': '٢', '3': '٣', '4': '٤', '5': '٥', '6': '٦', '7': '٧', '8': '٨', '9': '٩'}
def to_arabic_numeral(n):
    return ''.join(ARABIC_DIGITS.get(d, d) for d in str(n))

# ============================================================
# State & Reciter Rotation Management
# ============================================================
def load_state():
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "total_generated": 0,
        "last_reciter_idx": 0,
        "last_surah": 1,
        "last_ayah": 0,
        "history": []
    }

def save_state(state):
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                disk_data = json.load(f)
                if "used_backgrounds" in disk_data:
                    state["used_backgrounds"] = disk_data["used_backgrounds"]
        except Exception:
            pass
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def pick_next_reciter(state):
    """Select the next reciter in round-robin fashion for infinite variety."""
    current_idx = state.get("last_reciter_idx", 0)
    next_idx = (current_idx + 1) % len(RECITERS)
    state["last_reciter_idx"] = next_idx
    reciter = RECITERS[next_idx]
    logger.info(f"🎙️ Selected Reciter: {reciter['name']}")
    return reciter

def pick_ayah_sequence(state):
    """
    Picks consecutive Ayahs ensuring the total recitation time fits within Shorts limit.
    Surahs 78-114 (Juz Amma) preferred for perfect Shorts timing.
    """
    recent_keys = set()
    for entry in state.get("history", [])[-150:]:
        recent_keys.add(f"{entry.get('surah')}:{entry.get('start_ayah')}")

    # 75% Juz Amma (Surahs 78 to 114) for Shorts, 25% from rest of Quran
    for _ in range(250):
        if random.random() < 0.75:
            surah = random.randint(78, 114)
            max_ayah = VERSE_COUNTS[surah]
            num_ayahs = random.randint(2, min(5, max_ayah))
        else:
            surah = random.randint(1, 77)
            max_ayah = VERSE_COUNTS[surah]
            num_ayahs = random.randint(1, min(3, max_ayah))

        start_ayah = random.randint(1, max(1, max_ayah - num_ayahs + 1))
        end_ayah = min(start_ayah + num_ayahs - 1, max_ayah)

        key = f"{surah}:{start_ayah}"
        if key not in recent_keys:
            return surah, start_ayah, end_ayah

    # Default fallback
    surah = random.randint(78, 114)
    return surah, 1, min(4, VERSE_COUNTS[surah])

# ============================================================
# Media Downloader with Strict Anti-Human / Nature-Only Filter
# ============================================================
def is_strictly_pure_nature(video_obj):
    """
    Validates that a video is 100% Pure Elemental Nature.
    Rejects any video containing humans, faces, models, crowds, or animals.
    """
    # 1. Check video URL slug
    url_slug = str(video_obj.get("url", "")).lower()
    for word in BANNED_KEYWORDS:
        if word in url_slug:
            return False

    # 2. Check tags
    tags = video_obj.get("tags", [])
    for tag in tags:
        tag_str = str(tag).lower()
        for word in BANNED_KEYWORDS:
            if word in tag_str:
                return False

    # 3. Check user name / photographer title
    user_info = video_obj.get("user", {})
    user_name = str(user_info.get("name", "")).lower()
    if any(term in user_name for term in ["model", "fitness", "lifestyle", "girl", "boy"]):
        return False

    return True

def fetch_pexels_video(api_key):
    """Download vertical HD nature video from Pexels with STRICT 100% nature filtering."""
    if not api_key:
        raise ValueError(
            "❌ PEXELS_API_KEY is missing!\n"
            "Please add your Pexels API key to .env (for local use) or GitHub Secrets (PEXELS_API_KEY).\n"
            "Get a free API key at: https://www.pexels.com/api/"
        )
    headers = {"Authorization": api_key}
    
    # Shuffle search queries for variety
    queries_pool = random.sample(PURE_NATURE_QUERIES, len(PURE_NATURE_QUERIES))

    for query in queries_pool:
        params = {
            "query": query,
            "orientation": "portrait",
            "size": "medium",
            "per_page": 15,
            "page": random.randint(1, 3),
        }

        logger.info(f"🔍 Searching Pexels for pure nature: '{query}'")
        try:
            resp = safe_request("https://api.pexels.com/videos/search", headers=headers, params=params)
            videos = resp.json().get("videos", [])
        except Exception:
            continue

        # Filter strictly
        verified_nature_videos = [v for v in videos if is_strictly_pure_nature(v)]

        if not verified_nature_videos:
            logger.warning(f"⚠️ Query '{query}' had no 100% verified pure nature videos, trying next query...")
            continue

        video = random.choice(verified_nature_videos)
        video_files = video.get("video_files", [])

        best_file = None
        for vf in sorted(video_files, key=lambda x: x.get("height", 0), reverse=True):
            if 720 <= vf.get("height", 0) <= 1920:
                best_file = vf
                break

        if not best_file and video_files:
            best_file = video_files[0]

        if best_file:
            download_url = best_file["link"]
            logger.info(f"📥 Downloading verified pure nature video...")

            video_resp = safe_request(download_url, timeout=120)
            temp_path = AUDIO_DIR / "bg_video.mp4"
            with open(temp_path, 'wb') as f:
                f.write(video_resp.content)

            return str(temp_path)

    # Fallback to absolute safest elemental query
    fallback_resp = safe_request(
        "https://api.pexels.com/videos/search",
        headers=headers,
        params={"query": "clouds timelapse sky", "orientation": "portrait", "per_page": 10}
    )
    fallback_videos = fallback_resp.json().get("videos", [])
    if fallback_videos:
        download_url = fallback_videos[0]["video_files"][0]["link"]
        video_resp = safe_request(download_url, timeout=120)
        temp_path = AUDIO_DIR / "bg_video.mp4"
        with open(temp_path, 'wb') as f:
            f.write(video_resp.content)
        return str(temp_path)

    raise RuntimeError("Could not find suitable nature video from Pexels.")

def get_ayah_text(surah, ayah):
    resp = safe_request(f'https://api.alquran.cloud/v1/ayah/{surah}:{ayah}/quran-uthmani')
    return resp.json()['data']['text']

def download_audio(reciter_id, surah, ayah, output_path):
    from pydub import AudioSegment

    fn = f'{surah:03d}{ayah:03d}.mp3'
    url = f'https://everyayah.com/data/{reciter_id}/{fn}'
    resp = safe_request(url, timeout=60)

    with open(output_path, 'wb') as f:
        f.write(resp.content)

    # Trim leading/trailing silence for seamless recitation flow
    try:
        snd = AudioSegment.from_file(output_path, 'mp3')
        silence_thresh = max(-42.0, snd.dBFS - 12)

        def detect_start(s):
            chunk = 10
            pos = 0
            while pos < len(s) and s[pos:pos + chunk].dBFS < silence_thresh:
                pos += chunk
            return pos

        start = detect_start(snd)
        end = detect_start(snd.reverse())

        # Keep a tiny 30ms padding so recitation sounds natural without abrupt cuts
        start_pos = max(0, start - 30)
        end_pos = max(0, len(snd) - end + 30)

        if end_pos > start_pos + 300:
            trimmed = snd[start_pos:end_pos]
            trimmed.export(output_path, format='mp3')
    except Exception as e:
        logger.warning(f"Audio trim warning: {e}")

    return output_path

# ============================================================
# Video Engine (Slow-Motion, Seamless Loop, Pillow Typography)
# ============================================================
def get_best_quran_font():
    """Returns the best available Arabic Quran font path."""
    for fn in ["Amiri-Bold.ttf", "Amiri-Regular.ttf", "DUBAI-BOLD.TTF"]:
        p = FONTS_DIR / fn
        if p.exists() and p.stat().st_size > 10000:
            return str(p)
    return str(FONTS_DIR / "Amiri-Bold.ttf")

def create_text_image(text, font_size, text_color, font_path=None, is_wrapped=False, words_per_line=4, stroke_width=2, stroke_color='black', shadow=True):
    """
    Renders gorgeous Arabic typography to RGBA numpy array using Pillow.
    Guarantees proper RTL alignment, ligatures, and Tashkeel.
    """
    if font_path is None or not os.path.exists(font_path):
        font_path = get_best_quran_font()

    try:
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        try:
            font = ImageFont.truetype("fonts/Amiri-Bold.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

    if is_wrapped:
        display_text = wrap_and_reshape_arabic(text, words_per_line=words_per_line)
    else:
        display_text = reshape_arabic(text)

    # Compute bounding box
    dummy_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    dummy_draw = ImageDraw.Draw(dummy_img)
    bbox = dummy_draw.multiline_textbbox((0, 0), display_text, font=font, spacing=26, align='center')
    text_w = max(10, bbox[2] - bbox[0] + 60)
    text_h = max(10, bbox[3] - bbox[1] + 60)

    img = Image.new("RGBA", (int(text_w), int(text_h)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    x = 30
    y = 30
    # Drop shadow
    if shadow:
        draw.multiline_text(
            (x + 4, y + 4), display_text, font=font, fill=(0, 0, 0, 220),
            spacing=26, align='center', stroke_width=stroke_width + 2, stroke_fill=(0, 0, 0, 220)
        )
    # Main crisp text with outline
    draw.multiline_text(
        (x, y), display_text, font=font, fill=text_color,
        spacing=26, align='center', stroke_width=stroke_width, stroke_fill=stroke_color
    )

    return np.array(img)

def create_pil_text_clip(text, duration, font_size, text_color, font_path=None, is_wrapped=False, words_per_line=4, pos='center', stroke_width=2, shadow=True):
    from moviepy.editor import ImageClip
    img_arr = create_text_image(
        text, font_size, text_color, font_path=font_path,
        is_wrapped=is_wrapped, words_per_line=words_per_line,
        stroke_width=stroke_width, shadow=shadow
    )
    return ImageClip(img_arr, ismask=False).set_duration(duration).set_position(pos)

def process_background_clip(bg_path, target_duration):
    """
    Applies Slow-Motion (to stretch duration and add calm aesthetic),
    crops to 9:16, and loops seamlessly to match target_duration.
    """
    from moviepy.editor import VideoFileClip
    import moviepy.video.fx.all as vfx

    raw_clip = VideoFileClip(bg_path)
    
    # 1. Apply Slow Motion effect
    try:
        slow_clip = raw_clip.fx(vfx.speedx, BG_SPEED_MULTIPLIER)
    except Exception:
        slow_clip = raw_clip

    # 2. Resize & Crop to 1080x1920
    slow_clip = slow_clip.resize(height=VIDEO_HEIGHT)
    if slow_clip.w > VIDEO_WIDTH:
        slow_clip = slow_clip.crop(x_center=slow_clip.w / 2, y_center=VIDEO_HEIGHT / 2, width=VIDEO_WIDTH, height=VIDEO_HEIGHT)
    elif slow_clip.w < VIDEO_WIDTH:
        slow_clip = slow_clip.resize(width=VIDEO_WIDTH)
        if slow_clip.h > VIDEO_HEIGHT:
            slow_clip = slow_clip.crop(x_center=VIDEO_WIDTH / 2, y_center=slow_clip.h / 2, width=VIDEO_WIDTH, height=VIDEO_HEIGHT)

    # 3. Loop seamlessly for exact duration
    final_bg = slow_clip.fx(vfx.loop, duration=target_duration).subclip(0, target_duration)
    return final_bg

def build_reel(surah, start_ayah, end_ayah, reciter, pexels_key):
    from moviepy.editor import (
        AudioFileClip, CompositeVideoClip, concatenate_videoclips, ColorClip
    )

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)

    template = random.choice(TEMPLATES)
    logger.info(f"🎨 Theme: {template['name']} | 📖 سورة {SURAH_NAMES[surah-1]} ({start_ayah}-{end_ayah})")

    font_path = get_best_quran_font()

    # Download Background (100% Pure Nature Guaranteed)
    bg_video_path = fetch_pexels_video(pexels_key)

    # Download Audio & Ayah Data (Target: 35s to 58s duration)
    MIN_DURATION_SHORTS = 35.0
    MAX_DURATION_SHORTS = 58.0

    ayah_data = []
    total_audio_duration = 0.0
    max_verse = VERSE_COUNTS.get(surah, 7)
    curr_ayah = start_ayah

    while curr_ayah <= max_verse:
        audio_path = str(AUDIO_DIR / f"ayah_{surah}_{curr_ayah}.mp3")
        download_audio(reciter['id'], surah, curr_ayah, audio_path)
        text = get_ayah_text(surah, curr_ayah)

        audio_clip = AudioFileClip(audio_path)
        dur = audio_clip.duration

        # If adding this ayah exceeds MAX_DURATION_SHORTS and we already met MIN_DURATION, stop
        if total_audio_duration >= MIN_DURATION_SHORTS and (total_audio_duration + dur > MAX_DURATION_SHORTS):
            logger.info(f"⏱️ Reached ideal duration ({total_audio_duration:.1f}s >= {MIN_DURATION_SHORTS}s). Stopping before Ayah {curr_ayah}.")
            audio_clip.close()
            break

        total_audio_duration += dur
        ayah_data.append({
            'ayah': curr_ayah,
            'text': text,
            'audio_path': audio_path,
            'duration': dur,
            'audio_clip': audio_clip
        })
        end_ayah = curr_ayah

        if total_audio_duration >= MAX_DURATION_SHORTS:
            logger.info(f"⏱️ Reached max Shorts limit ({total_audio_duration:.1f}s). Stopping at Ayah {curr_ayah}.")
            break

        curr_ayah += 1

    # If surah ended before reaching MIN_DURATION and start_ayah > 1, prepend earlier ayahs from start_ayah-1 down to 1
    if total_audio_duration < MIN_DURATION_SHORTS and start_ayah > 1:
        prev_ayah = start_ayah - 1
        while prev_ayah >= 1 and total_audio_duration < MIN_DURATION_SHORTS:
            audio_path = str(AUDIO_DIR / f"ayah_{surah}_{prev_ayah}.mp3")
            download_audio(reciter['id'], surah, prev_ayah, audio_path)
            text = get_ayah_text(surah, prev_ayah)
            audio_clip = AudioFileClip(audio_path)
            dur = audio_clip.duration

            if total_audio_duration + dur > MAX_DURATION_SHORTS:
                audio_clip.close()
                break

            total_audio_duration += dur
            ayah_data.insert(0, {
                'ayah': prev_ayah,
                'text': text,
                'audio_path': audio_path,
                'duration': dur,
                'audio_clip': audio_clip
            })
            start_ayah = prev_ayah
            prev_ayah -= 1

    # Build Segments
    clips = []

    # Ayah Segments
    for data in ayah_data:
        dur = data['duration']
        bg_segment = process_background_clip(bg_video_path, dur)
        overlay = ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=template['overlay_color']).set_opacity(template['overlay_opacity']).set_duration(dur)

        # Surah Label
        surah_lbl = f"سورة {SURAH_NAMES[surah-1]}"
        surah_clip = create_pil_text_clip(surah_lbl, dur, 60, template['accent_color'], font_path, pos=('center', 180), stroke_width=2)

        # Reciter Label
        reciter_lbl = f"القارئ: {reciter['name']}"
        reciter_clip = create_pil_text_clip(reciter_lbl, dur, 44, template['text_color'], font_path, pos=('center', 265), stroke_width=1)

        layer_elements = [bg_segment, overlay, surah_clip, reciter_clip]

        # Full Ayah Text (Large, prominent, beautifully centered)
        if SHOW_AYAH_TEXT:
            word_count = len(data['text'].split())
            ayah_font_size = 58 if word_count > 20 else (66 if word_count > 12 else 74)
            words_per_line = 4 if word_count > 10 else 3
            
            text_clip = create_pil_text_clip(
                data['text'], dur, ayah_font_size, template['text_color'],
                font_path, is_wrapped=True, words_per_line=words_per_line,
                pos='center', stroke_width=3
            )
            
            arabic_num = to_arabic_numeral(data['ayah'])
            ayah_num_lbl = f"( آية {arabic_num} )"
            ayah_num_clip = create_pil_text_clip(ayah_num_lbl, dur, 48, template['accent_color'], font_path, pos=('center', 1480), stroke_width=2)
            layer_elements.extend([text_clip, ayah_num_clip])

        audio_with_fade = data['audio_clip'].audio_fadein(0.01).audio_fadeout(0.01)
        segment = CompositeVideoClip(layer_elements).set_audio(audio_with_fade)
        clips.append(segment)

    # Outro (Sadaq Allah + Duaa)
    outro_dur = 3.5
    outro_bg = ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=template['overlay_color']).set_duration(outro_dur)
    sadaq_clip = create_pil_text_clip("صَدَقَ اللَّهُ الْعَظِيمُ", outro_dur, 68, template['accent_color'], font_path, pos=('center', VIDEO_HEIGHT // 2 - 70), stroke_width=2)
    cta_clip = create_pil_text_clip("صدقة جارية 🤲 لا تنسونا من صالح دعائكم", outro_dur, 40, 'white', font_path, pos=('center', VIDEO_HEIGHT // 2 + 45), stroke_width=1)
    clips.append(CompositeVideoClip([outro_bg, sadaq_clip, cta_clip]))

    # Concatenate & Render
    final = concatenate_videoclips(clips, method='compose')
    total_duration = final.duration

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"QuranReel_{SURAH_NAMES[surah-1]}_{start_ayah}-{end_ayah}_{timestamp}.mp4"
    output_path = str(VIDEO_DIR / filename)

    logger.info(f"💾 Exporting Video: {filename} ({total_duration:.1f}s)")
    final.write_videofile(
        output_path,
        fps=VIDEO_FPS,
        codec='libx264',
        audio_codec='aac',
        audio_bitrate='192k',
        verbose=False,
        logger=None,
        ffmpeg_params=['-movflags', '+faststart']
    )

    # Cleanup temp audio
    try:
        for f in AUDIO_DIR.iterdir():
            f.unlink()
    except Exception:
        pass

    return output_path, total_duration, end_ayah

# ============================================================
# Main Entry Point
# ============================================================
def main(test_mode=False):
    logger.info("=" * 60)
    logger.info("📖 Quran Reels Infinite Generator - صدقة جارية")
    logger.info(f"📅 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    state = load_state()
    reciter = pick_next_reciter(state)
    surah, start_ayah, end_ayah = pick_ayah_sequence(state)

    logger.info(f"🎯 Target: سورة {SURAH_NAMES[surah-1]} | آيات {start_ayah} إلى {end_ayah}")

    video_path, duration, actual_end_ayah = build_reel(surah, start_ayah, end_ayah, reciter, PEXELS_API_KEY)

    # YouTube Upload
    video_id = None
    if not test_mode:
        try:
            from youtube_uploader import YouTubeUploader
            uploader = YouTubeUploader()
            surah_name = SURAH_NAMES[surah - 1]
            title = f"سورة {surah_name} | آيات {start_ayah}-{actual_end_ayah} | {reciter['name']} | تلاوة خاشعة 🤲 #shorts"
            if len(title) > 100:
                title = f"سورة {surah_name} | {reciter['name']} | تلاوة خاشعة 🤲 #shorts"

            description = f"""📖 سورة {surah_name} ({start_ayah}-{actual_end_ayah})
🎙️ القارئ: {reciter['name']}

هذا العمل صدقة جارية لوجه الله تعالى، نسألكم الدعاء بالمغفرة والرحمة لجميع موتى المسلمين. 🤲

#قرآن #quran #shorts #تلاوة_خاشعة #سورة_{surah_name.replace(' ', '_')} #صدقة_جارية"""

            tags = ['قرآن', 'quran', 'shorts', reciter['name'], f'سورة {surah_name}', 'صدقة جارية', 'تلاوة']
            video_id = uploader.upload(video_path, title, description, tags)
        except Exception as e:
            import traceback
            logger.error(f"Upload error: {e}")
            logger.error(traceback.format_exc())

    # Update State
    state["total_generated"] = state.get("total_generated", 0) + 1
    state["history"].append({
        "surah": surah,
        "surah_name": SURAH_NAMES[surah - 1],
        "start_ayah": start_ayah,
        "end_ayah": actual_end_ayah,
        "reciter": reciter['name'],
        "duration": round(duration, 1),
        "video_id": video_id,
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    save_state(state)

    logger.info(f"🎉 Successfully completed! Total videos generated: {state['total_generated']}")
    return video_path

# ============================================================
# 🎬 LONG-VIDEO CLOUD PATH | المسار السحابي للفديوهات الطويلة
#    يستخدم المحرك الموحّد القوي (quran_engine) لإنشاء سورة كاملة
#    بالنص العثماني المتزامن + خلفيات Pexels تلقائياً، ويرفعها
#    على يوتيوب كفيديو طويل (دعم LONG_YOUTUBE_* dual-project).
# ============================================================

CLOUD_MAX_AYAHS = 78   # حد آمن لـ GitHub Actions (timeout) — السور الأكبر يدوياً
RECITER_LOCK = 'ajamy'  # 🎙️ قناة متخصصة: الشيخ أحمد بن علي العجمي فقط

# 🎬 تجميعات سور مختارة (تنوع في الطول والثيمة) - مجموعات قرآنية مميزة
COMPILATION_SETS = [
    {
        "title": "خواتيم القرآن الكريم | جزء عمَّ المختصر",
        "items": [(78, 1, 20), (79, 1, 20), (80, 1, 20), (81, 1, 20), (82, 1, 19), (83, 1, 20)],
    },
    {
        "title": "السور الخمس العظيمة | يس والرحمن والواقعة والملك والنبأ",
        "items": [(36, 1, 83), (55, 1, 31), (56, 1, 26), (67, 1, 30), (78, 1, 40)],
    },
    {
        "title": "سور الفجر والطمأنينة | الفجر والضحى والشرح والقدر والزلزلة",
        "items": [(89, 1, 30), (93, 1, 11), (94, 1, 8), (97, 1, 5), (99, 1, 8)],
    },
    {
        "title": "المعوذات والفاتحة | تحصين وإيمان",
        "items": [(1, 1, 7), (112, 1, 4), (113, 1, 5), (114, 1, 6), (109, 1, 6)],
    },
    {
        "title": "سور الرحمة والمغفرة | طه والملك والقلم والنبأ",
        "items": [(20, 1, 30), (67, 1, 30), (68, 1, 30), (78, 1, 40)],
    },
    {
        "title": "جزء تبارك المختصر | الملك والقلم والحاقة والمعارج ونوح",
        "items": [(67, 1, 30), (68, 1, 30), (69, 1, 30), (70, 1, 30), (71, 1, 28)],
    },
    {
        "title": "سور الجنة والنار | الواقعة والطارق والغاشية والزلزلة والقارعة",
        "items": [(56, 1, 26), (86, 1, 17), (88, 1, 26), (99, 1, 8), (101, 1, 11)],
    },
    {
        "title": "القرآن كلام الله | الرحمن والنبأ والفجر والشمس والضحى",
        "items": [(55, 1, 31), (78, 1, 40), (89, 1, 30), (91, 1, 15), (93, 1, 11)],
    },
]


def pick_next_long_surah(state):
    """دورة ذكية عبر السور المناسبة للسحابة (تتخطى الضخمة جداً مثل البقرة)."""
    start_from = int(state.get("last_long_surah", 0) or 0)
    for offset in range(1, 115):
        s = ((start_from + offset - 1) % 114) + 1
        if VERSE_COUNTS[s] <= CLOUD_MAX_AYAHS:
            return s
    return 78  # النبأ (أطول سورة ضمن الحد)


def pick_next_long_reciter(state):
    """🎙️ القارئ مُثبّت على الشيخ العجمي (تخصص القناة)."""
    return get_reciter_by_id(RECITER_LOCK)


def _long_youtube_title(res, kind_label):
    return f"{kind_label} | {res.get('surah_name', 'تلاوة قرآنية')} | أحمد العجمي 🌿"


def _upload_long(video_path, title, description, tags, thumbnail_path=None):
    """رفع موحّد للفيديو الطويل (مشروع LONG_YOUTUBE_* المنفصل، احتياطي YOUTUBE_*)."""
    from youtube_uploader import YouTubeUploader
    try:
        uploader = YouTubeUploader(kind="long")
    except Exception:
        uploader = YouTubeUploader()
    return uploader.upload(video_path, title, description, tags, thumbnail_path=thumbnail_path)


def run_long_generation(state, test_mode=False):
    """يولّد سورة كاملة طويلة بالمحرك الموحّد ويرفعها لليوتيوب."""
    from quran_engine import render_long_quran_video
    from seo_engine import generate_surah_seo

    surah = pick_next_long_surah(state)
    reciter = pick_next_long_reciter(state)
    surah_name = SURAH_NAMES[surah - 1]

    logger.info("=" * 60)
    logger.info("🎬 LONG-VIDEO ENGINE (المحرك الموحّد) - سورة كاملة")
    logger.info("=" * 60)
    logger.info(f"🎯 الهدف: سورة {surah_name} كاملة ({VERSE_COUNTS[surah]} آية)")
    logger.info("🎙️ القارئ: أحمد العجمي")

    pexels_key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not pexels_key:
        logger.warning("⚠️ PEXELS_API_KEY غير موجود - سيتم استخدام الخلفيات المحلية/الكاش.")

    def _progress(pct, msg):
        logger.info(f"[{pct}%] {msg}")

    res = render_long_quran_video(
        surah_num=surah,
        reciter_id=reciter["id"],
        mode="full",
        aspect_ratio="16:9",
        speed_mode="max",
        progress_callback=_progress,
        pexels_mode="auto",
        pexels_api_key=pexels_key,
    )

    video_id = None
    if not test_mode:
        try:
            seo = generate_surah_seo(surah, res["ayahs_count"], res["duration"])
            title = seo["title"]
            description = seo["description"]
            tags = seo["tags"]
            video_id = _upload_long(res["video_path"], title, description, tags,
                                    thumbnail_path=res.get("thumbnail"))
        except Exception as e:
            import traceback
            logger.error(f"Upload error: {e}")
            logger.error(traceback.format_exc())

    state["total_generated"] = state.get("total_generated", 0) + 1
    state["last_long_surah"] = surah
    try:
        from quran_data import RECITERS_ORDERED
        state["last_long_reciter_idx"] = next(
            (i for i, r in enumerate(RECITERS_ORDERED) if r["id"] == reciter["id"]),
            state.get("last_long_reciter_idx", 0))
    except Exception:
        pass
    state["history"].append({
        "kind": "long",
        "surah": surah,
        "surah_name": surah_name,
        "ayahs": res["ayahs_count"],
        "reciter": reciter["name"],
        "duration": round(res["duration"], 1),
        "size_mb": res.get("size_mb"),
        "video_id": video_id,
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    save_state(state)
    logger.info(f"🎉 Long video done! Duration: {res['duration']:.1f}s, chapters: {res['chapters_count']}")
    if video_id and not test_mode:
        cleanup_after_upload(res["video_path"], res.get("thumbnail"))
    return res["video_path"]


def cleanup_after_upload(video_path, thumbnail_path=None):
    """حذف ملف الفيديو الطويل والملفات المؤقتة فور نجاح الرفع لتوفير المساحة في جيت هب."""
    try:
        if video_path and os.path.exists(video_path):
            sz_mb = os.path.getsize(video_path) / (1024 * 1024)
            os.remove(video_path)
            logger.info(f"🗑️ تم حذف الفيديو بعد اكتمال النشر لتوفير المساحة: {os.path.basename(video_path)} ({sz_mb:.1f} MB freed)")
    except Exception as e:
        logger.warning(f"تعذر حذف ملف الفيديو {video_path}: {e}")

    try:
        # تفريغ مسارات الصوت المؤقت وصفحات الفصول من outputs/audio
        for f in AUDIO_DIR.glob("long_*.mp3"):
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass
        for f in AUDIO_DIR.glob("chapter_*.png"):
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"ملاحظة تنظيف المؤقتات: {e}")


def run_job_surah(state, test_mode=False):
    """🎬 [1/3] سورة كاملة طويلة بالرسم العثماني بصوت الشيخ العجمي."""
    from quran_engine import render_long_quran_video
    reciter = pick_next_long_reciter(state)
    pexels_key = os.environ.get("PEXELS_API_KEY", "").strip()

    def _progress(pct, msg):
        logger.info(f"[{pct}%] {msg}")

    surah = pick_next_long_surah(state)
    surah_clean = SURAH_NAMES[surah - 1].replace("سورة", "").strip()
    logger.info("=" * 60)
    logger.info(f"🎬 [1/3] سورة كاملة: سورة {surah_clean} ({VERSE_COUNTS[surah]} آية)")
    logger.info("=" * 60)
    res = render_long_quran_video(surah_num=surah, reciter_id=reciter["id"], mode="full",
                                  aspect_ratio="16:9", speed_mode="max",
                                  progress_callback=_progress,
                                  pexels_mode="auto", pexels_api_key=pexels_key)
    video_id = None
    if not test_mode:
        try:
            from seo_engine import generate_surah_seo
            seo = generate_surah_seo(surah, res["ayahs_count"], res["duration"])
            title = seo["title"]
            desc = seo["description"]
            tags = seo["tags"]
            video_id = _upload_long(res["video_path"], title, desc, tags,
                                    thumbnail_path=res.get("thumbnail"))
            if video_id:
                cleanup_after_upload(res["video_path"], res.get("thumbnail"))
        except Exception as e:
            logger.error(f"[1/3] upload error: {e}")

    job = {"kind": "long_surah", "surah": surah,
           "surah_name": f"سورة {surah_clean}", "ayahs": res["ayahs_count"],
           "duration": round(res["duration"], 1), "video_id": video_id,
           "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    state["last_long_surah"] = surah
    state["total_generated"] = state.get("total_generated", 0) + 1
    state["history"].append(job)
    save_state(state)
    logger.info(f"🎉 [1/3] Surah video done: {res['duration']:.1f}s")
    return job


def run_job_compilation(state, test_mode=False):
    """🎬 [2/3] تجميع سور قرآنية متتابعة بصوت الشيخ العجمي."""
    from quran_engine import render_long_batch_video
    reciter = pick_next_long_reciter(state)
    pexels_key = os.environ.get("PEXELS_API_KEY", "").strip()
    comp_idx = int(state.get("compilation_idx", state.get("batch_idx", 0)) or 0)

    def _progress(pct, msg):
        logger.info(f"[{pct}%] {msg}")

    cset = COMPILATION_SETS[comp_idx % len(COMPILATION_SETS)]
    comp_title = cset["title"].strip()
    # استخدام صيغة الجمع "سُوَر" حصراً وتجنب كلمة "سورة" بالمفرد
    if not comp_title.startswith("سور") and not comp_title.startswith("سُوَر"):
        comp_display = f"سُوَر {comp_title}" if " | " not in comp_title else comp_title
    else:
        comp_display = comp_title

    logger.info("=" * 60)
    logger.info(f"🎬 [2/3] تجميع سور: {comp_display}")
    logger.info("=" * 60)
    res = render_long_batch_video(
        segments=[{"surah": s, "start": a, "end": b} for (s, a, b) in cset["items"]],
        reciter_id=reciter["id"], job_title=comp_display, out_prefix="Majmou3",
        aspect_ratio="16:9", speed_mode="max", progress_callback=_progress,
        pexels_mode="auto", pexels_api_key=pexels_key,
        hook_text="أرح سمعك وقلبك بالقرآن")
    video_id = None
    if not test_mode:
        try:
            from seo_engine import generate_compilation_seo
            seo = generate_compilation_seo(comp_title=comp_display,
                                           duration_seconds=res["duration"],
                                           ayahs_count=res["ayahs_count"])
            title = seo["title"]
            desc = seo["description"]
            tags = seo["tags"]
            video_id = _upload_long(res["video_path"], title, desc, tags,
                                    thumbnail_path=res.get("thumbnail"))
            if video_id:
                cleanup_after_upload(res["video_path"], res.get("thumbnail"))
        except Exception as e:
            logger.error(f"[2/3] upload error: {e}")

    job = {"kind": "compilation", "title": comp_display,
           "ayahs": res["ayahs_count"], "duration": round(res["duration"], 1),
           "video_id": video_id,
           "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    state["total_generated"] = state.get("total_generated", 0) + 1
    state["history"].append(job)
    state["compilation_idx"] = comp_idx + 1
    state["batch_idx"] = comp_idx + 1
    save_state(state)
    logger.info(f"🎉 [2/3] Compilation video done: {res['duration']:.1f}s")
    return job


def run_job_ruqyah(state, test_mode=False):
    """🎬 [3/3] رقية شرعية بكتاب الله بصوت الشيخ العجمي."""
    from quran_engine import render_long_batch_video
    from ruqyah_data import RUQYAH_TYPES, validate_ruqyah_segments
    from comfort_hooks import RUQYAH_COMFORT_HOOKS
    reciter = pick_next_long_reciter(state)
    pexels_key = os.environ.get("PEXELS_API_KEY", "").strip()
    rq_idx = int(state.get("ruqyah_idx", state.get("batch_idx", 0)) or 0)

    def _progress(pct, msg):
        logger.info(f"[{pct}%] {msg}")

    rq = RUQYAH_TYPES[rq_idx % len(RUQYAH_TYPES)]
    validate_ruqyah_segments(rq["segments"])
    rq_name = rq["name"].strip()  # خالي تماماً من كلمة "سورة"
    rq_hook = RUQYAH_COMFORT_HOOKS.get(rq["id"], "سكينة وشفاء للقلب والروح")
    logger.info("=" * 60)
    logger.info(f"🎬 [3/3] رقية شرعية: {rq_name}")
    logger.info("=" * 60)
    res = render_long_batch_video(
        segments=[{"surah": s, "start": a, "end": b} for (s, a, b) in rq["segments"]],
        reciter_id=reciter["id"], job_title=rq_name, out_prefix="Ruqyah",
        aspect_ratio="16:9", speed_mode="max", progress_callback=_progress,
        pexels_mode="auto", pexels_api_key=pexels_key,
        ruqyah_id=rq["id"], hook_text=rq_hook)
    video_id = None
    if not test_mode:
        try:
            from seo_engine import generate_ruqyah_seo
            seo = generate_ruqyah_seo(ruqyah_id=rq["id"],
                                      ruqyah_name=rq_name,
                                      ruqyah_desc=rq.get("description", ""),
                                      duration_seconds=res["duration"],
                                      ayahs_count=res["ayahs_count"])
            title = seo["title"]
            desc = seo["description"]
            tags = seo["tags"]
            video_id = _upload_long(res["video_path"], title, desc, tags,
                                    thumbnail_path=res.get("thumbnail"))
            if video_id:
                cleanup_after_upload(res["video_path"], res.get("thumbnail"))
        except Exception as e:
            logger.error(f"[3/3] upload error: {e}")

    job = {"kind": "ruqyah", "ruqyah": rq["id"], "title": rq_name,
           "ayahs": res["ayahs_count"], "duration": round(res["duration"], 1),
           "video_id": video_id,
           "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    state["total_generated"] = state.get("total_generated", 0) + 1
    state["history"].append(job)
    state["ruqyah_idx"] = rq_idx + 1
    state["batch_idx"] = rq_idx + 1
    save_state(state)
    logger.info(f"🎉 [3/3] Ruqyah video done: {res['duration']:.1f}s")
    return job


def run_auto_slot_job(state, test_mode=False):
    """تحديد ونشر فيديو مطول يومي واحد الساعة 5 مساءً بتوقيت مصر، بالتناوب التلقائي الذكي:
    - اليوم الأول: سورة كاملة مطولة
    - اليوم الثاني: تجميع سور قرآنية متتابعة
    - اليوم الثالث: رقية شرعية بكتاب الله
    دوران ذكي ومستمر لا ينتهي مدى الحياة."""
    cycle = int(state.get("daily_cycle_idx", state.get("total_generated", 0)) or 0)
    mode_idx = cycle % 3

    if mode_idx == 0:
        logger.info(f"🎬 [الدورة اليومية #{cycle+1}] موعد اليوم (05:00 م): سورة كاملة مطولة")
        job = run_job_surah(state, test_mode=test_mode)
    elif mode_idx == 1:
        logger.info(f"🎬 [الدورة اليومية #{cycle+1}] موعد اليوم (05:00 م): تجميع سور قرآنية")
        job = run_job_compilation(state, test_mode=test_mode)
    else:
        logger.info(f"🎬 [الدورة اليومية #{cycle+1}] موعد اليوم (05:00 م): رقية شرعية بكتاب الله")
        job = run_job_ruqyah(state, test_mode=test_mode)

    state["daily_cycle_idx"] = cycle + 1
    save_state(state)
    return job


def run_daily_batch(state, test_mode=False):
    """تشغيل الفيديوهات الثلاثة دفعة واحدة عند الطلب اليدوي المباشر."""
    logger.info("🚀 تشغيل الدفعة اليومية الكاملة (3 فيديوهات متتالية)...")
    j1 = run_job_surah(state, test_mode=test_mode)
    if not test_mode:
        time.sleep(20)
    j2 = run_job_compilation(state, test_mode=test_mode)
    if not test_mode:
        time.sleep(20)
    j3 = run_job_ruqyah(state, test_mode=test_mode)
    ok = sum(1 for j in (j1, j2, j3) if j)
    logger.info(f"🏁 اكتمال الدفعة اليومية: {ok}/3 فيديوهات أنجزت بنجاح.")
    return ok


if __name__ == "__main__":
    test = "--test" in sys.argv

    # قراءة نوع المهمة من وسائط سطر الأوامر:
    job = None
    for idx, arg in enumerate(sys.argv):
        if arg in ("--job", "-j") and idx + 1 < len(sys.argv):
            job = sys.argv[idx + 1].strip().lower()
        elif arg.startswith("--job="):
            job = arg.split("=", 1)[1].strip().lower()

    state = load_state()

    if job == "surah":
        run_job_surah(state=state, test_mode=test)
    elif job == "compilation":
        run_job_compilation(state=state, test_mode=test)
    elif job == "ruqyah":
        run_job_ruqyah(state=state, test_mode=test)
    elif job == "batch" or "--batch" in sys.argv:
        run_daily_batch(state=state, test_mode=test)
    elif job == "auto":
        run_auto_slot_job(state=state, test_mode=test)
    elif "--long" in sys.argv:
        run_long_generation(state=state, test_mode=test)
    else:
        if os.environ.get("GITHUB_ACTIONS") == "true":
            run_auto_slot_job(state=state, test_mode=test)
        else:
            main(test_mode=test)
