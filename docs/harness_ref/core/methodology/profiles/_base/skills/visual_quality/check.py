"""visual_quality/check.py — машинная проверка визуала (3.2.5). Детерминированно."""
from __future__ import annotations
from core.methodology.rules import GeneratedDoc, RuleIssue
SID = "visual_quality"
def _i(c, s, m, **e): return RuleIssue(SID, f"{SID}.{c}", s, m, e)
def check(doc: GeneratedDoc, params: dict) -> list[RuleIssue]:
    out = []
    min_w, min_h = params["min_resolution"]
    for img in doc.images:
        fmt = img.format.lower()
        if fmt in params["formats_conditional"]:
            out.append(_i("format_conditional", "soft", f"{img.path}: {fmt} только по согласованию"))
        elif fmt not in params["formats"]:
            out.append(_i("format", "hard", f"{img.path}: формат {fmt} не допускается"))
        if img.is_vector or fmt == "svg":
            continue
        if max(img.width, img.height) < params["min_long_side"]:
            out.append(_i("resolution", "hard", f"{img.path}: {img.width}x{img.height}px — длинная сторона < {params['min_long_side']}px"))
        elif img.width < min_w or img.height < min_h:
            out.append(_i("resolution_below_target", "soft", f"{img.path}: < {min_w}x{min_h}px"))
        if img.dpi is None:
            out.append(_i("dpi_unknown", "soft", f"{img.path}: DPI не извлекается"))
        elif img.dpi < params["min_dpi"]:
            out.append(_i("dpi", "hard", f"{img.path}: DPI {img.dpi} < {params['min_dpi']}"))
        kb = img.size_bytes / 1024
        if kb > params["max_file_kb"]:
            out.append(_i("file_size", "hard", f"{img.path}: {kb:.0f}KB > {params['max_file_kb']}KB"))
        elif kb > params["optimal_file_kb"]:
            out.append(_i("file_size_suboptimal", "soft", f"{img.path}: {kb:.0f}KB > оптимума"))
    return out
