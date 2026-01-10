# law-rag-pipeline

**2026/01 기준 현재 실험·설계 중:**  
이 프로젝트는 **비정형 데이터(특히 법률/계약 문서 등)**를  
자동 전처리·정제·정규화하여  
**LangChain 기반 RAG(Retrieval-Augmented Generation) 파이프라인**에서  
바로 활용할 수 있는 구조의 데이터로 변환하는 것을 목표로 합니다.

---

## 🎯 최종 목적

> **비정형 문서 → 자동 전처리 파이프라인 → RAG-ready 데이터 →  
LangChain RAG 연계 워크플로 구축**

- 다양한 원본 문서(docx, pdf, hwp 등)를
- parsing → segmentation → cleansing → normalization 단계를 거쳐
- **LangChain/RAG pipeline**(벡터DB/검색/생성형 QA 등)에 최적화된 JSON(또는 텍스트/메타) 구조로 자동 변환

---

## 주요 기능/개발 구조

- **모듈별 책임 분리와 단계적 자동화**  
  : parsing, segmentation, cleansing, normalization 완전 분리
- **실제 데이터-코드/메타/폴더화 설계**  
  : data/raw, data/normalization 등 단계별 저장소 관리
- **실험/설계/정책 반영 실시간 진행**  
  : 다양한 문서/고객사/정책 케이스별로 구조와 룰북 실험

---

## 폴더 구조 예시
```
law-rag-pipeline/
├── README.md                           # 프로젝트 설명 및 구조 안내
├── app.py                              # (예시) 진입점, 샘플 app용
├── data/                               # 문서 및 전처리 결과, 산출물 저장
│   ├── raw/                            # 수집된 원본 문서
│   ├── preprocess/                     # 사전 정제/클린징 처리 결과
│   │   ├── raw_clean/                  # 1차 클린된 파일 저장
│   │   └── failures/                   # 전처리 실패 파일(오염/중복/에러 등 분류)
│   ├── segmentation/                   # 세그멘트(조각)화 JSON 저장 (날짜/포맷별)
│   ├── parsed_raw/                     # 각종 파서(raw→json) 결과 저장
│   └── normalization/                  # 정규화(RAG-ready) 결과 및 테스트
│       └── test/                       # normalization 테스트 결과
├── experiments/                        # 실험/테스트용 로그 및 결과
│   ├── logs/
│   └── results/
└── src/                                
    ├── normalization/                  # 정규화/클렌징/스키마 통일 코드
    │   ├── base.py                     # 공통/기본 로직
    │   ├── docx_normalize.py           # docx 전용 정규화
    │   ├── cleanser/                   # 전처리/정제 로직 모듈 폴더
    │   │   ├── __init__.py
    │   │   ├── generic.py              # 모든 포맷 공통 클렌저
    │   │   ├── docx_cleanser.py        # docx 타입 특화 클렌저
    │   │   └── rules/                  # 클렌징 YAML 및 정책 관리
    │   │       ├── __init__.py
    │   │       ├── docx_default.yaml   # docx형 기본 클렌징 룰북 (yaml)
    │   │       └── rules_catalog.py    # 정책명 상수(자동완성 목적) 정의 py
    │   └── __init__.py
    ├── parsing/                        # 파서(포맷별 텍스트 추출) 모듈
    │   ├── __init__.py
    │   ├── base.py
    │   ├── docx_parser.py
    │   ├── hwp_parser.py
    │   └── pdf_parser.py
    ├── pipelines/                      # 전처리 전체 배치/자동 워크플로우
    │   ├── __init__.py
    │   ├── full_pipeline.py            # end-to-end 전체 파이프
    │   ├── deep_parse_folder.py        # RAW 파서
    │   └── segmentation_folder.py      # 세그먼트
    ├── preprocessing/                  # 파일명검증/고급 품질관리 등 1차 정제
    │   ├── __init__.py
    │   └── raw_cleaner.py
    ├── prompts/                        # LLM 프롬프트(예정)
    ├── rag/                            # RAG & 벡터DB 연동 코드 (예정)
    │   ├── embed/
    │   └── vectorstore/
    └── segmentation/                   # 문서 조각화(세그멘트) 모듈
        ├── __init__.py
        ├── base.py
        ├── docx_segmenter.py
        ├── hwp_segmenter.py
        └── pdf_segmenter.py
```
---

## 현재 상태

- 구조·스켈레톤·설계 중
- 각 단계별 책임/자동완성/폴더/룰북 등 실험 진행
- 향후 LangChain, Vector DB, 검색 QA와 직접 연계할 계획

---

## 개발자 정보

- 개발자 : Choi Bo Gyeong
- E-mail : cbg1704@gmail.com

---

**본 레포는 진행 중(Working in progress)이고,  
모든 정책/코드/구조/룰은 계속 진화·확장될 예정입니다.**