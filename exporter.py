import io
import os
import zipfile
from typing import Dict, Any

def clean_markdown_text(text: str) -> str:
    if not text:
        return ""
    return str(text).replace(r"\'", "'").replace(r'\"', '"')

def create_themis_zip(data: Dict[str, Any], io_mode: str = "file") -> bytes:
    """
    Pack the generated competitive programming problem into a standard Themis/CMS ZIP archive.
    """
    problem = data.get("problem", {})
    solution = data.get("solution", {})
    tests = data.get("tests", [])
    generator_code = data.get("generator_code", "")

    code = str(problem.get("problem_code", "PROBLEM")).upper()
    inp_name = f"{code}.INP" if io_mode == "file" else "input.txt"
    out_name = f"{code}.OUT" if io_mode == "file" else "output.txt"

    # Build Problem Statement Markdown
    subtasks_md = ""
    for st in problem.get("subtasks", []):
        subtasks_md += f"- **Subtask {st.get('subtask_num')}** ({st.get('points_percent')}% số điểm): {clean_markdown_text(st.get('constraints'))}\n"

    samples_md = ""
    for s in problem.get("sample_tests", []):
        exp_clean = clean_markdown_text(s.get('explanation', '').strip())
        samples_md += f"""### Ví dụ {s.get('sample_num')}:
**Dữ liệu vào ({inp_name}):**
```
{str(s.get('input', '')).strip()}
```

**Kết quả ({out_name}):**
```
{str(s.get('output', '')).strip()}
```

**Giải thích:**
{exp_clean}

---
"""

    de_bai_content = f"""# {clean_markdown_text(problem.get('problem_name', 'Bài toán'))} (Mã bài: {code})

- **Thời gian chạy giới hạn:** {problem.get('time_limit', '1.0 giây')}
- **Bộ nhớ giới hạn:** {problem.get('memory_limit', '256 MB')}
- **Tên tệp vào:** `{inp_name}`
- **Tên tệp ra:** `{out_name}`

## Đề bài
{clean_markdown_text(problem.get('story_and_statement', ''))}

## Dữ liệu vào
{clean_markdown_text(problem.get('input_format', ''))}

## Dữ liệu ra
{clean_markdown_text(problem.get('output_format', ''))}

## Giới hạn & Subtasks
{subtasks_md}

## Ví dụ minh họa
{samples_md}
"""

    # Build Tutorial Markdown
    huong_dan_content = f"""# HƯỚNG DẪN GIẢI & PHÂN TÍCH THUẬT TOÁN: {clean_markdown_text(problem.get('problem_name'))} [{code}]

## 1. Phân tích Subtask nhỏ (Phương pháp trâu / Vét cạn)
{clean_markdown_text(solution.get('brute_force_approach', 'Đang cập nhật...'))}

## 2. Giải thuật tối ưu (Full AC)
{clean_markdown_text(solution.get('optimal_approach', 'Đang cập nhật...'))}

## 3. Mã nguồn mẫu C++20
```cpp
{solution.get('cpp_solution', '')}
```

## 4. Mã nguồn mẫu Python 3
```python
{solution.get('python_solution', '')}
```
"""

    # Create in-memory zip
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Root contest docs
        base_dir = code
        zf.writestr(f"{base_dir}/de_bai.md", de_bai_content.encode("utf-8"))
        zf.writestr(f"{base_dir}/huong_dan_giai.md", huong_dan_content.encode("utf-8"))
        
        # Source codes
        if solution.get("cpp_solution"):
            zf.writestr(f"{base_dir}/solution.cpp", solution["cpp_solution"].encode("utf-8"))
        if solution.get("python_solution"):
            zf.writestr(f"{base_dir}/solution.py", solution["python_solution"].encode("utf-8"))
        if generator_code:
            zf.writestr(f"{base_dir}/generator.py", generator_code.encode("utf-8"))

        # Tests in Themis format (Folder Test01 ... Test10)
        for t in tests:
            test_num = t.get("test_num", 1)
            folder_name = f"Test{test_num:02d}"
            inp_data = t.get("input", "")
            out_data = t.get("output", "")

            # Themis folder style
            zf.writestr(f"{base_dir}/tests/{folder_name}/{inp_name}", inp_data.encode("utf-8"))
            zf.writestr(f"{base_dir}/tests/{folder_name}/{out_name}", out_data.encode("utf-8"))

            # Flat style (for CMS / Codeforces / Polygon)
            flat_in = f"{test_num:02d}.in"
            flat_out = f"{test_num:02d}.out"
            zf.writestr(f"{base_dir}/flat_tests/{flat_in}", inp_data.encode("utf-8"))
            zf.writestr(f"{base_dir}/flat_tests/{flat_out}", out_data.encode("utf-8"))

    zip_buffer.seek(0)
    return zip_buffer.getvalue()
