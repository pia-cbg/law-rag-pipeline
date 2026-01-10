'''
- Phase 2: 세그멘테이션 (Segmentation)
    Phase 1 단계에서 정제된 데이터를 세그멘테이션합니다.
INPUT_FOLDER 와 OUTPUT_FOLDER 명을 세션에 맞게 수정해주세요.

'''
import os
import json
from glob import glob
from typing import List
from src.segmentation.base import segment_document

'''
data/parsed_raw 파일명 규칙
[파일명]_[SUPPORTED_TYPES]_result.json
필요시 확장자 추가
'''
SUPPORTED_TYPES = {'pdf', 'hwp', 'docx', 'hwpx'}

'''
INPUT_FOLDER : 원시데이터 저장된 폴더
OUTPUT_FOLDER : 세그멘테이션 저장될 폴더
'''
INPUT_FOLDER = "data/parsed_raw/20260109_1438"
OUTPUT_FOLDER = "data/segmentation/20260109_1438"

def find_parsed_files(input_dir: str) -> List[str]:
    search_path = os.path.abspath(input_dir)
    jsons = glob(os.path.join(search_path, "*_*_results.json"))
    return sorted(set(jsons))

def mkdir_p(path: str):
    os.makedirs(path, exist_ok=True)

def get_segmentation_output_path(parsed_path: str, input_root: str, output_root: str) -> str:
    input_root = os.path.abspath(input_root)
    output_root = os.path.abspath(output_root)
    relpath = os.path.relpath(parsed_path, input_root)
    out_path = os.path.join(output_root, relpath)
    out_dir = os.path.dirname(out_path)
    mkdir_p(out_dir)
    return out_path

def infer_filetype_from_filename(filename: str) -> str:
    base = os.path.basename(filename).lower()
    if base.endswith('_results.json'):
        parts = base.split('_')
        if len(parts) >= 3:
            return parts[-2]
    raise ValueError(f"파일명 패턴이 맞지 않습니다: {filename}")

def segment_folder(input_root: str, output_root: str):
    input_root = os.path.abspath(input_root)
    output_root = os.path.abspath(output_root)
    print(f"[INFO] 입력폴더: {input_root}")
    print(f"[INFO] 출력폴더: {output_root}")

    file_paths = find_parsed_files(input_root)
    print(f"[INFO] 대상 파일 개수: {len(file_paths)}")

    if not file_paths:
        print(f"[WARNING] 대상 파일 없음: {input_root}")
        return

    for file_path in file_paths:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        doc_list = data if isinstance(data, list) else [data]
        filetype = infer_filetype_from_filename(file_path)

        segmented_all = []
        if filetype not in SUPPORTED_TYPES:
            error_message = f"지원하지 않는 filetype: {filetype}"
            for doc in doc_list:
                err_info = {
                    "filename": doc.get('filename'),
                    "error": error_message
                }
                segmented_all.append(err_info)
            print(f"[FAIL] {os.path.basename(file_path)}: {error_message}")
        else:
            for doc in doc_list:
                try:
                    seg_result = segment_document(doc, filetype=filetype)
                    segmented_all.append(seg_result)
                    print(f"[OK] {doc.get('filename', file_path)} ({len(seg_result.get('segments', []))} segments)")
                except Exception as e:
                    err_info = {
                        "filename": doc.get('filename', file_path),
                        "error": str(e)
                    }
                    segmented_all.append(err_info)
                    print(f"[FAIL] {doc.get('filename', file_path)}: {str(e)}")

        out_path = get_segmentation_output_path(file_path, input_root, output_root)
        with open(out_path, "w", encoding="utf-8") as wf:
            if len(segmented_all) == 1:
                json.dump(segmented_all[0], wf, ensure_ascii=False, indent=2)
            else:
                json.dump(segmented_all, wf, ensure_ascii=False, indent=2)
        print(f"[SAVE] {out_path}")

if __name__ == "__main__":
    segment_folder(INPUT_FOLDER, OUTPUT_FOLDER)