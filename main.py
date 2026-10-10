# -*- coding: utf-8 -*-
"""
Quran Studio - Backend Server
Unified local server providing video generation APIs, background library management,
YouTube one-click publishing, and auto-start settings.
"""

import os
import sys

# Ensure UTF-8 output on Windows consoles
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import json
import datetime
import logging
import warnings
# Hide harmless Google library nag about Python version (studio works fine on 3.10)
warnings.filterwarnings("ignore", category=FutureWarning)
import threading
import webbrowser
from pathlib import Path
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS

from quran_data import SURAH_NAMES, VERSE_COUNTS, is_makki, RECITERS_CATALOG
from quran_engine import (
    render_quran_video, render_ruqyah_video, render_compilation_video,
    generate_thumbnail_image,
    get_local_backgrounds, BACKGROUNDS_DIR,
    THUMBNAILS_DIR, OUTPUTS_DIR, VIDEO_OUT_DIR, ENGINE_VERSION,
    is_qsv_available, kill_current_ffmpeg
)
from youtube_manager import (
    check_youtube_auth, generate_video_metadata,
    generate_ruqyah_metadata, generate_compilation_metadata,
    upload_to_youtube, diagnose_upload_connection
)
from ruqyah_data import RUQYAH_TYPES, get_ruqyah_by_id
from setup_autostart import is_autostart_enabled, enable_autostart, disable_autostart

if getattr(sys, 'frozen', False):
    _exe_dir = Path(sys.executable).parent.resolve()
    _cands = (_exe_dir, *list(_exe_dir.parents)[:4])
    BASE_DIR = next((c for c in _cands
                     if (c / "templates").is_dir() and (c / "fonts").is_dir()), _exe_dir)
else:
    BASE_DIR = Path(__file__).parent.resolve()
STATE_FILE = BASE_DIR / "state.json"

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(BASE_DIR / "studio.log", encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder=str(BASE_DIR / "templates"), static_folder=str(BASE_DIR / "static"))
CORS(app)

# Global progress state
generation_state = {
    'is_running': False,
    'percent': 0,
    'status': 'في انتظار بدء العملية...',
    'logs': [],
    'result': None,
    'error': None,
    'is_complete': False
}

def load_state_data():
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"total_generated": 0, "history": []}

def save_state_data(data):
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving state: {e}")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/backgrounds/<path:filename>')
def serve_background(filename):
    return send_from_directory(str(BACKGROUNDS_DIR), filename)

@app.route('/thumbnails/<path:filename>')
def serve_thumbnail(filename):
    return send_from_directory(str(THUMBNAILS_DIR), filename)

@app.route('/outputs/<path:filename>')
def serve_output(filename):
    return send_from_directory(str(OUTPUTS_DIR), filename)

@app.route('/api/config', methods=['GET'])
def get_config():
    state = load_state_data()
    surahs_list = []
    for idx, name in enumerate(SURAH_NAMES, start=1):
        surahs_list.append({
            'number': idx,
            'name': name,
            'verses_count': VERSE_COUNTS[idx],
            'revelation': 'مكية' if is_makki(idx) else 'مدنية'
        })

    return jsonify({
        'surahs': surahs_list,
        'reciters': RECITERS_CATALOG,
        'total_generated': state.get('total_generated', 0)
    })

@app.route('/api/backgrounds', methods=['GET'])
def list_backgrounds():
    bgs = get_local_backgrounds()
    return jsonify(bgs)

@app.route('/api/upload-background', methods=['POST'])
def upload_background():
    if 'video' not in request.files:
        return jsonify({'success': False, 'error': 'لم يتم تحديد ملف'}), 400

    file = request.files['video']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'اسم الملف غير صالح'}), 400

    # World-class: accept any video OR image as background (images loop as still video)
    allowed = {'.mp4', '.mov', '.mkv', '.avi', '.webm', '.jpg', '.jpeg', '.png', '.webp', '.bmp'}
    filename = Path(file.filename).name
    ext = Path(filename).suffix.lower()
    if ext not in allowed:
        return jsonify({'success': False, 'error': f'صيغة غير مدعومة ({ext}). المدعوم: فيديو mp4/mov أو صورة jpg/png'}), 400

    # Sanitize filename to avoid path traversal
    filename = "".join(c for c in filename if c.isalnum() or c in ('_', '-', '.', ' ')).strip() or f"bg{ext}"
    save_path = BACKGROUNDS_DIR / filename
    file.save(str(save_path))

    # Refresh/create thumbnails
    get_local_backgrounds()

    return jsonify({'success': True, 'filename': filename})

def generation_worker(params):
    global generation_state
    try:
        def on_progress(p, msg):
            generation_state['percent'] = p
            generation_state['status'] = msg
            generation_state['logs'].append(f"[{p}%] {msg}")

        # --- Universal validation: any image + any sound must work ---
        try:
            surah_num = int(params.get('surah', 1))
        except (TypeError, ValueError):
            raise ValueError("رقم السورة غير صالح")
        if not (1 <= surah_num <= 114):
            raise ValueError("رقم السورة يجب أن يكون بين 1 و 114")

        reciter_id = str(params.get('reciter', '')).strip()
        if not reciter_id:
            raise ValueError("يجب اختيار القارئ")
        # Fallback to first reciter if unknown id (any sound works)
        from quran_data import get_reciter_by_id, VERSE_COUNTS as _VC
        _rec = get_reciter_by_id(reciter_id)
        reciter_id = _rec['id']

        mode = params.get('mode', 'full')
        if mode not in ('full', 'range'):
            mode = 'full'

        max_v = _VC[surah_num]
        try:
            start_ayah = int(params.get('startAyah', 1) or 1)
            end_ayah = int(params.get('endAyah', max_v) or max_v)
        except (TypeError, ValueError):
            start_ayah, end_ayah = 1, max_v
        start_ayah = max(1, min(start_ayah, max_v))
        end_ayah = max(1, min(end_ayah, max_v))
        if end_ayah < start_ayah:
            start_ayah, end_ayah = end_ayah, start_ayah

        aspect = params.get('aspectRatio', '16:9')
        if aspect not in ('16:9', '9:16'):
            aspect = '16:9'

        vintage = params.get('vintageEffect', 'black_and_white')
        # 'auto' = smart mood matching inside engine (sound+image mood)
        if vintage not in ('black_and_white', 'sepia', 'fog', 'grain_vignette', 'none', 'auto'):
            vintage = 'black_and_white'

        speed = params.get('speedMode', 'max')
        if speed not in ('max', 'balanced'):
            speed = 'max'

        bg_file = params.get('backgroundVideo')
        if isinstance(bg_file, str):
            bg_file = bg_file.strip() or None

        res = render_quran_video(
            surah_num=surah_num,
            reciter_id=reciter_id,
            mode=mode,
            start_ayah=start_ayah,
            end_ayah=end_ayah,
            bg_video_filename=bg_file,
            aspect_ratio=aspect,
            vintage_effect=vintage,
            speed_mode=speed,
            progress_callback=on_progress,
            caption_mode=params.get('captionMode', 'sync'),
            pexels_mode=params.get('pexelsMode', 'auto'),
            pexels_api_key=os.environ.get('PEXELS_API_KEY', ''),
        )

        # Generate smart YouTube metadata
        is_shorts = (aspect == '9:16')
        yt_meta = generate_video_metadata(
            surah_num=surah_num,
            reciter_name=res['reciter_name'],
            mode=mode,
            start_ayah=start_ayah,
            end_ayah=end_ayah,
            is_shorts=is_shorts
        )
        res['youtube_metadata'] = yt_meta

        # Auto thumbnail (same video frame + hook or default title)
        try:
            from pathlib import Path as _P
            hook = (params.get('hookText') or '').strip()
            thumb_name = _P(res['filename']).stem + "_thumb.jpg"
            thumb_path = str(VIDEO_OUT_DIR / thumb_name)
            generate_thumbnail_image(
                res['video_path'],
                hook or f"سورة {res['surah_name']} كاملة",
                small_title=res['reciter_name'],
                out_path=thumb_path)
            res['thumbnail'] = thumb_path
            res['thumbnail_url'] = f"/outputs/video/{thumb_name}"
        except Exception as e:
            logger.warning(f"Thumbnail auto-gen failed: {e}")

        # Update persistent state counter
        state = load_state_data()
        state['total_generated'] = state.get('total_generated', 0) + 1
        state['history'].append({
            'filename': res['filename'],
            'surah': res['surah_name'],
            'reciter': res['reciter_name'],
            'duration': res['duration'],
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        save_state_data(state)

        generation_state['result'] = res
        generation_state['is_complete'] = True
        generation_state['status'] = 'تم الانتهاء بنجاح!'
        generation_state['percent'] = 100

    except Exception as e:
        logger.error(f"Generation worker failed: {e}", exc_info=True)
        generation_state['error'] = str(e)
        generation_state['status'] = f"خطأ: {str(e)}"
    finally:
        generation_state['is_running'] = False

@app.route('/api/generate', methods=['POST'])
def start_generation():
    global generation_state
    if generation_state['is_running']:
        return jsonify({'success': False, 'error': 'عملية إنشاء فيديو قيد التنفيذ حالياً'}), 400

    data = request.json or {}
    
    # Reset state
    generation_state = {
        'is_running': True,
        'percent': 0,
        'status': 'جاري بدء العملية وتجهيز الملفات...',
        'logs': ['بدء العملية...'],
        'result': None,
        'error': None,
        'is_complete': False
    }

    thread = threading.Thread(target=generation_worker, args=(data,), daemon=True)
    thread.start()

    return jsonify({'success': True, 'message': 'تم بدء العملية'})

@app.route('/api/progress', methods=['GET'])
def get_progress():
    return jsonify(generation_state)

@app.route('/api/youtube/status', methods=['GET'])
def youtube_status():
    ok, msg = check_youtube_auth()
    return jsonify({'connected': ok, 'message': msg})

@app.route('/api/youtube/diag', methods=['GET'])
def youtube_diag():
    """Professional pre-upload network check (IPv4 vs IPv6 to Google APIs)."""
    try:
        return jsonify(diagnose_upload_connection())
    except Exception as e:
        logger.error(f"YouTube diag failed: {e}", exc_info=True)
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/ruqyah/types', methods=['GET'])
def ruqyah_types():
    from ruqyah_data import validate_ruqyah_segments
    out = []
    for r in RUQYAH_TYPES:
        try:
            total = validate_ruqyah_segments(r["segments"])
        except Exception:
            total = None
        out.append({
            'id': r['id'], 'name': r['name'], 'description': r['description'],
            'hook': r['hook'], 'total_ayahs': total,
            'segments_count': len(r['segments']),
        })
    return jsonify(out)

@app.route('/api/youtube/start-auth', methods=['POST'])
def start_youtube_auth():
    """Launches setup_youtube.py in a background process to authenticate in browser."""
    try:
        import subprocess
        subprocess.Popen([sys.executable, str(BASE_DIR / "setup_youtube.py")])
        return jsonify({'success': True, 'message': 'تم فتح المتصفح لتسجيل الدخول وربط القناة'})
    except Exception as e:
        logger.error(f"Failed to start YouTube auth: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/youtube/publish', methods=['POST'])
def publish_youtube():
    data = request.json or {}
    video_path = data.get('videoPath')
    title = data.get('title')
    description = data.get('description')
    privacy_status = data.get('privacyStatus', 'public')

    if not video_path or not os.path.exists(video_path):
        return jsonify({'success': False, 'error': 'ملف الفيديو المطلوب غير موجود'}), 400

    try:
        tags = ["قرآن", "تلاوة", "الزمن الجميل", "صدقة جارية"]
        video_id, video_url = upload_to_youtube(
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
            privacy_status=privacy_status
        )
        return jsonify({'success': True, 'video_id': video_id, 'url': video_url})
    except Exception as e:
        logger.error(f"YouTube upload failed: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

def _reset_generation_state(msg):
    global generation_state
    generation_state = {
        'is_running': True,
        'percent': 0,
        'status': msg,
        'logs': [msg],
        'result': None,
        'error': None,
        'is_complete': False
    }

def _finish_multisegment_result(res, yt_meta, kind_label):
    """Shared finish: thumbnail fallback + persistent history entry."""
    state = load_state_data()
    state['total_generated'] = state.get('total_generated', 0) + 1
    state['history'].append({
        'filename': res['filename'],
        'surah': res.get('surah_name', kind_label),
        'reciter': res.get('reciter_name', ''),
        'duration': res.get('duration', 0),
        'kind': kind_label,
        'thumbnail': res.get('thumbnail_url'),
        'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    save_state_data(state)
    res['youtube_metadata'] = yt_meta
    generation_state['result'] = res
    generation_state['is_complete'] = True
    generation_state['status'] = 'تم الانتهاء بنجاح!'
    generation_state['percent'] = 100

def ruqyah_worker(params):
    global generation_state
    try:
        def on_progress(p, msg):
            generation_state['percent'] = p
            generation_state['status'] = msg
            generation_state['logs'].append(f"[{p}%] {msg}")

        from quran_data import get_reciter_by_id as _gri
        ruqyah_id = str(params.get('ruqyahId') or params.get('ruqyah_id') or 'complete')
        reciter_id = _gri(str(params.get('reciter', '')).strip())['id']
        aspect = params.get('aspectRatio', '16:9')
        if aspect not in ('16:9', '9:16'):
            aspect = '16:9'
        speed = params.get('speedMode', 'max')
        if speed not in ('max', 'balanced'):
            speed = 'max'
        bg_list = params.get('backgrounds') or ([params.get('backgroundVideo')] if params.get('backgroundVideo') else [])
        if isinstance(bg_list, str):
            bg_list = [bg_list]
        hook = (params.get('hookText') or '').strip()

        rq = get_ruqyah_by_id(ruqyah_id)
        res = render_ruqyah_video(
            ruqyah_id=rq['id'], reciter_id=reciter_id,
            bg_filenames=[b for b in bg_list if b],
            aspect_ratio=aspect, speed_mode=speed,
            hook_text=hook, progress_callback=on_progress)
        yt_meta = generate_ruqyah_metadata(rq['name'], res['reciter_name'], hook or rq['hook'])
        _finish_multisegment_result(res, yt_meta, f"رقية: {rq['name']}")
    except Exception as e:
        logger.error(f"Ruqyah worker failed: {e}", exc_info=True)
        generation_state['error'] = str(e)
        generation_state['status'] = f"خطأ: {str(e)}"
    finally:
        generation_state['is_running'] = False

def compilation_worker(params):
    global generation_state
    try:
        def on_progress(p, msg):
            generation_state['percent'] = p
            generation_state['status'] = msg
            generation_state['logs'].append(f"[{p}%] {msg}")

        from quran_data import get_reciter_by_id as _gri, VERSE_COUNTS as _VC
        reciter_id = _gri(str(params.get('reciter', '')).strip())['id']
        aspect = params.get('aspectRatio', '16:9')
        if aspect not in ('16:9', '9:16'):
            aspect = '16:9'
        speed = params.get('speedMode', 'max')
        if speed not in ('max', 'balanced'):
            speed = 'max'
        bg_list = params.get('backgrounds') or ([params.get('backgroundVideo')] if params.get('backgroundVideo') else [])
        if isinstance(bg_list, str):
            bg_list = [bg_list]
        hook = (params.get('hookText') or '').strip()
        title = (params.get('title') or '').strip()

        raw_items = params.get('items') or []
        if not raw_items:
            raise ValueError("اختر سورة واحدة على الأقل للتجميع")
        items = []
        for it in raw_items[:40]:
            s = int(it.get('surah', 1))
            if s not in _VC:
                continue
            mode = it.get('mode', 'full')
            if mode not in ('full', 'range'):
                mode = 'full'
            a = int(it.get('startAyah') or it.get('start') or 1)
            b = int(it.get('endAyah') or it.get('end') or _VC[s])
            items.append({'surah': s, 'mode': mode, 'start': a, 'end': b,
                          'reciter_id': (it.get('reciter') or None)})
        if not items:
            raise ValueError("لا توجد سور صالحة في قائمة التجميع")
        res = render_compilation_video(
            items=items, reciter_id=reciter_id,
            bg_filenames=[b for b in bg_list if b],
            aspect_ratio=aspect, speed_mode=speed,
            hook_text=hook, title=title, progress_callback=on_progress)
        labels = [f"سورة {SURAH_NAMES[int(it['surah']) - 1]}" for it in items]
        yt_meta = generate_compilation_metadata(labels, res['reciter_name'], hook)
        _finish_multisegment_result(res, yt_meta, "تجميع سور")
    except Exception as e:
        logger.error(f"Compilation worker failed: {e}", exc_info=True)
        generation_state['error'] = str(e)
        generation_state['status'] = f"خطأ: {str(e)}"
    finally:
        generation_state['is_running'] = False

@app.route('/api/generate-ruqyah', methods=['POST'])
def start_ruqyah_generation():
    if generation_state['is_running']:
        return jsonify({'success': False, 'error': 'عملية إنشاء فيديو قيد التنفيذ حالياً'}), 400
    data = request.json or {}
    _reset_generation_state('جاري بدء الرقية الشرعية...')
    generation_state['is_running'] = True
    threading.Thread(target=ruqyah_worker, args=(data,), daemon=True).start()
    return jsonify({'success': True, 'message': 'تم بدء إنتاج الرقية الشرعية'})

@app.route('/api/generate-compilation', methods=['POST'])
def start_compilation_generation():
    if generation_state['is_running']:
        return jsonify({'success': False, 'error': 'عملية إنشاء فيديو قيد التنفيذ حالياً'}), 400
    data = request.json or {}
    _reset_generation_state('جاري بدء الفيديو المجمّع...')
    generation_state['is_running'] = True
    threading.Thread(target=compilation_worker, args=(data,), daemon=True).start()
    return jsonify({'success': True, 'message': 'تم بدء إنتاج الفيديو المجمّع'})

@app.route('/api/thumbnail', methods=['POST'])
def make_thumbnail():
    """Regenerates a thumbnail for any existing video/bg with a custom hook."""
    data = request.json or {}
    source = data.get('videoPath') or data.get('backgroundVideo') or ''
    hook = (data.get('hookText') or '').strip()
    small_title = (data.get('smallTitle') or '').strip()
    if not source or not os.path.exists(source):
        # allow background filename shorthand
        cand = BACKGROUNDS_DIR / Path(str(source)).name
        if cand.exists():
            source = str(cand)
        else:
            return jsonify({'success': False, 'error': 'ملف المصدر غير موجود'}), 400
    if not hook:
        return jsonify({'success': False, 'error': 'اكتب كلمات الهوك أولاً'}), 400
    try:
        out_name = Path(source).stem + "_thumb.jpg"
        out_path = str(VIDEO_OUT_DIR / out_name)
        generate_thumbnail_image(source, hook, small_title, out_path)
        return jsonify({'success': True, 'thumbnail_url': f"/outputs/video/{out_name}",
                        'thumbnail_path': out_path})
    except Exception as e:
        logger.error(f"Thumbnail failed: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/version', methods=['GET'])
def api_version():
    """Visible engine version so you can ALWAYS confirm the running server
    has the latest fixes (Python loads code once at startup - restart needed after updates)."""
    try:
        qsv = is_qsv_available()
    except Exception:
        qsv = False
    return jsonify({
        'engine_version': ENGINE_VERSION,
        'qsv_ready': qsv,
        'features': ['intro-5s', 'real-progress', 'qsv-maxspeed', 'tofu-guard', 'fullfile-mirrors', 'single-instance', 'exe-ready', 'fast-fog', 'live-eta', 'clean-video', 'ruqyah-mode', 'compilation-mode', 'auto-thumbnail', 'upload-diag', 'ipv4-fix']
    })

@app.route('/api/autostart/status', methods=['GET'])
def autostart_status():
    return jsonify({'enabled': is_autostart_enabled()})

@app.route('/api/autostart/toggle', methods=['POST'])
def autostart_toggle():
    if is_autostart_enabled():
        ok, msg = disable_autostart()
        return jsonify({'enabled': False, 'message': msg})
    else:
        ok, msg = enable_autostart()
        return jsonify({'enabled': True, 'message': msg})

@app.route('/api/shutdown', methods=['POST'])
def shutdown_server():
    """Stops the studio server completely so the laptop rests.
    Called from the red shutdown button in the UI."""
    if generation_state.get('is_running'):
        return jsonify({'success': False, 'error': 'يوجد فيديو قيد التوليد الآن! انتظر انتهاءه أولاً ثم أوقف السيرفر.'}), 400

    def stop():
        import time as _t
        _t.sleep(1.0)
        logger.info("Studio stopped by user - shutting down.")
        kill_current_ffmpeg()
        os._exit(0)

    threading.Thread(target=stop, daemon=True).start()
    return jsonify({'success': True, 'message': 'جاري إيقاف السيرفر... يمكنك إغلاق الصفحة والنافذة السوداء.'})

if __name__ == '__main__':
    print('=' * 60)
    print('  📖 منصة صانع فيديوهات القرآن الكريم (تلاوات الزمن الجميل)')
    print('  🌿 صدقة جارية لوجه الله تعالى')
    print('  🌐 الاستوديو متاح الآن على: http://127.0.0.1:5000')
    print('=' * 60)

    # --- Single-instance guard: never run two servers (the repeating-bug killer) ---
    # If our studio is already running, just open it in the browser and exit.
    import socket as _sock
    def _studio_already_up():
        s = _sock.socket()
        s.settimeout(1.5)
        try:
            s.connect(('127.0.0.1', 5000))
            s.close()
        except Exception:
            return False
        try:
            import urllib.request as _url
            with _url.urlopen('http://127.0.0.1:5000/api/config', timeout=4) as r:
                return r.status == 200
        except Exception:
            return False
    if _studio_already_up():
        print('✅ Studio is ALREADY running - opening it in your browser...')
        try:
            webbrowser.open('http://127.0.0.1:5000')
        except Exception:
            pass
        print('No second copy started (this prevents all port/zombie conflicts).')
        sys.exit(0)
    # Second look (closes the startup race window: re-check right before binding)
    import time as _time
    _time.sleep(0.5)
    if _studio_already_up():
        print('✅ Studio just started in another window - opening it...')
        try:
            webbrowser.open('http://127.0.0.1:5000')
        except Exception:
            pass
        sys.exit(0)

    # Safety net: killing this process also kills any running FFmpeg render.
    import atexit as _atexit
    _atexit.register(kill_current_ffmpeg)

    # Automatically open browser when run directly with `python main.py`.
    # Skipped when launched from our .bat files (they open the browser themselves
    # and set QURAN_BAT_OPEN=1) so you never get two tabs.
    # Waits until the server is TRULY READY (frozen exe warms up slowly) so the
    # tab never opens to a dead page.
    def _open_browser_when_ready():
        import time as _t
        print('Warming up (first start can take up to a minute)...')
        for _i in range(45):
            try:
                import urllib.request as _url
                with _url.urlopen('http://127.0.0.1:5000/', timeout=3) as _r:
                    if _r.status == 200:
                        break
            except Exception:
                pass
            _t.sleep(2)
        print('Opening Studio in your browser...')
        opened = False
        try:
            if hasattr(os, 'startfile'):
                os.startfile('http://127.0.0.1:5000')
                opened = True
        except Exception as e:
            logger.warning(f"startfile open failed: {e}")
        if not opened:
            try:
                webbrowser.open('http://127.0.0.1:5000')
                opened = True
            except Exception as e:
                logger.warning(f"webbrowser open failed: {e}")
        if not opened:
            try:
                import subprocess as _sp
                _sp.Popen(['cmd', '/c', 'start', '', 'http://127.0.0.1:5000'],
                          stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
                opened = True
            except Exception as e:
                logger.warning(f"cmd start failed: {e}")
        if not opened:
            print('Could not auto-open browser. Open manually: http://127.0.0.1:5000')

    if not os.environ.get("WERKZEUG_RUN_MAIN") and not os.environ.get("QURAN_BAT_OPEN"):
        threading.Thread(target=_open_browser_when_ready, daemon=True).start()

    try:
        app.run(host='127.0.0.1', port=5000, debug=False, threaded=True)
    except OSError:
        # Lost a startup race: if OUR studio owns the port, open it and exit quietly.
        if _studio_already_up():
            print('✅ Studio is already running - opened in browser, exiting this copy.')
            try:
                webbrowser.open('http://127.0.0.1:5000')
            except Exception:
                pass
            sys.exit(0)
        print('❌ Port 5000 is busy with another program. Close it and try again.')
        raise