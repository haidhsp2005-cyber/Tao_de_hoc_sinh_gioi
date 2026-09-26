# Olympiad Problem Forge 🏆
## Hệ Thống Web AI Agent Tạo Đề Thi Học Sinh Giỏi Tin Học & 10 Test Cases Chuẩn Themis

Hệ thống chuyên môn cao cấp dành cho Giáo viên bồi dưỡng và Đội tuyển Học sinh giỏi Tin học, ứng dụng mô hình **Google Gemini Flash** kết hợp **Ollama Offline (Qwen 2.5:7B)** cùng quy trình tư duy **AI Agent nhiều giai đoạn (Multi-stage Chain of Thought)**.

---

### ✨ Tính Năng Nổi Bật

1. **Đầy đủ 6 Chủ đề Cốt lõi của Kỳ thi HSG Tin học:**
   - 🔢 **Xử lý số & Số học**: Đồng dư, Nghịch đảo modulo, Sàng số nguyên tố, Phân tích thừa số, Tổ hợp $C(n,k)$, Lũy thừa ma trận, Phi hàm Euler.
   - 🔤 **Xử lý chuỗi (String)**: Thuật toán KMP, Rolling Hashing, Cây tiền tố Trie, Suffix Array, Z-Algorithm, Manacher Palindrome.
   - 📦 **Quy hoạch động cơ bản (Basic DP)**: LIS $O(N \log N)$, LCS, Balo 0/1 & Không giới hạn, DP trên bảng/lưới, Đếm số cách.
   - ⚡ **Quy hoạch động nâng cao (Advanced DP)**: DP Bitmask, DP Tree (trên cây) & Rerooting, DP Digit (chữ số), Bao lồi (Convex Hull Trick / Li Chao Tree), Tối ưu bằng Segment Tree / Fenwick.
   - 🕸️ **Đồ thị cơ bản (Basic Graph)**: BFS / DFS, Dijkstra, Kruskal (DSU), Floyd-Warshall, Topological Sort, Đồ thị hai phía.
   - 🌲 **Đồ thị nâng cao (Advanced Graph)**: Tổ tiên chung gần nhất (LCA), Cầu & Khớp (Tarjan), Thành phần liên thông mạnh (SCC), Luồng cực đại (Max Flow - Dinic/Min-Cut), Phân rã cây (HLD), 2-SAT.

2. **Phân cấp 4 mức độ đề thi chuẩn Việt Nam:**
   - 🟢 **HSG Cấp Trường / Cấp Huyện** (Dễ - Khởi đầu)
   - 🟡 **HSG Cấp Tỉnh / TP** (Trung bình - Khá, chuẩn phân hóa)
   - 🟠 **Chọn Đội Tuyển Tỉnh** (Khó - Vòng 2 chọn đội tuyển chính thức thi HSG Quốc gia)
   - 🔴 **HSG Quốc Gia (VOI / Pre-VOI)** (Cực khó - Chuyên sâu)

3. **Quy trình AI Agent Chuyên Nghiệp (Reasoning Pipeline):**
   - **Giai đoạn 1:** Lên ý tưởng, bối cảnh thực tế/dân gian, phát biểu toán học hình thức, thiết kế bảng phân bố Subtask (% điểm số và ràng buộc).
   - **Giai đoạn 2:** Phân tích thuật toán chi tiết từ vét cạn Subtask 1 đến tối ưu hoàn chỉnh, cung cấp mã nguồn C++20 chuẩn tối ưu (Fast I/O, `freopen`) và mã Python 3.
   - **Giai đoạn 3:** Khởi tạo và kiểm chứng **10 BỘ TEST CASES** từ dễ đến cực đại, bẫy số nguyên 64-bit, trường hợp góc hiểm hóc.
   - **Giai đoạn 4:** Viết script `generator.py` và đóng gói Contest Package chuẩn Themis.

4. **Trình duyệt, Xuất Word .docx & Đóng gói Themis/CMS (ZIP):**
   - Xem trực quan từng test case (Input và Output đối chiếu song song).
   - Xuất file Word `.docx` chuẩn font Times New Roman, công thức toán học Cambria Math sạch đẹp không tì vết.
   - Tải về tệp `.ZIP` trọn gói chỉ với 1 click, giải nén và nạp trực tiếp vào phần mềm chấm thi Themis hoặc CMS.

---

### 🌐 Hướng Dẫn Triển Khai Lên Render.com (Miễn phí 100%)

Dự án đã được cấu hình sẵn tệp `render.yaml`, `Procfile` và `requirements.txt` chuẩn Cloud-Native:

#### Bước 1: Đẩy mã nguồn lên GitHub
1. Tạo một repository mới trên [GitHub](https://github.com/new) (ví dụ: `olympiad-exam-generator`).
2. Chạy lệnh đẩy code từ máy tính:
   ```bash
   git add .
   git commit -m "Initial commit for Render deployment"
   git branch -M main
   git remote add origin https://github.com/<tai-khoan-cua-ban>/olympiad-exam-generator.git
   git push -u origin main
   ```

#### Bước 2: Tạo Web Service trên Render.com
1. Truy cập [Render.com](https://dashboard.render.com/) và đăng nhập (bằng tài khoản GitHub).
2. Nhấn nút **New +** ở góc trên cùng bên phải $\to$ Chọn **Web Service**.
3. Chọn repository `olympiad-exam-generator` mà bạn vừa đẩy lên.
4. Render sẽ tự động điền các thông tin:
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python server.py`
   - **Plan Type:** `Free`

#### Bước 3: Cấu hình API Key trên Render
1. Tại mục **Environment Variables** (Biến môi trường), thêm:
   - **Key:** `GEMINI_API_KEY` (hoặc `GEMINI_API_KEYS` nếu dùng nhiều key cách nhau bằng dấu phẩy)
   - **Value:** Dán Google Gemini API Key của bạn vào đây (lấy miễn phí tại [Google AI Studio](https://aistudio.google.com/app/apikey)).
2. Bấm **Create Web Service**.
3. Đợi khoảng 1-2 phút để Render tự động tải thư viện và khởi động máy chủ.
4. Bạn sẽ nhận được đường link web dạng: `https://olympiad-exam-generator.onrender.com` để sử dụng online từ mọi thiết bị (máy tính, điện thoại, máy tính bảng)!

---

### 💻 Hướng Dẫn Chạy Cục Bộ (Local Windows)

- **Cách 1 (Nhanh nhất):** Nhấp đúp vào tệp `run.bat` hoặc shortcut `Chay_Tao_De_Thi_HSG.bat` ngoài Desktop.
- **Cách 2 (Dòng lệnh):**
  ```powershell
  python server.py
  ```
  Sau đó mở trình duyệt truy cập: `http://localhost:5000`.
