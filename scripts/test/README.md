# 테스트 스크립트 가이드

STT 사후 점검 시스템의 통합 테스트를 위한 스크립트 모음입니다.

## 📁 구조

```
scripts/test/
├── README.md                    # 이 파일
├── integration-test.sh          # 통합 테스트 (API 엔드포인트 검증)
├── docker-test.sh               # Docker 기반 자동화 테스트
├── test_db_api.sh               # DB API 테스트
├── test-local.sh                # 로컬 환경 테스트
├── run-tests.sh                 # 단위/통합 테스트 실행기
├── test_routes.py               # Python 단위 테스트
└── conftest.py                  # pytest 설정
```

---

## 🚀 빠른 시작

### 1. 로컬 환경에서 테스트 (개발 중)

**전제 조건**: 서버가 이미 실행 중이어야 함 (기본값: localhost:8002)

```bash
# 기본 테스트 (localhost:8002)
./scripts/test/integration-test.sh

# 원격 서버에서 테스트
./scripts/test/integration-test.sh 192.168.1.100 8080
```

### 2. Docker 환경에서 자동화 테스트 (배포 후)

**전제 조건**: Docker 설치됨

```bash
# 기본: 빌드 → 실행 → 테스트
./scripts/test/docker-test.sh

# 기존 이미지로 테스트만
./scripts/test/docker-test.sh --only-test

# 테스트 후 정리
./scripts/test/docker-test.sh --cleanup

# 다른 포트에서 실행
API_PORT=9000 ./scripts/test/docker-test.sh
```

### 3. 단위 테스트 (Python)

```bash
# pytest 실행
./scripts/test/run-tests.sh

# 또는 직접 실행
pytest scripts/test/test_routes.py -v
```

---

## 📋 각 스크립트 상세 설명

### `integration-test.sh` - 통합 테스트

**목적**: 배포 후 API가 정상 작동하는지 검증

**테스트 항목**:
- ✅ 헬스 체크 (`/healthz`)
- ✅ 날짜별 통계 API (`/api/admin/date-stats`)
- ✅ 캘린더 상태 API (`/process/calendar/status/{year}/{month}`)
- ✅ 배치 처리 생성 (`POST /process/batch/submit`)
- ✅ 배치 상태 확인 (`/process/batch/status/{job_id}`)
- ✅ CSV 다운로드 (`/process/batch/results/{job_id}/download`)

**사용법**:
```bash
# 기본 사용 (localhost:8002)
./scripts/test/integration-test.sh

# 호스트와 포트 지정
./scripts/test/integration-test.sh api.example.com 8080

# 환경 변수로 지정
API_HOST=192.168.1.100 \
API_PORT=8000 \
TEST_DATE_START=20260320 \
TEST_DATE_END=20260322 \
TIMEOUT=20 \
./scripts/test/integration-test.sh
```

**환경 변수**:
- `API_HOST`: 서버 호스트 (기본값: localhost)
- `API_PORT`: 서버 포트 (기본값: 8002)
- `TEST_DATE_START`: 배치 시작 날짜 YYYYMMDD (기본값: 20260328)
- `TEST_DATE_END`: 배치 종료 날짜 YYYYMMDD (기본값: 20260329)
- `TIMEOUT`: 배치 완료 대기 시간 초 (기본값: 15)

**출력**:
```
=== TEST 1: 헬스 체크 ===
[✓] 서버 상태: 정상

=== TEST 2: 날짜별 통계 API ===
[✓] 날짜별 통계 조회 성공
  총 날짜: 16
  총 파일: 48
  성공: 48
  실패: 0

... (테스트 계속)

=== 테스트 완료 리포트 ===
  총 테스트: 6
  성공: 6
  실패: 0

[모든 테스트 통과! ✓]
```

---

### `docker-test.sh` - Docker 자동화 테스트

**목적**: Docker 빌드 → 실행 → 테스트의 전체 사이클을 자동화

**단계**:
1. Docker 설치 확인
2. 이미지 빌드
3. 기존 컨테이너 정지/제거
4. 새 컨테이너 실행
5. 서버 준비 대기
6. 통합 테스트 실행
7. (선택) 정리

**사용법**:
```bash
# 기본: 빌드 + 실행 + 테스트
./scripts/test/docker-test.sh

# 옵션 조합
./scripts/test/docker-test.sh --no-build    # 빌드 생략
./scripts/test/docker-test.sh --only-build  # 빌드만
./scripts/test/docker-test.sh --only-test   # 테스트만 (기존 컨테이너 사용)
./scripts/test/docker-test.sh --cleanup     # 테스트 후 정리

# 환경 변수 지정
DOCKER_IMAGE_NAME=stt-prod \
DOCKER_CONTAINER_NAME=stt-prod-test \
API_PORT=9000 \
./scripts/test/docker-test.sh
```

**환경 변수**:
- `DOCKER_IMAGE_NAME`: 이미지 이름 (기본값: stt-system)
- `DOCKER_CONTAINER_NAME`: 컨테이너 이름 (기본값: stt-api-test)
- `API_PORT`: 외부 포트 (기본값: 8002)
- `CONTAINER_PORT`: 컨테이너 내부 포트 (기본값: 8000)
- `DOCKERFILE_PATH`: Dockerfile 경로 (기본값: ./Dockerfile)

**출력**:
```
╔════════════════════════════════════════════════════════════╗
║   STT 사후 점검 시스템 - Docker 테스트                   ║
╚════════════════════════════════════════════════════════════╝

[✓] Docker 설치 확인

=== Step 1: Docker 이미지 빌드 ===
[INFO] 이미지 빌드 중: stt-system
[✓] Docker 이미지 빌드 완료
REPOSITORY    TAG       IMAGE ID      CREATED       SIZE
stt-system    latest    abc123def     5 seconds ago  1.2GB

=== Step 2: Docker 컨테이너 실행 ===
...

=== Step 3: 통합 테스트 실행 ===
...

╔════════════════════════════════════════════════════════════╗
║  완료! ✓                                                  ║
╚════════════════════════════════════════════════════════════╝
```

---

### `test_db_api.sh` - DB API 테스트

**목적**: 데이터베이스 관련 API 검증

**사용법**:
```bash
./scripts/test/test_db_api.sh
```

---

### `test-local.sh` - 로컬 환경 테스트

**목적**: 로컬 개발 환경에서 빠른 테스트

**사용법**:
```bash
./scripts/test/test-local.sh
```

---

### `run-tests.sh` - 테스트 실행기

**목적**: Python 단위 테스트와 통합 테스트 실행

**사용법**:
```bash
./scripts/test/run-tests.sh
```

---

## 🔄 CI/CD 통합 (GitHub Actions 예시)

```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Run Docker Test
        run: ./scripts/test/docker-test.sh --cleanup
        
      - name: Upload Report
        if: failure()
        uses: actions/upload-artifact@v2
        with:
          name: test-report
          path: test_report_*.txt
```

---

## 📊 AWS EC2 배포 후 테스트

```bash
# 1. 소스 코드 가져오기
git clone https://github.com/your-repo/stt-system.git
cd stt-system

# 2. Docker로 배포
docker build -t stt-system .
docker run -d -p 8002:8002 --name stt-api stt-system

# 3. 통합 테스트 실행
./scripts/test/integration-test.sh localhost 8002

# 4. 결과 확인
echo "테스트 완료: 위의 리포트를 확인하세요"
```

---

## 🏢 온프레미스 서버 배포 후 테스트

```bash
# 1. 서버 준비
ssh user@on-prem-server
cd /opt/stt-system

# 2. 서버 시작
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# 3. 테스트 실행 (원격)
./scripts/test/integration-test.sh on-prem-server 8000

# 4. 또는 직접 테스트
./scripts/test/integration-test.sh localhost 8000
```

---

## ✅ 체크리스트

### 개발 환경
- [ ] 단위 테스트 통과: `./scripts/test/run-tests.sh`
- [ ] 로컬 API 테스트: `./scripts/test/integration-test.sh`
- [ ] DB API 테스트: `./scripts/test/test_db_api.sh`

### 스테이징 환경
- [ ] Docker 빌드 성공: `./scripts/test/docker-test.sh --only-build`
- [ ] Docker 컨테이너 실행: `./scripts/test/docker-test.sh --only-test`
- [ ] 전체 자동화 테스트: `./scripts/test/docker-test.sh`

### 프로덕션 환경
- [ ] 배포 후 통합 테스트: `./scripts/test/integration-test.sh <prod-host> <prod-port>`
- [ ] 헬스 체크: `curl https://<prod-host>/healthz`
- [ ] 모니터링 확인

---

## 🐛 트러블슈팅

### "서버 응답 없음" 에러

```bash
# 1. 서버 상태 확인
curl -v http://localhost:8002/healthz

# 2. 방화벽 확인
netstat -tulpn | grep 8002

# 3. 서버 로그 확인
docker logs stt-api-test
```

### "Docker가 설치되어 있지 않습니다"

```bash
# Docker 설치 (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install docker.io

# Docker 설치 (macOS)
brew install docker
```

### "통합 테스트 실패"

```bash
# 상세 로그 출력
bash -x ./scripts/test/integration-test.sh

# 특정 API만 테스트
curl -v http://localhost:8002/api/admin/date-stats
```

---

## 📞 지원

문제가 발생하면:
1. 로그 확인: `docker logs <container-name>`
2. 서버 상태 확인: `curl http://localhost:8002/healthz`
3. 스크립트 실행 권한 확인: `ls -l scripts/test/*.sh`

---

**마지막 업데이트**: 2026-03-17  
**작성자**: STT Development Team
