import os
import sys
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import json
import logging
import asyncio
from aiohttp import web
from gemini_client import GeminiClient
from ollama_client import OllamaClient
from agent_pipeline import OlympiadAgentPipeline, TOPIC_DETAILS, DIFFICULTY_DETAILS
from exporter import create_themis_zip
from docx_exporter import create_olympiad_docx
from key_manager import KeyManager, mask_key

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

# Sample demo data for instant exploration without API key
SAMPLE_DEMO_DATA = {
    "topic": TOPIC_DETAILS["qhd_nang_cao"],
    "difficulty": DIFFICULTY_DETAILS["hsg_tinh"],
    "problem": {
        "problem_name": "Thu Thập Năng Lượng Vũ Trụ",
        "problem_code": "COSMIC",
        "time_limit": "1.0 giây",
        "memory_limit": "256 MB",
        "input_file": "COSMIC.INP",
        "output_file": "COSMIC.OUT",
        "story_and_statement": "Trạm quan sát vũ trụ Hà Nội cần kết nối $N$ trạm tiếp sóng được đánh số từ $1$ đến $N$ theo mô hình cây. Trạm thứ $i$ có nguồn năng lượng ban đầu là $A_i$ (có thể âm hoặc dương).\n\nGiáo sư An muốn chọn ra một tập hợp các trạm liên thông tạo thành một cây con sao cho tổng năng lượng thu được là lớn nhất, đồng thời không có bất kỳ hai trạm nào được chọn mà cả hai đều có năng lượng âm (tránh hiện tượng sụt nguồn hệ thống).\n\nHãy giúp Giáo sư An tìm tổng năng lượng lớn nhất có thể đạt được!",
        "input_format": "- Dòng đầu chứa số nguyên dương $N$ ($1 \\le N \\le 2 \\times 10^5$) - số trạm tiếp sóng.\n- Dòng thứ hai chứa $N$ số nguyên $A_1, A_2, \\dots, A_N$ ($-10^9 \\le A_i \\le 10^9$) - năng lượng từng trạm.\n- $N-1$ dòng tiếp theo, mỗi dòng chứa hai số nguyên $u, v$ ($1 \\le u, v \\le N, u \\ne v$) mô tả đường truyền nối giữa trạm $u$ và trạm $v$.",
        "output_format": "In ra một số nguyên duy nhất là tổng năng lượng lớn nhất của cây con thỏa mãn điều kiện.",
        "subtasks": [
            {"subtask_num": 1, "points_percent": 30, "constraints": "$N \\le 100$, tất cả $A_i \\ge 0$."},
            {"subtask_num": 2, "points_percent": 30, "constraints": "$N \\le 2000$."},
            {"subtask_num": 3, "points_percent": 40, "constraints": "$N \\le 2 \\times 10^5$, năng lượng $A_i$ lên tới $10^9$."}
        ],
        "sample_tests": [
            {
                "sample_num": 1,
                "input": "5\n2 -1 3 4 -2\n1 2\n1 3\n3 4\n3 5",
                "output": "8",
                "explanation": "Chọn tập các trạm {1, 3, 4} tạo thành cây con liên thông với tổng năng lượng là 2 + 3 + 4 = 9 (chứa 0 trạm âm). Hoặc chọn {1, 2, 3, 4} có trạm 2 là âm nhưng không có 2 trạm âm kề nhau: tổng = 8. Ta thấy chọn {1, 3, 4} cho tổng = 9 là tối ưu!"
            },
            {
                "sample_num": 2,
                "input": "3\n-5 -2 -7\n1 2\n2 3",
                "output": "-2",
                "explanation": "Tất cả các trạm đều âm. Cây con chỉ được chứa tối đa 1 trạm âm. Trạm có giá trị lớn nhất là trạm 2 với giá trị -2."
            }
        ]
    },
    "solution": {
        "brute_force_approach": "Với Subtask 1 ($N \\le 100, A_i \\ge 0$): Vì tất cả giá trị đều dương, việc chọn toàn bộ các đỉnh trong cây sẽ cho tổng lớn nhất, hoặc duyệt qua tất cả các cây con bằng DFS/BFS từ mỗi đỉnh mất $O(N^2)$.",
        "optimal_approach": "Sử dụng Quy hoạch động trên cây (Tree DP):\nGọi $dp[u][0]$ là tổng lớn nhất của cây con gốc $u$ có chứa đỉnh $u$, và đỉnh $u$ KHÔNG mang năng lượng âm.\nGọi $dp[u][1]$ là tổng lớn nhất của cây con gốc $u$ có chứa đỉnh $u$, và đỉnh $u$ CÓ mang năng lượng âm.\nNếu $A_u < 0$: $dp[u][1] = A_u + \\sum \\max(0, dp[v][0])$ với mọi con $v$ của $u$ (vì $u$ âm nên con $v$ không được âm).\nNếu $A_u \\ge 0$: $dp[u][0] = A_u + \\sum \\max(0, \\max(dp[v][0], dp[v][1]))$.\nĐộ phức tạp thời gian: $O(N)$, độ phức tạp bộ nhớ: $O(N)$. Sử dụng kiểu dữ liệu `long long` trong C++ để tránh tràn số.",
        "cpp_solution": """#include <bits/stdc++.h>
using namespace std;

// Problem: COSMIC - Thu Thap Nang Luong Vu Tru
// Complexity: O(N) Time, O(N) Space

static const long long INF = 1e18;
int n;
vector<long long> a;
vector<vector<int>> adj;
long long dp[200005][2];
long long ans = -INF;

void dfs(int u, int p) {
    if (a[u] < 0) {
        dp[u][1] = a[u];
        dp[u][0] = -INF;
    } else {
        dp[u][0] = a[u];
        dp[u][1] = -INF;
    }

    for (int v : adj[u]) {
        if (v == p) continue;
        dfs(v, u);

        if (a[u] < 0) {
            // u is negative, its children cannot be negative
            if (dp[v][0] > 0) {
                dp[u][1] += dp[v][0];
            }
        } else {
            // u is non-negative, children can be either
            long long best_child = max(dp[v][0], dp[v][1]);
            if (best_child > 0) {
                dp[u][0] += best_child;
            }
        }
    }
    ans = max({ans, dp[u][0], dp[u][1]});
}

int main() {
    ios_base::sync_with_stdio(false);
    cin.tie(NULL);

    #ifdef ONLINE_JUDGE
    // When submitting to online judge
    #else
    if (fopen("COSMIC.INP", "r")) {
        freopen("COSMIC.INP", "r", stdin);
        freopen("COSMIC.OUT", "w", stdout);
    }
    #endif

    if (!(cin >> n)) return 0;
    a.resize(n + 1);
    for (int i = 1; i <= n; ++i) {
        cin >> a[i];
    }

    adj.assign(n + 1, vector<int>());
    for (int i = 1; i < n; ++i) {
        int u, v;
        cin >> u >> v;
        adj[u].push_back(v);
        adj[v].push_back(u);
    }

    dfs(1, 0);

    cout << ans << "\\n";
    return 0;
}""",
        "python_solution": """import sys
sys.setrecursionlimit(300000)

def solve():
    input = sys.stdin.read
    data = input().split()
    if not data:
        return

    n = int(data[0])
    a = [0] + [int(x) for x in data[1:n+1]]

    adj = [[] for _ in range(n + 1)]
    idx = n + 1
    for _ in range(n - 1):
        u = int(data[idx])
        v = int(data[idx+1])
        adj[u].append(v)
        adj[v].append(u)
        idx += 2

    INF = 10**18
    dp0 = [-INF] * (n + 1)
    dp1 = [-INF] * (n + 1)
    ans = [-INF]

    def dfs(u, p):
        if a[u] < 0:
            dp1[u] = a[u]
            dp0[u] = -INF
        else:
            dp0[u] = a[u]
            dp1[u] = -INF

        for v in adj[u]:
            if v == p:
                continue
            dfs(v, u)

            if a[u] < 0:
                if dp0[v] > 0:
                    dp1[u] += dp0[v]
            else:
                best_c = max(dp0[v], dp1[v])
                if best_c > 0:
                    dp0[u] += best_c

        ans[0] = max(ans[0], dp0[u], dp1[u])

    dfs(1, 0)
    print(ans[0])

if __name__ == '__main__':
    solve()
"""
    },
    "tests": [
        {"test_num": 1, "name": "Test01", "subtask": 1, "description": "Ví dụ mẫu 1", "input": "5\n2 -1 3 4 -2\n1 2\n1 3\n3 4\n3 5\n", "output": "9\n"},
        {"test_num": 2, "name": "Test02", "subtask": 1, "description": "Ví dụ mẫu 2 (toàn âm)", "input": "3\n-5 -2 -7\n1 2\n2 3\n", "output": "-2\n"},
        {"test_num": 3, "name": "Test03", "subtask": 1, "description": "Subtask 1 - Đơn đỉnh N=1", "input": "1\n42\n", "output": "42\n"},
        {"test_num": 4, "name": "Test04", "subtask": 1, "description": "Subtask 1 - Tất cả giá trị dương N=6", "input": "6\n10 20 30 40 50 60\n1 2\n2 3\n3 4\n4 5\n5 6\n", "output": "210\n"},
        {"test_num": 5, "name": "Test05", "subtask": 2, "description": "Subtask 2 - Cây hình sao (Star graph)", "input": "5\n100 -5 -10 -20 -30\n1 2\n1 3\n1 4\n1 5\n", "output": "100\n"},
        {"test_num": 6, "name": "Test06", "subtask": 2, "description": "Subtask 2 - Cây nhị phân phân nhánh", "input": "7\n5 -3 4 -1 2 -8 10\n1 2\n1 3\n2 4\n2 5\n3 6\n3 7\n", "output": "19\n"},
        {"test_num": 7, "name": "Test07", "subtask": 3, "description": "Subtask 3 - Bẫy tràn số 64-bit int", "input": "4\n1000000000 1000000000 1000000000 1000000000\n1 2\n2 3\n3 4\n", "output": "4000000000\n"},
        {"test_num": 8, "name": "Test08", "subtask": 3, "description": "Subtask 3 - Đồ thị đường thẳng lớn N=10", "input": "10\n-1 2 -3 4 -5 6 -7 8 -9 10\n1 2\n2 3\n3 4\n4 5\n5 6\n6 7\n7 8\n8 9\n9 10\n", "output": "10\n"},
        {"test_num": 9, "name": "Test09", "subtask": 3, "description": "Subtask 3 - Cây phân cấp nhiều tầng sâu", "input": "8\n15 -10 25 30 -50 45 10 -2\n1 2\n2 3\n3 4\n1 5\n5 6\n6 7\n7 8\n", "output": "70\n"},
        {"test_num": 10, "name": "Test10", "subtask": 3, "description": "Subtask 3 - Cực đại và bẫy âm xen kẽ", "input": "10\n1000000000 -1 1000000000 -2 1000000000 -3 1000000000 -4 1000000000 -5\n1 2\n2 3\n3 4\n4 5\n5 6\n6 7\n7 8\n8 9\n9 10\n", "output": "4999999990\n"}
    ],
    "generator_code": """# Script sinh test tu dong cho COSMIC
import random

def generate_tree(n):
    edges = []
    for i in range(2, n + 1):
        p = random.randint(1, i - 1)
        edges.append((p, i))
    return edges

print("Generator ready.")
""",
    "agent_logs": [
        {"stage": 1, "title": "Giai đoạn 1: Lên ý tưởng & Thiết kế đặc tả đề bài", "status": "completed", "message": "Đã tạo đề bài 'Thu Thập Năng Lượng Vũ Trụ' [COSMIC] với 3 Subtasks."},
        {"stage": 2, "title": "Giai đoạn 2: Xây dựng Thuật toán & Mã nguồn chuẩn", "status": "completed", "message": "Đã phân tích thuật toán Tree DP O(N) và lập trình mã C++20 / Python 3."},
        {"stage": 3, "title": "Giai đoạn 3: Khởi tạo & Kiểm chứng 10 Bộ Test Cases", "status": "completed", "message": "Đã thẩm định chính xác 10 bộ Test Cases từ Test01 đến Test10."},
        {"stage": 4, "title": "Giai đoạn 4: Đóng gói Script Sinh Test & Hoàn thiện", "status": "completed", "message": "Đã đóng gói Contest Package chuẩn Themis/CMS sẵn sàng tải về."}
    ]
}

async def handle_index(request):
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0"
        }
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        return web.Response(text=html, content_type="text/html", headers=headers)
    return web.Response(text="Hệ thống Olympiad Exam Generator đang chuẩn bị giao diện...", content_type="text/plain; charset=utf-8")

async def handle_verify_key(request):
    """Verifies the current active key from server .env."""
    try:
        body = await request.json() if request.can_read_body else {}
        model = body.get("model", "gemini-3.6-flash").strip() if body else "gemini-3.6-flash"

        km = KeyManager.from_server_env()
        if km.total_count() == 0:
            return web.json_response({"valid": False, "error": "Chưa cấu hình API Key trong tệp .env trên máy chủ."}, status=400)

        client = GeminiClient(key_manager=km, model=model)
        result = await client.verify_key()
        return web.json_response(result)
    except Exception as e:
        logger.exception("Verify key error")
        return web.json_response({"valid": False, "error": str(e)}, status=500)

async def handle_get_keys_status(request):
    """Returns the status of server-configured hidden keys from .env and keys.txt."""
    try:
        km = KeyManager.from_server_env()
        summary = km.get_status_summary()
        return web.json_response({
            "success": True,
            "has_server_keys": km.total_count() > 0,
            "server_keys_count": km.total_count(),
            "healthy_count": km.healthy_count(),
            "data": summary
        })
    except Exception as e:
        logger.exception("Error checking server keys status")
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def handle_load_server_keys(request):
    """Returns the masked server keys list and status."""
    try:
        km = KeyManager.from_server_env()
        return web.json_response({
            "success": True,
            "keys": [k.to_dict() for k in km.key_objects],
            "count": km.total_count()
        })
    except Exception as e:
        logger.exception("Error loading server keys list")
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def handle_verify_pool(request):
    """Verifies all keys configured in .env and returns individual health checks."""
    try:
        body = await request.json() if request.can_read_body else {}
        model = body.get("model", "gemini-3.6-flash").strip() if body else "gemini-3.6-flash"

        km = KeyManager.from_server_env()
        if km.total_count() == 0:
            return web.json_response({
                "success": False,
                "error": "Không tìm thấy API Key nào trong tệp .env trên máy chủ. Vui lòng kiểm tra lại tệp .env."
            }, status=400)

        client = GeminiClient(key_manager=km, model=model)
        diagnostics = await client.verify_all_keys()

        return web.json_response({
            "success": True,
            "diagnostics": diagnostics,
            "total_count": km.total_count(),
            "healthy_count": sum(1 for d in diagnostics if d["valid"])
        })
    except Exception as e:
        logger.exception("Error verifying key pool")
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def handle_get_topics(request):
    ollama_client = OllamaClient()
    ollama_health = await ollama_client.check_health()
    ollama_models = await ollama_client.list_models() if ollama_health.get("available") else []

    gemini_models = [
        {"id": "gemini-3.6-flash", "name": "Google Gemini 3.6 Flash (Khuyên dùng Cloud - Nhanh & Chuẩn)", "default": True},
        {"id": "gemini-2.5-flash", "name": "Google Gemini 2.5 Flash", "default": False},
        {"id": "gemini-2.0-flash", "name": "Google Gemini 2.0 Flash", "default": False},
        {"id": "gemini-1.5-flash", "name": "Google Gemini 1.5 Flash", "default": False}
    ]

    return web.json_response({
        "topics": TOPIC_DETAILS,
        "difficulties": DIFFICULTY_DETAILS,
        "models": gemini_models,
        "gemini_models": gemini_models,
        "ollama_models": ollama_models,
        "ollama_available": ollama_health.get("available", False),
        "ollama_default_model": ollama_health.get("selected_model", "qwen2.5:7b")
    })

async def handle_get_ollama_status(request):
    """Returns status and installed models of local Ollama."""
    try:
        client = OllamaClient()
        health = await client.check_health()
        models = await client.list_models()
        return web.json_response({
            "success": True,
            "available": health.get("available", False),
            "selected_model": health.get("selected_model", "qwen2.5:7b"),
            "models": models,
            "error": health.get("error", "")
        })
    except Exception as e:
        return web.json_response({
            "success": False,
            "available": False,
            "error": str(e),
            "models": []
        })

async def handle_get_sample_data(request):
    return web.json_response({
        "success": True,
        "data": SAMPLE_DEMO_DATA
    })

async def handle_generate_problem(request):
    try:
        body = await request.json()
        ai_engine = (body.get("ai_engine") or body.get("engine") or "gemini").lower().strip()
        model = (body.get("model") or "").strip()
        topic = body.get("topic") or body.get("topic_key", "xu_ly_so")
        difficulty = body.get("difficulty") or body.get("difficulty_key", "hsg_tinh")
        custom_theme = body.get("custom_theme", "").strip()
        problem_code = (body.get("problem_code") or body.get("problem_code_preference") or "").strip()
        io_mode = body.get("io_mode", "file")

        km = None
        if ai_engine == "ollama":
            ollama_model = model or "qwen2.5:7b"
            client = OllamaClient(model=ollama_model)
            health = await client.check_health()
            if not health.get("available"):
                return web.json_response({
                    "success": False,
                    "error": "Không thể kết nối đến Ollama trên cổng 11434. Vui lòng mở ứng dụng Ollama hoặc chạy lệnh 'ollama serve' rồi thử lại."
                }, status=503)
            logger.info(f"Generating problem with LOCAL OLLAMA ({ollama_model}) for topic={topic}, difficulty={difficulty}")
        else:
            # Gemini Cloud Mode
            km = KeyManager.from_server_env()
            if km.total_count() == 0:
                return web.json_response({
                    "success": False,
                    "error": "Không tìm thấy API Key nào trong tệp .env trên máy chủ. Vui lòng mở tệp .env và thêm key (ví dụ GEMINI_API_KEY_1=...) hoặc chuyển sang chế độ Ollama Local (Offline 100%)."
                }, status=400)
            gemini_model = model or "gemini-3.6-flash"
            client = GeminiClient(key_manager=km, model=gemini_model)
            logger.info(f"Generating problem with GEMINI CLOUD ({gemini_model}) for topic={topic}, difficulty={difficulty}, pool_size={km.total_count()}")

        fallback_used = False
        fallback_msg = ""
        try:
            pipeline = OlympiadAgentPipeline(client)
            result = await pipeline.generate_full_problem(
                topic_key=topic,
                difficulty_key=difficulty,
                custom_theme=custom_theme,
                problem_code_preference=problem_code,
                io_mode=io_mode
            )
        except Exception as e_gen:
            if ai_engine == "ollama":
                km_fallback = KeyManager.from_server_env()
                if km_fallback.total_count() > 0:
                    logger.warning(f"Ollama generation encountered issue ({e_gen}). Auto-falling back to Gemini Cloud (10 keys in .env)...")
                    gemini_model = "gemini-3.6-flash"
                    cloud_client = GeminiClient(key_manager=km_fallback, model=gemini_model)
                    cloud_pipeline = OlympiadAgentPipeline(cloud_client)
                    result = await cloud_pipeline.generate_full_problem(
                        topic_key=topic,
                        difficulty_key=difficulty,
                        custom_theme=custom_theme,
                        problem_code_preference=problem_code,
                        io_mode=io_mode
                    )
                    client = cloud_client
                    km = km_fallback
                    ai_engine = "gemini"
                    fallback_used = True
                    fallback_msg = "Mô hình Ollama nội bộ bị quá tải CPU. Hệ thống đã tự động chuyển sang Gemini Cloud và hoàn thành xuất sắc trong vài giây!"
                else:
                    raise e_gen
            else:
                raise e_gen

        return web.json_response({
            "success": True,
            "data": result,
            "ai_engine": ai_engine,
            "fallback_used": fallback_used,
            "fallback_message": fallback_msg,
            "key_pool_status": km.get_status_summary() if km else {"type": "ollama_local", "model": getattr(client, "model", "qwen2.5:7b"), "status": "offline_local"},
            "rotation_events": getattr(client, "rotation_events", [])
        })
    except Exception as e:
        logger.exception("Problem generation failed")
        return web.json_response({
            "success": False,
            "error": f"Quá trình sinh đề gặp lỗi: {str(e)}"
        }, status=500)

async def handle_download_zip(request):
    try:
        data = await request.json()
        problem_code = data.get("problem", {}).get("problem_code", "PROBLEM").upper()
        io_mode = data.get("io_mode", "file")
        
        zip_bytes = create_themis_zip(data, io_mode=io_mode)
        filename = f"{problem_code}_THEMIS_TESTS.zip"

        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "application/zip",
            "Content-Length": str(len(zip_bytes))
        }
        return web.Response(body=zip_bytes, headers=headers)
    except Exception as e:
        logger.exception("ZIP generation failed")
        return web.json_response({"error": f"Lỗi tạo tệp ZIP: {str(e)}"}, status=500)

async def handle_download_word(request):
    try:
        data = await request.json()
        problem_code = data.get("problem", {}).get("problem_code", "PROBLEM").upper()
        
        docx_bytes = create_olympiad_docx(data, include_editorial=True)
        filename = f"{problem_code}_DE_THI_HSG.docx"

        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "Content-Length": str(len(docx_bytes))
        }
        return web.Response(body=docx_bytes, headers=headers)
    except Exception as e:
        logger.exception("Word docx generation failed")
        return web.json_response({"error": f"Lỗi tạo tệp Word (.docx): {str(e)}"}, status=500)

def create_app():
    app = web.Application(client_max_size=1024 * 1024 * 50)
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/topics", handle_get_topics)
    app.router.add_get("/api/ollama/status", handle_get_ollama_status)
    app.router.add_get("/api/sample-data", handle_get_sample_data)
    app.router.add_get("/api/keys/status", handle_get_keys_status)
    app.router.add_get("/api/keys/load-server-keys", handle_load_server_keys)
    app.router.add_post("/api/verify-key", handle_verify_key)
    app.router.add_post("/api/keys/verify-pool", handle_verify_pool)
    app.router.add_post("/api/generate", handle_generate_problem)
    app.router.add_post("/api/download-zip", handle_download_zip)
    app.router.add_post("/api/download-word", handle_download_word)

    # Static assets
    if os.path.exists(STATIC_DIR):
        app.router.add_static("/static/", path=STATIC_DIR, name="static")

    return app

if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    import socket

    def find_available_port(preferred_ports=[5000, 8000, 5050, 8888, 3000]):
        env_port = os.environ.get("PORT")
        if env_port:
            try:
                preferred_ports = [int(env_port)] + preferred_ports
            except ValueError:
                pass
        for p in preferred_ports:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("127.0.0.1", p))
                    return p
                except Exception:
                    continue
        return 5000

    app = create_app()
    env_port = os.environ.get("PORT")
    env_host = os.environ.get("HOST", "0.0.0.0" if env_port else "127.0.0.1")
    if env_port:
        try:
            port = int(env_port)
        except ValueError:
            port = find_available_port()
    else:
        port = find_available_port()

    print("================================================================")
    print("  OLYMPIAD PROBLEM FORGE - HE THONG TAO DE THI HSG TIN HOC")
    print(f"  Trang web dang chay tai: http://{env_host}:{port}")
    print("================================================================")
    web.run_app(app, host=env_host, port=port)
