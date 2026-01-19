import json
import os
from collections import defaultdict, Counter

def words_to_lines(words, y_tol=2.0, gap_tol=3.5):
    """좌표 기반으로 줄 묶기 + 띄어쓰기 복원

    - y_tol: 같은 줄로 간주할 y좌표 허용 오차 (pixel)
    - gap_tol: 띄어쓰기로 판단할 단어 간 x0-x1 거리 (pixel)
    """
    if not words:
        return []
    lines = defaultdict(list)
    for idx, word in enumerate(words):
        # y를 근사해 한 줄로 묶음 (y_tol은 문서 해상도에 따라 조정)
        y = round(word['top'] / y_tol) * y_tol
        lines[y].append((word['x0'], idx, word))

    line_items = []
    for y, xwords in lines.items():
        # X축 오름차순 정렬
        sort_xwords = sorted(xwords)
        line_text = ""
        prev_x1 = None
        sizes = []
        fontnames = []
        for x0, _, w in sort_xwords:
            # 띄어쓰기 필요시 공백 삽입
            if prev_x1 is not None:
                gap = x0 - prev_x1
                if gap > gap_tol:
                    line_text += " "
            line_text += w['text']
            prev_x1 = w['x1']
            if 'size' in w:
                sizes.append(w['size'])
            if 'fontname' in w:
                fontnames.append(w['fontname'])
        idxs = [i for _, i, _ in sort_xwords]
        avg_size = sum(sizes) / len(sizes) if sizes else None
        max_size = max(sizes) if sizes else None
        font_counter = Counter(fontnames)
        mode_font = font_counter.most_common(1)[0][0] if font_counter else None
        line_items.append({
            'y': y,
            'text': line_text,
            'word_indices': idxs,
            'words': [w for _, _, w in sort_xwords],
            'font_size_avg': avg_size,
            'font_size_max': max_size,
            'font_name_mode': mode_font,
        })
    return sorted(line_items, key=lambda x: x['y'])

def segment_pdf_parsed(parsed_pdf, filename=None, degraded_line_threshold=2, y_tol=2.0, gap_tol=3.5):
    """페이지별로 lines으로 쪼개 segment화합니다.

    각 세그먼트(dict)에 'colors': [ ... ] (각 word의 non_stroking_color 리스트) 포함
    """
    segments = []
    degraded_pages = []

    for page in parsed_pdf['content']['pages']:
        page_num = page['page']
        words = page.get('words', [])
        lines = words_to_lines(words, y_tol, gap_tol)
        if not lines:
            degraded_pages.append({
                "page": page_num,
                "reason": "line_merge_fail"
            })
            continue

        for line_num, line in enumerate(lines):
            segment_id = f"{parsed_pdf['filename']}-p{page_num:02d}-l{line_num:03d}"
            text = line['text'].strip()
            degraded = False
            reason = None
            if len(text) < degraded_line_threshold:
                degraded = True
                reason = "too_short_or_empty"

            # 모든 단어별 non_stroking_color 추출
            colors = [w.get("non_stroking_color") for w in line['words']]
            font_size_avg = line.get("font_size_avg")
            font_size_max = line.get("font_size_max")
            font_name_mode = line.get("font_name_mode")

            segments.append({
                "segment_id": segment_id,
                "filename": parsed_pdf['filename'],
                "page_num": page_num,
                "text": text,
                "source_word_indices": line['word_indices'],
                "colors": colors,
                "font_size_avg": font_size_avg,
                "font_size_max": font_size_max,
                "font_name_mode": font_name_mode,
                "degraded": degraded,
                "reason": reason
            })
    return {
        "filename": parsed_pdf['filename'] if filename is None else filename,
        "format": "PDF",
        "segments": segments,
        "degraded_pages": degraded_pages
    }
# # main 실험용
# def save_segments_to_json(output, out_path):
#     os.makedirs(os.path.dirname(out_path), exist_ok=True)
#     with open(out_path, "w", encoding="utf-8") as f:
#         json.dump(output, f, ensure_ascii=False, indent=2)

# if __name__ == '__main__':
#     # 실험용
#     parsed_pdf_path = "/Users/cbg/github/law-doc-poc/data/parsed_raw/20260109_0523/pdf_results.json"
#     segmentation_root_dir = "/Users/cbg/github/law-doc-poc/data/segmentation"
#     parsed_dir, filename = os.path.split(parsed_pdf_path)
#     parent_dir = os.path.basename(parsed_dir)
#     out_dir = os.path.join(segmentation_root_dir, parent_dir)
#     out_path = os.path.join(out_dir, filename)

#     print(f"[INFO] 입력: {parsed_pdf_path}")
#     print(f"[INFO] 출력: {out_path}")

#     with open(parsed_pdf_path, 'r', encoding='utf-8') as f:
#         parsed_pdf = json.load(f)

#     # 리스트인지 확인해 처리
#     if isinstance(parsed_pdf, list):
#         pdf_obj_list = parsed_pdf
#     else:
#         pdf_obj_list = [parsed_pdf]

#     all_results = []
#     for idx, pdf_obj in enumerate(pdf_obj_list):
#         print(f"[INFO] Segmentation 시작: {pdf_obj.get('filename', f'문서{idx}')}")
#         segmented = segment_pdf_parsed(pdf_obj)
#         print(f"[INFO] 총 {len(segmented['segments'])}개 세그먼트 생성")
#         if segmented['degraded_pages']:
#             print(f"[WARNING] Degraded page(s) 있음: {segmented['degraded_pages']}")
#         all_results.append(segmented)

#     results_to_save = all_results if len(all_results) > 1 else all_results[0]
#     save_segments_to_json(results_to_save, out_path)
#     print(f"[INFO] Segmentation 결과 저장됨: {out_path}")
