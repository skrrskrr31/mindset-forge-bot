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

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
INSTAGRAM_ACCESS_TOKEN = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")
SECRET_PATH = os.path.join(script_dir, "secret.json")
TOKEN_PATH = os.path.join(script_dir, "token.json")
LOGO_PATH = None
for f in os.listdir(script_dir):
    if f.lower().startswith("logo.") and f.lower().endswith(('.jpg', '.jpeg', '.png')):
        LOGO_PATH = os.path.join(script_dir, f)
        break

OUTPUT_VIDEO = os.path.join(script_dir, "mindset_shorts.mp4")
VIDEO_DURATION = 7  # saniye

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
# ADIM 1: GEMİNİ'DEN VİRAL SÖZ + KATEGORİ AL
# ============================================================
def generate_quote():
    print("🤖 Gemini'den viral motivasyon sözü üretiliyor...")
    used_quotes = load_used_quotes()
    print(f"📋 Daha önce kullanılan {len(used_quotes)} söz yüklendi.")

    avoid_block = ""
    if used_quotes:
        recent = used_quotes[-30:]
        avoid_list = "\n".join(f'- "{q}"' for q in recent)
        avoid_block = f"""
        PREVIOUSLY USED QUOTES (NEVER repeat or closely paraphrase these):
{avoid_list}
"""

    try:
        client = Groq(api_key=GROQ_API_KEY)
        prompt = f"""
        You are the editor of the most viral English motivation / stoicism / sigma mindset YouTube Shorts channel.

        Generate ONE powerful, viral, short motivational or stoic quote in English.
        It must be between 8-20 words, punchy, and deeply thought-provoking.
        Also suggest ONE best background category or ICONIC character from this list:
        [Muhammad Ali, Thomas Shelby, Tyler Durden, Batman, Joker, Andrew Tate, Marcus Aurelius, Mike Tyson, dark, nature, mountain, city, night, forest, ocean, abstract, fire, sky]

        STRICT RULES:
        - NEVER use these overused clichés: "pain is temporary", "work in silence", "your only limit is your mind", "don't count the days", "be so good they can't ignore you", "hustle", "grind", "believe in yourself", "never give up", "stay focused", "success is a journey"
        - The quote must feel SURPRISING or COUNTERINTUITIVE — something the viewer hasn't seen 100 times before
        - Prefer angles like: brutal honesty, dark wisdom, contrarian truth, or a statement that makes someone stop scrolling
        - Examples of good style: "Most people don't fail. They just never truly started.", "Comfort is the most socially accepted form of self-destruction.", "The world rewards performance, not effort."
        - EVERY quote must be 100% unique — never repeat a quote from the list below
{avoid_block}
        Format EXACTLY like this (no extra text):
        QUOTE: [your quote here]
        CATEGORY: [one category or character from list]
        """
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.choices[0].message.content.strip()
        quote = None
        category = "dark"
        for line in text.split("\n"):
            if line.startswith("QUOTE:"):
                quote = line.replace("QUOTE:", "").strip().strip('"')
            elif line.startswith("CATEGORY:"):
                category = line.replace("CATEGORY:", "").strip().lower()

        if not quote:
            raise Exception("Gemini returned empty quote")

        print(f"✅ Söz: \"{quote}\"")
        print(f"🎨 Arka Plan Kategorisi: {category}")
        save_used_quote(quote, used_quotes)
        return quote, category
    except Exception as e:
        print(f"⚠️ Söz üretilemedi ({e}). Yedek listeden rastgele seçiliyor.")
        fallback_quotes = [
            ("Pain is temporary. Quitting lasts forever.", "dark"),
            ("The secret to success is starting before you feel ready.", "city"),
            ("Discipline is doing what needs to be done even when you don't want to.", "mountain"),
            ("Work in silence, let your success be your noise.", "night"),
            ("Don't count the days, make the days count.", "ocean"),
            ("The only way to do great work is to love what you do.", "abstract"),
            ("Success is not final, failure is not fatal: it is the courage to continue that counts.", "forest"),
            ("Your only limit is your mind.", "fire"),
            ("Be so good they can't ignore you.", "sky"),
            ("The best revenge is massive success.", "city")
        ]
        q, c = random.choice(fallback_quotes)
        print(f"✅ Yedek Söz: \"{q}\"")
        return q, c


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
def render_quote_on_image(bg_path, quote):
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

        print(f"\n🎉 YAYINLANDI! https://youtube.com/shorts/{response['id']}")
    except Exception as e:
        print(f"❌ YouTube yükleme hatası: {e}")


# ============================================================
# ADIM 7: INSTAGRAM'A YÜKLE
# ============================================================
def upload_video_to_temp_host(video_path):
    """Videoyu geçici public sunucuya yükle, URL döndür."""
    try:
        print("⏫ Video geçici sunucuya yükleniyor (transfer.sh)...")
        with open(video_path, 'rb') as f:
            resp = requests.put(
                f"https://transfer.sh/{os.path.basename(video_path)}",
                data=f,
                headers={"Max-Days": "1", "Max-Downloads": "5"},
                timeout=120
            )
        if resp.status_code == 200:
            url = resp.text.strip()
            print(f"✅ Geçici URL: {url}")
            return url
    except Exception as e:
        print(f"⚠️ transfer.sh hatası ({e}), 0x0.st deneniyor...")
    try:
        with open(video_path, 'rb') as f:
            resp = requests.post("https://0x0.st", files={"file": f}, timeout=120)
        if resp.status_code == 200:
            url = resp.text.strip()
            print(f"✅ Geçici URL: {url}")
            return url
    except Exception as e:
        print(f"⚠️ 0x0.st hatası ({e})")
    return None


def get_instagram_user_id(access_token):
    """Facebook Page üzerinden Instagram Business Account ID'yi al."""
    try:
        resp = requests.get(
            "https://graph.facebook.com/v19.0/me/accounts",
            params={"access_token": access_token},
            timeout=15
        )
        result = resp.json()
        print(f"🔍 me/accounts yaniti: {result}")
        pages = result.get("data", [])
        print(f"🔍 Bulunan sayfa sayisi: {len(pages)}")
        for page in pages:
            page_id = page["id"]
            page_token = page.get("access_token", access_token)
            print(f"🔍 Sayfa kontrol ediliyor: {page_id} - {page.get('name','?')}")
            ig_resp = requests.get(
                f"https://graph.facebook.com/v19.0/{page_id}",
                params={"fields": "instagram_business_account", "access_token": page_token},
                timeout=15
            )
            ig_data = ig_resp.json()
            print(f"🔍 IG data: {ig_data}")
            if "instagram_business_account" in ig_data:
                ig_id = ig_data["instagram_business_account"]["id"]
                print(f"✅ Instagram Business ID bulundu: {ig_id}")
                return ig_id, page_token
    except Exception as e:
        print(f"⚠️ IG user ID alınamadı: {e}")
    return None, None


def post_to_instagram(video_path, quote, category):
    """Videoyu Instagram Reels olarak paylaş."""
    if not INSTAGRAM_ACCESS_TOKEN:
        print("⚠️ INSTAGRAM_ACCESS_TOKEN bulunamadı, Instagram atlanıyor.")
        return

    print("\n==========================================")
    print("📸 INSTAGRAM'A OTOMATİK YÜKLEME BAŞLIYOR...")
    print("==========================================")

    ig_user_id, token = get_instagram_user_id(INSTAGRAM_ACCESS_TOKEN)
    if not ig_user_id:
        print("❌ Instagram hesap ID'si alınamadı. Paylaşım iptal.")
        return
    print(f"✅ Instagram Hesap ID: {ig_user_id}")

    video_url = upload_video_to_temp_host(video_path)
    if not video_url:
        print("❌ Video URL alınamadı. Instagram paylaşımı iptal.")
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

    # Media container oluştur
    try:
        container_resp = requests.post(
            f"https://graph.facebook.com/v19.0/{ig_user_id}/media",
            data={
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
                "share_to_feed": "true",
                "access_token": token
            },
            timeout=30
        )
        container_data = container_resp.json()
        if "error" in container_data:
            print(f"❌ Media container hatası: {container_data['error']['message']}")
            return
        container_id = container_data["id"]
        print(f"✅ Media container oluşturuldu: {container_id}")
    except Exception as e:
        print(f"❌ Container oluşturma hatası: {e}")
        return

    # Video işlenmeyi bekle
    import time
    print("⏳ Instagram video işliyor...")
    for attempt in range(15):
        time.sleep(10)
        status_resp = requests.get(
            f"https://graph.facebook.com/v19.0/{container_id}",
            params={"fields": "status_code,status", "access_token": token},
            timeout=15
        )
        status_data = status_resp.json()
        status = status_data.get("status_code", "")
        print(f"  [{attempt+1}/15] Durum: {status}")
        if status == "FINISHED":
            break
        elif status == "ERROR":
            print(f"❌ Video işleme hatası: {status_data}")
            return

    # Yayınla
    try:
        publish_resp = requests.post(
            f"https://graph.facebook.com/v19.0/{ig_user_id}/media_publish",
            data={"creation_id": container_id, "access_token": token},
            timeout=30
        )
        publish_data = publish_resp.json()
        if "error" in publish_data:
            print(f"❌ Yayınlama hatası: {publish_data['error']['message']}")
            return
        print(f"🎉 INSTAGRAM'DA YAYINLANDI! Post ID: {publish_data.get('id', '?')}")
    except Exception as e:
        print(f"❌ Yayınlama hatası: {e}")


# ============================================================
# ANA AKIŞ
# ============================================================
if __name__ == "__main__":
    print("\n🚀 MindsetForge Otonom Bot Başlatıldı!\n")

    # 1. Söz üret
    quote, category = generate_quote()

    # 2. Arka plan indir
    bg_path = download_background(category)

    # 3. Görsel oluştur
    final_img = render_quote_on_image(bg_path, quote)

    # 4. Müzik indir
    music_path = download_music(quote)

    # 5. Video oluştur
    video_path = create_video(final_img, music_path)

    # 6. YouTube'a yükle
    upload_to_youtube(quote)

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
