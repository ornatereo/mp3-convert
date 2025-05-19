from flask import Flask, render_template, request, jsonify, send_from_directory
import yt_dlp
import os
import uuid
import shutil
import re # Özel karakterleri temizlemek için regular expression modülü

app = Flask(__name__)
TEMP_FOLDER = 'temp_files' # Geçici dosyaların ve MP3'lerin saklanacağı klasör
os.makedirs(TEMP_FOLDER, exist_ok=True) # Klasörü oluştur (varsa hata verme)

@app.route('/')
def index_page():
    return render_template('index.html')

def sanitize_filename(filename):
    """Dosya adlarından geçersiz karakterleri kaldırır veya değiştirir."""
    if filename is None:
        return ""
    # Geçersiz olabilecek karakterleri boşlukla veya alt çizgiyle değiştir
    filename = re.sub(r'[\\/*?:"<>|]', "_", filename) # Özel karakterleri "_" ile değiştir
    filename = filename.replace(" ", "_") # Boşlukları da alt çizgi yapalım
    # Çok uzun dosya adlarını kısalt (isteğe bağlı, dosya sistemleri limit koyabilir)
    if len(filename) > 180: # Örnek bir limit (uzantı hariç)
        name, ext = os.path.splitext(filename)
        filename = name[:170] + ext # Uzantıyı koruyarak kısalt
    return filename.strip() # Başındaki ve sonundaki boşlukları kaldır

def convert_video_to_mp3_with_yt_dlp(video_url, output_folder):
    """
    Verilen YouTube URL'sinden sesi indirir ve MP3'e dönüştürür.
    Başarılı olursa (mp3_filename_only, video_title) döndürür.
    Başarısız olursa (None, error_message) döndürür.
    """
    video_title_original = "Bilinmeyen_Video" # Varsayılan başlık
    mp3_filename_final = ""

    try:
        app.logger.info(f"Video bilgileri alınıyor. URL: {video_url}")
        # Önce sadece video bilgilerini alıp başlığı öğrenelim (indirme yapmadan)
        ydl_info_opts = {
            'quiet': True,
            'extract_flat': False, # Tüm bilgileri çekmeye çalış
            'skip_download': True,
            'nocheckcertificate': True,
        }
        with yt_dlp.YoutubeDL(ydl_info_opts) as ydl_info:
            info_dict = ydl_info.extract_info(video_url, download=False)
            video_title_original = info_dict.get('title', f"audio_{uuid.uuid4().hex[:8]}")

        app.logger.info(f"Orijinal video başlığı: {video_title_original}")

        # Dosya adı için başlığı temizle
        sanitized_base_name = sanitize_filename(video_title_original)
        if not sanitized_base_name: # Eğer temizleme sonrası başlık boş kalırsa
            sanitized_base_name = f"audio_{uuid.uuid4().hex[:8]}"
            
        mp3_filename_candidate = f"{sanitized_base_name}.mp3"
        final_mp3_path = os.path.join(output_folder, mp3_filename_candidate)

        # Eğer aynı isimde bir dosya zaten varsa, benzersiz bir isim ver
        count = 1
        base_name_for_unique, ext = os.path.splitext(mp3_filename_candidate)
        while os.path.exists(final_mp3_path):
            mp3_filename_candidate = f"{base_name_for_unique}_{count}{ext}"
            final_mp3_path = os.path.join(output_folder, mp3_filename_candidate)
            count += 1
        
        mp3_filename_final = mp3_filename_candidate # Kullanılacak son dosya adı
        app.logger.info(f"Hedef MP3 dosya adı: {mp3_filename_final}")
        
        # yt-dlp'nin MP3 dosyasını kaydedeceği tam yol (orijinal uzantı ile başlayıp sonra mp3 olur).
        # Postprocessor, key'de belirtilen dosya adını kullanmaya çalışır, 
        # bu yüzden outtmpl'yi doğrudan MP3 olarak ayarlamak daha iyi olabilir
        # ya da postprocessor'ın oluşturduğu dosyayı yeniden adlandırabiliriz.
        # Şimdilik, yt-dlp'nin adlandırmasına güvenelim ve dosyanın oluştuğunu kontrol edelim.
        # `outtmpl` sonuna `.%(ext)s` eklemek, indirilen orijinal formatın uzantısını alır.
        # Postprocessor bu dosyayı işleyip MP3 oluşturur ve `keepvideo: False` ile orijinali siler.
        # Oluşan MP3 dosyasının adı genellikle `outtmpl` şablonundaki temel ad + .mp3 olur.
        
        ydl_dl_opts = {
            'format': 'bestaudio/best',
            # Çıktı şablonu, postprocessor MP3'e çevireceği için temel adı ve .mp3 uzantısını hedefleyebiliriz.
            # Ancak yt-dlp bazen önce .webm vb. indirip sonra .mp3'e çevirir ve adını korur.
            # En güvenlisi, temel adı verip, postprocessor sonrası mp3'ü kontrol etmek.
            'outtmpl': os.path.join(output_folder, mp3_filename_final.replace('.mp3', '.%(ext)s')),
            'noplaylist': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': False,
            'verbose': False,
            'keepvideo': False, 
            'nocheckcertificate': True,
        }

        app.logger.info(f"yt-dlp indirme başlatılıyor. URL: {video_url}")
        app.logger.info(f"yt-dlp indirme seçenekleri: {ydl_dl_opts}")

        with yt_dlp.YoutubeDL(ydl_dl_opts) as ydl:
            ydl.download([video_url])
        
        # Oluşan MP3 dosyasının tam yolunu tekrar oluştur (postprocessor sonrası)
        # `outtmpl`'deki `%(ext)s` kısmı, indirilen orijinal dosyanın uzantısıydı.
        # Postprocessor bunu `.mp3` yapmalı ve dosya adı `mp3_filename_final` olmalı.
        expected_final_mp3_path = os.path.join(output_folder, mp3_filename_final)

        if os.path.exists(expected_final_mp3_path):
            app.logger.info(f"MP3 dosyası başarıyla oluşturuldu: {expected_final_mp3_path}")
            return mp3_filename_final, video_title_original # Kullanıcıya orijinal başlığı göster
        else:
            # Bazen dosya adı küçük harfe dönebilir veya farklı bir isimlendirme olabilir, kontrol edelim
            found_file = None
            base_name_check = os.path.splitext(mp3_filename_final)[0]
            for f_name in os.listdir(output_folder):
                if base_name_check.lower() in f_name.lower() and f_name.lower().endswith(".mp3"):
                    # Eğer dosya adını değiştirdiysek (örn: _1, _2 eklendiyse), onu kullanalım
                    # Ya da yt-dlp'nin adlandırdığı dosyayı kullanalım
                    if os.path.splitext(f_name)[0] == os.path.splitext(mp3_filename_final)[0]:
                         # Eğer benzersizleştirme sonrası adla eşleşiyorsa bu bizim dosyamızdır.
                        os.rename(os.path.join(output_folder, f_name), expected_final_mp3_path) # Hedef adımıza yeniden adlandır
                        found_file = expected_final_mp3_path
                        break
                    # Eğer benzersizleştirme öncesi temel adla eşleşiyorsa ve mp3_filename_final henüz yoksa, bunu kullanalım
                    elif not os.path.exists(expected_final_mp3_path) and sanitize_filename(video_title_original) in f_name:
                        os.rename(os.path.join(output_folder, f_name), expected_final_mp3_path)
                        found_file = expected_final_mp3_path
                        break
            
            if found_file and os.path.exists(found_file):
                 app.logger.info(f"MP3 dosyası (alternatif kontrolle) başarıyla bulundu ve yeniden adlandırıldı: {found_file}")
                 return os.path.basename(found_file), video_title_original
            else:
                app.logger.error(f"yt-dlp işlemi sonrası beklenen MP3 dosyası bulunamadı: {expected_final_mp3_path}")
                app.logger.error(f"TEMP_FOLDER içeriği ({output_folder}): {os.listdir(output_folder)}")
                return None, "MP3 dosyası oluşturulamadı veya bulunamadı."

    except yt_dlp.utils.DownloadError as e:
        app.logger.error(f"yt-dlp indirme/işleme hatası: {e}")
        return None, f"Video indirilemedi veya MP3'e dönüştürülemedi. (Hata: {str(e)})"
    except Exception as e:
        app.logger.error(f"Dönüştürme sırasında genel bir hata oluştu: {e}")
        import traceback
        app.logger.error(traceback.format_exc())
        return None, f"Beklenmedik bir sunucu hatası oluştu: {str(e)}"

@app.route('/api/convert', methods=['POST'])
def handle_conversion():
    data = request.get_json()
    video_url = data.get('url')
    app.logger.info(f"/api/convert endpoint'ine istek geldi. URL: {video_url}")

    if not video_url:
        app.logger.warning("URL girilmeden istek yapıldı.")
        return jsonify({'success': False, 'error': 'Lütfen bir YouTube video URL\'si girin.'}), 400

    mp3_file, title_or_error = convert_video_to_mp3_with_yt_dlp(video_url, TEMP_FOLDER)

    if mp3_file:
        download_url = f"/download/{mp3_file}"
        app.logger.info(f"Dönüştürme başarılı. İndirme linki: {download_url}, Başlık: {title_or_error}")
        return jsonify({'success': True, 'download_url': download_url, 'title': title_or_error, 'filename': mp3_file})
    else:
        app.logger.error(f"Dönüştürme başarısız. Hata: {title_or_error}")
        return jsonify({'success': False, 'error': title_or_error}), 500

@app.route('/download/<filename>')
def download_generated_file(filename):
    safe_filename = os.path.basename(filename) # Ekstra güvenlik
    app.logger.info(f"/download endpoint'ine istek geldi. Dosya: {safe_filename}")
    try:
        return send_from_directory(TEMP_FOLDER, safe_filename, as_attachment=True)
    except FileNotFoundError:
        app.logger.error(f"İndirilmek istenen dosya bulunamadı: {safe_filename}")
        return jsonify({'success': False, 'error': 'Dosya bulunamadı veya sunucudan silinmiş olabilir.'}), 404

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)