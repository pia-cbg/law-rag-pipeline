import os
import json

def segment_hwp_parsed(parsed, degraded_para_threshold=2):
    segments = []
    degraded_segments = []

    filename = parsed.get("filename")
    content = parsed.get("content", {})
    hwp_format = content.get("format")
    paragraphs = content.get("paragraphs", [])

    if hwp_format == "HWP_OWPML_XML":
        # 기존 OWPML (XML) 처리방식: tokens 정보 계승 (변경 없음)
        for idx, para in enumerate(paragraphs):
            text = para.get("text", "")
            tokens = para.get("tokens", [])
            text_stripped = text.strip() if isinstance(text, str) else ""
            degraded = len(text_stripped) < degraded_para_threshold
            reason = "too_short_or_empty" if degraded else None

            segment_info = {
                "segment_id": f"{filename}-para{idx:04d}",
                "filename": filename,
                "para_index": idx,
                "text": text_stripped,
                "tokens": tokens,
                "degraded": degraded,
                "reason": reason,
            }
            segments.append(segment_info)
            if degraded:
                degraded_segments.append(segment_info)

    elif hwp_format == "HWP_V5_BINARY":
        # v5바이너리: 각 paragraph['char_styles'] 구조를 그대로 계승
        for idx, para in enumerate(paragraphs):
            text = para.get("text", "")
            char_styles = para.get("char_styles", [])
            text_stripped = text.strip() if isinstance(text, str) else ""
            degraded = len(text_stripped) < degraded_para_threshold
            reason = "too_short_or_empty" if degraded else None

            segment_info = {
                "segment_id": f"{filename}-para{idx:04d}",
                "filename": filename,
                "para_index": idx,
                "text": text_stripped,
                "char_styles": char_styles,   # 이 부분 추가!
                "degraded": degraded,
                "reason": reason,
            }
            segments.append(segment_info)
            if degraded:
                degraded_segments.append(segment_info)

    else:
        # format 미구현 등 - 빈 값 반환
        pass

    return {
        "filename": filename,
        "format": hwp_format,
        "segments": segments,
        "degraded_segments": degraded_segments
    }
    
    
    
    
# import os
# import json

# def segment_hwp_parsed(parsed, degraded_para_threshold=2):
#     segments = []
#     degraded_segments = []

#     # 파싱 결과에서 메타 정보 추출
#     filename = parsed.get("filename")
#     hwp_format = parsed.get("hwp_format")
#     # 파싱 함수에서 result.update(out)로 합쳤으므로 루트에서 바로 접근
#     paragraphs = parsed.get("paragraphs", [])

#     # 1. HWP_OWPML_XML (XML 기반: tokens 구조)
#     if hwp_format == "HWP_OWPML_XML":
#         for idx, para in enumerate(paragraphs):
#             text = para.get("text", "")
#             tokens = para.get("tokens", []) # 텍스트 조각 + 스타일(폰트명 포함)
            
#             text_stripped = text.strip() if isinstance(text, str) else ""
#             degraded = len(text_stripped) < degraded_para_threshold
#             reason = "too_short_or_empty" if degraded else None

#             segment_info = {
#                 "segment_id": f"{filename}-para{idx:04d}",
#                 "filename": filename,
#                 "para_index": idx,
#                 "text": text_stripped,
#                 "tokens": tokens,  # XML 특유의 구역 단위 스타일 정보
#                 "degraded": degraded,
#                 "reason": reason,
#                 "hwp_format": hwp_format
#             }
#             segments.append(segment_info)
#             if degraded:
#                 degraded_segments.append(segment_info)

#     # 2. HWP_V5_BINARY (바이너리 기반: char_styles 구조)
#     elif hwp_format == "HWP_V5_BINARY":
#         for idx, para in enumerate(paragraphs):
#             text = para.get("text", "")
#             # 바이너리 특유의 오프셋(at) 기반 스타일 정보
#             char_styles = para.get("char_styles", []) 
            
#             text_stripped = text.strip() if isinstance(text, str) else ""
#             degraded = len(text_stripped) < degraded_para_threshold
#             reason = "too_short_or_empty" if degraded else None

#             segment_info = {
#                 "segment_id": f"{filename}-para{idx:04d}",
#                 "filename": filename,
#                 "para_index": idx,
#                 "text": text_stripped,
#                 "char_styles": char_styles, # 오프셋 단위 스타일 정보
#                 "degraded": degraded,
#                 "reason": reason,
#                 "hwp_format": hwp_format
#             }
#             segments.append(segment_info)
#             if degraded:
#                 degraded_segments.append(segment_info)

#     return {
#         "filename": filename,
#         "hwp_format": hwp_format,
#         "segments": segments,
#         "degraded_segments": degraded_segments
#     }
    
# # main 실험용
# def find_parsed_files(input_dir):
#     files = []
#     for fname in sorted(os.listdir(input_dir)):
#         if fname.endswith("_results.json"):
#             files.append(os.path.join(input_dir, fname))
#     return files

# def save_json(obj, out_path):
#     os.makedirs(os.path.dirname(out_path), exist_ok=True)
#     with open(out_path, "w", encoding="utf-8") as f:
#         json.dump(obj, f, ensure_ascii=False, indent=2)

# def get_segmentation_output_path(parsed_path, input_root, output_root):
#     input_root = os.path.abspath(input_root)
#     output_root = os.path.abspath(output_root)
#     relpath = os.path.relpath(parsed_path, input_root)
#     out_path = os.path.join(output_root, relpath)
#     out_dir = os.path.dirname(out_path)
#     os.makedirs(out_dir, exist_ok=True)
#     return out_path

# if __name__ == "__main__":
#     # 실험용
#     INPUT_FOLDER = "/Users/cbg/github/law-doc-poc/data/parsed_raw/20260109_1438"
#     OUTPUT_FOLDER = "/Users/cbg/github/law-doc-poc/data/segmentation/20260109_1438"

#     files = find_parsed_files(INPUT_FOLDER)
#     print(f"[INFO] 입력 파일 수: {len(files)}")
#     for fpath in files:
#         with open(fpath, "r", encoding="utf-8") as f:
#             parsed = json.load(f)
#         ext = parsed.get("extension", "").lower()
#         if ext != ".hwp":
#             continue
#         seg_result = segment_hwp_parsed(parsed)
#         out_path = get_segmentation_output_path(fpath, INPUT_FOLDER, OUTPUT_FOLDER)
#         save_json(seg_result, out_path)
#         print(f"[OK] {os.path.basename(fpath)} ({len(seg_result['segments'])} segments) -> {out_path}")