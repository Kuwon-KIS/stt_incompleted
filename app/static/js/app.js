/**
 * STT 탐지 시스템 - 메인 애플리케이션
 */

class App {
    constructor() {
        this.currentPage = 'dashboard';
        this.statusCheckInterval = null;
        this.init();
    }

    async init() {
        console.log('🚀 STT 탐지 시스템 시작...');
        
        // 이벤트 리스너 등록
        this.setupEventListeners();
        
        // 초기 상태 로드
        await this.refreshStatus();
        await this.loadTemplates();
        
        // 주기적 상태 업데이트
        this.statusCheckInterval = setInterval(() => this.refreshStatus(), 30000);
        
        console.log('✅ 초기화 완료');
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
        document.getElementById('batch-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleBatchSubmit();
        });

        // 탐지 방식 변경 이벤트 (템플릿 활성화/비활성화)
        document.getElementById('call-type').addEventListener('change', (e) => {
            const templateSelect = document.getElementById('template-select');
            if (e.target.value === 'agent') {
                // AI Agent 선택: 템플릿 비활성화
                templateSelect.disabled = true;
                templateSelect.required = false;
            } else {
                // vLLM 선택: 템플릿 활성화
                templateSelect.disabled = false;
                templateSelect.required = true;
            }
        });

        // 템플릿 관리 폼
        document.getElementById('template-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleTemplateSave();
        });

        // 템플릿 선택 이벤트
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('template-card')) {
                this.selectTemplate(e.target.dataset.templateName);
            }
        });

        // 템플릿 삭제 버튼
        document.getElementById('delete-template').addEventListener('click', () => {
            this.handleTemplateDelete();
        });

        // 검색 및 필터
        document.getElementById('search-input').addEventListener('input', () => {
            this.filterJobs();
        });

        document.getElementById('status-filter').addEventListener('change', () => {
            this.filterJobs();
        });

        // 결과 다운로드
        document.getElementById('download-results').addEventListener('click', () => {
            this.downloadResults();
        });
    }

    // ===== Page Navigation =====

    switchPage(pageName) {
        // Hide all pages
        document.querySelectorAll('.page').forEach(page => {
            page.classList.remove('active');
        });

        // Show selected page
        document.getElementById(pageName).classList.add('active');

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
        } else if (pageName === 'templates') {
            this.loadTemplates();
        }
    }

    // ===== Dashboard =====

    async refreshStatus() {
        try {
            const status = await api.getHealthz();
            this.updateStatusDisplay(status);
            this.updateRecentJobs();
        } catch (error) {
            console.error('상태 조회 실패:', error);
            document.getElementById('status-text').textContent = '오류';
        }
    }

    updateStatusDisplay(status) {
        // Uptime
        const uptimeSeconds = status.uptime_seconds;
        const uptime = this.formatUptime(uptimeSeconds);
        document.getElementById('uptime').textContent = uptime;

        // Environment
        document.getElementById('env').textContent = status.app_env || 'unknown';

        // Status indicator
        const statusDot = document.querySelector('.status-dot');
        if (status.status === 'ok') {
            statusDot.style.backgroundColor = '#10b981';
            document.getElementById('status-text').textContent = '정상';
        }
    }

    updateRecentJobs() {
        const recentJobs = jobHistory.getRecent(5);
        const container = document.getElementById('recent-jobs');

        if (recentJobs.length === 0) {
            container.innerHTML = '<p class="empty-state">작업 이력이 없습니다</p>';
            return;
        }

        container.innerHTML = recentJobs.map(job => `
            <div class="job-item ${job.status}">
                <div><strong>${job.dateRange}</strong></div>
                <div>상태: <span class="status-badge ${job.status}">${this.getStatusText(job.status)}</span></div>
                <div>생성: ${new Date(job.createdAt).toLocaleString()}</div>
            </div>
        `).join('');
    }

    // ===== Batch Processing =====

    async handleBatchSubmit() {
        const startDateInput = document.getElementById('start-date').value;
        const endDateInput = document.getElementById('end-date').value;
        const callType = document.getElementById('call-type').value;
        const templateName = document.getElementById('template-select').value;

        // HTML date input을 YYYYMMDD 형식으로 변환 (예: 2026-03-16 → 20260316)
        const startDate = startDateInput.replace(/-/g, '');
        const endDate = endDateInput.replace(/-/g, '');

        // 날짜 검증 (이미 HTML5 date input에 의해 검증됨)
        if (!startDateInput || !endDateInput) {
            alert('시작 날짜와 종료 날짜를 입력하세요.');
            return;
        }

        if (startDate > endDate) {
            alert('시작 날짜가 종료 날짜보다 클 수 없습니다.');
            return;
        }

        try {
            // 진행 상황 표시
            document.getElementById('progress-container').style.display = 'block';
            document.getElementById('results-container').style.display = 'none';

            // 배치 작업 제출
            const response = await api.submitBatch({
                startDate,
                endDate,
                callType,
                templateName: callType === 'agent' ? null : templateName,  // AI Agent일 때는 템플릿 미전송
            });

            const jobId = response.job_id;
            console.log(`✅ 배치 작업 제출: ${jobId}`);

            // 작업 이력에 추가
            jobHistory.add({
                jobId,
                dateRange: `${startDate} ~ ${endDate}`,
                status: 'pending',
            });

            // 상태 모니터링 시작
            this.monitorBatchJob(jobId);
        } catch (error) {
            alert(`배치 처리 실패: ${error.message}`);
            console.error('배치 처리 오류:', error);
        }
    }

    async monitorBatchJob(jobId) {
        const maxAttempts = 1800; // 30분 (1초 주기)
        let attempts = 0;

        const checkStatus = async () => {
            try {
                const status = await api.getBatchStatus(jobId);

                // 진행 상황 업데이트
                if (status.status === 'running') {
                    const completed = status.results ? status.results.length : 0;
                    document.getElementById('progress-count').textContent = 
                        `${completed} / 계산 중...`;
                    document.getElementById('progress-status').textContent = '실행 중...';
                }

                // 완료 또는 오류
                if (status.status === 'completed' || status.status === 'failed') {
                    this.displayBatchResults(status);
                    jobHistory.update(jobId, { status: status.status, results: status.results });
                    return;
                }

                // 계속 모니터링
                if (attempts < maxAttempts) {
                    attempts++;
                    setTimeout(checkStatus, 1000);
                } else {
                    alert('작업 모니터링 타임아웃');
                }
            } catch (error) {
                console.error('상태 조회 오류:', error);
                attempts++;
                if (attempts < maxAttempts) {
                    setTimeout(checkStatus, 5000);
                }
            }
        };

        checkStatus();
    }

    displayBatchResults(status) {
        document.getElementById('progress-container').style.display = 'none';
        document.getElementById('results-container').style.display = 'block';

        const results = status.results || [];
        const successCount = results.filter(r => r.success).length;
        const errorCount = results.filter(r => !r.success).length;

        // 요약
        document.getElementById('result-total').textContent = results.length;
        document.getElementById('result-success').textContent = successCount;
        document.getElementById('result-error').textContent = errorCount;

        // 결과 테이블
        const tbody = document.querySelector('.results-table tbody');
        tbody.innerHTML = results.map(r => `
            <tr>
                <td>${r.date}</td>
                <td>${r.filename}</td>
                <td><span class="status-badge ${r.success ? 'success' : 'error'}">
                    ${r.success ? '성공' : '실패'}
                </span></td>
                <td>${r.error || (r.result?.status === 'ok' ? '완료' : '')}</td>
            </tr>
        `).join('');

        // 스크롤
        document.getElementById('results-container').scrollIntoView({ behavior: 'smooth' });
    }

    downloadResults() {
        const results = document.querySelector('.results-table tbody').innerText;
        const csv = '날짜,파일명,상태,메시지\n' + 
                    results.split('\n').map(r => r.split('\t').join(',')).join('\n');
        
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `results_${new Date().toISOString().slice(0, 10)}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    }

    // ===== Templates =====

    async loadTemplates() {
        try {
            const response = await api.getTemplates();
            const templates = response.templates || [];

            // 템플릿 목록 업데이트
            const listContainer = document.getElementById('templates-list');
            listContainer.innerHTML = templates.map(name => `
                <div class="template-card" data-template-name="${name}">
                    <div class="template-name">${name}</div>
                    <div class="template-preview">클릭하여 편집...</div>
                </div>
            `).join('');

            // 템플릿 선택 드롭다운 업데이트
            const selectContainer = document.getElementById('template-select');
            selectContainer.innerHTML = templates.map(name => `
                <option value="${name}">${name}</option>
            `).join('');

            // 배치 페이지의 템플릿 선택
            const batchSelectContainer = document.getElementById('template-select');
            batchSelectContainer.innerHTML = templates.map(name => `
                <option value="${name}">${name}</option>
            `).join('');
        } catch (error) {
            console.error('템플릿 로드 실패:', error);
        }
    }

    async selectTemplate(templateName) {
        try {
            const response = await api.getTemplate(templateName);
            const content = response.content;

            // 폼에 채우기
            document.getElementById('template-name').value = templateName;
            document.getElementById('template-content').value = content;

            // 선택 표시
            document.querySelectorAll('.template-card').forEach(card => {
                card.classList.remove('active');
            });
            event.target.closest('.template-card').classList.add('active');

            // 삭제 버튼 표시
            document.getElementById('delete-template').style.display = 'block';
        } catch (error) {
            console.error('템플릿 조회 실패:', error);
        }
    }

    async handleTemplateSave() {
        const name = document.getElementById('template-name').value;
        const content = document.getElementById('template-content').value;

        if (!name || !content) {
            alert('템플릿 이름과 내용은 필수입니다.');
            return;
        }

        try {
            await api.saveTemplate(name, content);
            alert('✅ 템플릿이 저장되었습니다.');
            
            // 템플릿 목록 새로고침
            await this.loadTemplates();
            
            // 폼 초기화
            document.getElementById('template-form').reset();
            document.getElementById('delete-template').style.display = 'none';
        } catch (error) {
            alert(`템플릿 저장 실패: ${error.message}`);
        }
    }

    async handleTemplateDelete() {
        const name = document.getElementById('template-name').value;
        if (!name) {
            alert('삭제할 템플릿을 선택하세요.');
            return;
        }

        if (!confirm(`"${name}" 템플릿을 삭제하시겠습니까?`)) {
            return;
        }

        try {
            await api.deleteTemplate(name);
            alert('✅ 템플릿이 삭제되었습니다.');
            
            // 템플릿 목록 새로고침
            await this.loadTemplates();
            
            // 폼 초기화
            document.getElementById('template-form').reset();
            document.getElementById('delete-template').style.display = 'none';
        } catch (error) {
            alert(`템플릿 삭제 실패: ${error.message}`);
        }
    }

    // ===== Job History =====

    loadJobHistory() {
        const jobs = jobHistory.getAll();
        const tbody = document.querySelector('.jobs-table tbody');

        if (jobs.length === 0) {
            tbody.innerHTML = '<tr class="empty-state"><td colspan="5">작업 이력이 없습니다</td></tr>';
            return;
        }

        tbody.innerHTML = jobs.map(job => `
            <tr>
                <td>${job.id}</td>
                <td><span class="status-badge ${job.status}">${this.getStatusText(job.status)}</span></td>
                <td>${new Date(job.createdAt).toLocaleString()}</td>
                <td>${job.dateRange}</td>
                <td>
                    <button class="btn btn-secondary btn-small" onclick="app.viewJobDetails('${job.id}')">조회</button>
                </td>
            </tr>
        `).join('');
    }

    filterJobs() {
        const searchTerm = document.getElementById('search-input').value.toLowerCase();
        const statusFilter = document.getElementById('status-filter').value;

        const rows = document.querySelectorAll('.jobs-table tbody tr');
        rows.forEach(row => {
            if (row.classList.contains('empty-state')) return;

            const jobId = row.cells[0].textContent.toLowerCase();
            const status = row.cells[1].textContent.toLowerCase();

            const matchesSearch = jobId.includes(searchTerm);
            const matchesStatus = !statusFilter || status.includes(statusFilter);

            row.style.display = matchesSearch && matchesStatus ? '' : 'none';
        });
    }

    viewJobDetails(jobId) {
        const job = jobHistory.getAll().find(j => j.id === jobId);
        if (job && job.results) {
            console.log('작업 상세:', job);
            alert(`작업 ID: ${jobId}\n상태: ${job.status}\n결과: ${job.results.length}개 파일`);
        }
    }

    // ===== Utilities =====

    validateDate(dateStr) {
        // HTML5 date input은 YYYY-MM-DD 형식을 사용하므로 이전 YYYYMMDD 형식 검증은 사용되지 않음
        // 하지만 호환성을 위해 YYYYMMDD 형식도 검증 가능
        return /^\d{8}$/.test(dateStr) && !isNaN(parseInt(dateStr)) || /^\d{4}-\d{2}-\d{2}$/.test(dateStr);
    }

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

// 앱 초기화
document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
});
