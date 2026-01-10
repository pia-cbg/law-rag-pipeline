'''
- Phase 1: 딥파싱 (Parsing)
    Pre processing 단계에서 필터링 된 RAW 데이터를 파싱합니다.
'''

import os
import json
from datetime import datetime
from src.parsing.base import parse_file

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INPUT_DIR = os.path.join(PROJECT_ROOT, "data", "preprocess","raw_clean")

# 세션 폴더명: YYYYMMDD_HHMM
session_dir = datetime.now().strftime("%Y%m%d_%H%M")
PARSED_RAW_DIR = os.path.join(PROJECT_ROOT, "data", "parsed_raw", session_dir)

# 주요 포맷별(혹은 필요시 확장) 구분용 필드
MAIN_FIELDS = {
    ".pdf": "pages",
    ".docx": "paragraphs",
    ".hwp": "paragraphs",
    ".hwpx": "paragraphs",
    # 필요시 더 추가 가능
}

def is_success_result(ext, result):
    """
    파싱 성공 여부 판단.
    - 주요 컨텐츠 필드가 있거나 비어있지 않아야 True
    """
    main_key = MAIN_FIELDS.get(ext)
    return (
        (isinstance(result, str) and result.strip())
        or (isinstance(result, list) and len(result) > 0)
        or (
            isinstance(result, dict)
            and main_key
            and main_key in result
            and isinstance(result[main_key], list)
            and len(result[main_key]) > 0
        )
    )

def sanitize_filename(name):
    """
    원본 파일명에서 OS/FS에 안전한 파일명 생성
    (필요 시 구현, 여기서는 간단 예시)
    """
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in name)

def parse_folder(input_dir, out_dir):
    files = [
        f for f in os.listdir(input_dir)
        if os.path.isfile(os.path.join(input_dir, f)) and not f.startswith('.')
    ]
    n_success, n_fail = 0, 0
    failed_files = []

    os.makedirs(out_dir, exist_ok=True)
    for fname in files:
        fpath = os.path.join(input_dir, fname)
        ext = os.path.splitext(fname)[1].lower()
        name_wo_ext = os.path.splitext(fname)[0]
        safe_name = sanitize_filename(name_wo_ext)
        result = parse_file(fpath)
        is_success = is_success_result(ext, result)

        rec_base = {
            "filename": fname,
            "extension": ext,
            "content": result if is_success else "",
            "parsed_at": datetime.now().isoformat()
        }

        # [파일명]_[확장자]_results.json 형태로 저장 (. 제외)
        result_filename = f"{safe_name}_{ext[1:]}_results.json"
        result_path = os.path.join(out_dir, result_filename)
        with open(result_path, "w", encoding="utf-8") as outf:
            json.dump(rec_base, outf, ensure_ascii=False, indent=2)

        if is_success:
            n_success += 1
        else:
            n_fail += 1
            failed_files.append(fname)

    print(f"[DONE] 성공 : {n_success}, 실패 : {n_fail}, 총 : {len(files)}개")
    print(f"[OUTPUT DIR]: {out_dir}")
    if failed_files:
        print("[실패 파일 목록]:")
        for ff in failed_files:
            print("  -", ff)

if __name__ == "__main__":
    parse_folder(INPUT_DIR, PARSED_RAW_DIR)