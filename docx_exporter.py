import io
import re
import zipfile
from typing import Dict, Any, List
from agent_pipeline import force_to_str, clean_explanation_text

# Comprehensive LaTeX to Unicode symbol map
MATH_SYMBOLS = {
    r'\le': '≤', r'\leq': '≤',
    r'\ge': '≥', r'\geq': '≥',
    r'\ne': '≠', r'\neq': '≠',
    r'\approx': '≈',
    r'\equiv': '≡',
    r'\sim': '∼',
    r'\cong': '≅',
    r'\times': '×',
    r'\cdot': '·',
    r'\pm': '±',
    r'\mp': '∓',
    r'\div': '÷',
    r'\dots': '…', r'\ldots': '…', r'\cdots': '…', r'\vdots': '⋮', r'\ddots': '⋱',
    r'\in': '∈', r'\notin': '∉',
    r'\subset': '⊂', r'\subseteq': '⊆',
    r'\supset': '⊃', r'\supseteq': '⊇',
    r'\cap': '∩', r'\cup': '∪',
    r'\setminus': '∖',
    r'\emptyset': '∅', r'\varnothing': '∅',
    r'\to': '→', r'\rightarrow': '→', r'\leftarrow': '←', r'\gets': '←',
    r'\leftrightarrow': '↔',
    r'\Rightarrow': '⇒', r'\implies': '⇒',
    r'\Leftarrow': '⇐',
    r'\Leftrightarrow': '⇔', r'\iff': '⇔',
    r'\forall': '∀', r'\exists': '∃',
    r'\neg': '¬', r'\lor': '∨', r'\land': '∧', r'\oplus': '⊕',
    r'\infty': '∞', r'\partial': '∂',
    r'\circ': '°', r'\degree': '°',
    r'\perp': '⊥', r'\parallel': '∥',
    r'\angle': '∠', r'\triangle': '△',
    r'\mid': '|', r'\nmid': '∤',
    # Greek letters (lowercase)
    r'\alpha': 'α', r'\beta': 'β', r'\gamma': 'γ', r'\delta': 'δ',
    r'\epsilon': 'ϵ', r'\varepsilon': 'ε', r'\zeta': 'ζ', r'\eta': 'η',
    r'\theta': 'θ', r'\vartheta': 'ϑ', r'\iota': 'ι', r'\kappa': 'κ',
    r'\lambda': 'λ', r'\mu': 'μ', r'\nu': 'ν', r'\xi': 'ξ',
    r'\pi': 'π', r'\varpi': 'ϖ', r'\rho': 'ρ', r'\varrho': 'ϱ',
    r'\sigma': 'σ', r'\varsigma': 'ς', r'\tau': 'τ', r'\upsilon': 'υ',
    r'\phi': 'ϕ', r'\varphi': 'φ', r'\chi': 'χ', r'\psi': 'ψ', r'\omega': 'ω',
    # Greek letters (uppercase)
    r'\Gamma': 'Γ', r'\Delta': 'Δ', r'\Theta': 'Θ', r'\Lambda': 'Λ',
    r'\Xi': 'Ξ', r'\Pi': 'Π', r'\Sigma': 'Σ', r'\Upsilon': 'Υ',
    r'\Phi': 'Φ', r'\Psi': 'Ψ', r'\Omega': 'Ω',
}

def xml_escape(text: str) -> str:
    """Escape XML special characters and sanitize XML 1.0 illegal control characters."""
    if not text:
        return ""
    s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f\ufffe\uffff]', '', str(text))
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;"))

def clean_exam_text(text: str) -> str:
    """
    Clean artifacts, escape sequences, straight quotes, markdown ticks,
    and XML-illegal control characters from LLM generated problem texts.
    Protects math formulas ($...$ and $$...$$) from quotation replacements.
    """
    if not text:
        return ""
    
    # Protect math formulas ($...$ and $$...$$)
    math_tokens = []
    def save_math(m):
        idx = len(math_tokens)
        math_tokens.append(m.group(0))
        return f"__MATH_EXPR_TOKEN_{idx}__"

    protected = re.sub(r'\$\$[^\$]+\$\$', save_math, str(text))
    protected = re.sub(r'\$[^\$]+\$', save_math, protected)

    res = protected
    # 1. Unescape JSON escaped quotes and newlines
    res = res.replace(r"\'", "'").replace(r'\"', '"')
    res = res.replace(r'\r\n', '\n').replace(r'\r', '\n').replace(r'\n', '\n')
    
    # 2. Restore LaTeX commands mangled by JSON escape sequences (\f -> \x0c, \b -> \x08)
    res = res.replace('\x0corall', r'\forall')
    res = res.replace('\x0crac', r'\frac')
    res = res.replace('\x0c', ' ')
    res = res.replace('\x08eta', r'\beta')
    res = res.replace('\x08', '')
    res = res.replace('\x0b', '')
    
    # 3. Convert straight single-quoted values like 'YES', 'NO', '1', '-1', 'A' to Vietnamese typographic double quotes “YES”
    res = re.sub(r"(^|[\s(\[])'([a-zA-Z0-9_+\-*/]+)'(?=[\s)\].,:;!?]|$)", r'\1“\2”', res)
    
    # 4. Strip markdown backticks around inline variables/code (e.g. `N`, `A[i]`, `10^5`, `SUMK.INP`)
    res = re.sub(r'`([^`\n]+)`', r'\1', res)
    res = res.replace('`', '')

    # 5. Strip all XML 1.0 illegal control characters
    res = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f\ufffe\uffff]', '', res)

    # Restore protected math tokens
    for idx, token_val in enumerate(math_tokens):
        res = res.replace(f"__MATH_EXPR_TOKEN_{idx}__", token_val)

    return res

def extract_braced(s: str, pos: int):
    """Extract content inside balanced curly braces {...} starting at pos (where s[pos] == '{')."""
    if pos >= len(s) or s[pos] != '{':
        return "", pos
    depth = 1
    i = pos + 1
    while i < len(s) and depth > 0:
        if s[i] == '{':
            depth += 1
        elif s[i] == '}':
            depth -= 1
        i += 1
    return s[pos+1 : i-1], i

def latex_to_omml(latex: str) -> str:
    """
    Convert a LaTeX math expression into Word OMML (<m:oMath>...</m:oMath>).
    Handles fractions, square roots, superscripts, subscripts, sub-superscripts,
    binomial coefficients, summations, products, vectors, delimiters,
    Greek letters, and standard math symbols.
    """
    s = latex.strip()
    while s.startswith("$") and s.endswith("$") and len(s) >= 2:
        s = s[1:-1].strip()

    # Normalize double backslashes
    s = re.sub(r'\\\\([a-zA-Z]+)', r'\\\1', s)
    s = re.sub(r'\\le\b', r'\\leq', s)
    s = re.sub(r'\\ge\b', r'\\geq', s)
    s = re.sub(r'\\ne\b', r'\\neq', s)
    s = re.sub(r'\\to\b', r'\\rightarrow', s)
    s = re.sub(r'\\gets\b', r'\\leftarrow', s)
    s = re.sub(r'\\overrightarrow\b', r'\\vec', s)
    s = re.sub(r'\\overleftarrow\b', r'\\vec', s)
    s = re.sub(r'\\prime\b', "'", s)

    # Normalize functions inside math
    s = re.sub(r'\\max\b', 'max', s)
    s = re.sub(r'\\min\b', 'min', s)
    s = re.sub(r'\\gcd\b', 'gcd', s)
    s = re.sub(r'\\lcm\b', 'lcm', s)
    s = re.sub(r'\\log\b', 'log', s)
    s = re.sub(r'\\ln\b', 'ln', s)
    s = re.sub(r'\\exp\b', 'exp', s)
    s = re.sub(r'\\sin\b', 'sin', s)
    s = re.sub(r'\\cos\b', 'cos', s)
    s = re.sub(r'\\tan\b', 'tan', s)
    s = re.sub(r'\\cot\b', 'cot', s)

    # Normalize \pmod{m} -> (mod m), \bmod -> mod
    s = re.sub(r'\\pmod\s*\{([^}]+)\}', r' (mod \1)', s)
    s = re.sub(r'\\bmod\b', r' mod ', s)
    s = re.sub(r'\\mod\b', r' mod ', s)

    # Remove \left and \right prefixes
    s = re.sub(r'\\left\s*([(\[{|])', r'\1', s)
    s = re.sub(r'\\right\s*([)\]}|])', r'\1', s)
    s = re.sub(r'\\left\\\{', '{', s)
    s = re.sub(r'\\right\\\}', '}', s)
    s = re.sub(r'\\\{', '{', s)
    s = re.sub(r'\\\}', '}', s)

    # Spacing commands
    s = re.sub(r'\\[,;:! ]', ' ', s)
    s = re.sub(r'\\quad\b', '   ', s)
    s = re.sub(r'\\qquad\b', '      ', s)

    # Replace symbols
    for cmd, sym in MATH_SYMBOLS.items():
        s = re.sub(re.escape(cmd) + r'\b', lambda m, sym=sym: sym, s)

    # Text / Mathbb / Mathcal replacements
    s = re.sub(r'\\mathcal\{O\}', 'O', s)
    s = re.sub(r'\\mathcal\{([^}]+)\}', r'\1', s)
    s = re.sub(r'\\mathbb\{R\}', 'ℝ', s)
    s = re.sub(r'\\mathbb\{Z\}', 'ℤ', s)
    s = re.sub(r'\\mathbb\{N\}', 'ℕ', s)
    s = re.sub(r'\\mathbf\{([^}]+)\}', r'\1', s)
    s = re.sub(r'\\mathit\{([^}]+)\}', r'\1', s)
    s = re.sub(r'\\mathrm\{([^}]+)\}', r'\1', s)

    def parse_expr(expr_str: str) -> str:
        parts = []
        i = 0
        n = len(expr_str)
        text_buffer = []

        def flush_text():
            if text_buffer:
                t = "".join(text_buffer)
                parts.append(f'<m:r><m:t xml:space="preserve">{xml_escape(t)}</m:t></m:r>')
                text_buffer.clear()

        while i < n:
            # 1. \frac{num}{den}, \dfrac, \tfrac
            m_frac = re.match(r'\\(d|t)?frac\s*\{', expr_str[i:])
            if m_frac:
                flush_text()
                open_pos = i + m_frac.end() - 1
                num, next_pos = extract_braced(expr_str, open_pos)
                while next_pos < n and expr_str[next_pos].isspace():
                    next_pos += 1
                if next_pos < n and expr_str[next_pos] == '{':
                    den, end_pos = extract_braced(expr_str, next_pos)
                    i = end_pos
                else:
                    den = ""
                    i = next_pos
                num_xml = parse_expr(num)
                den_xml = parse_expr(den)
                parts.append(f'<m:f><m:num>{num_xml}</m:num><m:den>{den_xml}</m:den></m:f>')
                continue

            # 2. \binom{n}{k}
            m_binom = re.match(r'\\binom\s*\{', expr_str[i:])
            if m_binom:
                flush_text()
                open_pos = i + m_binom.end() - 1
                n_val, next_pos = extract_braced(expr_str, open_pos)
                while next_pos < n and expr_str[next_pos].isspace():
                    next_pos += 1
                if next_pos < n and expr_str[next_pos] == '{':
                    k_val, end_pos = extract_braced(expr_str, next_pos)
                    i = end_pos
                else:
                    k_val = ""
                    i = next_pos
                n_xml = parse_expr(n_val)
                k_xml = parse_expr(k_val)
                parts.append(f'<m:d><m:dPr><m:begChr m:val="("/><m:endChr m:val=")"/></m:dPr><m:e><m:f><m:fPr><m:type m:val="noBar"/></m:fPr><m:num>{n_xml}</m:num><m:den>{k_xml}</m:den></m:f></m:e></m:d>')
                continue

            # 3. \sqrt[n]{expr} or \sqrt{expr}
            m_sqrt = re.match(r'\\sqrt(\[[^\]]+\])?\s*\{', expr_str[i:])
            if m_sqrt:
                flush_text()
                deg_part = m_sqrt.group(1)
                open_pos = i + m_sqrt.end() - 1
                radicand, end_pos = extract_braced(expr_str, open_pos)
                i = end_pos
                rad_xml = parse_expr(radicand)
                if deg_part:
                    deg_val = deg_part[1:-1]
                    deg_xml = parse_expr(deg_val)
                    parts.append(f'<m:rad><m:radPr><m:degHide m:val="0"/></m:radPr><m:deg>{deg_xml}</m:deg><m:e>{rad_xml}</m:e></m:rad>')
                else:
                    parts.append(f'<m:rad><m:radPr><m:degHide m:val="1"/></m:radPr><m:deg/><m:e>{rad_xml}</m:e></m:rad>')
                continue

            # 4. \sum, \prod, \coprod, \bigcap, \bigcup, \int, etc. (n-ary operators)
            m_nary = re.match(r'\\(sum|prod|coprod|bigcap|bigcup|int|iint|iiint|oint)(?![a-zA-Z])', expr_str[i:])
            if m_nary:
                flush_text()
                op = m_nary.group(1)
                sym_map = {
                    "sum": "∑", "prod": "∏", "coprod": "∐",
                    "bigcap": "⋂", "bigcup": "⋃",
                    "int": "∫", "iint": "∬", "iiint": "∭", "oint": "∮"
                }
                sym = sym_map.get(op, "∑")
                lim_loc = "subSup" if "int" in op else "undOvr"
                
                cur = i + m_nary.end()
                sub_val = None
                sup_val = None
                
                # Match subscript and superscript in any order with full balanced brace extraction
                for _ in range(2):
                    while cur < n and expr_str[cur].isspace():
                        cur += 1
                    if cur < n and expr_str[cur] == '_' and sub_val is None:
                        cur += 1
                        while cur < n and expr_str[cur].isspace():
                            cur += 1
                        if cur < n and expr_str[cur] == '{':
                            sub_val, cur = extract_braced(expr_str, cur)
                        else:
                            m_tok = re.match(r'(\\[a-zA-Z]+|[a-zA-Z0-9])', expr_str[cur:])
                            if m_tok:
                                sub_val = m_tok.group(1)
                                cur += m_tok.end()
                    elif cur < n and expr_str[cur] == '^' and sup_val is None:
                        cur += 1
                        while cur < n and expr_str[cur].isspace():
                            cur += 1
                        if cur < n and expr_str[cur] == '{':
                            sup_val, cur = extract_braced(expr_str, cur)
                        else:
                            m_tok = re.match(r'(\\[a-zA-Z]+|[a-zA-Z0-9])', expr_str[cur:])
                            if m_tok:
                                sup_val = m_tok.group(1)
                                cur += m_tok.end()

                sub_hide = "0" if sub_val else "1"
                sup_hide = "0" if sup_val else "1"
                sub_xml = f'<m:sub>{parse_expr(sub_val)}</m:sub>' if sub_val else '<m:sub/>'
                sup_xml = f'<m:sup>{parse_expr(sup_val)}</m:sup>' if sup_val else '<m:sup/>'

                # Use zero-width space &#x200B; in <m:e> so Word doesn't show an empty operand placeholder box □
                parts.append(
                    f'<m:nary>'
                    f'<m:naryPr>'
                    f'<m:chr m:val="{sym}"/>'
                    f'<m:limLoc m:val="{lim_loc}"/>'
                    f'<m:grow m:val="0"/>'
                    f'<m:subHide m:val="{sub_hide}"/>'
                    f'<m:supHide m:val="{sup_hide}"/>'
                    f'</m:naryPr>'
                    f'{sub_xml}'
                    f'{sup_xml}'
                    f'<m:e><m:r><m:t>&#x200B;</m:t></m:r></m:e>'
                    f'</m:nary>'
                )
                i = cur
                continue

            # 5. \text{...}
            m_text = re.match(r'\\text\s*\{', expr_str[i:])
            if m_text:
                flush_text()
                open_pos = i + m_text.end() - 1
                inner, end_pos = extract_braced(expr_str, open_pos)
                i = end_pos
                parts.append(f'<m:r><m:rPr><m:nor/></m:rPr><m:t xml:space="preserve">{xml_escape(inner)}</m:t></m:r>')
                continue

            # 6. Floor / Ceil delimiters
            m_floor = re.match(r'\\lfloor\s*(.*?)\\rfloor', expr_str[i:])
            if m_floor:
                flush_text()
                inner_xml = parse_expr(m_floor.group(1))
                parts.append(f'<m:d><m:dPr><m:begChr m:val="⌊"/><m:endChr m:val="⌋"/></m:dPr><m:e>{inner_xml}</m:e></m:d>')
                i += m_floor.end()
                continue

            m_ceil = re.match(r'\\lceil\s*(.*?)\\rceil', expr_str[i:])
            if m_ceil:
                flush_text()
                inner_xml = parse_expr(m_ceil.group(1))
                parts.append(f'<m:d><m:dPr><m:begChr m:val="⌈"/><m:endChr m:val="⌉"/></m:dPr><m:e>{inner_xml}</m:e></m:d>')
                i += m_ceil.end()
                continue

            # Absolute value / norm / delimiters
            m_norm = re.match(r'\\lVert\s*(.*?)\\rVert', expr_str[i:])
            if m_norm:
                flush_text()
                inner_xml = parse_expr(m_norm.group(1))
                parts.append(f'<m:d><m:dPr><m:begChr m:val="‖"/><m:endChr m:val="‖"/></m:dPr><m:e>{inner_xml}</m:e></m:d>')
                i += m_norm.end()
                continue

            m_abs = re.match(r'\\lvert\s*(.*?)\\rvert', expr_str[i:])
            if m_abs:
                flush_text()
                inner_xml = parse_expr(m_abs.group(1))
                parts.append(f'<m:d><m:dPr><m:begChr m:val="|"/><m:endChr m:val="|"/></m:dPr><m:e>{inner_xml}</m:e></m:d>')
                i += m_abs.end()
                continue

            # 7. Overline / Bar: \overline{expr} or \bar{expr}
            m_bar = re.match(r'\\(overline|bar)\s*\{', expr_str[i:])
            if m_bar:
                flush_text()
                open_pos = i + m_bar.end() - 1
                inner, end_pos = extract_braced(expr_str, open_pos)
                i = end_pos
                inner_xml = parse_expr(inner)
                parts.append(f'<m:bar><m:barPr><m:pos m:val="top"/></m:barPr><m:e>{inner_xml}</m:e></m:bar>')
                continue

            # 8. Accents: \hat, \tilde, \dot, \ddot
            m_acc = re.match(r'\\(hat|tilde|dot|ddot)\s*\{', expr_str[i:])
            if m_acc:
                flush_text()
                cmd = m_acc.group(1)
                acc_chr = {"hat": "^", "tilde": "~", "dot": "˙", "ddot": "¨"}.get(cmd, "^")
                open_pos = i + m_acc.end() - 1
                inner, end_pos = extract_braced(expr_str, open_pos)
                i = end_pos
                inner_xml = parse_expr(inner)
                parts.append(f'<m:acc><m:accPr><m:chr m:val="{acc_chr}"/></m:accPr><m:e>{inner_xml}</m:e></m:acc>')
                continue

            # 9. Vectors \vec{...}
            m_vec = re.match(r'\\vec\s*\{', expr_str[i:])
            if m_vec:
                flush_text()
                open_pos = i + m_vec.end() - 1
                vec_inner, end_pos = extract_braced(expr_str, open_pos)
                i = end_pos
                vec_xml = parse_expr(vec_inner)
                parts.append(f'<m:acc><m:accPr><m:chr m:val="→"/></m:accPr><m:e>{vec_xml}</m:e></m:acc>')
                continue

            # 10. Subscripts and Superscripts attached to preceding element (supports primes like u', v'')
            m_subsup = re.match(r"([a-zA-Z0-9]+(?:'|\\prime)*|\\?[a-zA-Z]+)((?:_\{[^}]+\}|_[a-zA-Z0-9]+|\^\{[^}]+\}|\^[a-zA-Z0-9]+)+)", expr_str[i:])
            if m_subsup:
                flush_text()
                base_str = m_subsup.group(1)
                tokens_str = m_subsup.group(2)
                sub_m = re.search(r'_\{([^}]+)\}|_([a-zA-Z0-9]+)', tokens_str)
                sup_m = re.search(r'\^\{([^}]+)\}|\^([a-zA-Z0-9]+)', tokens_str)
                sub_val = (sub_m.group(1) or sub_m.group(2)) if sub_m else None
                sup_val = (sup_m.group(1) or sup_m.group(2)) if sup_m else None
                
                base_val = MATH_SYMBOLS.get(base_str, base_str.lstrip('\\'))
                base_xml = f'<m:r><m:t>{xml_escape(base_val)}</m:t></m:r>'
                
                if sub_val and sup_val:
                    parts.append(f'<m:sSubSup><m:e>{base_xml}</m:e><m:sub>{parse_expr(sub_val)}</m:sub><m:sup>{parse_expr(sup_val)}</m:sup></m:sSubSup>')
                elif sub_val:
                    parts.append(f'<m:sSub><m:e>{base_xml}</m:e><m:sub>{parse_expr(sub_val)}</m:sub></m:sSub>')
                elif sup_val:
                    parts.append(f'<m:sSup><m:e>{base_xml}</m:e><m:sup>{parse_expr(sup_val)}</m:sup></m:sSup>')
                i += m_subsup.end()
                continue

            # 11. Lone subscript / superscript (attaches to preceding element in parts to avoid empty base boxes)
            m_lone = re.match(r'(_\{[^}]+\}|_[a-zA-Z0-9]+|\^\{[^}]+\}|\^[a-zA-Z0-9]+)', expr_str[i:])
            if m_lone:
                flush_text()
                tok = m_lone.group(1)
                is_sub = tok.startswith('_')
                val = tok[2:-1] if (tok.startswith('_{') or tok.startswith('^{')) else tok[1:]
                val_xml = parse_expr(val)
                prev = parts.pop() if parts else '<m:r><m:t> </m:t></m:r>'
                
                m_prev_sup = re.match(r'^<m:sSup><m:e>(.*?)</m:e><m:sup>(.*?)</m:sup></m:sSup>$', prev)
                m_prev_sub = re.match(r'^<m:sSub><m:e>(.*?)</m:e><m:sub>(.*?)</m:sub></m:sSub>$', prev)
                
                if is_sub and m_prev_sup:
                    base_e = m_prev_sup.group(1)
                    sup_e = m_prev_sup.group(2)
                    parts.append(f'<m:sSubSup><m:e>{base_e}</m:e><m:sub>{val_xml}</m:sub><m:sup>{sup_e}</m:sup></m:sSubSup>')
                elif (not is_sub) and m_prev_sub:
                    base_e = m_prev_sub.group(1)
                    sub_e = m_prev_sub.group(2)
                    parts.append(f'<m:sSubSup><m:e>{base_e}</m:e><m:sub>{sub_e}</m:sub><m:sup>{val_xml}</m:sup></m:sSubSup>')
                elif is_sub:
                    parts.append(f'<m:sSub><m:e>{prev}</m:e><m:sub>{val_xml}</m:sub></m:sSub>')
                else:
                    parts.append(f'<m:sSup><m:e>{prev}</m:e><m:sup>{val_xml}</m:sup></m:sSup>')
                i += m_lone.end()
                continue

            char = expr_str[i]
            if char != '\\':
                text_buffer.append(char)
            i += 1

        flush_text()
        return "".join(parts)

    inner_xml = parse_expr(s)
    return f"<m:oMath>{inner_xml}</m:oMath>"

def format_non_math_text(text: str, default_bold: bool = False, color: str = None, font_size: int = 26) -> str:
    """
    Format text outside $...$, cleanly handling symbols, superscripts, subscripts,
    bold tags, and any stray LaTeX commands without leaving unparsed backslashes.
    """
    if not text:
        return ""
    
    # 1. Replace ASCII comparisons
    s = text.replace('<=', '≤').replace('>=', '≥').replace('!=', '≠')
    
    # 2. Replace common LaTeX commands that might appear without $
    replacements = [
        (r'\\le\b', '≤'), (r'\\leq\b', '≤'),
        (r'\\ge\b', '≥'), (r'\\geq\b', '≥'),
        (r'\\ne\b', '≠'), (r'\\neq\b', '≠'),
        (r'\\times\b', '×'),
        (r'\\cdot\b', '·'),
        (r'\\dots\b', '…'), (r'\\ldots\b', '…'), (r'\\cdots\b', '…'),
        (r'\\approx\b', '≈'),
        (r'\\pm\b', '±'),
        (r'\\mp\b', '∓'),
        (r'\\infty\b', '∞'),
        (r'\\circ\b', '°'), (r'\\degree\b', '°'),
        (r'\\sum\b', '∑'),
        (r'\\prod\b', '∏'),
        (r'\\sqrt\{([^}]+)\}', r'√(\1)'),
        (r'\\sqrt\b', '√'),
        (r'\\frac\{([^}]+)\}\{([^}]+)\}', r'(\1)/(\2)'),
        (r'\\dfrac\{([^}]+)\}\{([^}]+)\}', r'(\1)/(\2)'),
        (r'\\pmod\{([^}]+)\}', r'(mod \1)'),
        (r'\\bmod\b', 'mod'),
        (r'\\mod\b', 'mod'),
        (r'\\log\b', 'log'),
        (r'\\ln\b', 'ln'),
        (r'\\max\b', 'max'),
        (r'\\min\b', 'min'),
        (r'\\gcd\b', 'gcd'),
        (r'\\lcm\b', 'lcm'),
        (r'\\alpha\b', 'α'), (r'\\beta\b', 'β'), (r'\\pi\b', 'π'), (r'\\phi\b', 'φ'), (r'\\theta\b', 'θ'),
        (r'\\in\b', '∈'), (r'\\notin\b', '∉'), (r'\\subset\b', '⊂'), (r'\\cap\b', '∩'), (r'\\cup\b', '∪'),
        (r'\\rightarrow\b', '→'), (r'\\to\b', '→'), (r'\\leftarrow\b', '←'),
        (r'\\mathcal\{O\}', 'O'), (r'\\mathcal\{([^}]+)\}', r'\1'),
        (r'\\mathbb\{R\}', 'ℝ'), (r'\\mathbb\{Z\}', 'ℤ'), (r'\\mathbb\{N\}', 'ℕ'),
        (r'\\text\{([^}]+)\}', r'\1'),
        (r'\\textbf\{([^}]+)\}', r'**\1**'),
        (r'\\mathbf\{([^}]+)\}', r'**\1**'),
        (r'\\left\(', '('), (r'\\right\)', ')'),
        (r'\\left\[', '['), (r'\\right\]', ']'),
        (r'\\left\\\{', '{'), (r'\\right\\\}', '}'),
        (r'\\\{', '{'), (r'\\\}', '}'),
        (r'\\ ', ' '),
    ]
    for pat, rep in replacements:
        s = re.sub(pat, rep, s)
        
    # Strip any stray backslashes before words
    s = re.sub(r'\\([a-zA-Z]+)', r'\1', s)
    
    # 3. Split by bold (**bold**)
    runs_xml = []
    bold_parts = re.split(r'(\*\*[^*]+\*\*)', s)
    for part in bold_parts:
        if not part:
            continue
        is_bold = (part.startswith("**") and part.endswith("**")) or default_bold
        inner = part[2:-2] if (part.startswith("**") and part.endswith("**")) else part

        # Sub / Sup processing: ^5, ^{18}, _i, _{i,j}
        sub_sup_tokens = re.split(r'(\^[0-9a-zA-Z]{1,4}\b|\^\{[^}]+\}|_[0-9a-zA-Z]{1,3}\b|_\{[^}]+\})', inner)
        for token in sub_sup_tokens:
            if not token:
                continue

            bold_attr = "<w:b/>" if is_bold else ""
            color_attr = f'<w:color w:val="{color}"/>' if color else ""
            rPr_common = f"<w:rPr>{bold_attr}{color_attr}<w:sz w:val=\"{font_size}\"/></w:rPr>"

            if token.startswith("^"):
                val = token[2:-1] if token.startswith("^{") else token[1:]
                runs_xml.append(f'<w:r><w:rPr>{bold_attr}{color_attr}<w:vertAlign w:val="superscript"/><w:sz w:val="{font_size}"/></w:rPr><w:t xml:space="preserve">{xml_escape(val)}</w:t></w:r>')
            elif token.startswith("_"):
                val = token[2:-1] if token.startswith("_{") else token[1:]
                runs_xml.append(f'<w:r><w:rPr>{bold_attr}{color_attr}<w:vertAlign w:val="subscript"/><w:sz w:val="{font_size}"/></w:rPr><w:t xml:space="preserve">{xml_escape(val)}</w:t></w:r>')
            else:
                runs_xml.append(f'<w:r>{rPr_common}<w:t xml:space="preserve">{xml_escape(token)}</w:t></w:r>')

    return "".join(runs_xml)

def parse_runs_with_sub_sup(text: str, default_bold: bool = False, color: str = None, font_size: int = 26) -> str:
    """
    Parse a text string containing a mixture of natural language and inline math ($...$),
    generating WordprocessingML <w:r> runs and Office Math <m:oMath> elements.
    Maintains backward compatibility with callers expecting parse_runs_with_sub_sup.
    """
    if not text:
        return ""
    
    cleaned = clean_exam_text(text)
    
    # Split by inline math ($...$)
    tokens = re.split(r'(\$[^\$]+\$)', cleaned)
    elements = []
    
    for token in tokens:
        if not token:
            continue
        if token.startswith("$") and token.endswith("$") and len(token) > 2:
            # Inline math formula -> Native Word OMML equation!
            elements.append(latex_to_omml(token))
        else:
            # Natural language text -> Word runs with symbols & sub/sup
            elements.append(format_non_math_text(token, default_bold=default_bold, color=color, font_size=font_size))
            
    return "".join(elements)

def make_paragraph(text: str, align: str = "left", bold: bool = False, size_pt: int = 13, color: str = None, space_before: int = 0, space_after: int = 100) -> str:
    """Generate WordprocessingML paragraph XML with full math and OMML support."""
    jc_map = {"center": "center", "right": "right", "justify": "both", "left": "left"}
    jc_val = jc_map.get(align, "left")
    half_pt = size_pt * 2
    runs = parse_runs_with_sub_sup(text, default_bold=bold, color=color, font_size=half_pt)

    return f"""<w:p>
  <w:pPr>
    <w:jc w:val="{jc_val}"/>
    <w:spacing w:line="276" w:lineRule="auto" w:before="{space_before}" w:after="{space_after}"/>
  </w:pPr>
  {runs}
</w:p>"""

def make_heading(text: str, level: int = 1) -> str:
    """Generate Heading paragraph with clear distinct styling and math support."""
    size_pt = 14 if level == 1 else (13 if level == 2 else 12)
    color = "1E40AF" if level == 1 else "1E293B"
    before_space = 240 if level == 1 else 180
    after_space = 100 if level == 1 else 80
    runs = parse_runs_with_sub_sup(text, default_bold=True, color=color, font_size=size_pt * 2)

    return f"""<w:p>
  <w:pPr>
    <w:spacing w:before="{before_space}" w:after="{after_space}"/>
  </w:pPr>
  {runs}
</w:p>"""

def render_multiline_text(text: str, default_align: str = "justify") -> List[str]:
    """
    Split multiline text into Word paragraphs.
    Supports display equations ($$...$$), bullet points, numbered items, and prose.
    """
    if not text:
        return []
    
    cleaned = clean_exam_text(force_to_str(text))
    cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n')
    lines = cleaned.split("\n")
    p_elements = []
    
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
            
        # Check if line is a display equation ($$ ... $$)
        m_disp = re.match(r'^\$\$\s*(.+?)\s*\$\$$', line)
        if m_disp:
            omml_eq = latex_to_omml(m_disp.group(1))
            p_elements.append(f"""<w:p>
  <w:pPr>
    <w:jc w:val="center"/>
    <w:spacing w:before="120" w:after="120"/>
  </w:pPr>
  {omml_eq}
</w:p>""")
            continue
        
        # Check if line is a bullet point
        m_bullet = re.match(r'^[-*+•–]\s+(.*)$', line)
        m_num = re.match(r'^(\d+[\.)])\s+(.*)$', line)
        
        if m_bullet:
            content = m_bullet.group(1)
            runs = parse_runs_with_sub_sup(content)
            p_elements.append(f"""<w:p>
  <w:pPr>
    <w:ind w:left="480" w:hanging="240"/>
    <w:spacing w:line="276" w:lineRule="auto" w:before="40" w:after="60"/>
  </w:pPr>
  <w:r><w:rPr><w:b/><w:color w:val="2563EB"/><w:sz w:val="26"/></w:rPr><w:t>• </w:t></w:r>
  {runs}
</w:p>""")
        elif m_num:
            prefix = m_num.group(1)
            content = m_num.group(2)
            runs = parse_runs_with_sub_sup(content)
            p_elements.append(f"""<w:p>
  <w:pPr>
    <w:ind w:left="480" w:hanging="240"/>
    <w:spacing w:line="276" w:lineRule="auto" w:before="40" w:after="60"/>
  </w:pPr>
  <w:r><w:rPr><w:b/><w:color w:val="1E40AF"/><w:sz w:val="26"/></w:rPr><w:t>{prefix} </w:t></w:r>
  {runs}
</w:p>""")
        else:
            p_elements.append(make_paragraph(line, align=default_align, space_before=0, space_after=80))
            
    return p_elements

def make_explanation_box(s_num: int, explanation: str) -> str:
    """
    Format sample explanation in a professional callout box with distinct lines,
    bullets, and full mathematical equations.
    """
    if not explanation or not explanation.strip():
        return ""
    
    cleaned = clean_exam_text(clean_explanation_text(force_to_str(explanation)))
    cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n')
    lines = cleaned.split("\n")
    
    inner_ps = []
    inner_ps.append(f"""<w:p>
  <w:pPr>
    <w:spacing w:before="0" w:after="80"/>
  </w:pPr>
  <w:r>
    <w:rPr><w:b/><w:sz w:val="22"/><w:color w:val="1E40AF"/></w:rPr>
    <w:t>💡 Giải thích ví dụ {s_num}:</w:t>
  </w:r>
</w:p>""")
    
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        
        m_bullet = re.match(r'^[-*+•–]\s+(.*)$', line)
        m_num = re.match(r'^(\d+[\.)])\s+(.*)$', line)
        m_summary = re.match(r'^((?:Tổng|Tổng cộng|Do đó|Vậy|Kết luận|Kết quả)\s*[:=]\s*)(.*)$', line, re.IGNORECASE)
        
        if m_bullet:
            content = m_bullet.group(1)
            runs = parse_runs_with_sub_sup(content, font_size=22)
            inner_ps.append(f"""<w:p>
  <w:pPr>
    <w:ind w:left="360" w:hanging="200"/>
    <w:spacing w:line="240" w:lineRule="auto" w:before="30" w:after="40"/>
  </w:pPr>
  <w:r><w:rPr><w:b/><w:color w:val="2563EB"/><w:sz w:val="22"/></w:rPr><w:t>• </w:t></w:r>
  {runs}
</w:p>""")
        elif m_num:
            prefix = m_num.group(1)
            content = m_num.group(2)
            runs = parse_runs_with_sub_sup(content, font_size=22)
            inner_ps.append(f"""<w:p>
  <w:pPr>
    <w:ind w:left="360" w:hanging="200"/>
    <w:spacing w:line="240" w:lineRule="auto" w:before="30" w:after="40"/>
  </w:pPr>
  <w:r><w:rPr><w:b/><w:color w:val="1E40AF"/><w:sz w:val="22"/></w:rPr><w:t>{prefix} </w:t></w:r>
  {runs}
</w:p>""")
        elif m_summary:
            prefix = m_summary.group(1)
            content = m_summary.group(2)
            runs = parse_runs_with_sub_sup(content, font_size=22)
            inner_ps.append(f"""<w:p>
  <w:pPr>
    <w:spacing w:line="240" w:lineRule="auto" w:before="60" w:after="40"/>
  </w:pPr>
  <w:r><w:rPr><w:b/><w:color w:val="059669"/><w:sz w:val="22"/></w:rPr><w:t>✓ {xml_escape(prefix)}</w:t></w:r>
  {runs}
</w:p>""")
        else:
            runs = parse_runs_with_sub_sup(line, font_size=22)
            inner_ps.append(f"""<w:p>
  <w:pPr>
    <w:spacing w:line="250" w:lineRule="auto" w:before="40" w:after="60"/>
  </w:pPr>
  {runs}
</w:p>""")

    return f"""<w:tbl>
  <w:tblPr>
    <w:tblW w:w="9200" w:type="dxa"/>
    <w:tblBorders>
      <w:top w:val="none"/>
      <w:left w:val="single" w:sz="24" w:space="0" w:color="2563EB"/>
      <w:bottom w:val="none"/>
      <w:right w:val="none"/>
      <w:insideH w:val="none"/>
      <w:insideV w:val="none"/>
    </w:tblBorders>
    <w:tblCellMar>
      <w:top w:w="120" w:type="dxa"/>
      <w:left w:w="180" w:type="dxa"/>
      <w:bottom w:w="120" w:type="dxa"/>
      <w:right w:w="180" w:type="dxa"/>
    </w:tblCellMar>
  </w:tblPr>
  <w:tr>
    <w:tc>
      <w:tcPr>
        <w:tcW w:w="9200" w:type="dxa"/>
        <w:shd w:val="clear" w:color="auto" w:fill="F8FAFC"/>
      </w:tcPr>
      {"".join(inner_ps)}
    </w:tc>
  </w:tr>
</w:tbl>
<w:p><w:pPr><w:spacing w:before="60" w:after="60"/></w:pPr></w:p>"""

def make_code_box(code: str) -> str:
    """Generate a boxed, monospaced code snippet."""
    lines = code.split("\n")
    p_xmls = []
    for line in lines:
        escaped_line = xml_escape(line)
        p_xmls.append(f"""<w:p>
  <w:pPr>
    <w:spacing w:line="240" w:lineRule="auto" w:before="0" w:after="0"/>
  </w:pPr>
  <w:r>
    <w:rPr>
      <w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>
      <w:sz w:val="20"/>
      <w:color w:val="1E293B"/>
    </w:rPr>
    <w:t xml:space="preserve">{escaped_line}</w:t>
  </w:r>
</w:p>""")
    
    inner_ps = "".join(p_xmls)
    return f"""<w:tbl>
  <w:tblPr>
    <w:tblW w:w="9000" w:type="dxa"/>
    <w:tblBorders>
      <w:top w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>
      <w:left w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>
      <w:bottom w:val="single" w:sz="4" w:color="CBD5E1"/>
      <w:right w:val="single" w:sz="4" w:color="CBD5E1"/>
      <w:insideH w:val="none"/>
      <w:insideV w:val="none"/>
    </w:tblBorders>
    <w:tblCellMar>
      <w:top w:w="120" w:type="dxa"/>
      <w:left w:w="180" w:type="dxa"/>
      <w:bottom w:w="120" w:type="dxa"/>
      <w:right w:w="180" w:type="dxa"/>
    </w:tblCellMar>
  </w:tblPr>
  <w:tr>
    <w:tc>
      <w:tcPr>
        <w:tcW w:w="9000" w:type="dxa"/>
        <w:shd w:val="clear" w:color="auto" w:fill="F8FAFC"/>
      </w:tcPr>
      {inner_ps}
    </w:tc>
  </w:tr>
</w:tbl>"""

def create_olympiad_docx(data: Dict[str, Any], include_editorial: bool = True) -> bytes:
    """
    Generate a professional Microsoft Word (.docx) exam paper with native OMML math support,
    clean Vietnamese typography, and publication-ready layout.
    """
    problem = data.get("problem", {})
    solution = data.get("solution", {})
    topic = data.get("topic", {})
    diff = data.get("difficulty", {})

    code = str(problem.get("problem_code", "PROBLEM")).upper()
    name = str(problem.get("problem_name", "Bài toán Tin học"))
    inp_file = str(problem.get("input_file", f"{code}.INP"))
    out_file = str(problem.get("output_file", f"{code}.OUT"))
    time_lim = str(problem.get("time_limit", "1.0 giây"))
    mem_lim = str(problem.get("memory_limit", "256 MB"))

    body_elements = []

    # 1. School & Contest Header
    body_elements.append("""<w:tbl>
  <w:tblPr>
    <w:tblW w:w="9200" w:type="dxa"/>
    <w:tblBorders>
      <w:top w:val="none"/>
      <w:left w:val="none"/>
      <w:bottom w:val="none"/>
      <w:right w:val="none"/>
      <w:insideH w:val="none"/>
      <w:insideV w:val="none"/>
    </w:tblBorders>
  </w:tblPr>
  <w:tr>
    <w:tc>
      <w:tcPr><w:tcW w:w="4600" w:type="dxa"/></w:tcPr>
      <w:p><w:pPr><w:jc w:val="center"/><w:spacing w:after="60"/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="22"/></w:rPr><w:t>SỞ GIÁO DỤC VÀ ĐÀO TẠO</w:t></w:r></w:p>
      <w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="22"/></w:rPr><w:t>ĐỘI TUYỂN HỌC SINH GIỎI</w:t></w:r></w:p>
    </w:tc>
    <w:tc>
      <w:tcPr><w:tcW w:w="4600" w:type="dxa"/></w:tcPr>
      <w:p><w:pPr><w:jc w:val="center"/><w:spacing w:after="60"/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="22"/></w:rPr><w:t>KỲ THI HỌC SINH GIỎI TIN HỌC</w:t></w:r></w:p>
      <w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:i/><w:sz w:val="20"/></w:rPr><w:t>ĐỀ THI CHÍNH THỨC</w:t></w:r></w:p>
    </w:tc>
  </w:tr>
</w:tbl>""")

    # Divider
    body_elements.append("""<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="60" w:after="180"/></w:pPr><w:r><w:rPr><w:color w:val="94A3B8"/></w:rPr><w:t>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</w:t></w:r></w:p>""")

    # Problem Title
    body_elements.append(f"""<w:p>
  <w:pPr><w:jc w:val="center"/><w:spacing w:before="120" w:after="120"/></w:pPr>
  <w:r><w:rPr><w:b/><w:sz w:val="32"/><w:color w:val="0F172A"/></w:rPr><w:t>BÀI TOÁN: {xml_escape(clean_exam_text(name.upper()))}</w:t></w:r>
</w:p>""")

    # Problem Info Box Table
    body_elements.append(f"""<w:tbl>
  <w:tblPr>
    <w:tblW w:w="9200" w:type="dxa"/>
    <w:tblBorders>
      <w:top w:val="single" w:sz="6" w:color="2563EB"/>
      <w:bottom w:val="single" w:sz="6" w:color="2563EB"/>
      <w:left w:val="single" w:sz="6" w:color="2563EB"/>
      <w:right w:val="single" w:sz="6" w:color="2563EB"/>
      <w:insideH w:val="single" w:sz="4" w:color="E2E8F0"/>
      <w:insideV w:val="single" w:sz="4" w:color="E2E8F0"/>
    </w:tblBorders>
    <w:tblCellMar>
      <w:top w:w="80" w:type="dxa"/><w:left w:w="120" w:type="dxa"/>
      <w:bottom w:w="80" w:type="dxa"/><w:right w:w="120" w:type="dxa"/>
    </w:tblCellMar>
  </w:tblPr>
  <w:tr>
    <w:tc><w:tcPr><w:tcW w:w="2300" w:type="dxa"/><w:shd w:val="clear" w:color="auto" w:fill="F1F5F9"/></w:tcPr><w:p><w:pPr><w:spacing w:before="40" w:after="40"/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="22"/></w:rPr><w:t>Mã bài (Problem Code):</w:t></w:r></w:p></w:tc>
    <w:tc><w:tcPr><w:tcW w:w="2300" w:type="dxa"/></w:tcPr><w:p><w:pPr><w:spacing w:before="40" w:after="40"/></w:pPr><w:r><w:rPr><w:b/><w:color w:val="2563EB"/><w:sz w:val="22"/></w:rPr><w:t>{code}</w:t></w:r></w:p></w:tc>
    <w:tc><w:tcPr><w:tcW w:w="2300" w:type="dxa"/><w:shd w:val="clear" w:color="auto" w:fill="F1F5F9"/></w:tcPr><w:p><w:pPr><w:spacing w:before="40" w:after="40"/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="22"/></w:rPr><w:t>Chủ đề &amp; Mức độ:</w:t></w:r></w:p></w:tc>
    <w:tc><w:tcPr><w:tcW w:w="2300" w:type="dxa"/></w:tcPr><w:p><w:pPr><w:spacing w:before="40" w:after="40"/></w:pPr><w:r><w:rPr><w:sz w:val="22"/></w:rPr><w:t>{xml_escape(clean_exam_text(topic.get('name', '')))} - {xml_escape(clean_exam_text(diff.get('name', '')))}</w:t></w:r></w:p></w:tc>
  </w:tr>
  <w:tr>
    <w:tc><w:tcPr><w:tcW w:w="2300" w:type="dxa"/><w:shd w:val="clear" w:color="auto" w:fill="F1F5F9"/></w:tcPr><w:p><w:pPr><w:spacing w:before="40" w:after="40"/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="22"/></w:rPr><w:t>Tệp dữ liệu vào:</w:t></w:r></w:p></w:tc>
    <w:tc><w:tcPr><w:tcW w:w="2300" w:type="dxa"/></w:tcPr><w:p><w:pPr><w:spacing w:before="40" w:after="40"/></w:pPr><w:r><w:rPr><w:b/><w:color w:val="D97706"/><w:sz w:val="22"/></w:rPr><w:t>{inp_file}</w:t></w:r></w:p></w:tc>
    <w:tc><w:tcPr><w:tcW w:w="2300" w:type="dxa"/><w:shd w:val="clear" w:color="auto" w:fill="F1F5F9"/></w:tcPr><w:p><w:pPr><w:spacing w:before="40" w:after="40"/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="22"/></w:rPr><w:t>Tệp kết quả ra:</w:t></w:r></w:p></w:tc>
    <w:tc><w:tcPr><w:tcW w:w="2300" w:type="dxa"/></w:tcPr><w:p><w:pPr><w:spacing w:before="40" w:after="40"/></w:pPr><w:r><w:rPr><w:b/><w:color w:val="059669"/><w:sz w:val="22"/></w:rPr><w:t>{out_file}</w:t></w:r></w:p></w:tc>
  </w:tr>
  <w:tr>
    <w:tc><w:tcPr><w:tcW w:w="2300" w:type="dxa"/><w:shd w:val="clear" w:color="auto" w:fill="F1F5F9"/></w:tcPr><w:p><w:pPr><w:spacing w:before="40" w:after="40"/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="22"/></w:rPr><w:t>Giới hạn thời gian:</w:t></w:r></w:p></w:tc>
    <w:tc><w:tcPr><w:tcW w:w="2300" w:type="dxa"/></w:tcPr><w:p><w:pPr><w:spacing w:before="40" w:after="40"/></w:pPr><w:r><w:rPr><w:sz w:val="22"/></w:rPr><w:t>{time_lim}</w:t></w:r></w:p></w:tc>
    <w:tc><w:tcPr><w:tcW w:w="2300" w:type="dxa"/><w:shd w:val="clear" w:color="auto" w:fill="F1F5F9"/></w:tcPr><w:p><w:pPr><w:spacing w:before="40" w:after="40"/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="22"/></w:rPr><w:t>Giới hạn bộ nhớ:</w:t></w:r></w:p></w:tc>
    <w:tc><w:tcPr><w:tcW w:w="2300" w:type="dxa"/></w:tcPr><w:p><w:pPr><w:spacing w:before="40" w:after="40"/></w:pPr><w:r><w:rPr><w:sz w:val="22"/></w:rPr><w:t>{mem_lim}</w:t></w:r></w:p></w:tc>
  </w:tr>
</w:tbl>""")

    # Spacing
    body_elements.append("""<w:p><w:pPr><w:spacing w:before="120" w:after="120"/></w:pPr></w:p>""")

    # 2. Problem Statement
    body_elements.append(make_heading("I. ĐỀ BÀI", level=1))
    statement_raw = force_to_str(problem.get("story_and_statement", ""))
    body_elements.extend(render_multiline_text(statement_raw, default_align="justify"))

    # 3. Input Format
    body_elements.append(make_heading("II. DỮ LIỆU VÀO (INPUT)", level=1))
    in_format = force_to_str(problem.get("input_format", ""))
    body_elements.extend(render_multiline_text(in_format, default_align="left"))

    # 4. Output Format
    body_elements.append(make_heading("III. DỮ LIỆU RA (OUTPUT)", level=1))
    out_format = force_to_str(problem.get("output_format", ""))
    body_elements.extend(render_multiline_text(out_format, default_align="left"))

    # 5. Subtasks Table
    body_elements.append(make_heading("IV. RÀNG BUỘC VÀ BẢNG ĐIỂM (SUBTASKS)", level=1))
    subtasks = problem.get("subtasks", [])
    if subtasks:
        st_rows = []
        st_rows.append("""<w:tr>
  <w:tc><w:tcPr><w:tcW w:w="2000" w:type="dxa"/><w:shd w:val="clear" w:color="auto" w:fill="E2E8F0"/></w:tcPr><w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="60" w:after="60"/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="22"/></w:rPr><w:t>Subtask</w:t></w:r></w:p></w:tc>
  <w:tc><w:tcPr><w:tcW w:w="2000" w:type="dxa"/><w:shd w:val="clear" w:color="auto" w:fill="E2E8F0"/></w:tcPr><w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="60" w:after="60"/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="22"/></w:rPr><w:t>Tỉ lệ điểm</w:t></w:r></w:p></w:tc>
  <w:tc><w:tcPr><w:tcW w:w="5200" w:type="dxa"/><w:shd w:val="clear" w:color="auto" w:fill="E2E8F0"/></w:tcPr><w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="60" w:after="60"/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="22"/></w:rPr><w:t>Ràng buộc chi tiết</w:t></w:r></w:p></w:tc>
</w:tr>""")
        for st in subtasks:
            num = st.get("subtask_num", 1)
            pct = st.get("points_percent", 30)
            cstr = force_to_str(st.get("constraints", ""))
            
            # Constraints might be multi-line
            c_lines = [cl.strip() for cl in cstr.replace('\r\n', '\n').split("\n") if cl.strip()]
            c_paragraphs = []
            for cl in c_lines:
                c_runs = parse_runs_with_sub_sup(cl, font_size=22)
                c_paragraphs.append(f'<w:p><w:pPr><w:spacing w:before="40" w:after="40"/></w:pPr>{c_runs}</w:p>')
            if not c_paragraphs:
                c_paragraphs.append('<w:p><w:pPr><w:spacing w:before="40" w:after="40"/></w:pPr></w:p>')

            st_rows.append(f"""<w:tr>
  <w:tc><w:tcPr><w:tcW w:w="2000" w:type="dxa"/></w:tcPr><w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="60" w:after="60"/></w:pPr><w:r><w:rPr><w:b/><w:color w:val="2563EB"/><w:sz w:val="22"/></w:rPr><w:t>Subtask {num}</w:t></w:r></w:p></w:tc>
  <w:tc><w:tcPr><w:tcW w:w="2000" w:type="dxa"/></w:tcPr><w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="60" w:after="60"/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="22"/></w:rPr><w:t>{pct}% điểm</w:t></w:r></w:p></w:tc>
  <w:tc><w:tcPr><w:tcW w:w="5200" w:type="dxa"/></w:tcPr>{"".join(c_paragraphs)}</w:tc>
</w:tr>""")

        body_elements.append(f"""<w:tbl>
  <w:tblPr>
    <w:tblW w:w="9200" w:type="dxa"/>
    <w:tblBorders>
      <w:top w:val="single" w:sz="4" w:color="CBD5E1"/>
      <w:bottom w:val="single" w:sz="4" w:color="CBD5E1"/>
      <w:left w:val="single" w:sz="4" w:color="CBD5E1"/>
      <w:right w:val="single" w:sz="4" w:color="CBD5E1"/>
      <w:insideH w:val="single" w:sz="4" w:color="E2E8F0"/>
      <w:insideV w:val="single" w:sz="4" w:color="E2E8F0"/>
    </w:tblBorders>
    <w:tblCellMar>
      <w:top w:w="80" w:type="dxa"/><w:left w:w="120" w:type="dxa"/>
      <w:bottom w:w="80" w:type="dxa"/><w:right w:w="120" w:type="dxa"/>
    </w:tblCellMar>
  </w:tblPr>
  {"".join(st_rows)}
</w:tbl>""")

    # 6. Sample Tests
    body_elements.append(make_heading("V. VÍ DỤ MINH HỌA", level=1))
    for s in problem.get("sample_tests", []):
        s_num = s.get("sample_num", 1)
        s_in = clean_exam_text(force_to_str(s.get("input", ""))).strip()
        s_out = clean_exam_text(force_to_str(s.get("output", ""))).strip()
        s_exp = clean_explanation_text(force_to_str(s.get("explanation", ""))).strip()

        # Format input lines
        in_p = "".join(f'<w:p><w:pPr><w:spacing w:before="0" w:after="0"/></w:pPr><w:r><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="20"/></w:rPr><w:t xml:space="preserve">{xml_escape(l)}</w:t></w:r></w:p>' for l in s_in.split("\n"))
        out_p = "".join(f'<w:p><w:pPr><w:spacing w:before="0" w:after="0"/></w:pPr><w:r><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="20"/></w:rPr><w:t xml:space="preserve">{xml_escape(l)}</w:t></w:r></w:p>' for l in s_out.split("\n"))

        body_elements.append(f"""<w:p><w:pPr><w:spacing w:before="120" w:after="60"/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="22"/><w:color w:val="1E293B"/></w:rPr><w:t>Ví dụ {s_num}:</w:t></w:r></w:p>
<w:tbl>
  <w:tblPr>
    <w:tblW w:w="9200" w:type="dxa"/>
    <w:tblBorders>
      <w:top w:val="single" w:sz="4" w:color="CBD5E1"/><w:bottom w:val="single" w:sz="4" w:color="CBD5E1"/>
      <w:left w:val="single" w:sz="4" w:color="CBD5E1"/><w:right w:val="single" w:sz="4" w:color="CBD5E1"/>
      <w:insideH w:val="single" w:sz="4" w:color="E2E8F0"/><w:insideV w:val="single" w:sz="4" w:color="E2E8F0"/>
    </w:tblBorders>
  </w:tblPr>
  <w:tr>
    <w:tc><w:tcPr><w:tcW w:w="4600" w:type="dxa"/><w:shd w:val="clear" w:color="auto" w:fill="F1F5F9"/></w:tcPr><w:p><w:r><w:rPr><w:b/><w:sz w:val="20"/></w:rPr><w:t>{inp_file}</w:t></w:r></w:p></w:tc>
    <w:tc><w:tcPr><w:tcW w:w="4600" w:type="dxa"/><w:shd w:val="clear" w:color="auto" w:fill="F1F5F9"/></w:tcPr><w:p><w:r><w:rPr><w:b/><w:sz w:val="20"/></w:rPr><w:t>{out_file}</w:t></w:r></w:p></w:tc>
  </w:tr>
  <w:tr>
    <w:tc><w:tcPr><w:tcW w:w="4600" w:type="dxa"/><w:shd w:val="clear" w:color="auto" w:fill="FAFAFA"/></w:tcPr>{in_p}</w:tc>
    <w:tc><w:tcPr><w:tcW w:w="4600" w:type="dxa"/><w:shd w:val="clear" w:color="auto" w:fill="FAFAFA"/></w:tcPr>{out_p}</w:tc>
  </w:tr>
</w:tbl>""")
        if s_exp:
            body_elements.append(make_explanation_box(s_num, s_exp))

    # 7. Optional Editorial & Source Codes
    if include_editorial and solution:
        body_elements.append("""<w:p><w:r><w:br w:type="page"/></w:r></w:p>""")
        body_elements.append(f"""<w:p>
  <w:pPr><w:jc w:val="center"/><w:spacing w:before="120" w:after="120"/></w:pPr>
  <w:r><w:rPr><w:b/><w:sz w:val="28"/><w:color w:val="1E40AF"/></w:rPr><w:t>HƯỚNG DẪN CHẤM &amp; LỜI GIẢI CHI TIẾT</w:t></w:r>
</w:p>""")

        body_elements.append(make_heading("1. Thuật toán vét cạn (Subtask nhỏ)", level=2))
        bf_text = force_to_str(solution.get("brute_force_approach", ""))
        body_elements.extend(render_multiline_text(bf_text, default_align="justify"))

        body_elements.append(make_heading("2. Thuật toán tối ưu hoàn chỉnh (Full AC)", level=2))
        opt_text = force_to_str(solution.get("optimal_approach", ""))
        body_elements.extend(render_multiline_text(opt_text, default_align="justify"))

        cpp_code = solution.get("cpp_solution", "").strip()
        if cpp_code:
            body_elements.append(make_heading("3. Mã nguồn C++20 chuẩn", level=2))
            body_elements.append(make_code_box(cpp_code))

        py_code = solution.get("python_solution", "").strip()
        if py_code:
            body_elements.append(make_heading("4. Mã nguồn Python 3 chuẩn", level=2))
            body_elements.append(make_code_box(py_code))

    # Assemble Document XML with full Office Math namespace
    doc_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" 
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
            xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
  <w:body>
    {"".join(body_elements)}
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720"/>
    </w:sectPr>
  </w:body>
</w:document>"""

    # Build ZIP package
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>""")

        zf.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""")

        zf.writestr("word/_rels/document.xml.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>""")

        zf.writestr("word/styles.xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>
        <w:sz w:val="26"/>
        <w:color w:val="0F172A"/>
      </w:rPr>
    </w:rPrDefault>
  </w:docDefaults>
</w:styles>""")

        # Ensure entire document XML is 100% free of illegal XML control characters
        doc_xml = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f\ufffe\uffff]', '', doc_xml)
        zf.writestr("word/document.xml", doc_xml.encode("utf-8"))

    buf.seek(0)
    return buf.getvalue()
