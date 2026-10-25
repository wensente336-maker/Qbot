FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# greenlet 等需要编译；libpq-dev 供 asyncpg/psycopg 编译兜底
# ffmpeg：渲染 / 质检 / 抽音轨；fonts-noto-cjk：中文字幕烧录不出现方框
# 国内机器换腾讯云 Debian 镜像（deb.debian.org 在国内长连接易卡住）
RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i 's|http://deb.debian.org/debian|http://mirrors.cloud.tencent.com/debian|g' /etc/apt/sources.list.d/debian.sources; \
    fi; \
    apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=3 update; \
    apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=3 install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        ffmpeg \
        fonts-noto-cjk; \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# 国内机器可用镜像源构建：--build-arg PIP_INDEX_URL=http://mirrors.tencentyun.com/pypi/simple/
ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_TRUSTED_HOST=
RUN pip install --no-cache-dir -i "${PIP_INDEX_URL}" \
        ${PIP_TRUSTED_HOST:+--trusted-host "${PIP_TRUSTED_HOST}"} \
        -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]