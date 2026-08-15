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

# `reflex export` luôn lỗi ở đúng bước cuối "bun run export" (Script not
# found / react-router: command not found) vì bước cài devDependencies bên
# trong Reflex 0.9.8 không ổn định (có lúc bỏ qua, có lúc package.json ghi
# ra dependencies rỗng dù log báo "250 packages installed"). Phần QUAN
# TRỌNG mà bước này làm ĐÚNG là compile Python -> .web/app/root.jsx +
# routes.js (đã xác minh bằng debug build trước). Nên: để nó chạy hết (bỏ
# qua lỗi cuối bằng "|| true"), sau đó TỰ cài đúng danh sách
# dependencies/devDependencies (copy từ reflex_base/constants/installer.py)
# bằng bun add, rồi tự chạy lại đúng script "export" (= "react-router
# build") mà package.json đã định nghĩa.
RUN (reflex export --frontend-only --no-zip --loglevel debug || true) \
 && echo "=== .web/app sau compile (phải có root.jsx) ===" \
 && find .web/app -type f \
 && cd .web \
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
 && echo "=== node_modules/.bin ===" \
 && ls node_modules/.bin/ | grep -i router \
 && $BUN run export \
 && echo "=== build output ===" \
 && find build -maxdepth 3

COPY Caddyfile /app/Caddyfile

CMD ["sh", "-c", "reflex run --env prod --backend-only --backend-host 0.0.0.0 --backend-port 8000 --loglevel debug & caddy run --config /app/Caddyfile --adapter caddyfile"]
