# 배치 탭 SFTP 호출 최적화 실행 계획

작성일: 2026-03-20
범위: 배치 처리 탭의 날짜 선택, 분석(BATCH_ANALYSIS), 실행 단계에서 발생하는 SFTP 호출 최적화

## 목적
- 동일 사용자 상호작용 내 중복 SFTP 호출을 제거한다.
- 날짜 수가 많은 구간에서 분석 응답 지연을 줄인다.
- 분석 단계에서 수집한 파일 메타데이터를 실행 단계에서 재사용한다.

## 현재 이슈
- date-range 조회와 batch-analysis에서 available dates를 중복 조회한다.
- batch-analysis에서 날짜별 list_files를 순차 호출한다.
- batch-analysis에서 이미 확인한 파일 목록을 run_batch_async에서 다시 조회한다.

## 구현 단계

### 1. 호출 가시화
- admin 라우트와 process 라우트에 호출 횟수/소요시간 로그를 추가한다.
- 지표: get_available_dates 호출 수, list_files 총 호출 수, 요청당 총 지연.

### 2. 조회 단계 중복 제거
- 원칙: 한 번 조회한 available dates를 같은 사용자 흐름에서 재사용한다.
- 방법:
  - 옵션 A: 프론트에서 date-range 결과를 batch-analysis 요청에 전달
  - 옵션 B: 서버 메모리 TTL 캐시(짧은 만료)
- 권장: A+B 혼합 (정합성은 A, 급한 재호출 완충은 B)

### 3. 날짜별 파일 수집 병렬화
- batch-analysis 내부 날짜 루프를 제한 동시성으로 전환한다.
- 워커별 SFTP 연결 분리 정책을 유지한다.
- 일부 날짜 실패 시 전체 실패로 중단하지 않고 부분 실패를 응답에 포함한다.

### 4. 분석-실행 재사용
- batch-analysis 결과를 job metadata에 저장한다.
- run_batch_async는 우선 metadata를 사용하고, 검증 실패 시에만 재조회한다.
- 검증 기준:
  - TTL 만료 여부
  - 선택 날짜 집합 불일치
  - 필요 시 파일 수/해시 불일치

### 5. 폴백 및 운영 안전장치
- 재사용 불가 시 기존 경로로 자동 폴백한다.
- 응답에 freshness 상태(reused/refetched)를 포함한다.

## 영향 파일
- app/routes/admin.py
- app/routes/process.py
- app/sftp_client.py
- app/utils/batch_analyzer.py
- app/database/manager.py

## 검증
- 동일 날짜 범위를 연속 2회 분석할 때 SFTP 호출 수 감소 확인
- 5/10/20일 범위에서 분석 응답 p50/p95 비교
- 분석 직후 실행 시 재사용 경로 진입 로그 확인
- 재사용 불일치 유도 시 자동 폴백 확인

## 완료 기준
- get_available_dates 중복 호출 제거 또는 1회로 수렴
- 날짜 20개 기준 분석 지연 유의미 감소(목표 30%+)
- 기능 회귀 없이 실행 결과 건수 동일
