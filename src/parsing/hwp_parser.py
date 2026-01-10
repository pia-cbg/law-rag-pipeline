import olefile
import zlib
import struct
import base64
import re

HWPTAG_PARA_HEADER = 0x42  # 66
HWPTAG_PARA_TEXT = 0x43    # 67
HWPTAG_PARA_CHAR_SHAPE = 0x44
HWPTAG_PARA_SHAPE = 0x63
HWPTAG_STYLE = 0x65
HWPTAG_NUMBERING = 0x69
HWPTAG_TABLE = 0x10

def bytes_to_b64(obj):
    if isinstance(obj, dict):
        return {k: bytes_to_b64(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [bytes_to_b64(v) for v in obj]
    elif isinstance(obj, bytes):
        return base64.b64encode(obj).decode('ascii')
    else:
        return obj

def remove_surrogates(obj):
    if isinstance(obj, dict):
        return {k: remove_surrogates(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [remove_surrogates(v) for v in obj]
    elif isinstance(obj, str):
        return re.sub(r'[\ud800-\udfff]', '', obj)
    else:
        return obj

def identify_hwp_format(file_path):
    with open(file_path, 'rb') as f:
        sig = f.read(2048)
    if sig.startswith(b'\xd0\xcf\x11\xe0'):
        return "HWP_V5_BINARY"
    if b'<?xml' in sig or b'<HWPML' in sig:
        return "HWP_OWPML_XML"
    return None

def extract_hwp_v5_binary_deep(file_path):
    doc_info = {"char_shapes": [], "para_shapes": [], "styles": [], "numberings": []}
    paragraphs = []
    tables = []
    try:
        with olefile.OleFileIO(file_path) as ole:
            header = ole.openstream("FileHeader").read()
            is_compressed = (header[36] & 1) == 1

            try:
                docinfo = ole.openstream("DocInfo").read()
                pos = 0
                while pos < len(docinfo):
                    rec_header = struct.unpack_from("<I", docinfo, pos)[0]
                    rec_type = rec_header & 0x3ff
                    rec_len = (rec_header >> 20) & 0xfff
                    curr_i = pos + 4
                    if rec_len == 0xfff:
                        rec_len = struct.unpack_from("<I", docinfo, curr_i)[0]
                        curr_i += 4
                    rec_data = docinfo[curr_i:curr_i+rec_len]
                    if rec_type == HWPTAG_PARA_CHAR_SHAPE:
                        doc_info["char_shapes"].append(rec_data)
                    elif rec_type == HWPTAG_PARA_SHAPE:
                        doc_info["para_shapes"].append(rec_data)
                    elif rec_type == HWPTAG_STYLE:
                        doc_info["styles"].append(rec_data)
                    elif rec_type == HWPTAG_NUMBERING:
                        doc_info["numberings"].append(rec_data)
                    pos = curr_i + rec_len
            except Exception:
                pass

            sections = sorted([s for s in ole.listdir() if 'BodyText/Section' in '/'.join(s)])
            for sec in sections:
                try:
                    data = ole.openstream(sec).read()
                    unpacked = zlib.decompress(data, -15) if is_compressed else data
                    i = 0
                    curr_paragraph = None
                    paragraph_list = []
                    while i < len(unpacked) - 4:
                        rec_header = struct.unpack_from("<I", unpacked, i)[0]
                        rec_type = rec_header & 0x3ff
                        rec_len = (rec_header >> 20) & 0xfff
                        curr_i = i + 4
                        if rec_len == 0xfff:
                            rec_len = struct.unpack_from("<I", unpacked, curr_i)[0]
                            curr_i += 4
                        rec_data = unpacked[curr_i:curr_i+rec_len]

                        if rec_type == HWPTAG_PARA_HEADER:
                            if curr_paragraph is not None:
                                paragraph_list.append(curr_paragraph)
                            curr_paragraph = {
                                "text": "",
                                "char_shapes": [],
                                "para_shapes": [],
                                "type": "paragraph"
                            }
                        elif rec_type == HWPTAG_PARA_TEXT and curr_paragraph is not None:
                            text = []
                            j = 0
                            while j < len(rec_data) - 1:
                                char_code = struct.unpack_from("<H", rec_data, j)[0]
                                if 1 <= char_code <= 31:
                                    if char_code == 9:
                                        text.append("\t")
                                    elif char_code in [10, 13]:
                                        text.append("\n")
                                    elif char_code in [12, 14]:
                                        text.append("[OBJECT]")
                                    j += 2
                                else:
                                    text.append(chr(char_code))
                                    j += 2
                            curr_paragraph["text"] += "".join(text)
                        elif rec_type == HWPTAG_PARA_CHAR_SHAPE and curr_paragraph is not None:
                            curr_paragraph["char_shapes"].append(rec_data)
                        elif rec_type == HWPTAG_PARA_SHAPE and curr_paragraph is not None:
                            curr_paragraph["para_shapes"].append(rec_data)
                        elif rec_type == HWPTAG_TABLE:
                            tables.append({
                                "raw_data": rec_data
                            })
                            if curr_paragraph is not None:
                                paragraph_list.append(curr_paragraph)
                                curr_paragraph = None
                        i = curr_i + rec_len
                    if curr_paragraph is not None:
                        paragraph_list.append(curr_paragraph)
                    paragraphs.extend(paragraph_list)
                except Exception:
                    pass
    except Exception:
        pass
    return {
        "meta": doc_info,
        "paragraphs": paragraphs,
        "tables": tables
    }

def extract_hwp_owpml_xml(file_path):
    """OWPML XML(.hwp) 파싱, <P> 단순 추출(최소 파서)"""
    try:
        with open(file_path, "rb") as f:
            content = f.read()
        # 인코딩 자동 추정 (utf-8, utf-16, cp949), 가장 흔한 것 부터
        for enc in ["utf-8", "utf-16", "cp949"]:
            try:
                text = content.decode(enc)
                break
            except Exception:
                continue
        else:
            text = content.decode("utf-8", errors="replace")  # 강제
        # <P> 태그 추출 (실사용시 lxml 등으로 보완 가능)
        paras = re.findall(r"<P[^>]*>(.*?)</P>", text, re.DOTALL | re.IGNORECASE)
        paragraphs = [{"text": re.sub(r"<[^>]+>", "", p).strip()} for p in paras]
        return {"meta": {}, "paragraphs": paragraphs, "tables": []}
    except Exception:
        return {"meta": {}, "paragraphs": [], "tables": []}

def parse_hwp(file_path):
    fmt = identify_hwp_format(file_path)
    if fmt == "HWP_V5_BINARY":
        out = extract_hwp_v5_binary_deep(file_path)
        out = bytes_to_b64(out)
        out = remove_surrogates(out)
    elif fmt == "HWP_OWPML_XML":
        out = extract_hwp_owpml_xml(file_path)
        out = remove_surrogates(out)
    else:
        out = {"meta": {}, "paragraphs": [], "tables": []}
    # 포맷 명시 해줘야함. HWP_V5_BINARY, HWP_OWPML_XML
    result = {"hwp_format": fmt}
    result.update(out)
    return result
