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


def _base_source_id(source_id: Optional[str]) -> Optional[str]:
    if not source_id:
        return None
    # Strip split suffixes like -partXX or -partXX-listYY.
    return re.sub(r"-part\\d+(?:-list\\d+)?$", "", source_id)


def add_group_ids(structured: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    group_cfg = cfg.get("group_id", {}) if isinstance(cfg, dict) else {}
    if not group_cfg or not group_cfg.get("enabled", True):
        return structured
    open_patterns = [re.compile(p) for p in group_cfg.get("open_patterns", [])]
    close_patterns = [re.compile(p) for p in group_cfg.get("close_patterns", [])]
    attach_next_patterns = [re.compile(p) for p in group_cfg.get("attach_next_if_matches", [])]
    merge_cfg = group_cfg.get("merge_sentence", {}) if isinstance(group_cfg, dict) else {}
    merge_enabled = bool(merge_cfg.get("enabled", True))
    merge_sentence_end = [re.compile(p) for p in merge_cfg.get("sentence_end_patterns", [])]
    merge_sentence_exceptions = _compile_sentence_end_exceptions(merge_cfg.get("sentence_end_exceptions", []))
    merge_block_patterns = [re.compile(p) for p in merge_cfg.get("block_if_next_matches", [])]
    merge_allow_next_patterns = [re.compile(p) for p in merge_cfg.get("allow_if_next_matches", [])]
    merge_next_hangul = bool(merge_cfg.get("next_start_hangul", True))
    merge_next_regex = merge_cfg.get("next_start_regex")
    merge_next_rx = re.compile(merge_next_regex) if merge_next_regex else None

    chunks = structured.get("chunks", [])
    for chunk in chunks:
        meta = chunk.get("metadata", {})
        base_id = None
        source_segments = meta.get("source_segments")
        if isinstance(source_segments, list) and source_segments:
            base_id = _base_source_id(source_segments[0])
        if not base_id:
            base_id = _base_source_id(meta.get("source_segment_id"))
        if not base_id:
            base_id = chunk.get("chunk_id")
        if base_id:
            meta["group_id"] = base_id
    # If a chunk ends with an open <... or [..., bind next chunk to same group_id.
    for idx, chunk in enumerate(chunks[:-1]):
        text = chunk.get("content", "")
        if not isinstance(text, str):
            continue
        has_open = any(rx.search(text) for rx in open_patterns) if open_patterns else False
        has_close = any(rx.search(text) for rx in close_patterns) if close_patterns else False
        if not has_open or has_close:
            continue
        curr_gid = chunk.get("metadata", {}).get("group_id")
        if not curr_gid:
            continue
        next_chunk = chunks[idx + 1]
        next_meta = next_chunk.get("metadata", {})
        next_meta["group_id"] = curr_gid
    # Attach trailing annotation chunks like "[본조신설 ...]" to the previous group.
    if attach_next_patterns:
        for idx, chunk in enumerate(chunks[:-1]):
            curr_gid = chunk.get("metadata", {}).get("group_id")
            if not curr_gid:
                continue
            next_chunk = chunks[idx + 1]
            next_text = next_chunk.get("content", "")
            if not isinstance(next_text, str):
                continue
            if any(rx.match(next_text.strip()) for rx in attach_next_patterns):
                next_chunk.get("metadata", {})["group_id"] = curr_gid
    # Merge hard-wrapped lines that continue a sentence across segments.
    if not merge_enabled:
        return structured
    for idx, chunk in enumerate(chunks[:-1]):
        curr_text = chunk.get("content", "")
        next_chunk = chunks[idx + 1]
        next_text = next_chunk.get("content", "")
        if not isinstance(curr_text, str) or not isinstance(next_text, str):
            continue
        if _is_sentence_end_with_exceptions(
            curr_text.strip(),
            merge_sentence_end,
            merge_sentence_exceptions,
            next_text.strip() if isinstance(next_text, str) else None,
        ):
            continue
        if any(rx.match(next_text.strip()) for rx in merge_block_patterns):
            if not any(rx.match(next_text.strip()) for rx in merge_allow_next_patterns):
                continue
        if merge_next_hangul and merge_next_rx and merge_next_rx.match(next_text.strip()):
            curr_gid = chunk.get("metadata", {}).get("group_id")
            if curr_gid:
                next_chunk.get("metadata", {})["group_id"] = curr_gid
    return structured


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


def _compile_sentence_end_exceptions(exceptions_cfg: Any) -> List[Dict[str, Any]]:
    if not isinstance(exceptions_cfg, list):
        return []
    compiled = []
    for item in exceptions_cfg:
        if not isinstance(item, dict):
            continue
        end_pat = item.get("end_pattern")
        prefixes = item.get("next_prefixes", [])
        if not end_pat or not prefixes:
            continue
        compiled.append(
            {
                "end_pattern": re.compile(end_pat),
                "next_prefixes": [re.compile(p) for p in prefixes],
            }
        )
    return compiled


def _is_sentence_end_with_exceptions(
    text: str,
    end_patterns: List[re.Pattern],
    exceptions: List[Dict[str, Any]],
    next_text: Optional[str],
) -> bool:
    if not _is_sentence_end(text, end_patterns):
        return False
    if not exceptions or not next_text:
        return True
    for item in exceptions:
        if item["end_pattern"].search(text):
            if any(rx.match(next_text) for rx in item["next_prefixes"]):
                return False
    return True


def _pick_span_color(
    colors: List[Any],
    accept_hex: bool,
    accept_rgb_list: bool,
    accept_numbers: bool,
) -> Optional[Any]:
    if not colors:
        return None
    if accept_hex:
        hexes = [c for c in colors if isinstance(c, str) and c.strip()]
        if "#0000FF" in [h.upper() for h in hexes]:
            return "#0000FF"
        if hexes:
            return hexes[0]
    if accept_rgb_list:
        lists = [c for c in colors if isinstance(c, list) and any(v is not None for v in c)]
        if lists:
            return lists[0]
    if accept_numbers:
        nums = [c for c in colors if isinstance(c, (int, float))]
        if nums:
            return nums[0]
    return None


def _normalize_break_chars(value: Any) -> Optional[set]:
    if value is None:
        return None
    if isinstance(value, str):
        return set(value)
    if isinstance(value, list):
        chars = []
        for item in value:
            if isinstance(item, str):
                chars.append(item)
        return set("".join(chars)) if chars else None
    return None


def _iter_token_spans(
    text: str,
    token_regex: re.Pattern,
    break_chars: Optional[set],
) -> List[Tuple[int, int]]:
    spans: List[Tuple[int, int]] = []
    for match in token_regex.finditer(text):
        token = match.group(0)
        base = match.start()
        sub_start = 0
        for idx, ch in enumerate(token):
            if break_chars and ch in break_chars and idx > sub_start:
                spans.append((base + sub_start, base + idx))
                sub_start = idx
        spans.append((base + sub_start, base + len(token)))
    return spans


def _token_color_spans(
    text: str,
    colors: List[Any],
    start: int,
    accept_hex: bool,
    accept_rgb_list: bool,
    accept_numbers: bool,
    token_regex: re.Pattern,
    break_chars: Optional[set],
) -> Optional[List[Tuple[int, int, Optional[Any]]]]:
    tokens = _iter_token_spans(text, token_regex, break_chars)
    if tokens and len(tokens) == len(colors):
        spans: List[Tuple[int, int, Optional[Any]]] = []
        run_start = None
        run_end = None
        run_color = None
        for (tok_start, tok_end), raw_color in zip(tokens, colors):
            token_color = _pick_span_color([raw_color], accept_hex, accept_rgb_list, accept_numbers)
            token_start = start + tok_start
            token_end = start + tok_end
            if run_start is None:
                run_start = token_start
                run_end = token_end
                run_color = token_color
                continue
            if token_color == run_color:
                run_end = token_end
                continue
            spans.append((run_start, run_end, run_color))
            run_start = token_start
            run_end = token_end
            run_color = token_color
        if run_start is not None:
            spans.append((run_start, run_end, run_color))
        return spans

    base_tokens = _iter_token_spans(text, token_regex, None)
    if not base_tokens or len(base_tokens) != len(colors):
        return None

    def split_token_spans(token_text: str, token_start: int) -> List[Tuple[int, int]]:
        spans: List[Tuple[int, int]] = []
        if not break_chars:
            spans.append((token_start, token_start + len(token_text)))
            return spans
        sub_start = 0
        for idx, ch in enumerate(token_text):
            if ch in break_chars and idx > sub_start:
                spans.append((token_start + sub_start, token_start + idx))
                sub_start = idx
        spans.append((token_start + sub_start, token_start + len(token_text)))
        return spans

    spans: List[Tuple[int, int, Optional[Any]]] = []
    run_start = None
    run_end = None
    run_color = None
    for (tok_start, tok_end), raw_color in zip(base_tokens, colors):
        token_color = _pick_span_color([raw_color], accept_hex, accept_rgb_list, accept_numbers)
        token_text = text[tok_start:tok_end]
        for sub_start, sub_end in split_token_spans(token_text, start + tok_start):
            if run_start is None:
                run_start = sub_start
                run_end = sub_end
                run_color = token_color
                continue
            if token_color == run_color:
                run_end = sub_end
                continue
            spans.append((run_start, run_end, run_color))
            run_start = sub_start
            run_end = sub_end
            run_color = token_color
    if run_start is not None:
        spans.append((run_start, run_end, run_color))
    return spans


def _summarize_colors(span_colors: List[Any]) -> Dict[str, Any]:
    valid = [c for c in span_colors if c is not None]
    if not valid:
        return {"has_color": False, "dominant_color": None}
    counts: Dict[Any, int] = {}
    for c in valid:
        counts[c] = counts.get(c, 0) + 1
    dominant = max(counts, key=counts.get)
    return {"has_color": True, "dominant_color": dominant}


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
    token_regex: re.Pattern,
    token_break_chars: Optional[set],
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
    prev_hangul_regex = merge_space_cfg.get("prev_hangul_regex")
    next_hangul_regex = merge_space_cfg.get("next_hangul_regex")
    prev_hangul_rx = re.compile(prev_hangul_regex) if prev_hangul_regex else None
    next_hangul_rx = re.compile(next_hangul_regex) if next_hangul_regex else None
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
            prev_hangul = bool(prev_hangul_rx.search(last_token)) if (prev_hangul_rx and last_token) else False
            next_hangul = bool(next_hangul_rx.search(next_token)) if (next_hangul_rx and next_token) else False
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
        font_name = seg.get("font_name_mode")
        bold_flag = any(pat.search(font_name) for pat in bold_font_patterns) if font_name else False
        italic_flag = any(pat.search(font_name) for pat in italic_font_patterns) if font_name else False
        underline_flag = any(pat.search(font_name) for pat in underline_font_patterns) if font_name else False

        token_spans = None
        if isinstance(colors, list):
            token_spans = _token_color_spans(
                text,
                colors,
                start,
                accept_hex,
                accept_rgb_list,
                accept_numbers,
                token_regex,
                token_break_chars,
            )

        if token_spans:
            for span_start, span_end, span_color in token_spans:
                span_entry = {
                    "start": span_start,
                    "end": span_end,
                    "color": span_color,
                    "font_size_avg": seg.get("font_size_avg"),
                    "font_size_max": seg.get("font_size_max"),
                    "font_name": font_name,
                    "bold": True if bold_flag else None,
                    "italic": True if italic_flag else None,
                    "underline": True if underline_flag else None,
                }
                style_spans.append(_drop_none(span_entry))
        else:
            span_color = None
            if isinstance(colors, list):
                span_color = _pick_span_color(colors, accept_hex, accept_rgb_list, accept_numbers)
            elif colors is not None:
                span_color = _pick_span_color([colors], accept_hex, accept_rgb_list, accept_numbers)
            if span_color or seg.get("font_size_avg") or font_name:
                span_entry = {
                    "start": start,
                    "end": cursor,
                    "color": span_color,
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


    chunk_type = "heading" if heading_min_font_size and chunk_max_font_size and chunk_max_font_size >= heading_min_font_size else "body"

    chunk_id = f"{doc_id}-s{len(chunks):04d}"
    metadata = _drop_none(
        {
            "filename": filename,
            "format": fmt,
            "pages": pages,
            "source_segments": source_ids,
            "degraded": degraded,
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
    preserve_repeated_mode = str(cfg.get("preserve_repeated_mode", "all")).lower()
    preserve_header_footer = str(cfg.get("preserve_header_footer", "all")).lower()
    header_tag = cfg["header_tag"]
    footer_tag = cfg["footer_tag"]
    heading_min_font_size = cfg.get("heading_min_font_size")
    heading_min_font_size = float(heading_min_font_size) if heading_min_font_size is not None else None
    sentence_end_regexes = [re.compile(pat) for pat in cfg["sentence_end_patterns"]]
    sentence_end_exceptions = _compile_sentence_end_exceptions(cfg.get("sentence_end_exceptions", []))
    bold_font_patterns = [re.compile(pat) for pat in cfg.get("bold_font_patterns", [])]
    italic_font_patterns = [re.compile(pat) for pat in cfg.get("italic_font_patterns", [])]
    underline_font_patterns = [re.compile(pat) for pat in cfg.get("underline_font_patterns", [])]
    merge_space_cfg = cfg.get("merge_space", {}) if isinstance(cfg, dict) else {}
    color_cfg = cfg.get("color_handling", {}) if isinstance(cfg, dict) else {}
    style_span_cfg = cfg.get("style_span_split", {}) if isinstance(cfg, dict) else {}
    token_regex_pattern = style_span_cfg.get("token_regex")
    if not token_regex_pattern:
        raise RuntimeError("Missing style_span_split.token_regex in structurer rules.")
    if "\\\\" in token_regex_pattern:
        # YAML에 이스케이프가 중복된 경우를 방지한다.
        token_regex_pattern = token_regex_pattern.replace("\\\\", "\\")
    token_regex = re.compile(token_regex_pattern)
    token_break_chars = _normalize_break_chars(style_span_cfg.get("token_break_chars"))

    header_regexes = [re.compile(pat) for pat in cfg["header_regexes"]]
    footer_regexes = [re.compile(pat) for pat in cfg["footer_regexes"]]
    heading_cfg = cfg.get("heading_split", {}) if isinstance(cfg, dict) else {}
    heading_enabled = bool(heading_cfg.get("enabled", True))
    heading_patterns = [re.compile(p) for p in heading_cfg.get("patterns", [])]
    heading_inline_patterns = [re.compile(p) for p in heading_cfg.get("inline_patterns", [])]
    list_cfg = cfg.get("list_split", {}) if isinstance(cfg, dict) else {}
    list_enabled = bool(list_cfg.get("enabled", False))
    list_inline_patterns = [re.compile(p) for p in list_cfg.get("inline_patterns", [])]
    list_start_patterns = [re.compile(p) for p in list_cfg.get("start_patterns", [])]
    article_list_cfg = cfg.get("article_list_split", {}) if isinstance(cfg, dict) else {}
    article_list_enabled = bool(article_list_cfg.get("enabled", False))
    article_list_patterns = [re.compile(p) for p in article_list_cfg.get("patterns", [])]
    article_list_prefix_regex = article_list_cfg.get("required_prefix_regex")
    article_list_prefix_rx = re.compile(article_list_prefix_regex) if article_list_prefix_regex else None
    article_list_skip_contains = [re.compile(p) for p in article_list_cfg.get("skip_if_contains_regexes", [])]
    noop_regex = cfg.get("noop_regex")
    if not noop_regex:
        raise RuntimeError("Missing noop_regex in structurer rules.")
    noop_regexes = [re.compile(noop_regex)]
    section_break_regexes = heading_patterns or noop_regexes
    heading_inline_regexes = heading_inline_patterns or noop_regexes
    exception_cfg = cfg.get("exceptions", {}) if isinstance(cfg, dict) else {}
    disable_heading_after = [re.compile(p) for p in exception_cfg.get("disable_heading_after", [])]
    heading_disabled = False

    segments: List[Dict[str, Any]] = seg_json.get("segments", []) or []
    chunks: List[Dict[str, Any]] = []

    pages = _bucket_by_page(segments)
    ordered_pages = sorted(pages.items())
    ordered_segs = [seg for _, segs in ordered_pages for seg in segs]
    next_text_by_segment_id: Dict[str, str] = {}
    for idx, seg in enumerate(ordered_segs):
        seg_id = seg.get("segment_id")
        if not seg_id:
            continue
        next_text = None
        for next_seg in ordered_segs[idx + 1 :]:
            raw = next_seg.get("text")
            if isinstance(raw, str) and raw.strip():
                next_text = raw.strip()
                break
        if next_text:
            next_text_by_segment_id[seg_id] = next_text

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
    preserved_headers = set()
    preserved_footers = set()

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

    def split_by_list(text: str) -> List[str]:
        if not text or not list_enabled or not list_inline_patterns:
            return [text]
        matches = []
        for rx in list_inline_patterns:
            matches.extend(list(rx.finditer(text)))
        matches = sorted(matches, key=lambda m: m.start())
        if len(matches) <= 1:
            return [text]
        parts = []
        prev_end = 0
        for i, m in enumerate(matches):
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            if start > prev_end:
                prev = text[prev_end:start].strip()
                if prev:
                    parts.append(prev)
            parts.append(text[start:end].strip())
            prev_end = end
        return [p for p in parts if p]

    def split_article_list(text: str) -> List[str]:
        if not text or not article_list_enabled or not article_list_patterns:
            return [text]
        if article_list_prefix_rx and not article_list_prefix_rx.match(text):
            return [text]
        if article_list_skip_contains and any(rx.search(text) for rx in article_list_skip_contains):
            return [text]
        for rx in article_list_patterns:
            m = rx.search(text)
            if m and m.start() > 0:
                head = text[: m.start()].rstrip()
                tail = text[m.start():].lstrip()
                if head and tail:
                    return [head, tail]
        return [text]

    for page_num, segs in ordered_pages:
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
                    if preserve_header_footer == "header_only" and is_footer_zone:
                        continue
                    if preserve_header_footer == "footer_only" and is_header_zone:
                        continue
                    if preserve_repeated_mode == "first":
                        if is_header_zone and text in preserved_headers:
                            continue
                        if is_footer_zone and text in preserved_footers:
                            continue
                        if is_header_zone:
                            preserved_headers.add(text)
                        if is_footer_zone:
                            preserved_footers.add(text)
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
                article_parts = split_article_list(part_text)
                list_parts = []
                for ap in article_parts:
                    list_parts.extend(split_by_list(ap))
                for list_idx, list_text in enumerate(list_parts):
                    next_text = None
                    if list_idx + 1 < len(list_parts):
                        next_text = list_parts[list_idx + 1].strip()
                    else:
                        next_text = next_text_by_segment_id.get(seg.get("segment_id"))
                    part_seg = seg if (part_idx == 0 and list_idx == 0) else {
                        **seg,
                        "segment_id": f"{seg.get('segment_id')}-part{part_idx:02d}-list{list_idx:02d}",
                    }
                    part_seg["text"] = list_text

                    if list_enabled and list_start_patterns and sentence_buffer:
                        if any(rx.match(list_text) for rx in list_start_patterns):
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
                                token_regex,
                                token_break_chars,
                            )

                    # If a new section heading starts, flush current buffer first.
                    if heading_enabled and not heading_disabled and sentence_buffer:
                        if any(rx.match(list_text) for rx in section_break_regexes):
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
                                token_regex,
                                token_break_chars,
                            )

                    sentence_buffer.append(part_seg)
                    if _is_sentence_end_with_exceptions(list_text, sentence_end_regexes, sentence_end_exceptions, next_text):
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
                            token_regex,
                            token_break_chars,
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
        token_regex,
        token_break_chars,
    )

    structured = {
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
    return add_group_ids(structured, cfg)


if __name__ == "__main__":
    import json
    INPUT_PATH = "/Users/cbg/github/law-doc-poc/data/normalization/20260118_1305/01_Cleansed/저작권법_법률__제20841호__20250926__pdf_results.json"
    OUTPUT_PATH = "/Users/cbg/github/law-doc-poc/data/normalization/20260118_1305/02_Structured/저작권법_법률__제20841호__20250926__pdf_structured.json"

    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        seg_json = json.load(f)

    if seg_json.get("format") != "PDF":
        raise SystemExit(f"Unsupported format: {seg_json.get('format')}")

    structured = structure_pdf(seg_json)

    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(structured, f, ensure_ascii=False, indent=2)

    print(f"[OK] Structured output saved: {OUTPUT_PATH}")
