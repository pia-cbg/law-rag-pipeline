"""
base.py

- 지원되는 파일 유형별 파싱 엔진 자동 호출
- 입력: 파일경로
- 출력: 파서별 결과(raw text 또는 list)
- 실패·미지원시 로깅 및 None/빈값 반환
"""

import os

# 실제 파서 import (상대경로일 경우 경로 맞추세요)
from src.parsing.pdf_parser import parse_pdf
from src.parsing.docx_parser import parse_docx
from src.parsing.hwp_parser import parse_hwp

PARSERS = {
    '.pdf' : parse_pdf,
    '.docx': parse_docx,
    '.hwp' : parse_hwp,
    '.hwpx': parse_hwp
}

def parse_file(file_path):
    """
    파일 확장자에 따라 적절한 파서 호출. 
    지원하지 않는 확장자는 None 반환.
    """
    ext = os.path.splitext(file_path)[1].lower()
    parser = PARSERS.get(ext)
    if parser is None:
        print(f"[UNSUPPORTED] {file_path}")
        return None
    try:
        return parser(file_path)
    except Exception as e:
        print(f"[PARSING ERROR] {file_path}: {e}")
        return None

def guess_type(file_path):
    "확장자 및 내용 기반 유형 자동 판별 (option)"
    ext = os.path.splitext(file_path)[1].lower()
    if ext in PARSERS:
        return ext.replace('.', '')
    # (필요시 hwp/hwpx 내부 바이너리 검사 등 고도화)
    return 'unknown'

# if __name__ == "__main__":
#     import sys
#     if len(sys.argv) < 2:
#         print("Usage: python base.py <file>")
#         exit(1)
#     fp = sys.argv[1]
#     result = parse_file(fp)
#     if result:
#         if isinstance(result, list):
#             # 리스트형(페이지/단락 등)인 경우 일부만 미리보기
#             print(result[:2])
#         else:
#             print(result[:500])
#     else:
#         print("No parse result.")