"""
base.py

- 역할: Segmentation에서 넘어온 결과물을
        확장자별 normalization 함수로 표준 구조로 변환
- 입력: segmentation json (파싱된 파일의 메타 포함)
- 출력: 완전 통일된 normalized json (모든 포맷에 공통)
"""

def normalize_docx(seg):
    # ... (docx normalization 구현)
    pass  # 위 예시처럼

def normalize_pdf(seg):
    # ... (pdf normalization 구현)
    pass

def normalize_hwp(seg):
    # ... (hwp normalization 구현)
    pass

NORMALIZERS = {
    ".docx": normalize_docx,
    ".pdf": normalize_pdf,
    ".hwp": normalize_hwp,
    ".hwpx": normalize_hwp
}

def normalize_file(seg_json):
    """
    segmentation json의 extension 값을 기준으로 해당 normalizer 호출
    """
    ext = seg_json.get("extension", "").lower()
    norm_fn = NORMALIZERS.get(ext)
    if not norm_fn:
        print(f"[UNSUPPORTED_EXTENSION] {ext}")
        return None
    try:
        return norm_fn(seg_json)
    except Exception as e:
        print(f"[NORMALIZATION ERROR] {e}")
        return None