import json
import os

def segment_docx_parsed(parsed_docx, filename=None, degraded_para_threshold=2):
    segments = []
    degraded_segments = []
    content = parsed_docx.get("content", {})

    # --- 문단(paragraph) 세그먼트화 ---
    paras = content.get("paragraphs", [])
    for idx, para in enumerate(paras):
        text = para.get("text", "")
        text_stripped = text.strip() if isinstance(text, str) else ""
        degraded = False
        reason = None
        if len(text_stripped) < degraded_para_threshold:
            degraded = True
            reason = "too_short_or_empty"

        segment_id = f"{parsed_docx.get('filename', filename)}-para{idx:04d}"
        seg_info = {
            "segment_id": segment_id,
            "filename": parsed_docx.get("filename", filename),
            "source_type": "paragraph",
            "para_num": para.get("para_num", idx+1),
            "text": text_stripped,
            "runs": para.get("runs", []),
            "style": para.get("style"),
            "alignment": para.get("alignment"),
            "source_para_index": idx,
            "degraded": degraded,
            "reason": reason
        }
        segments.append(seg_info)
        if degraded: degraded_segments.append(seg_info)

    # --- 표(table) 세그먼트화 ---
    tables = content.get("tables", [])
    for t_idx, table in enumerate(tables):
        for r_idx, row in enumerate(table.get("rows", [])):
            for c_idx, cell in enumerate(row):
                for p_idx, para in enumerate(cell.get('paragraphs', [])):
                    text = para.get("text", "")
                    text_stripped = text.strip() if isinstance(text, str) else ""
                    degraded = False
                    reason = None
                    if len(text_stripped) < degraded_para_threshold:
                        degraded = True
                        reason = "too_short_or_empty"
                    segment_id = (
                        f"{parsed_docx.get('filename', filename)}-table{t_idx+1:02d}"
                        f"-row{r_idx+1:02d}-col{c_idx+1:02d}-para{p_idx+1:02d}"
                    )
                    seg_info = {
                        "segment_id": segment_id,
                        "filename": parsed_docx.get("filename", filename),
                        "source_type": "table_cell",
                        "table_num": table.get("table_num", t_idx+1),
                        "row": cell.get("row", r_idx+1),
                        "col": cell.get("col", c_idx+1),
                        "cell_width": cell.get("width"),
                        "text": text_stripped,
                        "runs": para.get("runs", []),
                        "style": para.get("style"),
                        "alignment": para.get("alignment"),
                        "source_para_index": None,
                        "source_cell_index": [t_idx, r_idx, c_idx, p_idx],
                        "degraded": degraded,
                        "reason": reason,
                    }
                    segments.append(seg_info)
                    if degraded: degraded_segments.append(seg_info)

    return {
        "filename": parsed_docx.get("filename", filename),
        "format": "DOCX",
        "segments": segments,
        "degraded_pages": [],
        "degraded_segments": degraded_segments
    }
# main 실험용
# def save_json(obj, outpath):
#     os.makedirs(os.path.dirname(outpath), exist_ok=True)
#     with open(outpath, "w", encoding="utf-8") as f:
#         json.dump(obj, f, ensure_ascii=False, indent=2)

# if __name__ == "__main__":
#     # 실험용
#     docx_json_path = "/Users/cbg/github/law-doc-poc/data/parsed_raw/20260109_1329/샘플_해수욕장_샤워실_대여계약서__docx_results.json"
#     out_json_path = "/Users/cbg/github/law-doc-poc/data/segmentation/20260109_1329/샘플_해수욕장_샤워실_대여계약서__docx_results.json"

#     with open(docx_json_path, "r", encoding="utf-8") as f:
#         parsed_docx = json.load(f)

#     print(f"[INFO] 입력: {docx_json_path}")
#     seg_result = segment_docx_parsed(parsed_docx)
#     print(f"[INFO] segment 개수: {len(seg_result['segments'])}")
#     save_json(seg_result, out_json_path)
#     print(f"[INFO] 저장 완료: {out_json_path}")