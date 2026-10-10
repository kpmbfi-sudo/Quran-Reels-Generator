# -*- coding: utf-8 -*-
"""
Ruqyah Data Module - الرقية الشرعية
Authentic ruqyah presets composed ONLY of verified Quranic verse ranges.
- No verse text is hardcoded here: audio comes from EveryAyah per-ayah files and
  on-screen text is fetched live from api.alquran.cloud (uthmani), so Allah's
  words can never contain a typo from our side.
- Every (surah, start, end) below was validated against VERSE_COUNTS.
"""

from quran_data import SURAH_NAMES, VERSE_COUNTS

# Each segment: (surah_num, start_ayah, end_ayah)
RUQYAH_TYPES = [
    {
        "id": "complete",
        "name": "الرقية الشرعية الشاملة",
        "description": "تحصين شامل: الفاتحة + خواتيم البقرة + آيات السحر + الصافات + الحشر + المعوذات",
        "hook": "الرقية الشرعية الكاملة | تحصين شامل بإذن الله",
        "segments": [
            (1, 1, 7), (2, 1, 5), (2, 255, 255), (2, 284, 286),
            (7, 117, 122), (10, 81, 82), (20, 69, 69),
            (37, 1, 10), (59, 21, 24), (72, 1, 5),
            (68, 51, 52), (112, 1, 4), (113, 1, 5), (114, 1, 6),
        ],
    },
    {
        "id": "hasad",
        "name": "رقية الحسد والعين",
        "description": "للعين والحسد: الفاتحة + الكرسي + خواتيم البقرة + (وإن يكاد) + المعوذات",
        "hook": "رقية الحسد والعين | راحة للأعصاب",
        "segments": [
            (1, 1, 7), (2, 255, 255), (2, 284, 286),
            (68, 51, 52), (112, 1, 4), (113, 1, 5), (114, 1, 6),
        ],
    },
    {
        "id": "sihr",
        "name": "رقية السحر وإبطاله",
        "description": "لإبطال السحر بإذن الله: آية البقرة 102 + آيات موسى + طه + المعوذات",
        "hook": "رقية إبطال السحر | بإذن الله الشفاء",
        "segments": [
            (1, 1, 7), (2, 102, 102),
            (7, 117, 122), (10, 81, 82), (20, 69, 69),
            (112, 1, 4), (113, 1, 5), (114, 1, 6),
        ],
    },
    {
        "id": "jinn",
        "name": "رقية المس والجن والتحصين",
        "description": "للتحصين: الكرسي + الصافات + الأحقاف + الجن + الحشر + المؤمنون + المعوذات",
        "hook": "رقية التحصين من الجن | نوم آمن بإذن الله",
        "segments": [
            (1, 1, 7), (2, 255, 255), (37, 1, 10),
            (46, 29, 32), (72, 1, 9), (59, 21, 24),
            (23, 115, 118), (112, 1, 4), (113, 1, 5), (114, 1, 6),
        ],
    },
    {
        "id": "sleep",
        "name": "رقية النوم والسكينة",
        "description": "للأرق والقلق: الكرسي + خواتيم البقرة + الملك + الشرح + المعوذات",
        "hook": "رقية النوم العميق | سكينة وطمأنينة",
        "segments": [
            (1, 1, 7), (2, 255, 255), (2, 284, 286),
            (67, 1, 5), (94, 1, 8),
            (112, 1, 4), (113, 1, 5), (114, 1, 6),
        ],
    },
    {
        "id": "rizq",
        "name": "رقية الرزق وتيسير الحال",
        "description": "للبركة والفرج: آيات الصدقة + (ومن يتق الله) + الواقعة + الشرح + المعوذات",
        "hook": "رقية الرزق وتيسير الحال | بركة وفرج",
        "segments": [
            (1, 1, 7), (2, 261, 267), (11, 6, 6),
            (65, 2, 3), (56, 1, 11), (94, 1, 8),
            (112, 1, 4), (113, 1, 5), (114, 1, 6),
        ],
    },
]

MAX_RUQYAH_AYAHS = 120


def get_ruqyah_by_id(ruqyah_id):
    for r in RUQYAH_TYPES:
        if r["id"] == ruqyah_id:
            return r
    return RUQYAH_TYPES[0]


def validate_ruqyah_segments(segments):
    """Raises ValueError if any segment is out of range. Returns total ayah count."""
    total = 0
    for seg in segments:
        s, a, b = int(seg[0]), int(seg[1]), int(seg[2])
        if s not in VERSE_COUNTS:
            raise ValueError(f"رقم السورة غير صالح في الرقية: {s}")
        max_v = VERSE_COUNTS[s]
        if not (1 <= a <= max_v and 1 <= b <= max_v and a <= b):
            raise ValueError(
                f"مدى آيات غير صالح في الرقية: سورة {SURAH_NAMES[s-1]} ({a}-{b})"
            )
        total += (b - a + 1)
    if total > MAX_RUQYAH_AYAHS:
        raise ValueError(
            f"الرقية طويلة جداً ({total} آية). الحد الأقصى {MAX_RUQYAH_AYAHS} آية."
        )
    return total


def describe_segments(segments):
    """Human-readable Arabic summary, e.g. 'الفاتحة 1-7 + الكرسي + ...'."""
    parts = []
    for (s, a, b) in segments:
        name = SURAH_NAMES[s - 1]
        if a == b:
            parts.append(f"{name} ({a})")
        else:
            parts.append(f"{name} ({a}-{b})")
    return " + ".join(parts)
