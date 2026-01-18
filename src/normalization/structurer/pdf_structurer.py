"""
PDF Structurer
--------------
Segmentation 결과(PDF)를 chunk 단위로 표준화합니다.
- 모든 정책(헤더/풋터 판정, 문장 경계, 헤딩 판정 등)은 YAML에서 로드합니다.
- 줄 단위 세그먼트를 문장 단위로 병합해 페이지 경계 단절을 줄입니다.
- 딥파싱 저수준 필드(word_indices 등)는 제거하고, 스타일 정보는 요약형 메타/스팬으로 남깁니다.
"""
from typing import Any, Dict, List, Optional, Tuple
import re
from collections import Counter, defaultdict
from pathlib import Path
import yaml
import src.normalization.structurer.rules.rules_catalog as rule_cat

# 정책 경로 및 기본 룰 이름
RULES_PATH = Path(__file__).parent / "rules"
DEFAULT_RULE_NAME = rule_cat.PDF_DEFAULT


def _sanitize_doc_id(filename: Optional[str]) -> str:
    if not filename:
        return "document"
    base = filename.rsplit(".", 1)[0]
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in base)


def _drop_none(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


def _load_rules(rule_name: str = DEFAULT_RULE_NAME) -> Dict[str, Any]:
    rule_path = RULES_PATH / f"{rule_name}.yaml"
    try:
        with open(rule_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            return {k: v for k, v in data.items() if v is not None}
    except Exception as e:
        raise RuntimeError(f"Failed to load structurer rules: {rule_path} ({e})")


def _bucket_by_page(segments: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
    pages = defaultdict(list)
    for seg in segments:
        pages[seg.get("page_num", -1)].append(seg)
    for p in pages:
        pages[p] = sorted(pages[p], key=lambda s: s.get("segment_id", ""))
    return dict(pages)


def _find_repeated_lines(
    pages: Dict[int, List[Dict[str, Any]]],
    header_max_lines: int,
    footer_max_lines: int,
) -> Tuple[Counter, Counter]:
    header_counter = Counter()
    footer_counter = Counter()
    for _, segs in pages.items():
        if not segs:
            continue
        header_candidates = [s.get("text", "").strip() for s in segs[:header_max_lines]]
        footer_candidates = [s.get("text", "").strip() for s in segs[-footer_max_lines:]]
        for t in header_candidates:
            if t:
                header_counter[t] += 1
        for t in footer_candidates:
            if t:
                footer_counter[t] += 1
    return header_counter, footer_counter


def _is_repeated(text: str, counter: Counter, total_pages: int, repeat_ratio: float) -> bool:
    if not text or total_pages == 0:
        return False
    return counter[text] >= total_pages * repeat_ratio


def _is_header_footer(
    text: str,
    header_regexes: List[re.Pattern],
    footer_regexes: List[re.Pattern],
    repeated_headers: set,
    repeated_footers: set,
    is_header_zone: bool,
    is_footer_zone: bool,
) -> bool:
    if not text:
        return False
    for rx in header_regexes:
        if rx.match(text):
            return True
    for rx in footer_regexes:
        if rx.match(text):
            return True
    if is_header_zone and text in repeated_headers:
        return True
    if is_footer_zone and text in repeated_footers:
        return True
    return False


def _is_sentence_end(text: str, end_patterns: List[re.Pattern]) -> bool:
    if not text:
        return False
    for rx in end_patterns:
        if rx.search(text):
            return True
    return False


def _summarize_colors(colors: List[Any], accept_hex: bool, accept_rgb_list: bool, accept_numbers: bool) -> Dict[str, Any]:
    has_color = False
    dominant = None
    for c in colors or []:
        if c is None:
            continue
        if accept_hex and isinstance(c, str) and c.strip():
            has_color = True
            if dominant is None:
                dominant = c
            continue
        if accept_rgb_list and isinstance(c, list) and any(v is not None for v in c):
            has_color = True
            if dominant is None:
                dominant = c
            continue
        if accept_numbers and isinstance(c, (int, float)):
            has_color = True
            if dominant is None:
                dominant = c
    return {"has_color": has_color, "dominant_color": dominant}


def _merge_sentence_chunks(
    doc_id: str,
    filename: str,
    fmt: str,
    seg_buffer: List[Dict[str, Any]],
    chunks: List[Dict[str, Any]],
    heading_min_font_size: Optional[float],
    bold_font_patterns: List[re.Pattern],
    italic_font_patterns: List[re.Pattern],
    underline_font_patterns: List[re.Pattern],
    merge_space_cfg: Dict[str, Any],
    color_cfg: Dict[str, Any],
) -> None:
    if not seg_buffer:
        return
    pieces = []
    style_spans: List[Dict[str, Any]] = []
    cursor = 0
    prev_text = None
    keep_space_tokens = set(merge_space_cfg.get("keep_space_tokens", []))
    no_join_prefixes = tuple(merge_space_cfg.get("no_join_prefixes", []))
    join_single_syllable = bool(merge_space_cfg.get("join_single_syllable", True))
    require_prev_hangul = bool(merge_space_cfg.get("require_prev_hangul", True))
    require_next_hangul = bool(merge_space_cfg.get("require_next_hangul", True))
    accept_hex = bool(color_cfg.get("accept_hex", True))
    accept_rgb_list = bool(color_cfg.get("accept_rgb_list", True))
    accept_numbers = bool(color_cfg.get("accept_numbers", False))

    for seg in seg_buffer:
        raw_text = seg.get("text", "")
        text = raw_text.strip() if isinstance(raw_text, str) else ""
        if not text:
            continue
        if pieces:
            # Avoid inserting space for mid-word Korean splits, but keep it for normal word boundaries.
            last_token = prev_text.split()[-1] if prev_text else ""
            next_token = text.split()[0] if text else ""
            prev_hangul = bool(re.match(r"[가-힣]$", last_token)) if last_token else False
            next_hangul = bool(re.match(r"^[가-힣]", next_token)) if next_token else False
            can_join = bool(merge_space_cfg.get("enabled", True))
            if require_prev_hangul:
                can_join = can_join and prev_hangul
            if require_next_hangul:
                can_join = can_join and next_hangul
            if no_join_prefixes and next_token.startswith(no_join_prefixes):
                can_join = False
            if join_single_syllable and len(last_token) != 1:
                can_join = False
            if last_token in keep_space_tokens:
                can_join = False
            if not can_join:
                pieces.append(" ")
                cursor += 1
        start = cursor
        pieces.append(text)
        cursor += len(text)
        prev_text = text

        colors = seg.get("colors")
        has_color = False
        dominant = None
        if isinstance(colors, list):
            for c in colors:
                if c is None:
                    continue
                if accept_hex and isinstance(c, str) and c.strip():
                    has_color = True
                    if dominant is None:
                        dominant = c
                    continue
                if accept_rgb_list and isinstance(c, list) and any(v is not None for v in c):
                    has_color = True
                    if dominant is None:
                        dominant = c
                    continue
                if accept_numbers and isinstance(c, (int, float)):
                    has_color = True
                    if dominant is None:
                        dominant = c
        font_name = seg.get("font_name_mode")
        bold_flag = any(pat.search(font_name) for pat in bold_font_patterns) if font_name else False
        italic_flag = any(pat.search(font_name) for pat in italic_font_patterns) if font_name else False
        underline_flag = any(pat.search(font_name) for pat in underline_font_patterns) if font_name else False

        if has_color or seg.get("font_size_avg") or font_name:
            span_entry = {
                "start": start,
                "end": cursor,
                "color": dominant if has_color else None,
                "font_size_avg": seg.get("font_size_avg"),
                "font_size_max": seg.get("font_size_max"),
                "font_name": font_name,
                "bold": True if bold_flag else None,
                "italic": True if italic_flag else None,
                "underline": True if underline_flag else None,
            }
            style_spans.append(_drop_none(span_entry))

    content = "".join(pieces).strip()
    if not content:
        seg_buffer.clear()
        return

    source_ids = [s.get("segment_id") for s in seg_buffer if s.get("segment_id")]
    pages = sorted({s.get("page_num") for s in seg_buffer if s.get("page_num") is not None})
    degraded = any(s.get("degraded") for s in seg_buffer)

    # chunk 레벨 폰트 크기 요약
    font_sizes = [s.get("font_size_max") for s in seg_buffer if isinstance(s.get("font_size_max"), (int, float))]
    chunk_max_font_size = max(font_sizes) if font_sizes else None

    all_colors = []
    for s in seg_buffer:
        col = s.get("colors")
        if col:
            all_colors.extend(col if isinstance(col, list) else [col])
    color_info = _summarize_colors(
        all_colors,
        accept_hex,
        accept_rgb_list,
        accept_numbers,
    )

    chunk_type = "heading" if heading_min_font_size and chunk_max_font_size and chunk_max_font_size >= heading_min_font_size else "body"

    chunk_id = f"{doc_id}-s{len(chunks):04d}"
    metadata = _drop_none(
        {
            "filename": filename,
            "format": fmt,
            "pages": pages,
            "source_segments": source_ids,
            "degraded": degraded,
            "has_color": color_info["has_color"],
            "dominant_color": color_info["dominant_color"],
            "header_footer": None,
            "chunk_type": chunk_type,
            "max_font_size": chunk_max_font_size,
            "style_spans": style_spans or None,
        }
    )
    chunks.append(
        {
            "chunk_id": chunk_id,
            "content": content,
            "metadata": metadata,
        }
    )
    seg_buffer.clear()


def structure_pdf(seg_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    PDF segmentation JSON -> 표준화된 chunks 구조로 변환합니다.
    - 페이지 헤더/풋터 반복 라인은 YAML 정책에 따라 제거하거나 태그만 붙여 보존합니다.
    - 줄 단위 세그먼트를 문장 단위로 병합합니다(YAML에서 문장 경계 패턴 로드).
    """
    filename = seg_json.get("filename")
    fmt = seg_json.get("format", "PDF")
    doc_id = _sanitize_doc_id(filename)

    cfg = _load_rules()
    header_max_lines = int(cfg["header_max_lines"])
    footer_max_lines = int(cfg["footer_max_lines"])
    repeat_ratio = float(cfg["repeat_ratio"])
    preserve_repeated = bool(cfg["preserve_repeated"])
    header_tag = cfg["header_tag"]
    footer_tag = cfg["footer_tag"]
    heading_min_font_size = cfg.get("heading_min_font_size")
    heading_min_font_size = float(heading_min_font_size) if heading_min_font_size is not None else None
    sentence_end_regexes = [re.compile(pat) for pat in cfg["sentence_end_patterns"]]
    bold_font_patterns = [re.compile(pat) for pat in cfg.get("bold_font_patterns", [])]
    italic_font_patterns = [re.compile(pat) for pat in cfg.get("italic_font_patterns", [])]
    underline_font_patterns = [re.compile(pat) for pat in cfg.get("underline_font_patterns", [])]
    merge_space_cfg = cfg.get("merge_space", {}) if isinstance(cfg, dict) else {}
    color_cfg = cfg.get("color_handling", {}) if isinstance(cfg, dict) else {}

    header_regexes = [re.compile(pat) for pat in cfg["header_regexes"]]
    footer_regexes = [re.compile(pat) for pat in cfg["footer_regexes"]]
    heading_cfg = cfg.get("heading_split", {}) if isinstance(cfg, dict) else {}
    heading_enabled = bool(heading_cfg.get("enabled", True))
    heading_patterns = [re.compile(p) for p in heading_cfg.get("patterns", [])]
    heading_inline_patterns = [re.compile(p) for p in heading_cfg.get("inline_patterns", [])]
    section_break_regexes = heading_patterns or [re.compile(r"$^")]
    heading_inline_regexes = heading_inline_patterns or [re.compile(r"$^")]
    exception_cfg = cfg.get("exceptions", {}) if isinstance(cfg, dict) else {}
    disable_heading_after = [re.compile(p) for p in exception_cfg.get("disable_heading_after", [])]
    heading_disabled = False

    segments: List[Dict[str, Any]] = seg_json.get("segments", []) or []
    chunks: List[Dict[str, Any]] = []

    pages = _bucket_by_page(segments)

    header_counter, footer_counter = _find_repeated_lines(pages, header_max_lines, footer_max_lines)
    repeated_headers = {
        t for t, _ in header_counter.items() if _is_repeated(t, header_counter, len(pages), repeat_ratio)
    }
    repeated_footers = {
        t for t, _ in footer_counter.items() if _is_repeated(t, footer_counter, len(pages), repeat_ratio)
    }

    empty_text = 0
    degraded = 0
    flagged_header_footer = 0

    sentence_buffer: List[Dict[str, Any]] = []

    def split_by_heading(text: str, end_patterns: List[re.Pattern]) -> List[str]:
        if not text:
            return []
        if not heading_enabled or heading_disabled:
            return [text]
        matches = []
        for rx in heading_inline_regexes:
            matches.extend(list(rx.finditer(text)))
        matches = sorted(matches, key=lambda m: m.start())
        if len(matches) <= 1:
            return [text]
        parts = []
        for i, m in enumerate(matches):
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            if start > 0:
                prev = text[:start].rstrip()
                if prev and not _is_sentence_end(prev, end_patterns):
                    continue
                parts.append(prev.strip())
            parts.append(text[start:end].strip())
        return [p for p in parts if p]

    for page_num, segs in sorted(pages.items()):
        for idx_within_page, seg in enumerate(segs):
            raw_text = seg.get("text", "")
            text = raw_text.strip() if isinstance(raw_text, str) else ""

            is_header_zone = idx_within_page < header_max_lines
            is_footer_zone = idx_within_page >= len(segs) - footer_max_lines
            is_hf = _is_header_footer(
                text,
                header_regexes,
                footer_regexes,
                repeated_headers,
                repeated_footers,
                is_header_zone,
                is_footer_zone,
            )

            if is_hf:
                flagged_header_footer += 1
                if preserve_repeated:
                    chunks.append(
                        {
                            "chunk_id": seg.get("segment_id") or f"{doc_id}-p{page_num:02d}-seg{idx_within_page:04d}",
                            "content": text,
                            "metadata": _drop_none(
                                {
                                    "filename": seg.get("filename") or filename,
                                    "format": fmt,
                                    "page": seg.get("page_num"),
                                    "source_segment_id": seg.get("segment_id"),
                                    "degraded": bool(seg.get("degraded")),
                                    "header_footer": header_tag if is_header_zone else footer_tag,
                                }
                            ),
                        }
                    )
                continue

            if not text:
                empty_text += 1
                continue
            if seg.get("degraded"):
                degraded += 1

            if any(rx.match(text) for rx in disable_heading_after):
                heading_disabled = True

            for part_idx, part_text in enumerate(split_by_heading(text, sentence_end_regexes)):
                part_seg = seg if part_idx == 0 else {**seg, "segment_id": f"{seg.get('segment_id')}-part{part_idx:02d}"}
                part_seg["text"] = part_text

                # If a new section heading starts, flush current buffer first.
                if heading_enabled and not heading_disabled and sentence_buffer:
                    if any(rx.match(part_text) for rx in section_break_regexes):
                        _merge_sentence_chunks(
                            doc_id,
                            filename,
                            fmt,
                            sentence_buffer,
                            chunks,
                            heading_min_font_size,
                            bold_font_patterns,
                            italic_font_patterns,
                            underline_font_patterns,
                            merge_space_cfg,
                            color_cfg,
                        )

                sentence_buffer.append(part_seg)
                if _is_sentence_end(part_text, sentence_end_regexes):
                    _merge_sentence_chunks(
                        doc_id,
                        filename,
                        fmt,
                        sentence_buffer,
                        chunks,
                        heading_min_font_size,
                        bold_font_patterns,
                        italic_font_patterns,
                        underline_font_patterns,
                        merge_space_cfg,
                        color_cfg,
                    )

    _merge_sentence_chunks(
        doc_id,
        filename,
        fmt,
        sentence_buffer,
        chunks,
        heading_min_font_size,
        bold_font_patterns,
        italic_font_patterns,
        underline_font_patterns,
        merge_space_cfg,
        color_cfg,
    )

    return {
        "doc_id": doc_id,
        "filename": filename,
        "format": fmt,
        "chunks": chunks,
        "stats": {
            "total_segments": len(segments),
            "empty_text_segments": empty_text,
            "degraded_segments": degraded,
            "degraded_pages": seg_json.get("degraded_pages", []),
            "flagged_header_footer": flagged_header_footer,
            "repeated_headers": list(repeated_headers),
            "repeated_footers": list(repeated_footers),
        },
    }
