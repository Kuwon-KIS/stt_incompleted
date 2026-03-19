/**
 * STT 사후 점검 시스템 - 메인 애플리케이션
 */

class App {
    constructor() {
        this.currentPage = 'dashboard';
        this.statusCheckInterval = null;
        this.autoAnalysisDebounceTimer = null;  // Auto-analysis debounce timer
        this.init();
    }

    async init() {
        
        
        try {
            // 이벤트 리스너 등록
            this.setupEventListeners();
            
            
            // 초기 상태 로드
            await this.refreshStatus();
            // Dashboard 진입 시 통계 데이터 로드
            await this.loadDashboardStats();
            
            // 주기적 상태 업데이트 (모든 페이지: 180초)
            this.statusCheckInterval = setInterval(() => this.refreshStatus(), 180000);
            this.statusCheckIntervalMs = 180000;
            
            
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

        // ===== Phase 4: Calendar Batch UI =====
        // 분석 버튼
        const analyzeBtn = document.getElementById('analyze-batch-btn');
        if (analyzeBtn) {
            analyzeBtn.addEventListener('click', (e) => {
                e.preventDefault();
                
                this.analyzeBatchRange();
            });
        } else {
            console.warn('⚠️ analyze-batch-btn not found');
        }

        // 처리 시작 버튼
        const startBtn = document.getElementById('start-processing-btn');
        if (startBtn) {
            startBtn.addEventListener('click', (e) => {
                e.preventDefault();
                
                this.submitBatchWithOption();
            });
        } else {
            console.warn('⚠️ start-processing-btn not found');
        }

        // 취소 버튼
        const cancelBtn = document.getElementById('cancel-analysis-btn');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', (e) => {
                e.preventDefault();
                
                this.resetBatchUI();
            });
        } else {
            console.warn('⚠️ cancel-analysis-btn not found');
        }

        // 날짜 입력 필드 이벤트 리스너
        const startDateInput = document.getElementById('start-date-input');
        const endDateInput = document.getElementById('end-date-input');
        if (startDateInput) {
            startDateInput.addEventListener('change', () => {
                
                this.onDateInputChange();
            });
        }
        if (endDateInput) {
            endDateInput.addEventListener('change', () => {
                
                this.onDateInputChange();
            });
        }

        // 새로고침 버튼
        const refreshBtn = document.getElementById('refresh-date-range');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', (e) => {
                e.preventDefault();
                
                this.loadBatchDateRange();
            });
        }

        // ===== Legacy Batch Form =====
        // 배치 처리 폼 (레거시)
        const batchForm = document.getElementById('batch-form');
        if (batchForm) {
            batchForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleBatchSubmit();
            });
        }

        // 결과 다운로드 버튼
        const downloadBtn = document.getElementById('download-results');
        if (downloadBtn) {
            downloadBtn.addEventListener('click', (e) => {
                e.preventDefault();
                if (window.currentJob && window.currentJob.job_id) {
                    api.downloadBatchResults(window.currentJob.job_id);
                } else {
                    alert('다운로드할 작업이 없습니다');
                }
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

        // 모달 내 다운로드 버튼
        const modalDownloadBtn = document.getElementById('modal-download-btn');
        if (modalDownloadBtn) {
            
            modalDownloadBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                
                this.downloadResults();
            });
        } else {
            console.warn('⚠️ 모달 다운로드 버튼 못 찾음');
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

        // Dashboard 수동 갱신 버튼
        const refreshStatsBtn = document.getElementById('refresh-stats-btn');
        if (refreshStatsBtn) {
            refreshStatsBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.refreshDashboardStats();
            });
        }

        // Agent API Info Icon Hover Tooltip
        const agentInfoIcon = document.getElementById('agent-info-icon');
        if (agentInfoIcon) {
            agentInfoIcon.addEventListener('mouseenter', () => {
                this.showAgentTooltip();
            });
            agentInfoIcon.addEventListener('mouseleave', () => {
                this.hideAgentTooltip();
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
        if (pageName === 'dashboard') {
            // Dashboard 진입 시 통계 데이터 로드
            this.loadDashboardStats();
        } else if (pageName === 'batch') {
            this.initializeBatchCalendar();
        } else if (pageName === 'history') {
            this.loadJobHistory();
        }
    }

    // ===== Dashboard =====

    async refreshStatus() {
        try {
            // Get basic health status
            const healthResponse = await fetch('/healthz');
            if (!healthResponse.ok) {
                throw new Error(`Health check failed: ${healthResponse.status}`);
            }
            
            const status = await healthResponse.json();
            this.updateStatusDisplay(status);
            
            // Get detailed system status (SFTP, Agent connections)
            try {
                const systemResponse = await fetch('/api/system-status');
                if (systemResponse.ok) {
                    const systemStatus = await systemResponse.json();
                    this.updateDeploymentStatus(systemStatus);
                }
            } catch (error) {
                console.warn('시스템 상태 조회 실패 (비필수):', error);
            }
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

    updateDeploymentStatus(systemStatus) {
        // SFTP Status
        const sftp = systemStatus.deployment?.sftp;
        if (sftp) {
            const sftpElement = document.getElementById('sftp-status');
            if (sftpElement) {
                let statusColor, statusText;
                if (sftp.status === 'mock') {
                    statusColor = '#8b5cf6';  // Purple for mock
                    statusText = '모의 모드';
                } else if (sftp.connected) {
                    statusColor = '#10b981';  // Green
                    statusText = '연결됨';
                } else {
                    statusColor = '#ef4444';  // Red
                    statusText = '연결 안 됨';
                }
                
                let tooltip = `${sftp.host}`;
                if (sftp.port) tooltip += `:${sftp.port}`;
                if (sftp.error) tooltip += ` - ${sftp.error}`;
                if (sftp.message) tooltip += ` (${sftp.message})`;
                
                sftpElement.innerHTML = `
                    <span class="status-dot" style="background: ${statusColor};"></span>
                    <span title="${tooltip}">${statusText}</span>
                `;
            }
        }

        // Agent Status
        const agent = systemStatus.deployment?.agent;
        if (agent) {
            const agentElement = document.getElementById('agent-status');
            const agentInfoIcon = document.getElementById('agent-info-icon');
            
            if (agentElement) {
                let statusColor, statusText;
                if (agent.status === 'mock') {
                    statusColor = '#8b5cf6';  // Purple for mock
                    statusText = '모의 모드';
                } else if (agent.connected) {
                    statusColor = '#10b981';  // Green
                    statusText = '연결됨';
                } else {
                    statusColor = '#ef4444';  // Red
                    statusText = '연결 안 됨';
                }
                
                let tooltip = `${agent.url}`;
                if (agent.error) tooltip += ` - ${agent.error}`;
                if (agent.message) tooltip += ` (${agent.message})`;
                
                agentElement.innerHTML = `
                    <span class="status-dot" style="background: ${statusColor};"></span>
                    <span title="${tooltip}">${statusText}</span>
                `;
                
                // Update info icon tooltip with endpoint URL
                if (agentInfoIcon && agent.url) {
                    agentInfoIcon.dataset.tooltip = `엔드포인트: ${agent.url}`;
                }
            }
        }
    }

    showAgentTooltip() {
        const tooltip = document.getElementById('agent-tooltip');
        const tooltipText = document.getElementById('agent-tooltip-text');
        const agentInfoIcon = document.getElementById('agent-info-icon');
        
        if (tooltip && agentInfoIcon) {
            const tooltipContent = agentInfoIcon.dataset.tooltip || '엔드포인트 정보 없음';
            if (tooltipText) {
                tooltipText.textContent = tooltipContent;
            }
            tooltip.style.display = 'block';
        }
    }

    hideAgentTooltip() {
        const tooltip = document.getElementById('agent-tooltip');
        if (tooltip) {
            tooltip.style.display = 'none';
        }
    }

    async loadDashboardStats() {
        // Dashboard 진입 시 통계 데이터만 로드 (health check와 분리)
        try {
            await this.loadDateStatistics();
            await this.loadRecentJobs();
        } catch (error) {
            console.error('Dashboard 통계 로드 실패:', error);
        }
    }

    async refreshDashboardStats() {
        // 수동 갱신 버튼 클릭 시 호출
        const btn = document.getElementById('refresh-stats-btn');
        if (btn) {
            btn.disabled = true;
            btn.textContent = '새로고침 중...';
        }

        try {
            await this.loadDashboardStats();
            // 성공 피드백
            if (btn) {
                btn.textContent = '갱신됨!';
                setTimeout(() => {
                    btn.textContent = '수동 갱신';
                    btn.disabled = false;
                }, 1500);
            }
        } catch (error) {
            console.error('통계 갱신 실패:', error);
            if (btn) {
                btn.textContent = '갱신 실패';
                setTimeout(() => {
                    btn.textContent = '수동 갱신';
                    btn.disabled = false;
                }, 2000);
            }
        }
    }

    async loadDateStatistics() {
        try {
            // 유효한 날짜 범위 먼저 로드 (없으면 현재 설정된 범위 사용)
            if (!window.batchDateRange) {
                await this.loadBatchDateRange();
            }
            
            let url = '/api/admin/date-stats';
            
            // 유효한 범위가 있으면 필터링
            if (window.batchDateRange && window.batchDateRange.min_date && window.batchDateRange.max_date) {
                url += `?start_date=${window.batchDateRange.min_date}&end_date=${window.batchDateRange.max_date}`;
            }
            
            const response = await fetch(url);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            
            // Update summary stats
            if (data.total_files !== undefined) {
                document.getElementById('total-files').textContent = data.total_files;
                document.getElementById('success-count').textContent = data.total_success || 0;
                document.getElementById('error-count').textContent = data.total_failed || 0;
            }

            // Update date-wise table
            const tbody = document.getElementById('date-stats-tbody');
            if (!tbody) return;

            if (!data.dates || data.dates.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #999;">처리된 날짜가 없습니다</td></tr>';
                return;
            }

            tbody.innerHTML = data.dates.map(stat => {
                const date = stat.date;
                const formattedDate = `${date.substring(0, 4)}-${date.substring(4, 6)}-${date.substring(6, 8)}`;
                const statusBadge = this.getStatusBadge(stat.status);
                const lastProcessed = stat.last_processed 
                    ? new Date(stat.last_processed).toLocaleString('ko-KR')
                    : '-';

                return `
                    <tr>
                        <td>${formattedDate}</td>
                        <td>${stat.total_files}</td>
                        <td class="success">${stat.processed_files}</td>
                        <td class="error">${stat.failed_files}</td>
                        <td>${statusBadge}</td>
                        <td style="font-size: 0.9em;">${lastProcessed}</td>
                    </tr>
                `;
            }).join('');
        } catch (error) {
            console.error('날짜별 통계 로드 실패:', error);
            const tbody = document.getElementById('date-stats-tbody');
            if (tbody) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #c00;">통계 로드 실패</td></tr>';
            }
        }
    }

    async loadRecentJobs() {
        try {
            const response = await fetch('/api/admin/recent-jobs?limit=5');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            const container = document.getElementById('recent-jobs');
            if (!container) return;

            if (!data.jobs || data.jobs.length === 0) {
                container.innerHTML = '<p class="empty-state">최근 작업이 없습니다</p>';
                return;
            }

            container.innerHTML = data.jobs.map(job => {
                const startDate = job.start_date;
                const endDate = job.end_date;
                const formattedRange = `${startDate.substring(0, 4)}-${startDate.substring(4, 6)}-${startDate.substring(6, 8)} ~ ${endDate.substring(0, 4)}-${endDate.substring(4, 6)}-${endDate.substring(6, 8)}`;
                const statusClass = job.status === 'completed' ? 'success' : job.status === 'failed' ? 'error' : 'info';
                const statusText = job.status === 'completed' ? '완료' : job.status === 'running' ? '실행 중' : job.status === 'failed' ? '실패' : '대기';
                const createdAt = new Date(job.created_at).toLocaleString('ko-KR');
                
                return `
                    <div style="padding: 12px; border: 1px solid #e0e0e0; border-radius: 4px; margin-bottom: 8px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <div style="font-weight: 600; margin-bottom: 4px;">${formattedRange}</div>
                                <div style="font-size: 0.85em; color: #666;">
                                    파일: ${job.total_files} | 성공: ${job.success_files} | 실패: ${job.failed_files}
                                </div>
                                <div style="font-size: 0.8em; color: #999; margin-top: 4px;">${createdAt}</div>
                            </div>
                            <span style="background: ${statusClass === 'success' ? '#10b981' : statusClass === 'error' ? '#ef4444' : '#3b82f6'}; color: white; padding: 4px 8px; border-radius: 3px; font-size: 0.85em; font-weight: 600;">
                                ${statusText}
                            </span>
                        </div>
                    </div>
                `;
            }).join('');
        } catch (error) {
            console.error('최근 작업 로드 실패:', error);
            const container = document.getElementById('recent-jobs');
            if (container) {
                container.innerHTML = '<p class="empty-state">작업 이력을 로드할 수 없습니다</p>';
            }
        }
    }

    getStatusBadge(status) {
        const badges = {
            'ready': '<span style="background: #e0e0e0; padding: 2px 6px; border-radius: 3px; font-size: 0.85em;">미처리</span>',
            'done': '<span style="background: #10b981; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.85em;">완료</span>',
            'incomplete': '<span style="background: #f59e0b; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.85em;">일부 실패</span>',
            'failed': '<span style="background: #ef4444; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.85em;">실패</span>'
        };
        return badges[status] || `<span>${status}</span>`;
    }

    // ===== Batch Processing =====

    async handleBatchSubmit() {
        const startDateInput = document.getElementById('start-date');
        const endDateInput = document.getElementById('end-date');
        const forceReprocessCheckbox = document.getElementById('force-reprocess');
        const handleOverlapRadio = document.querySelector('input[name="handle-overlap"]:checked');

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
            // 옵션값 수집
            const forceReprocess = forceReprocessCheckbox?.checked || false;
            const handleOverlap = handleOverlapRadio?.value || 'new';


            // 진행 상황 표시
            const progressContainer = document.getElementById('progress-container');
            const resultsContainer = document.getElementById('results-container');
            
            if (progressContainer) progressContainer.style.display = 'block';
            if (resultsContainer) resultsContainer.style.display = 'none';

            // 배치 작업 제출 (새 API 사용)
            const response = await api.submitBatch({
                startDate: startDate,
                endDate: endDate,
                forceReprocess: forceReprocess,
                handleOverlap: handleOverlap
            });



            // 응답 케이스별 처리
            if (response.status === 'submitted' && response.case === 'no_overlap') {
                // ✅ 케이스 3: 새 작업 생성 - 모니터링 시작
                const jobId = response.job_id;
                this.monitorBatchJob(jobId);

            } else if (response.status === 'duplicate' && response.case === 'exact_overlap') {
                // ⚠️ 케이스 1: 전체 겹침
                if (forceReprocess) {
                    // force_reprocess=true인데 여기 올 수 없음 (백엔드에서 새 job 생성)
                    this.monitorBatchJob(response.job_id);
                } else {
                    // force_reprocess=false - 기존 작업 반환
                    alert(`❌ 동일한 범위의 작업이 이미 ${response.message}\n\n작업 ID: ${response.job_id}`);
                    const resultsContainer = document.getElementById('results-container');
                    if (resultsContainer) resultsContainer.style.display = 'block';
                    if (progressContainer) progressContainer.style.display = 'none';
                }

            } else if (response.status === 'partial_overlap_detected' && response.case === 'partial_overlap') {
                // ⚠️ 케이스 2: 부분 겹침
                const overlappingInfo = response.overlapping_jobs
                    .map(j => `• ${j.range} (${j.status})`)
                    .join('\n');
                
                const options = Object.entries(response.available_options)
                    .map(([key, desc]) => `• ${key}: ${desc}`)
                    .join('\n');

                alert(
                    `⚠️ 부분적으로 겹치는 작업이 발견되었습니다\n\n` +
                    `겹치는 작업들:\n${overlappingInfo}\n\n` +
                    `처리 방식:\n${options}\n\n` +
                    `다시 시도할 때 처리 방식을 선택하세요.`
                );
                
                const resultsContainer = document.getElementById('results-container');
                if (resultsContainer) resultsContainer.style.display = 'none';
                if (progressContainer) progressContainer.style.display = 'none';

            } else if (response.status === 'error') {
                // ❌ 에러
                alert(`❌ 처리 실패: ${response.message}`);
                if (progressContainer) progressContainer.style.display = 'none';

            } else {
                // 예상 외의 응답
                console.warn('예상 외의 응답:', response);
                alert(`예상 외의 응답이 발생했습니다: ${response.status}`);
            }

        } catch (error) {
            alert(`배치 처리 실패: ${error.message}`);
            console.error('배치 처리 오류:', error);
            const progressContainer = document.getElementById('progress-container');
            if (progressContainer) progressContainer.style.display = 'none';
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
        setTimeout(() => {
            this.switchPage('history');
            // loadJobHistory 호출
            this.loadJobHistory();
        }, 500);
    }

    // ===== Job History & Detail View =====

    async loadJobHistory(startDate = null, endDate = null) {
        try {
            let jobs = [];
            
            // 날짜 범위가 지정된 경우 (이전 기록 보기)
            if (startDate && endDate) {
                try {
                    const response = await fetch(`/api/admin/jobs?start_date=${startDate}&end_date=${endDate}`);
                    if (!response.ok) {
                        throw new Error(`API 응답 오류: ${response.status}`);
                    }
                    const data = await response.json();
                    jobs = data.jobs || [];
                } catch (error) {
                    console.error('❌ 날짜 범위 작업 조회 실패:', error);
                    jobs = [];
                }
            } else {
                // 날짜 범위 없이 전체 이력 조회 (이력 페이지 첫 진입)
                try {
                    const response = await fetch('/api/admin/jobs/all');
                    if (!response.ok) {
                        throw new Error(`API 응답 오류: ${response.status}`);
                    }
                    const data = await response.json();
                    jobs = data.jobs || [];
                } catch (error) {
                    console.error('❌ 전체 작업 조회 실패:', error);
                    jobs = [];
                }
            }
            
            this.displayJobList(jobs, startDate, endDate);
        } catch (error) {
            console.error('작업 이력 로드 실패:', error);
        }
    }

    displayJobList(jobs, filterStartDate = null, filterEndDate = null) {
        const container = document.getElementById('jobs-list');
        
        
        if (!container) {
            console.error('❌ jobs-list 컨테이너를 찾을 수 없습니다!');
            return;
        }

        if (!jobs || jobs.length === 0) {
            let emptyMessage = '작업 이력이 없습니다';
            if (filterStartDate && filterEndDate) {
                const formattedStart = `${filterStartDate.substring(0, 4)}-${filterStartDate.substring(4, 6)}-${filterStartDate.substring(6, 8)}`;
                const formattedEnd = `${filterEndDate.substring(0, 4)}-${filterEndDate.substring(4, 6)}-${filterEndDate.substring(6, 8)}`;
                emptyMessage = `${formattedStart} ~ ${formattedEnd} 기간의 작업 이력이 없습니다`;
            }
            container.innerHTML = `<p class="empty-state">${emptyMessage}</p>`;
            return;
        }

        // 날짜 범위 필터 정보 표시
        if (filterStartDate && filterEndDate) {
            const formattedStart = `${filterStartDate.substring(0, 4)}-${filterStartDate.substring(4, 6)}-${filterStartDate.substring(6, 8)}`;
            const formattedEnd = `${filterEndDate.substring(0, 4)}-${filterEndDate.substring(4, 6)}-${filterEndDate.substring(6, 8)}`;
        }

        container.innerHTML = jobs.map(job => this.renderJobItem(job)).join('');

        // 확장 버튼 이벤트 등록
        const toggleBtns = document.querySelectorAll('.job-toggle');
        
        toggleBtns.forEach((btn, idx) => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const jobItem = btn.closest('.job-item');
                const fileResults = jobItem?.querySelector('.file-results');
                
                if (fileResults) {
                    const isCurrentlyHidden = fileResults.style.display === 'none';
                    
                    // 파일이 보여질 예정이고, 내용이 아직 없으면 로드
                    if (isCurrentlyHidden && fileResults.innerHTML.trim() === '') {
                        const jobId = jobItem?.dataset.jobId;
                        if (jobId) {
                            try {
                                const response = await fetch(`/process/batch/status/${jobId}`);
                                if (!response.ok) {
                                    throw new Error(`API 응답 실패: ${response.status}`);
                                }
                                const fullJob = await response.json();
                                
                                if (fullJob.results && Array.isArray(fullJob.results) && fullJob.results.length > 0) {
                                    fileResults.innerHTML = this.renderFileResults(fullJob);
                                } else {
                                    fileResults.innerHTML = '<p class="empty-state">처리 결과가 없습니다</p>';
                                }
                            } catch (error) {
                                console.error('❌ 파일 결과 로드 실패:', error);
                                fileResults.innerHTML = `<p class="empty-state">결과 로드 실패: ${error.message}</p>`;
                            }
                        }
                    }
                    
                    // display 토글
                    fileResults.style.display = isCurrentlyHidden ? 'block' : 'none';
                    // expanded 클래스 토글
                    btn.classList.toggle('expanded', isCurrentlyHidden);
                    // 텍스트 업데이트
                    const textNode = btn.childNodes[btn.childNodes.length - 1];
                    if (textNode && textNode.nodeType === Node.TEXT_NODE) {
                        textNode.textContent = isCurrentlyHidden ? ' 파일 목록 숨기기' : ' 파일 목록 보기';
                    }
                }
            });
        });

        // 상세보기 버튼 이벤트 (Event Delegation)
        const jobsList = document.getElementById('jobs-list');
        if (jobsList) {
            jobsList.addEventListener('click', async (e) => {
                const btn = e.target.closest('.view-details-btn');
                if (!btn) return;
                
                e.stopPropagation();
                const fileIndex = parseInt(btn.dataset.fileIndex);
                const jobItem = btn.closest('.job-item');
                const jobId = jobItem?.dataset.jobId;
                
                
                if (!jobId) {
                    console.error('❌ jobId 없음');
                    return;
                }
                
                // 현재 저장된 job이 results를 가지고 있지 않으면 API에서 조회
                if (!window.currentJob?.results) {
                    try {
                        const response = await fetch(`/process/batch/status/${jobId}`);
                        if (response.ok) {
                            const fullJob = await response.json();
                            this.showDetailModal(fullJob, fileIndex);
                        } else {
                            alert('파일 정보를 불러올 수 없습니다');
                        }
                    } catch (error) {
                        console.error('❌ Job 정보 조회 실패:', error);
                        alert('파일 정보 조회 실패: ' + error.message);
                    }
                } else {
                    // 이미 results를 가지고 있으면 바로 표시
                    this.showDetailModal(window.currentJob, fileIndex);
                }
            });
        }

        // 작업 다운로드 버튼 이벤트
        const downloadBtns = document.querySelectorAll('.job-download-btn');
        
        downloadBtns.forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const jobId = btn.dataset.jobId;
                
                if (!jobId) {
                    console.error('❌ jobId 없음');
                    return;
                }
                
                try {
                    await this.downloadJobResults(jobId);
                } catch (error) {
                    console.error('❌ 작업 다운로드 실패:', error);
                    alert('작업 다운로드 실패: ' + error.message);
                }
            });
        });
    }

    renderJobItem(job) {
        const successCount = job.success_files || (job.results ? job.results.filter(r => r.success).length : 0);
        const errorCount = job.failed_files || (job.results ? job.results.filter(r => !r.success).length : 0);
        const totalFiles = job.total_files || (job.results ? job.results.length : 0);
        const totalOmissions = job.results ? job.results.reduce((sum, r) => {
            return sum + (r.detected_issues ? r.detected_issues.length : 0);
        }, 0) : 0;

        const createdDate = job.created_at ? new Date(job.created_at).toLocaleString('ko-KR') : '-';
        const statusText = job.status || 'unknown';

        return `
            <div class="job-item" data-job-id="${job.job_id || job.id}">
                <div class="job-header">
                    <div class="job-header-info">
                        <div class="job-id">작업 ID: ${(job.job_id || job.id || '').substring(0, 8)}...</div>
                        <div class="job-meta">생성: ${createdDate} | 범위: ${job.date_range || `${job.start_date} ~ ${job.end_date}` || '-'} | 상태: <span class="badge">${this.getStatusText(statusText)}</span></div>
                    </div>
                    <div class="job-stats">
                        <div class="job-stat">
                            <span class="job-stat-label">처리 파일:</span>
                            <span class="job-stat-value">${totalFiles}</span>
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
                        <div style="display: flex; gap: 12px; align-items: center; margin-left: auto;">
                            <button class="job-download-btn" data-job-id="${job.job_id || job.id}" style="padding: 8px 14px; font-size: 0.9em; background: #3b82f6; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: 500; transition: background 0.2s;">
                                다운로드
                            </button>
                            <button class="job-toggle"> 파일 목록 보기</button>
                        </div>
                    </div>
                </div>
                <div class="file-results" style="display: none;">
                </div>
            </div>
        `;
    }

    renderFileResults(job) {
        if (!job.results || job.results.length === 0) {
            return '<p class="empty-state">처리 결과가 없습니다</p>';
        }

        return job.results.map((result, index) => {
            // detected_issues 처리 (배열 또는 JSON 문자열 모두 지원)
            let detectedCount = 0;
            if (result.detected_issues) {
                if (typeof result.detected_issues === 'string') {
                    try {
                        const parsed = JSON.parse(result.detected_issues);
                        detectedCount = Array.isArray(parsed) ? parsed.length : 0;
                    } catch {
                        detectedCount = 0;
                    }
                } else if (Array.isArray(result.detected_issues)) {
                    detectedCount = result.detected_issues.length;
                }
            }
            
            const statusText = result.success ? '성공' : '실패';
            const statusDetail = detectedCount > 0 ? `누락: ${detectedCount}건` : (result.success ? '완료' : (result.error_message || '처리 실패'));
            
            return `
            <div class="file-result-item ${result.success ? 'success' : 'error'}">
                <div class="file-result-info">
                    <div class="file-result-name">${result.filename || `파일 #${index + 1}`}</div>
                    <div class="file-result-meta">
                        날짜: ${result.date || result.file_date || '-'} | ${statusDetail}
                    </div>
                </div>
                <div class="file-result-action">
                    <span class="file-result-badge ${result.success ? 'success' : 'error'}">
                        ${statusText}
                    </span>
                    <button class="view-details-btn" data-file-index="${index}">상세보기</button>
                </div>
            </div>
        `}).join('');
    }

    showDetailModal(job, fileIndex) {
        
        // job이 없거나 results가 없는 경우 처리
        if (!job || !job.results || !Array.isArray(job.results)) {
            console.error('❌ job.results 없음:', job);
            alert('파일 결과를 찾을 수 없습니다');
            return;
        }
        
        const result = job.results[fileIndex];
        if (!result) {
            console.error('❌ result 없음:', { fileIndex, resultsLength: job.results.length });
            alert('해당 파일의 결과를 찾을 수 없습니다');
            return;
        }
        

        // 모달 헤더
        const modalTitle = document.getElementById('modal-title');
        if (modalTitle) {
            modalTitle.textContent = `파일 상세 분석: ${result.filename || `파일 #${fileIndex + 1}`}`;
        }

        // 원본 텍스트
        const originalText = document.getElementById('original-text');
        if (originalText) {
            if (result.success) {
                // 백엔드에서는 text_content 필드 사용
                const textContent = result.text_content || result.text || '원본 텍스트를 불러올 수 없습니다.';
                originalText.textContent = textContent;
            } else {
                originalText.textContent = `[처리 실패]\n\n오류: ${result.error_message || result.error || '알 수 없는 오류'}\n\n이 파일은 처리에 실패했습니다.`;
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
            // detected_issues를 안전하게 배열로 변환
            let detectedIssues = [];
            if (result.detected_issues) {
                if (typeof result.detected_issues === 'string') {
                    try {
                        detectedIssues = JSON.parse(result.detected_issues);
                    } catch (e) {
                        console.warn('⚠️ detected_issues 파싱 실패:', e);
                        detectedIssues = [];
                    }
                } else if (Array.isArray(result.detected_issues)) {
                    detectedIssues = result.detected_issues;
                }
            }
            
            if (result.success && detectedIssues && detectedIssues.length > 0) {
                issuesContainer.innerHTML = detectedIssues.map((issue, idx) => `
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
            console.error('❌ window.currentDetailResult 없음');
            alert('다운로드할 분석 결과가 없습니다.');
            return;
        }

        const result = window.currentDetailResult;
        
        // detected_issues를 안전하게 배열로 변환
        let detectedIssues = [];
        if (result.detected_issues) {
            if (typeof result.detected_issues === 'string') {
                try {
                    detectedIssues = JSON.parse(result.detected_issues);
                } catch (e) {
                    console.warn('⚠️ detected_issues 파싱 실패:', e);
                    detectedIssues = [];
                }
            } else if (Array.isArray(result.detected_issues)) {
                detectedIssues = result.detected_issues;
            }
        }
        
        // CSV 생성 헬퍼 함수
        const escapeCSV = (str) => {
            if (str === null || str === undefined) return '';
            const text = String(str);
            if (text.includes(',') || text.includes('"') || text.includes('\n')) {
                return `"${text.replace(/"/g, '""')}"`;
            }
            return text;
        };
        
        // CSV 콘텐츠 구성
        const rows = [];
        
        // 헤더: 파일명,날짜,카테고리,요약,누락건수,검출된누락항목
        rows.push('파일명,날짜,카테고리,요약,누락건수,검출된누락항목');
        
        // 누락 항목들을 JSON 배열로 변환
        const issuesJson = detectedIssues && detectedIssues.length > 0 
            ? JSON.stringify(detectedIssues)
            : '[]';
        
        // 데이터 행
        const dataRow = [
            escapeCSV(result.filename || '-'),
            escapeCSV(result.file_date || result.date || '-'),
            escapeCSV(result.category || '-'),
            escapeCSV(result.summary || '-'),
            escapeCSV(result.omission_num || '0'),
            escapeCSV(issuesJson)
        ];
        
        rows.push(dataRow.join(','));
        
        // CSV 문자열 생성
        const csvContent = rows.join('\n');
        
        // UTF-8 BOM 추가 (Excel에서 한글 깨짐 방지)
        const BOM = '\uFEFF';
        const blob = new Blob([BOM + csvContent], { type: 'text/csv;charset=utf-8' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `분석결과_${result.filename || 'report'}_${Date.now()}.csv`;
        link.click();
        URL.revokeObjectURL(link.href);
    }

    /**
     * 작업(Job) 단위로 모든 결과를 CSV로 다운로드
     */
    async downloadJobResults(jobId) {
        
        if (!jobId) {
            alert('작업 ID가 없습니다.');
            return;
        }
        
        try {
            // Job의 전체 정보 조회
            const response = await fetch(`/process/batch/status/${jobId}`);
            if (!response.ok) {
                throw new Error('작업 정보 조회 실패');
            }
            
            const job = await response.json();
            
            if (!job.results || job.results.length === 0) {
                alert('다운로드할 결과가 없습니다.');
                return;
            }
            
            // CSV 생성 헬퍼 함수
            const escapeCSV = (str) => {
                if (str === null || str === undefined) return '';
                const text = String(str);
                if (text.includes(',') || text.includes('"') || text.includes('\n')) {
                    return `"${text.replace(/"/g, '""')}"`;
                }
                return text;
            };
            
            // CSV 콘텐츠 구성
            const rows = [];
            
            // 헤더: 파일명,날짜,카테고리,요약,누락건수,검출된누락항목
            rows.push('파일명,날짜,카테고리,요약,누락건수,검출된누락항목');
            
            // 각 result를 행으로 추가
            job.results.forEach((result) => {
                // detected_issues를 안전하게 배열로 변환
                let detectedIssues = [];
                if (result.detected_issues) {
                    if (typeof result.detected_issues === 'string') {
                        try {
                            detectedIssues = JSON.parse(result.detected_issues);
                        } catch (e) {
                            console.warn('⚠️ detected_issues 파싱 실패:', e);
                            detectedIssues = [];
                        }
                    } else if (Array.isArray(result.detected_issues)) {
                        detectedIssues = result.detected_issues;
                    }
                }
                
                // 누락 항목들을 JSON 배열로 변환
                const issuesJson = detectedIssues && detectedIssues.length > 0 
                    ? JSON.stringify(detectedIssues)
                    : '[]';
                
                // 데이터 행
                const dataRow = [
                    escapeCSV(result.filename || '-'),
                    escapeCSV(result.file_date || result.date || '-'),
                    escapeCSV(result.category || '-'),
                    escapeCSV(result.summary || '-'),
                    escapeCSV(result.omission_num || '0'),
                    escapeCSV(issuesJson)
                ];
                
                rows.push(dataRow.join(','));
            });
            
            // CSV 문자열 생성
            const csvContent = rows.join('\n');
            
            // UTF-8 BOM 추가 (Excel에서 한글 깨짐 방지)
            const BOM = '\uFEFF';
            const blob = new Blob([BOM + csvContent], { type: 'text/csv;charset=utf-8' });
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = `작업결과_${jobId.substring(0, 8)}_${Date.now()}.csv`;
            link.click();
            URL.revokeObjectURL(link.href);
        } catch (error) {
            console.error('❌ 작업 다운로드 실패:', error);
            throw error;
        }
    }

    /**
     * 배치 캘린더 UI 초기화
     */
    async initializeBatchCalendar() {
        
        // date-range 로드
        await this.loadBatchDateRange();
        
        // date-stats 로드 (배지용)
        await this.loadBatchDateStats();
        
        // 캘린더 초기화
        this.initializeCalendar();
    }

    /**
     * 처리 가능 날짜 범위 로드
     */
    async loadBatchDateRange() {
        try {
            const data = await api.getDateRange();
            
            // 범위 정보 표시
            const minDate = data.min_date ? this.formatDateForDisplay(data.min_date) : '미정';
            const maxDate = data.max_date ? this.formatDateForDisplay(data.max_date) : '미정';
            const rangeInfo = document.getElementById('date-range-info');
            if (rangeInfo) {
                rangeInfo.textContent = `${minDate} ~ ${maxDate}`;
            }
            
            // 전역 변수로 저장 (캘린더 초기화에 사용)
            window.batchDateRange = data;
            
            // TEST_MODE 안내
            if (data.test_mode) {
            }
        } catch (error) {
            console.error('❌ Date range 로드 실패:', error);
            const rangeInfo = document.getElementById('date-range-info');
            if (rangeInfo) {
                rangeInfo.textContent = '범위 로드 실패';
            }
        }
    }

    /**
     * 날짜별 통계 로드 (캘린더 배지용)
     */
    async loadBatchDateStats() {
        try {
            const data = await api.getDateStats();
            
            // 전역 변수로 저장
            window.batchDateStats = data;
            
            // dateStatusMap 생성
            window.dateStatusMap = {};
            if (data.dates && Array.isArray(data.dates)) {
                data.dates.forEach(stat => {
                    window.dateStatusMap[stat.date] = {
                        file_count: stat.total_files || 0,
                        processed_count: stat.processed_files || 0,
                        failed_count: stat.failed_files || 0,
                        status: stat.status || 'unknown'
                    };
                });
            }
        } catch (error) {
            console.error('❌ Date stats 로드 실패:', error);
        }
    }

    /**
     * 캘린더 초기화 (flatpickr)
     */
    initializeCalendar() {
        const calendarEl = document.getElementById('batch-calendar');
        if (!calendarEl) {
            console.error('❌ batch-calendar element not found');
            return;
        }
        
        // 이전 인스턴스 제거
        if (calendarEl._flatpickr) {
            calendarEl._flatpickr.destroy();
        }
        
        // 선택 가능 날짜 설정
        const availableDates = window.batchDateRange?.available_dates || [];
        
        // 최소/최대 날짜 설정
        const minDate = window.batchDateRange?.min_date ? this.convertDateFormat(window.batchDateRange.min_date, 'YYYYMMDD_to_Date') : null;
        const maxDate = window.batchDateRange?.max_date ? this.convertDateFormat(window.batchDateRange.max_date, 'YYYYMMDD_to_Date') : null;
        
        
        // flatpickr 캘린더 생성 (inline 모드 - 항상 표시)
        flatpickr(calendarEl, {
            mode: 'range',
            dateFormat: 'Y-m-d',
            minDate: minDate,
            maxDate: maxDate,
            inline: true,  // 인라인 캘린더로 항상 표시
            static: false,
            defaultDate: minDate ? [minDate] : [],
            onChange: (selectedDates) => {
                this.onCalendarDateChange(selectedDates);
            },
            onClose: (selectedDates, dateStr, instance) => {
            }
        });
        
    }

    /**
     * 비활성 날짜 목록 생성 (선택 불가능)
     */
    getDisabledDates(availableDates) {
        // availableDates는 ['YYYYMMDD', ...] 형식
        // 이 함수는 이제 사용되지 않음 - disable 함수를 사용
        return [];

    }

    /**
     * 캘린더 날짜 변경 이벤트
     */
    onCalendarDateChange(selectedDates) {
        
        if (selectedDates.length === 2) {
            const startDate = selectedDates[0];
            const endDate = selectedDates[1];
            
            const startStr = `${startDate.getFullYear()}-${String(startDate.getMonth() + 1).padStart(2, '0')}-${String(startDate.getDate()).padStart(2, '0')}`;
            const endStr = `${endDate.getFullYear()}-${String(endDate.getMonth() + 1).padStart(2, '0')}-${String(endDate.getDate()).padStart(2, '0')}`;
            
            // 전역 변수 저장
            window.selectedDateRange = {
                start: startStr,
                end: endStr,
                startDate: startDate,
                endDate: endDate
            };
            
            
            // 입력 필드 업데이트
            this.updateDateInputsFromCalendar(startStr, endStr);
            
            // 선택 정보 카드 업데이트
            const summary = this.calculateSelectionSummary(startDate, endDate);
            this.updateSelectionCard(summary);
            
            // Auto-analysis: trigger batch analysis after debounce delay
            this.scheduleAutoAnalysis();
        } else if (selectedDates.length === 0) {
            // 선택 해제
            window.selectedDateRange = null;
            const card = document.getElementById('selection-info-card');
            if (card) {
                card.style.display = 'none';
            }
            // 입력 필드 초기화
            this.clearDateInputs();
        }
    }

    /**
     * Schedule auto-analysis with debounce (500ms delay)
     * This only fetches the analysis data, doesn't display results yet
     * Results are only displayed when user clicks "Analyze" button
     */
    scheduleAutoAnalysis() {
        // Cancel previous timer
        if (this.autoAnalysisDebounceTimer) {
            clearTimeout(this.autoAnalysisDebounceTimer);
        }
        
        // Set new timer - delay 500ms to allow user to finish selecting
        this.autoAnalysisDebounceTimer = setTimeout(() => {
            this.fetchBatchAnalysisData();  // Only fetch data, don't display
            this.autoAnalysisDebounceTimer = null;
        }, 500);
    }

    /**
     * Fetch batch analysis data without displaying full results
     * Used for auto-analysis to populate cache and update UI metadata
     */
    async fetchBatchAnalysisData() {
        const selectedRange = window.selectedDateRange;
        if (!selectedRange) {
            return;
        }
        
        try {
            // API 호출
            const response = await api.analyzeBatch({
                start_date: selectedRange.start.replace(/-/g, ''),
                end_date: selectedRange.end.replace(/-/g, '')
            });
            
            // 전역 변수 저장 (캐시)
            window.batchAnalysisResult = response;
            
            // Update selection card with file count data from API
            this.updateSelectionCardFromAnalysis(response);
            
            // Update date details table with file counts
            this.updateDateDetailsTable(response);
        } catch (error) {
            console.error('❌ 분석 데이터 조회 실패:', error);
            // 에러는 무시 - 사용자가 버튼을 누를 때 다시 시도
        }
    }

    /**
     * Update selection-info-box with data from batch analysis API
     * Shows file counts and date details without displaying analysis results
     */
    updateSelectionCardFromAnalysis(analysisResult) {
        const card = document.getElementById('selection-info-card');
        const dateCount = document.getElementById('stats-date-count');
        const totalFiles = document.getElementById('stats-total-files');
        
        if (!card) return;
        
        // Calculate total dates and files
        const allDates = [...new Set([...analysisResult.overlap_dates, ...analysisResult.new_dates])].sort();
        const totalFileCount = analysisResult.total_files_to_process || 
                              Object.values(analysisResult.files_per_date || {}).reduce((a, b) => a + b, 0);
        
        // Update counts
        if (dateCount) {
            dateCount.textContent = allDates.length;
        }
        if (totalFiles) {
            totalFiles.textContent = totalFileCount;
        }
        
        // Ensure card is visible
        card.style.display = 'block';
        
    }

    /**
     * 날짜별 배지 추가 (파일 개수 표시)
     */
    addDateBadges() {
        const stats = window.batchDateStats?.dates || [];
        
        stats.forEach(stat => {
            const dateStr = stat.date; // YYYYMMDD
            const date = this.convertDateFormat(dateStr, 'YYYYMMDD_to_Date');
            
            // 캘린더에서 해당 날짜 요소 찾기
            const dayElement = document.querySelector(`[aria-label="${this.formatDateForDisplay(dateStr)}"]`);
            if (dayElement && stat.total_files > 0) {
                // 배지 추가
                const badge = document.createElement('span');
                badge.className = 'date-badge';
                badge.textContent = stat.total_files;
                badge.style.cssText = 'position: absolute; top: 2px; right: 2px; background: #2563eb; color: white; border-radius: 50%; width: 18px; height: 18px; display: flex; align-items: center; justify-content: center; font-size: 0.7em; font-weight: bold;';
                dayElement.style.position = 'relative';
                dayElement.appendChild(badge);
            }
        });
    }

    /**
     * 배치 범위 분석
     */
    async analyzeBatchRange() {
        const selectedRange = window.selectedDateRange;
        if (!selectedRange) {
            console.warn('⚠️ 선택된 범위 없음:', window.selectedDateRange);
            alert('먼저 날짜 범위를 선택해주세요');
            return;
        }
        
        
        try {
            // API 호출
            const response = await api.analyzeBatch({
                start_date: selectedRange.start.replace(/-/g, ''),
                end_date: selectedRange.end.replace(/-/g, '')
            });
            
            
            // 전역 변수 저장
            window.batchAnalysisResult = response;
            
            // 결과 표시
            this.displayAnalysisResult(response);
        } catch (error) {
            console.error('❌ 분석 실패:', error);
            alert('배치 분석 실패: ' + error.message);
        }
    }

    /**
     * 분석 결과 표시
     */
    displayAnalysisResult(result) {
        const resultContainer = document.getElementById('analysis-result-container');
        const optionsContainer = document.getElementById('options-container');
        const caseInfoBox = document.getElementById('case-info-box');
        const caseDescription = document.getElementById('case-description');
        
        if (!resultContainer || !optionsContainer) return;
        
        // 케이스 정보 표시
        const caseText = {
            'full_overlap': '✅ 모든 날짜가 이미 처리되었습니다',
            'partial_overlap': '⚠️ 일부 날짜는 처리되었고, 일부는 새로운 데이터입니다',
            'no_overlap': '🆕 모든 날짜가 새로운 데이터입니다',
            'no_data': '❌ 선택한 범위에 처리할 데이터가 없습니다'
        };
        
        if (caseDescription) {
            caseDescription.textContent = caseText[result.case] || '분류 불가';
        }
        
        if (caseInfoBox && result.case !== 'no_data') {
            caseInfoBox.style.display = 'block';
        }
        
        // 옵션 표시
        optionsContainer.innerHTML = '';
        
        if (result.options && result.options.length > 0) {
            result.options.forEach((option, index) => {
                const optionCard = document.createElement('div');
                optionCard.className = 'option-card';
                const optionId = option.option_id || option.id;
                
                optionCard.innerHTML = `
                    <input type="radio" name="batch-option" value="${optionId}" id="option-${optionId}" style="margin-right: 10px;">
                    <label for="option-${optionId}" style="cursor: pointer; flex: 1;">
                        <strong>${option.label}</strong>
                        <p style="margin: 4px 0 0 0; font-size: 0.9em; color: #666;">${option.description}</p>
                    </label>
                `;
                
                // 호버 효과
                optionCard.addEventListener('mouseenter', () => {
                    optionCard.style.borderColor = '#2563eb';
                    optionCard.style.backgroundColor = '#eff6ff';
                });
                optionCard.addEventListener('mouseleave', () => {
                    optionCard.style.borderColor = '#e5e7eb';
                    optionCard.style.backgroundColor = '#f9fafb';
                });
                
                // 클릭 시 라디오 선택
                optionCard.addEventListener('click', () => {
                    document.getElementById(`option-${optionId}`).checked = true;
                });
                
                optionsContainer.appendChild(optionCard);
                
                // 첫 번째 옵션 기본 선택
                if (index === 0) {
                    document.getElementById(`option-${optionId}`).checked = true;
                }
            });
        } else {
            optionsContainer.innerHTML = '<p style="text-align: center; color: #666;">선택 가능한 옵션이 없습니다</p>';
        }
        
        // 버튼 텍스트를 "수행하기"로 설정 (고정)
        const startBtn = document.getElementById('start-processing-btn');
        if (startBtn) {
            startBtn.textContent = '수행하기';
        }
        
        // 날짜별 파일 개수 및 상태 테이블 업데이트 (배치 분석 결과 활용)
        this.updateDateDetailsTable(result);
        
        // 결과 컨테이너 표시
        resultContainer.style.display = 'block';
    }

    /**
     * 배치 분석 결과를 기반으로 날짜별 파일 개수 및 상태 테이블 업데이트
     */
    updateDateDetailsTable(analysisResult) {
        const tbody = document.getElementById('date-details-tbody');
        if (!tbody) return;
        
        tbody.innerHTML = '';
        
        // 모든 날짜 수집 (완료된 날짜 + 새로운 날짜)
        const allDates = [...new Set([...analysisResult.overlap_dates, ...analysisResult.new_dates])].sort();
        
        allDates.forEach(dateStr => {
            const row = document.createElement('tr');
            const dateDisplay = this.formatDateString(dateStr); // YYYYMMDD → 유저 친화적 포맷
            
            // 파일 개수 (API 응답의 files_per_date 또는 0)
            const fileCount = analysisResult.files_per_date?.[dateStr] || 0;
            
            // 상태 결정: 완료됨 vs 대기
            const isCompleted = analysisResult.overlap_dates.includes(dateStr);
            const status = isCompleted ? '완료' : '대기';
            const statusColor = isCompleted ? '#10b981' : '#3b82f6'; // 초록 vs 파랑
            
            row.innerHTML = `
                <td style="padding: 8px; border-bottom: 1px solid #f0f0f0;">${dateDisplay}</td>
                <td style="padding: 8px; text-align: center; border-bottom: 1px solid #f0f0f0;">${fileCount}개</td>
                <td style="padding: 8px; text-align: center; border-bottom: 1px solid #f0f0f0;">
                    <span style="background-color: ${statusColor}; color: white; padding: 3px 10px; border-radius: 4px; font-size: 0.85em; font-weight: 500;">${status}</span>
                </td>
            `;
            tbody.appendChild(row);
        });
    }

    /**
     * YYYYMMDD 형식의 날짜를 사용자 친화적 포맷으로 변환
     * 예: 20260315 → 2026-03-15
     */
    formatDateString(dateStr) {
        if (!dateStr || dateStr.length !== 8) return dateStr;
        return `${dateStr.substring(0, 4)}-${dateStr.substring(4, 6)}-${dateStr.substring(6, 8)}`;
    }

    /**
     * 선택한 옵션으로 배치 처리 시작
     */
    async submitBatchWithOption() {
        const selectedOption = document.querySelector('input[name="batch-option"]:checked');
        if (!selectedOption) {
            console.warn('⚠️ 선택한 옵션 없음');
            alert('처리 방식을 선택해주세요');
            return;
        }
        
        const selectedRange = window.selectedDateRange;
        if (!selectedRange) {
            console.warn('⚠️ 선택한 범위 없음');
            alert('날짜 범위를 선택해주세요');
            return;
        }
        
        // "이전 기록 보기" 옵션인 경우 특별 처리
        if (selectedOption.value === 'view_history') {
            
            // 필터링 정보를 전역 변수에 저장
            window.historyFilter = {
                start_date: selectedRange.start.replace(/-/g, ''),
                end_date: selectedRange.end.replace(/-/g, ''),
                status: ''  // 모든 상태
            };
            
            // UI 초기화
            this.resetBatchUI();
            
            // 이력 페이지로 이동 (배치 처리 없음)
            setTimeout(() => {
                this.switchPage('history');
                this.loadJobHistory(window.historyFilter.start_date, window.historyFilter.end_date);
            }, 500);
            return;
        }
        
        try {
            // API 요청 구성
            const request = {
                start_date: selectedRange.start.replace(/-/g, ''),
                end_date: selectedRange.end.replace(/-/g, ''),
                option_id: selectedOption.value
            };
            
            
            // API 호출
            const response = await api.submitBatchWithOption(request);
            
            
            // 현재 작업을 메모리에 저장 (history 페이지에서 표시하기 위함)
            window.currentJob = response;
            
            // 성공 메시지
            alert(`배치 처리가 시작되었습니다!\n작업 ID: ${response.job_id}`);
            
            // UI 초기화
            this.resetBatchUI();
            
            // 이력 페이지로 이동
            setTimeout(() => {
                this.switchPage('history');
            }, 1000);
        } catch (error) {
            console.error('❌ 처리 실패:', error);
            alert('배치 처리 실패: ' + error.message);
        }
    }

    /**
     * 배치 UI 초기화
     */
    resetBatchUI() {
        // 캘린더 선택 제거
        const calendarEl = document.getElementById('batch-calendar');
        if (calendarEl && calendarEl._flatpickr) {
            calendarEl._flatpickr.clear();
        }
        
        // 선택된 범위 텍스트 초기화
        const selectedRangeEl = document.getElementById('selected-range');
        if (selectedRangeEl) {
            selectedRangeEl.textContent = '선택해주세요';
        }
        
        // 분석 결과 컨테이너 숨김
        const resultContainer = document.getElementById('analysis-result-container');
        if (resultContainer) {
            resultContainer.style.display = 'none';
        }
        
        // 전역 변수 초기화
        window.selectedDateRange = null;
        window.batchAnalysisResult = null;
    }

    /**
     * 날짜 포맷 변환 헬퍼
     */
    convertDateFormat(dateStr, format) {
        if (format === 'YYYYMMDD_to_Date') {
            // YYYYMMDD → Date
            const year = parseInt(dateStr.substring(0, 4));
            const month = parseInt(dateStr.substring(4, 6)) - 1;
            const day = parseInt(dateStr.substring(6, 8));
            return new Date(year, month, day);
        } else if (format === 'Date_to_YYYYMMDD') {
            // Date → YYYYMMDD
            const year = dateStr.getFullYear();
            const month = String(dateStr.getMonth() + 1).padStart(2, '0');
            const day = String(dateStr.getDate()).padStart(2, '0');
            return `${year}${month}${day}`;
        }
        return dateStr;
    }

    /**
     * 날짜 표시 포맷 (YYYY-MM-DD)
     */
    formatDateForDisplay(dateStr) {
        // YYYYMMDD → YYYY-MM-DD
        if (typeof dateStr === 'string' && dateStr.length === 8) {
            return `${dateStr.substring(0, 4)}-${dateStr.substring(4, 6)}-${dateStr.substring(6, 8)}`;
        }
        return dateStr;
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

    // ===== 선택 요약 및 카드 업데이트 =====

    /**
     * 선택 범위의 요약 정보 계산
     */
    calculateSelectionSummary(startDate, endDate) {
        let totalFiles = 0;
        let dateDetails = [];
        
        const dateStatusMap = window.dateStatusMap || {};
        
        // 선택 범위의 모든 날짜 순회
        let current = new Date(startDate);
        while (current <= endDate) {
            const dateStr = this.formatDateAsYYYYMMDD(current);
            const stat = dateStatusMap[dateStr];
            
            if (stat) {
                totalFiles += stat.file_count || 0;
                dateDetails.push({
                    date: dateStr,
                    files: stat.file_count || 0,
                    status: stat.status || 'unknown'
                });
            }
            
            // 다음 날짜로
            current.setDate(current.getDate() + 1);
        }
        
        return {
            dateCount: dateDetails.length,
            totalFiles: totalFiles,
            details: dateDetails
        };
    }

    /**
     * 선택 정보 카드 업데이트
     */
    updateSelectionCard(summary) {
        const card = document.getElementById('selection-info-card');
        if (!card) return;
        
        // 요약 통계 업데이트
        const dateCount = document.getElementById('stats-date-count');
        const totalFiles = document.getElementById('stats-total-files');
        
        if (dateCount) {
            dateCount.textContent = summary.dateCount || 0;
        }
        if (totalFiles) {
            totalFiles.textContent = summary.totalFiles || 0;
        }
        
        // 날짜별 상세 테이블 업데이트
        const tbody = document.getElementById('date-details-tbody');
        if (tbody) {
            tbody.innerHTML = '';
            
            summary.details.forEach(detail => {
                const row = document.createElement('tr');
                const dateDisplay = this.formatDateForDisplay(detail.date);
                const statusText = this.getDateStatusText(detail.status);
                const statusColor = this.getDateStatusColor(detail.status);
                
                row.innerHTML = `
                    <td style="padding: 8px;">${dateDisplay}</td>
                    <td style="padding: 8px; text-align: center;">${detail.files}</td>
                    <td style="padding: 8px; text-align: center;">
                        <span style="background-color: ${statusColor}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 0.85em;">${statusText}</span>
                    </td>
                `;
                tbody.appendChild(row);
            });
        }
        
        // 카드 표시
        card.style.display = 'block';
    }

    /**
     * 날짜 상태 텍스트
     */
    getDateStatusText(status) {
        const statusMap = {
            'done': '완료',
            'incomplete': '부분',
            'ready': '대기',
            'failed': '불가',
            'unknown': '미정'
        };
        return statusMap[status] || status;
    }

    /**
     * 날짜 상태 배경색
     */
    getDateStatusColor(status) {
        const colorMap = {
            'done': '#10b981',
            'incomplete': '#f59e0b',
            'ready': '#3b82f6',
            'failed': '#ef4444',
            'unknown': '#6b7280'
        };
        return colorMap[status] || '#9ca3af';
    }

    /**
     * Date를 YYYYMMDD 문자열로 변환
     */
    formatDateAsYYYYMMDD(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}${month}${day}`;
    }

    // ===== 날짜 입력 필드 관련 메서드 =====

    /**
     * 캘린더에서 입력 필드 업데이트
     */
    updateDateInputsFromCalendar(startStr, endStr) {
        const startInput = document.getElementById('start-date-input');
        const endInput = document.getElementById('end-date-input');
        
        if (startInput) {
            startInput.value = startStr;
            this.clearDateError('start');
        }
        if (endInput) {
            endInput.value = endStr;
            this.clearDateError('end');
        }
    }

    /**
     * 입력 필드 초기화
     */
    clearDateInputs() {
        const startInput = document.getElementById('start-date-input');
        const endInput = document.getElementById('end-date-input');
        
        if (startInput) {
            startInput.value = '';
            this.clearDateError('start');
        }
        if (endInput) {
            endInput.value = '';
            this.clearDateError('end');
        }
    }

    /**
     * 입력 필드 변경 이벤트
     */
    onDateInputChange() {
        const startInput = document.getElementById('start-date-input');
        const endInput = document.getElementById('end-date-input');
        
        const startStr = startInput?.value || '';
        const endStr = endInput?.value || '';
        
        // 둘 다 비어있으면 리턴
        if (!startStr && !endStr) {
            return;
        }
        
        // 현재 선택된 범위와 병합 - 하나만 바껴도 반영되도록
        const finalStartStr = startStr || window.selectedDateRange?.start || '';
        const finalEndStr = endStr || window.selectedDateRange?.end || '';
        
        // 두 값이 모두 존재해야만 진행
        if (!finalStartStr || !finalEndStr) {
            return;
        }
        
        // 범위 검증
        const validationResult = this.validateDateRange(finalStartStr, finalEndStr);
        if (!validationResult.valid) {
            this.showDateError(validationResult.errorType, validationResult.message);
            return;
        }
        
        // 검증 성공 시 에러 메시지 제거
        this.clearDateError('start');
        this.clearDateError('end');
        
        // 캘린더 업데이트 (무한 루프 방지)
        this.updateCalendarFromDateInputsWithoutEvent(finalStartStr, finalEndStr);
        
        // date status 업데이트
        const startDate = new Date(finalStartStr + 'T00:00:00Z');
        const endDate = new Date(finalEndStr + 'T00:00:00Z');
        const summary = this.calculateSelectionSummary(startDate, endDate);
        this.updateSelectionCard(summary);
    }

    /**
     * 범위 검증
     */
    validateDateRange(startStr, endStr) {
        // 날짜 형식 확인
        const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
        if (!dateRegex.test(startStr) || !dateRegex.test(endStr)) {
            return { valid: false, errorType: 'start', message: '날짜 형식: YYYY-MM-DD' };
        }
        
        // UTC 기준으로 생성해서 시간대 문제 방지
        const startDate = new Date(startStr + 'T00:00:00Z');
        const endDate = new Date(endStr + 'T00:00:00Z');
        
        if (isNaN(startDate.getTime()) || isNaN(endDate.getTime())) {
            return { valid: false, errorType: 'start', message: '유효한 날짜가 아닙니다' };
        }
        
        // 타임스탐프로 정확하게 비교
        if (startDate.getTime() > endDate.getTime()) {
            return { valid: false, errorType: 'start', message: '시작일이 종료일보다 뒤입니다' };
        }
        
        if (!window.batchDateRange) {
            return { valid: true };
        }
        
        const minDateStr = window.batchDateRange.min_date ? this.formatDateForDisplay(window.batchDateRange.min_date) : null;
        const maxDateStr = window.batchDateRange.max_date ? this.formatDateForDisplay(window.batchDateRange.max_date) : null;
        
        const minDate = minDateStr ? new Date(minDateStr + 'T00:00:00Z') : null;
        const maxDate = maxDateStr ? new Date(maxDateStr + 'T00:00:00Z') : null;
        
        // 타임스탐프로 정확하게 비교
        if (minDate && startDate.getTime() < minDate.getTime()) {
            return { valid: false, errorType: 'start', message: `범위 초과: ${minDateStr}보다 앞` };
        }
        
        if (maxDate && endDate.getTime() > maxDate.getTime()) {
            return { valid: false, errorType: 'end', message: `범위 초과: ${maxDateStr}를 초과` };
        }
        
        return { valid: true };
    }

    /**
     * 날짜 에러 표시
     */
    showDateError(errorType, message) {
        const errorEl = document.getElementById(`${errorType}-date-error`);
        if (errorEl) {
            errorEl.textContent = message;
            errorEl.style.display = 'block';
        }
    }

    /**
     * 날짜 에러 제거
     */
    clearDateError(errorType) {
        const errorEl = document.getElementById(`${errorType}-date-error`);
        if (errorEl) {
            errorEl.style.display = 'none';
            errorEl.textContent = '';
        }
    }

    /**
     * 입력 필드에서 캘린더 업데이트 (이벤트 무시)
     */
    updateCalendarFromDateInputsWithoutEvent(startStr, endStr) {
        const calendarEl = document.getElementById('batch-calendar');
        if (!calendarEl || !calendarEl._flatpickr) {
            console.warn('⚠️ 캘린더가 초기화되지 않았습니다');
            return;
        }
        
        const startDate = new Date(startStr + 'T00:00:00Z');
        const endDate = new Date(endStr + 'T00:00:00Z');
        
        // 현재 선택된 날짜와 비교 (같으면 스킵)
        const current = calendarEl._flatpickr.selectedDates;
        if (current.length === 2) {
            const currentStart = this.formatDateAsYYYYMMDD(current[0]);
            const currentEnd = this.formatDateAsYYYYMMDD(current[1]);
            
            if (currentStart === startStr && currentEnd === endStr) {
                return;
            }
        }
        
        // change 이벤트 핸들러 임시 해제
        const onChangeHandlers = calendarEl._flatpickr.config.onChange || [];
        calendarEl._flatpickr.config.onChange = [];
        
        // 캘린더 업데이트
        calendarEl._flatpickr.setDate([startDate, endDate], true);
        
        // change 이벤트 핸들러 복원
        calendarEl._flatpickr.config.onChange = onChangeHandlers;
        
    }

    /**
     * 입력 필드에서 캘린더 업데이트 (기존)
     */
    updateCalendarFromDateInputs(startStr, endStr) {
        const calendarEl = document.getElementById('batch-calendar');
        if (!calendarEl || !calendarEl._flatpickr) {
            console.warn('⚠️ 캘린더가 초기화되지 않았습니다');
            return;
        }
        
        const startDate = new Date(startStr);
        const endDate = new Date(endStr);
        
        calendarEl._flatpickr.setDate([startDate, endDate], true);
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
