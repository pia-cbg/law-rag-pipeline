import pdfplumber

def parse_pdf(file_path):
    """
    PDF에서 가능한 모든 정보(텍스트, 좌표, 폰트, 테이블, 이미지, 도형, 메타데이터)를 최대한 추출
    반환:
        {
            "doc_meta": {...},
            "pages": [
                {
                    "page": 1,
                    "words": [...],
                    "chars": [...],
                    "tables": [...],
                    "images": [...],
                    "shapes": [...]
                }, ...
            ]
        }
    """
    results = []
    doc_meta = {}
    try:
        with pdfplumber.open(file_path) as pdf:
            # 문서 메타데이터 추출
            if hasattr(pdf, 'metadata'):
                doc_meta = pdf.metadata or {}
            elif hasattr(pdf, 'docinfo'):
                doc_meta = pdf.docinfo or {}

            # 암호화된 파일 처리(필요시)
            if getattr(pdf, "is_encrypted", False):
                print(f"[ERROR] 파일이 암호화되어 있습니다: {file_path}")
                return None

            for page_num, page in enumerate(pdf.pages, 1):
                words = page.extract_words(extra_attrs=[
                    "size", "fontname", "stroking_color", "non_stroking_color"
                ])
                chars = page.chars
                tables = page.extract_tables()

                images = []
                if hasattr(page, 'images'):
                    for img in page.images:
                        img_obj = page.extract_image(img['object_id']) if 'object_id' in img else None
                        images.append({
                            "object_id": img.get("object_id"),
                            "name": img.get("name"),
                            "x0": img.get("x0"),
                            "top": img.get("top"),
                            "x1": img.get("x1"),
                            "bottom": img.get("bottom"),
                            "width": img.get("width"),
                            "height": img.get("height"),
                            "srcsize": img_obj["size"] if img_obj else None,
                            "ext": img_obj["ext"] if img_obj else None,
                            # "image_data": img_obj["image"] if img_obj else None
                        })

                shapes = []
                if hasattr(page, 'rects'):
                    shapes.extend([{"type": "rect", **r} for r in page.rects])
                if hasattr(page, 'curves'):
                    shapes.extend([{"type": "curve", **c} for c in page.curves])
                if hasattr(page, 'lines'):
                    shapes.extend([{"type": "line", **l} for l in page.lines])

                results.append({
                    "page": page_num,
                    "words": words,
                    "chars": chars,
                    "tables": tables,
                    "images": images,
                    "shapes": shapes
                })
    except Exception as e:
        print(f"[PDF PARSER ERROR - DEEP] {file_path}: {e}")
        return None
    return {"doc_meta": doc_meta, "pages": results}