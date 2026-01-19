"""
generic.py

- 목적: 지정된 segmentation 폴더(다수 json)에서
  모든 segment의 'text' 필드에 제너럴 클린징을 적용,
  normalization/test 아래 동일 파일명으로 저장
"""

import os
import json
import re

# ------ 제너럴 클린징 함수 ------
RE_MULTISPACE = re.compile(r'\s+')
RE_CONTROLCHAR = re.compile(r'[\x00-\x1F\u200B]+')

def generic_cleanser(text: str) -> str:
    t = RE_CONTROLCHAR.sub(' ', text)
    t = RE_MULTISPACE.sub(' ', t)
    return t.strip()

# # 실험용
# INPUT_DIR = "/Users/cbg/github/law-doc-poc/data/segmentation/20260109_1438"
# OUTPUT_DIR = "/Users/cbg/github/law-doc-poc/data/normalization/test"

# def main():
#     os.makedirs(OUTPUT_DIR, exist_ok=True)
#     files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.json') and os.path.isfile(os.path.join(INPUT_DIR, f))]
#     print(f"[INFO] {len(files)}개 파일 처리 시작")

#     for fname in files:
#         inpath = os.path.join(INPUT_DIR, fname)
#         outpath = os.path.join(OUTPUT_DIR, fname)
#         with open(inpath, "r", encoding="utf-8") as fin:
#             data = json.load(fin)
#         if "segments" in data and isinstance(data["segments"], list):
#             for seg in data["segments"]:
#                 # text 필드가 문자열일 때만 적용
#                 if isinstance(seg.get("text", None), str):
#                     seg["text"] = generic_cleanser(seg["text"])
#         # 결과 json 저장
#         with open(outpath, "w", encoding="utf-8") as fout:
#             json.dump(data, fout, ensure_ascii=False, indent=2)
#         print(f" [OK] {fname} → {outpath}")

#     print(f"[DONE] 모든 제너럴 클린징 완료! (out: {OUTPUT_DIR})")

# if __name__ == "__main__":
#     main()