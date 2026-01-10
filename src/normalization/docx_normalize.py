"""
docx_normalize.py

- 목적: DOCX 세그멘테이션 결과를 downstream/RAG/QA에서 쓸 수 있는
        표준 normalized JSON 스키마로 변환
- 입력: segmentation json (dict)
- 출력: normalized json (dict)
"""

import os
import json
from uuid import uuid4

def normalize_docx(segmentation_json):
    """
    DOCX 세그멘테이션 결과를 표준 normalized 구조로 변환
    """
    normalized = {
        "doc_id": segmentation_json.get("filename", ""),
        "source": "docx",
        "segments": []
    }
    segs = segmentation_json.get("segments", [])
    for idx, seg in enumerate(segs):
        normalized["segments"].append({
            "id": str(uuid4()),
            "order": idx + 1,
            "text": seg.get("text", ""),
            "meta": {
                "style": seg.get("style", ""),
                # 필요한 추가 메타필드는 여기에
            }
        })
    return normalized

if __name__ == "__main__":
    # 절대경로 실험용 입력/출력 파일
    input_path  = "/Users/cbg/github/law-doc-poc/data/segmentation/20260109_1438/샘플_해수욕장_샤워실_대여계약서__docx_results.json"
    output_path = "/Users/cbg/github/law-doc-poc/data/normalization/20260109_1438/샘플_해수욕장_샤워실_대여계약서__docx_results.json"

    # 입력 데이터 로딩
    with open(input_path, "r", encoding="utf-8") as f:
        seg_json = json.load(f)

    # 노멀라이제이션
    norm_json = normalize_docx(seg_json)

    # 출력 폴더가 없으면 생성
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    # 결과 저장
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(norm_json, f, ensure_ascii=False, indent=2)

    print(f"[OK] normalized 파일을 저장했습니다: {output_path}")