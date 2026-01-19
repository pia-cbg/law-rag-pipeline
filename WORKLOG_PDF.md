# Structurer Worklog

## 2026-01-19

### 목표
- PDF structurer 스타일 기반 그룹핑 안정화 및 검수 뷰 제공

### 진행 요약
- chunk 병합/분리 규칙 보정: '>' 종결 처리, 주석 라인 병합, 단독 항목 예외, heading 분리 예외 해제(벌칙 구간 조 분리)
- group_id 확장: 주석 라인 그룹 연계, 하드랩 문장 병합 예외 반영
- style_spans 개선: 토큰/기호 분리로 색상 스팬 정밀화('<', '[' 기준 분리)
- 메타 정리: has_color/dominant_color 제거(중복 정보 정리)
- 정책 정리: YAML 정책 주석 보강 및 섹션 재구성

### 결과물
- Structured JSON에 group_id 포함
- grouped 텍스트 출력 최신화
- 검수용 HTML 뷰 추가: group_id 기반 접이식, 청킹 분리 그룹 강조, 원문/스타일 스팬 미리보기 포함

### 관련 변경 파일
- pdf_structurer.py
- pdf_default.yaml

### 다음 작업
- 띄어쓰기 검증 로직 추가 및 규칙 보정

## 2026-01-18
- YAML 기반 structurer 정책 정의
- group_id를 출력에 포함
- grouped 텍스트 출력 형식 유지

## 2026-01-17
- PDF 스타일 인지 structurer 추가

## 2026-01-12
- 설계 스켈레톤 구축 및 Cleaning 단계 완료
