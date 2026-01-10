# src/segmentation/base.py

from typing import Dict, Any
from src.segmentation.docx_segmenter import segment_docx_parsed
from src.segmentation.pdf_segmenter import segment_pdf_parsed
from src.segmentation.hwp_segmenter import segment_hwp_parsed

def segment_document(parsed: Dict[str, Any], filetype: str = None):
    """
    parsed: 파싱 결과 dict (pdf/hwp/docx 등 타입별)
    filetype: 확장자 ('pdf', 'hwp', ...)
    ---
    return: 
      {
        "filename": ...,
        "segments": [...],
        "degraded_pages": [...]
      }
    """
    if filetype == 'pdf':
        return segment_pdf_parsed(parsed)
    elif filetype == 'hwp':
        return segment_hwp_parsed(parsed)
    elif filetype == 'docx':
        return segment_docx_parsed(parsed)
    else:
        raise ValueError(f"지원하지 않는 문서 타입: {filetype}")