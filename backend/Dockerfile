# stadio temp che compila esclusivamente il connettore mariaDB
FROM python:3.11-slim-bookworm AS mariadb-builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        pkg-config \
        libmariadb-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip wheel \
    --no-cache-dir \
    --wheel-dir /wheels \
    mariadb==1.1.14


FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libmariadb3 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY --from=mariadb-builder /wheels /wheels

RUN pip install --upgrade pip \
    && pip install \
        --no-cache-dir \
        --find-links=/wheels \
        -r requirements.txt \
    && rm -rf /wheels

RUN python -m playwright install --with-deps chromium

COPY src ./src

EXPOSE 8003

CMD ["uvicorn", "src.server.server:app", "--host", "0.0.0.0", "--port", "8003"]