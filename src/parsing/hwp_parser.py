import olefile
import zlib
import struct
import base64
import re
import xml.etree.ElementTree as ET

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

def clean_font_name(name):
    """폰트 이름 뒤에 붙는 바이너리 노이즈 제거"""
    if not name:
        return "Unknown"
    # 한글, 영문, 숫자, 공백, 기본 특수문자만 허용
    cleaned = re.sub(r'[^a-zA-Z0-9가-힣\s\-_()]', '', name)
    return cleaned.strip()

def extract_hwp_v5_binary_deep(file_path):
    face_names = []
    char_shapes_list = []
    paragraphs = []

    try:
        with olefile.OleFileIO(file_path) as ole:
            # 1. 파일 헤더 확인 (압축 여부 파악)
            header = ole.openstream("FileHeader").read()
            is_compressed = (header[36] & 1) == 1

            # 2. DocInfo 파싱 (해독표 구축)
            if ole.exists("DocInfo"):
                raw_data = ole.openstream("DocInfo").read()
                try:
                    docinfo = zlib.decompress(raw_data, -15) if is_compressed else raw_data
                except:
                    docinfo = raw_data

                pos = 0
                while pos < len(docinfo):
                    if pos + 4 > len(docinfo): break
                    h = struct.unpack_from("<I", docinfo, pos)[0]
                    t, l = h & 0x3ff, (h >> 20) & 0xfff
                    curr_i = pos + 4
                    if l == 0xfff:
                        l = struct.unpack_from("<I", docinfo, curr_i)[0]
                        curr_i += 4
                    rec_data = docinfo[curr_i:curr_i+l]

                    # [Tag 19] 글꼴 이름
                    if t == 19:
                        try:
                            # 매뉴얼상 3바이트 속성 이후가 이름 (utf-16-le)
                            raw_name = rec_data[3:].decode('utf-16-le').split('\x00')[0]
                            face_names.append(clean_font_name(raw_name))
                        except: pass

                    # [Tag 21] 글자 모양 (색상, 폰트, 그리고 '속성' 추출)
                    elif t == 21:
                        if len(rec_data) >= 16:
                            try:
                                # f_idx: 한글 글꼴 ID (0~1바이트)
                                f_idx = struct.unpack_from("<H", rec_data, 0)[0]
                                
                                # prop: 글자 속성 비트 (4~7바이트)
                                # 비트 0: 진하게(Bold), 비트 1: 밑줄, 비트 2: 기울임(Italic) 등
                                prop = struct.unpack_from("<I", rec_data, 4)[0]
                                is_bold = bool(prop & 0x00000001)
                                is_italic = bool(prop & 0x00000004) # 공식 문서상 비트 2 (3번째 자리)
                                
                                # c_raw: RGB 색상 (12~15바이트)
                                c_raw = struct.unpack_from("<I", rec_data, 12)[0]
                                r, g, b = c_raw & 0xFF, (c_raw >> 8) & 0xFF, (c_raw >> 16) & 0xFF
                                
                                font_name = face_names[f_idx] if f_idx < len(face_names) else "기본글꼴"
                                char_shapes_list.append({
                                    "font": font_name,
                                    "color": f"#{r:02x}{g:02x}{b:02x}",
                                    "bold": is_bold,
                                    "italic": is_italic
                                })
                            except: pass
                    pos = curr_i + l

            # 3. 본문 파싱 및 스타일 매핑
            sections = [ "/".join(e) for e in ole.listdir() if "Section" in e[-1] and "BodyText" in e ]
            
            for sec in sorted(sections):
                s_raw = ole.openstream(sec).read()
                try:
                    unpacked = zlib.decompress(s_raw, -15) if is_compressed else s_raw
                except:
                    unpacked = s_raw
                
                i = 0
                curr_p = None
                while i < len(unpacked) - 4:
                    h = struct.unpack_from("<I", unpacked, i)[0]
                    t, l = h & 0x3ff, (h >> 20) & 0xfff
                    curr_i = i + 4
                    if l == 0xfff:
                        l = struct.unpack_from("<I", unpacked, curr_i)[0]
                        curr_i += 4
                    data = unpacked[curr_i:curr_i+l]

                    if t == 66: # PARA_HEADER
                        if curr_p: paragraphs.append(curr_p)
                        curr_p = {"text": "", "char_styles": [], "type": "paragraph"}
                    
                    elif t == 67 and curr_p: # PARA_TEXT
                        txt = ""
                        for j in range(0, len(data)-1, 2):
                            code = struct.unpack_from("<H", data, j)[0]
                            # 특수 제어 문자 제외 일반 문자 추출
                            if code > 31: txt += chr(code)
                        curr_p["text"] += txt
                    
                    elif t == 68 and curr_p: # PARA_CHAR_SHAPE
                        for j in range(0, len(data), 8):
                            if j + 8 <= len(data):
                                pos_off, s_id = struct.unpack_from("<II", data, j)
                                if s_id < len(char_shapes_list):
                                    curr_p["char_styles"].append({
                                        "at": pos_off, 
                                        "style": char_shapes_list[s_id]
                                    })
                    i = curr_i + l
                if curr_p: paragraphs.append(curr_p)

    except Exception as e:
        print(f"Error: {e}")

    return {
        "meta": {"fonts": face_names, "styles": char_shapes_list},
        "paragraphs": paragraphs
    }


# --- OWPML XML 파싱 로직 ---
def extract_hwp_owpml_xml(file_path):
    try:
        with open(file_path, "rb") as f:
            xml_data = f.read()
        
        # XML 네임스페이스 제거 (파싱 편의성)
        xml_text = xml_data.decode("utf-8", errors="replace")
        xml_text = re.sub(r'\sxmlns="[^"]+"', '', xml_text, count=1)
        root = ET.fromstring(xml_text)

        # 1. Font ID -> Name 매핑 구축
        font_map = {}
        for ff in root.findall(".//FONTFACE"):
            lang = ff.get("Lang")
            if lang == "Hangul": # 한글 글꼴 기준
                for font in ff.findall("FONT"):
                    font_map[font.get("Id")] = font.get("Name")

        # 2. CharShape ID -> 실제 의미 정보 매핑
        charshape_info = {}
        for cs in root.findall(".//CHARSHAPE"):
            cs_id = cs.get("Id")
            # 폰트 이름 찾기
            f_id_node = cs.find("FONTID")
            h_font_id = f_id_node.get("Hangul") if f_id_node is not None else "0"
            font_name = font_map.get(h_font_id, "Unknown")
            
            # 색상 변환 (10진수 -> Hex)
            raw_color = int(cs.get("TextColor", 0))
            # HWP XML 색상은 가끔 BGR일 수 있으나 기본적으로 0xRRGGBB 형태로 변환
            hex_color = f"#{raw_color:06x}"
            
            is_bold = cs.find("BOLD") is not None
            is_italic = cs.find("ITALIC") is not None
            
            charshape_info[cs_id] = {
                "font": font_name,
                "color": hex_color,
                "bold": is_bold,
                "italic": is_italic
            }

        # 3. 본문 문단 추출
        paragraphs = []
        # 모든 섹션 내의 P 태그 탐색
        for p in root.findall(".//P"):
            p_text = ""
            p_tokens = []
            
            # P 태그 내부의 TEXT 노드들 순회 (순서 보장)
            for text_node in p.findall(".//TEXT"):
                cs_id = text_node.get("CharShape")
                style = charshape_info.get(cs_id, {})
                
                # TEXT 내부의 실제 글자(CHAR)들만 합치기
                node_text = ""
                for char_node in text_node.findall("CHAR"):
                    if char_node.text:
                        node_text += char_node.text
                
                if node_text:
                    p_text += node_text
                    p_tokens.append({
                        "text": node_text,
                        "style": style
                    })
            
            if p_text:
                paragraphs.append({
                    "text": p_text,
                    "tokens": p_tokens,
                    "type": "paragraph"
                })

        return {"meta": {"styles": charshape_info}, "paragraphs": paragraphs}
    except Exception as e:
        print(f"OWXML Parse Error: {e}")
        return {"meta": {}, "paragraphs": []}



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
    result = {"format": fmt}
    result.update(out)
    return result
