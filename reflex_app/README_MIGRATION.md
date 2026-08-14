# Media Tool Pro — Migration Streamlit → Reflex

## 1. Chạy thử ở máy local

```bash
cd reflex_app
python3 -m venv .venv && source .venv/bin/activate      # tuỳ chọn nhưng khuyến nghị
pip install -r requirements.txt

reflex init      # chỉ lần đầu — tải Bun (frontend runtime), cần internet
reflex run       # chạy dev server: frontend :3000, backend :8000
```

Mở `http://localhost:3000`.

**Lưu ý quan trọng:** app Reflex phải chạy với `sys.path`/`cwd` sao cho
`media_tool_pro/backend/st_compat.py` tự động `chdir` về thư mục gốc repo
(nơi có `users_db.json`, `core/`, `auth.py`...). Việc này đã được xử lý tự
động trong `st_compat.py` — không cần cấu hình gì thêm, chỉ cần **giữ
nguyên cấu trúc thư mục** `repo_root/reflex_app/media_tool_pro/...`.

### Biến môi trường (thay cho `st.secrets` trong bản Streamlit cũ)
| Biến | Dùng cho |
|---|---|
| `GITHUB_TOKEN`, `GITHUB_REPO`, `GITHUB_BRANCH` | Auto-sync `users_db.json` lên GitHub (auth.py, admin panel) |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Google Drive mode — dán nguyên JSON service account (1 dòng) |

## 2. Deploy miễn phí

### Cách A — Reflex Cloud (khuyến nghị, đơn giản nhất)
1. `pip install reflex`, `reflex login` (tài khoản Reflex Cloud, free tier).
2. Trong `reflex_app/`: `reflex deploy`.
3. CLI sẽ hỏi app name, region — chọn mặc định. Free tier đủ cho demo/nội bộ
   (giới hạn tài nguyên nhưng không mất phí).
4. Set biến môi trường (`GITHUB_TOKEN`, ...) qua dashboard Reflex Cloud nếu cần.
5. **users_db.json**: Reflex Cloud dùng container tạm thời như Streamlit Cloud
   → cấu hình `GITHUB_TOKEN`/`GITHUB_REPO` để không mất dữ liệu user khi container
   restart (giống cơ chế auto-sync GitHub đã có sẵn trong `auth.py`).

### Cách B — Render.com free Web Service (fallback)
1. Push code lên GitHub (thao tác git sẽ làm ở bước riêng, không nằm trong
   phạm vi lần này).
2. Trên Render: New → Web Service → connect repo.
3. Root Directory: `reflex_app`
4. Build Command:
   ```
   pip install -r requirements.txt && reflex init && reflex export --frontend-only --no-zip
   ```
5. Start Command:
   ```
   reflex run --env prod --backend-only
   ```
   (hoặc dùng `reflex run --env prod` nếu Render cho phép chạy cả 2 port —
   cần cấu hình thêm reverse-proxy vì Reflex mặc định tách frontend :3000 /
   backend :8000; xem docs Reflex "Self-Hosting" để cấu hình 1-port qua Caddy/Nginx
   nếu dùng Render free tier chỉ mở 1 port).
6. Set Environment Variables giống Cách A.

## 3. Checklist tính năng — đã port vs còn việc cần làm

### Đã port đầy đủ, dùng logic gốc không đổi
- [x] Đăng nhập / Đăng ký (bọc `auth.authenticate`, `auth.register_user` —
      PBKDF2 hashing, brute-force lock, GitHub sync — logic 100% giữ nguyên).
- [x] Đổi mật khẩu (`auth.change_own_password`).
- [x] Mode **Web/TGDD**: scrape sản phẩm (`modes/tgdd_scraper.py` — pure Python,
      dùng lại y nguyên), build TaskItem, cookie loader, chạy qua
      `core.batch.BatchManager.start_background` — KHÔNG đổi core/batch.py.
- [x] Mode **Drive**: file/folder Google Drive qua Service Account
      (`core.download`), giữ nguyên logic gốc.
- [x] Mode **Local**: upload nhiều file/ZIP, giải nén, dedup, chạy qua
      BatchManager — giữ nguyên logic gốc (`core.validation`, `core.imaging`).
- [x] Progress/queue realtime: thay cho vòng lặp `time.sleep()+st.rerun()` của
      Streamlit, dùng Reflex background event handler (`@rx.event(background=True)`)
      polling `core.batch.BatchManager` mỗi 0.8s — BatchManager (thread nền +
      pause/cancel) hoàn toàn không đổi.
- [x] Tải ZIP kết quả + Report CSV.
- [x] Cleanup workspace cũ (`cleanup_old_workspaces`).
- [x] Preset picker (`core.presets.load_all`).
- [x] Admin Panel: duyệt/khoá/xoá/reset mật khẩu/phân quyền, GitHub pull/push
      — bọc nguyên các hàm trong `auth.py` (không viết lại).
- [x] Trang Guide (nội dung hướng dẫn) — port nguyên nội dung tiếng Việt.
- [x] Dark/Light mode — dùng `rx.color_mode` built-in của Reflex (native,
      không cần CSS thủ công như `ui/theme.py` cũ).

### Đã port đầy đủ tính năng (đợt cập nhật sau)
- [x] **Studio (mode_adjust.py, 824 dòng UI Streamlit)** — port lại hoàn
      toàn sang `backend/studio_state.py` + `components/modes.py::render_studio`,
      dùng lại các hàm thật của `utils.py` (compat shim, KHÔNG sửa):
      `estimate_default_scale_for_size`, `build_live_preview_b64`,
      `resize_to_multi_sizes`, `merge_final_with_adjusted`, `make_zip`,
      `open_zip_for_download`, `readable_file_size`, `get_size_label`,
      `apply_name_template`, `add_to_history`, `EXPORT_FORMATS`.
      Tính năng: nạp batch gần nhất (nút "🔄 Nạp batch gần nhất" ở tab
      Studio, tự nạp khi chuyển tab); bộ lọc (từ khoá/sản phẩm/trạng thái);
      pagination 6/10/16/24 mỗi trang; card từng ảnh với slider
      Scale/X/Y + nút Reset/±5% + checkbox chọn + badge trạng thái
      (chưa render / đã render / đã chỉnh) + cảnh báo ảnh nhỏ; bulk-ops
      (chọn tất cả/bỏ chọn/chọn ảnh nhỏ/xoá chọn, áp scale/X/Y hàng loạt
      cho trang hiện tại hoặc toàn bộ kết quả lọc); render hàng loạt ảnh
      đã chọn qua `@rx.event(background=True)` (polling progress giống
      `batch_state.py::_poll_loop`), mỗi ảnh dùng đúng scale% riêng của nó;
      xuất ZIP gộp (final + adjusted, ưu tiên bản đã chỉnh) và tải ZIP gốc
      / ZIP gộp; KPI batch.

      **Khác biệt có chủ đích so với gọi y nguyên các hàm trong
      mode_adjust.py** (lý do nêu chi tiết ở đầu `studio_state.py`):
      1. `mode_adjust.py` gọi `resize_to_multi_sizes(...)` với 5 đối số vị
         trí trong khi hàm thật trong `utils.py` chỉ nhận 4 — gọi y nguyên
         sẽ luôn `TypeError`. Studio Reflex gọi đúng chữ ký thật.
      2. `mode_adjust.py` gọi `estimate_default_scale_for_size(width,
         height, tw, th)` (4 số) nhưng chữ ký thật nhận `source_path` (mở
         ảnh bằng PIL) — Studio Reflex gọi đúng chữ ký thật.
      3. `resize_to_multi_sizes` không tự tạo thư mục con theo
         `group_name` như `core/batch.py` (`final/size_label/group/name.ext`).
         Studio Reflex vẫn dùng nguyên hàm này để resize (không viết lại
         pixel-engine), rồi tự di chuyển file kết quả vào đúng vị trí lồng
         thư mục khớp với cây `final/` để `merge_final_with_adjusted` so
         khớp đường dẫn tương đối chính xác.
      4. **Pan (offset X/Y) không áp dụng vào ảnh export thật** — đúng như
         hành vi thật của bản gốc: `core.imaging.apply_size`/
         `resize_letterbox` không có tham số dịch chuyển pixel nào, nên cả
         bản Streamlit gốc (dù sửa lỗi gọi hàm) cũng chỉ dùng offset cho
         CSS transform ở live-preview, không áp dụng khi resize/export.
         Studio Reflex giữ đúng giới hạn này — slider X/Y vẫn lưu và hiển
         thị được nhưng không đổi pixel khi render (không giả vờ hỗ trợ).
      5. Nguồn "batch vừa chạy" lấy từ `core.state.batch()`/`items()` (v11)
         thay vì `st.session_state["last_batch_manifest/cfg/meta"]` —
         key đó thuộc schema TaskItem cũ hơn không còn tồn tại trong
         `core/batch.py` hiện tại của repo (xem comment đầu file).

### Chưa làm / cần theo dõi thêm (follow-up)
- [ ] **Đa người dùng đồng thời thực sự độc lập**: vì `core/batch.py` và
      `auth.py` (gốc) lưu state qua `st.session_state`, và Reflex không có
      global session_state kiểu Streamlit, `st_compat.py` dùng 1 dict Python
      **global cho toàn server** để giả lập. Hệ quả: toàn hệ thống chỉ chạy
      **1 batch cùng lúc** (không phải 1 batch/user), và bộ đếm brute-force
      login cũng dùng chung. Với tool nội bộ/1 team nhỏ, việc này chấp nhận
      được. Nếu cần multi-tenant thật (nhiều batch song song, nhiều user độc
      lập), phải viết lại phần lưu trữ state trong `core/batch.py`/`auth.py`
      (ngoài phạm vi "giữ core/ nguyên vẹn" của lần migrate này).
- [ ] `reflex run`/`reflex export` CHƯA được chạy thử thành công trong sandbox
      dùng để build lần này — môi trường sandbox không có internet ra
      `bun.sh` nên bước tải Bun (frontend build tool bắt buộc của Reflex) bị
      chặn (`403 Forbidden`). Đã verify thay thế bằng cách import toàn bộ
      app Python (`media_tool_pro.media_tool_pro.app`) và compile trang qua
      `app._compile_page()` — **không có ImportError/SyntaxError/UntypedVarError**
      ở tầng Python/component-tree. Việc `reflex run` thực tế build frontend
      (Bun/React) cần chạy ở máy có internet đầy đủ — rất nên làm bước này
      trước khi deploy thật.
- [ ] Studio: chưa test qua trình duyệt thật (cùng lý do không có `bun.sh`
      trong sandbox) — mới verify ở tầng `app._compile_page('index')` (không
      lỗi import/syntax/Var). Nên chạy `reflex run` thật + click thử luồng
      Render → Export ZIP trên máy có internet trước khi bàn giao.
- [ ] Studio chưa có: preset save/load riêng cho Studio (bản gốc cũng không
      có tính năng này — mode_adjust.py chỉ dùng preset của batch gốc), và
      chưa hỗ trợ pan pixel thật (xem mục giải thích ở trên — bản gốc cũng
      vậy).
- [ ] Chưa test tải file rất lớn qua `rx.upload` (giới hạn size mặc định của
      Reflex có thể khác Streamlit `file_uploader` — nên set
      `max_upload_size` nếu cần cho phép ZIP lớn).
- [ ] Toast lỗi hiện dùng `rx.callout` inline (không phải popup toast nổi) —
      dễ đổi sang `rx.toast.error(...)` nếu muốn UX giống thông báo nổi hơn.

## 4. Kiến trúc & các file quan trọng
```
reflex_app/
  rxconfig.py
  requirements.txt
  media_tool_pro/
    media_tool_pro.py          # app entry, add_page("/")
    backend/
      st_compat.py             # shim streamlit (session_state/secrets) + chdir repo root
      auth_state.py            # bọc auth.py (đăng nhập/đăng ký/đổi mật khẩu)
      batch_state.py           # bọc core.batch.BatchManager cho 3 mode + polling
      admin_state.py           # bọc auth.py (quản trị user)
      studio_state.py          # Studio rút gọn (PIL ImageEnhance)
    components/
      ui.py                    # header, sidebar, progress panel, queue table
      modes.py                 # nội dung từng tab (Home/Web/Drive/Local/Studio/Guide/Admin)
    pages/
      index.py                 # trang duy nhất: login hoặc dashboard (rx.cond)
```

Toàn bộ `core/*.py`, `auth.py` (logic hash/verify), `cleanup.py`,
`users_db.json`, `modes/tgdd_scraper.py` được **import trực tiếp từ repo
root, không sao chép, không sửa đổi**.
