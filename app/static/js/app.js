/**
 * STT 사후 점검 시스템 - 메인 애플리케이션
 */

class App {
    constructor() {
        this.currentPage = 'dashboard';
        this.statusCheckInterval = null;
        this.init();
    }

    async init() {
        console.log('🚀 STT 사후 점검 시스템 시작...');
        
        try {
            // 이벤트 리스너 등록
            this.setupEventListeners();
            console.log('✅ 이벤트 리스너 등록 완료');
            
            // 초기 상태 로드
            await this.refreshStatus();
            console.log('✅ 상태 로드 완료');
            
            // 주기적 상태 업데이트
            this.statusCheckInterval = setInterval(() => this.refreshStatus(), 30000);
            
            console.log('✅ 초기화 완료');
        } catch (error) {
            console.error('❌ 초기화 실패:', error);
        }
    }

    setupEventListeners() {
        // 페이지 네비게이션
        document.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                this.switchPage(link.dataset.page);
            });
        });

        // 배치 처리 폼
        const batchForm = document.getElementById('batch-form');
        if (batchForm) {
            batchForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleBatchSubmit();
            });
        }

        // 검색 및 필터
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
            searchInput.addEventListener('input', () => {
                this.filterJobs();
            });
        }

        const statusFilter = document.getElementById('status-filter');
        if (statusFilter) {
            statusFilter.addEventListener('change', () => {
                this.filterJobs();
            });
        }

        // 모달 닫기
        const modalCloseBtn = document.getElementById('modal-close-btn');
        if (modalCloseBtn) {
            modalCloseBtn.addEventListener('click', () => {
                closeDetailModal();
            });
        }

        const modalCloseFooterBtn = document.getElementById('modal-close-btn-footer');
        if (modalCloseFooterBtn) {
            modalCloseFooterBtn.addEventListener('click', () => {
                closeDetailModal();
            });
        }

        // 모달 배경 클릭으로 닫기
        const modal = document.getElementById('detail-modal');
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    closeDetailModal();
                }
            });
        }
    }

    // ===== Page Navigation =====

    switchPage(pageName) {
        // Hide all pages
        document.querySelectorAll('.page').forEach(page => {
            page.classList.remove('active');
        });

        // Show selected page
        const page = document.getElementById(pageName);
        if (page) {
            page.classList.add('active');
        }

        // Update nav links
        document.querySelectorAll('.nav-link').forEach(link => {
            link.classList.remove('active');
            if (link.dataset.page === pageName) {
                link.classList.add('active');
            }
        });

        this.currentPage = pageName;

        // Page-specific setup
        if (pageName === 'history') {
            this.loadJobHistory();
        }
    }

    // ===== Dashboard =====

    async refreshStatus() {
        try {
            const response = await fetch('/healthz');
            if (!response.ok) {
                throw new Error(`Health check failed: ${response.status}`);
            }
            
            const status = await response.json();
            this.updateStatusDisplay(status);
        } catch (error) {
            console.error('상태 조회 실패:', error);
            const statusText = document.getElementById('status-text');
            if (statusText) {
                statusText.textContent = '오류';
            }
        }
    }

    updateStatusDisplay(status) {
        // Uptime
        if (status.uptime_seconds !== undefined) {
            const uptimeSeconds = status.uptime_seconds;
            const uptime = this.formatUptime(uptimeSeconds);
            const uptimeEl = document.getElementById('uptime');
            if (uptimeEl) {
                uptimeEl.textContent = uptime;
            }
        }

        // Environment
        const envEl = document.getElementById('env');
        if (envEl) {
            envEl.textContent = status.app_env || 'unknown';
        }

        // Status indicator
        const statusDot = document.querySelector('.status-dot');
        if (statusDot && status.status === 'ok') {
            statusDot.style.backgroundColor = '#10b981';
            const statusText = document.getElementById('status-text');
            if (statusText) {
                statusText.textContent = '정상';
            }
        }
    }

    // ===== Batch Processing =====

    async handleBatchSubmit() {
        const startDateInput = document.getElementById('start-date');
        const endDateInput = document.getElementById('end-date');

        if (!startDateInput || !endDateInput) {
            alert('날짜 입력 필드를 찾을 수 없습니다.');
            return;
        }

        const startDate = startDateInput.value.replace(/-/g, '');
        const endDate = endDateInput.value.replace(/-/g, '');

        if (!startDate || !endDate) {
            alert('시작 날짜와 종료 날짜를 입력하세요.');
            return;
        }

        if (startDate > endDate) {
            alert('시작 날짜가 종료 날짜보다 클 수 없습니다.');
            return;
        }

        try {
            // 진행 상황 표시
            const progressContainer = document.getElementById('progress-container');
            const resultsContainer = document.getElementById('results-container');
            
            if (progressContainer) progressContainer.style.display = 'block';
            if (resultsContainer) resultsContainer.style.display = 'none';

            // 배치 작업 제출
            const response = await fetch('/process/batch/submit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ start_date: startDate, end_date: endDate })
            });

            if (!response.ok) throw new Error('Batch submission failed');
            
            const data = await response.json();
            const jobId = data.job_id;
            console.log(`✅ 배치 작업 제출: ${jobId}`);

            // 작업 모니터링 시작
            this.monitorBatchJob(jobId);
        } catch (error) {
            alert(`배치 처리 실패: ${error.message}`);
            console.error('배치 처리 오류:', error);
        }
    }

    async monitorBatchJob(jobId) {
        const maxAttempts = 1800; // 30분
        let attempts = 0;

        const checkStatus = async () => {
            try {
                const response = await fetch(`/process/batch/status/${jobId}`);
                if (!response.ok) throw new Error('Status check failed');
                
                const status = await response.json();

                // 진행 상황 업데이트 (running 상태에서도 결과 수 표시)
                if (status.status === 'running' || status.status === 'completed') {
                    const completed = status.results ? status.results.length : 0;
                    const progressCount = document.getElementById('progress-count');
                    const progressStatus = document.getElementById('progress-status');
                    
                    if (progressCount) {
                        progressCount.textContent = `${completed}개 처리 중...`;
                    }
                    if (progressStatus) {
                        progressStatus.textContent = status.status === 'running' ? '🔄 실행 중...' : '✅ 처리 완료';
                    }
                }

                // 완료 또는 오류
                if (status.status === 'completed' || status.status === 'failed') {
                    console.log('✅ 배치 처리 완료:', status);
                    this.displayBatchResults(status, jobId);
                    return;
                }

                // 계속 모니터링 (3초 주기)
                if (attempts < maxAttempts) {
                    attempts++;
                    setTimeout(checkStatus, 3000);
                } else {
                    alert('작업 모니터링 타임아웃');
                }
            } catch (error) {
                console.error('상태 조회 오류:', error);
                attempts++;
                if (attempts < maxAttempts) {
                    setTimeout(checkStatus, 3000);
                }
            }
        };

        checkStatus();
    }

    displayBatchResults(status, jobId) {
        const progressContainer = document.getElementById('progress-container');
        const resultsContainer = document.getElementById('results-container');
        
        if (progressContainer) progressContainer.style.display = 'none';
        if (resultsContainer) resultsContainer.style.display = 'block';

        const results = status.results || [];
        const successCount = results.filter(r => r.success).length;
        const errorCount = results.filter(r => !r.success).length;

        // 요약
        const resultTotal = document.getElementById('result-total');
        const resultSuccess = document.getElementById('result-success');
        const resultError = document.getElementById('result-error');
        
        if (resultTotal) resultTotal.textContent = results.length;
        if (resultSuccess) resultSuccess.textContent = successCount;
        if (resultError) resultError.textContent = errorCount;

        // 테이블에 결과 렌더링
        const resultsTableBody = document.querySelector('#results-table tbody');
        if (resultsTableBody) {
            resultsTableBody.innerHTML = results.map(result => `
                <tr class="${result.success ? 'success-row' : 'error-row'}">
                    <td>${result.date || '-'}</td>
                    <td>${result.filename || `파일 #${results.indexOf(result) + 1}`}</td>
                    <td>
                        <span class="badge ${result.success ? 'success' : 'error'}">
                            ${result.success ? '성공' : '실패'}
                        </span>
                    </td>
                    <td>
                        ${result.success ? 
                            (result.detected_issues ? `누락: ${result.detected_issues.length}건` : '완료') :
                            (result.error || '처리 실패')}
                    </td>
                </tr>
            `).join('');
        }

        // 작업 저장
        window.currentJob = {
            job_id: jobId,
            status: status.status,
            results: results,
            created_at: new Date().toISOString()
        };

        // 스크롤
        if (resultsContainer) {
            resultsContainer.scrollIntoView({ behavior: 'smooth' });
        }
        
        // 자동으로 이력 탭으로 전환하고 결과 표시
        console.log('✅ 배치 처리 완료, 이력 탭으로 전환');
        setTimeout(() => {
            this.switchPage('history');
            // loadJobHistory 호출
            this.loadJobHistory();
        }, 500);
    }

    // ===== Job History & Detail View =====

    async loadJobHistory() {
        try {
            // 메모리에서 현재 작업 로드
            const jobs = window.currentJob ? [window.currentJob] : [];
            this.displayJobList(jobs);
        } catch (error) {
            console.error('작업 이력 로드 실패:', error);
        }
    }

    displayJobList(jobs) {
        const container = document.getElementById('jobs-list');
        
        if (!container) return;

        if (!jobs || jobs.length === 0) {
            container.innerHTML = '<p class="empty-state">작업 이력이 없습니다</p>';
            return;
        }

        container.innerHTML = jobs.map(job => this.renderJobItem(job)).join('');

        // 확장 버튼 이벤트
        document.querySelectorAll('.job-toggle').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const jobItem = btn.closest('.job-item');
                const fileResults = jobItem?.querySelector('.file-results');
                if (fileResults) {
                    const isHidden = fileResults.style.display === 'none';
                    fileResults.style.display = isHidden ? 'block' : 'none';
                    btn.classList.toggle('expanded', isHidden);
                }
            });
        });

        // 상세보기 버튼 이벤트
        document.querySelectorAll('.view-details-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const fileIndex = parseInt(btn.dataset.fileIndex);
                const jobItem = btn.closest('.job-item');
                const jobId = jobItem?.dataset.jobId;
                
                if (window.currentJob && window.currentJob.job_id === jobId) {
                    this.showDetailModal(window.currentJob, fileIndex);
                }
            });
        });
    }

    renderJobItem(job) {
        const successCount = job.results ? job.results.filter(r => r.success).length : 0;
        const errorCount = job.results ? job.results.filter(r => !r.success).length : 0;
        const totalOmissions = job.results ? job.results.reduce((sum, r) => {
            return sum + (r.detected_issues ? r.detected_issues.length : 0);
        }, 0) : 0;

        const createdDate = job.created_at ? new Date(job.created_at).toLocaleString('ko-KR') : '-';

        return `
            <div class="job-item" data-job-id="${job.job_id}">
                <div class="job-header">
                    <div class="job-header-info">
                        <div class="job-id">작업 ID: ${job.job_id.substring(0, 8)}...</div>
                        <div class="job-meta">
                            생성: ${createdDate} | 
                            상태: <span class="badge">${this.getStatusText(job.status)}</span>
                        </div>
                    </div>
                    <div class="job-stats">
                        <div class="job-stat">
                            <span class="job-stat-label">처리 파일:</span>
                            <span class="job-stat-value">${job.results ? job.results.length : 0}</span>
                        </div>
                        <div class="job-stat success">
                            <span class="job-stat-label">성공:</span>
                            <span class="job-stat-value">${successCount}</span>
                        </div>
                        <div class="job-stat error">
                            <span class="job-stat-label">실패:</span>
                            <span class="job-stat-value">${errorCount}</span>
                        </div>
                        <div class="job-stat">
                            <span class="job-stat-label">총 누락:</span>
                            <span class="job-stat-value">${totalOmissions}</span>
                        </div>
                    </div>
                    <button class="job-toggle">▼</button>
                </div>
                <div class="file-results" style="display: none;">
                    ${this.renderFileResults(job)}
                </div>
            </div>
        `;
    }

    renderFileResults(job) {
        if (!job.results || job.results.length === 0) {
            return '<p class="empty-state">처리 결과가 없습니다</p>';
        }

        return job.results.map((result, index) => `
            <div class="file-result-item ${result.success ? 'success' : 'error'}">
                <div class="file-result-info">
                    <div class="file-result-name">${result.filename || `파일 #${index + 1}`}</div>
                    <div class="file-result-meta">
                        날짜: ${result.date} | 
                        ${result.detected_issues ? `누락: ${result.detected_issues.length}건` : result.success ? '완료' : result.error || '처리 실패'}
                    </div>
                </div>
                <div class="file-result-action">
                    <span class="file-result-badge ${result.success ? 'success' : 'error'}">
                        ${result.success ? '성공' : '실패'}
                    </span>
                    <button class="view-details-btn" data-file-index="${index}">상세보기</button>
                </div>
            </div>
        `).join('');
    }

    showDetailModal(job, fileIndex) {
        const result = job.results[fileIndex];
        if (!result) return;

        // 모달 헤더
        const modalTitle = document.getElementById('modal-title');
        if (modalTitle) {
            modalTitle.textContent = `파일 상세 분석: ${result.filename || `파일 #${fileIndex + 1}`}`;
        }

        // 원본 텍스트
        const originalText = document.getElementById('original-text');
        if (originalText) {
            if (result.success) {
                originalText.textContent = result.text || '원본 텍스트를 불러올 수 없습니다.';
            } else {
                originalText.textContent = `[처리 실패]\n\n오류: ${result.error || '알 수 없는 오류'}\n\n이 파일은 처리에 실패했습니다.`;
            }
        }

        // 분석 결과 요약
        const category = document.getElementById('modal-category');
        const summary = document.getElementById('modal-summary');
        const omissionNum = document.getElementById('modal-omission-num');
        
        if (result.success) {
            if (category) category.textContent = result.category || '-';
            if (summary) summary.textContent = result.summary || '-';
            if (omissionNum) omissionNum.textContent = result.omission_num || '0';
        } else {
            if (category) category.textContent = '처리 실패';
            if (summary) summary.textContent = result.error || '알 수 없는 오류';
            if (omissionNum) omissionNum.textContent = '-';
        }

        // 이슈 목록
        const issuesContainer = document.getElementById('issues-container');
        if (issuesContainer) {
            if (result.success && result.detected_issues && result.detected_issues.length > 0) {
                issuesContainer.innerHTML = result.detected_issues.map((issue, idx) => `
                    <div class="issue-item">
                        <div class="issue-index">#${idx + 1}</div>
                        <div class="issue-step"><strong>항목:</strong> ${issue.step || ''}</div>
                        <div class="issue-reason"><strong>근거:</strong> ${issue.reason || ''}</div>
                        <div class="issue-category"><strong>분류:</strong> ${issue.category || ''}</div>
                    </div>
                `).join('');
            } else if (result.success) {
                issuesContainer.innerHTML = '<p class="empty-state">누락된 항목이 없습니다</p>';
            } else {
                issuesContainer.innerHTML = '<p class="empty-state">처리 실패로 인해 분석 결과를 표시할 수 없습니다</p>';
            }
        }

        // 현재 결과 저장 (내보내기용)
        window.currentDetailResult = result;

        // 모달 표시
        const modal = document.getElementById('detail-modal');
        if (modal) {
            modal.classList.add('show');
            modal.style.display = 'flex';
        }
    }

    filterJobs() {
        const searchInput = document.getElementById('search-input');
        const statusFilter = document.getElementById('status-filter');
        
        if (!searchInput) return;

        const searchText = searchInput.value.toLowerCase();
        const statusFilterValue = statusFilter ? statusFilter.value : '';

        document.querySelectorAll('.job-item').forEach(jobItem => {
            const jobId = jobItem.dataset.jobId?.toLowerCase() || '';
            const matchesSearch = !searchText || jobId.includes(searchText);
            const matchesStatus = !statusFilterValue || true;

            jobItem.style.display = (matchesSearch && matchesStatus) ? 'block' : 'none';
        });
    }

    downloadResults() {
        if (!window.currentDetailResult) {
            alert('다운로드할 분석 결과가 없습니다.');
            return;
        }

        const result = window.currentDetailResult;
        const content = `STT 사후 점검 결과 보고서
================================

파일명: ${result.filename || '미지정'}
날짜: ${result.date || '미지정'}
처리 시간: ${result.processing_time_ms || '-'}ms

[종합 정보]
카테고리: ${result.category || '-'}
요약: ${result.summary || '-'}
누락건수: ${result.omission_num || '0'}

[점검 항목]
${result.detected_issues && result.detected_issues.length > 0 ? result.detected_issues.map((issue, idx) => `
${idx + 1}. ${issue.step || '항목'}
   근거: ${issue.reason || ''}
   분류: ${issue.category || ''}
`).join('') : '적절한 점검 결과입니다'}

[원본 텍스트]
${result.text || '텍스트 없음'}

================================
생성 시간: ${new Date().toLocaleString('ko-KR')}`;

        const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `analysis_${result.filename || 'report'}_${Date.now()}.txt`;
        link.click();
        URL.revokeObjectURL(link.href);
    }

    // ===== Utilities =====

    formatUptime(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        return `${hours}시간 ${minutes}분`;
    }

    getStatusText(status) {
        const statusMap = {
            'pending': '대기 중',
            'running': '실행 중',
            'completed': '완료',
            'failed': '실패',
            'success': '성공',
            'error': '오류',
        };
        return statusMap[status] || status;
    }
}

// 전역 함수들
function closeDetailModal() {
    const modal = document.getElementById('detail-modal');
    if (modal) {
        modal.classList.remove('show');
        modal.style.display = 'none';
    }
}

// 앱 초기화
document.addEventListener('DOMContentLoaded', () => {
    console.log('📄 DOM 로드 완료');
    try {
        window.app = new App();
    } catch (error) {
        console.error('❌ 앱 초기화 실패:', error);
        alert(`앱 초기화 실패: ${error.message}`);
    }
});

// 전역 에러 핸들러
window.addEventListener('error', (event) => {
    console.error('❌ 전역 에러:', event.error);
});
