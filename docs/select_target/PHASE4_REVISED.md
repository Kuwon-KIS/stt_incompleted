# Phase 4 개선: 캘린더 상태 시각화 UI 설계 (수정본)

## 개요
기존 Phase 4 계획을 개선하여 **캘린더 중심의 UI**로 재설계.
사용자가 캘린더에서 직관적으로 보고 선택할 수 있도록 **상태별 시각화**를 강화.

---

## 1. 주요 변경사항 (vs 기존 PLAN.md)

### 1.1 UI 레이아웃 순서 변경
**기존 (PLAN.md)**:
```
1. 처리 가능 범위 정보 (파란색 박스)
2. 캘린더 입력
3. 분석 버튼
4. 분석 결과 (조건부 표시)
```

**개선** (이번 계획):
```
1. 캘린더 (먼저 표시)
   - 가능한 날짜: 텍스트 활성화
   - 불가능한 날짜: 회색 비활성화
   - 처리 상태별 색상 표시 (일시 표시)
   
2. 선택 정보 카드 (동적 표시)
   - "선택된 범위: YYYY-MM-DD ~ YYYY-MM-DD"
   - "가능한 범위: YYYY-MM-DD ~ YYYY-MM-DD"
   - 파일 요약 정보

3. 분석 버튼
4. 분석 결과 (조건부 표시)
```

### 1.2 상태 시각화 추가
date-stats의 `status` 필드를 캘린더에 표시:

```json
// date-stats API 응답 (이미 구현됨)
{
  "date": "20260315",
  "file_count": 15,
  "processed_count": 15,
  "status": "completed",  // ← 이 정보를 캘린더에 시각화
  "job_id": "abc123..."
}
```

**Status별 표시**:
- `"completed"`: ✅ 초록색 배경
- `"partial"`: ⚠️ 주황색 배경
- `"pending"`: ⏳ 회색 배경
- **처리 불가 (파일 없음)**: 흐린 회색

---

## 2. 데이터 흐름 (개선)

```
┌─ 페이지 로드 ────────────────────────┐
│                                      │
│ 1. 병렬 로드:                        │
│    - GET /api/admin/date-range      │
│    - GET /api/admin/date-stats       │
│    ↓                                 │
│    캘린더 렌더링 + 상태 아이콘       │
│                                      │
│ 2. 사용자 상호작용:                  │
│    - 캘린더에서 범위 선택            │
│    - 선택 정보 카드 업데이트         │
│    ↓                                 │
│    분석 버튼 활성화                  │
│                                      │
│ 3. 분석 (선택 사항):                 │
│    - POST /api/admin/batch-analysis │
│    ↓                                 │
│    Case별 옵션 렌더링                │
│                                      │
│ 4. 처리 시작:                        │
│    - POST /process/batch/create      │
│    ↓                                 │
│    결과 표시                         │
│                                      │
└──────────────────────────────────────┘
```

---

## 3. 개선된 UI 레이아웃

### 3.1 캘린더 섹션 (먼저 표시)

```html
┌─ 배치 처리 페이지 ─────────────────────────────────────┐
│                                                        │
│ 📅 날짜 범위 선택                                      │
│ ┌──────────────────────────────────────────────────┐  │
│ │ [캘린더 (flatpickr)]                              │ │
│ │ ┌─ 2026년 3월 ──────────────────────────┐        │ │
│ │ │ Sun Mon Tue Wed Thu Fri Sat           │        │ │
│ │ │              1   2  3✅  4⚠️           │        │ │
│ │ │  5✅ 6⚠️ 7⏳  8✅ 9   10  11           │        │ │
│ │ │ 12✅ 13✅ 14✅15✅16✅17⚠️18           │        │ │
│ │ │ 19  20  21  22  23  24  25           │        │ │
│ │ │ 26  27  28  29  30  31               │        │ │
│ │ └─────────────────────────────────────┘        │ │
│ │ 범례: ✅ 완료  ⚠️ 부분  ⏳ 대기  (흐린색) 불가  │ │
│ └──────────────────────────────────────────────────┘  │
│                                                        │
│ 📋 선택 정보                                           │
│ ┌──────────────────────────────────────────────────┐  │
│ │ 선택된 범위: 2026-03-10 ~ 2026-03-15             │  │
│ │ 가능한 범위: 2026-03-01 ~ 2026-03-31            │  │
│ │ 선택된 파일: 25개                                 │  │
│ │ 처리 현황: 완료 10개 / 부분 3개 / 대기 12개      │  │
│ └──────────────────────────────────────────────────┘  │
│                                                        │
│ [분석 및 옵션 확인] [초기화]                            │
│                                                        │
│ === (분석 결과 - 조건부 표시) ===                      │
│ [분석 결과 박스는 여기에 표시]                         │
│                                                        │
└────────────────────────────────────────────────────────┘
```

### 3.2 상태별 시각화

**캘린더 날짜 셀 디자인**:
```html
<div class="date-cell date-cell--completed">
    15
    <div class="date-icons">
        <span class="status-icon">✅</span>
        <span class="file-badge">5</span>
    </div>
</div>
```

**CSS 스타일**:
```css
.date-cell {
    position: relative;
    padding: 4px;
    border-radius: 4px;
    background-color: #f3f4f6;
    color: #6b7280;
    cursor: default;
}

/* Completed - 초록색 */
.date-cell--completed {
    background-color: #d1fae5;
    color: #065f46;
    font-weight: 600;
}

/* Partial - 주황색 */
.date-cell--partial {
    background-color: #fed7aa;
    color: #92400e;
    font-weight: 600;
}

/* Pending - 파란색 */
.date-cell--pending {
    background-color: #dbeafe;
    color: #1e40af;
    font-weight: 600;
}

/* Unavailable - 연한 회색 */
.date-cell--unavailable {
    opacity: 0.4;
    color: #9ca3af;
    cursor: not-allowed;
}

/* Selected range - 배경색 */
.date-cell--selected {
    background-color: #eff6ff;
    border: 2px solid #3b82f6;
}

.status-icon {
    position: absolute;
    top: 0;
    right: 0;
    font-size: 0.7em;
}

.file-badge {
    position: absolute;
    bottom: 0;
    left: 0;
    background-color: #2563eb;
    color: white;
    border-radius: 50%;
    width: 16px;
    height: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.6em;
    font-weight: bold;
}
```

---

## 4. 구현 세부사항

### 4.1 캘린더 렌더링 개선 (JavaScript)

**1단계: 데이터 로드 (병렬)**
```javascript
async switchToBatchPage() {
    // 병렬 로드
    await Promise.all([
        this.loadBatchDateRange(),    // /api/admin/date-range
        this.loadBatchDateStats()     // /api/admin/date-stats
    ]);
    
    // 모든 데이터 로드 후 캘린더 초기화
    this.initializeCalendar();
    this.addDateBadgesAndStatus();   // ← 상태 아이콘 추가
}
```

**2단계: 상태 정보 적용**
```javascript
async loadBatchDateStats() {
    const data = await api.getDateStats();
    
    // 날짜별 상태 맵 생성
    window.dateStatusMap = {};
    data.dates?.forEach(stat => {
        window.dateStatusMap[stat.date] = {
            status: stat.status,      // "completed" | "partial" | "pending"
            file_count: stat.total_files,
            processed_count: stat.processed_count
        };
    });
    
    console.log('📊 Date status map:', window.dateStatusMap);
}
```

**3단계: 캘린더 셀에 상태 표시**
```javascript
addDateBadgesAndStatus() {
    const calendarDays = document.querySelectorAll('.flatpickr-day');
    
    calendarDays.forEach(dayEl => {
        if (dayEl.classList.contains('disabled')) return; // 비활성 날짜 제외
        
        const dateStr = dayEl.getAttribute('data-datestr'); // YYYY-MM-DD
        const dateYYYYMMDD = dateStr.replace(/-/g, '');     // YYYYMMDD
        
        const stat = window.dateStatusMap[dateYYYYMMDD];
        
        if (stat) {
            // Status 클래스 추가
            dayEl.classList.add(`date-${stat.status}`);
            
            // Status 아이콘 추가
            const statusIcon = document.createElement('span');
            statusIcon.className = 'status-icon';
            statusIcon.textContent = this.getStatusIcon(stat.status);
            dayEl.appendChild(statusIcon);
            
            // 파일 개수 배지 추가
            if (stat.file_count > 0) {
                const badge = document.createElement('span');
                badge.className = 'file-badge';
                badge.textContent = stat.file_count;
                dayEl.appendChild(badge);
            }
        }
    });
}

getStatusIcon(status) {
    const icons = {
        'completed': '✅',
        'partial': '⚠️',
        'pending': '⏳'
    };
    return icons[status] || '';
}
```

### 4.2 선택 정보 카드 (동적 업데이트)

```javascript
onCalendarDateChange(selectedDates) {
    if (selectedDates.length === 2) {
        const startDate = selectedDates[0];
        const endDate = selectedDates[1];
        
        // 선택 범위의 상태 요약
        const summary = this.calculateSelectionSummary(startDate, endDate);
        
        // 선택 정보 카드 업데이트
        this.updateSelectionCard(summary);
        
        // 전역 변수 저장
        window.selectedDateRange = {
            start: this.formatDate(startDate),
            end: this.formatDate(endDate)
        };
    }
}

calculateSelectionSummary(startDate, endDate) {
    let totalFiles = 0;
    let completedCount = 0;
    let partialCount = 0;
    let pendingCount = 0;
    
    // 선택 범위의 모든 날짜 순회
    let current = new Date(startDate);
    while (current <= endDate) {
        const dateStr = this.formatDateAsYYYYMMDD(current);
        const stat = window.dateStatusMap[dateStr];
        
        if (stat) {
            totalFiles += stat.file_count;
            if (stat.status === 'completed') completedCount++;
            else if (stat.status === 'partial') partialCount++;
            else if (stat.status === 'pending') pendingCount++;
        }
        
        current.setDate(current.getDate() + 1);
    }
    
    return {
        totalFiles,
        completedCount,
        partialCount,
        pendingCount,
        daysCount: Math.floor((endDate - startDate) / (1000 * 60 * 60 * 24)) + 1
    };
}

updateSelectionCard(summary) {
    const card = document.getElementById('selection-info-card');
    if (!card) return;
    
    const startStr = this.formatDateForDisplay(window.selectedDateRange.start);
    const endStr = this.formatDateForDisplay(window.selectedDateRange.end);
    
    card.innerHTML = `
        <div class="selection-info">
            <p><strong>선택된 범위:</strong> ${startStr} ~ ${endStr}</p>
            <p><strong>가능한 범위:</strong> ${this.formatDateForDisplay(window.batchDateRange.min_date)} ~ ${this.formatDateForDisplay(window.batchDateRange.max_date)}</p>
            <div class="selection-stats" style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #e5e7eb;">
                <p><strong>처리 현황 (${summary.daysCount}일):</strong></p>
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-top: 8px;">
                    <div class="stat-box stat-total"><span>${summary.totalFiles}</span>개 파일</div>
                    <div class="stat-box stat-completed"><span>${summary.completedCount}</span>일 완료</div>
                    <div class="stat-box stat-partial"><span>${summary.partialCount}</span>일 부분</div>
                    <div class="stat-box stat-pending"><span>${summary.pendingCount}</span>일 대기</div>
                </div>
            </div>
        </div>
    `;
}
```

---

## 5. HTML 마크업 변경

### 5.1 구조 변경 (index.html)

**변경 전**:
```html
<!-- Date Range Info (먼저) -->
<div class="card" style="background-color: #f0f4f8;">
    ...범위 정보...
</div>

<!-- Calendar (나중) -->
<div class="card">
    <input id="batch-calendar" ...>
    <button>분석 버튼</button>
</div>
```

**변경 후**:
```html
<!-- Calendar (먼저) -->
<div class="card">
    <h3 style="margin-top: 0;">📅 날짜 범위 선택</h3>
    <input id="batch-calendar" placeholder="범위 선택 (클릭)" ...>
</div>

<!-- Selection Info (동적 표시) -->
<div id="selection-info-card" style="display: none;" class="card">
    <!-- 선택 정보 카드 -->
</div>

<!-- Date Range Info (범위 표시) -->
<div class="card" style="background-color: #f0f4f8;">
    <p style="margin: 0; font-size: 0.9em; color: #666;">📝 가능한 범위</p>
    <p id="date-range-info" style="margin: 8px 0 0 0; font-size: 1em;">로딩 중...</p>
</div>

<!-- Analyze Button -->
<button id="analyze-batch-btn" class="btn-primary" style="width: 100%;">
    📊 분석 및 옵션 확인
</button>

<!-- Analysis Result (조건부) -->
<div id="analysis-result-container" style="display: none;">
    ...분석 결과...
</div>
```

### 5.2 CSS 추가 (app.css)

```css
/* 상태별 날짜 셀 스타일 */
.flatpickr-day.date-completed {
    background-color: #d1fae5;
    color: #065f46;
    font-weight: 600;
}

.flatpickr-day.date-partial {
    background-color: #fed7aa;
    color: #92400e;
    font-weight: 600;
}

.flatpickr-day.date-pending {
    background-color: #dbeafe;
    color: #1e40af;
    font-weight: 600;
}

/* 선택 정보 카드 */
#selection-info-card {
    margin: 12px 0;
}

.selection-info p {
    margin: 8px 0;
    font-size: 0.95em;
}

/* 통계 박스 */
.stat-box {
    padding: 8px;
    border-radius: 4px;
    text-align: center;
    font-size: 0.9em;
}

.stat-box span {
    display: block;
    font-size: 1.2em;
    font-weight: bold;
    margin-bottom: 2px;
}

.stat-total { background-color: #f3f4f6; color: #374151; }
.stat-completed { background-color: #d1fae5; color: #065f46; }
.stat-partial { background-color: #fed7aa; color: #92400e; }
.stat-pending { background-color: #dbeafe; color: #1e40af; }
```

---

## 6. 구현 순서 (Phase 4 상세)

### Step 1: 백엔드 데이터 확인 (검증)
- [x] `GET /api/admin/date-stats` - status 필드 반환 확인
- [x] `GET /api/admin/date-range` - available_dates 반환 확인

### Step 2: HTML 구조 변경 (index.html)
- [ ] 캘린더 섹션을 맨 앞으로 이동
- [ ] 선택 정보 카드 추가 (숨김 상태)
- [ ] 날짜 범위 정보 카드 아래로 이동
- [ ] CSS 클래스 추가

### Step 3: JavaScript 개선 (app.js)
- [ ] `loadBatchDateStats()` - dateStatusMap 생성
- [ ] `addDateBadgesAndStatus()` - 상태 아이콘 + 배지 추가
- [ ] `onCalendarDateChange()` - 선택 정보 카드 업데이트
- [ ] `calculateSelectionSummary()` - 범위 요약 계산
- [ ] `updateSelectionCard()` - 카드 렌더링

### Step 4: CSS 스타일 추가 (app.css)
- [ ] 상태별 날짜 셀 스타일
- [ ] 선택 정보 카드 스타일
- [ ] 통계 박스 스타일

### Step 5: 테스트 & 데이터 검증
- [ ] Mock/Test 데이터로 캘린더 표시 확인
- [ ] 상태 아이콘 표시 확인
- [ ] 범위 선택 시 선택 정보 카드 업데이트 확인
- [ ] 분석 버튼 → Case별 결과 표시 확인

---

## 7. 주의사항

### 7.1 기술적 고려사항
1. **flatpickr 커스터마이징**
   - flatpickr는 기본적으로 월별 캘린더만 표시
   - 상태 아이콘을 추가하려면 flatpickr의 내부 DOM을 접근
   - 또는 flatpickr의 `onReady` 콜백에서 후처리

2. **성능 최적화**
   - 큰 달력에서 많은 상태 아이콘을 그리면 성능 저하 가능
   - 필요시 가상 스크롤링(virtualization) 고려

3. **브라우저 호환성**
   - CSS Grid 사용 (IE 미지원, 하지만 현대 브라우저는 모두 지원)

### 7.2 사용자 경험
1. **시각적 명확성**
   - 범례(legend)를 명확하게 표시
   - 마우스 호버 시 상세 정보 팝오버(tooltip) 추가 고려

2. **상태 업데이트**
   - 페이지 로드 시 상태 아이콘 업데이트
   - 처리 완료 후 상태 아이콘 자동 갱신 (polling 또는 WebSocket)

---

## 8. 이후 작업 (Phase 5 이상)

### Phase 5: 업로드 기능 (독립적)
- 사용자 폴더 생성 & 파일 업로드
- 업로드 폴더 기반 배치 처리

### Phase 6: 통합 테스트
- 캘린더 UI 완성 후 E2E 테스트
- 모든 케이스별 시나리오 검증

### Phase 7: 추가 기능 (선택사항)
- 상태별 필터 (완료된 날짜만 보기 등)
- 월 단위 요약 정보
- 성능 개선 (캐싱, 최적화)

---

## 9. 예상 작업량

| 항목 | 예상 시간 | 난이도 |
|------|----------|--------|
| Step 1: 백엔드 검증 | 0.5시간 | 낮음 |
| Step 2: HTML 구조 변경 | 0.5시간 | 낮음 |
| Step 3: JavaScript 개선 | 2시간 | 중 |
| Step 4: CSS 스타일 | 1시간 | 낮음 |
| Step 5: 테스트 | 1시간 | 중 |
| **총합** | **5시간** | **중** |

---

## 10. 체크리스트

- [ ] dateStatusMap 생성 로직 정확성 확인
- [ ] 상태별 색상 시각화 계획 검토
- [ ] flatpickr 커스터마이징 방법 확인
- [ ] 선택 정보 카드 UI/UX 검토
- [ ] 성능 영향도 분석 (많은 아이콘 렌더링)
- [ ] 다양한 상태 조합으로 테스트

---

## 11. 결론

**개선 효과**:
1. ✅ 캘린더 **중심** UI - 사용자가 한 눈에 전체 상황 파악 가능
2. ✅ **상태 시각화** - 각 날짜의 처리 현황을 아이콘/색상으로 표시
3. ✅ **동적 정보 카드** - 범위 선택 시 자동 업데이트
4. ✅ **선택 지원** - 재처리/부분 처리 선택 시 참고 정보 제공

**구현 가능성**: ✅ 높음
- flatpickr 라이브러리 이미 로드됨
- 필요한 API 모두 구현되어 있음
- 추가 라이브러리 불필요
- JavaScript 수정만으로 완성 가능

**다음 단계**: Step 1 검증부터 시작하여 순차적으로 진행
