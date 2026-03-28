# ============================================================
# MINDSET FORGE BOT - TAM OTONOM VERSİYON
# ============================================================
# Çalışma Akışı:
# 1. Gemini → Viral motivasyon sözü + arka plan kategorisi üret
# 2. Unsplash → Kategoriyle eşleşen sinematik arka plan indir
# 3. PIL → Sözü arka plana gölgeli, şık fontla yaz + logo ekle
# 4. Gemini + yt-dlp → Uygun müzik araması yap ve indir
# 5. MoviePy → 7 saniyelik Shorts videosu oluştur
# 6. YouTube API → Videoyu otomatik yükle
# ============================================================

import os
import sys
import random
import textwrap
import requests
import io
import base64
import json
import signal

# GitHub Actions / Linux ortamında stdout encoding ayarla
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except AttributeError:
        pass  # zaten sarmalanmış

# ── GitHub Actions: token ve secret dosyalarını env'den yaz ──────────────────
def _write_from_env(env_var, filepath):
    val = os.environ.get(env_var)
    if val and not os.path.exists(filepath):
        with open(filepath, 'wb') as f:
            f.write(base64.b64decode(val))
        print(f"✅ {env_var} → {filepath} yazıldı")

_script_dir_early = os.path.dirname(os.path.abspath(__file__))
_write_from_env("TOKEN_JSON",  os.path.join(_script_dir_early, "token.json"))
_write_from_env("SECRET_JSON", os.path.join(_script_dir_early, "secret.json"))

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageStat
from groq import Groq
try:
    from moviepy import ImageClip, AudioFileClip, afx
except ImportError:
    # MoviePy v2.0+ compatibility (Verified paths)
    from moviepy.video.VideoClip import ImageClip
    from moviepy.audio.io.AudioFileClip import AudioFileClip
    import moviepy.video.fx.all as vfx
    # Import specific audio effects as they are not automatically exported in v2
    import moviepy.audio.fx.audio_fadein as afadein
    import moviepy.audio.fx.audio_fadeout as afadeout
    import moviepy.audio.fx.volumex as avolumex
    afx = None # Will use individual imports

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
# from yt_dlp import ... (Local music used now)

# ============================================================
# AYARLAR
# ============================================================
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

GROQ_API_KEY           = os.environ.get("GROQ_API_KEY", "")
INSTAGRAM_ACCESS_TOKEN = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_USERNAME     = os.environ.get("INSTAGRAM_USERNAME", "dailymindsetforge")
INSTAGRAM_PASSWORD     = os.environ.get("INSTAGRAM_PASSWORD", "")
INSTAGRAM_SESSION_B64  = os.environ.get("INSTAGRAM_SESSION", "")
TELEGRAM_BOT_TOKEN     = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID       = os.environ.get("TELEGRAM_CHAT_ID", "")
SECRET_PATH = os.path.join(script_dir, "secret.json")
TOKEN_PATH  = os.path.join(script_dir, "token.json")
LOGO_PATH = None
for f in os.listdir(script_dir):
    if f.lower().startswith("logo.") and f.lower().endswith(('.jpg', '.jpeg', '.png')):
        LOGO_PATH = os.path.join(script_dir, f)
        break

OUTPUT_VIDEO = os.path.join(script_dir, "mindset_shorts.mp4")
VIDEO_DURATION = 7  # saniye


def save_run_log(status, video_id=None, error=None):
    from datetime import datetime
    log_path = os.path.join(script_dir, "run_log.json")
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except:
        data = {"bot": "mindset", "runs": []}
    entry = {"ts": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"), "status": status}
    if video_id: entry["video_id"] = video_id
    if error:    entry["error"]    = str(error)[:200]
    data["runs"].append(entry)
    data["runs"] = data["runs"][-20:]
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    import urllib.request, urllib.parse
    try:
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML"
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data=data
        )
        urllib.request.urlopen(req, timeout=10)
        print("[Telegram] Mesaj gonderildi.")
    except Exception as e:
        print(f"[Telegram] Hata: {e}")

TEMP_BG = "gecici_arka_plan.jpg"
TEMP_FINAL = "gecici_final.jpg"
TEMP_MUSIC = "gecici_muzik"


# ============================================================
# KULLANILAN SÖZLER - TEKRAR ÖNLEME
# ============================================================
USED_QUOTES_PATH = os.path.join(script_dir, "kullanilan_sozler.json")
MAX_SAVED_QUOTES = 60

def load_used_quotes():
    if os.path.exists(USED_QUOTES_PATH):
        try:
            with open(USED_QUOTES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return []

def save_used_quote(quote, used_list):
    used_list.append(quote)
    if len(used_list) > MAX_SAVED_QUOTES:
        used_list = used_list[-MAX_SAVED_QUOTES:]
    try:
        with open(USED_QUOTES_PATH, "w", encoding="utf-8") as f:
            json.dump(used_list, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Kullanılan sözler kaydedilemedi: {e}")
    return used_list


# ============================================================
# TEMA LİSTESİ - Her çalışmada farklı bir konu
# ============================================================
THEMES = [
    ("loneliness and solitude", "night"),
    ("the real cost of ambition", "mountain"),
    ("failure as the best teacher", "dark"),
    ("silence and patience", "forest"),
    ("time you will never get back", "city"),
    ("money and wealth mindset", "city"),
    ("fear of what others think", "dark"),
    ("comfort zone slowly killing you", "fire"),
    ("loyalty and betrayal", "dark"),
    ("self-discipline vs. motivation", "mountain"),
    ("social media and distraction", "night"),
    ("people who drain your energy", "dark"),
    ("wasted years and regret", "night"),
    ("the gap between potential and reality", "mountain"),
    ("3am thoughts and inner demons", "night"),
    ("being busy vs. being productive", "city"),
    ("saying no and protecting your peace", "forest"),
    ("jealousy disguised as advice", "dark"),
    ("mental strength over emotion", "mountain"),
    ("sacrifice and delayed gratification", "fire"),
    ("pretending to be someone you are not", "dark"),
    ("revenge through becoming great", "fire"),
    ("power of doing less but better", "ocean"),
    ("books and knowledge no one talks about", "forest"),
    ("your environment is shaping you silently", "nature"),
    ("the lie of overnight success", "city"),
    ("choosing hard now vs. suffering later", "mountain"),
    ("ego as the silent killer", "dark"),
    ("what rejection actually means", "dark"),
    ("morning routines and who you become", "sky"),
]


def _extract_banned_words(used_quotes):
    """Son 10 sözden sık geçen güçlü kelimeleri çıkar."""
    from collections import Counter
    stop = {"is","are","not","the","a","an","you","your","to","of","in","it",
            "be","but","and","that","this","was","for","on","as","with","if",
            "they","most","will","do","make","by","or","from","at","no","get",
            "who","what","how","its","has","have","can","just","so","all","my"}
    recent = used_quotes[-10:] if len(used_quotes) >= 10 else used_quotes
    words = []
    for q in recent:
        for w in q.lower().split():
            w = w.strip(".,!?\"'")
            if len(w) > 4 and w not in stop:
                words.append(w)
    common = [w for w, _ in Counter(words).most_common(12)]
    return common


# ============================================================
# ADIM 1: GEMİNİ'DEN VİRAL SÖZ + KATEGORİ AL
# ============================================================
def fetch_zenquotes():
    """zenquotes.io'dan 50 rastgele gerçek alıntı çeker."""
    try:
        import warnings
        warnings.filterwarnings('ignore')
        r = requests.get('https://zenquotes.io/api/quotes', timeout=10, verify=False)
        if r.status_code == 200:
            data = r.json()
            quotes = []
            for item in data:
                text = item.get('q', '').strip()
                author = item.get('a', '').strip()
                if 35 < len(text) < 220 and author and author != 'Unknown':
                    quotes.append(f'"{text}" — {author}')
            print(f"🌐 zenquotes.io'dan {len(quotes)} kaliteli alıntı alındı.")
            return quotes
    except Exception as e:
        print(f"⚠️ zenquotes erişilemedi: {e}")
    return []


def generate_quote():
    print("🤖 Gerçek alıntılardan viral motivasyon sözü seçiliyor...")
    used_quotes = load_used_quotes()
    print(f"📋 Daha önce kullanılan {len(used_quotes)} söz yüklendi.")

    # Tema rotasyonu
    meta_path = os.path.join(script_dir, "tema_index.txt")
    try:
        theme_idx = int(open(meta_path).read().strip()) if os.path.exists(meta_path) else 0
    except:
        theme_idx = 0
    next_idx = (theme_idx + 1) % len(THEMES)
    try:
        with open(meta_path, "w") as f:
            f.write(str(next_idx))
    except:
        pass
    theme_label, theme_category = THEMES[theme_idx]
    print(f"🎯 Bu çalışmanın teması: {theme_label}")

    # Son 30 sözü gönder (tekrar önleme)
    avoid_block = ""
    if used_quotes:
        recent_quotes = used_quotes[-30:]
        avoid_list = "\n".join(f'- "{q}"' for q in recent_quotes if isinstance(q, str))
        avoid_block = f"\nPREVIOUSLY USED QUOTES (never repeat or paraphrase):\n{avoid_list}\n"

    # Yasak kelimeler
    banned_words = _extract_banned_words([q for q in used_quotes if isinstance(q, str)])
    banned_str = ", ".join(banned_words) if banned_words else ""
    banned_block = f"\nFORBIDDEN WORDS (overused recently, avoid completely): {banned_str}\n" if banned_str else ""

    # Gerçek alıntıları çek
    real_quotes = fetch_zenquotes()

    try:
        client = Groq(api_key=GROQ_API_KEY)

        if real_quotes:
            # Mod 1: Gerçek alıntılardan en uygun olanı seç
            quotes_block = "\n".join(f"{i+1}. {q}" for i, q in enumerate(real_quotes[:50]))
            prompt = f"""You are the editor of a viral English motivation / stoicism YouTube Shorts channel.

TODAY'S TOPIC: "{theme_label}"

From the real quotes below, pick ONE that best fits the topic and would make someone stop scrolling.
If none fit the topic well, you may write one original quote instead.

REAL QUOTES:
{quotes_block}
{avoid_block}
Rules:
- Quote must be 8-25 words
- Must feel like a brutal truth or deep wisdom
- If picking from list: return it EXACTLY as written (author attribution included)
- If writing original: make it powerful and topic-specific
{banned_block}
Also pick ONE background: [Muhammad Ali, Thomas Shelby, Tyler Durden, Batman, Joker, Andrew Tate, Marcus Aurelius, Mike Tyson, dark, nature, mountain, city, night, forest, ocean, abstract, fire, sky]
Prefer: {theme_category}

Format EXACTLY (no extra text):
QUOTE: [the quote text only, no author]
AUTHOR: [author name or empty if original]
CATEGORY: [one option from list]"""
        else:
            # Mod 2: Groq üretir (fallback)
            prompt = f"""You are the editor of the most viral English motivation / stoicism / sigma mindset YouTube Shorts channel.

TODAY'S SPECIFIC TOPIC: "{theme_label}"
Generate ONE powerful, viral, short quote in English.
- Between 8-18 words
- Punchy, counterintuitive, makes someone stop scrolling
- Must feel like a brutal truth or dark wisdom about: {theme_label}
{banned_block}
{avoid_block}
Also pick ONE background from: [Muhammad Ali, Thomas Shelby, Tyler Durden, Batman, Joker, Andrew Tate, Marcus Aurelius, Mike Tyson, dark, nature, mountain, city, night, forest, ocean, abstract, fire, sky]
Prefer: {theme_category}

Format EXACTLY (no extra text):
QUOTE: [your quote here]
AUTHOR:
CATEGORY: [one option from list]"""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.choices[0].message.content.strip()
        quote = None
        author = ""
        category = theme_category
        for line in text.split("\n"):
            if line.startswith("QUOTE:"):
                quote = line.replace("QUOTE:", "").strip().strip('"')
            elif line.startswith("AUTHOR:"):
                author = line.replace("AUTHOR:", "").strip()
            elif line.startswith("CATEGORY:"):
                category = line.replace("CATEGORY:", "").strip().lower()

        if not quote:
            raise Exception("Empty quote returned")

        # Yazar varsa ekle
        display = f'"{quote}"\n— {author}' if author else quote
        print(f"✅ Söz: {display}")
        print(f"🎨 Kategori: {category}")
        save_used_quote(quote, used_quotes)
        return quote, category, author
    except Exception as e:
        print(f"⚠️ Söz üretilemedi ({e}). Yedek listeden seçiliyor.")
        fallback_quotes = [
            ("The years you wasted on comfort will cost you more than failure ever could.", "dark", ""),
            ("Most people scroll past their own potential every single day.", "night", ""),
            ("Silence is not weakness. It is the loudest answer you can give.", "forest", ""),
            ("You are not tired. You are uninspired.", "mountain", ""),
            ("The person you fear becoming is still you.", "dark", ""),
            ("By failing to prepare, you are preparing to fail.", "mountain", "Benjamin Franklin"),
            ("The pessimist sees difficulty in every opportunity. The optimist sees opportunity in every difficulty.", "sky", "Winston Churchill"),
            ("Mastery is not a function of genius or talent, it is a function of time and intense focus.", "dark", "Robert Greene"),
        ]
        q, c, a = random.choice(fallback_quotes)
        print(f"✅ Yedek Söz: \"{q}\"")
        return q, c, a


# ============================================================
# ADIM 2: UNSPLASH'TEN ARKA PLAN İNDİR (API KEY GEREKMİYOR)
# ============================================================
def get_next_background_index(max_count=10):
    """Sıradaki arkaplan numarasını okur ve günceller (arkaplan1.jpg -> arkaplan10.jpg)."""
    index_file = os.path.join(script_dir, "arkaplan_index.txt")
    current_index = 1
    
    try:
        if os.path.exists(index_file):
            with open(index_file, "r") as f:
                content = f.read().strip()
                if content.isdigit():
                    current_index = int(content)
                else:
                    print("⚠️ Index dosyası bozuk, 1'den başlanıyor.")
        else:
            print("📝 İlk çalışma, index dosyası oluşturuluyor.")
    except Exception as e:
        print(f"⚠️ Index okuma hatası ({e}), 1'den başlanıyor.")

    # Bir sonraki indexi hesapla ve kaydet
    next_index = current_index + 1
    if next_index > max_count:
        next_index = 1
        
    try:
        with open(index_file, "w") as f:
            f.write(str(next_index))
            f.flush()
            os.fsync(f.fileno()) # Diske yazıldığından emin ol
    except Exception as e:
        print(f"⚠️ Index kaydetme hatası ({e})")
        
    return current_index

def download_background(category):
    """Localdeki arkaplanX.jpg dosyalarından rastgele seçer (CI/CD uyumlu)."""
    available = [i for i in range(1, 11)
                 if os.path.exists(os.path.join(script_dir, f"arkaplan{i}.jpg"))]
    idx = random.choice(available) if available else 1
    bg_filename = f"arkaplan{idx}.jpg"
    bg_full_path = os.path.join(script_dir, bg_filename)
    
    print(f"🖼️ Sıradaki görsel seçildi: {bg_filename} (Index: {idx})")
    
    if os.path.exists(bg_full_path):
        # MoviePy'ın TEMP_BG üzerinden çalışması için dosyayı kopyalayalım veya direkt yolunu döndürelim
        # Scriptin geri kalanıyla uyum için TEMP_BG'ye kopyalamak daha güvenli
        try:
            with open(bg_full_path, 'rb') as src, open(TEMP_BG, 'wb') as dst:
                dst.write(src.read())
            return TEMP_BG
        except Exception as e:
            print(f"⚠️ Dosya kopyalama hatası ({e})")
            return None
    else:
        print(f"❌ Hata: {bg_filename} dosyası bulunamadı!")
        return None


# ============================================================
# ADIM 3: SÖZÜ ARKA PLANA YAZ (PIL)
# ============================================================
def render_quote_on_image(bg_path, quote, author=""):
    print("🖊️ Söz arka plana yazılıyor...")
    
    target_w, target_h = 1080, 1920

    # Arka planı yükle veya düz siyah oluştur
    if bg_path and os.path.exists(bg_path):
        try:
            img = Image.open(bg_path).convert("RGB")
            # Aspect ratio koruyarak merkezden kırp ve boyutlandır
            img_w, img_h = img.size
            img_ratio = img_w / img_h
            target_ratio = target_w / target_h

            if img_ratio > target_ratio:
                # Görsel çok geniş, yanlardan kırp
                new_w = int(target_ratio * img_h)
                left = (img_w - new_w) // 2
                img = img.crop((left, 0, left + new_w, img_h))
            else:
                # Görsel çok dar, üstten/alttan kırp
                new_h = int(img_w / target_ratio)
                top = (img_h - new_h) // 2
                img = img.crop((0, top, img_w, top + new_h))
            
            img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
        except Exception as e:
            print(f"⚠️ Arka plan işleme hatası ({e}). Siyah arka plan kullanılacak.")
            img = Image.new("RGB", (target_w, target_h), (15, 15, 15))
    else:
        img = Image.new("RGB", (target_w, target_h), (15, 15, 15))

    draw = ImageDraw.Draw(img)

    # Üstüne karanlık yarı saydam overlay ekle (okunabilirlik için)
    overlay = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 140))
    img_rgba = img.convert("RGBA")
    img_rgba = Image.alpha_composite(img_rgba, overlay)
    img = img_rgba.convert("RGB")
    draw = ImageDraw.Draw(img)

    # Font yükle (Linux + Windows uyumlu)
    font_size = 72
    font = None
    bold_fonts = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "C:\\Windows\\Fonts\\impact.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf",
        "C:\\Windows\\Fonts\\calibrib.ttf",
        "C:\\Windows\\Fonts\\georgia.ttf",
    ]
    for fp in bold_fonts:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, font_size)
                break
            except:
                continue
    if not font:
        font = ImageFont.load_default(size=font_size)

    # Sözü satırlara böl (max 20 karakter/satır yaklaşık)
    wrapped = textwrap.wrap(quote.upper(), width=18)
    
    # Toplam metin yüksekliğini hesapla
    line_height = font_size + 20
    total_h = len(wrapped) * line_height
    start_y = (target_h - total_h) // 2 - 80  # ortalanmış ama biraz yukarı

    for i, line in enumerate(wrapped):
        y = start_y + i * line_height
        # Gölge efekti (önce siyah, sonra beyaz)
        shadow_offset = 4
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (target_w - text_w) // 2

        draw.text((x + shadow_offset, y + shadow_offset), line, font=font, fill=(0, 0, 0, 200))
        draw.text((x, y), line, font=font, fill=(255, 255, 255))

    # Alt çizgi (ince dekoratif çizgi)
    line_y = start_y + total_h + 20
    draw.rectangle([(target_w // 2 - 150, line_y), (target_w // 2 + 150, line_y + 3)], fill=(200, 200, 200))

    # Yazar adı (varsa çizginin altında)
    if author:
        author_text = f"— {author}"
        author_font = None
        for fp in bold_fonts:
            if os.path.exists(fp):
                try:
                    author_font = ImageFont.truetype(fp, 40)
                    break
                except:
                    continue
        if not author_font:
            author_font = ImageFont.load_default(size=40)
        bbox_a = draw.textbbox((0, 0), author_text, font=author_font)
        aw = bbox_a[2] - bbox_a[0]
        ax = (target_w - aw) // 2
        ay = line_y + 18
        draw.text((ax + 3, ay + 3), author_text, font=author_font, fill=(0, 0, 0, 200))
        draw.text((ax, ay), author_text, font=author_font, fill=(220, 180, 100))

    # ==========================================
    # LOGO + KANAL ADI (Sol Üst)
    # ==========================================
    logo_y = 50
    logo_size = (100, 100)
    logo_pos = (40, logo_y)

    if LOGO_PATH and os.path.exists(LOGO_PATH):
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            logo = logo.resize(logo_size, Image.Resampling.LANCZOS)
            # Yuvarlak kırp
            circle_mask = Image.new("L", logo_size, 0)
            draw_mask = ImageDraw.Draw(circle_mask)
            draw_mask.ellipse((0, 0) + logo_size, fill=255)
            logo.putalpha(circle_mask)
            img.paste(logo, logo_pos, logo)
        except Exception as e:
            print(f"⚠️ Logo eklenemedi: {e}")

    fn = fh = None
    for fp in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
               "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
               "C:\\Windows\\Fonts\\arialbd.ttf"]:
        if os.path.exists(fp):
            try:
                fn = ImageFont.truetype(fp, 36)
                fh = ImageFont.truetype(fp, 28)
                break
            except:
                continue
    if not fn:
        fn = ImageFont.load_default(size=36)
        fh = ImageFont.load_default(size=28)

    text_x = logo_pos[0] + logo_size[0] + 18
    draw.text((text_x, logo_y + 12), "MindsetForge", font=fn, fill="white")
    draw.text((text_x, logo_y + 56), "@mindsetforge", font=fh, fill=(160, 160, 160))

    img.save(TEMP_FINAL, quality=95)
    print(f"✅ Final görsel oluşturuldu: {TEMP_FINAL}")
    return TEMP_FINAL


# ============================================================
# ADIM 4: GEMİNİ + YT-DLP İLE MÜZİK SEÇ VE İNDİR
# ============================================================
def download_music(quote):
    """Artık internetten indirmek yerine localdeki music.mp3 dosyasını kullanır."""
    music_file = os.path.join(script_dir, "music.mp3")
    
    if os.path.exists(music_file):
        print(f"🎵 Yerel müzik dosyası kullanılıyor: music.mp3")
        return music_file
    else:
        print(f"❌ Hata: 'music.mp3' dosyası bulunamadı! Lütfen şarkıyı bu isimle klasöre koyun.")
        return None


# ============================================================
# ADIM 5: VİDEO OLUŞTUR
# ============================================================
def create_video(final_image_path, music_path):
    print(f"🎬 {VIDEO_DURATION} saniyelik Shorts videosu oluşturuluyor...")
    clip = ImageClip(final_image_path, duration=VIDEO_DURATION)
    write_audio = False

    if music_path and os.path.exists(music_path):
        try:
            audio = AudioFileClip(music_path)
            # Şarkının en iyi kısmını seç
            if audio.duration > 20:
                start_t = random.randint(12, 20)
            elif audio.duration > 8:
                start_t = 4
            else:
                start_t = 0

            end_t = min(start_t + VIDEO_DURATION, audio.duration)
            audio = audio.subclip(start_t, end_t)
            
            # MoviePy v2 compatibility for effects
            if hasattr(audio, 'audio_fadein'):
                audio = audio.audio_fadein(0.5).audio_fadeout(1.0)
                audio = audio.volumex(0.25)
            else:
                # v2 logic (fx based)
                audio = audio.fx(afadein.audio_fadein, 0.5)
                audio = audio.fx(afadeout.audio_fadeout, 1.0)
                audio = audio.fx(avolumex.volumex, 0.25)
                
            clip = clip.set_audio(audio)
            write_audio = True
            print("✅ Müzik videoya eklendi.")
        except Exception as e:
            print(f"⚠️ Müzik eklenemedi: {e}")

    clip.write_videofile(OUTPUT_VIDEO, fps=24, codec="libx264", audio=write_audio, logger=None)
    print(f"✅ Video hazır: {OUTPUT_VIDEO}")
    return OUTPUT_VIDEO


# ============================================================
# ADIM 6: YOUTUBE'A YÜKLE
# ============================================================
def upload_to_youtube(quote):
    print("\n==========================================")
    print("🎥 YOUTUBE'A OTOMATİK YÜKLEME BAŞLIYOR...")
    print("==========================================")

    if not os.path.exists(SECRET_PATH):
        print(f"❌ '{SECRET_PATH}' bulunamadı. YouTube yüklemesi iptal.")
        return

    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    credentials = None

    if os.path.exists(TOKEN_PATH):
        print("🔑 Kayıtlı oturum bulundu, otomatik giriş...")
        credentials = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            print("🚨 Tarayıcı açılıyor, YouTube hesabınıza giriş yapın...")
            flow = InstalledAppFlow.from_client_secrets_file(SECRET_PATH, SCOPES)
            credentials = flow.run_local_server(port=0)
        with open(TOKEN_PATH, 'w') as token:
            token.write(credentials.to_json())

    # Başlık üret
    title_formulas = [
        "Nobody talks about this...",
        "This hit different at 3am...",
        "They don't want you to know this.",
        "Stop lying to yourself.",
        "Most people will scroll past this.",
        "The truth nobody told you.",
        "Read this twice.",
        "This will change how you think.",
        "Everybody knows this. Nobody does this.",
        "This is why you're stuck.",
    ]
    chosen_formula = random.choice(title_formulas)

    try:
        client = Groq(api_key=GROQ_API_KEY)
        title_prompt = f"""
        This is a motivational quote for a YouTube Shorts video: "{quote}"

        Create a viral YouTube Shorts TITLE in English.
        Start with or be inspired by this hook formula: "{chosen_formula}"
        Rules:
        - Max 60 characters total
        - End with #shorts
        - Must make someone STOP scrolling
        - Do NOT just repeat the quote
        ONLY THE TITLE, NO EXTRA TEXT:
        """
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": title_prompt}]
        )
        title = resp.choices[0].message.content.strip().replace('"', '')
    except:
        title = f"{chosen_formula} #shorts"

    # Kategoriye göre dinamik hashtag
    category_hashtags = {
        "muhammad ali":   "#MuhammadAli #boxing #champion #goat #legend",
        "thomas shelby":  "#ThomasShelby #PeakyBlinders #sigma #gangster #series",
        "tyler durden":   "#TylerDurden #FightClub #sigma #rebel #matrix",
        "batman":         "#Batman #DC #darkknight #hero #justice",
        "joker":          "#Joker #chaos #darkwisdom #villain #DC",
        "andrew tate":    "#AndrewTate #Tate #TopG #sigma #redpill",
        "marcus aurelius":"#MarcusAurelius #stoic #stoicism #philosophy #meditations",
        "mike tyson":     "#MikeTyson #boxing #iron #champion #beast",
        "dark":           "#darkwisdom #darkquotes #hardtruths #realitycheck #mindshift",
        "nature":         "#nature #naturequotes #earth #peaceful #mindset",
        "mountain":       "#mountain #climbing #summit #hardwork #nolimits",
        "city":           "#city #urban #hustle #ambition #streetwisdom",
        "night":          "#nightvibes #latenight #darkthoughts #alone #3am",
        "forest":         "#forest #silence #nature #solitude #deepthinking",
        "ocean":          "#ocean #waves #depth #calm #infinite",
        "abstract":       "#abstract #art #deepthoughts #philosophy #mindblown",
        "fire":           "#fire #passion #burn #energy #beast",
        "sky":            "#sky #freedom #limitless #highermind #believe",
    }
    base_hashtags = "#shorts #motivation #mindset #discipline #success"
    extra = category_hashtags.get(category.lower(), "#quotes #wisdom #life #truth #powerful")
    description = f'"{quote}"\n\n{base_hashtags} {extra}'
    print(f"📌 Başlık: {title}")

    youtube = build('youtube', 'v3', credentials=credentials)
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': ['motivation', 'mindset', 'shorts', 'stoic', 'sigma', 'grind', 'discipline'],
            'categoryId': '26'  # How-to & Style
        },
        'status': {
            'privacyStatus': 'public',
            'selfDeclaredMadeForKids': False
        }
    }

    try:
        media = MediaFileUpload(OUTPUT_VIDEO, mimetype='video/mp4', resumable=True)
        request = youtube.videos().insert(part='snippet,status', body=body, media_body=media)

        print("⏫ Yükleniyor...")
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"  %{int(status.progress() * 100)}")

        video_id = response['id']
        print(f"\n🎉 YAYINLANDI! https://youtube.com/shorts/{video_id}")
        return video_id
    except Exception as e:
        print(f"❌ YouTube yükleme hatası: {e}")
        return None


# ============================================================
# ADIM 7: INSTAGRAM'A YÜKLE (instagrapi)
# ============================================================
def post_to_instagram(video_path, quote, category):
    """Videoyu instagrapi ile Instagram Reels olarak paylaş."""
    if not INSTAGRAM_PASSWORD:
        print("⚠️ INSTAGRAM_PASSWORD bulunamadı, Instagram atlanıyor.")
        return

    print("\n==========================================")
    print("📸 INSTAGRAM'A OTOMATİK YÜKLEME BAŞLIYOR...")
    print("==========================================")

    try:
        from instagrapi import Client
        from instagrapi.exceptions import LoginRequired
    except ImportError:
        print("❌ instagrapi yüklü değil. pip install instagrapi")
        return

    category_hashtags = {
        "muhammad ali":    "#MuhammadAli #boxing #champion #goat #legend",
        "thomas shelby":   "#ThomasShelby #PeakyBlinders #sigma #gangster",
        "tyler durden":    "#TylerDurden #FightClub #sigma #rebel",
        "batman":          "#Batman #darkknight #hero #DC",
        "joker":           "#Joker #chaos #darkwisdom #DC",
        "andrew tate":     "#AndrewTate #TopG #sigma #redpill",
        "marcus aurelius": "#MarcusAurelius #stoic #stoicism #meditations",
        "mike tyson":      "#MikeTyson #boxing #iron #champion",
        "dark":            "#darkwisdom #hardtruths #realitycheck #mindshift",
        "mountain":        "#mountain #summit #hardwork #nolimits",
        "city":            "#city #hustle #ambition #streetwisdom",
        "night":           "#nightvibes #latenight #alone #3am",
        "forest":          "#forest #silence #solitude",
        "ocean":           "#ocean #depth #calm #infinite",
        "fire":            "#fire #passion #energy #beast",
        "sky":             "#sky #freedom #limitless",
    }
    extra = category_hashtags.get(category.lower(), "#quotes #wisdom #truth")
    caption = f'"{quote}"\n\n#motivation #mindset #discipline #success #reels {extra}'

    session_file = os.path.join(script_dir, "instagram_session.json")

    # Session dosyasini Secret'tan yaz
    if INSTAGRAM_SESSION_B64 and not os.path.exists(session_file):
        try:
            with open(session_file, 'wb') as f:
                f.write(base64.b64decode(INSTAGRAM_SESSION_B64))
            print("✅ Instagram session dosyasi yazildi.")
        except Exception as e:
            print(f"⚠️ Session dosyasi yazılamadı: {e}")

    def _instagram_timeout_handler(signum, frame):
        raise TimeoutError("Instagram islemi 3 dakikada tamamlanamadi")

    signal.signal(signal.SIGALRM, _instagram_timeout_handler)
    signal.alarm(180)  # 3 dakika timeout
    try:
        cl = Client()
        cl.delay_range = [1, 3]

        if os.path.exists(session_file):
            try:
                cl.load_settings(session_file)
                cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
                print(f"✅ Oturum yuklendi: @{INSTAGRAM_USERNAME}")
            except LoginRequired:
                print("⚠️ Oturum suresi dolmus, yeniden giris yapiliyor...")
                cl = Client()
                cl.delay_range = [1, 3]
                cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
                cl.dump_settings(session_file)
        else:
            cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            cl.dump_settings(session_file)
            print(f"✅ Giris yapildi: @{INSTAGRAM_USERNAME}")

        from pathlib import Path
        media = cl.clip_upload(
            Path(video_path),
            caption=caption,
        )
        print(f"🎉 INSTAGRAM'DA YAYINLANDI! Post ID: {media.pk}")

    except TimeoutError as e:
        print(f"⏱️ Instagram zaman asimi: {e} — atlanıyor.")
    except Exception as e:
        print(f"❌ Instagram paylaşım hatası: {e}")
    finally:
        signal.alarm(0)  # Timeout'u iptal et


# ============================================================
# ANA AKIŞ
# ============================================================
if __name__ == "__main__":
    print("\n🚀 MindsetForge Otonom Bot Başlatıldı!\n")

    # 1. Söz üret
    quote, category, author = generate_quote()

    # 2. Arka plan indir
    bg_path = download_background(category)

    # 3. Görsel oluştur
    final_img = render_quote_on_image(bg_path, quote, author)

    # 4. Müzik indir
    music_path = download_music(quote)

    # 5. Video oluştur
    video_path = create_video(final_img, music_path)

    # 6. YouTube'a yükle
    video_id = upload_to_youtube(quote)
    if video_id:
        save_run_log("ok", video_id=video_id)
        send_telegram(
            f"✅ <b>MindsetForge</b> video yayınlandı!\n"
            f"🔗 https://youtube.com/shorts/{video_id}"
        )
    else:
        save_run_log("error", error="YouTube upload failed")
        send_telegram("❌ <b>MindsetForge</b> YouTube yüklemesi başarısız!")

    # 7. Instagram'a yükle
    post_to_instagram(video_path, quote, category)

    # Temizlik
    print("\n🧹 Geçici dosyalar temizleniyor...")
    for f in [TEMP_BG, TEMP_FINAL]:
        if f and os.path.exists(f):
            try: os.remove(f)
            except: pass
    if music_path and os.path.exists(music_path):
        try: os.remove(music_path)
        except: pass

    print("\n✨ Tamamlandı! Bot bir sonraki çalışmayı bekliyor.")
