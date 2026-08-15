# Dockerfile — build & chạy Media Tool Pro (Reflex) cho Render.
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

# `reflex export` tự nó bị lỗi "Script not found export" ở đúng bước cuối
# (bun run export) dù .web/package.json thực tế CÓ đủ script này (đã xác
# minh bằng cách in file ra ngay sau khi lệnh fail) -> đây là race condition/
# bug nội bộ của Reflex 0.9.8 (bun đọc package.json trước khi ghi xong, hoặc
# workspace resolution nhầm). Vì .web/package.json và reflex.lock/package.json
# đã đúng ngay sau khi export "fail", ta chỉ cần chạy lại đúng lệnh build đó
# một lần nữa thủ công -> chạy trên state đĩa đã ổn định -> thành công.
RUN (reflex export --frontend-only --no-zip --loglevel debug || true) \
 && echo "=== retry: bun run export thủ công trên .web/package.json đã ổn định ===" \
 && cd .web \
 && /root/.local/share/reflex/bun/bin/bun run export \
 && echo "=== build output ===" \
 && find build -maxdepth 3 2>&1 | head -50

COPY Caddyfile /app/Caddyfile

CMD ["sh", "-c", "reflex run --env prod --backend-only --backend-host 0.0.0.0 --backend-port 8000 --loglevel debug & caddy run --config /app/Caddyfile --adapter caddyfile"]
