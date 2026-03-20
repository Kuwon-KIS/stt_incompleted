/**
 * API 통신 모듈
 * 백엔드 API와의 모든 통신을 담당
 */

class API {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl || window.location.origin;
    }

    /**
     * GET 요청
     */
    async get(endpoint) {
        const response = await fetch(`${this.baseUrl}${endpoint}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    }

    /**
     * POST 요청
     */
    async post(endpoint, data) {
        const response = await fetch(`${this.baseUrl}${endpoint}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    }

    /**
     * DELETE 요청
     */
    async delete(endpoint) {
        const response = await fetch(`${this.baseUrl}${endpoint}`, {
            method: 'DELETE',
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    }

    // ===== Health & Status =====

    /**
     * 시스템 상태 조회
     */
    async getHealthz() {
        return this.get('/healthz');
    }

    // ===== Batch Processing =====

    /**
     * 배치 처리 시작 (3가지 케이스 처리)
     * 
     * @param {Object} batchData
     *   - startDate: 시작 날짜 (YYYYMMDD)
     *   - endDate: 종료 날짜 (YYYYMMDD)
     *   - forceReprocess: boolean (기본값: false) - 기존 완료된 작업도 재처리
     *   - handleOverlap: string (기본값: "new") - "new" / "reprocess_all" / "skip_overlap"
     */
    async submitBatch(batchData) {
        return this.post('/process/batch/submit', {
            start_date: batchData.startDate,
            end_date: batchData.endDate,
            force_reprocess: batchData.forceReprocess || false,
            handle_overlap: batchData.handleOverlap || "new"
        });
    }

    /**
     * 배치 작업 상태 조회
     */
    async getBatchStatus(jobId) {
        return this.get(`/process/batch/status/${jobId}`);
    }

    /**
     * 배치 처리 (동기 - 즉시 결과 반환)
     */
    async processBatch(batchData) {
        return this.post('/process/batch', {
            start_date: batchData.startDate,
            end_date: batchData.endDate,
        });
    }

    // ===== Phase 4: Calendar UI APIs =====

    /**
     * 처리 가능 날짜 범위 조회 (SFTP 또는 Mock)
     * @returns {Object} {min_date, max_date, available_dates, source, test_mode}
     */
    async getDateRange() {
        return this.get('/api/admin/date-range');
    }

    /**
     * 날짜별 통계 조회 (처리 현황)
     * @returns {Object} {dates: [{date, total_files, processed_files, ...}], ...}
     */
    async getDateStats() {
        return this.get('/api/admin/date-stats');
    }

    /**
     * 배치 케이스 분석 및 옵션 조회
     * @param {Object} batchData
     *   - start_date: 시작 날짜 (YYYYMMDD)
     *   - end_date: 종료 날짜 (YYYYMMDD)
     *   - include_empty: 파일 0개 날짜 포함 여부 (기본: false)
     *   - available_dates: 이미 조회한 available_dates 배열 (선택사항, 중복 호출 제거)
     * @returns {Object} {case, user_range, completed_range, overlap_dates, new_dates, options}
     */
    async analyzeBatch(batchData) {
        return this.post('/api/admin/batch-analysis', {
            start_date: batchData.start_date,
            end_date: batchData.end_date,
            include_empty: batchData.include_empty || false,
            available_dates: batchData.available_dates || null
        });
    }

    /**
     * 배치 처리 시작 (옵션 선택 후)
     * @param {Object} request
     *   - start_date, end_date, option_id
     */
    async submitBatchWithOption(request) {
        return this.post('/process/batch/submit', request);
    }

    /**
     * 배치 결과 CSV 다운로드
     */
    async downloadBatchResults(jobId) {
        const url = `${this.baseUrl}/process/batch/results/${jobId}/download`;
        window.location.href = url;
    }

    // ===== Date Statistics =====

    /**
     * 날짜별 통계 조회 (대시보드용)
     */
    async getDateStatistics(startDate = null, endDate = null) {
        let url = '/api/admin/date-stats';
        const params = [];
        
        if (startDate) params.push(`start_date=${startDate}`);
        if (endDate) params.push(`end_date=${endDate}`);
        
        if (params.length > 0) {
            url += '?' + params.join('&');
        }
        
        return this.get(url);
    }

    // ===== Templates =====

    /**
     * 템플릿 목록 조회
     */
    async getTemplates() {
        return this.get('/templates');
    }

    /**
     * 특정 템플릿 조회
     */
    async getTemplate(name) {
        return this.get(`/templates/${name}`);
    }

    /**
     * 템플릿 생성 또는 수정
     */
    async saveTemplate(name, content) {
        return this.post('/templates', {
            name: name,
            content: content,
        });
    }

    /**
     * 템플릿 삭제
     */
    async deleteTemplate(name) {
        return this.delete(`/templates/${name}`);
    }

    /**
     * 템플릿 새로고침 (디스크에서 재로드)
     */
    async refreshTemplates() {
        return this.post('/templates/refresh', {});
    }

    // ===== Single File Processing =====

    /**
     * 단일 파일 처리
     */
    async processSingle(processData) {
        return this.post('/process', {
            remote_path: processData.remotePath || null,
            inline_text: processData.inlineText || null,
        });
    }

    // ===== SFTP =====

    /**
     * SFTP 경로의 파일 목록 조회
     */
    async listSFTP(host, path, username, password) {
        return this.post('/sftp/list', {
            host: host,
            path: path,
            username: username,
            password: password,
        });
    }
}

// 전역 API 인스턴스 생성
const api = new API();

/**
 * 로컬 스토리지를 이용한 작업 이력 관리
 */
class JobHistory {
    constructor() {
        this.storageKey = 'stt_job_history';
    }

    /**
     * 작업 추가
     */
    add(jobData) {
        const history = this.getAll();
        const job = {
            id: jobData.jobId || this._generateId(),
            status: jobData.status || 'pending',
            createdAt: jobData.createdAt || new Date().toISOString(),
            dateRange: jobData.dateRange || '',
            results: jobData.results || null,
            error: jobData.error || null,
        };
        history.unshift(job);
        // 최근 100개만 유지
        localStorage.setItem(this.storageKey, JSON.stringify(history.slice(0, 100)));
        return job;
    }

    /**
     * 모든 작업 조회
     */
    getAll() {
        try {
            return JSON.parse(localStorage.getItem(this.storageKey) || '[]');
        } catch (e) {
            return [];
        }
    }

    /**
     * 작업 업데이트
     */
    update(jobId, updates) {
        const history = this.getAll();
        const index = history.findIndex(j => j.id === jobId);
        if (index >= 0) {
            history[index] = { ...history[index], ...updates };
            localStorage.setItem(this.storageKey, JSON.stringify(history));
        }
        return index >= 0 ? history[index] : null;
    }

    /**
     * 작업 삭제
     */
    delete(jobId) {
        const history = this.getAll();
        const filtered = history.filter(j => j.id !== jobId);
        localStorage.setItem(this.storageKey, JSON.stringify(filtered));
    }

    /**
     * 최근 N개 작업 조회
     */
    getRecent(n = 5) {
        return this.getAll().slice(0, n);
    }

    /**
     * 상태별 작업 조회
     */
    getByStatus(status) {
        return this.getAll().filter(j => j.status === status);
    }

    /**
     * ID 생성
     */
    _generateId() {
        return 'job_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    /**
     * 모든 이력 삭제
     */
    clear() {
        localStorage.removeItem(this.storageKey);
    }
}

// 전역 작업 이력 인스턴스 생성
const jobHistory = new JobHistory();
