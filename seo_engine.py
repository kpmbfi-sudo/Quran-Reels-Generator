# -*- coding: utf-8 -*-
"""
محرك السيو والكلمات المفتاحية المتقدم لليوتيوب (YouTube SEO Engine)
مخصص لإنتاج:
1. عناوين قوية متوافقة مع محركات البحث وخوارزميات يوتيوب (Exact Match & LSI).
2. أوصاف احترافية غنية بالكلمات الدلالية، دعوة صريحة للاشتراك، وهاشتاجات عالية البحث.
3. كلمات مفتاحية (Tags) ذكية بجميع صيغ البحث (مع همزة وبدون همزة، بالعامية والإنجليزية)،
   مع الالتزام الصارم بحد يوتيوب (480 حرف كحد أقصى لمنع أخطاء الرفع).

ملاحظة التسمية: يستخدم حصراً "أحمد العجمي" أو "العجمي" بناءً على طلب القناة،
دون إدراج الاسم الطويل "الشيخ أحمد بن علي العجمي" في العناوين والكلمات الدلالية لضمان أعلى ظهور في البحث.
"""

from typing import Dict, List, Optional
from quran_data import SURAH_NAMES, is_makki

# القارئ المعتمد والمثبت للقناة
DEFAULT_RECITER_NAME = "أحمد العجمي"
DEFAULT_RECITER_SHORT = "العجمي"

# أسماء السور الـ 114 باللغة الإنجليزية لتعزيز الظهور في البحث الدولي
SURAH_NAMES_EN = [
    'Al-Fatihah', 'Al-Baqarah', 'Ali Imran', 'An-Nisa', 'Al-Maidah', 'Al-Anam', 'Al-Araf', 'Al-Anfal', 'At-Tawbah', 'Yunus',
    'Hud', 'Yusuf', 'Ar-Rad', 'Ibrahim', 'Al-Hijr', 'An-Nahl', 'Al-Isra', 'Al-Kahf', 'Maryam', 'Taha',
    'Al-Anbiya', 'Al-Hajj', 'Al-Muminun', 'An-Nur', 'Al-Furqan', 'Ash-Shuara', 'An-Naml', 'Al-Qasas', 'Al-Ankabut', 'Ar-Rum',
    'Luqman', 'As-Sajdah', 'Al-Ahzab', 'Saba', 'Fatir', 'Ya-Sin', 'As-Saffat', 'Sad', 'Az-Zumar', 'Ghafir',
    'Fussilat', 'Ash-Shura', 'Az-Zukhruf', 'Ad-Dukhan', 'Al-Jathiyah', 'Al-Ahqaf', 'Muhammad', 'Al-Fath', 'Al-Hujurat', 'Qaf',
    'Adh-Dhariyat', 'At-Tur', 'An-Najm', 'Al-Qamar', 'Ar-Rahman', 'Al-Waqiah', 'Al-Hadid', 'Al-Mujadila', 'Al-Hashr', 'Al-Mumtahanah',
    'As-Saff', 'Al-Jumuah', 'Al-Munafiqun', 'At-Taghabun', 'At-Talaq', 'At-Tahrim', 'Al-Mulk', 'Al-Qalam', 'Al-Haqqah', 'Al-Maarij',
    'Nuh', 'Al-Jinn', 'Al-Muzzammil', 'Al-Muddaththir', 'Al-Qiyamah', 'Al-Insan', 'Al-Mursalat', 'An-Naba', 'An-Naziat', 'Abasa',
    'At-Takwir', 'Al-Infitar', 'Al-Mutaffifin', 'Al-Inshiqaq', 'Al-Buruj', 'At-Tariq', 'Al-Ala', 'Al-Ghashiyah', 'Al-Fajr', 'Al-Balad',
    'Ash-Shams', 'Al-Layl', 'Ad-Duha', 'Ash-Sharh', 'At-Tin', 'Al-Alaq', 'Al-Qadr', 'Al-Bayyinah', 'Az-Zalzalah', 'Al-Adiyat',
    'Al-Qariah', 'At-Takathur', 'Al-Asr', 'Al-Humazah', 'Al-Fil', 'Quraysh', 'Al-Maun', 'Al-Kawthar', 'Al-Kafirun', 'An-Nasr',
    'Al-Masad', 'Al-Ikhlas', 'Al-Falaq', 'An-Nas'
]


def strip_hamza(text: str) -> str:
    """إزالة الهمزات وتوحيد التاء المربوطة لتوليد كلمات بحث مطابقة للبحث الشائع."""
    if not text:
        return ""
    table = str.maketrans({
        'أ': 'ا', 'إ': 'ا', 'آ': 'ا',
        'ة': 'ه', 'ى': 'ي'
    })
    return text.translate(table)


def build_safe_tags(candidates: List[str], max_chars: int = 480) -> List[str]:
    """
    دمج وترشيح الكلمات المفتاحية (Tags) مع إزالة التكرار،
    والتأكد الصارم من أن إجمالي عدد الأحرف لا يتجاوز 480 حرفاً
    (حد يوتيوب هو 500 حرف بما فيها الفواصل، ونستخدم 480 كحد أمان تام لمنع أي خطأ 400).
    """
    tags: List[str] = []
    seen = set()
    total_len = 0

    for tag in candidates:
        tag = (tag or "").strip()
        if not tag or len(tag) < 2:
            continue
        key = tag.lower()
        if key in seen:
            continue
        # احتساب طول التاج مع الفاصلة (comma)
        added_len = len(tag) + (1 if tags else 0)
        if total_len + added_len > max_chars:
            continue
        tags.append(tag)
        seen.add(key)
        total_len += added_len

    return tags


def format_duration(seconds: float) -> str:
    """تنسيق المدة الزمنية بالدقائق والثواني."""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"


# ============================================================
# 1. سيو السورة الكاملة (Surah SEO)
# ============================================================
def generate_surah_seo(surah_num: int, ayahs_count: int, duration_seconds: float,
                       reciter_name: str = DEFAULT_RECITER_NAME) -> Dict[str, any]:
    """
    توليد حزمة السيو الكاملة لسورة قرآنية كاملة:
    - عنوان قوي متوافق 100% مع البحث.
    - وصف غني بالكلمات الدلالية مع دعوة الاشتراك ومعلومات السورة.
    - كلمات مفتاحية تغطي جميع صيغ البحث الشائعة عربياً وإنجليزياً.
    """
    surah_num = int(surah_num)
    surah_raw = SURAH_NAMES[surah_num - 1]
    surah_clean = surah_raw.replace("سورة", "").strip()
    surah_clean_no_hamza = strip_hamza(surah_clean)
    surah_en = SURAH_NAMES_EN[surah_num - 1] if 1 <= surah_num <= 114 else "Quran"
    revelation = "مكية" if is_makki(surah_num) else "مدنية"
    dur_str = format_duration(duration_seconds)

    # 1. العنوان (أقل من 95 حرف - يحقق Exact Match عالي جداً)
    title = f"سورة {surah_clean} كاملة | {reciter_name} 🌿 تلاوة خاشعة بالرسم العثماني"
    if len(title) > 95:
        title = f"سورة {surah_clean} كاملة | {reciter_name} 🌿 تلاوة خاشعة"

    # 2. الوصف (Description) - مصمم بدقة لخوارزميات اليوتيوب
    tag_hashtag = surah_clean.replace(" ", "_")
    description = f"""📖 سورة {surah_clean} كاملة ({ayahs_count} آية) بصوت القارئ {reciter_name}
تلاوة خاشعة وهادئة تريح القلب والنفس، مكتوبة بالرسم العثماني المصحف الشريف بجودة صوت نقية عالية.

🔔 اشترك في القناة الآن وفعل جرس التنبيهات 🔔 ليصلك جديد التلاوات اليومية والرقية الشرعية بصوت {reciter_name}.
اشتراكك في القناة ودعمك بالمشاركة والإعجاب هو صدقة جارية في ميزان حسناتك. 🌿

⏱️ معلومات التلاوة:
- القارئ: {reciter_name} ({DEFAULT_RECITER_SHORT})
- السورة: سورة {surah_clean} ({revelation})
- عدد الآيات: {ayahs_count} آية
- المدة: {dur_str} دقيقة
- الرسم: الخط العثماني المشكّل بالكامل

قال رسول الله ﷺ: «خَيْرُكُمْ مَنْ تَعَلَّمَ الْقُرْآنَ وَعَلَّمَهُ».
نسأل الله سبحانه أن يجعل هذا العمل خالصاً لوجهه الكريم وصدقة جارية لنا ولوالدينا ولجميع موتى المسلمين. 🤲

📌 كلمات دلالية للبحث:
سورة {surah_clean} كاملة | سورة {surah_clean} {reciter_name} | سورة {surah_clean_no_hamza} {strip_hamza(reciter_name)} | {reciter_name} سورة {surah_clean} | {DEFAULT_RECITER_SHORT} سورة {surah_clean} | قرآن كريم بصوت {reciter_name} | تلاوة خاشعة {reciter_name} | تلاوة هادئة للراحة النفسية والنوم | سورة {surah_clean} مكتوبة | Surah {surah_en} Ahmed Al-Ajamy | Surah {surah_en} Full

#{reciter_name.replace(' ', '_')} #{strip_hamza(reciter_name).replace(' ', '_')} #{DEFAULT_RECITER_SHORT} #سورة_{tag_hashtag} #القرآن_الكريم #تلاوة_خاشعة #قرآن_كريم #quran #صدقة_جارية"""

    # 3. الكلمات المفتاحية (Tags) - جميع التباديل الشائعة
    tag_candidates = [
        f"سورة {surah_clean} كاملة",
        f"سورة {surah_clean} {reciter_name}",
        f"سورة {surah_clean_no_hamza} {strip_hamza(reciter_name)}",
        f"سورة {surah_clean}",
        f"سورة {surah_clean_no_hamza}",
        reciter_name,
        strip_hamza(reciter_name),
        DEFAULT_RECITER_SHORT,
        f"{reciter_name} سورة {surah_clean}",
        f"{strip_hamza(reciter_name)} سورة {surah_clean_no_hamza}",
        f"{DEFAULT_RECITER_SHORT} سورة {surah_clean}",
        f"الشيخ {strip_hamza(reciter_name)}",
        f"الشيخ {reciter_name}",
        f"تلاوة خاشعة {reciter_name}",
        f"قرآن كريم {reciter_name}",
        f"سورة {surah_clean} كاملة {reciter_name}",
        "تلاوة خاشعة",
        "تلاوة هادئة",
        "تلاوة مريحة للنوم",
        "قرآن كريم",
        "القرآن الكريم",
        "سورة كاملة",
        "راحة نفسية",
        "تلاوة تريح القلب",
        "صدقة جارية",
        "quran",
        "ahmed al ajamy",
        "ahmed ajamy",
        f"surah {surah_en.lower()}",
        f"surah {surah_en.lower()} full",
        f"surah {surah_en.lower()} ahmed al ajamy",
    ]

    tags = build_safe_tags(tag_candidates, max_chars=480)

    return {
        "title": title,
        "description": description.strip(),
        "tags": tags,
        "surah_clean": surah_clean,
    }


# ============================================================
# 2. سيو الرقية الشرعية (Ruqyah SEO) - خالي تماماً من كلمة "سورة"
# ============================================================
def generate_ruqyah_seo(ruqyah_id: str, ruqyah_name: str, ruqyah_desc: str,
                        duration_seconds: float, ayahs_count: int = 0,
                        reciter_name: str = DEFAULT_RECITER_NAME) -> Dict[str, any]:
    """
    توليد حزمة السيو للرقية الشرعية بكتاب الله:
    - خالية تماماً من كلمة "سورة".
    - كلمات مفتاحية مركزة على الشفاء، التحصين، الحسد، السحر، العين، والراحة النفسية.
    """
    dur_str = format_duration(duration_seconds)
    rq_clean = ruqyah_name.strip()
    rq_no_hamza = strip_hamza(rq_clean)

    # 1. العنوان
    title = f"{rq_clean} | {reciter_name} 🤲 تحصين وشفاء بإذن الله"
    if len(title) > 95:
        title = f"{rq_clean} | {reciter_name} 🤲 رقية شرعية"

    # 2. الوصف
    description = f"""🤲 {rq_clean} بصوت القارئ {reciter_name}
📖 {ruqyah_desc}
رقية شرعية مباركة بآيات كتاب الله الحكيم لطرد الشياطين وجلب السكينة والشفاء للقلب والبدن والنفس.

🔔 لا تنسَ الاشتراك في القناة وتفعيل زر الجرس 🔔 ليصلك جديد الرقى الشرعية والتلاوات القرآنية بصوت {reciter_name}.
اشتراكك ودعمك بنشر الرقية صدقة جارية لوجه الله تعالى ولنفع كل مبتلى ومحتاج. 🌿

⏱️ معلومات الرقية:
- القارئ: {reciter_name} ({DEFAULT_RECITER_SHORT})
- الرقية: {rq_clean}
- المدة: {dur_str} دقيقة
- المصدر: آيات مباركة من كتاب الله عز وجل

الشفاء بيد الله وحده، والقرآن شفاء ورحمة للمؤمنين: ﴿وَنُنَزِّلُ مِنَ الْقُرْآنِ مَا هُوَ شِفَاءٌ وَرَحْمَةٌ لِلْمُؤْمِنِينَ﴾.
احرص على الاستماع إليها يومياً بيقين وتدبر، وتشغيلها في أرجاء البيت للتحصين وطرد الطاقة السلبية. 🤲

📌 كلمات دلالية للبحث:
الرقية الشرعية {reciter_name} | رقية شرعية {strip_hamza(reciter_name)} | {rq_clean} {reciter_name} | {rq_no_hamza} {DEFAULT_RECITER_SHORT} | {reciter_name} رقية شرعية | رقية العين والحسد {reciter_name} | رقية السحر والمس | رقية النوم وراحة البال | تحصين البيت والأولاد | أقوى رقية شرعية | Ruqyah Ahmed Al Ajamy | Ruqyah Shariah

#الرقية_الشرعية #رقية_شرعية #{reciter_name.replace(' ', '_')} #{strip_hamza(reciter_name).replace(' ', '_')} #{DEFAULT_RECITER_SHORT} #تحصين_البيت #علاج_الحسد #علاج_السحر #قرآن_كريم #quran #صدقة_جارية"""

    # 3. الكلمات المفتاحية (Tags)
    tag_candidates = [
        f"الرقية الشرعية {reciter_name}",
        f"الرقية الشرعية {strip_hamza(reciter_name)}",
        f"رقية شرعية {reciter_name}",
        f"رقية شرعية {strip_hamza(reciter_name)}",
        f"{rq_clean} {reciter_name}",
        f"{rq_no_hamza} {strip_hamza(reciter_name)}",
        "الرقية الشرعية",
        "رقية شرعية",
        "الرقيه الشرعيه",
        "رقيه شرعيه",
        rq_clean,
        rq_no_hamza,
        reciter_name,
        strip_hamza(reciter_name),
        DEFAULT_RECITER_SHORT,
        f"{reciter_name} رقية شرعية",
        f"{strip_hamza(reciter_name)} رقية شرعية",
        f"{DEFAULT_RECITER_SHORT} رقية شرعية",
        "الرقية الشرعية الشاملة",
        "الرقيه الشرعيه الشامله",
        "رقية العين والحسد",
        "رقية السحر",
        "رقية المس",
        "رقية النوم",
        "تحصين البيت",
        "تحصين النفس",
        "علاج ضيق الصدر",
        "شفاء وسكينة",
        "صدقة جارية",
        "ruqyah",
        "ruqyah shariah",
        "ruqyah ahmed al ajamy",
        "ahmed ajamy ruqyah",
        "islamic healing"
    ]

    tags = build_safe_tags(tag_candidates, max_chars=480)

    return {
        "title": title,
        "description": description.strip(),
        "tags": tags,
    }


# ============================================================
# 3. سيو تجميع السور (Compilation SEO) - بصيغة الجمع "سُوَر"
# ============================================================
def generate_compilation_seo(comp_title: str, duration_seconds: float, ayahs_count: int = 0,
                             reciter_name: str = DEFAULT_RECITER_NAME) -> Dict[str, any]:
    """
    توليد حزمة السيو لتجميعات السور القرآنية:
    - استخدام صيغة الجمع "سُوَر" أو العنوان المعتمد دون إدراج لفظ "سورة" بالمفرد.
    - كلمات مفتاحية مخصصة للراحة النفسية والنوم والسكينة وتلاوات القارئ.
    """
    dur_str = format_duration(duration_seconds)
    comp_clean = comp_title.strip()
    if not comp_clean.startswith("سور") and not comp_clean.startswith("سُوَر"):
        comp_display = f"سُوَر {comp_clean}" if " | " not in comp_clean else comp_clean
    else:
        comp_display = comp_clean
    comp_no_hamza = strip_hamza(comp_display)

    # 1. العنوان
    title = f"{comp_display} | {reciter_name} 🌿 تلاوة خاشعة تريح القلب"
    if len(title) > 95:
        title = f"{comp_display} | {reciter_name} 🌿 تلاوة خاشعة"

    # 2. الوصف
    description = f"""📖 {comp_display} بصوت القارئ {reciter_name}
تلاوة قرآنية مباركة خاشعة وهادئة تبعث الطمأنينة والسكينة في القلب، وتريح النفس والبال.

🔔 اشترك الآن في القناة وفعل جرس التنبيهات 🔔 ليصلك كل جديد من روائع التلاوات والرقية الشرعية بصوت {reciter_name}.
اشتراكك ودعمك المستمر صدقة جارية تساهم في نشر كلام الله تعالى. 🌿

⏱️ معلومات التلاوة:
- القارئ: {reciter_name} ({DEFAULT_RECITER_SHORT})
- المحتوى: {comp_display}
- عدد الآيات: {ayahs_count} آية
- المدة: {dur_str} دقيقة

قال الله تعالى: ﴿الَّذِينَ آمَنُوا وَتَطْمَئِنُّ قُلُوبُهُمْ بِذِكْرِ اللَّهِ أَلَا بِذِكْرِ اللَّهِ تَطْمَئِنُّ الْقُلُوبُ﴾.
نسأل الله العلي القدير أن يتقبل منا ومنكم صالح الأعمال، وأن يجعل القرآن شفيعاً لنا يوم القيامة. 🤲

📌 كلمات دلالية للبحث:
{comp_display} {reciter_name} | {comp_no_hamza} {strip_hamza(reciter_name)} | {reciter_name} تلاوة خاشعة | {DEFAULT_RECITER_SHORT} تلاوة هادئة | تلاوة مريحة للنوم والراحة النفسية | سور قصيرة {reciter_name} | جزء عم {reciter_name} | جزء تبارك {reciter_name} | تلاوة قرآنية مجمعة | Quran Recitation Ahmed Al Ajamy

#{reciter_name.replace(' ', '_')} #{strip_hamza(reciter_name).replace(' ', '_')} #{DEFAULT_RECITER_SHORT} #القرآن_الكريم #تلاوة_خاشعة #تلاوة_هادئة #قرآن_كريم #quran #صدقة_جارية"""

    # 3. الكلمات المفتاحية (Tags)
    tag_candidates = [
        f"{comp_display} {reciter_name}",
        f"{comp_no_hamza} {strip_hamza(reciter_name)}",
        comp_display,
        comp_no_hamza,
        reciter_name,
        strip_hamza(reciter_name),
        DEFAULT_RECITER_SHORT,
        f"{reciter_name} تلاوة خاشعة",
        f"{strip_hamza(reciter_name)} تلاوة خاشعة",
        f"{reciter_name} تلاوة هادئة",
        f"{DEFAULT_RECITER_SHORT} تلاوة خاشعة",
        f"قرآن كريم {reciter_name}",
        f"قرآن كريم {strip_hamza(reciter_name)}",
        "تلاوة خاشعة",
        "تلاوة هادئة",
        "تلاوة مريحة للنوم",
        "قرآن كريم",
        "القرآن الكريم",
        "تلاوة تريح القلب",
        "راحة نفسية",
        "سور قصيرة",
        "جزء عم",
        "جزء تبارك",
        "صدقة جارية",
        "quran",
        "quran recitation",
        "ahmed al ajamy",
        "ahmed ajamy",
        "peaceful quran"
    ]

    tags = build_safe_tags(tag_candidates, max_chars=480)

    return {
        "title": title,
        "description": description.strip(),
        "tags": tags,
    }
