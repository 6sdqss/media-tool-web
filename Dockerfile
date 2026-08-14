# Dockerfile — build & chạy Media Tool Pro (Reflex) cho Render / bất kỳ Docker host nào.
# Build context PHẢI là repo root (không phải reflex_app/) vì app cần import
# core/, auth.py, cleanup.py, modes/, users_db.json nằm ở root (xem
# reflex_app/media_tool_pro/backend/st_compat.py).
FROM python:3.12-slim

RUN apt-get update -y && apt-get install -y --no-install-recommends \
    curl unzip caddy && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

# requirements.txt gốc (Group B: auth/cleanup/mode_adjust...) + reflex_app riêng
RUN pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir -r reflex_app/requirements.txt

WORKDIR /app/reflex_app

# KHÔNG chạy `reflex init` riêng trước — nó tạo sẵn .web/ bằng template
# không có script "export" trong package.json, khiến bước export sau báo
# "Script not found \"export\"" (đã gặp lỗi này khi deploy lần đầu trên
# Render). Để `reflex export` tự init + build trong 1 bước duy nhất.
#
# API_URL: URL public của service (Render set qua biến RENDER_EXTERNAL_URL,
# điền tay ở render.yaml sau lần deploy đầu tiên biết được domain thật).
ARG API_URL
ENV API_URL=${API_URL}
RUN reflex export --frontend-only --no-zip --loglevel debug

# Caddy làm reverse-proxy gộp frontend (static, port 3000 nội bộ) + backend
# (port 8000 nội bộ) ra DUY NHẤT 1 cổng $PORT mà Render forward traffic vào.
COPY Caddyfile /app/Caddyfile

# Render tự inject $PORT lúc runtime, Caddyfile đọc {$PORT} nên không cần EXPOSE cố định
CMD ["sh", "-c", "reflex run --env prod --backend-only --backend-port 8000 & caddy run --config /app/Caddyfile --adapter caddyfile"]
