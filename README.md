# 📖 Quran Reels Generator | أداة ومولّد فيديوهات القرآن الكريم الآلي

<div align="center">

![Quran Reels Generator](https://img.shields.io/badge/Quran%20Reels-Generator-emerald?style=for-the-badge&logo=youtube)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-Automated%2024%2F7-2088FF?style=for-the-badge&logo=githubactions)
![Engine](https://img.shields.io/badge/Engine-Unified%20Long--Video-d4af37?style=for-the-badge)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)

**مصنع فيديوهات قرآنية متكامل الآلية: سور كاملة طويلة + ريلز يومية، بخلفيات طبيعية نقية 100% من Pexels، ونص عثماني مُشكَّل متزامن مع كل آية.**  
*مشروع مفتوح المصدر ومجاني بالكامل بنية الصدقة الجارية ونشر كتاب الله ﷻ.*

[📖 دليل الإعداد التفصيلي](./SETUP_GUIDE.md) • [🇪🇬 العربية](#-اللغة-العربية) • [🇬🇧 English](#-english) • [🛠️ البنية التقنية](#-البنية-التقنية)

</div>

---

## 🇪🇬 اللغة العربية

### 🌟 نبذة عن المشروع
هذا المشروع صُمم ليكون **صدقة جارية** مدى الحياة. محرك واحد موحّد وقوي يقوم يومياً وتلقائياً بـ:
1. اختيار السورة والقارئ بنظام دوري ذكي (مع **تركيز على القراء السعوديين**: الشيخ العجمي، السديس، المعيقلي، الشريم، الدوسري...).
2. جلب التلاوة الصوتية (آية-آية لتزامن دقيق + كاش دائم + تنزيل متوازي + قص الصمت).
3. جلب النص القرآني **بالرسم العثماني المُشكَّل** وعرضه متزامناً مع كل آية على هيئة "صفحات مصحف".
4. البحث في **Pexels API** عن مقاطع فيديو طبيعية خلابة مع فلترة صارمة تضمن 0% بشر أو كائنات حية (مع احتياطي تلقائي للخلفيات المحلية).
5. مونتاج سينمائي عبر **FFmpeg + تسريع العتاد (QSV)** — ساعات طويلة برامات منخفضة.
6. الرفع التلقائي على **YouTube** (فيديو طويل + شورتس بمشاريع OAuth منفصلة) وتوثيق النشر في `state.json`.

### 🚀 أبرز المميزات
- **🎬 محرك موحّد قوي للفديوهات الطويلة:** السورة الكاملة (من 10 ثوانٍ حتى ساعتين+) — النص العثماني يظهر متزامناً مع كل آية بنفس فكرة الريلز تماماً، مقسّماً إلى صفحات مصحف أنيقة.
- **🌿 خلفيات طبيعية تلقائية من Pexels:** طبقة Pexels موحدة مع 20 استعلام + فلتر ثلاثي صارم (URL + tags + المصور) — 100% طبيعة نقية. احتياطي تلقائي للخلفيات المحلية (دائماً يعمل، بدون مشاكل).
- **🇸🇦 القراء السعوديون أولاً:** كتالوج 22 قارئاً مع ترتيب خاص لأئمة الحرم والقراء السعوديين.
- **⚡ أداء عالي:** FFmpeg خالص + تسريع Intel QSV + تنزيل متوازي للآيات (سورة 40 آية في دقيقتين) + كاش دائم.
- **🛡️ متانة مطلقة:** مرايا متعددة لكل قارئ، fallback آية-آية، حلقة ضبط حجم الخط (لا مربعات Tofu أبداً)، معالجة مشاكل IPv6/WE/اتصالات، تخطّي الآيات الفاشلة دون التوقف.
- **☁️ أتمتة سحابية مجانية 100%:** يعمل عبر **GitHub Actions** (ريلز 2× يومياً + فيديو طويل 1× يومياً) دون سيرفر مدفوع.
- **🖥️ واجهة ويب احترافية:** استوديو كامل للإنشاء اليدوي (سورة كاملة/مجموعة آيات/رقية شرعية/تجميع سور) + رفع بضغطة + تشغيل تلقائي مع ويندوز.

---

### ⚡ البدء السريع

#### التشغيل الآلي السحابي (GitHub Actions)
اتبع [📖 دليل الإعداد الشامل](./SETUP_GUIDE.md):
1. مفتاح **Pexels** المجاني → `PEXELS_API_KEY`
2. مشروع Google + YouTube Data API v3 → `YOUTUBE_*` (واختيارياً `LONG_YOUTUBE_*` للفيديو الطويل)
3. رمز الربط عبر `python setup_youtube.py`

#### التشغيل المحلي
```bash
git clone https://github.com/kpmbfi-sudo/Quran-Reels-Generator.git
cd Quran-Reels-Generator
pip install -r requirements.txt
cp .env.example .env   # ثم ضع مفاتيحك
python main.py         # يفتح الاستوديو على http://127.0.0.1:5000
```

#### الفيديو الطويل من سطر الأوامر
```bash
python auto_generate.py --long          # سورة كاملة + رفع يوتيوب
python auto_generate.py --long --test   # بدون رفع (تجربة)
```

---

### 🛠️ البنية التقنية

```
Quran-Reels-Generator/
├── 🎬 quran_engine.py      المحرك الموحّد القوي (FFmpeg + QSV + التزامن)
├── 📖 quran_data.py        114 سورة + 22 قارئاً + ترتيب السعوديين أولاً
├── ☁️ pexels_api.py        طبقة Pexels الموحدة (بحث/فلترة/تنزيل/كاش)
├── 🚀 auto_generate.py     المسار السحابي: --long (طويل) / افتراضي (ريلز)
├── 🖥️ main.py + templates/ استوديو الويب (Flask + RTL ذهبي)
├── 🎥 youtube_uploader.py  رفع OAuth2 (dual-project: SHORTS_* / LONG_*)
├── 📝 youtube_manager.py   ميتاداتا SEO ذكية + تشخيص شبكة
├── 📿 ruqyah_data.py       6 رقيات شرعية موثقة (آيات حية من alquran.cloud)
├── ⚙️ setup_youtube.py     توليد رمز الربط بضغطة
└── .github/workflows/
    ├── daily_quran_reel.yml   ريلز 2× يومياً (6AM/6PM UTC)
    └── daily_long_video.yml   سورة كاملة 1× يومياً (9AM UTC)
```

**سياسة المحتوى الصارمة:** 100% طبيعة عنصرية (سحب/ماء/جبال/فضاء/مطر) — 0% بشر، 0% حيوانات، 0% كائنات حية (فلترة على URL + الوسوم + المصور).

---

## 🇬🇧 English

### 🌟 Overview
A fully automated engine that generates and publishes high-quality Quran videos to YouTube — built as ongoing charity (*Sadaqah Jariyah*). A single unified engine powers **full long videos** (Uthmani script synced with every ayah) and **daily reels**, over pure-nature backgrounds fetched automatically from Pexels.

### ✨ Features
- **Unified Long-Video Engine:** Full surahs (10s → 2h+) with Uthmani script synchronized per ayah as elegant "mushaf pages".
- **Automatic Pexels Backgrounds:** 20 curated queries + strict 3-layer purity filter (URL/tags/photographer) — pure nature only, with automatic local fallback.
- **Saudi Reciters First:** 22 reciters with a special ordering for Saudi/Haram imams (Ajamy, Sudais, Al-Muaiqly, Shuraim, Al-Dossary...).
- **High Performance:** Raw FFmpeg + Intel QSV + parallel ayah downloads + permanent cache (40-ayah surah in ~2 minutes).
- **Bulletproof Resilience:** Multi-mirror audio, ayah-by-ayah fallback, font-cmap guard (no tofu), IPv4-first networking, skip-and-continue on failures.
- **100% Free Cloud Automation:** GitHub Actions (reels 2×/day + long video 1×/day) — no paid server.

See the [📖 Complete Setup Guide](./SETUP_GUIDE.md) for step-by-step instructions.

---

## 🔐 Environment Variables & Secrets | المفاتيح المطلوبة

| Variable | Required | Description (الوصف) |
| :--- | :---: | :--- |
| `PEXELS_API_KEY` | ✅ | Free key for HD nature backgrounds — https://www.pexels.com/api/ |
| `YOUTUBE_CLIENT_ID` | ✅ | Google OAuth Client ID (Cloud Console) |
| `YOUTUBE_CLIENT_SECRET` | ✅ | Google OAuth Client Secret |
| `YOUTUBE_REFRESH_TOKEN` | ✅ | Generated via `python setup_youtube.py` |
| `LONG_YOUTUBE_CLIENT_ID` | ➖ | Separate project for the daily long video (dual-project) |
| `LONG_YOUTUBE_CLIENT_SECRET` | ➖ | Same as above |
| `LONG_YOUTUBE_REFRESH_TOKEN` | ➖ | Same as above |
| `TELEGRAM_BOT_TOKEN` | ➖ | Optional success/failure notifications |
| `TELEGRAM_CHAT_ID` | ➖ | Optional notifications chat id |

> 🔔 **هام:** تأكد أن تطبيق Google **منشور (Published)** وليس في وضع Testing، وإلا انتهت صلاحية الرمز كل 7 أيام. (OAuth consent screen → Publish App)

---

## 📞 الدعم والتواصل | Support

إذا كان لديك أي استفسار أو واجهت أي مشكلة، نسعد بمساعدتك:

- 📧 **Email / البريد الإلكتروني:** `mostafabehaey66666@gmail.com`
- 💬 **GitHub Issues:** افتح تذكرة عبر المستودع.

---

<div align="center">

**«الدال على الخير كفاعله»**  
نسألكم صالح الدعاء بالمغفرة والرحمة لجميع موتى المسلمين 🤲

</div>
