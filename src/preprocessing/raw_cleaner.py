'''
raw_cleaner.py

- 목적: 데이터 파이프라인의 첫 단계에서 data/raw 폴더의 모든 파일을 검증/클린징하여
        품질 기준을 통과한 파일만 data/preprocess/raw_clean/에 복사합니다.
        기준 미달(불량, 오염, 임시, 비타깃, 손상 등) 파일은 상세 사유별로 data/preprocess/failures/ 하위 폴더에 분리 보관합니다.

[예외 및 분류 종류]
    - extension   : 대상을 벗어난 파일 확장자 (jpg, exe 등)
    - hidden      : 숨김/임시/시스템 파일 (~$, .DS_Store 등)
    - size        : 너무 작거나 큰 파일
    - encoding    : .txt/.csv/.md 등에서 인코딩 불능/깨짐
    - filename    : 파일명 금지문자/OS불가/너무 긴 이름 등
    - signature   : 확장자와 파일 헤더 미일치(예: pdf/head 불일치)
    - corrupted   : 파일카피/복사실패 등 장애
    - empty       : 내용이 완전히 없음
    - 기타 필요한 정책(duplicate, policy, other) 등

- 적용: 반드시 이 스크립트로 raw 데이터를 먼저 처리한 뒤, 
        data/preprocess/raw_clean/ 하위 파일만 후속 파이프라인(parsing 등)에 사용할 것
- 실무 및 데이터 파이프라인 품질/안정성 확보에 최적화
'''

import os
import shutil

RAW_DIR = "data/raw"
RAW_CLEAN_DIR = "data/preprocess/raw_clean"
FAILURE_ROOT = "data/preprocess/failures"

TARGET_EXTENSIONS = {'.hwp', '.pdf', '.docx', '.hwpx', '.txt'}
ENCODING_CHECK_EXT = {'.txt', '.csv', '.md'}

def get_extension(fname):
    return os.path.splitext(fname)[1].lower()

def is_hidden_or_tmp(fname):
    return (
        fname.startswith('.') or
        fname.startswith('~$') or
        fname in {'.DS_Store', 'Thumbs.db'}
    )

def is_valid_extension(ext):
    return ext in TARGET_EXTENSIONS

def is_file_too_small_or_large(fpath, min_bytes=100, max_bytes=1024*1024*200):
    sz = os.path.getsize(fpath)
    return sz < min_bytes or sz > max_bytes

def is_filename_invalid(fname):
    BAD_CHARS = set('?*:/\\"<>|')
    return any(c in BAD_CHARS for c in fname) or len(fname) > 240

def is_encoding_failure(fpath, ext):
    if ext not in ENCODING_CHECK_EXT:
        return False
    try:
        with open(fpath, encoding='utf-8') as f:
            _ = f.read()
        return False
    except UnicodeDecodeError:
        return True

def is_signature_mismatch(fpath, ext):
    try:
        with open(fpath, 'rb') as f:
            sig = f.read(8)
        if ext == '.pdf' and not sig.startswith(b'%PDF'):
            return True
        if ext == '.hwp' and not (sig.startswith(b'\xd0\xcf\x11\xe0') or b'<?xml' in sig):
            return True
    except Exception:
        return True
    return False

def preprocess_raw_folder(raw_dir, raw_clean_dir, failure_root):
    os.makedirs(raw_clean_dir, exist_ok=True)
    failure_types = [
        "extension", "hidden", "size", "encoding", "filename",
        "signature", "duplicate", "corrupted", "empty", "policy", "other"
    ]
    for ft in failure_types:
        os.makedirs(os.path.join(failure_root, ft), exist_ok=True)

    # 실패 사유별 파일명 목록 dict
    failed = {ft: [] for ft in failure_types}
    n_clean = 0

    for fname in os.listdir(raw_dir):
        src = os.path.join(raw_dir, fname)
        if not os.path.isfile(src):
            continue
        ext = get_extension(fname)

        # 각 품질검사 작업 (우선순위대로 분기)
        if is_hidden_or_tmp(fname):
            shutil.copy2(src, os.path.join(failure_root, "hidden", fname))
            failed["hidden"].append(fname)
            continue
        if not is_valid_extension(ext):
            shutil.copy2(src, os.path.join(failure_root, "extension", fname))
            failed["extension"].append(fname)
            continue
        if is_filename_invalid(fname):
            shutil.copy2(src, os.path.join(failure_root, "filename", fname))
            failed["filename"].append(fname)
            continue
        if is_file_too_small_or_large(src):
            shutil.copy2(src, os.path.join(failure_root, "size", fname))
            failed["size"].append(fname)
            continue
        if is_encoding_failure(src, ext):
            shutil.copy2(src, os.path.join(failure_root, "encoding", fname))
            failed["encoding"].append(fname)
            continue
        if is_signature_mismatch(src, ext):
            shutil.copy2(src, os.path.join(failure_root, "signature", fname))
            failed["signature"].append(fname)
            continue
        if os.path.getsize(src) == 0:
            shutil.copy2(src, os.path.join(failure_root, "empty", fname))
            failed["empty"].append(fname)
            continue
        # 기타 정책(예: 중복, policy 등) 필요시 추가

        try:
            shutil.copy2(src, os.path.join(raw_clean_dir, fname))
            n_clean += 1
        except Exception as e:
            shutil.copy2(src, os.path.join(failure_root, "corrupted", fname))
            failed["corrupted"].append(fname)

    print(f"[DONE] Preprocessing phase0 (raw_cleaner) complete.")
    print(f"[CLEAN] {n_clean} files moved to raw_clean/")
    n_fail = sum(len(lst) for lst in failed.values())
    print(f"[FAILURES] 총 실패 {n_fail}개")
    for k, v in failed.items():
        if v:
            print(f"  - {k}: {len(v)}개")
            for fname in v:
                print(f"      • {fname}")

if __name__ == "__main__":
    preprocess_raw_folder(RAW_DIR, RAW_CLEAN_DIR, FAILURE_ROOT)