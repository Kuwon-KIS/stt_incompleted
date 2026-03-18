# Phase 4 개선: 인라인 캘린더 구현 계획 (2026년 3월 17일)

## 📋 현황 분석

### 현재 구현 상태 (AS-IS)
```
사용자 흐름:
1. 배치 처리 페이지 진입
2. "범위 선택 (클릭)" input 필드 표시
3. 사용자 클릭 → flatpickr 팝업 캘린더 출현
4. 날짜 범위 선택 후 캘린더 닫힘
5. "분석 및 옵션 확인" 버튼 클릭
6. 분석 결과 표시

문제점:
- 캘린더가 숨겨져 있다가 클릭했을 때만 나타남
- 가능한 날짜범위/파일 개수/상태 정보를 미리 볼 수 없음
- 사용자가 informed decision을 할 수 없음
```

### 사용자 요구사항 (TO-BE)
```
사용자 흐름:
1. 배치 처리 페이지 진입
2. 즉시 캘린더가 보이고, 다음 정보 표시:
   - 가능한 날짜 범위 (min_date ~ max_date)
   - 각 날짜별 파일 개수 (배지)
   - 각 날짜별 처리 상태 (배경색: 완료/부분/대기/불가)
3. 캘린더에서 범위를 마우스로 선택
4. 선택하면 자동으로 선택 정보 카드 표시
5. "분석 및 옵션 확인" 버튼 클릭
6. 분석 결과 표시

장점:
- 한눈에 전체 상황 파악 가능
- 선택 전에 정보를 완전히 볼 수 있음
- 더 나은 사용자 경험
```

---

## 🎯 구현 방안 검토

### Q1: 가능한가?
✅ **YES, 매우 가능함**

**근거**:
1. **flatpickr 라이브러리 지원**
   - `inline: true` 옵션 지원 → 팝업이 아닌 항상 보이는 캘린더 생성 가능
   - `range` mode 지원 → 범위 선택 가능
   - DOM 이벤트 지원 → 선택 시 자동 업데이트 가능

2. **필요한 데이터 이미 준비됨**
   - ✅ GET /api/admin/date-range → min_date, max_date, available_dates
   - ✅ GET /api/admin/date-stats → {date, file_count, processed_count, status}
   - ✅ JavaScript에서 window.batchDateRange, window.dateStatusMap 관리 중

3. **날짜별 정보 표시 이미 구현됨**
   - ✅ addDateBadgesAndStatus() 함수 존재
   - ✅ 배경색 기반 상태 표시 (CSS 완성)
   - ✅ 파일 개수 배지 로직 존재

---

## 📊 구체적 수정 계획

### Phase 4.1: HTML 구조 변경 (Step 1)

**파일**: `app/static/index.html`

**변경사항**:
```diff
- <input type="text" id="batch-calendar" placeholder="범위 선택 (클릭)" ...>
+ <!-- 인라인 캘린더 컨테이너 -->
+ <div id="batch-calendar" style="margin-bottom: 20px;"></div>
```

**이유**:
- flatpickr의 `inline: true` 옵션은 div에 마운트될 때만 정상 작동
- input은 팝업 캘린더만 지원함

---

### Phase 4.2: JavaScript 설정 변경 (Step 2)

**파일**: `app/static/js/app.js` → `initializeCalendar()` 메서드

**변경사항**:
```javascript
// 기존 (라인 1149-1153)
const fpInstance = flatpickr(calendarEl, {
    mode: 'range',
    dateFormat: 'Y-m-d',
    minDate: minDate,
    maxDate: maxDate,
    locale: 'ko',
    
// 변경 (추가 옵션)
const fpInstance = flatpickr(calendarEl, {
    mode: 'range',
    dateFormat: 'Y-m-d',
    minDate: minDate,
    maxDate: maxDate,
    locale: 'ko',
    
    // 인라인 캘린더 설정
    inline: true,                          // ← 항상 보이게
    defaultDate: [minDate],                // ← 기본 시작일
    static: false,                         // ← 상호작용 가능하게
    
    // 이벤트 핸들러
    onChange: (selectedDates) => {
        console.log('📅 onChange triggered:', selectedDates);
        this.onCalendarDateChange(selectedDates);
    },
    onReady: () => {
        console.log('📅 flatpickr onReady triggered - 상태 표시 시작');
        this.addDateBadgesAndStatus();
    }
});
```

**이유**:
- `inline: true` → 캘린더 항상 표시
- `defaultDate` → 사용자 편의성
- 나머지는 기존 코드 유지

---

### Phase 4.3: Status 표시기 이모지 제거 (Step 3)

**파일들**:
1. `app/static/index.html` (라인 113-118)
2. `app/static/js/app.js` (addDateBadgesAndStatus 함수)
3. `app/static/css/style.css` (필요시)

**현재 Legend (HTML)**:
```html
<div style="padding: 6px; background-color: #d1fae5; color: #065f46;">완료</div>
<div style="padding: 6px; background-color: #fed7aa; color: #92400e;">부분</div>
<div style="padding: 6px; background-color: #dbeafe; color: #1e40af;">대기</div>
<div style="padding: 6px; background-color: #f3f4f6; color: #9ca3af;">불가</div>
```

**현재 상태**: 이미 이모지가 없는 텍스트 형식 ✅

**확인 필요**:
- addDateBadgesAndStatus()의 상태 아이콘/이모지 표시 코드 검토
- 불필요한 이모지 문자 제거

---

## 🔧 세부 구현 단계

### Step 1: HTML 구조 변경 (5분)
- `app/static/index.html` 라인 110-113 수정
- input → div 변경

### Step 2: flatpickr 옵션 수정 (5분)
- `app/static/js/app.js` 라인 1149-1165 수정
- `inline: true` 옵션 추가

### Step 3: 페이지 로드 시 데이터 순서 확인 (5분)
- `initializeBatchCalendar()` 실행 순서 확인:
  1. loadBatchDateRange() ✅
  2. loadBatchDateStats() ✅
  3. initializeCalendar() ✅
  4. addDateBadgesAndStatus() ✅

### Step 4: 테스트 및 미세 조정 (15min)
- 로컬 APP_ENV=local 환경에서 테스트
- 캘린더 표시 확인
- 날짜별 상태색 표시 확인
- 범위 선택 동작 확인
- 선택 정보 카드 업데이트 확인

### Step 5: 이모지 제거 확인 (5분)
- Status 표시에서 불필요한 이모지/아이콘 제거

---

## ⚡ 핵심 변경사항 요약

| 항목 | 현재 | 개선 후 | 수정 파일 |
|------|------|--------|---------|
| 캘린더 표시 | 팝업 (클릭 시) | 항상 보입니다 | HTML, JS |
| 초기 정보 | 텍스트로만 | 캘린더 + 범례 + 상태색 | HTML |
| 사용자 경험 | 선택 전 정보 제한 | 전체 정보 미리 표시 | - |
| Status 표시 | 텍스트 + (이모지 있을 수 있음) | 텍스트 + 배경색 | JS, HTML |

---

## 📌 최종 확인

### 기술적 가능성
- ✅ flatpickr inline 모드 지원
- ✅ 필요한 API 및 데이터 준비됨
- ✅ 기존 코드 최소 수정 (2개 파일 수정)
- ✅ 추가 라이브러리 불필요

### 구현 시간
- **총 소요시간**: 약 35분
  - HTML 수정: 5분
  - JavaScript 수정: 5분
  - 데이터 흐름 확인: 5분
  - 테스트: 15분
  - 이모지 제거: 5분

### 위험 요소
- ⚠️ **매우 낮음**: 기존 API 모두 준비됨
- ⚠️ **최소**: flatpickr의 inline 모드는 표준 기능

---

## 🎓 구현 후 예상 결과

### Before (현재)
```
배치 처리 페이지 진입
       ↓
[클릭] → 캘린더 팝업 출현
       ↓
범위 선택 후 캘린더 닫힘
       ↓
분석 버튼 클릭
```

### After (개선 후)
```
배치 처리 페이지 진입
       ↓
✅ 캘린더 항상 보임
✅ 가능한 범위: 2026-03-15 ~ 2026-03-30 표시
✅ 각 날짜에 파일 개수와 상태색 표시
       ↓
캘린더에서 직접 범위 선택 가능
       ↓
선택 정보 카드 자동 업데이트
       ↓
분석 버튼 클릭
```

---

## ✅ 결론

**실행 가능성**: ⭐⭐⭐⭐⭐ (매우 높음)

**개선 효과**:
- ✅ 사용자가 캘린더에서 **한눈에** 전체 상황 파악 가능
- ✅ **정보 기반 의사결정** 가능
- ✅ 더 나은 **UX** 제공
- ✅ **단순한 코드 수정** (기존 로직 활용)

**다음 단계**: 위의 Step 1-5에 따라 구현 진행

---

## 📎 참조 파일
- `app/static/index.html` (라인 110-160)
- `app/static/js/app.js` (라인 1024-1290)
- `app/static/css/style.css` (라인 891-1150)
