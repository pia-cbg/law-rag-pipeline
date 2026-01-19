"""
cleanser/base.py
"""
from src.normalization.cleanser.pdf_cleanser import pdf_cleanser
from src.normalization.cleanser.docx_cleanser import docx_cleanser
from src.normalization.cleanser.hwp_cleanser import hwp_cleanser

# JSON 스키마의 "format" 값에 맞춘 정밀 매핑
CLEANSERS = {
    'PDF': pdf_cleanser,
    'DOCX': docx_cleanser,
    'HWP': hwp_cleanser,
}

def clean_segments(seg_json):
    fmt = seg_json.get("format", "").upper()
    cleanser_fn = CLEANSERS.get(fmt)
    
    if cleanser_fn is None:
        print(f"[CLEANSER] Unsupported format: {fmt}")
        return seg_json

    try:
        return cleanser_fn(seg_json)
    except Exception as e:
        print(f"[CLEANING ERROR] {seg_json.get('filename')}: {e}")
        return seg_json