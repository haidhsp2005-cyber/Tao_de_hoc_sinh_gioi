# Shared mock/sample data for instant exploration without API key

SAMPLE_DEMO_DATA = {
    "topic": {
        "key": "qhd_nang_cao",
        "name": "Quy hoạch động nâng cao",
        "description": "Tree DP, Digit DP, Bitmask DP, Convex Hull Trick, D&C Optimization, Matrix Exponentiation."
    },
    "difficulty": {
        "key": "hsg_tinh",
        "name": "HSG Tỉnh / Thành phố",
        "audience": "Học sinh giỏi cấp Tỉnh/Thành phố chọn lọc",
        "target_level": "Vận dụng & Vận dụng cao, phân hóa 3 subtask rõ ràng",
        "constraints_scale": "Subtask 1: N <= 100 (trâu), Subtask 2: N <= 2000 (O(N^2)), Subtask 3: N <= 2*10^5 (O(N log N) hoặc O(N))"
    },
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
