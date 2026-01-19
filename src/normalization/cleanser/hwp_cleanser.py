import yaml
import re
from pathlib import Path
import os 
import json

# 외부 의존성
from src.normalization.cleanser.generic import generic_cleanser
import src.normalization.cleanser.rules.rules_catalog as rule_cat

# 규칙 경로 설정
RULES_PATH = Path(__file__).parent / "rules"

# 1. 포맷별 전용 룰 상수 정의
RULE_FILE_V5 = rule_cat.HWP_V5_DEFAULT      # "hwp_v5_default"
RULE_FILE_OWXML = rule_cat.HWP_OWPML_XML    # "hwp_owpml_xml"

def load_rules(rule_file):
    """
    1. 파일이 없으면 빈 규칙 반환
    2. 파일이 있어도 내용이 비어있으면(None) 빈 규칙 반환
    3. 정상적인 경우에만 데이터 반환
    """
    # 기본 규칙 뼈대
    default_rules = {"replace": [], "regex": []}
    
    if not rule_file:
        return default_rules
        
    rule_path = RULES_PATH / f"{rule_file}.yaml"
    
    # 1. 파일 존재 여부 체크
    if not rule_path.exists():
        return default_rules
        
    try:
        with open(rule_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            # 2. yaml.safe_load는 파일이 비어있으면 None을 반환함
            # 유효한 데이터(dict)면 데이터를 쓰고, 아니면 기본 뼈대 반환
            if isinstance(data, dict):
                return data
            else:
                return default_rules
    except Exception:
        # 파일이 깨졌거나 읽기 권한이 없는 등 예외 발생 시 안전하게 패스
        return default_rules

def hwp_cleanser(text, hwp_format):
    """
    [핵심 알고리즘]
    1. hwp_format 필드를 엄격하게 체크하여 타겟 룰을 결정한다.
    2. HWP 계열이 아예 아니라면(예: PDF, DOCX) 즉시 원본을 반환(Pass)한다.
    3. HWP라면 로드된 YAML 룰에 따라 텍스트를 정제한다.
    """
    if not text:
        return ""

    # [가드 로직] 아예 HWP가 아닌 포맷(PDF, DOCX 등)은 정제 절차를 타지 않음
    # 사용자님의 스키마에 따라 'format' 필드 값을 검사
    if hwp_format not in ["HWP_V5_BINARY", "HWP_OWPML_XML"]:
        return text

    # [단계 1 & 2] 포맷에 따른 룰 결정 (사용자님의 설계 반영)
    if hwp_format == "HWP_V5_BINARY":
        target_rule = RULE_FILE_V5
    elif hwp_format == "HWP_OWPML_XML":
        target_rule = RULE_FILE_OWXML
    else:
        # 그 외의 HWP 관련 케이스는 기본 V5 룰 적용
        target_rule = RULE_FILE_V5

    # 룰 로드
    rules = load_rules(target_rule)

    # [단계 3] 실제 정제 수행
    text = generic_cleanser(text)

    # Replace 규칙
    for sub_rule in rules.get("replace", []):
        src, tgt = sub_rule.get("from"), sub_rule.get("to")
        if src is not None and tgt is not None:
            text = text.replace(src, tgt)

    # Regex 규칙
    for reg_rule in rules.get("regex", []):
        pat, rep = reg_rule.get("pattern"), reg_rule.get("replace")
        if pat and rep is not None:
            text = re.sub(pat, rep, text)

    return text

if __name__ == "__main__":
    # --- 실험용 단독 실행부 ---
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

        # 2. HWP 계열인지 엄격히 판별
        is_hwp = fmt in ["HWP_V5_BINARY", "HWP_OWPML_XML"]

        if not is_hwp:
            # [CASE 1] 내 담당이 아님 -> 아무 작업도 하지 않고 건너뜀(Continue)
            print(f"[SKIP] {fname} (Format: {fmt}) - HWP 전용 정제 대상이 아니므로 파일 생성 안 함")
            continue 
        else:
            # [CASE 2] 내 담당 (HWP 계열)
            print(f"[PROCESS] {fname} (Format: {fmt})")
            for seg in data.get("segments", []):
                if "text" in seg and isinstance(seg["text"], str):
                    # 정제 수행
                    seg["text"] = hwp_cleanser(seg["text"], fmt)

            # 3. 결과 저장 (HWP인 경우에만 저장 수행)
            with open(fout_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"   ㄴ [OK] 정제 완료 및 저장: {fout_path}")
            print("-" * 50)