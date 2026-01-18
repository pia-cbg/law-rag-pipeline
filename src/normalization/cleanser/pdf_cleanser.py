import yaml
import re
import os
import json
from pathlib import Path

# 외부 의존성
from src.normalization.cleanser.generic import generic_cleanser
import src.normalization.cleanser.rules.rules_catalog as rule_cat

# 규칙 경로 설정
RULES_PATH = Path(__file__).parent / "rules"
# PDF 전용 규칙 상수 (rules_catalog.py에 정의되어 있다고 가정)
RULE_FILE_PDF = rule_cat.PDF_DEFAULT 

def load_rules(rule_file):
    """YAML 규칙을 로드하며, 예외 상황 발생 시 빈 규칙을 반환합니다."""
    default_rules = {"replace": [], "regex": []}
    if not rule_file:
        return default_rules
        
    rule_path = RULES_PATH / f"{rule_file}.yaml"
    if not rule_path.exists():
        return default_rules
        
    try:
        with open(rule_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else default_rules
    except Exception:
        return default_rules

def pdf_cleanser(text, doc_format):
    """
    [핵심 알고리즘: PDF 자가 판별 및 정제]
    1. doc_format이 'PDF'인지 확인한다.
    2. 아니면 텍스트를 건드리지 않고 그대로 반환한다 (Safe Pass).
    3. 'PDF'라면 전용 YAML 룰을 로드하여 정제를 수행한다.
    """
    if not text:
        return ""

    # [가드 로직] PDF 포맷이 아니면 즉시 원본 반환
    if doc_format != "PDF":
        return text

    # 규칙 로드
    rules = load_rules(RULE_FILE_PDF)
    
    # 기본 정제 (공통 잡음 제거)
    text = generic_cleanser(text)

    # 1. Plain Replace
    for sub_rule in rules.get("replace", []):
        src, tgt = sub_rule.get("from"), sub_rule.get("to")
        if src is not None and tgt is not None:
            text = text.replace(src, tgt)

    # 2. Regex 정규화 (PDF 특유의 줄바꿈/공백 처리 등)
    for reg_rule in rules.get("regex", []):
        pat, rep = reg_rule.get("pattern"), reg_rule.get("replace")
        if pat and rep is not None:
            text = re.sub(pat, rep, text)

    return text


def _channel_to_int(value):
    if value is None:
        return None
    if isinstance(value, bool):
        value = int(value)
    if isinstance(value, (int, float)):
        if 0 <= value <= 1:
            value = round(value * 255)
        else:
            value = round(value)
        return max(0, min(255, int(value)))
    return None


def _color_to_hex(color):
    if color is None:
        return None
    if isinstance(color, (list, tuple)):
        if len(color) == 1:
            r = g = b = _channel_to_int(color[0])
        elif len(color) >= 3:
            r = _channel_to_int(color[0])
            g = _channel_to_int(color[1])
            b = _channel_to_int(color[2])
        else:
            return None
    else:
        r = g = b = _channel_to_int(color)
    if r is None or g is None or b is None:
        return None
    return f"#{r:02X}{g:02X}{b:02X}"


def _normalize_segment_colors(seg):
    if "colors" not in seg:
        return
    colors = seg.get("colors")
    if isinstance(colors, list):
        seg["colors"] = [_color_to_hex(c) for c in colors]
    else:
        seg["colors"] = _color_to_hex(colors)

if __name__ == "__main__":
    # --- [PDF 단독 실험용 메인단] ---
    INPUT_DIR = "/Users/cbg/github/law-doc-poc/data/segmentation/20260112_0442"
    OUTPUT_DIR = "/Users/cbg/github/law-doc-poc/data/normalization/test_2"
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    input_files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(".json")]
    
    for fname in input_files:
        fin_path = os.path.join(INPUT_DIR, fname)
        fout_path = os.path.join(OUTPUT_DIR, fname)

        with open(fin_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 1. 포맷 정보를 가져옴
        fmt = data.get("format", "UNKNOWN")

        # 2. PDF 포맷인지 엄격히 판별
        is_pdf = (fmt == "PDF")

        if not is_pdf:
            # [CASE 1] 내 담당이 아님 -> test_2에 파일을 생성하지 않고 건너뜀
            print(f"[SKIP] {fname} (Format: {fmt}) - PDF 정제 대상이 아니므로 제외")
            continue 
        else:
            # [CASE 2] 내 담당 (PDF)
            print(f"[PROCESS] {fname} (Format: {fmt}) - 정제 시작")
            for seg in data.get("segments", []):
                if "text" in seg and isinstance(seg["text"], str):
                    # PDF 전용 정제 수행
                    seg["text"] = pdf_cleanser(seg["text"], fmt)
                _normalize_segment_colors(seg)

            # 3. 결과 저장 (PDF인 경우에만 저장 수행)
            with open(fout_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"   ㄴ [OK] 정제 완료 및 저장: {fout_path}")
            print("-" * 50)
