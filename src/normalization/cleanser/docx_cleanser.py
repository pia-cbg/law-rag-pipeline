"""
src/normalization/cleanser/docx_cleanser.py

- 역할: generic_cleanser 이후 DOCX 치환/정규화 규칙을 적용
- 규칙명 상수는 rules_catalog.py에서 import (자동완성)
- 실제 규칙은 rules/ 밑 YAML(docx_default.yaml(버전별))로 관리
- (이 버전은 아래 지정된 input/output 절대경로를 직접 파일로 처리)
"""

import yaml
import re
import os
import json
from pathlib import Path

# 외부 의존성
from src.normalization.cleanser.generic import generic_cleanser
import src.normalization.cleanser.rules.rules_catalog as rule_cat

# 정책별 YAML 경로
RULES_PATH = Path(__file__).parent / "rules"
DEFAULT_RULE_NAME = rule_cat.DOCX_DEFAULT # "docx_default"

def load_rules(rule_file):
    """YAML 파일을 로드하되, 없거나 비어있으면 빈 딕셔너리를 반환하여 에러를 방지합니다."""
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

def docx_cleanser(text, doc_format):
    """
    [핵심 알고리즘: DOCX 자가 판별 및 정제]
    1. format이 'DOCX'인지 확인한다.
    2. 아니면 텍스트를 건드리지 않고 그대로 반환한다 (Safe Pass).
    3. 'DOCX'라면 전용 YAML 룰을 로드하여 정제를 수행한다.
    """
    if not text:
        return ""

    # [가드 로직] DOCX 포맷이 아니면 즉시 원본 반환
    if doc_format != "DOCX":
        return text

    # 규칙 로드
    rules = load_rules(DEFAULT_RULE_NAME)
    
    # 기본 정제
    text = generic_cleanser(text)

    # 1. Plain Replace
    for sub_rule in rules.get("replace", []):
        src, tgt = sub_rule.get("from"), sub_rule.get("to")
        if src and tgt:
            text = text.replace(src, tgt)

    # 2. Regex 정규화
    for reg_rule in rules.get("regex", []):
        pat, rep = reg_rule.get("pattern"), reg_rule.get("replace")
        if pat and rep is not None:
            text = re.sub(pat, rep, text)

    return text

if __name__ == "__main__":
    # --- [특정 포맷 전용 단독 실험용] ---
    INPUT_DIR = "/Users/cbg/github/law-doc-poc/data/segmentation/20260112_0442"
    OUTPUT_DIR = "/Users/cbg/github/law-doc-poc/data/normalization/test_2"
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 이 클리너가 처리할 타겟 설정 (파일마다 다르게 설정 가능)
    # docx_cleanser라면 ["DOCX"], hwp_cleanser라면 ["HWP_V5_BINARY", "HWP_OWPML_XML"]
    TARGET_FORMATS = ["DOCX"] 

    input_files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(".json")]
    
    for fname in input_files:
        fin_path = os.path.join(INPUT_DIR, fname)
        fout_path = os.path.join(OUTPUT_DIR, fname)

        with open(fin_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        fmt = data.get("format", "UNKNOWN")

        # [핵심 변경부] 타겟 포맷이 아니면 아예 프로세스를 건너뜁니다.
        if fmt not in TARGET_FORMATS:
            print(f"[SKIP] {fname} (Format: {fmt}) - 타겟 포맷이 아니므로 제외합니다.")
            continue 

        # --- 여기서부터는 타겟 포맷인 경우에만 실행됨 ---
        print(f"[PROCESS] {fname} (Format: {fmt}) - 정제 시작")
        
        for seg in data.get("segments", []):
            if "text" in seg and isinstance(seg["text"], str):
                # 각 포맷에 맞는 클리너 호출
                seg["text"] = docx_cleanser(seg["text"], fmt)

        # 결과 저장
        with open(fout_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        print(f"   ㄴ [OK] 정제 완료: {fout_path}")