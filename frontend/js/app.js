let currentSessionId = null;
let currentTaskType = 'answer';
let stats = {
    documents: 0,
    queries: 0
};

const elements = {
    uploadSection: document.getElementById('uploadSection'),
    documentSection: document.getElementById('documentSection'),
    dropArea: document.getElementById('dropArea'),
    fileInput: document.getElementById('fileInput'),
    browseBtn: document.getElementById('browseBtn'),
    newSessionBtn: document.getElementById('newSessionBtn'),
    backBtn: document.getElementById('backBtn'),
    taskTypeSelect: document.getElementById('taskTypeSelect'),
    docsCount: document.getElementById('docsCount'),
    queriesCount: document.getElementById('queriesCount'),
    loadingOverlay: document.getElementById('loadingOverlay'),
    loadingText: document.getElementById('loadingText')
};

document.addEventListener('DOMContentLoaded', () => {
    console.log(' DocAssistant AI initialized');
    
    setupEventListeners();
    
    checkHealth();
    
    loadStats();
    
    elements.taskTypeSelect.addEventListener('change', (e) => {
        currentTaskType = e.target.value;
        console.log(' Task type changed:', currentTaskType);
    });
});

function setupEventListeners() {
    elements.browseBtn.addEventListener('click', () => elements.fileInput.click());
    elements.fileInput.addEventListener('change', handleFileSelect);
    elements.dropArea.addEventListener('click', () => elements.fileInput.click());
    
    elements.dropArea.addEventListener('dragover', handleDragOver);
    elements.dropArea.addEventListener('dragleave', handleDragLeave);
    elements.dropArea.addEventListener('drop', handleDrop);
    
    elements.newSessionBtn.addEventListener('click', () => {
        showUploadSection();
    });
    
    elements.backBtn.addEventListener('click', () => {
        if (currentSessionId) {
            deleteSession(currentSessionId).then(() => {
                currentSessionId = null;
                showUploadSection();
            });
        } else {
            showUploadSection();
        }
    });
}

function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        uploadFile(file);
    }
}

function handleDragOver(e) {
    e.preventDefault();
    elements.dropArea.classList.add('drag-over');
}

function handleDragLeave(e) {
    e.preventDefault();
    elements.dropArea.classList.remove('drag-over');
}

function handleDrop(e) {
    e.preventDefault();
    elements.dropArea.classList.remove('drag-over');
    
    const file = e.dataTransfer.files[0];
    if (file) {
        uploadFile(file);
    }
}

async function uploadFile(file) {
    showLoading('Загрузка документа...');
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Ошибка загрузки');
        }
        
        const data = await response.json();
        console.log(' Document uploaded:', data);
        
        currentSessionId = data.session_id;
        stats.documents++;
        saveStats();
        updateStatsDisplay();
        
        showDocumentSection(data);
        
    } catch (error) {
        console.error(' Upload error:', error);
        alert(`Ошибка загрузки: ${error.message}`);
    } finally {
        hideLoading();
        elements.fileInput.value = ''; // Reset input
    }
}

function showUploadSection() {
    elements.uploadSection.classList.add('active');
    elements.documentSection.classList.remove('active');
}

function showDocumentSection(docInfo) {
    elements.uploadSection.classList.remove('active');
    elements.documentSection.classList.add('active');
    
    document.getElementById('docTitle').textContent = docInfo.filename;
    document.getElementById('docTypeBadge').textContent = docInfo.doc_type.toUpperCase();
    
    let statsText = '';
    if (docInfo.statistics) {
        if (docInfo.doc_type === 'word') {
            statsText = `${docInfo.statistics.total_words || 0} слов, ${docInfo.statistics.paragraphs_count || 0} абзацев`;
        } else if (docInfo.doc_type === 'excel') {
            statsText = `${docInfo.statistics.sheets_count || 0} листов, ${docInfo.statistics.total_rows || 0} строк`;
        } else if (docInfo.doc_type === 'pdf') {
            statsText = `${docInfo.statistics.pages || 0} страниц, ${docInfo.statistics.total_words || 0} слов`;
        }
    }
    document.getElementById('docStats').textContent = statsText;
    
    document.getElementById('chatMessages').innerHTML = `
        <div class="message bot-message">
            <div class="message-content">
                <p>Документ "<strong>${docInfo.filename}</strong>" успешно загружен и проанализирован!</p>
                <p>Что вас интересует?</p>
                <div class="quick-replies">
                    <button class="quick-reply" data-query="Какие основные разделы в документе?">Основные разделы</button>
                    <button class="quick-reply" data-query="Есть ли в документе таблицы?">Таблицы</button>
                    <button class="quick-reply" data-query="Проверь грамматику документа">Грамматика</button>
                    <button class="quick-reply" data-query="Найди повторяющиеся фразы">Повторы</button>
                </div>
            </div>
        </div>
    `;
}

async function checkHealth() {
    try {
        const response = await fetch('/health');
        const data = await response.json();
        
        const statusDot = document.querySelector('.status-dot');
        const statusText = document.querySelector('.status-text');
        
        if (data.status === 'ok') {
            statusDot.className = 'status-dot status-online';
            statusText.textContent = 'Сервис работает';
            
            document.querySelector('.version').textContent = `v${data.version}`;
            
            console.log(' Service health check passed');
        } else {
            statusDot.style.background = 'var(--danger-color)';
            statusText.textContent = 'Ошибка сервиса';
        }
    } catch (error) {
        console.error(' Health check failed:', error);
    }
}

async function deleteSession(sessionId) {
    try {
        const response = await fetch(`/sessions/${sessionId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            console.log(' Session deleted');
        }
    } catch (error) {
        console.error(' Session delete error:', error);
    }
}

// ==================== Stats Management ====================
function loadStats() {
    const saved = localStorage.getItem('docAssistantStats');
    if (saved) {
        stats = JSON.parse(saved);
        updateStatsDisplay();
    }
}

function saveStats() {
    localStorage.setItem('docAssistantStats', JSON.stringify(stats));
}

function updateStatsDisplay() {
    if (elements.docsCount) elements.docsCount.textContent = stats.documents;
    if (elements.queriesCount) elements.queriesCount.textContent = stats.queries;
}

function showLoading(message = 'Обработка...') {
    if (elements.loadingText) elements.loadingText.textContent = message;
    if (elements.loadingOverlay) elements.loadingOverlay.style.display = 'flex';
}

function hideLoading() {
    if (elements.loadingOverlay) elements.loadingOverlay.style.display = 'none';
}

function formatDateTime(date) {
    return new Date(date).toLocaleString('ru-RU', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function truncateText(text, maxLength = 100) {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}


window.app = {
    currentSessionId,
    currentTaskType,
    stats,
    showLoading,
    hideLoading,
    showUploadSection,
    formatDateTime,
    truncateText,
    setCurrentSessionId: (id) => { currentSessionId = id; },
    getCurrentSessionId: () => currentSessionId,
    getCurrentTaskType: () => currentTaskType
};