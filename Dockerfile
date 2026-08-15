# Dockerfile — build & chạy Media Tool Pro (Reflex) cho Render.
# Build context PHẢI là repo root vì app cần import core/, auth.py,
# cleanup.py, modes/, users_db.json ở root (xem
# reflex_app/media_tool_pro/backend/st_compat.py).
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

# QUAN TRỌNG: KHÔNG "|| true" ở đây nữa — lỗi export bị nuốt mất bấy lâu
# nay chính là nguyên nhân .web/app/root.jsx không được ghi ra (compile_app_root
# trong reflex/compiler/compiler.py bị exception nhưng RUN step vẫn "pass"
# nhờ || true, để lại .web/app chỉ có template gốc -> react-router build
# báo thiếu app/root.tsx). Để lộ traceback thật ra build log.
RUN reflex export --frontend-only --no-zip --loglevel debug
RUN echo "=== .web/app sau export (phải có root.jsx) ===" && find .web/app -type f

COPY Caddyfile /app/Caddyfile

CMD ["sh", "-c", "reflex run --env prod --backend-only --backend-host 0.0.0.0 --backend-port 8000 --loglevel debug & caddy run --config /app/Caddyfile --adapter caddyfile"]
