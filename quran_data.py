# -*- coding: utf-8 -*-
"""
Quran Data Module
Contains metadata for all 114 Surahs, verse counts, revelation types,
and an expanded catalog of Golden Era reciters (الزمن الجميل) and Haram reciters.
"""

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

# Revelation types (1 = Makkiyah, 2 = Madaniyah)
MAKKI_SURAHS = {
    1, 6, 7, 10, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 23, 25, 26, 27, 28, 29, 30,
    31, 32, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 50, 51, 52, 53, 54,
    56, 67, 68, 69, 70, 71, 72, 73, 74, 75, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86,
    87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 100, 101, 102, 103, 104, 105, 106, 107,
    108, 109, 111, 112, 113, 114
}

def is_makki(surah_num):
    return surah_num in MAKKI_SURAHS

# Historical recordings of Sheikh Mohamed Refaat (d. 1950) are LIMITED.
# Verified via mp3quran API: only these 31 surahs exist as full files.
# Full mode with any other surah, or range mode (wrong-voice risk), is blocked
# with a friendly message instead of hanging on ayah-by-ayah downloads.
REFAAT_SURAHS = {
    1, 10, 11, 12, 17, 18, 19, 20, 48, 54, 55, 56, 69, 72, 73, 75, 76, 77,
    78, 79, 81, 82, 83, 85, 86, 87, 88, 89, 96, 98, 100
}

# Mirror URL templates for full-surah files (fallback if primary server fails).
# {n} = surah number unpadded (islamic.network), {n03} = zero-padded 3 digits.
# NOTE: only mirrors verified with HTTP 200 are listed here.
MIRROR_ISLAMIC = "https://cdn.islamic.network/quran/audio/128/{ed}/{n}.mp3"

# Expanded Reciters Catalog categorised by era and school
# Each entry may carry 'mirrors': list of full-surah fallback URL templates
# ({n} unpadded, {n03} zero-padded) tried in order if the primary server fails.
RECITERS_CATALOG = [
    # --- عمالقة الزمن الجميل (مصر والعالم الإسلامي) ---
    {
        'id': 'minshawi_historic',
        'name': 'الشيخ محمد صديق المنشاوي (تسجيلات الستينات 1967م)',
        'category': 'golden_era',
        'subname': 'صاحب الصوت الباكي الخاشع',
        'everyayah_id': 'Minshawy_Mujawwad_64kbps',
        'full_surah_server': 'https://server10.mp3quran.net/minsh1387/'
    },
    {
        'id': 'minshawi_mujawwad',
        'name': 'الشيخ محمد صديق المنشاوي (المصحف المجود)',
        'category': 'golden_era',
        'subname': 'تلاوة مجودة تاريخية',
        'everyayah_id': 'Minshawy_Mujawwad_64kbps',
        'full_surah_server': 'https://server10.mp3quran.net/minsh/Almusshaf-Al-Mojawwad/'
    },
    {
        'id': 'minshawi_murattal',
        'name': 'الشيخ محمد صديق المنشاوي (مرتل)',
        'category': 'golden_era',
        'subname': 'ترتيل خاشع وهادئ',
        'everyayah_id': 'Minshawy_Murattal_128kbps',
        'full_surah_server': 'https://server10.mp3quran.net/minsh/',
        'mirrors': ['https://cdn.islamic.network/quran/audio/128/ar.minshawi/{n}.mp3']
    },
    {
        'id': 'abdulbasit_mujawwad',
        'name': 'الشيخ عبدالباسط عبدالصمد (المصحف المجود النادر)',
        'category': 'golden_era',
        'subname': 'صوت مكة وسفير القرآن الكريم',
        'everyayah_id': 'AbdulSamad_64kbps_QuranExplorer.Com',
        'full_surah_server': 'https://server7.mp3quran.net/basit/Almusshaf-Al-Mojawwad/'
    },
    {
        'id': 'abdulbasit_murattal',
        'name': 'الشيخ عبدالباسط عبدالصمد (مرتل)',
        'category': 'golden_era',
        'subname': 'ترتيل كلاسيكي عذب',
        'everyayah_id': 'Abdul_Basit_Murattal_64kbps',
        'full_surah_server': 'https://server7.mp3quran.net/basit/'
    },
    {
        'id': 'husary_mujawwad',
        'name': 'الشيخ محمود خليل الحصري (المصحف المجود)',
        'category': 'golden_era',
        'subname': 'شيخ عموم المقارئ المصرية ودقة الأحكام',
        'everyayah_id': 'Husary_64kbps',
        'full_surah_server': 'https://server13.mp3quran.net/husr/Almusshaf-Al-Mojawwad/',
        'mirrors': ['https://cdn.islamic.network/quran/audio/128/ar.husarymujawwad/{n}.mp3']
    },
    {
        'id': 'husary_murattal',
        'name': 'الشيخ محمود خليل الحصري (مرتل)',
        'category': 'golden_era',
        'subname': 'المصحف المرتل المعتمد',
        'everyayah_id': 'Husary_64kbps',
        'full_surah_server': 'https://server13.mp3quran.net/husr/',
        'mirrors': ['https://cdn.islamic.network/quran/audio/128/ar.husary/{n}.mp3']
    },
    {
        'id': 'mustafa_ismail',
        'name': 'الشيخ مصطفى إسماعيل (صاحب الحنجرة الذهبية)',
        'category': 'golden_era',
        'subname': 'عبقري التلاوة والمقامات',
        'everyayah_id': 'Mustafa_Ismail_48kbps',
        'full_surah_server': 'https://server8.mp3quran.net/mustafa/'
    },
    {
        'id': 'mahmoud_ali_banna',
        'name': 'الشيخ محمود علي البنا (المصحف المجود والمرتل)',
        'category': 'golden_era',
        'subname': 'صوت الأصالة والخشوع الفطري',
        'everyayah_id': 'mahmoud_ali_al_banna_32kbps',
        'full_surah_server': 'https://server8.mp3quran.net/bna/'
    },
    {
        'id': 'mohamed_refaat',
        'name': 'الشيخ محمد رفعت (قيثارة السماء - الثلاثينات والأربعينات)',
        'category': 'golden_era',
        'subname': 'تسجيلات تاريخية أثرية',
        'everyayah_id': 'Mohammad_al_Tablaway_64kbps',
        'full_surah_server': 'https://server14.mp3quran.net/refat/'
    },
    {
        'id': 'tablawi',
        'name': 'الشيخ محمد محمود الطبلاوي',
        'category': 'golden_era',
        'subname': 'نغم مصري أصيل وتلاوة تأسر القلوب',
        'everyayah_id': 'Mohammad_al_Tablaway_64kbps',
        'full_surah_server': 'https://server12.mp3quran.net/tblawi/'
    },
    
    # --- أئمة وقراء الحرم المكي الشريف ---
    {
        'id': 'ali_jaber',
        'name': 'الشيخ علي جابر (إمام الحرم المكي التاريخي - الثمانينات)',
        'category': 'haram',
        'subname': 'تلاوات الحرم المكي الخالدة',
        'everyayah_id': 'Ali_Jaber_64kbps',
        'full_surah_server': 'https://server11.mp3quran.net/a_jbr/'
    },
    {
        'id': 'sudais',
        'name': 'الشيخ عبدالرحمن السديس (إمام الحرم المكي)',
        'category': 'haram',
        'subname': 'إمام وخطيب المسجد الحرام',
        'everyayah_id': 'Abdurrahmaan_As-Sudais_64kbps',
        'full_surah_server': 'https://server11.mp3quran.net/sds/'
    },
    {
        'id': 'shuraim',
        'name': 'الشيخ سعود الشريم (إمام الحرم المكي)',
        'category': 'haram',
        'subname': 'ترتيل سريع ومهيب من رحاب الكعبة',
        'everyayah_id': 'Saood_ash-Shuraym_64kbps',
        'full_surah_server': 'https://server7.mp3quran.net/shur/'
    },
    {
        'id': 'maher_almuaiqly',
        'name': 'الشيخ ماهر المعيقلي (إمام الحرم المكي)',
        'category': 'haram',
        'subname': 'تلاوة رقيقة ومؤثرة',
        'everyayah_id': 'Maher_AlMuaiqly_64kbps',
        'full_surah_server': 'https://server12.mp3quran.net/maher/',
        'mirrors': ['https://cdn.islamic.network/quran/audio/128/ar.mahermuaiqly/{n}.mp3']
    },
    {
        'id': 'hudhaify',
        'name': 'الشيخ علي بن عبدالرحمن الحذيفي (إمام الحرم النبوي)',
        'category': 'haram',
        'subname': 'ترتيل متقن ورزين من رحاب المسجد النبوي',
        'everyayah_id': 'Hudhaify_64kbps',
        'full_surah_server': 'https://server9.mp3quran.net/hthfi/',
        'mirrors': ['https://cdn.islamic.network/quran/audio/128/ar.hudhaify/{n}.mp3']
    },

    # --- نخبة القراء المعاصرين ---
    {
        'id': 'alafasy',
        'name': 'الشيخ مشاري راشد العفاسي',
        'category': 'modern',
        'subname': 'صوت شجي وأداء متقن',
        'everyayah_id': 'Alafasy_64kbps',
        'full_surah_server': 'https://server8.mp3quran.net/afs/',
        'mirrors': [
            'https://cdn.islamic.network/quran/audio/128/ar.alafasy/{n}.mp3',
            'https://download.quranicaudio.com/quran/mishaari_raashid_al_3afaasee/{n03}.mp3'
        ]
    },
    {
        'id': 'yasser_dussary',
        'name': 'الشيخ ياسر الدوسري (إمام الحرم المكي)',
        'category': 'modern',
        'subname': 'تلاوة حماسية خاشعة تبكي القلوب',
        'everyayah_id': 'Yasser_Ad-Dussary_128kbps',
        'full_surah_server': 'https://server11.mp3quran.net/yasser/'
    },
    {
        'id': 'ghamadi',
        'name': 'الشيخ سعد الغامدي',
        'category': 'modern',
        'subname': 'ترتيل عذب ومريح للأعصاب',
        'everyayah_id': 'Ghamadi_40kbps',
        'full_surah_server': 'https://server7.mp3quran.net/s_gmd/'
    },
    {
        'id': 'ajamy',
        'name': 'الشيخ أحمد بن علي العجمي',
        'category': 'modern',
        'subname': 'قراءة جهورية مؤثرة',
        'everyayah_id': 'Ahmed_ibn_Ali_al-Ajamy_64kbps',
        'full_surah_server': 'https://server10.mp3quran.net/ajm/',
        'mirrors': ['https://cdn.islamic.network/quran/audio/128/ar.ahmedajamy/{n}.mp3']
    },
    {
        'id': 'shaatree',
        'name': 'الشيخ أبو بكر الشاطري',
        'category': 'modern',
        'subname': 'ترتيل حجازي هادئ',
        'everyayah_id': 'Abu_Bakr_Ash-Shaatree_128kbps',
        'full_surah_server': 'https://server11.mp3quran.net/shatri/',
        'mirrors': ['https://cdn.islamic.network/quran/audio/128/ar.shaatree/{n}.mp3']
    }
]

def get_reciter_by_id(reciter_id):
    for r in RECITERS_CATALOG:
        if r['id'] == reciter_id:
            return r
    return RECITERS_CATALOG[0]


# Fallback ayah-audio editions on cdn.islamic.network (global ayah number 1..6236).
# Used automatically when EveryAyah returns 404 (e.g. Ajamy folder was removed).
# Verified live: ar.ahmedajamy, ar.husary. Others follow the documented CDN scheme
# and are tried gracefully (a failed fallback never crashes, it just moves on).
ISLAMIC_AYAH_EDITIONS = {
    'minshawi_murattal': 'ar.minshawi',
    'abdulbasit_murattal': 'ar.abdulbasitmurattal',
    'abdulbasit_mujawwad': 'ar.abdulbasitmurattal',
    'husary_mujawwad': 'ar.husarymujawwad',
    'husary_murattal': 'ar.husary',
    'ali_jaber': 'ar.alijaber',
    'sudais': 'ar.abdurrahmaansudais',
    'shuraim': 'ar.saoodshuraym',
    'maher_almuaiqly': 'ar.mahermuaiqly',
    'hudhaify': 'ar.hudhaify',
    'alafasy': 'ar.alafasy',
    'ghamadi': 'ar.saadalghamdi',
    'ajamy': 'ar.ahmedajamy',
    'shaatree': 'ar.shaatree',
}


def get_islamic_ayah_edition(reciter_id):
    return ISLAMIC_AYAH_EDITIONS.get(reciter_id)


def ayah_global_number(surah_num, ayah_num):
    """Converts surah:ayah to the global 1..6236 ayah number (uthmani order)."""
    total = 0
    for s in range(1, int(surah_num)):
        total += VERSE_COUNTS[s]
    return total + int(ayah_num)


# ============================================================
# 🇸🇦 ترتيب القراء السعوديين أولاً (التركيز الأساسي للمشروع)
#    يبدأ بالشيخ أحمد بن علي العجمي كما طُلب، ثم أئمة الحرمين
#    والقراء السعوديين، ثم الزمن الجميل كخيارات إضافية.
# ============================================================
SAUDI_RECITER_IDS = [
    'ajamy',              # الشيخ أحمد بن علي العجمي (الأولوية القصوى)
    'sudais',             # الشيخ عبدالرحمن السديس (إمام الحرم)
    'maher_almuaiqly',    # الشيخ ماهر المعيقلي (إمام الحرم)
    'shuraim',            # الشيخ سعود الشريم (إمام الحرم)
    'yasser_dussary',     # الشيخ ياسر الدوسري (إمام الحرم)
    'ghamadi',            # الشيخ سعد الغامدي
    'hudhaify',           # الشيخ علي الحذيفي (إمام المسجد النبوي)
    'shaatree',           # الشيخ أبو بكر الشاطري
    'ali_jaber',          # الشيخ علي جابر (إمام الحرم التاريخي)
]

# القائمة المرتبة للعرض والاختيار الدوري: السعوديون أولاً ثم البقية
RECITERS_ORDERED = []
for _rid in SAUDI_RECITER_IDS:
    _r = get_reciter_by_id(_rid)
    if _r and _r['id'] == _rid and _r not in RECITERS_ORDERED:
        RECITERS_ORDERED.append(_r)
for _r in RECITERS_CATALOG:
    if _r not in RECITERS_ORDERED:
        RECITERS_ORDERED.append(_r)

def is_saudi_reciter(reciter_id):
    return reciter_id in SAUDI_RECITER_IDS


# ============================================================
# 📖 جلب نصوص السورة كاملة دفعة واحدة (الرسم العثماني المُشكَّل)
#    - طلب HTTP واحد لكل السورة (سريع جداً بدل 286 طلب).
#    - كاش على القرص: outputs/audio/ayah_text/sNNN_full.json
#    - أبداً لا تنهار: تُرجع {} عند الفشل فيصبح النص "وضع العنوان".
# ============================================================
import json as _json
from pathlib import Path as _Path

_ENGINE_DIR = _Path(__file__).parent.resolve()
TEXT_FULL_CACHE_DIR = _ENGINE_DIR / "outputs" / "audio" / "ayah_text"

def fetch_surah_texts(surah_num, timeout=25):
    """تُرجع قاموساً {آية: نص عثماني} لكل آيات السورة (مع كاش دائم)."""
    try:
        s = int(surah_num)
        if not (1 <= s <= 114):
            return {}
        TEXT_FULL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = TEXT_FULL_CACHE_DIR / f"s{s:03d}_full.json"
        if cache_file.exists():
            try:
                return _json.loads(cache_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        import requests as _requests
        url = f"https://api.alquran.cloud/v1/surah/{s}/quran-uthmani"
        resp = _requests.get(url, timeout=timeout)
        resp.raise_for_status()
        data = resp.json().get("data") or {}
        ayahs = data.get("ayahs") or []
        out = {}
        for a in ayahs:
            n = int(a.get("numberInSurah") or 0)
            t = (a.get("text") or "").strip()
            if n and t:
                out[str(n)] = t
        if out:
            try:
                cache_file.write_text(_json.dumps(out, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass
        return out
    except Exception as e:
        # نسجل دون استيراد logger (تجنب دورية)
        print(f"[quran_data] fetch_surah_texts failed for {surah_num}: {e}")
        return {}
