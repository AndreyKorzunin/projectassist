
let currentSessionId = null;
let currentTaskType = 'answer';
let stats = {
    documents: 0,
    queries: 0
};


const elements = {
    uploadSection: document.getElementById('uploadSection'),
    documentSection: document.getElementById('documentSection'),

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
