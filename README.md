# 📖 Quran Reels Generator | أداة ومولد ريلز القرآن الكريم الآلي

<div align="center">

![Quran Reels Generator](https://img.shields.io/badge/Quran%20Reels-Generator-emerald?style=for-the-badge&logo=youtube)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-Automated%2024%2F7-2088FF?style=for-the-badge&logo=githubactions)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)

**أداة ذكية ومؤتمتة لإنشاء ورفع مقاطع فيديو قصيرة (Reels / Shorts) للقرآن الكريم بجودة فائقة وخلفيات طبيعية نقية 100%**  
*مشروع مفتوح المصدر ومجاني بالكامل بنية الصدقة الجارية ونشر كتاب الله ﷻ.*

[📖 دليل الإعداد التفصيلي (Setup Guide)](./SETUP_GUIDE.md) • [🇪🇬 العربية](#-اللغة-العربية) • [🇬🇧 English](#-english) • [📞 التواصل والدعم](#-الدعم-والتواصل--support)

</div>

---

## 🇪🇬 اللغة العربية

### 🌟 نبذة عن المشروع
هذا المشروع صُمم ليكون **صدقة جارية** مدى الحياة، حيث يعمل بنظام أتمتة متكامل يقوم يومياً وبشكل تلقائي بـ:
1. اختيار السورة والآيات القرآنية والقارئ بنظام دوري ذكي ومتتابع.
2. جلب التلاوة الصوتية العطرة والنص القرآني بالرسم العثماني المعتمد مع كامل التشكيل.
3. البحث في **Pexels API** عن مقاطع فيديو طبيعية خلابة (سحب، أنهار، جبال، أمطار، فضاء) مع فلترة صارمة تضمن عدم وجود أي أشخاص أو كائنات حية نهائياً.
4. مونتاج الفيديو آلياً بأبعاد طولية (9:16) وجودة عالية Full HD مع تزامن دقيق للآيات والصوتيات.
5. رفع الفيديو تلقائياً إلى قناتك على **YouTube** مع العنوان والوصف والوسوم المناسبة، وتوثيق سجل النشر في `state.json`.

---

### 🚀 أبرز المميزات
- **أتمتة سحابية مجانية 100%:** يعمل بدون توقف عبر **GitHub Actions** مرتين يومياً (أو حسب رغبتك) دون الحاجة لتشغيل جهازك أو شراء سيرفر مدفوع.
- **طبيعة نقية 100%:** فلاتر ذكية متعددة الطبقات لمنع ظهور الأشخاص أو الوجوه أو الكائنات.
- **تنوع القراء:** دعم لأكثر من 10 قراء من عمالقة التلاوة في العالم الإسلامي (المنشاوي، الحصري، عبدالباسط، العفاسي، المعيقلي، وغيرهم).
- **رسم عثماني أصيل:** محاذاة وتنسيق احترافي للنص القرآني مع التشكيل الكامل وعلامات الآيات.
- **واجهة مستخدم رسومية (UI):** يتضمن واجهة ويب أنيقة للإنشاء اليدوي المخصص عند الرغبة.
- **آمن ومفتوح المصدر:** نظام عزل تام للمفاتيح والبيانات الحساسة عبر متغيرات البيئة (`.env` و GitHub Secrets).

---

### ⚡ البدء السريع (Quick Start)

#### 1. التشغيل الآلي السحابي (GitHub Actions)
اتبع [📖 دليل الإعداد والتشغيل الشامل (SETUP_GUIDE.md)](./SETUP_GUIDE.md) المرفق في المشروع لمعرفة خطوات:
- إنشاء وتفعيل YouTube Data API v3 على Google Cloud Console.
- الحصول على مفتاح Pexels API المجاني.
- استخراج رمز الربط عبر السكربت المساعد `python setup_youtube.py`.
- وضع المفاتيح في GitHub Secrets وتشغيل البوت ليعمل مدى الحياة مجاناً.

#### 2. التشغيل المحلي على جهازك
```bash
# 1. استنساخ المستودع
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
cd Quran-Reels-Generator-main

# 2. تثبيت المكتبات المطلوبة
pip install -r requirements_auto.txt

# 3. إعداد المتغيرات البيئية
cp .env.example .env
# ثم قم بتعديل ملف .env وكتابة المفاتيح الخاصة بك

# 4. توليد ريلز تلقائياً
python auto_generate.py

# 5. أو تشغيل الواجهة الرسومية التفاعلية
pip install -r requirements.txt
python main.py
```

---

## 🇬🇧 English

### 🌟 Overview
An automated 24/7 engine designed to generate and publish high-quality Quran Reels/Shorts to YouTube. Built to serve as ongoing charity (*Sadaqah Jariyah*).

### ✨ Features
- **100% Free Cloud Automation:** Runs via **GitHub Actions** cron schedule twice daily without needing a paid server.
- **Strict 100% Elemental Nature:** Advanced negative keyword filtering ensures pure nature backgrounds (clouds, water, mountains, space, rain) with 0% humans or living beings.
- **Multiple Famous Reciters:** Supports Minshawi, Husary, Abdulbasit, Afasy, Al-Muaiqly, and more.
- **Authentic Uthmani Script:** High-quality Arabic rendering with full diacritics (Tashkeel).
- **Clean Architecture & Security:** Zero credential leaks; fully configured via environment variables and GitHub Secrets.

For detailed setup instructions, please see the [📖 Complete Setup Guide (SETUP_GUIDE.md)](./SETUP_GUIDE.md).

---

## 🔐 Environment Variables & Secrets | المفاتيح المطلوبة

| Variable / Secret | Description (الوصف) |
| :--- | :--- |
| `PEXELS_API_KEY` | Free API key for downloading HD nature video backgrounds |
| `YOUTUBE_CLIENT_ID` | Google OAuth Client ID from Google Cloud Console |
| `YOUTUBE_CLIENT_SECRET` | Google OAuth Client Secret from Google Cloud Console |
| `YOUTUBE_REFRESH_TOKEN` | YouTube OAuth Refresh Token generated via `setup_youtube.py` |

---

## 📞 الدعم والتواصل | Support

إذا كان لديك أي استفسار أو واجهت أي مشكلة أثناء إعداد وتشغيل البوت، نسعد بمساعدتك:

- 📧 **Email / البريد الإلكتروني:** `mostafabehaey66666@gmail.com`
- 💬 **GitHub Issues:** يمكنك فتح تذكرة (Issue) عبر المستودع.

---

<div align="center">

**«الدال على الخير كفاعله»**  
نسألكم صالح الدعاء بالمغفرة والرحمة لجميع موتى المسلمين 🤲

</div>
