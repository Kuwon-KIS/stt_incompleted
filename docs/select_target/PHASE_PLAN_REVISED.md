# SELECT_TARGET 프로젝트 - 개정 계획 (2026년 3월 17일)

## 📋 Executive Summary

현재 Phase 4를 진행 중이며, **사용자 피드백을 반영하여 캘린더 UI를 개선**합니다.
주요 개선사항:
1. **캘린더 중심 레이아웃** - 캘린더가 먼저 표시
2. **상태 시각화** - 각 날짜의 처리 현황(완료/부분/대기)을 아이콘/색상으로 표시
3. **동적 선택 정보** - 범위 선택 시 자동으로 요약 정보 업데이트

---

## 📊 현황

### 완료된 항목 ✅

| Phase | 항목 | 상태 | 설명 |
|-------|------|------|------|
| 1 | SFTP 날짜 조회 API | ✅ | `GET /api/admin/date-range` 구현 완료 |
| 2 | 케이스 분류 API | ✅ | `POST /api/admin/batch-analysis` 구현 완료 |
| 3 | Batch Create 수정 | ✅ | option_id 기반 분기 처리 완료 |
| 4 | 프론트엔드 기본 구조 | ✅ | flatpickr 캘린더 + 분석 UI 기본 구현 |

### 진행 중 항목 🔄

| Phase | 항목 | 진행률 | 다음 단계 |
|-------|------|-------|---------|
| 4 | 캘린더 상태 시각화 | 30% | PHASE4_REVISED.md 참고 |

---

## 🎯 개정된 Phase 계획

### Phase 4: 캘린더 상태 시각화 UI 구현 (개선)

**기간**: ~3월 24일 (약 5-7시간)

**목표**: 사용자가 캘린더에서 한눈에 처리 현황을 파악하고 범위를 선택할 수 있도록 개선

**변경사항** (vs 기존 PLAN.md):
```
AS-IS (기존)              →  TO-BE (개선)
──────────────────────────→─────────────────────────
1. 범위 정보             1. 캘린더 (먼저 표시)
2. 캘린더 입력           2. 선택 정보 카드 (동기적)
3. 분석 버튼             3. 범위 정보
4. 결과 표시             4. 분석 버튼
                         5. 결과 표시
```

**상태 시각화 (추가)**:
- 📊 date-stats의 `status` 필드를 활용
- ✅ `completed` → 초록색
- ⚠️ `partial` → 주황색
- ⏳ `pending` → 파란색
- 🚫 (파일 없음) → 회색

**세부 사항**: [PHASE4_REVISED.md](PHASE4_REVISED.md) 참고

---

### Phase 5: 사용자 폴더/파일 업로드 기능 (독립적)

**기간**: ~3월 31일 (약 3-4시간)

**개요**: SFTP 기반 배치 처리에 추가로, 사용자가 직접 파일을 업로드하여 처리할 수 있는 기능

**기능**:
- 폴더 생성/삭제
- 파일 업로드 (드래그&드롭)
- 파일 목록 확인
- 업로드 폴더 기반 배치 처리

**참고**: [UPLOAD_FEATURE.md](/Users/a113211/workspace/stt_incompleted/docs/select_target/UPLOAD_FEATURE.md)

**API 엔드포인트** (신규):
```
POST   /process/upload/folder         - 폴더 생성
POST   /process/upload/files          - 파일 업로드
GET    /process/upload/folders        - 폴더 목록
GET    /process/upload/{id}/files     - 폴더의 파일 목록
DELETE /process/upload/{id}           - 폴더 삭제
```

---

### Phase 6: 통합 테스트 & 최적화

**기간**: ~4월 7일 (약 2-3시간)

**범위**:
- 캘린더 UI 완성 후 E2E 테스트
- 모든 케이스별 시나리오 검증
- 성능 최적화 (필요 시)

**수행 항목**:
1. 캘린더 시각화 테스트
   - [ ] 상태별 색상 표시 확인
   - [ ] 아이콘 렌더링 확인
   - [ ] 범위 선택 시 선택 정보 카드 업데이트

2. 케이스별 시나리오 테스트
   - [ ] full_overlap 케이스
   - [ ] partial_overlap 케이스
   - [ ] no_overlap 케이스
   - [ ] no_data 케이스

3. 업로드 기능 테스트
   - [ ] 폴더 생성/삭제
   - [ ] 파일 업로드
   - [ ] 배치 처리 실행

---

## 📈 의존성 관계

```
Phase 1: SFTP 날짜 조회 API ✅
    ↓
Phase 2: 케이스 분류 API ✅
    ↓
Phase 3: Batch Create 수정 ✅
    ↓
┌─ Phase 4: 캘린더 상태 시각화 UI (진행 중) 🔄
│           ↓
│  Phase 6: 통합 테스트 (예정)
│
└─ Phase 5: 업로드 기능 (독립적) 🔜
            ↓
    Phase 6: 통합 테스트 (예정)
```

**병렬 진행 가능**:
- Phase 4와 Phase 5는 독립적이므로 병렬 진행 가능
- Phase 6은 Phase 4, 5 모두 완료 후 진행

---

## 💡 주요 개선사항 상세

### 개선 1: 캘린더 중심 UI

**목표**: 사용자가 캘린더를 보고 처리해야 할 날짜를 직관적으로 선택

**구현**:
- flatpickr 캘린더를 최상단에 배치
- 가능한 날짜는 활성화 (텍스트 검정색)
- 불가능한 날짜는 비활성화 (회색)
- 처리 상태별 배경색 적용

---

### 개선 2: 상태 시각화

**목표**: 각 날짜의 처리 현황을 한눈에 파악

**구현**:
```javascript
// date-stats API 응답 활용
{
  "date": "20260315",
  "file_count": 15,
  "processed_count": 15,
  "status": "completed"  // ← 이 정보를 캘린더에 시각화
}
```

**표시 방식**:
- Status 아이콘 (✅/⚠️/⏳)
- 배경색 변경
- 파일 개수 배지

---

### 개선 3: 동적 선택 정보 카드

**목표**: 사용자가 범위를 선택할 때 실시간으로 정보 제공

**표시 내용**:
- 선택된 범위 (YYYY-MM-DD ~ YYYY-MM-DD)
- 가능한 범위 (YYYY-MM-DD ~ YYYY-MM-DD)
- 선택된 파일 총 개수
- 상태별 날짜 분포 (완료/부분/대기)

**업데이트 시점**:
- 캘린더에서 범위 선택 시 자동 업데이트
- 선택 해제 시 카드 숨김

---

## 🔧 기술 고려사항

### flatpickr 커스터마이징

flatpickr는 기본적으로 월별 캘린더만 제공하므로, 상태 아이콘을 추가하려면:

**방안 1: DOM 후처리 (현재 선택)**
```javascript
// flatpickr 초기화 후
const calendarDays = document.querySelectorAll('.flatpickr-day');
calendarDays.forEach(day => {
    // 상태 아이콘 추가
    const statue = getStatus(day.date);
    day.innerHTML += `<span>${getStatusIcon(status)}</span>`;
});
```

**방안 2: 커스텀 렌더러 사용**
- 더 복잡하지만 성능이 나을 수 있음
- 필요 시 추후 고려

### 성능 최적화

- 큰 달력에서 많은 DOM 조작 시 성능 저하 가능
- 필요시 requestAnimationFrame() 사용
- 또는 더 가벼운 캘린더 라이브러리로 교체 가능

---

## 📝 문서 구조

```
docs/select_target/
├─ README.md                    # 전체 계획 요약 (기존)
├─ PLAN.md                      # 원본 상세 계획
├─ CODE_REVIEW.md               # 기존 코드 재활용 검토
├─ UPLOAD_FEATURE.md            # Phase 5: 업로드 기능
├─ PHASE4_REVISED.md            # Phase 4 개정 계획 (NEW)
└─ PHASE_PLAN_REVISED.md        # 전체 개정 계획 (THIS FILE)
```

---

## ⚠️ 주의사항

### 1. 기존 코드와의 호환성
- 기존 PLAN.md의 API 명세는 변경 없음
- 프론트엔드 UI만 개선
- 백엔드 수정 불필요

### 2. 환경별 테스트
- Mock 데이터 (APP_ENV=local)
- Dev 환경 (APP_ENV=dev)
- 각 환경에서 캘린더 표시 확인 필요

### 3. 브라우저 호환성
- flatpickr: IE 11 미지원 (현대 브라우저는 모두 지원)
- CSS Grid: IE 부분 지원 (대체 방안 필요 시)

---

## 🎓 학습 기록

### 기존 계획의 장점 ✅
- 명확한 케이스 분류 (4가지)
- 체계적인 API 설계
- 프론트엔드 기본 구조 제공

### 사용자 피드백으로 개선된 점 ✅
- **캘린더 중심 UI** - 사용자 경험 개선
- **상태 시각화** - 한눈에 전체 상황 파악
- **동적 정보** - 실시간 피드백

### 향후 고려할 사항
- 성능 모니터링 (DOM 조작 최적화)
- 접근성 개선 (키보드 네비게이션)
- 국제화 (다국어 지원)

---

## ✅ 다음 단계

### 즉시 실행 (이번 주)
1. [PHASE4_REVISED.md](PHASE4_REVISED.md) 검토 및 피드백
2. Step 1-2 진행 (HTML 구조 변경)
3. Step 3-4 진행 (JavaScript & CSS)

### 1주 후 (다음 주)
1. Phase 4 테스트 완료
2. Phase 5 구현 시작 (또는 병렬)

### 2주 후
1. Phase 4, 5 완료
2. Phase 6 통합 테스트

---

## 📞 논의사항

**확인이 필요한 부분**:

1. ✅ **상태 시각화 디자인** - 현재 계획의 색상/아이콘이 적절한가?
2. ✅ **성능 우려** - flatpickr DOM 조작의 성능 영향도는?
3. ✅ **커스터마이징 범위** - flatpickr를 얼마나 수정할 것인가?
4. ✅ **추가 기능** - 상태 필터, 월 요약 등은 필요한가?

---

## 📌 결론

**Phase 4 개선의 효과**:
- ✅ 사용자가 캘린더에서 **한눈에** 상황 파악 가능
- ✅ 실시간 **선택 정보** 제공으로 결정 용이
- ✅ **상태별 시각화**로 직관성 극대화

**구현 가능성**: ⭐⭐⭐⭐⭐ (매우 높음)
- 필요한 API 모두 구현됨
- 추가 라이브러리 불필요
- JavaScript 수정만으로 완성 가능

**예상 일정**:
- Phase 4: 3월 24일 (5-7시간)
- Phase 5: 3월 31일 (3-4시간)
- Phase 6: 4월 7일 (2-3시간)
- **총 2주 이내 완성 가능**

---

## 📎 참조

- **기존 계획**: [PLAN.md](PLAN.md)
- **코드 리뷰**: [CODE_REVIEW.md](CODE_REVIEW.md)
- **업로드 기능**: [UPLOAD_FEATURE.md](UPLOAD_FEATURE.md)
- **Phase 4 상세**: [PHASE4_REVISED.md](PHASE4_REVISED.md)
