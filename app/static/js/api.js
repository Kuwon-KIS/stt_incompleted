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
     * 배치 처리 시작 (비동기)
     */
    async submitBatch(batchData) {
        return this.post('/process/batch/submit', {
            start_date: batchData.startDate,
            end_date: batchData.endDate,
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
