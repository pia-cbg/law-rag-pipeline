"""
full_pipeline.py

문서 전처리 파이프라인의 전체 과정 스켈레톤입니다.

- Phase 1: 딥파싱 (Parsing)
    Pre processing 단계에서 필터링 된 RAW 데이터를 파싱합니다.
- Phase 2: 세그멘테이션 (Segmentation)
    Phase 1 단계에서 정제된 데이터를 세그멘테이션합니다.
- Phase 3: 노멀라이제이션 (Normalization) (구현 중)
    Phase 2 단계에서 세그멘테이션된 데이터를 정규화하여 RAG에 들어갈 수 있게 포맷팅 합니다.

사용 예시:
    1. data/preprocess/raw_clean/ 폴더의 문서 파일을 입력으로 사용
    2. 각 단계별 세션 폴더를 만들어 결과를 저장
"""
import os
import json
from datetime import datetime

# Phase 1
from src.pipelines.deep_parse_folder import parse_folder
# Phase 2
from src.pipelines.segmentation_folder import segment_folder
# Phase 3
from src.pipelines.normalize_folder import normalize_folder  # (구현 예정)


# 필터링된 RAW 데이터
RAW_CLEAN_DIR = "data/preprocess/raw_clean"

def phase1_parsing(raw_clean_dir, parsed_raw_dir):
    os.makedirs(parsed_raw_dir, exist_ok=True)
    files = [f for f in os.listdir(raw_clean_dir) if os.path.isfile(os.path.join(raw_clean_dir, f))]
    for fname in files:
        ext = os.path.splitext(fname)[1].lower()
        inpath = os.path.join(raw_clean_dir, fname)
        result = parse_folder(inpath)
        name_wo_ext = os.path.splitext(fname)[0]
        outname = f"{name_wo_ext}_{ext[1:]}_results.json"
        outpath = os.path.join(parsed_raw_dir, outname)
        with open(outpath, "w", encoding="utf-8") as fout:
            json.dump(result, fout, ensure_ascii=False, indent=2)

def phase2_segmentation(parsed_raw_dir, segmentation_dir):
    os.makedirs(segmentation_dir, exist_ok=True)
    files = [f for f in os.listdir(parsed_raw_dir) if f.endswith("_results.json")]
    for fname in files:
        inpath = os.path.join(parsed_raw_dir, fname)
        with open(inpath, "r", encoding="utf-8") as fin:
            parsed = json.load(fin)
        ext = parsed.get("extension", None)
        seg = segment_folder(parsed, filetype=ext[1:] if ext else None)
        outpath = os.path.join(segmentation_dir, fname)
        with open(outpath, "w", encoding="utf-8") as fout:
            json.dump(seg, fout, ensure_ascii=False, indent=2)

def phase3_normalization(segmentation_dir, normalization_dir):
    """
    Phase 3: 세그멘테이션된 데이터를 정규화합니다.
    전문 모듈인 normalization_folder에 위임하여 처리합니다.
    """
    print(f"[*] Starting Phase 3 Normalization...")
    print(f"[*] Input: {segmentation_dir}")
    print(f"[*] Output: {normalization_dir}")
    
    # 이 한 줄로 Cleaning -> Structuring -> RAG Formatting이 모두 실행됩니다.
    processed_count = normalize_folder(segmentation_dir, normalization_dir)
    
    print(f"[+] Phase 3 Complete. (Processed {processed_count} files)")

def main():
    # 1. 세션 식별자 생성 (시점 기록)
    session_dir = datetime.now().strftime("%Y%m%d_%H%M")
    
    # 2. 각 단계별 결과 저장 경로 설정
    parsed_raw_dir = os.path.join("data/parsed_raw", session_dir)
    segmentation_dir = os.path.join("data/segmentation", session_dir)
    normalization_dir = os.path.join("data/normalization", session_dir)

    print(f"\n" + "="*60)
    print(f"🚀 Law-Doc-POC Full Pipeline Start (Session: {session_dir})")
    print("="*60)

    # [PHASE 1] Deep Parsing (Raw -> JSON)
    print(f"\n[PHASE 1] Parsing: {RAW_CLEAN_DIR} → {parsed_raw_dir}")
    phase1_parsing(RAW_CLEAN_DIR, parsed_raw_dir)

    # [PHASE 2] Segmentation (JSON -> Segments)
    print(f"\n[PHASE 2] Segmentation: {parsed_raw_dir} → {segmentation_dir}")
    phase2_segmentation(parsed_raw_dir, segmentation_dir)

    # [PHASE 3] Normalization (Clean/Struct/Format -> RAG Ready)
    print(f"\n[PHASE 3] Normalization: {segmentation_dir} → {normalization_dir}")
    phase3_normalization(segmentation_dir, normalization_dir)

    print("\n" + "="*60)
    print(f"✅ [DONE] Pipeline finished. Session: {session_dir}")
    print(f"📂 Final Result: {normalization_dir}")
    print("="*60)

if __name__ == "__main__":
    main()