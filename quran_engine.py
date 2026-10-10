# -*- coding: utf-8 -*-
"""
Quran Video Engine - High Performance & Vintage Aesthetics
Supports Full Surah generation & custom Ayah ranges.
Features 60s/70s Golden Era visual filters, local background library,
Arabic typography via Pillow, and high-speed FFmpeg compositing.
"""

import os
import sys
import json
import time
import random
import logging
import datetime
import socket
import subprocess
from pathlib import Path

# --- Same IPv6 fix as the uploader: broken IPv6 on WE/Etisalat routers hangs
# all downloads (EveryAyah, mp3quran, alquran.cloud). Force IPv4-first. ---
try:
    _orig_getaddrinfo = socket.getaddrinfo

    def _ipv4_first_getaddrinfo(*args, **kwargs):
        try:
            responses = _orig_getaddrinfo(*args, **kwargs)
            return sorted(responses, key=lambda r: r[0] != socket.AF_INET)
        except Exception:
            return _orig_getaddrinfo(*args, **kwargs)

    socket.getaddrinfo = _ipv4_first_getaddrinfo
except Exception:
    pass

from PIL import Image, ImageDraw, ImageFont

# Compatibility with Pillow 10+
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

import requests
import arabic_reshaper
from bidi.algorithm import get_display

from quran_data import (
    SURAH_NAMES, VERSE_COUNTS, is_makki, get_reciter_by_id,
    get_islamic_ayah_edition, ayah_global_number,
)

logger = logging.getLogger(__name__)

# Base Directories (exe-aware: uses the project folder with templates+fonts,
# whether running as script or as frozen QuranStudio.exe inside dist/)
ENGINE_VERSION = "5.5"
def _find_engine_base():
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).parent.resolve()
        # exe lives at dist/QuranStudio/ -> project root is 2 levels up; search upward
        for cand in (exe_dir, *list(exe_dir.parents)[:4]):
            if (cand / "templates").is_dir() and (cand / "fonts").is_dir():
                return cand
        return exe_dir
    return Path(__file__).parent.resolve()

ENGINE_DIR = _find_engine_base()
FONTS_DIR = ENGINE_DIR / "fonts"
BACKGROUNDS_DIR = ENGINE_DIR / "backgrounds"
THUMBNAILS_DIR = BACKGROUNDS_DIR / "thumbnails"
OUTPUTS_DIR = ENGINE_DIR / "outputs"
AUDIO_CACHE_DIR = OUTPUTS_DIR / "audio"
VIDEO_OUT_DIR = OUTPUTS_DIR / "video"

# Tracked FFmpeg process so closing the app ALWAYS kills rendering too (no zombies).
_CURRENT_FFMPEG_PROC = None

def kill_current_ffmpeg():
    """Terminates any running FFmpeg render immediately."""
    global _CURRENT_FFMPEG_PROC
    proc = _CURRENT_FFMPEG_PROC
    _CURRENT_FFMPEG_PROC = None
    if proc is None:
        return
    try:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
            logger.info("FFmpeg render terminated with app shutdown.")
    except Exception:
        pass

BACKGROUNDS_DIR.mkdir(parents=True, exist_ok=True)
THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_OUT_DIR.mkdir(parents=True, exist_ok=True)

# Arabic Reshaper Configuration
_reshaper_config = {
    'delete_harakat': False,
    'support_ligatures': True,
    'support_tashkeel': True,
}
_reshaper = arabic_reshaper.ArabicReshaper(configuration=_reshaper_config)

ARABIC_DIGITS = {'0': '٠', '1': '١', '2': '٢', '3': '٣', '4': '٤', '5': '٥', '6': '٦', '7': '٧', '8': '٨', '9': '٩'}
def to_arabic_digits(n):
    return ''.join(ARABIC_DIGITS.get(d, d) for d in str(n))

# --- Tofu-killer: no more empty squares on video ---
# Some decorative chars (emoji, dingbats) have NO glyph in Arabic fonts and render as boxes.
# Verified against Amiri-Bold cmap: ❖(2756) NO, mic/palms emoji NO | ۞ ۝ • ﴾ ، – YES.
SAFE_REPLACEMENTS = {
    '🎙️': '•', '🎙': '•', '🤲': '', '❖': '•', '✨': '•', '🌿': '•',
    '🕊️': '•', '🕊': '•', '📻': '•', '📜': '•', '🌫️': '•', '📽️': '•',
    '🤍': '•', '❤️': '•', '♥': '•', '★': '•', '☆': '•', '✦': '•', '✧': '•',
}
_VS_CHARS = set(chr(c) for c in list(range(0xFE00, 0xFE10)) + [0x200D, 0xFFFC])
_CMAP_CACHE = {}

def _font_cmap(font_path):
    """Cached set of supported codepoints for a font (None if fontTools missing)."""
    if font_path in _CMAP_CACHE:
        return _CMAP_CACHE[font_path]
    cmap = None
    try:
        from fontTools.ttLib import TTFont
        cmap = set(TTFont(font_path).getBestCmap().keys())
    except Exception as e:
        logger.warning(f"cmap check unavailable for {font_path}: {e}")
    _CMAP_CACHE[font_path] = cmap
    return cmap

def sanitize_for_font(text, font_path):
    """Replaces/drops chars the font cannot render so NO tofu boxes ever appear."""
    if not text:
        return ""
    for bad, good in SAFE_REPLACEMENTS.items():
        text = text.replace(bad, good)
    text = ''.join(c for c in text if c not in _VS_CHARS)
    cmap = _font_cmap(font_path) if font_path else None
    if cmap is None:
        return text
    out = []
    for c in text:
        o = ord(c)
        if o < 128 or o in cmap:
            out.append(c)
        # else: drop silently (would render as an empty square)
    cleaned = ''.join(out)
    # collapse gaps left by dropped chars
    cleaned = ' '.join(cleaned.split())
    return cleaned

def reshape_text(text, font_path=None):
    """Format Arabic text with proper ligatures and RTL ordering.
    When font_path is given, unsupported glyphs are sanitized first (no tofu boxes)."""
    if not text:
        return ""
    if font_path:
        text = sanitize_for_font(text, font_path)
        if not text:
            return ""
    try:
        reshaped = _reshaper.reshape(text)
        return get_display(reshaped)
    except Exception:
        return text

def wrap_and_reshape(text, words_per_line=6, font_path=None):
    if not text:
        return ""
    words = text.split()
    lines = [' '.join(words[i:i + words_per_line]) for i in range(0, len(words), words_per_line)]
    return '\n'.join([reshape_text(l, font_path=font_path) for l in lines])

def get_best_font():
    # NOTE: AmiriQuran-Regular.ttf in this repo is 0 bytes (corrupt) -> auto-skipped by size check.
    # Also supports root font.ttf fallback.
    candidates = ["Amiri-Bold.ttf", "DUBAI-BOLD.TTF", "DUBAI-MEDIUM.TTF", "AmiriQuran-Regular.ttf"]
    for fn in candidates:
        p = FONTS_DIR / fn
        if p.exists() and p.stat().st_size > 10000:
            return str(p)
    root_font = ENGINE_DIR / "font.ttf"
    if root_font.exists() and root_font.stat().st_size > 10000:
        return str(root_font)
    return "arial.ttf"

VIDEO_EXTS = ('.mp4', '.mov', '.mkv', '.avi', '.webm')
IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.webp', '.bmp')

def is_image_background(path_str):
    return Path(path_str).suffix.lower() in IMAGE_EXTS

def pick_background_smart(bg_video_filename=None):
    """Universal picker: any video OR image works. Random fallback (not always first)."""
    if bg_video_filename:
        target = BACKGROUNDS_DIR / Path(bg_video_filename).name
        if target.exists() and target.is_file():
            return str(target)
        # also accept absolute path inside project
        alt = Path(str(bg_video_filename))
        if alt.exists() and alt.is_file():
            return str(alt)
        logger.warning(f"Requested background '{bg_video_filename}' not found, picking random instead.")
    all_bgs = get_local_backgrounds()
    if all_bgs:
        chosen = random.choice(all_bgs)
        return chosen['path']
    raise RuntimeError("لا توجد خلفيات في مجلد backgrounds! ضع فيديو mp4 أو صورة jpg/png واحدة على الأقل.")

def analyze_background_mood(bg_path):
    """Smart mood matching: analyzes first frame brightness/contrast and picks vintage effect.
    Dark night -> fog, bright warm -> sepia, mid -> black_and_white classic, very bright -> grain_vignette.
    Never fails: returns 'black_and_white' on any error."""
    try:
        thumb = AUDIO_CACHE_DIR / "mood_probe.jpg"
        cmd = ["ffmpeg", "-y", "-ss", "00:00:01", "-i", str(bg_path),
               "-vframes", "1", "-vf", "scale=160:-1", str(thumb)]
        # image backgrounds: no seek needed
        if is_image_background(str(bg_path)):
            cmd = ["ffmpeg", "-y", "-i", str(bg_path),
                   "-vframes", "1", "-vf", "scale=160:-1", str(thumb)]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        if not thumb.exists():
            return "black_and_white"
        with Image.open(str(thumb)).convert("L") as im:
            import statistics
            px = list(im.getdata())
            if not px:
                return "black_and_white"
            mean = sum(px) / len(px)
            stdev = statistics.pstdev(px) if len(px) > 1 else 0
        # Heuristics tuned for nature backgrounds
        if mean < 60:
            return "fog"            # dark night -> dreamy mist glow
        if mean > 150 and stdev < 55:
            return "sepia"          # bright flat daylight -> warm archival
        if stdev > 70:
            return "grain_vignette" # high contrast scenery -> film look
        return "black_and_white"    # classic default
    except Exception as e:
        logger.warning(f"Mood analysis failed ({e}), using classic B&W")
        return "black_and_white"

def build_audio_mood_filter(vintage_effect, duration):
    """CLEAN broadcast audio: loudness normalization + gentle fades only.
    No coloration, no echo - pure recitation exactly as recorded."""
    try:
        dur = max(5.0, float(duration))
    except Exception:
        dur = 60.0
    fade_out_start = max(0.0, dur - 2.0)
    return (f"aresample=44100,loudnorm=I=-16:TP=-1.5:LRA=11,"
            f"afade=t=in:st=0:d=1,afade=t=out:st={fade_out_start:.2f}:d=2")

def get_local_backgrounds():
    """Scans backgrounds directory (videos AND images) and creates thumbnails if missing."""
    supported = VIDEO_EXTS + IMAGE_EXTS
    bg_files = []
    
    for f in BACKGROUNDS_DIR.iterdir():
        if f.is_file() and f.suffix.lower() in supported:
            thumb_name = f"{f.stem}.jpg"
            thumb_path = THUMBNAILS_DIR / thumb_name
            
            # Generate thumbnail if not present (video: seek 1s, image: direct)
            if not thumb_path.exists():
                try:
                    if f.suffix.lower() in IMAGE_EXTS:
                        cmd = [
                            "ffmpeg", "-y", "-i", str(f),
                            "-vframes", "1", "-vf", "scale=360:-1", str(thumb_path)
                        ]
                    else:
                        cmd = [
                            "ffmpeg", "-y", "-ss", "00:00:01", "-i", str(f),
                            "-vframes", "1", "-vf", "scale=360:-1", str(thumb_path)
                        ]
                    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
                except Exception as e:
                    logger.warning(f"Failed to generate thumbnail for {f.name}: {e}")
            
            # File size in MB
            size_mb = round(f.stat().st_size / (1024 * 1024), 1)
            
            bg_files.append({
                'filename': f.name,
                'path': str(f),
                'thumbnail': f"/thumbnails/{thumb_name}" if thumb_path.exists() else None,
                'size_mb': size_mb
            })
            
    return bg_files

def try_download_sources(urls, target_path, timeout_each=90, progress_hook=None, on_source_change=None):
    """Universal fast-fail source chain: tries each URL ONCE and moves on.

    - A 404/dead mirror fails in seconds instead of burning retries.
    - The program only gives up after EVERY source fails.
    Raises RuntimeError with an Arabic summary if all sources fail.
    """
    urls = [u for u in (urls or []) if u]
    if not urls:
        raise RuntimeError("لا توجد مصادر تحميل متاحة")
    last_err = None
    for idx, url in enumerate(urls, start=1):
        if on_source_change:
            try:
                on_source_change(idx, len(urls), url)
            except Exception:
                pass
        try:
            download_file(url, target_path, timeout=timeout_each, retries=1,
                          progress_hook=progress_hook)
            if Path(target_path).exists() and Path(target_path).stat().st_size >= 10000:
                if idx > 1:
                    logger.info(f"Backup source {idx}/{len(urls)} worked")
                return str(target_path)
            raise RuntimeError("ملف ناقص من المصدر")
        except Exception as e:
            last_err = e
            logger.warning(f"Source {idx}/{len(urls)} failed: {str(e)[:150]}")
            try:
                if Path(target_path).exists():
                    Path(target_path).unlink()
            except Exception:
                pass
    raise RuntimeError(f"تعذر التحميل من كل المصادر ({len(urls)} مصادر): {last_err}")


def download_file(url, target_path, timeout=180, retries=3, progress_hook=None):
    """Download file with streaming, retries and error handling.
    progress_hook(downloaded_mb, total_mb_or_None) is called periodically for big files."""
    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, stream=True, timeout=timeout)
            resp.raise_for_status()
            total = resp.headers.get("content-length")
            try:
                total_mb = round(int(total) / (1024 * 1024), 1) if total else None
            except Exception:
                total_mb = None
            downloaded = 0
            last_report = 0
            with open(target_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_hook and downloaded - last_report >= 2 * 1024 * 1024:
                            last_report = downloaded
                            try:
                                progress_hook(round(downloaded / (1024 * 1024), 1), total_mb)
                            except Exception:
                                pass
            if Path(target_path).stat().st_size < 10000:
                raise RuntimeError("Downloaded file too small, likely failed")
            return target_path
        except Exception as e:
            last_err = e
            logger.warning(f"Download attempt {attempt+1}/{retries} failed for {url}: {e}")
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Download failed after {retries} attempts: {url} ({last_err})")

def get_audio_duration(audio_path):
    """Get accurate audio duration using ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(res.stdout.strip())
    except Exception as e:
        logger.error(f"Error reading audio duration: {e}")
        return 60.0

def fetch_full_surah_audio(reciter, surah_num, progress_cb=None):
    """Downloads the full Surah as ONE complete MP3 file (never ayah-by-ayah for long videos).

    Strategy:
      1. Memory cache (already downloaded before).
      2. Refaat guard: his historical recordings cover only 31 surahs -> friendly error.
      3. Primary server (mp3quran) with live MB progress.
      4. Verified mirror servers, one by one.
      5. LAST resort: ayah stitching ONLY for short surahs (<=12 ayahs).
         Long surahs raise a clear error instead of hanging on hundreds of downloads.
    """
    from quran_data import REFAAT_SURAHS

    surah_name = SURAH_NAMES[surah_num - 1]
    filename = f"{reciter['id']}_surah_{surah_num:03d}.mp3"
    target_path = AUDIO_CACHE_DIR / filename

    if target_path.exists() and target_path.stat().st_size > 50000:
        if progress_cb:
            progress_cb(15, f"تم العثور على تلاوة سورة {surah_name} كاملة في الذاكرة المؤقتة")
        return str(target_path)

    # --- Refaat guard: limited historical catalog, and range-stitching would use the WRONG voice ---
    if reciter.get('id') == 'mohamed_refaat' and surah_num not in REFAAT_SURAHS:
        raise RuntimeError(
            f"تسجيلات الشيخ محمد رفعت التاريخية متاحة لـ 31 سورة فقط، وسورة {surah_name} ليست منها. "
            f"اختر سورة من السور المتاحة (مثل: الفاتحة، الكهف، مريم، طه، النبأ) أو اختر قارئاً آخر للسور الطويلة."
        )

    def hook(dl_mb, total_mb):
        if progress_cb:
            info = f"{dl_mb}MB" + (f" / {total_mb}MB" if total_mb else "")
            progress_cb(12, f"جاري تحميل سورة {surah_name} كاملة ملف واحد ({info})...")

    candidates = [f"{reciter['full_surah_server']}{surah_num:03d}.mp3"]
    for m in reciter.get('mirrors', []) or []:
        try:
            candidates.append(m.format(n=surah_num, n03=f"{surah_num:03d}"))
        except Exception:
            continue
    # Automatic extra mirror: same reciter on islamic.network full-surah CDN
    try:
        _ed = get_islamic_ayah_edition(reciter.get('id', ''))
        if _ed:
            candidates.append(f"https://cdn.islamic.network/quran/audio/128/{_ed}/{surah_num}.mp3")
    except Exception:
        pass

    if progress_cb:
        progress_cb(10, f"جاري تحميل تلاوة سورة {surah_name} كاملة ملف واحد بصوت {reciter['name']}...")

    try:
        def _src(i, n, u):
            if progress_cb and n > 1:
                progress_cb(11, f"جاري التحميل من المصدر {i} من {n} لسورة {surah_name}...")
        try_download_sources(candidates, target_path, timeout_each=90,
                             progress_hook=hook, on_source_change=_src)
        if progress_cb:
            progress_cb(20, "اكتمل تحميل التلاوة الصوتية المباركة كاملة")
        return str(target_path)
    except Exception as e:
        # LAST RESORT (any length): stitch ayah-by-ayah from backup mirrors.
        # Slow for long surahs, but the program NEVER dies because of audio.
        logger.warning(f"All whole-file sources failed ({e}), stitching ayah-by-ayah...")
        if progress_cb:
            progress_cb(12, "المصادر الكاملة تعذرت، جاري تجميع التلاوة آية آية من مصادر بديلة (قد يستغرق وقتاً أطول)...")
        return download_and_stitch_ayahs(reciter, surah_num, 1, VERSE_COUNTS[surah_num],
                                         progress_cb, allow_long=True)

def download_ayah_audio(reciter, surah_num, ayah_num, target_path):
    """Downloads ONE ayah MP3 with automatic source fallback.

    1. EveryAyah (primary, per-reciter folder).
    2. cdn.islamic.network ayah audio (global ayah number) when the reciter
       has a mapped edition - covers cases like Ajamy whose EveryAyah
       folder was removed (404).

    Raises a clear Arabic RuntimeError only if ALL sources fail.
    """
    surah_num, ayah_num = int(surah_num), int(ayah_num)
    candidates = []
    everyayah_id = reciter.get('everyayah_id', 'Minshawy_Mujawwad_64kbps')
    fn = f'{surah_num:03d}{ayah_num:03d}.mp3'
    candidates.append(f'https://everyayah.com/data/{everyayah_id}/{fn}')
    edition = get_islamic_ayah_edition(reciter.get('id', ''))
    if edition:
        g = ayah_global_number(surah_num, ayah_num)
        candidates.append(f'https://cdn.islamic.network/quran/audio/128/{edition}/{g}.mp3')

    last_err = None
    try:
        return try_download_sources(candidates, target_path, timeout_each=60)
    except Exception as e:
        last_err = e
    raise RuntimeError(
        f"تعذر تحميل صوت الآية {ayah_num} من سورة {SURAH_NAMES[surah_num-1]} "
        f"بصوت {reciter.get('name', '')} من كل المصادر ({last_err}). "
        f"تحقق من الإنترنت ثم أعد المحاولة، أو جرّب قارئاً آخر (الحصري / المنشاوي / العفاسي)."
    )


def download_and_stitch_ayahs(reciter, surah_num, start_ayah, end_ayah, progress_cb=None, allow_long=False):
    """Downloads a SHORT range of Ayahs and stitches them seamlessly with silence trimming.
    Ayah-by-ayah is ONLY for shorts/small clips. Long ranges are refused with guidance
    to use full-surah mode (one complete file) instead of hanging on hundreds of downloads.
    allow_long=True is reserved for the full-surah LAST-RESORT fallback (never-die mode)."""
    from pydub import AudioSegment

    # Refaat guard: his everyayah mapping is another reciter's voice -> block wrong-voice output
    if reciter.get('id') == 'mohamed_refaat':
        raise RuntimeError(
            "الشيخ محمد رفعت متاح بوضع السورة الكاملة فقط (تسجيلاته التاريخية 31 سورة). "
            "اختر وضع السورة الكاملة أو قارئاً آخر للمقاطع."
        )

    total = end_ayah - start_ayah + 1
    if total > 40 and not allow_long:
        raise RuntimeError(
            f"المقطع المطلوب كبير جداً ({total} آية). وضع الآيات مخصص للشورتس والمقاطع الصغيرة فقط. "
            f"للفيديوهات الطويلة اختر وضع السورة الكاملة الذي يحمّل ملفاً واحداً كاملاً."
        )
    combined_audio = AudioSegment.empty()
    everyayah_id = reciter.get('everyayah_id', 'Minshawy_Mujawwad_64kbps')
    
    for idx, ayah in enumerate(range(start_ayah, end_ayah + 1), start=1):
        if progress_cb:
            p = 10 + int((idx / total) * 15)
            progress_cb(p, f"جاري تحميل صوت الآية {ayah} من سورة {SURAH_NAMES[surah_num-1]}...")

        fn = f'{surah_num:03d}{ayah:03d}.mp3'
        tmp_ayah = AUDIO_CACHE_DIR / f"temp_{everyayah_id}_{fn}"

        if not (tmp_ayah.exists() and tmp_ayah.stat().st_size > 10000):
            download_ayah_audio(reciter, surah_num, ayah, tmp_ayah)
            
        snd = AudioSegment.from_file(str(tmp_ayah), 'mp3')
        
        # Trim silence
        silence_thresh = max(-42.0, snd.dBFS - 12)
        chunk = 10
        pos = 0
        while pos < len(snd) and snd[pos:pos + chunk].dBFS < silence_thresh:
            pos += chunk
        start_trim = max(0, pos - 20)
        
        pos = len(snd)
        while pos > 0 and snd[pos - chunk:pos].dBFS < silence_thresh:
            pos -= chunk
        end_trim = min(len(snd), pos + 20)
        
        trimmed = snd[start_trim:end_trim]
        combined_audio += trimmed
        
    out_file = AUDIO_CACHE_DIR / f"stitched_{surah_num}_{start_ayah}_{end_ayah}.mp3"
    combined_audio.export(str(out_file), format='mp3', bitrate='192k')
    return str(out_file)

TEXT_CACHE_DIR = AUDIO_CACHE_DIR / "ayah_text"
_TEXT_MEM_CACHE = {}

def _text_cache_path(surah_num):
    return TEXT_CACHE_DIR / f"s{int(surah_num):03d}.json"

def _text_cache_get(surah_num, ayah_num):
    key = (int(surah_num), int(ayah_num))
    if key in _TEXT_MEM_CACHE:
        return _TEXT_MEM_CACHE[key]
    try:
        p = _text_cache_path(surah_num)
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            t = data.get(str(ayah_num), "")
            if t:
                _TEXT_MEM_CACHE[key] = t
                return t
    except Exception:
        pass
    return ""

def _text_cache_put(surah_num, ayah_num, text):
    if not text:
        return
    key = (int(surah_num), int(ayah_num))
    _TEXT_MEM_CACHE[key] = text
    try:
        TEXT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        p = _text_cache_path(surah_num)
        data = {}
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        data[str(ayah_num)] = text
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Text cache write failed: {e}")

def fetch_ayah_text(surah_num, ayah_num):
    """Fetches Uthmani ayah text with cache + backup API. NEVER crashes:
    returns '' on total failure so the overlay degrades to title mode."""
    s, a = int(surah_num), int(ayah_num)
    cached = _text_cache_get(s, a)
    if cached:
        return cached
    # 1. Primary: alquran.cloud (2 fast attempts)
    for _ in range(2):
        try:
            url = f'https://api.alquran.cloud/v1/ayah/{s}:{a}/quran-uthmani'
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            text = (resp.json().get('data') or {}).get('text', '')
            if text:
                _text_cache_put(s, a, text)
                return text
        except Exception as e:
            logger.warning(f"Ayah text primary failed ({s}:{a}): {e}")
            time.sleep(1)
    # 2. Backup: quran.com v4 Uthmani text
    try:
        url = (f'https://api.quran.com/api/v4/verses/by_key/{s}:{a}'
               f'?words=false&text_uthmani=true&translations=')
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        text = ((resp.json().get('verse') or {}).get('text_uthmani') or '').strip()
        if text:
            _text_cache_put(s, a, text)
            return text
    except Exception as e:
        logger.warning(f"Ayah text backup failed ({s}:{a}): {e}")
    logger.error(f"Ayah text unavailable ({s}:{a}), overlay will use title mode")
    return ""

def create_vintage_overlay_image(width, height, surah_num, reciter, ayah_range_text="كاملة", custom_ayah_text=None):
    """
    Creates an ultra high resolution transparent PNG overlay with
    vintage Islamic ornamental frames, Golden Era typography, and borders.
    """
    font_path = get_best_font()
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    surah_name = SURAH_NAMES[surah_num - 1]
    is_makkah = is_makki(surah_num)
    revelation_str = "مَكِّيَّة" if is_makkah else "مَدَنِيَّة"
    verses_str = f"{VERSE_COUNTS[surah_num]} آيات"
    
    # 1. Elegant Soft Vignette Darkening (to make text crystal readable)
    overlay_box = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay_box)
    
    # Center subtle dark plate
    plate_margin_x = int(width * 0.08)
    plate_margin_y = int(height * 0.12)
    overlay_draw.rounded_rectangle(
        [plate_margin_x, plate_margin_y, width - plate_margin_x, height - plate_margin_y],
        radius=24,
        fill=(10, 10, 15, 160),
        outline=(212, 175, 55, 90),
        width=2
    )
    img = Image.alpha_composite(img, overlay_box)
    draw = ImageDraw.Draw(img)
    
    # 2. Outer Ornamental Borders (Golden Era Islamic Framing)
    border_inset = int(width * 0.04)
    gold_color = (220, 185, 90, 240)
    white_color = (255, 255, 255, 255)
    cream_gold = (245, 230, 180, 255)
    
    draw.rectangle(
        [border_inset, border_inset, width - border_inset, height - border_inset],
        outline=(212, 175, 55, 180),
        width=2
    )
    draw.rectangle(
        [border_inset + 8, border_inset + 8, width - border_inset - 8, height - border_inset - 8],
        outline=(212, 175, 55, 80),
        width=1
    )
    
    # Corner Accents (Islamic Geometric Corners)
    corner_size = 40
    corners = [
        (border_inset + 14, border_inset + 14),
        (width - border_inset - 14, border_inset + 14),
        (border_inset + 14, height - border_inset - 14),
        (width - border_inset - 14, height - border_inset - 14)
    ]
    for cx, cy in corners:
        draw.regular_polygon((cx, cy, 10), n_sides=8, fill=gold_color, outline=(0, 0, 0, 180))
        
    # 3. Top Decorative Header (سورة ...)
    top_y = int(height * 0.16)
    
    font_header_sub = ImageFont.truetype(font_path, int(height * 0.026))
    header_sub_text = reshape_text(f"❖  سورة {surah_name} ({ayah_range_text})  |  {revelation_str}  |  {verses_str}  ❖", font_path=font_path)
    bbox_sub = draw.textbbox((0, 0), header_sub_text, font=font_header_sub)
    draw.text(
        ((width - (bbox_sub[2] - bbox_sub[0])) // 2, top_y),
        header_sub_text,
        font=font_header_sub,
        fill=gold_color,
        stroke_width=2,
        stroke_fill=(0, 0, 0, 220)
    )
    
    # 4. Golden Era Reciter Banner
    reciter_y = top_y + int(height * 0.045)
    font_reciter = ImageFont.truetype(font_path, int(height * 0.034))
    reciter_text = reshape_text(f"🎙️ {reciter['name']}", font_path=font_path)
    bbox_rec = draw.textbbox((0, 0), reciter_text, font=font_reciter)
    draw.text(
        ((width - (bbox_rec[2] - bbox_rec[0])) // 2, reciter_y),
        reciter_text,
        font=font_reciter,
        fill=cream_gold,
        stroke_width=3,
        stroke_fill=(0, 0, 0, 240)
    )
    
    # 5. Central Quranic Display
    # Basmalah
    basmalah_y = int(height * 0.30)
    font_basmalah = ImageFont.truetype(font_path, int(height * 0.044))
    basmalah_text = reshape_text("بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ", font_path=font_path)
    bbox_bas = draw.textbbox((0, 0), basmalah_text, font=font_basmalah)
    draw.text(
        ((width - (bbox_bas[2] - bbox_bas[0])) // 2, basmalah_y),
        basmalah_text,
        font=font_basmalah,
        fill=gold_color,
        stroke_width=3,
        stroke_fill=(0, 0, 0, 240)
    )
    
    # Divider line under Basmalah
    div_y = basmalah_y + int(height * 0.06)
    draw.line([(width * 0.3, div_y), (width * 0.7, div_y)], fill=(212, 175, 55, 140), width=2)
    draw.regular_polygon((width // 2, div_y, 6), n_sides=4, fill=gold_color)
    
    # Main Body Text
    if custom_ayah_text:
        # Wrapped Ayah verses
        words_count = len(custom_ayah_text.split())
        words_per_line = 5 if width > height else 4
        font_size = int(height * 0.042) if words_count < 30 else int(height * 0.034)
        font_body = ImageFont.truetype(font_path, font_size)
        
        wrapped_ayah = wrap_and_reshape(custom_ayah_text, words_per_line=words_per_line, font_path=font_path)
        body_y = int(height * 0.42)
        
        bbox_body = draw.multiline_textbbox((0, 0), wrapped_ayah, font=font_body, spacing=18, align='center')
        draw.multiline_text(
            ((width - (bbox_body[2] - bbox_body[0])) // 2, body_y),
            wrapped_ayah,
            font=font_body,
            fill=white_color,
            spacing=18,
            align='center',
            stroke_width=3,
            stroke_fill=(0, 0, 0, 240)
        )
    else:
        # Full Surah Classical Archival Gateway
        center_y = int(height * 0.44)
        font_main_title = ImageFont.truetype(font_path, int(height * 0.065))
        surah_title_text = reshape_text(f"سُورَةُ {surah_name}", font_path=font_path)
        bbox_title = draw.textbbox((0, 0), surah_title_text, font=font_main_title)
        draw.text(
            ((width - (bbox_title[2] - bbox_title[0])) // 2, center_y),
            surah_title_text,
            font=font_main_title,
            fill=white_color,
            stroke_width=4,
            stroke_fill=(0, 0, 0, 240)
        )
        
        font_quote = ImageFont.truetype(font_path, int(height * 0.030))
        quote_text = reshape_text("تِلَاوَةٌ خَاشِعَةٌ مُبَارَكَةٌ مِنَ الزَّمَنِ الجَمِيلِ", font_path=font_path)
        bbox_quote = draw.textbbox((0, 0), quote_text, font=font_quote)
        draw.text(
            ((width - (bbox_quote[2] - bbox_quote[0])) // 2, center_y + int(height * 0.09)),
            quote_text,
            font=font_quote,
            fill=cream_gold,
            stroke_width=2,
            stroke_fill=(0, 0, 0, 220)
        )
        
        font_tag = ImageFont.truetype(font_path, int(height * 0.024))
        tag_text = reshape_text("۞  اسْتَمِعْ وَتَدَبَّرْ كَلَامَ رَبِّ العَالَمِينَ  ۞", font_path=font_path)
        bbox_tag = draw.textbbox((0, 0), tag_text, font=font_tag)
        draw.text(
            ((width - (bbox_tag[2] - bbox_tag[0])) // 2, center_y + int(height * 0.15)),
            tag_text,
            font=font_tag,
            fill=(255, 255, 255, 200),
            stroke_width=2,
            stroke_fill=(0, 0, 0, 200)
        )

    # 6. Bottom Continuous Charity Banner
    bottom_y = int(height * 0.83)
    font_bottom = ImageFont.truetype(font_path, int(height * 0.026))
    bottom_text = reshape_text("صَدَقَةٌ جَارِيَةٌ لِوَجْهِ اللَّهِ تَعَالَى 🤲 نَسْأَلُكُمُ الدُّعَاءَ بِالمَغْفِرَةِ وَالرَّحْمَةِ", font_path=font_path)
    bbox_bot = draw.textbbox((0, 0), bottom_text, font=font_bottom)
    draw.text(
        ((width - (bbox_bot[2] - bbox_bot[0])) // 2, bottom_y),
        bottom_text,
        font=font_bottom,
        fill=gold_color,
        stroke_width=2,
        stroke_fill=(0, 0, 0, 220)
    )

    out_path = AUDIO_CACHE_DIR / f"overlay_{surah_num}_{width}x{height}.png"
    img.save(str(out_path), "PNG")
    return str(out_path)

# Intro overlay timing: text/frames appear ONLY in the first seconds,
# fade in gently like light turning on, fade out with soft mist like light turning off,
# then the video stays 100% clean and moving for pure listening comfort.
INTRO_FULL_SEC = 5.0

def build_intro_fade_filter(duration):
    """Computes overlay fade in/out times so the intro disappears softly within ~5 seconds.
    Long videos: visible 0-4.5s (in 1s, out 2.5-4.5s). Short videos: adapted proportionally."""
    try:
        dur = max(4.0, float(duration))
    except Exception:
        dur = 60.0
    if dur <= 7:
        fade_in = 0.8
        t_out = max(1.2, dur * 0.3)
        d_out = max(0.8, dur - t_out - 0.3)
    elif dur <= 12:
        fade_in = 1.0
        t_out = max(1.5, dur - 3.5)
        d_out = max(1.0, dur - t_out - 0.3)
    else:
        fade_in = 1.0
        t_out = 2.5
        d_out = 2.0                    # fully gone by 4.5s
    # Safety clamp
    if t_out + d_out > dur - 0.2:
        d_out = max(0.8, dur - t_out - 0.2)
    return fade_in, t_out, d_out

def build_ffmpeg_filter(aspect_ratio, vintage_effect, bg_is_image=False, duration=60.0):
    """
    CLEAN pipeline (user choice): NO vintage filters at all - pure clean video.
    Only technical normalization remains: scaling, fps, pixel format.
    vintage_effect is accepted but ignored (kept for backward compatibility).
    """
    width, height = (1920, 1080) if aspect_ratio == "16:9" else (1080, 1920)

    if bg_is_image:
        # Still image -> slow living drift so the frame is ALWAYS alive (no filter, just motion)
        filters = [
            f"scale=w={int(width * 1.18)}:h={int(height * 1.18)}:force_original_aspect_ratio=increase",
            f"crop={width}:{height}:x='(in_w-{width})/2+(in_w-{width})/2*sin(2*PI*n/900)':y='(in_h-{height})/2+(in_h-{height})/2*cos(2*PI*n/900)'",
            "fps=30",
            "format=yuv420p"
        ]
    else:
        filters = [
            f"scale=w={width}:h={height}:force_original_aspect_ratio=increase",
            f"crop={width}:{height}",
            "fps=30",
            "format=yuv420p"
        ]

    filter_chain = ",".join(filters)
    return filter_chain, width, height

# --- Max-speed mode: Intel Quick Sync (QSV) hardware encoding ---
# Benchmarked on this machine (1080p vintage filters): QSV 2.7s vs x264 7.7s per 10s (~2.9x).
# Quality locked via global_quality 20 (same visual league as x264 CRF 20). Safe fallback to x264.
_HW_QSV_OK = None

def is_qsv_available():
    """Cached probe: can this machine encode h264_qsv? (~2s first call, instant after)."""
    global _HW_QSV_OK
    if _HW_QSV_OK is not None:
        return _HW_QSV_OK
    try:
        probe_out = AUDIO_CACHE_DIR / "_qsv_probe.mp4"
        cmd = ["ffmpeg", "-y", "-v", "error",
               "-f", "lavfi", "-i", "color=c=black:s=320x240:d=1:r=15",
               "-c:v", "h264_qsv", "-preset", "veryfast", "-global_quality", "23",
               str(probe_out)]
        r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        _HW_QSV_OK = (r.returncode == 0 and probe_out.exists() and probe_out.stat().st_size > 1000)
    except Exception:
        _HW_QSV_OK = False
    try:
        if probe_out.exists():
            probe_out.unlink()
    except Exception:
        pass
    logger.info(f"QSV hardware encoder available: {_HW_QSV_OK}")
    return _HW_QSV_OK

def build_video_codec_args(speed_mode):
    """Returns (ffmpeg_video_args, label).
    - max: QSV hardware (same visual quality, ~3x faster); CPU-ultrafast fallback if no QSV.
    - balanced: classic x264 veryfast CRF20."""
    if speed_mode == "max" and is_qsv_available():
        return (["-c:v", "h264_qsv", "-preset", "veryfast", "-global_quality", "20"],
                "تسريع العتاد QSV (سرعة قصوى + جودة عالية)")
    if speed_mode == "max":
        return (["-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-threads", "0"],
                "أسرع وضع CPU (ملف أكبر قليلاً + نفس الجودة)")
    return (["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-threads", "0"],
            "وضع متوازن سينمائي")

def render_quran_video(
    surah_num,
    reciter_id,
    mode="full",
    start_ayah=1,
    end_ayah=7,
    bg_video_filename=None,
    aspect_ratio="16:9",
    vintage_effect="black_and_white",
    speed_mode="max",
    progress_callback=None,
    caption_mode="sync",
    pexels_mode="auto",
    pexels_api_key=None
):
    """
    Main orchestration function to render the complete video using FFmpeg.

    caption_mode:
      - "sync"  (الافتراضي): المحرك الموحّد القوي - نصوص الآيات بالرسم العثماني
                 تظهر متزامنة مع التلاوة + خلفيات Pexels تلقائياً (السور الكاملة).
      - "intro" : المحرك الكلاسيكي - إطار ذهبي في أول 5 ثوانٍ ثم فيديو صافي.
    """
    # المحرك الموحّد القوي (الدمج الكامل لمحرك الريلز داخل الفيديو الطويل)
    if caption_mode == "sync":
        return render_long_quran_video(
            surah_num=surah_num,
            reciter_id=reciter_id,
            mode=mode,
            start_ayah=start_ayah,
            end_ayah=end_ayah,
            bg_video_filename=bg_video_filename,
            aspect_ratio=aspect_ratio,
            speed_mode=speed_mode,
            progress_callback=progress_callback,
            pexels_mode=pexels_mode,
            pexels_api_key=pexels_api_key,
        )

    def update_p(percent, msg):
        if progress_callback:
            progress_callback(percent, msg)
        logger.info(f"[{percent}%] {msg}")

    update_p(5, "جاري تحضير المحرك وإعدادات التلاوة...")

    if not (1 <= surah_num <= 114):
        raise ValueError(f"رقم السورة غير صالح: {surah_num}")
    reciter = get_reciter_by_id(reciter_id)
    surah_name = SURAH_NAMES[surah_num - 1]

    # 1. Resolve Background (ANY video OR image + ANY reciter = works)
    bg_path = pick_background_smart(bg_video_filename)
    bg_is_image = is_image_background(bg_path)

    # 1b. No filters by user choice: pure clean video, any mood option maps to clean.
    vintage_effect = "none"
    mood_note = " (نقي بدون فلاتر)"

    update_p(10, f"تم اختيار الخلفية: {Path(bg_path).name}{mood_note}")
    
    # 2. Resolve Audio
    # RULE: long videos = ONE complete surah file / shorts & small clips = ayah-by-ayah.
    custom_ayah_text = None
    if mode == "full":
        audio_path = fetch_full_surah_audio(reciter, surah_num, update_p)
        ayah_range_label = "كاملة"
    else:
        max_v = VERSE_COUNTS[surah_num]
        end_ayah = min(end_ayah, max_v)
        if end_ayah - start_ayah + 1 > 30:
            raise RuntimeError(
                f"المقطع المطلوب كبير ({end_ayah - start_ayah + 1} آية). "
                f"وضع الآيات للشورتس والمقاطع الصغيرة فقط (حتى 30 آية). "
                f"للفيديوهات الطويلة اختر وضع السورة الكاملة الذي يحمّل ملفاً واحداً كاملاً."
            )
        ayah_range_label = f"الآيات {start_ayah}-{end_ayah}"
        audio_path = download_and_stitch_ayahs(reciter, surah_num, start_ayah, end_ayah, update_p)
        # Fetch text for the verses if short range
        if end_ayah - start_ayah <= 5:
            texts = [fetch_ayah_text(surah_num, a) for a in range(start_ayah, end_ayah + 1)]
            custom_ayah_text = " ۝ ".join(filter(None, texts))

    update_p(30, "جاري احتساب مدة التلاوة الصوتية وتوليد الإطارات الإسلامية...")
    duration = get_audio_duration(audio_path)
    if duration < 3:
        raise RuntimeError("ملف الصوت الناتج تالف أو قصير جداً، أعد المحاولة")
    logger.info(f"Audio Duration: {duration:.2f}s")
    
    # 3. Create High-Res Overlay Graphic (intro only: fades in/out in first seconds)
    filter_chain, width, height = build_ffmpeg_filter(
        aspect_ratio, vintage_effect, bg_is_image=bg_is_image, duration=duration
    )
    overlay_png = create_vintage_overlay_image(
        width, height, surah_num, reciter,
        ayah_range_text=ayah_range_label,
        custom_ayah_text=custom_ayah_text
    )
    fade_in, fade_out_start, fade_out_dur = build_intro_fade_filter(duration)
    
    update_p(40, f"تم تصميم إطار الزمن الجميل ({width}x{height}) بنجاح")
    
    # 4. Generate Output Video via Native FFmpeg
    # SMART LOOP: background repeats seamlessly to EXACTLY match surah duration.
    # - video bg: -stream_loop -1 (infinite loop, cut with -t duration)
    # - image bg: -loop 1 (still image rendered as video for full duration)
    # Audio mood filter unifies sound character with image mood + broadcast loudness.
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_reciter = "".join(c for c in reciter['id'] if c.isalnum() or c in ('_', '-'))[:40]
    out_filename = f"Quran_{surah_name}_{safe_reciter}_{vintage_effect}_{timestamp}.mp4"
    out_video_path = VIDEO_OUT_DIR / out_filename

    update_p(50, f"جاري بدء المونتاج السينمائي (مقدمة 5 ثوانٍ ثم فيديو صافي متحرك لمدة {duration:.0f} ثانية)...")

    audio_filter = build_audio_mood_filter(vintage_effect, duration)

    if bg_is_image:
        input_args = ["-loop", "1", "-framerate", "30", "-i", bg_path]
    else:
        input_args = ["-stream_loop", "-1", "-i", bg_path]

    # FFmpeg command:
    # - background loops/moves for the EXACT audio duration (video loops, image drifts slowly)
    # - overlay (all text/frames) appears ONCE in the first seconds, fades out softly,
    #   then its stream is CUT OFF entirely (eof_action=pass) so it can NEVER reappear.
    overlay_fade = (
        f"format=rgba,"
        f"fade=t=in:st=0:d={fade_in:.1f}:alpha=1,"
        f"fade=t=out:st={fade_out_start:.1f}:d={fade_out_dur:.1f}:alpha=1"
    )
    overlay_cut = round(fade_out_start + fade_out_dur + 0.5, 1)  # stream ends right after fade-out
    if speed_mode not in ("max", "balanced"):
        speed_mode = "max"
    video_codec_args, codec_label = build_video_codec_args(speed_mode)
    update_p(48, f"وضع الرندر: {codec_label}")
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        *input_args,
        "-loop", "1", "-framerate", "30", "-t", f"{overlay_cut}", "-i", overlay_png,
        "-i", audio_path,
        "-filter_complex",
        f"[1:v]{overlay_fade}[ov];[0:v]{filter_chain}[vbg];[vbg][ov]overlay=0:0:eof_action=pass:format=yuv420[vout]",
        "-map", "[vout]",
        "-map", "2:a",
        *video_codec_args,
        "-af", audio_filter,
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "44100",
        "-t", f"{duration:.2f}",
        "-movflags", "+faststart",
        "-shortest",
        str(out_video_path)
    ]
    
    logger.info(f"Running FFmpeg: {' '.join(ffmpeg_cmd)}")
    ffmpeg_log_file = AUDIO_CACHE_DIR / "ffmpeg_render.log"

    def run_ffmpeg(cmd):
        """Runs FFmpeg with real time-based progress + live speed/ETA. Returns (returncode, err_tail)."""
        global _CURRENT_FFMPEG_PROC
        import re as _re
        _time_re = _re.compile(r"time=(\d+):(\d+):([\d.]+)")
        wall_start = time.time()
        with open(ffmpeg_log_file, "w", encoding="utf-8") as f_log:
            try:
                proc = subprocess.Popen(cmd, stdout=f_log, stderr=subprocess.STDOUT, universal_newlines=True)
            except Exception as e:
                _CURRENT_FFMPEG_PROC = None
                return 1, f"Could not start FFmpeg (is it installed?): {e}"
            _CURRENT_FFMPEG_PROC = proc
            last_pct = 50
            idle_ticks = 0
            while proc.poll() is None:
                pct = None
                extra = ""
                try:
                    with open(ffmpeg_log_file, "r", encoding="utf-8", errors="ignore") as _lf:
                        _lf.seek(0, 2)
                        _size = _lf.tell()
                        _lf.seek(max(0, _size - 4096))
                        tail = _lf.read()
                    matches = _time_re.findall(tail)
                    if matches:
                        h, m, s = matches[-1]
                        enc_sec = int(h) * 3600 + int(m) * 60 + float(s)
                        wall = max(1.0, time.time() - wall_start)
                        if duration > 0:
                            pct = 50 + min(49, int(49 * enc_sec / duration))
                            spd = enc_sec / wall
                            if spd > 0.05:
                                eta_s = max(0.0, (duration - enc_sec) / spd)
                                if eta_s >= 90:
                                    eta_txt = f"المتبقي ~{eta_s / 60:.0f} دقيقة"
                                else:
                                    eta_txt = f"المتبقي ~{eta_s:.0f} ثانية"
                                extra = f" • السرعة {spd:.1f}x • {eta_txt}"
                except Exception:
                    pct = None
                if pct is None:
                    idle_ticks += 1
                    pct = min(92, last_pct + (1 if idle_ticks % 2 == 0 else 0))
                pct = max(last_pct, min(99, pct))
                last_pct = pct
                update_p(pct, f"جاري الرندر والمونتاج... {pct}%{extra}")
                time.sleep(1.0)
        err_tail = ""
        if proc.returncode != 0 and ffmpeg_log_file.exists():
            with open(ffmpeg_log_file, "r", encoding="utf-8", errors="ignore") as f_log:
                err_tail = f_log.read()[-500:]
        _CURRENT_FFMPEG_PROC = None
        return proc.returncode, err_tail

    retcode, err_content = run_ffmpeg(ffmpeg_cmd)

    # Bulletproof fallback: if hardware encoder failed, retry once with classic x264
    if retcode != 0 and "h264_qsv" in " ".join(ffmpeg_cmd):
        logger.warning("Hardware encoder failed, retrying with classic x264 (balanced)...")
        update_p(50, "تعذر تسريع العتاد، جاري إعادة المحاولة بالوضع الكلاسيكي...")
        fallback_cmd = [a for a in ffmpeg_cmd]
        for _i, _a in enumerate(fallback_cmd):
            if _a == "h264_qsv":
                fallback_cmd[_i] = "libx264"
            elif _a == "-global_quality":
                fallback_cmd[_i] = "-crf"
        if "-threads" not in fallback_cmd:
            fallback_cmd += ["-threads", "0"]
        retcode, err_content = run_ffmpeg(fallback_cmd)

    if retcode != 0:
        logger.error(f"FFmpeg error: {err_content}")
        raise RuntimeError(f"خطأ أثناء معالجة الفيديو: {err_content}")
        
    update_p(100, "تم إنشاء الفيديو بنجاح وجاهز للمعاينة والنشر!")

    try:
        size_mb = round(out_video_path.stat().st_size / (1024 * 1024), 1)
    except Exception:
        size_mb = 0

    return {
        'video_path': str(out_video_path),
        'filename': out_filename,
        'duration': round(duration, 1),
        'size_mb': size_mb,
        'surah_name': surah_name,
        'surah_num': surah_num,
        'ayah_range_label': ayah_range_label,
        'reciter_name': reciter['name'],
        'vintage_effect': vintage_effect,
        'speed_mode': speed_mode,
        'aspect_ratio': aspect_ratio,
        'web_url': f"/outputs/video/{out_filename}"
    }


# ============================================================
# Multi-segment engine: Ruqyah + Compilation (slideshow bgs)
# - Audio: per-segment files (full-surah OR ayah-stitched) joined with
#   FFmpeg concat (low RAM, works for hours-long compilations).
# - Backgrounds: slideshow with HARD cuts (each bg shows its slice then
#   the next one) - exactly as requested, no crossfade weirdness.
# - Quranic text: NEVER hardcoded; fetched live (uthmani) when needed.
# ============================================================

def resolve_background_list(bg_filenames, count):
    """Resolves an ordered, de-duplicated list of background paths.

    bg_filenames: user-chosen ordered list (may be empty/None) -> validated.
    Missing entries fall back to random distinct backgrounds.
    """
    wanted = []
    if bg_filenames:
        for name in bg_filenames:
            if not name:
                continue
            cand = BACKGROUNDS_DIR / Path(str(name)).name
            if cand.exists() and cand.is_file():
                if str(cand) not in wanted:
                    wanted.append(str(cand))
            else:
                alt = Path(str(name))
                if alt.exists() and alt.is_file() and str(alt) not in wanted:
                    wanted.append(str(alt))
    if count <= 0:
        count = 1
    if len(wanted) >= count:
        return wanted[:count]
    # Fill up with random distinct backgrounds
    pool = [b['path'] for b in get_local_backgrounds() if b['path'] not in wanted]
    random.shuffle(pool)
    wanted += pool[:max(0, count - len(wanted))]
    if not wanted:
        raise RuntimeError("لا توجد خلفيات في مجلد backgrounds! ضع فيديو mp4 أو صورة jpg/png واحدة على الأقل.")
    # If still short (fewer bgs than slices), cycle from the start
    while len(wanted) < count:
        wanted.append(wanted[len(wanted) % len(wanted)])
    return wanted[:count]


def concat_audio_files_ffmpeg(audio_files, out_path, progress_cb=None):
    """Joins MP3 files into ONE mp3 (re-encoded 192k) via FFmpeg concat demuxer."""
    if not audio_files:
        raise RuntimeError("لا توجد ملفات صوتية للدمج")
    if len(audio_files) == 1:
        # Single file: copy/normalize to out_path for a uniform pipeline
        import shutil
        shutil.copy(str(audio_files[0]), str(out_path))
        return str(out_path)
    list_file = AUDIO_CACHE_DIR / f"concat_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for p in audio_files:
            safe = str(p).replace("'", "'\\''")
            f.write(f"file '{safe}'\n")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
           "-c:a", "libmp3lame", "-b:a", "192k", "-ar", "44100", str(out_path)]
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3600)
    try:
        list_file.unlink()
    except Exception:
        pass
    if r.returncode != 0 or not Path(out_path).exists():
        raise RuntimeError("فشل دمج الملفات الصوتية، أعد المحاولة")
    return str(out_path)


def create_multisegment_overlay_image(width, height, center_title, top_label,
                                      reciter_name, summary_text=None):
    """Gold-frame intro overlay for ruqyah/compilation (same studio aesthetic)."""
    font_path = get_best_font()
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    overlay_box = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay_box)
    plate_margin_x = int(width * 0.08)
    plate_margin_y = int(height * 0.12)
    overlay_draw.rounded_rectangle(
        [plate_margin_x, plate_margin_y, width - plate_margin_x, height - plate_margin_y],
        radius=24, fill=(10, 10, 15, 160),
        outline=(212, 175, 55, 90), width=2)
    img = Image.alpha_composite(img, overlay_box)
    draw = ImageDraw.Draw(img)

    border_inset = int(width * 0.04)
    gold_color = (220, 185, 90, 240)
    white_color = (255, 255, 255, 255)
    cream_gold = (245, 230, 180, 255)
    draw.rectangle([border_inset, border_inset, width - border_inset, height - border_inset],
                   outline=(212, 175, 55, 180), width=2)
    draw.rectangle([border_inset + 8, border_inset + 8, width - border_inset - 8, height - border_inset - 8],
                   outline=(212, 175, 55, 80), width=1)

    top_y = int(height * 0.16)
    font_header = ImageFont.truetype(font_path, int(height * 0.028))
    header_text = reshape_text(top_label, font_path=font_path)
    bbox = draw.textbbox((0, 0), header_text, font=font_header)
    draw.text(((width - (bbox[2] - bbox[0])) // 2, top_y), header_text,
              font=font_header, fill=gold_color, stroke_width=2, stroke_fill=(0, 0, 0, 220))

    reciter_y = top_y + int(height * 0.05)
    font_reciter = ImageFont.truetype(font_path, int(height * 0.034))
    reciter_text = reshape_text(reciter_name, font_path=font_path)
    bbox_rec = draw.textbbox((0, 0), reciter_text, font=font_reciter)
    draw.text(((width - (bbox_rec[2] - bbox_rec[0])) // 2, reciter_y), reciter_text,
              font=font_reciter, fill=cream_gold, stroke_width=3, stroke_fill=(0, 0, 0, 240))

    basmalah_y = int(height * 0.30)
    font_basmalah = ImageFont.truetype(font_path, int(height * 0.042))
    basmalah_text = reshape_text("بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ", font_path=font_path)
    bbox_bas = draw.textbbox((0, 0), basmalah_text, font=font_basmalah)
    draw.text(((width - (bbox_bas[2] - bbox_bas[0])) // 2, basmalah_y), basmalah_text,
              font=font_basmalah, fill=gold_color, stroke_width=3, stroke_fill=(0, 0, 0, 240))

    center_y = int(height * 0.44)
    font_main = ImageFont.truetype(font_path, int(height * 0.055))
    title_text = reshape_text(center_title, font_path=font_path)
    bbox_title = draw.textbbox((0, 0), title_text, font=font_main)
    draw.text(((width - (bbox_title[2] - bbox_title[0])) // 2, center_y), title_text,
              font=font_main, fill=white_color, stroke_width=4, stroke_fill=(0, 0, 0, 240))

    if summary_text:
        font_sum = ImageFont.truetype(font_path, int(height * 0.024))
        wrapped = wrap_and_reshape(summary_text, words_per_line=6, font_path=font_path)
        # Keep summary compact: max 4 lines so it never overflows the frame
        lines = wrapped.split("\n")[:4]
        wrapped = "\n".join(lines)
        bbox_sum = draw.multiline_textbbox((0, 0), wrapped, font=font_sum, spacing=10, align='center')
        draw.multiline_text(((width - (bbox_sum[2] - bbox_sum[0])) // 2, center_y + int(height * 0.10)),
                            wrapped, font=font_sum, fill=(255, 255, 255, 210),
                            spacing=10, align='center', stroke_width=2, stroke_fill=(0, 0, 0, 200))

    bottom_y = int(height * 0.83)
    font_bottom = ImageFont.truetype(font_path, int(height * 0.026))
    bottom_text = reshape_text("صَدَقَةٌ جَارِيَةٌ لِوَجْهِ اللَّهِ تَعَالَى", font_path=font_path)
    bbox_bot = draw.textbbox((0, 0), bottom_text, font=font_bottom)
    draw.text(((width - (bbox_bot[2] - bbox_bot[0])) // 2, bottom_y), bottom_text,
              font=font_bottom, fill=gold_color, stroke_width=2, stroke_fill=(0, 0, 0, 220))

    out_path = AUDIO_CACHE_DIR / f"overlay_multi_{width}x{height}_{abs(hash(center_title)) % 100000}.png"
    img.save(str(out_path), "PNG")
    return str(out_path)


def generate_thumbnail_image(bg_path, hook_text, small_title, out_path, progress_cb=None):
    """Builds a 1280x720 YouTube thumbnail: same background + bold hook words.

    hook_text: 1-2 short lines, simple Arabic (user's hook).
    small_title: gold top line (e.g. surah/reciter name).
    """
    W, H = 1280, 720
    font_path = get_best_font()
    frame = AUDIO_CACHE_DIR / f"thumb_frame_{abs(hash(str(bg_path))) % 100000}.jpg"
    try:
        if is_image_background(str(bg_path)):
            src = Image.open(str(bg_path)).convert("RGB")
        else:
            # Grab a frame from the MIDDLE (after the 5s intro overlay fades out)
            try:
                _dur = get_audio_duration(str(bg_path))
                _seek = max(10.0, _dur / 2.0)
            except Exception:
                _seek = 12.0
            _hh, _rem = divmod(int(_seek), 3600)
            _mm, _ss = divmod(_rem, 60)
            cmd = ["ffmpeg", "-y", "-ss", f"{_hh:02d}:{_mm:02d}:{_ss:02d}", "-i", str(bg_path),
                   "-vframes", "1", "-vf", "scale=1280:-1", str(frame)]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            src = Image.open(str(frame)).convert("RGB") if frame.exists() else Image.new("RGB", (W, H), (10, 12, 20))
        # Cover-crop to 16:9
        scale = max(W / src.width, H / src.height)
        src = src.resize((int(src.width * scale) + 1, int(src.height * scale) + 1), Image.LANCZOS)
        x0 = (src.width - W) // 2
        y0 = (src.height - H) // 2
        src = src.crop((x0, y0, x0 + W, y0 + H))
        # Darken for readability + bottom plate
        dark = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dd = ImageDraw.Draw(dark)
        dd.rectangle([0, 0, W, H], fill=(0, 0, 0, 70))
        dd.rounded_rectangle([60, H - 300, W - 60, H - 40], radius=26, fill=(8, 8, 14, 185),
                             outline=(212, 175, 55, 160), width=3)
        src = Image.alpha_composite(src.convert("RGBA"), dark).convert("RGB")
        draw = ImageDraw.Draw(src)

        if small_title:
            font_top = ImageFont.truetype(font_path, 44)
            top_t = reshape_text(small_title, font_path=font_path)
            bb = draw.textbbox((0, 0), top_t, font=font_top)
            draw.text(((W - (bb[2] - bb[0])) // 2, 52), top_t, font=font_top,
                      fill=(245, 215, 127), stroke_width=2, stroke_fill=(0, 0, 0, 230))

        hook_text = (hook_text or "").strip()
        if hook_text:
            font_hook = ImageFont.truetype(font_path, 84)
            # Support explicit line break with | or newline; else wrap 4 words/line, max 3 lines
            if "|" in hook_text:
                parts = [p.strip() for p in hook_text.split("|") if p.strip()]
                wrapped = "\n".join([reshape_text(p, font_path=font_path) for p in parts[:3]])
            elif "\n" in hook_text:
                parts = [p.strip() for p in hook_text.split("\n") if p.strip()]
                wrapped = "\n".join([reshape_text(p, font_path=font_path) for p in parts[:3]])
            else:
                wrapped = wrap_and_reshape(hook_text, words_per_line=4, font_path=font_path)
                wrapped = "\n".join(wrapped.split("\n")[:3])
            bb = draw.multiline_textbbox((0, 0), wrapped, font=font_hook, spacing=14, align='center')
            draw.multiline_text(((W - (bb[2] - bb[0])) // 2, H - 272), wrapped, font=font_hook,
                                fill=(255, 255, 255), spacing=14, align='center',
                                stroke_width=3, stroke_fill=(0, 0, 0, 245))
        src.save(str(out_path), "JPEG", quality=90)
    finally:
        try:
            if frame.exists():
                frame.unlink()
        except Exception:
            pass
    return str(out_path)


def render_multisegment_video(
    job_title,
    segments,
    reciter_id,
    bg_filenames=None,
    aspect_ratio="16:9",
    speed_mode="max",
    top_label="",
    summary_text="",
    hook_text="",
    file_prefix="Multi",
    progress_callback=None,
):
    """Core renderer for ruqyah & compilation jobs.

    segments: list of dicts {surah, start, end, mode('full'|'range'), reciter_id?}
    reciter_id: default reciter (a segment may override it for compilations).
    Returns the same result dict shape as render_quran_video + thumbnail fields.
    """
    def update_p(percent, msg):
        if progress_callback:
            progress_callback(percent, msg)
        logger.info(f"[{percent}%] {msg}")

    if not segments:
        raise ValueError("لا توجد مقاطع صوتية في هذه المهمة")
    if len(segments) > 40:
        raise ValueError("عدد المقاطع كبير جداً (الحد 40 مقطعاً في الفيديو الواحد)")

    main_reciter = get_reciter_by_id(reciter_id)
    update_p(5, f"جاري تجهيز {job_title} ({len(segments)} مقطعاً)...")

    # 1. Per-segment audio files
    audio_files = []
    for idx, seg in enumerate(segments, start=1):
        s = int(seg["surah"])
        a = int(seg.get("start", 1))
        b = int(seg.get("end", VERSE_COUNTS.get(s, 7)))
        seg_mode = seg.get("mode", "range")
        seg_reciter = get_reciter_by_id(seg.get("reciter_id") or main_reciter["id"])
        sname = SURAH_NAMES[s - 1]
        update_p(6 + int(14 * idx / max(1, len(segments))),
                 f"تحميل المقطع {idx}/{len(segments)}: سورة {sname} بصوت {seg_reciter['name']}...")
        if seg_mode == "full":
            audio_files.append(fetch_full_surah_audio(seg_reciter, s, None))
        else:
            max_v = VERSE_COUNTS[s]
            a = max(1, min(a, max_v))
            b = max(1, min(b, max_v))
            if b < a:
                a, b = b, a
            audio_files.append(download_and_stitch_ayahs(seg_reciter, s, a, b, None))

    # 2. Join into one audio track
    update_p(22, "جاري دمج المقاطع الصوتية في مسار واحد...")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    joint_mp3 = AUDIO_CACHE_DIR / f"joint_{file_prefix}_{timestamp}.mp3"
    concat_audio_files_ffmpeg(audio_files, joint_mp3)
    duration = get_audio_duration(str(joint_mp3))
    if duration < 3:
        raise RuntimeError("ملف الصوت الناتج تالف أو قصير جداً، أعد المحاولة")
    logger.info(f"Multi-segment audio duration: {duration:.2f}s")

    # 3. Background slideshow
    width, height = (1920, 1080) if aspect_ratio == "16:9" else (1080, 1920)
    n_bg = min(max(1, len(segments)), 8)
    bg_list = resolve_background_list(bg_filenames, n_bg)
    update_p(30, f"تم تجهيز {len(bg_list)} خلفيات متتابعة (كل صورة تُعرض ثم التي بعدها)...")
    slice_dur = duration / len(bg_list)

    overlay_png = create_multisegment_overlay_image(
        width, height, center_title=job_title,
        top_label=top_label or job_title,
        reciter_name=main_reciter["name"],
        summary_text=summary_text)
    fade_in, fade_out_start, fade_out_dur = build_intro_fade_filter(duration)
    overlay_cut = round(fade_out_start + fade_out_dur + 0.5, 1)

    safe_reciter = "".join(c for c in main_reciter['id'] if c.isalnum() or c in ('_', '-'))[:30]
    out_filename = f"{file_prefix}_{safe_reciter}_{timestamp}.mp4"
    out_video_path = VIDEO_OUT_DIR / out_filename
    update_p(40, "جاري بدء المونتاج السينمائي متعدد المقاطع...")

    if speed_mode not in ("max", "balanced"):
        speed_mode = "max"
    video_codec_args, codec_label = build_video_codec_args(speed_mode)
    update_p(42, f"وضع الرندر: {codec_label}")
    audio_filter = build_audio_mood_filter("none", duration)

    # Build FFmpeg inputs: one per slideshow slice + overlay + audio
    ffmpeg_inputs = []
    for bg in bg_list:
        if is_image_background(bg):
            ffmpeg_inputs += ["-loop", "1", "-framerate", "30", "-t", f"{slice_dur:.2f}", "-i", bg]
        else:
            ffmpeg_inputs += ["-stream_loop", "-1", "-ss", "0", "-t", f"{slice_dur:.2f}", "-i", bg]
    n_vid_inputs = len(bg_list)
    ffmpeg_inputs += ["-loop", "1", "-framerate", "30", "-t", f"{overlay_cut}", "-i", overlay_png,
                      "-i", str(joint_mp3)]

    if n_vid_inputs == 1:
        vbg_filter = f"[0:v]scale=w={width}:h={height}:force_original_aspect_ratio=increase,crop={width}:{height},fps=30,format=yuv420p[vbg]"
    else:
        parts = []
        for i in range(n_vid_inputs):
            parts.append(f"[{i}:v]scale=w={width}:h={height}:force_original_aspect_ratio=increase,"
                         f"crop={width}:{height},fps=30,format=yuv420p,settb=AVTB[v{i}]")
        parts.append("".join(f"[v{i}]" for i in range(n_vid_inputs)) + f"concat=n={n_vid_inputs}:v=1:a=0[vbg]")
        vbg_filter = ";".join(parts)
    overlay_fade = (f"format=rgba,fade=t=in:st=0:d={fade_in:.1f}:alpha=1,"
                    f"fade=t=out:st={fade_out_start:.1f}:d={fade_out_dur:.1f}:alpha=1")
    filter_complex = (f"{vbg_filter};[{n_vid_inputs}:v]{overlay_fade}[ov];"
                      f"[vbg][ov]overlay=0:0:eof_action=pass:format=yuv420[vout]")

    ffmpeg_cmd = ["ffmpeg", "-y", *ffmpeg_inputs,
                  "-filter_complex", filter_complex,
                  "-map", "[vout]", "-map", f"{n_vid_inputs + 1}:a",
                  *video_codec_args, "-af", audio_filter,
                  "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
                  "-t", f"{duration:.2f}", "-movflags", "+faststart", "-shortest",
                  str(out_video_path)]
    logger.info(f"Running FFmpeg (multisegment): {' '.join(ffmpeg_cmd[:12])} ...")
    ffmpeg_log_file = AUDIO_CACHE_DIR / "ffmpeg_render.log"

    def run_ffmpeg(cmd):
        global _CURRENT_FFMPEG_PROC
        import re as _re
        _time_re = _re.compile(r"time=(\d+):(\d+):([\d.]+)")
        wall_start = time.time()
        with open(ffmpeg_log_file, "w", encoding="utf-8") as f_log:
            try:
                proc = subprocess.Popen(cmd, stdout=f_log, stderr=subprocess.STDOUT, universal_newlines=True)
            except Exception as e:
                _CURRENT_FFMPEG_PROC = None
                return 1, f"Could not start FFmpeg (is it installed?): {e}"
            _CURRENT_FFMPEG_PROC = proc
            last_pct = 45
            idle_ticks = 0
            while proc.poll() is None:
                pct = None
                extra = ""
                try:
                    with open(ffmpeg_log_file, "r", encoding="utf-8", errors="ignore") as _lf:
                        _lf.seek(0, 2)
                        _size = _lf.tell()
                        _lf.seek(max(0, _size - 4096))
                        tail = _lf.read()
                    matches = _time_re.findall(tail)
                    if matches:
                        h, m, s = matches[-1]
                        enc_sec = int(h) * 3600 + int(m) * 60 + float(s)
                        wall = max(1.0, time.time() - wall_start)
                        if duration > 0:
                            pct = 45 + min(50, int(50 * enc_sec / duration))
                            spd = enc_sec / wall
                            if spd > 0.05:
                                eta_s = max(0.0, (duration - enc_sec) / spd)
                                eta_txt = f"المتبقي ~{eta_s / 60:.0f} دقيقة" if eta_s >= 90 else f"المتبقي ~{eta_s:.0f} ثانية"
                                extra = f" • السرعة {spd:.1f}x • {eta_txt}"
                except Exception:
                    pct = None
                if pct is None:
                    idle_ticks += 1
                    pct = min(94, last_pct + (1 if idle_ticks % 2 == 0 else 0))
                pct = max(last_pct, min(99, pct))
                last_pct = pct
                update_p(pct, f"جاري الرندر والمونتاج... {pct}%{extra}")
                time.sleep(1.0)
        err_tail = ""
        if proc.returncode != 0 and ffmpeg_log_file.exists():
            with open(ffmpeg_log_file, "r", encoding="utf-8", errors="ignore") as f_log:
                err_tail = f_log.read()[-500:]
        _CURRENT_FFMPEG_PROC = None
        return proc.returncode, err_tail

    retcode, err_content = run_ffmpeg(ffmpeg_cmd)
    if retcode != 0 and "h264_qsv" in " ".join(ffmpeg_cmd):
        logger.warning("Hardware encoder failed, retrying with classic x264...")
        update_p(45, "تعذر تسريع العتاد، جاري إعادة المحاولة بالوضع الكلاسيكي...")
        fallback_cmd = [("libx264" if a == "h264_qsv" else ("-crf" if a == "-global_quality" else a)) for a in ffmpeg_cmd]
        if "-threads" not in fallback_cmd:
            fallback_cmd += ["-threads", "0"]
        retcode, err_content = run_ffmpeg(fallback_cmd)
    if retcode != 0:
        logger.error(f"FFmpeg error: {err_content}")
        raise RuntimeError(f"خطأ أثناء معالجة الفيديو: {err_content}")

    # 5. Auto thumbnail (same background + hook)
    thumb_path, thumb_url = None, None
    try:
        update_p(96, "جاري توليد الصورة المصغرة...")
        thumb_name = Path(out_filename).stem + "_thumb.jpg"
        thumb_path = str(VIDEO_OUT_DIR / thumb_name)
        generate_thumbnail_image(bg_list[0], hook_text or job_title,
                                 small_title=top_label or "", out_path=thumb_path)
        thumb_url = f"/outputs/video/{thumb_name}"
    except Exception as e:
        logger.warning(f"Thumbnail generation failed: {e}")

    try:
        size_mb = round(out_video_path.stat().st_size / (1024 * 1024), 1)
    except Exception:
        size_mb = 0
    update_p(100, "تم إنشاء الفيديو بنجاح وجاهز للمعاينة والنشر!")
    return {
        'video_path': str(out_video_path),
        'filename': out_filename,
        'duration': round(duration, 1),
        'size_mb': size_mb,
        'surah_name': job_title,
        'reciter_name': main_reciter['name'],
        'vintage_effect': 'none',
        'speed_mode': speed_mode,
        'aspect_ratio': aspect_ratio,
        'web_url': f"/outputs/video/{out_filename}",
        'thumbnail': thumb_path,
        'thumbnail_url': thumb_url,
        'segments_count': len(segments),
    }


def render_ruqyah_video(ruqyah_id, reciter_id, bg_filenames=None,
                        aspect_ratio="16:9", speed_mode="max",
                        hook_text="", progress_callback=None):
    """Renders a complete ruqyah video from an authentic preset."""
    from ruqyah_data import get_ruqyah_by_id, validate_ruqyah_segments, describe_segments
    from quran_data import get_reciter_by_id as _gri
    rec = _gri(reciter_id)
    if rec.get("id") == "mohamed_refaat":
        raise RuntimeError("الشيخ محمد رفعت غير متاح للرقية (تسجيلاته 31 سورة فقط وبصوت بديل في المقاطع). اختر قارئاً آخر.")
    rq = get_ruqyah_by_id(ruqyah_id)
    validate_ruqyah_segments(rq["segments"])
    segments = [{"surah": s, "start": a, "end": b, "mode": "range"} for (s, a, b) in rq["segments"]]
    return render_multisegment_video(
        job_title=rq["name"],
        segments=segments,
        reciter_id=rec["id"],
        bg_filenames=bg_filenames,
        aspect_ratio=aspect_ratio,
        speed_mode=speed_mode,
        top_label="الرقية الشرعية",
        summary_text=describe_segments(rq["segments"]),
        hook_text=hook_text or rq["hook"],
        file_prefix=f"Ruqyah_{rq['id']}",
        progress_callback=progress_callback,
    )


# ============================================================
# 🎬 UNIFIED LONG-VIDEO ENGINE | المحرك الموحّد القوي للفديوهات الطويلة
#   يدمج روح محرك الريلز داخل محرك الفيديوهات الطويلة:
#   - صوت: آيات مفردة (تزامن دقيق 100%) + قص الصمت + تنزيل متوازي + كاش دائم.
#   - نص: الرسم العثماني المُشكَّل يظهر متزامناً مع كل "صفحة" آيات،
#         بنفس فكرة الريلز (نص الآية + رقمها) لكن على هيئة صفحات
#         مصحف متتالية تناسب السور الكاملة (حتى ساعتين+).
#   - خلفيات: Pexels تلقائياً (طبيعة نقية 100%) + احتياطي الخلفيات المحلية.
#   - FFmpeg خالص + QSV + concat: ساعات طويلة برامات منخفضة.
# ============================================================

AYAH_DOWNLOAD_WORKERS = 12      # تنزيل متوازي لآيات السور الطويلة (سرعة)
MAX_CHAPTERS = 48               # أقصى عدد فصول نصية (أداء FFmpeg + نص واضح)
CHAPTER_TARGET_SEC = 62.0       # متوسط مدة كل صفحة نصية (ثانية)


def _trim_silence_edges(src_path, dst_path):
    """يقص الصمت من بداية/نهاية الآية (نفس منطق الريلز تماماً) بأمان تام."""
    try:
        from pydub import AudioSegment
        snd = AudioSegment.from_file(str(src_path), "mp3")
        thresh = max(-42.0, snd.dBFS - 12)
        chunk = 10
        pos = 0
        while pos < len(snd) and snd[pos:pos + chunk].dBFS < thresh:
            pos += chunk
        start = max(0, pos - 30)
        pos = len(snd)
        while pos > 0 and snd[pos - chunk:pos].dBFS < thresh:
            pos -= chunk
        end = min(len(snd), pos + 30)
        if end > start + 300:
            snd[start:end].export(str(dst_path), format="mp3", bitrate="192k")
            return str(dst_path)
    except Exception as e:
        logger.warning(f"Trim failed (using raw): {e}")
    return str(src_path)


def _fetch_surah_ayahs(reciter, surah_num, start_ayah, end_ayah, progress_cb=None):
    """يجلب كل آيات المدى (صوت + نص عثماني + مدة دقيقة) بشكل متوازي.

    - نص السورة كاملة في طلب HTTP واحد (fetch_surah_texts).
    - تنزيل متوازي مع كاش دائم (السور المعادة فورية).
    - متسامح: إن فشلت آية يُعاد المحاولة تسلسلياً، ثم تُتخطى بنسبة صغيرة.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from quran_data import fetch_surah_texts

    texts_map = fetch_surah_texts(surah_num)
    total = end_ayah - start_ayah + 1
    failed = []

    def _one(ayah):
        fn = f"{reciter['id']}_{surah_num:03d}_{ayah:03d}.mp3"
        raw = AUDIO_CACHE_DIR / fn
        trm = AUDIO_CACHE_DIR / fn.replace(".mp3", "_t.mp3")
        try:
            if not (trm.exists() and trm.stat().st_size > 5000):
                if not (raw.exists() and raw.stat().st_size > 5000):
                    download_ayah_audio(reciter, surah_num, ayah, raw)
                _trim_silence_edges(raw, trm)
            dur = get_audio_duration(str(trm))
            return (ayah, str(trm), max(0.4, dur), texts_map.get(str(ayah), ""), None)
        except Exception as e:
            return (ayah, None, 0.0, texts_map.get(str(ayah), ""), str(e))

    results = {}
    with ThreadPoolExecutor(max_workers=AYAH_DOWNLOAD_WORKERS) as ex:
        futures = [ex.submit(_one, a) for a in range(start_ayah, end_ayah + 1)]
        for i, fut in enumerate(as_completed(futures), start=1):
            a, p, d, t, err = fut.result()
            results[a] = (p, d, t, err)
            if progress_cb and total > 1:
                progress_cb(6 + int(18 * i / total),
                            f"جاري تجهيز الآية {a} ({i}/{total}) من سورة {SURAH_NAMES[surah_num-1]}...")

    # إعادة تسلسلية للفاشلة فقط (مرونة قصوى)
    for a in range(start_ayah, end_ayah + 1):
        p, d, t, err = results.get(a, (None, 0.0, "", "missing"))
        if not p:
            try:
                a2, p2, d2, t2, e2 = _one(a)
                if p2:
                    results[a] = (p2, d2, t2, None)
            except Exception:
                pass

    ordered = []
    for a in range(start_ayah, end_ayah + 1):
        p, d, t, err = results.get(a, (None, 0.0, "", "missing"))
        if not p:
            failed.append(a)
        else:
            ordered.append({"ayah": a, "audio_path": p, "duration": d, "text": t})

    if failed:
        ratio = len(failed) / max(1, total)
        if ratio > 0.05:
            raise RuntimeError(
                f"تعذر تحميل {len(failed)} آية من أصل {total} من سورة "
                f"{SURAH_NAMES[surah_num-1]} (مثال: الآية {failed[0]}). "
                "تحقق من الإنترنت أو جرّب قارئاً سعودياً آخر (الشيخ العجمي / السديس / المعيقلي)."
            )
        logger.warning(f"Skipping {len(failed)} failed ayahs: {failed[:8]}...")
    if not ordered:
        raise RuntimeError("لم يتمكن المحرك من جلب أي آية. تحقق من الإنترنت وحاول مرة أخرى.")
    return ordered


def group_ayahs_into_chapters(ayahs, target_sec=CHAPTER_TARGET_SEC, max_chapters=MAX_CHAPTERS):
    """يجمع الآيات في فصول نصية (صفحات) كل منها ~target_sec ثانية.

    - يضبط المدة تلقائياً ليبقى عدد الفصول ضمن max_chapters (أداء FFmpeg).
    - يدمج الفقير الأخير مع سابقه حتى لا تظهر صفحة قصيرة مفردة.
    """
    if not ayahs:
        return []
    total = sum(a["duration"] for a in ayahs)
    tgt = max(25.0, target_sec)
    if total / tgt > max_chapters:
        tgt = total / max_chapters
    chapters = []
    cur, cur_dur = [], 0.0
    for a in ayahs:
        cur.append(a)
        cur_dur += a["duration"]
        if cur_dur >= tgt:
            chapters.append({"ayahs": cur, "duration": round(cur_dur, 2)})
            cur, cur_dur = [], 0.0
    if cur:
        if chapters and cur_dur < tgt * 0.35:
            chapters[-1]["ayahs"].extend(cur)
            chapters[-1]["duration"] = round(chapters[-1]["duration"] + cur_dur, 2)
        else:
            chapters.append({"ayahs": cur, "duration": round(cur_dur, 2)})
    return chapters


def create_chapter_overlay_image(width, height, chapter, surah_num, reciter,
                                 page_no=None, total_pages=None):
    """صفحة مصحف متزامنة: آيات الفصل بالرسم العثماني المُشكَّل + أرقام الآيات.

    تحاكي فكرة كتابة الريلز (النص + رقم الآية) على نطاق السور الطويلة:
    نص متكيف الحجم تلقائياً (لا يخرج أبداً عن الإطار) + إطار ذهبي خفيف
    + اسم السورة والقارئ + ترقيم الصفحات. لا تفشل أبداً (fallback للعنوان).
    """
    font_path = get_best_font()
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    surah_name = SURAH_NAMES[surah_num - 1]
    is_makkah = is_makki(surah_num)
    revelation = "مكية" if is_makkah else "مدنية"
    ayahs = [a for a in chapter["ayahs"] if a.get("text")]
    gold = (220, 185, 90, 240)
    cream = (245, 230, 180, 255)
    white = (255, 255, 255, 255)

    # شريط علوي داكن خفيف + شريط سفلي لقراءة النص
    plate = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pd_ = ImageDraw.Draw(plate)
    pd_.rectangle([0, 0, width, int(height * 0.135)], fill=(6, 8, 14, 150))
    pd_.rectangle([0, int(height * 0.86), width, height], fill=(6, 8, 14, 150))
    img = Image.alpha_composite(img, plate)
    draw = ImageDraw.Draw(img)

    # الترويسة: اسم السورة + الوحي
    f_head = ImageFont.truetype(font_path, int(height * 0.030))
    head = reshape_text(f"❖  سورة {surah_name}  |  {revelation}  ❖", font_path=font_path)
    bb = draw.textbbox((0, 0), head, font=f_head)
    draw.text(((width - (bb[2] - bb[0])) // 2, int(height * 0.032)), head,
              font=f_head, fill=gold, stroke_width=2, stroke_fill=(0, 0, 0, 230))
    f_rec = ImageFont.truetype(font_path, int(height * 0.024))
    rec_txt = reshape_text(f"القارئ: {reciter['name']}", font_path=font_path)
    bb2 = draw.textbbox((0, 0), rec_txt, font=f_rec)
    draw.text(((width - (bb2[2] - bb2[0])) // 2, int(height * 0.085)), rec_txt,
              font=f_rec, fill=cream, stroke_width=2, stroke_fill=(0, 0, 0, 220))

    # التذييل: صدقة جارية + رقم الصفحة
    f_foot = ImageFont.truetype(font_path, int(height * 0.020))
    foot = "صَدَقَةٌ جَارِيَةٌ لِوَجْهِ اللَّهِ تَعَالَى"
    if page_no and total_pages:
        foot = f"الصفحة {to_arabic_digits(page_no)} / {to_arabic_digits(total_pages)}   •   {foot}"
    foot_t = reshape_text(foot, font_path=font_path)
    bb3 = draw.textbbox((0, 0), foot_t, font=f_foot)
    draw.text(((width - (bb3[2] - bb3[0])) // 2, int(height * 0.905)), foot_t,
              font=f_foot, fill=(220, 185, 90, 200), stroke_width=1, stroke_fill=(0, 0, 0, 200))

    if not ayahs:
        # fallback: عنوان السورة فقط (النص غير متاح)
        f_main = ImageFont.truetype(font_path, int(height * 0.055))
        main_txt = reshape_text(f"سُورَةُ {surah_name}", font_path=font_path)
        bbm = draw.textbbox((0, 0), main_txt, font=f_main)
        draw.text(((width - (bbm[2] - bbm[0])) // 2, int(height * 0.42)), main_txt,
                  font=f_main, fill=white, stroke_width=4, stroke_fill=(0, 0, 0, 240))
        out = AUDIO_CACHE_DIR / f"chapter_{surah_num}_{page_no or 0}_{width}x{height}_plain.png"
        img.save(str(out), "PNG")
        return str(out)

    # بناء نص الفصل: كل آية + رقمها بالأرقام العربية (مثل الريلز بالضبط)
    segments = []
    for a in ayahs:
        num = to_arabic_digits(a["ayah"])
        body = " ".join(a["text"].split())
        segments.append(f"{body} ۝{num}")
    full = " ".join(segments)

    top_y = int(height * 0.155)
    bottom_limit = int(height * 0.855)
    avail_h = bottom_limit - top_y
    words_per_line = 7 if width > height else 5

    # حجم الخط يتكيف تلقائياً حتى يلائم المساحة (حلقة ضبط آمنة)
    words = len(full.split())
    if words < 45:
        font_size = int(height * 0.046)
    elif words < 90:
        font_size = int(height * 0.039)
    elif words < 160:
        font_size = int(height * 0.033)
    else:
        font_size = int(height * 0.028)
        words_per_line += 2

    chosen = None
    for _attempt in range(8):
        font = ImageFont.truetype(font_path, font_size)
        wrapped = wrap_and_reshape(full, words_per_line=words_per_line, font_path=font_path)
        spacing = max(10, int(font_size * 0.42))
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=spacing, align="center")
        h = bbox[3] - bbox[1]
        if h <= avail_h:
            chosen = (font, wrapped, spacing)
            break
        font_size = int(font_size * 0.90)
        words_per_line = min(words_per_line + 2, 16)

    if chosen is None:
        # ضمان نهائي: تصغير النص حتى يلائم (لا يخرج أبداً عن الإطار)
        font = ImageFont.truetype(font_path, max(16, font_size))
        max_chars = max(20, int(words_per_line * 6))
        short = " ".join(full.split()[:max_chars]) + " ..."
        wrapped = wrap_and_reshape(short, words_per_line=words_per_line, font_path=font_path)
        spacing = max(8, int(font_size * 0.4))
        chosen = (font, wrapped, spacing)

    font, wrapped, spacing = chosen
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=spacing, align="center")
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (width - tw) // 2
    y = top_y + max(0, (avail_h - th) // 2)
    draw.multiline_text((x + 3, y + 3), wrapped, font=font, fill=(0, 0, 0, 200),
                        spacing=spacing, align="center", stroke_width=2, stroke_fill=(0, 0, 0, 210))
    draw.multiline_text((x, y), wrapped, font=font, fill=white,
                        spacing=spacing, align="center", stroke_width=1, stroke_fill=(0, 0, 0, 190))

    tag = "_".join(str(a["ayah"]) for a in ayahs[:6])
    out = AUDIO_CACHE_DIR / f"chapter_{surah_num}_{width}x{height}_{tag}_{page_no or 0}.png"
    img.save(str(out), "PNG")
    return str(out)


_BG_DIM_CACHE = {}


def _bg_dimensions(path):
    """أبعاد أي خلفية (فيديو أو صورة) مع كاش - (w, h) أو None."""
    if path in _BG_DIM_CACHE:
        return _BG_DIM_CACHE[path]
    dim = None
    try:
        p = str(path)
        if is_image_background(p):
            with Image.open(p) as im:
                dim = (im.width, im.height)
        else:
            cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
                   "-show_entries", "stream=width,height",
                   "-of", "csv=p=0:s=x", p]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            line = (r.stdout or "").strip().splitlines()
            if line:
                w, h = line[0].split("x")[:2]
                dim = (int(w), int(h))
    except Exception:
        dim = None
    _BG_DIM_CACHE[path] = dim
    return dim


def resolve_long_backgrounds(n, aspect_ratio, bg_video_filename=None,
                             pexels_mode="auto", pexels_api_key=None, progress_cb=None):
    """يجلب n خلفيات طبيعية متتالية: Pexels (auto) أولاً ثم الخلفيات المحلية.

    - الوضع التلقائي: يتطلب مفتاح Pexels صالحاً (غير placeholder).
    - الاحتياطي: الخلفيات المحلية في backgrounds/ (دائماً يعمل، بدون مشاكل).
    """
    if n < 1:
        n = 1
    if bg_video_filename:
        try:
            one = pick_background_smart(bg_video_filename)
            return [one] * n
        except Exception:
            pass

    key = (pexels_api_key or "").strip()
    if not key:
        try:
            from pexels_api import get_api_key
            key = get_api_key()
        except Exception:
            key = ""

    if pexels_mode == "auto" and key and key != "your_pexels_api_key_here":
        try:
            from pexels_api import fetch_nature_video
            orientation = "landscape" if aspect_ratio == "16:9" else "portrait"
            paths = []
            for i in range(n):
                if progress_cb:
                    progress_cb(34, f"جاري جلب خلفية طبيعية نقية من Pexels ({i+1}/{n})...")
                p = fetch_nature_video(orientation, min_duration=6,
                                       api_key=key, prefer_long=True, seed=i + 1)
                if p:
                    paths.append(p)
            if paths:
                try:
                    for b in get_local_backgrounds():
                        if len(paths) >= n:
                            break
                        paths.append(b["path"])
                except Exception:
                    pass
                while len(paths) < n:
                    paths.append(paths[0])
                return paths[:n]
        except Exception as e:
            logger.warning(f"Pexels unavailable ({str(e)[:140]}) - using local backgrounds.")

    # الاحتياطي المحلي (مضمون دائماً)
    try:
        bgs = get_local_backgrounds()
    except Exception:
        bgs = []
    # فلتر الجودة: استبعد أي خلفية بأبعاد أقل من 960px (ستكون ضبابية على 1080p)
    MIN_DIM = 960
    good_bgs = []
    for b in bgs:
        try:
            dim = _bg_dimensions(b["path"])
            if dim and min(dim) >= MIN_DIM:
                good_bgs.append(b)
        except Exception:
            pass
    if good_bgs:
        bgs = good_bgs
    if not bgs:
        raise RuntimeError(
            "لا توجد خلفيات متاحة! أضف مفتاح Pexels (PEXELS_API_KEY) أو ضع فيديو/صورة طبيعية (≥960px) في مجلد backgrounds."
        )
    pool = [b["path"] for b in bgs]
    rng = random.Random(2024)
    rng.shuffle(pool)
    paths = []
    i = 0
    while len(paths) < n:
        paths.append(pool[i % len(pool)])
        i += 1
    return paths[:n]


def render_long_quran_video(surah_num, reciter_id, mode="full", start_ayah=1, end_ayah=None,
                            bg_video_filename=None, aspect_ratio="16:9", speed_mode="max",
                            progress_callback=None, pexels_mode="auto", pexels_api_key=None):
    """المحرك الموحّد القوي للفديوهات القرآنية الطويلة (السورة الكاملة).

    يجمع: قوة FFmpeg/QSV (سرعة) + تزامن الريلز (نص كل آية) + خلفيات Pexels.
    مناسب من 10 ثوانٍ حتى ساعتين+ (سورة البقرة كاملة) برامات منخفضة.
    """
    def update_p(percent, msg):
        if progress_callback:
            progress_callback(percent, msg)
        logger.info(f"[{percent}%] {msg}")

    update_p(4, "جاري تهيئة المحرك الموحّد للفيديو الطويل...")

    if not (1 <= surah_num <= 114):
        raise ValueError(f"رقم السورة غير صالح: {surah_num}")
    reciter = get_reciter_by_id(reciter_id)
    if reciter.get("id") == "mohamed_refaat":
        raise RuntimeError(
            "الشيخ محمد رفعت متاح فقط بالمسار الكلاسيكي (تسجيلاته 31 سورة وبصوت بديل في المقاطع). "
            "اختر قارئاً سعودياً (الشيخ العجمي / السديس / المعيقلي) أو القارئ الكلاسيكي."
        )
    surah_name = SURAH_NAMES[surah_num - 1]
    max_v = VERSE_COUNTS[surah_num]

    if mode == "full":
        start_ayah, end_ayah = 1, max_v
    else:
        try:
            start_ayah = int(start_ayah) if start_ayah else 1
            end_ayah = int(end_ayah) if end_ayah else max_v
        except Exception:
            start_ayah, end_ayah = 1, max_v
        start_ayah = max(1, min(start_ayah, max_v))
        end_ayah = max(1, min(end_ayah, max_v))
        if end_ayah < start_ayah:
            start_ayah, end_ayah = end_ayah, start_ayah

    update_p(6, f"المطلوب: سورة {surah_name} ({start_ayah}-{end_ayah}) بصوت {reciter['name']}")

    # 1) الآيات: صوت مقصوص + نص عثماني + مدة دقيقة (تزامن 100%)
    ayahs = _fetch_surah_ayahs(reciter, surah_num, start_ayah, end_ayah, update_p)
    total_audio = sum(a["duration"] for a in ayahs)
    if total_audio < 3:
        raise RuntimeError("الصوت الناتج قصير جداً أو تالف، أعد المحاولة")
    update_p(26, f"تم تجهيز {len(ayahs)} آية - المدة الإجمالية {total_audio/60:.1f} دقيقة")

    # 2) دمج الصوت في مسار واحد
    update_p(28, "جاري دمج التلاوة في مسار صوتي واحد...")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_reciter = "".join(c for c in reciter['id'] if c.isalnum() or c in ('_', '-'))[:40]
    joint_mp3 = AUDIO_CACHE_DIR / f"long_{safe_reciter}_{surah_num:03d}_{start_ayah}_{end_ayah}_{timestamp}.mp3"
    concat_audio_files_ffmpeg([a["audio_path"] for a in ayahs], joint_mp3)
    duration = get_audio_duration(str(joint_mp3))
    if duration < 3:
        raise RuntimeError("ملف الصوت المدمج تالف، أعد المحاولة")
    logger.info(f"Long video audio: {duration:.1f}s ({len(ayahs)} ayahs)")

    # 3) الفصول النصية (صفحات المصحف)
    chapters = group_ayahs_into_chapters(ayahs)
    update_p(30, f"تم تقسيم التلاوة إلى {len(chapters)} صفحة قرآنية متزامنة...")

    # 4) الخلفيات الطبيعية (Pexels تلقائياً + احتياطي محلي)
    n_bg = min(max(2, len(chapters) // 4), 8)
    bg_list = resolve_long_backgrounds(n_bg, aspect_ratio,
                                       bg_video_filename=bg_video_filename,
                                       pexels_mode=pexels_mode,
                                       pexels_api_key=pexels_api_key,
                                       progress_cb=update_p)
    update_p(38, f"تم تجهيز {len(bg_list)} خلفيات طبيعية متتالية...")

    # 5) صور كل فصل (نصوص الآيات بالرسم العثماني)
    width, height = (1920, 1080) if aspect_ratio == "16:9" else (1080, 1920)
    chapter_pngs = []
    for i, ch in enumerate(chapters, start=1):
        try:
            png = create_chapter_overlay_image(
                width=width, height=height, chapter=ch,
                surah_num=surah_num, reciter=reciter,
                page_no=i, total_pages=len(chapters))
            chapter_pngs.append(png)
        except Exception as e:
            logger.warning(f"Chapter {i} overlay failed: {e}")
    chapter_pngs = [p for p in chapter_pngs if p]
    if not chapter_pngs:
        raise RuntimeError("تعذر توليد صفحات النص القرآني")
    update_p(44, f"تم تصميم {len(chapter_pngs)} صفحة بالرسم العثماني المُشكَّل")

    # 6) التركيب النهائي عبر FFmpeg
    if speed_mode not in ("max", "balanced"):
        speed_mode = "max"
    video_codec_args, codec_label = build_video_codec_args(speed_mode)
    update_p(46, f"وضع الرندر: {codec_label}")

    # أوقات الفصول (تراكمية) للتزامن الدقيق
    cum = 0.0
    chapter_times = []
    for ch in chapters[:len(chapter_pngs)]:
        chapter_times.append((cum, cum + ch["duration"]))
        cum += ch["duration"]

    ffmpeg_inputs = []
    slice_dur = duration / len(bg_list)
    for bg in bg_list:
        if is_image_background(bg):
            ffmpeg_inputs += ["-loop", "1", "-framerate", "30", "-t", f"{slice_dur:.2f}", "-i", bg]
        else:
            ffmpeg_inputs += ["-stream_loop", "-1", "-ss", "0", "-t", f"{slice_dur:.2f}", "-i", bg]
    n_bg_in = len(bg_list)
    for i, png in enumerate(chapter_pngs):
        cd = chapter_times[i][1] - chapter_times[i][0]
        ffmpeg_inputs += ["-loop", "1", "-framerate", "30", "-t", f"{cd:.2f}", "-i", png]
    n_txt_in = len(chapter_pngs)
    ffmpeg_inputs += ["-i", str(joint_mp3)]

    # فلتر: خلفيات مدمجة ← طبقات النص متسلسلة بإظهار زمني دقيق
    parts = []
    for i in range(n_bg_in):
        parts.append(f"[{i}:v]scale=w={width}:h={height}:force_original_aspect_ratio=increase,"
                     f"crop={width}:{height},fps=30,format=yuv420p,setsar=1,settb=AVTB[b{i}]")
    parts.append("".join(f"[b{i}]" for i in range(n_bg_in)) +
                 f"concat=n={n_bg_in}:v=1:a=0[vbg]")
    fade_d = 1.0
    t0, t1 = chapter_times[0]
    parts.append(f"[{n_bg_in}:v]format=rgba,fade=t=in:st=0:d={fade_d}:alpha=1,"
                 f"fade=t=out:st={max(0, (t1 - t0) - fade_d):.2f}:d={fade_d}:alpha=1[ov0]")
    parts.append(f"[vbg][ov0]overlay=0:0:enable='between(t,{t0:.2f},{t1:.2f})':format=yuv420[v0]")
    prev = "v0"
    for i in range(1, n_txt_in):
        idx = n_bg_in + i
        a, b = chapter_times[i]
        cd = b - a
        parts.append(f"[{idx}:v]format=rgba,fade=t=in:st=0:d={fade_d}:alpha=1,"
                     f"fade=t=out:st={max(0, cd - fade_d):.2f}:d={fade_d}:alpha=1[ov{i}]")
        parts.append(f"[{prev}][ov{i}]overlay=0:0:enable='between(t,{a:.2f},{b:.2f})':format=yuv420[v{i}]")
        prev = f"v{i}"
    parts.append(f"[{prev}]format=yuv420p[vout]")
    filter_complex = ";".join(parts)
    audio_filter = build_audio_mood_filter("none", duration)

    out_filename = f"Quran_{surah_name}_{start_ayah}_{end_ayah}_{safe_reciter}_{timestamp}.mp4"
    out_video_path = VIDEO_OUT_DIR / out_filename
    update_p(50, f"جاري الرندر السينمائي ({duration/60:.1f} دقيقة • {len(chapter_pngs)} صفحة)...")

    ffmpeg_cmd = ["ffmpeg", "-y", *ffmpeg_inputs,
                  "-filter_complex", filter_complex,
                  "-map", "[vout]", "-map", f"{n_bg_in + n_txt_in}:a",
                  *video_codec_args, "-af", audio_filter,
                  "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
                  "-t", f"{duration:.2f}", "-movflags", "+faststart", "-shortest",
                  str(out_video_path)]
    logger.info(f"Running FFmpeg (long engine): inputs={n_bg_in + n_txt_in + 1}")
    ffmpeg_log_file = AUDIO_CACHE_DIR / "ffmpeg_render.log"

    def run_ffmpeg(cmd):
        global _CURRENT_FFMPEG_PROC
        import re as _re
        _time_re = _re.compile(r"time=(\d+):(\d+):([\d.]+)")
        wall_start = time.time()
        with open(ffmpeg_log_file, "w", encoding="utf-8") as f_log:
            try:
                proc = subprocess.Popen(cmd, stdout=f_log, stderr=subprocess.STDOUT, universal_newlines=True)
            except Exception as e:
                _CURRENT_FFMPEG_PROC = None
                return 1, f"Could not start FFmpeg (is it installed?): {e}"
            _CURRENT_FFMPEG_PROC = proc
            last_pct = 50
            while proc.poll() is None:
                pct = None
                extra = ""
                try:
                    with open(ffmpeg_log_file, "r", encoding="utf-8", errors="ignore") as _lf:
                        _lf.seek(0, 2)
                        _size = _lf.tell()
                        _lf.seek(max(0, _size - 4096))
                        tail = _lf.read()
                    matches = _time_re.findall(tail)
                    if matches:
                        h, m, s = matches[-1]
                        enc_sec = int(h) * 3600 + int(m) * 60 + float(s)
                        wall = max(1.0, time.time() - wall_start)
                        if duration > 0:
                            pct = 50 + min(48, int(48 * enc_sec / duration))
                            spd = enc_sec / wall
                            if spd > 0.05:
                                eta_s = max(0.0, (duration - enc_sec) / spd)
                                eta_txt = (f"المتبقي ~{eta_s / 60:.1f} دقيقة" if eta_s >= 90
                                           else f"المتبقي ~{eta_s:.0f} ثانية")
                                extra = f" • السرعة {spd:.1f}x • {eta_txt}"
                except Exception:
                    pct = None
                if pct is None:
                    pct = min(96, last_pct + 1)
                pct = max(last_pct, min(99, pct))
                last_pct = pct
                update_p(pct, f"جاري الرندر والمونتاج... {pct}%{extra}")
                time.sleep(1.5)
            err_tail = ""
            if proc.returncode != 0 and ffmpeg_log_file.exists():
                with open(ffmpeg_log_file, "r", encoding="utf-8", errors="ignore") as f_log:
                    err_tail = f_log.read()[-600:]
            _CURRENT_FFMPEG_PROC = None
            return proc.returncode, err_tail

    retcode, err_content = run_ffmpeg(ffmpeg_cmd)
    if retcode != 0 and "h264_qsv" in " ".join(ffmpeg_cmd):
        logger.warning("Hardware encoder failed, retrying with classic x264...")
        update_p(50, "تعذر تسريع العتاد، جاري إعادة المحاولة بالوضع الكلاسيكي...")
        fallback_cmd = [("libx264" if a == "h264_qsv" else ("-crf" if a == "-global_quality" else a)) for a in ffmpeg_cmd]
        if "-threads" not in fallback_cmd:
            fallback_cmd += ["-threads", "0"]
        retcode, err_content = run_ffmpeg(fallback_cmd)
    if retcode != 0:
        logger.error(f"FFmpeg error: {err_content}")
        raise RuntimeError(f"خطأ أثناء معالجة الفيديو: {err_content[-300:]}")

    update_p(97, "جاري توليد الصورة المصغرة...")
    thumb_path, thumb_url = None, None
    try:
        thumb_name = Path(out_filename).stem + "_thumb.jpg"
        thumb_path = str(VIDEO_OUT_DIR / thumb_name)
        generate_thumbnail_image(bg_list[0], f"سورة {surah_name} كاملة",
                                 small_title=reciter["name"], out_path=thumb_path)
        thumb_url = f"/outputs/video/{thumb_name}"
    except Exception as e:
        logger.warning(f"Thumbnail generation failed: {e}")

    try:
        size_mb = round(out_video_path.stat().st_size / (1024 * 1024), 1)
    except Exception:
        size_mb = 0
    update_p(100, "تم إنشاء الفيديو الطويل بنجاح وجاهز للمعاينة والنشر!")
    return {
        'video_path': str(out_video_path),
        'filename': out_filename,
        'duration': round(duration, 1),
        'size_mb': size_mb,
        'surah_name': surah_name,
        'surah_num': surah_num,
        'ayah_range_label': ("كاملة" if mode == "full" else f"الآيات {start_ayah}-{end_ayah}"),
        'reciter_name': reciter['name'],
        'vintage_effect': 'none',
        'speed_mode': speed_mode,
        'aspect_ratio': aspect_ratio,
        'web_url': f"/outputs/video/{out_filename}",
        'thumbnail': thumb_path,
        'thumbnail_url': thumb_url,
        'chapters_count': len(chapter_pngs),
        'ayahs_count': len(ayahs),
        'engine': 'unified_long',
    }


def render_compilation_video(items, reciter_id, bg_filenames=None,
                             aspect_ratio="16:9", speed_mode="max",
                             hook_text="", title="", progress_callback=None):
    """Renders one video combining multiple surahs/ranges.

    items: [{surah, mode, start, end, reciter_id?}] (1..40 items).
    """
    if not items:
        raise ValueError("اختر سورة واحدة على الأقل للتجميع")
    if len(items) > 40:
        raise ValueError("الحد الأقصى 40 مقطعاً في الفيديو المجمّع الواحد")
    segments = []
    names = []
    for it in items:
        s = int(it["surah"])
        if s not in VERSE_COUNTS:
            raise ValueError(f"رقم السورة غير صالح: {s}")
        mode = it.get("mode", "full")
        if mode not in ("full", "range"):
            mode = "full"
        a = int(it.get("start", 1) or 1)
        b = int(it.get("end", VERSE_COUNTS[s]) or VERSE_COUNTS[s])
        segments.append({"surah": s, "start": a, "end": b, "mode": mode,
                         "reciter_id": it.get("reciter_id")})
        label = SURAH_NAMES[s - 1] + (" كاملة" if mode == "full" else f" ({a}-{b})")
        if label not in names:
            names.append(label)
    job_title = title.strip() if title and title.strip() else (" + ".join(names[:4]) + ("..." if len(names) > 4 else ""))
    summary = " + ".join(names[:6]) + ("..." if len(names) > 6 else "")
    return render_multisegment_video(
        job_title=job_title,
        segments=segments,
        reciter_id=reciter_id,
        bg_filenames=bg_filenames,
        aspect_ratio=aspect_ratio,
        speed_mode=speed_mode,
        top_label="تلاوة مجمّعة",
        summary_text=summary,
        hook_text=hook_text or f"القرآن الكريم | {' + '.join(names[:3])}",
        file_prefix="Majmou3",
        progress_callback=progress_callback,
    )

