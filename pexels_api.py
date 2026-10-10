# -*- coding: utf-8 -*-
"""
Pexels Nature API - وحدة موحدة لجلب خلفيات الطبيعة النقية
============================================================
طبقة واحدة مشتركة يستخدمها كل من:
  - quran_engine.py  (محرك الفيديوهات الطويلة)
  - auto_generate.py (المسار السحابي)

سياسة المحتوى الصارمة (موروثة من محرك الريلز الأصلي):
  - 100% طبيعة عنصرية نقية فقط (سحب / ماء / جبال / فضاء / مطر / غيوم).
  - 0% بشر (لا رجال ولا نساء ولا أطفال ولا وجوه).
  - 0% حيوانات أو كائنات حية.
  - فلترة متعددة الطبقات: URL slug + tags + اسم المصور.

المفتاح: PEXELS_API_KEY (env / .env / GitHub Secrets).
مجاني: 200 طلب/الساعة — التخزين المؤقت يقلل الاستهلاك لأقصى حد.
"""

import os
import json
import time
import random
import logging
import threading
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent.resolve()
CACHE_DIR = SCRIPT_DIR / "backgrounds" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "").strip()
PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"

# =================================================================
# 🌿 استعلامات الطبيعة النقية (0% بشر، 0% كائنات حية)
#    جاهزة لكل من النمط العمودي (9:16) والأفقي (16:9).
# =================================================================
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
    "mist over peaceful lake sunrise",
]

# استعلامات أطول مدةً (للفيديوهات الطويلة نريد مشاهد بطيئة ممتدة)
LONG_SCENE_QUERIES = [
    "slow motion clouds sky",
    "aerial mountains landscape",
    "ocean waves slow motion",
    "forest canopy drone aerial",
    "desert dunes slow",
    "lake reflection calm morning",
    "milky way timelapse night",
    "rain forest slow motion",
]

# =================================================================
# 🚫 كلمات محظورة (تُرفض بمجرد ظهور أي منها)
# =================================================================
BANNED_KEYWORDS = [
    "person", "people", "man", "woman", "girl", "boy", "human", "face",
    "portrait", "model", "child", "baby", "kid", "couple", "family", "crowd",
    "walking", "dancer", "fashion", "hand", "hands", "feet", "body", "selfie",
    "lifestyle", "fitness", "workout", "legs", "eyes", "hair", "smile", "clothing",
    "dress", "shirt", "shoe", "run", "running", "yoga", "gym",
    "animal", "dog", "cat", "bird", "lion", "horse", "fish", "creature", "pet",
    "wildlife", "insect", "bear", "deer", "monkey", "tiger", "shark", "whale",
]

# قفل بسيط لتجنب الطلبات المتزامنة المتكررة (thread-safe caching)
_CACHE_LOCK = threading.Lock()
_RATE_LAST = {"ts": 0.0}


def _load_env_once():
    """تحميل .env مرة واحدة إن وُجد (يتم من قبل المتصل عادةً)."""
    if PEXELS_API_KEY:
        return
    env_file = SCRIPT_DIR / ".env"
    if env_file.exists():
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    if k.strip() == "PEXELS_API_KEY":
                        os.environ["PEXELS_API_KEY"] = v.strip()
                        globals()["PEXELS_API_KEY"] = v.strip()
                        return
        except Exception:
            pass


def get_api_key():
    """يُرجع مفتاح Pexels من البيئة (مع قراءة .env احتياطياً)."""
    key = (os.environ.get("PEXELS_API_KEY") or "").strip()
    if not key:
        _load_env_once()
        key = (os.environ.get("PEXELS_API_KEY") or "").strip()
    return key


# =================================================================
# 🛡️ الفلتر الصارم (ثلاث طبقات)
# =================================================================
def is_strictly_pure_nature(video_obj):
    """يتحقق أن الفيديو طبيعة نقية 100%: URL + tags + المصور."""
    try:
        # 1. رابط الفيديو (slug)
        url_slug = str(video_obj.get("url", "")).lower()
        for word in BANNED_KEYWORDS:
            if word in url_slug:
                return False

        # 2. الوسوم (tags)
        tags = video_obj.get("tags") or []
        for tag in tags:
            tag_str = str(tag).lower()
            for word in BANNED_KEYWORDS:
                if word in tag_str:
                    return False

        # 3. اسم المصور (استبعاد حسابات الأزياء/الليف ستايل)
        user_info = video_obj.get("user") or {}
        user_name = str(user_info.get("name", "")).lower()
        if any(t in user_name for t in ("model", "fitness", "lifestyle", "girl", "boy")):
            return False
        return True
    except Exception:
        return False


def _pick_best_file(video_obj, orientation, min_duration=None):
    """يختار أفضل ملف: الأعلى دجة المناسبة ضمن 720p–1440p، يفضّل الطويل."""
    try:
        video_files = video_obj.get("video_files") or []
        if not video_files:
            return None
        # مدة الفيديو الكلية (Pexels يوفرها)
        total_dur = video_obj.get("duration") or 0
        if min_duration and total_dur and total_dur < min_duration:
            return None

        def score(vf):
            h = vf.get("height") or 0
            w = vf.get("width") or 0
            # الأفقي: width أكبر؛ العمودي: height أكبر
            primary = w if orientation == "landscape" else h
            secondary = h if orientation == "landscape" else w
            return (primary, secondary)

        # داخل النطاق الجيد (720p..1440p) مع تفضيل 1080p
        good = []
        for vf in video_files:
            h = vf.get("height") or 0
            if 720 <= h <= 1920:
                good.append(vf)
        pool = good or video_files
        # رتّب: الأقرب لـ 1080 ارتفاعاً هو الأفضل + يفضّل الاتجاه الصحيح
        pool_sorted = sorted(
            pool,
            key=lambda vf: (
                abs((vf.get("height") or 0) - 1080),
                -(vf.get("width") or 0) if orientation == "landscape" else -(vf.get("height") or 0),
            ),
        )
        return pool_sorted[0] if pool_sorted else None
    except Exception:
        return None


def search_nature_videos(query, orientation="landscape", per_page=15, page=1,
                         api_key=None, min_duration=None):
    """يبحث في Pexels ويُرجع قائمة الفيديوهات النقية المتحقَّق منها فقط."""
    key = (api_key or get_api_key()).strip()
    if not key:
        raise ValueError(
            "❌ PEXELS_API_KEY غير موجود!\n"
            "أضف مفتاحك في .env أو GitHub Secrets (PEXELS_API_KEY).\n"
            "مجاني من: https://www.pexels.com/api/"
        )
    # تباعد بسيط بين الطلبات لاحترام حد 200/ساعة
    now = time.time()
    with _CACHE_LOCK:
        gap = now - _RATE_LAST["ts"]
        if gap < 0.7:
            time.sleep(0.7 - gap)
        _RATE_LAST["ts"] = time.time()

    params = {
        "query": query,
        "orientation": orientation,
        "size": "medium",
        "per_page": per_page,
        "page": page,
    }
    resp = requests.get(PEXELS_SEARCH_URL,
                        headers={"Authorization": key},
                        params=params, timeout=30)
    resp.raise_for_status()
    videos = resp.json().get("videos", [])
    return [v for v in videos if is_strictly_pure_nature(v)]


def fetch_nature_video(orientation="landscape", min_duration=None, api_key=None,
                       prefer_long=False, seed=None):
    """
    يبحث حتى يجد فيديو طبيعة نقياً مناسباً ويُرجّع مسار الملف المحلي.

    - orientation: "landscape" (16:9) أو "portrait" (9:16).
    - min_duration: يُفضّل المشاهد الطويلة (للفيديو الطويل نطلب ≥ 8 ثوانٍ).
    - prefer_long: يستخدم استعلامات المشاهد البطيئة الممتدة.
    - seed: لتكرارية معقولة عند الحاجة.
    يخزّن النتيجة محلياً في backgrounds/cache/ مع اسم دلالي.
    """
    key = (api_key or get_api_key()).strip()
    rng = random.Random(seed) if seed is not None else random

    pool = (LONG_SCENE_QUERIES if prefer_long else PURE_NATURE_QUERIES)
    queries = list(pool)
    rng.shuffle(queries)

    for query in queries:
        try:
            page = rng.randint(1, 3)
            videos = search_nature_videos(query, orientation=orientation,
                                          per_page=12, page=page,
                                          api_key=key, min_duration=min_duration)
        except Exception as e:
            logger.warning(f"Pexels search failed for '{query}': {e}")
            continue

        for video in videos:
            best = _pick_best_file(video, orientation, min_duration=min_duration)
            if not best:
                continue
            try:
                link = best["link"]
                # اسم دلالي وآمن
                slug = Path(str(video.get("url", "pexels")).split("/")[-1]).stem or "pexels"
                safe = "".join(c for c in slug if c.isalnum() or c in ("_", "-"))[:40] or "pexels"
                ext = Path(link).suffix.lower() or ".mp4"
                local = CACHE_DIR / f"{safe}_{(video.get('id') or 'x')}{ext}"

                if local.exists() and local.stat().st_size > 200000:
                    logger.info(f"♻️ Reusing cached nature video: {local.name}")
                    return str(local)

                r = requests.get(link, timeout=180)
                r.raise_for_status()
                with open(local, "wb") as f:
                    f.write(r.content)
                if local.stat().st_size > 200000:
                    logger.info(f"📥 Downloaded nature video: {local.name} ({local.stat().st_size // 1024}KB)")
                    return str(local)
                try:
                    local.unlink()
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"Download failed for one candidate: {e}")
                continue

    # ملجأ أخير: استعلام "السحب" الآمن مطلقاً (كما في الريلز الأصلي)
    try:
        videos = search_nature_videos("clouds timelapse sky", orientation=orientation,
                                      per_page=10, page=1, api_key=key,
                                      min_duration=None)
        if videos:
            best = _pick_best_file(videos[0], orientation)
            if best:
                link = best["link"]
                local = CACHE_DIR / f"fallback_clouds_{videos[0].get('id', 'x')}.mp4"
                if not (local.exists() and local.stat().st_size > 200000):
                    r = requests.get(link, timeout=180)
                    r.raise_for_status()
                    with open(local, "wb") as f:
                        f.write(r.content)
                if local.stat().st_size > 200000:
                    return str(local)
    except Exception as e:
        logger.warning(f"Fallback search failed: {e}")

    raise RuntimeError(
        "تعذر جلب فيديو طبيعة من Pexels (تأكد من PEXELS_API_KEY صحيح ومتصل بالإنترنت)."
    )


if __name__ == "__main__":
    # اختبار سريع: جلب خلفيتين (أفقي + عمودي)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    key = get_api_key()
    print("API key present:", bool(key))
    if key:
        p1 = fetch_nature_video("landscape", prefer_long=True)
        print("Landscape:", p1)
        p2 = fetch_nature_video("portrait")
        print("Portrait:", p2)
