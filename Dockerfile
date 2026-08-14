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

# ĐÃ THỬ `reflex export --frontend-only` nhưng Reflex 0.9.8 (bản dùng
# Vite + react-router mới) không còn script "export" trong package.json
# template -> luôn báo "Script not found \"export\"" (lỗi nội bộ của bản
# Reflex này, không phải do cấu hình Dockerfile). Bỏ hẳn build-time export,
# để `reflex run --env prod` tự build + serve lúc container khởi động —
# đây là lệnh chính, được test nhiều nhất trong hệ sinh thái Reflex.
#
# API_URL: URL public của service (Render set qua biến RENDER_EXTERNAL_URL,
# điền tay ở render.yaml sau lần deploy đầu tiên biết được domain thật).
ARG API_URL
ENV API_URL=${API_URL}
# Bắt buộc Python xả log ngay lập tức (không buffer) — nếu không, khi
# `reflex run` chạy nền bằng "&" và crash sớm, log debug bị kẹt trong
# buffer và KHÔNG BAO GIỜ xuất hiện trên Render (đã gặp: container chạy
# nhưng cổng 8000 luôn "connection refused", không có bất kỳ log lỗi nào).
ENV PYTHONUNBUFFERED=1

# `reflex export` / `reflex run --env prod` gọi nội bộ lệnh `bun run export`
# nhưng lỗi "Script not found \"export\"" xảy ra dù package.json THẬT (in ra
# kiểm tra) có đủ script này — vì `reflex run --env prod` ở RUNTIME tự
# re-init lại .web theo đường khác và làm mất script đó (bug/khác biệt
# phiên bản Reflex 0.9.8). Né lỗi bằng cách: tự gọi `bun run export` NGAY
# LÚC BUILD (khi package.json chắc chắn đúng), build tĩnh 1 lần cho xong,
# rồi lúc chạy container CHỈ khởi động backend (--backend-only), không để
# `reflex run` tự động build lại frontend nữa.
RUN reflex init --loglevel debug \
 && echo "=== package.json scripts ===" \
 && python3 -c "import json; print(json.dumps(json.load(open('.web/package.json'))['scripts'], indent=2))" \
 && cd .web \
 && /root/.local/share/reflex/bun/bin/bun run export \
 && echo "=== .web build output ===" \
 && find . -maxdepth 3 -iname "*build*" -o -iname "*dist*" | grep -v node_modules | head -50

# Caddy làm reverse-proxy gộp frontend (port 3000 nội bộ) + backend
# (port 8000 nội bộ) ra DUY NHẤT 1 cổng $PORT mà Render forward traffic vào.
COPY Caddyfile /app/Caddyfile

# Render tự inject $PORT lúc runtime, Caddyfile đọc {$PORT} nên không cần EXPOSE cố định.
# QUAN TRỌNG: ở --env prod, Reflex bắt buộc frontend+backend chạy CHUNG 1
# cổng (đã gặp lỗi "In prod mode, frontend and backend must run on the same
# port." khi thử tách --frontend-port riêng khỏi --backend-port). Vì vậy
# CHỈ truyền --backend-port, không truyền --frontend-port; Caddy proxy toàn
# bộ traffic về đúng 1 cổng nội bộ đó (xem Caddyfile).
# Lưu ý: build frontend (bun/vite) diễn ra ở LẦN CHẠY ĐẦU TIÊN của container
# (không phải lúc docker build) nên request đầu tiên sau khi container khởi
# động / thức dậy (free tier) có thể chậm hơn bình thường vài chục giây.
CMD ["sh", "-c", "reflex run --env prod --backend-only --backend-host 0.0.0.0 --backend-port 8000 --loglevel debug & caddy run --config /app/Caddyfile --adapter caddyfile"]
