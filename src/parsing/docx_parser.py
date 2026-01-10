# """
# docx_parser.py

# 책임:
# - DOCX 파일에서 텍스트(단락/셀)를 추출
# - 기본 불필요한 유니코드/제어문자만 소거
# """

# from docx import Document

# def parse_docx(file_path):
#     results = []
#     doc = Document(file_path)

#     # 1. 패러그래프 추출
#     for num, para in enumerate(doc.paragraphs):
#         txt = para.text.strip()
#         if txt:
#             results.append({"para_num": num+1, "text": txt})

#     # 2. 표 셀 추출
#     for t_num, table in enumerate(doc.tables):
#         for r_idx, row in enumerate(table.rows):
#             for c_idx, cell in enumerate(row.cells):
#                 cell_txt = cell.text.strip()
#                 if cell_txt:
#                     results.append({
#                         "cell": True,
#                         "table": t_num+1,
#                         "row": r_idx+1,
#                         "col": c_idx+1,
#                         "text": cell_txt
#                     })
#     return results

from docx import Document

def parse_docx(file_path):
    doc = Document(file_path)
    
    # 1. 메타데이터 (core + extended)
    meta = {}
    if hasattr(doc, "core_properties"):
        props = doc.core_properties
        meta = {
            "title": getattr(props, "title", None),
            "subject": getattr(props, "subject", None),
            "creator": getattr(props, "author", None),
            "last_modified_by": getattr(props, "last_modified_by", None),
            "created": str(getattr(props, "created", "")) if getattr(props, "created", None) else None,
            "modified": str(getattr(props, "modified", "")) if getattr(props, "modified", None) else None,
            "keywords": getattr(props, "keywords", None),
            "description": getattr(props, "description", None),
            "category": getattr(props, "category", None),
            "comments": getattr(props, "comments", None),
            "revision": getattr(props, "revision", None),
            "identifier": getattr(props, "identifier", None),
            "language": getattr(props, "language", None),
            "version": getattr(props, "version", None)
        }

    # 2. 문단(Paragraphs) - run, 스타일, 하이퍼링크 등 모든 정보
    paragraphs = []
    for p_idx, para in enumerate(doc.paragraphs):
        runs = []
        for run in para.runs:
            runs.append({
                "text": run.text,
                "bold": run.bold,
                "italic": run.italic,
                "underline": run.underline,
                "font": str(run.font.name) if run.font and run.font.name else None,
                "size": run.font.size.pt if run.font.size else None,
                "color": run.font.color.rgb if run.font.color and run.font.color.rgb else None,
                "highlight_color": run.font.highlight_color if hasattr(run.font, "highlight_color") else None,
            })
        # 하이퍼링크 식별(간접적) - run과 field_code 조합 등 복잡
        hyperlinks = [
            run.text for run in para.runs
            if hasattr(run, "hyperlink") or "HYPERLINK" in run.text
        ]
        para_info = {
            "para_num": p_idx + 1,
            "text": para.text,
            "style": para.style.name if para.style else None,
            "alignment": str(para.alignment) if para.alignment else None,
            "runs": runs,
            "hyperlinks": hyperlinks
        }
        paragraphs.append(para_info)

    # 3. 표(Table): 셀 병합 여부, 셀 내부 문단(및 run), 셀 스타일 등 최대한 추출
    tables = []
    for t_idx, table in enumerate(doc.tables):
        tbl = []
        for r_idx, row in enumerate(table.rows):
            row_data = []
            for c_idx, cell in enumerate(row.cells):
                # 셀 내용 전체(문단별 deep parsing)
                cell_paragraphs = []
                for c_p_idx, c_para in enumerate(cell.paragraphs):
                    c_runs = []
                    for run in c_para.runs:
                        c_runs.append({
                            "text": run.text,
                            "bold": run.bold,
                            "italic": run.italic,
                            "underline": run.underline,
                            "font": str(run.font.name) if run.font and run.font.name else None,
                            "size": run.font.size.pt if run.font.size else None
                        })
                    c_para_info = {
                        "text": c_para.text,
                        "style": c_para.style.name if c_para.style else None,
                        "runs": c_runs
                    }
                    cell_paragraphs.append(c_para_info)
                row_data.append({
                    "row": r_idx + 1,
                    "col": c_idx + 1,
                    "text": cell.text,
                    "paragraphs": cell_paragraphs,
                    "width": cell.width if hasattr(cell, "width") else None
                    # python-docx는 직접적으로 셀 병합 정보는 노출하지 않음 (cell._tc와 gridSpan 등 xml 접근 필요)
                })
            tbl.append(row_data)
        tables.append({
            "table_num": t_idx + 1,
            "rows": tbl
        })

    # 4. 그림(이미지)
    images = []
    if hasattr(doc.part, "related_parts"):
        for rel_id, rel in doc.part.related_parts.items():
            if hasattr(rel, "image"):
                img = rel.image
                images.append({
                    "rel_id": rel_id,
                    "content_type": rel.content_type,
                    "image_ext": img.ext,
                    "image_bytes_len": len(img.blob),
                })

    # 5. 머리글(Header) / 바닥글(Footer)
    headers, footers = [], []
    for section in doc.sections:
        h = section.header
        f = section.footer
        headers.extend([p.text for p in h.paragraphs])
        footers.extend([p.text for p in f.paragraphs])

    # 6. 각주(Footnotes), 미주(Endnotes)
    # python-docx에는 기본 지원 없음 -> XML 파싱 필요, 여기서는 구조만 보존
    footnotes, endnotes = [], []
    if hasattr(doc.part.package, "part_related_by_reltype"):
        for rel in doc.part.package.part_related_by_reltype("http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes"):
            footnotes.append(rel.blob.decode(errors="ignore"))
        for rel in doc.part.package.part_related_by_reltype("http://schemas.openxmlformats.org/officeDocument/2006/relationships/endnotes"):
            endnotes.append(rel.blob.decode(errors="ignore"))

    # 7. 섹션 정보
    sections = []
    for s_idx, section in enumerate(doc.sections):
        sections.append({
            "section_num": s_idx + 1,
            "start_type": str(section.start_type) if hasattr(section, "start_type") else None,
            "orientation": str(section.orientation) if hasattr(section, "orientation") else None,
            "page_height": getattr(section, "page_height", None),
            "page_width": getattr(section, "page_width", None),
            "header_distance": getattr(section, "header_distance", None),
            "footer_distance": getattr(section, "footer_distance", None),
            "left_margin": getattr(section, "left_margin", None),
            "right_margin": getattr(section, "right_margin", None),
            "top_margin": getattr(section, "top_margin", None),
            "bottom_margin": getattr(section, "bottom_margin", None),
        })

    return {
        "meta": meta,
        "paragraphs": paragraphs,
        "tables": tables,
        "images": images,
        "headers": headers,
        "footers": footers,
        "footnotes": footnotes,
        "endnotes": endnotes,
        "sections": sections
    }