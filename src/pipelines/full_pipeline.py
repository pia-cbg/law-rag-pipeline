"""
full_pipeline.py

문서 전처리 파이프라인의 전체 과정 스켈레톤입니다.

- Phase 1: 딥파싱 (Parsing)
    Pre processing 단계에서 필터링 된 RAW 데이터를 파싱합니다.
- Phase 2: 세그멘테이션 (Segmentation)
    Phase 1 단계에서 정제된 데이터를 세그멘테이션합니다.
- Phase 3: 노멀라이제이션 (Normalization) (구현 중)
    Phase 2 단계에서 세그멘테이션된 데이터를 정규화합니다
- Phase 4: RAG Preparation (미구현)
    Phase 3 단계에서 정규화된 데이터를 RAG 모델 및 벡터 데이터베이스/임베딩/검색 시스템에 맞게 chunking, 필터링, 임베딩 등 수행하여 최적화합니다.

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
# from src.pipelines.normalization_folder import normalize_folder  # (구현 예정)
# Phase 4 
# from src.pipelines.rag_preparation_folder import rag_folder # (구현 예정)

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
    os.makedirs(normalization_dir, exist_ok=True)
    files = [f for f in os.listdir(segmentation_dir) if f.endswith("_results.json")]
    for fname in files:
        inpath = os.path.join(segmentation_dir, fname)
        with open(inpath, "r", encoding="utf-8") as fin:
            seg = json.load(fin)
        # --- normalization 함수 자리 ---
        norm = {"filename": seg.get("filename"), "segments_normalized": seg.get("segments", [])}  # placeholder
        outpath = os.path.join(normalization_dir, fname)
        with open(outpath, "w", encoding="utf-8") as fout:
            json.dump(norm, fout, ensure_ascii=False, indent=2)

def main():
    session_dir = datetime.now().strftime("%Y%m%d_%H%M")
    parsed_raw_dir = os.path.join("data/parsed_raw", session_dir)
    segmentation_dir = os.path.join("data/segmentation", session_dir)
    normalization_dir = os.path.join("data/normalization", session_dir)

    print(f"[PHASE 1] Parsing: {RAW_CLEAN_DIR} → {parsed_raw_dir}")
    phase1_parsing(RAW_CLEAN_DIR, parsed_raw_dir)

    print(f"[PHASE 2] Segmentation: {parsed_raw_dir} → {segmentation_dir}")
    phase2_segmentation(parsed_raw_dir, segmentation_dir)

    print(f"[PHASE 3] Normalization: {segmentation_dir} → {normalization_dir}")
    phase3_normalization(segmentation_dir, normalization_dir)

    print(f"[DONE] 세션: {session_dir}")
    print(f"[INFO] Normalized output: {normalization_dir}")

if __name__ == "__main__":
    main()