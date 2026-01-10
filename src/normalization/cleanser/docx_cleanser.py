"""
docx_cleanser.py

- 역할: generic_cleanser 이후 DOCX 특화 치환/정제 규칙을 적용
- 룰은 YAML 파일(룰 정책 논리 이름만, .yaml은 내부에서 붙임)로 관리
- rules_catalog.py의 상수를 네임스페이스 import하여 자동완성 지원
"""

import yaml
import re
from pathlib import Path
from src.normalization.cleanser.generic import generic_cleanser
import src.normalization.cleanser.rules.rules_catalog as rule_cat 

RULES_PATH = Path(__file__).parent / "rules"

# 정책에 따라 변경
RULE_FILE = rule_cat.DOCX_DEFAULT

def load_rules(rule_file=RULE_FILE):
    rule_path = RULES_PATH / f"{rule_file}.yaml"
    if not rule_path.exists():
        raise FileNotFoundError(f"Rule file not found: {rule_path}")
    with open(rule_path, encoding="utf-8") as f:
        return yaml.safe_load(f)

def docx_cleanser(text, rule_file=RULE_FILE):
    rules = load_rules(rule_file)
    text = generic_cleanser(text)
    for sub_rule in rules.get("replace", []):
        src = sub_rule.get("from")
        tgt = sub_rule.get("to")
        if src is not None and tgt is not None:
            text = text.replace(src, tgt)
    for reg_rule in rules.get("regex", []):
        pat = reg_rule.get("pattern")
        rep = reg_rule.get("replace")
        if pat and rep is not None:
            text = re.sub(pat, rep, text)
    return text

if __name__ == "__main__":
    # 사용 예시: dot(.) 자동완성을 IDE에서 누릴 수 있음!
    test_str = "제 1 조【 목 적 】"
    print("cleansed (default):", docx_cleanser(test_str))  # 기본값(DOCX_DEFAULT)로 동작
    print("cleansed (lotte):", docx_cleanser(test_str, rule_file=rule_cat.DOCX_LOTTE_V1))
    print("cleansed (court):", docx_cleanser(test_str, rule_file=rule_cat.DOCX_COURT_2024))