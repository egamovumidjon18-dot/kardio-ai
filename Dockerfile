# CardioPath AI — server (FastAPI + ONNX Runtime, faqat CPU).
# Model og'irliklari (weights/) va ma'lumot (baza, yozuvlar) obrazga KIRMAYDI: ular docker-compose.yml da
# tashqi papka sifatida ulanadi. Sabab: ayrim og'irliklar faqat tadqiqot litsenziyali ma'lumotda o'qitilgan
# (masalan EchoNext), obraz esa boshqalarga berilishi mumkin; bemor ma'lumoti hech qachon obrazda bo'lmasligi kerak.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# rapidocr (MNO rasm OCR) opencv'ni talab qiladi: unga libGL va glib kerak
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# root bo'lmagan foydalanuvchi; /data — baza va yozuvlar uchun
RUN useradd --create-home --uid 10001 cardiopath \
 && mkdir -p /data /app/models \
 && chown -R cardiopath:cardiopath /data /app/models
USER cardiopath

ENV CARDIOPATH_DB=/data/cardiopath.db \
    CARDIOPATH_MODELS=/app/models/pcg \
    CARDIOPATH_MODE=research \
    CARDIOPATH_AUTH=off

EXPOSE 8010
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8010/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "api.main:default_app", "--factory", "--host", "0.0.0.0", "--port", "8010"]
