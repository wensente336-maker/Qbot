FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# greenlet 等需要编译；libpq-dev 供 asyncpg/psycopg 编译兜底
# ffmpeg：渲染 / 质检 / 抽音轨；fonts-noto-cjk：中文字幕烧录不出现方框
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        ffmpeg \
        fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]