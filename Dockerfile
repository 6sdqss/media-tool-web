FROM python:3.12-slim

RUN apt-get update -y && apt-get install -y --no-install-recommends \
    curl unzip caddy && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir -r reflex_app/requirements.txt

WORKDIR /app/reflex_app

ARG API_URL
ENV API_URL=${API_URL}
ENV PYTHONUNBUFFERED=1

# DEBUG: chạy export, KHÔNG để build fail sớm — in ra package.json thật +
# nội dung .web/app để biết chính xác "export" script bị mất ở bước nào.
RUN reflex export --frontend-only --no-zip --loglevel debug; \
    echo "EXPORT_EXIT_CODE=$?"; \
    echo "=== .web/package.json ==="; cat .web/package.json 2>&1; \
    echo "=== .web/app files ==="; find .web/app -type f 2>&1; \
    echo "=== root package.json (persisted) ==="; cat package.json 2>&1 || echo "(no root package.json)"; \
    echo "=== reflex.lock dir ==="; find reflex.lock -type f 2>&1 || echo "(no reflex.lock)"

COPY Caddyfile /app/Caddyfile

CMD ["sh", "-c", "reflex run --env prod --backend-only --backend-host 0.0.0.0 --backend-port 8000 --loglevel debug & caddy run --config /app/Caddyfile --adapter caddyfile"]
