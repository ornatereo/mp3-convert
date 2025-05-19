# 1. Temel Python İmajını Seçin
# Python 3.9'un slim (daha küçük) versiyonunu kullanıyoruz.
# Uygulamanızla uyumlu başka bir Python 3.x sürümü de seçebilirsiniz (örn: python:3.10-slim).
FROM python:3.9-slim

# 2. Ortam Değişkenleri (İsteğe Bağlı ama İyi Pratikler)
# Python'un logları tamponlamasını engeller, böylece loglar anında görünür.
ENV PYTHONUNBUFFERED 1
# Pip'in en son sürümünü kullanmasını ve sanal ortam dışına kurulum yapmamasını sağlar.
ENV PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random

# 3. Sistem Bağımlılıklarını Kurun (ffmpeg dahil)
# apt-get (Debian/Ubuntu tabanlı imajlar için paket yöneticisi) kullanılır.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    # Eğer uygulamanızın başka sistem kütüphanelerine ihtiyacı varsa buraya ekleyebilirsiniz
    # Örneğin, resim işleme için libjpeg-dev, zlib1g-dev vb. (şu anki projeniz için gerekmeyebilir)
    && rm -rf /var/lib/apt/lists/*

# 4. Uygulama İçin Bir Çalışma Dizini Oluşturun ve Ayarlayın
WORKDIR /app

# 5. Python Bağımlılıklarını Kurun
# Önce requirements.txt dosyasını kopyalayıp bağımlılıkları kurmak, Docker katman önbelleklemesini daha iyi kullanır.
# Eğer requirements.txt değişmediyse, bu katman yeniden çalıştırılmaz.
COPY requirements.txt .
RUN pip install -r requirements.txt

# 6. Uygulama Kodunun Tamamını Kopyalayın
# requirements.txt'den sonra kopyalamak, kodunuzdaki her değişiklikte
# bağımlılıkların yeniden kurulmasını engeller.
COPY . .

# 7. Uygulamanın Dinleyeceği Port (Render bunu genellikle $PORT çevre değişkeniyle geçersiz kılar)
# Bu satır bilgilendirme amaçlıdır ve genellikle Render tarafından yönetilir.
# EXPOSE 5000 

# 8. Uygulamayı Başlatma Komutu
# Gunicorn'u WSGI sunucusu olarak kullanıyoruz.
# app:app -> app.py dosyasındaki Flask uygulamanızın adı (app = Flask(__name__))
# Render, $PORT çevre değişkenini otomatik olarak ayarlar, bu yüzden onu kullanıyoruz.
# --workers: Aynı anda işlenebilecek istek sayısı. Ücretsiz planlar için 1 veya 2 genellikle yeterlidir.
# --threads: Her bir worker'ın kullanabileceği thread sayısı (I/O bound işler için faydalı).
# --timeout 0: Gunicorn'un worker'ları zaman aşımına uğratmasını engeller. 
#             Bu, uzun süren video dönüştürme işlemleri için önemlidir.
#             Ancak Render'ın kendi platform seviyesinde bir istek zaman aşımı olabilir, bunu kontrol edin.
#             Eğer Render'ın zaman aşımı varsa (örn: 5 dakika), Gunicorn timeout'unu ondan biraz kısa tutmak iyi olabilir.
#             Şimdilik "0" (sınırsız) olarak bırakıyoruz, ancak Render dokümantasyonunu kontrol edin.
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:$PORT", "--workers", "1", "--threads", "2", "--timeout", "0"]

# Alternatif Başlatma Komutu (Waitress ile, eğer platform bağımsız bir sunucu tercih ederseniz):
# Önce requirements.txt'e 'waitress' eklemelisiniz.
# CMD ["waitress-serve", "--host=0.0.0.0", "--port=$PORT", "app:app"]
