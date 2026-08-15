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
# `reflex init` MỘT MÌNH không cài đủ devDependencies (react-router, vite...)
# — các gói đó chỉ được `reflex export` cài (qua "bun add -d ..." nội bộ),
# nhưng `reflex export` LẠI lỗi ở đúng bước cuối "bun run export" (Script
# not found / command not found tuỳ lúc — bug của Reflex 0.9.8). Giải pháp:
# để `reflex export` chạy hết phần cài đặt (bỏ qua lỗi ở bước cuối bằng
# "|| true"), sau đó TỰ gọi react-router build thủ công bằng bun x — lúc
# này node_modules/.bin/react-router đã tồn tại thật.
# Reflex (init/export/run) có lúc BỎ QUA bước cài devDependencies
# (react-router, vite...) do cơ chế cache nội bộ (project hash) không ổn
# định — có build cài đủ (~30s, 2 đợt "bun add"), có build chỉ mất 1.4s và
# thiếu hẳn node_modules/.bin. Danh sách gói chính xác đã thấy lặp lại
# nhiều lần ở các build cài đủ, nên tự cài THẲNG bằng bun, không phụ thuộc
# Reflex quyết định có cài hay không.
RUN reflex init --loglevel debug
# `reflex export` tự "Compile pages" (Python -> app/root.tsx và các file
# react khác) TRƯỚC khi cài gói/build — bước compile này KHÔNG xảy ra nếu
# chỉ gọi `reflex init`. Thiếu nó thì `react-router build` báo "Could not
# find a root route module in app/root.tsx". Nên chạy `reflex export` cho
# nó tự compile + cài gói (bỏ qua crash ở bước cuối "bun run export"),
# RỒI mới tự cài bù devDependencies còn thiếu + tự build bằng bun x.
RUN reflex export --frontend-only --no-zip --loglevel debug || true
RUN echo "=== .web top-level after export attempt ===" \
 && find .web -maxdepth 2 -not -path "*/node_modules*" \
 && echo "=== react-router.config.js ===" \
 && cat .web/react-router.config.js 2>&1 || echo "MISSING react-router.config.js"
RUN cd .web \
 && BUN=/root/.local/share/reflex/bun/bin/bun \
 && $BUN add --legacy-peer-deps -d \
      "@react-router/dev@7.18.2" "postcss@8.5.23" "vite@8.0.16" \
      "autoprefixer@10.5.4" "@react-router/fs-routes@7.18.2" \
      "@emotion/react@11.14.0" "postcss-import@16.1.1" \
 && $BUN add --legacy-peer-deps \
      "@react-router/node@7.18.2" "rehype-katex@7.0.1" "remark-gfm@4.0.1" \
      "react-debounce-input@3.3.0" "react-markdown@10.1.0" "sonner@2.0.7" \
      "universal-cookie@8.1.2" "rehype-unwrap-images@1.0.0" \
      "react-syntax-highlighter@16.1.1" "@radix-ui/themes@3.3.0" "react@19.2.8" \
      "@radix-ui/react-accordion@1.2.18" "react-router@7.18.2" \
      "socket.io-client@4.8.3" "lucide-react@1.26.0" "rehype-raw@7.0.0" \
      "remark-math@6.0.0" "react-error-boundary@6.1.2" "react-router-dom@7.18.2" \
      "isbot@5.2.1" "react-helmet@6.1.0" "react-dom@19.2.8" "react-dropzone@15.0.0" \
 && echo "=== node_modules/.bin listing ===" \
 && ls -la node_modules/.bin/ 2>&1 | head -30 \
 && echo "=== running bun x react-router build ===" \
 && $BUN x react-router build \
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
