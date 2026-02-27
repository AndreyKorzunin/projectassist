const chatElements = {
    chatMessages: document.getElementById('chatMessages'),
    userInput: document.getElementById('userInput'),
    sendBtn: document.getElementById('sendBtn')
};

document.addEventListener('DOMContentLoaded', () => {
    if (chatElements.sendBtn) {
        chatElements.sendBtn.addEventListener('click', sendMessage);
    }

    if (chatElements.userInput) {
        chatElements.userInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        chatElements.userInput.addEventListener('input', autoResizeTextarea);
    }

    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('quick-reply')) {
            const query = e.target.getAttribute('data-query');
            if (query) {
                chatElements.userInput.value = query;
                chatElements.userInput.focus();
                sendMessage();
            }
        }
    });
});

async function sendMessage() {
    const message = chatElements.userInput.value.trim();
    if (!message || !window.app.getCurrentSessionId()) return;

    addMessage(message, 'user');
    chatElements.userInput.value = '';
    autoResizeTextarea();

    const loadingId = addLoadingMessage();

    try {
        window.app.stats.queries++;
        window.app.saveStats();
        window.app.updateStatsDisplay();

        const response = await fetch('/query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session_id: window.app.getCurrentSessionId(),
                query: message,
                task_type: window.app.getCurrentTaskType()
            })
        });

        if (!response.ok) {
            throw new Error('Ошибка сервера');
        }

        const data = await response.json();

        removeLoadingMessage(loadingId);

        processResponse(data, message);

        scrollToBottom();

    } catch (error) {
        console.error(' Chat error:', error);
        removeLoadingMessage(loadingId);
        addMessage(`Ошибка: ${error.message}`, 'error');
    }
}


function addMessage(text, type = 'bot') {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;

    let content = '';

    if (type === 'error') {
        content = `<div class="message-content"><p> ${text}</p></div>`;
    } else if (type === 'info') {
        content = `<div class="message-content"><p> ${text}</p></div>`;
    } else {
        content = `<div class="message-content"><p>${formatMessage(text)}</p></div>`;
    }

    messageDiv.innerHTML = content;
    chatElements.chatMessages.appendChild(messageDiv);

    return messageDiv;
}

function addLoadingMessage() {
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message message-loading';
    loadingDiv.id = 'loading-' + Date.now();
    loadingDiv.innerHTML = `
        <div class="message-content">
            <p>Думаю над ответом <span class="loading-dots"></span></p>
        </div>
    `;
    chatElements.chatMessages.appendChild(loadingDiv);
    scrollToBottom();
    return loadingDiv.id;
}

function removeLoadingMessage(loadingId) {
    const loadingElement = document.getElementById(loadingId);
    if (loadingElement) {
        loadingElement.remove();
    }
}

function scrollToBottom() {
    chatElements.chatMessages.scrollTop = chatElements.chatMessages.scrollHeight;
}

function processResponse(data, originalQuery) {
    console.log('Response received:', data);

    if (data.task_type === 'answer') {
        processAnswerResponse(data.result);
    } else if (data.task_type === 'grammar_check') {
        processGrammarResponse(data.result);
    } else if (data.task_type === 'find_repeats') {
        processRepeatsResponse(data.result);
    } else if (data.task_type === 'structure_analysis') {
        processStructureResponse(data.result);
    }
}

function processAnswerResponse(result) {
    if (typeof result === 'string') {
        addMessage(result);
    } else {
        addMessage('Неожиданный формат ответа');
    }
}

function processGrammarResponse(result) {
    let message = ' <strong>Результаты проверки грамматики:</strong>\n\n';

    if (result.grammar && result.grammar.status === 'success') {
        message += `<strong>Ошибки (${result.grammar.total_issues}):</strong>\n`;

        if (result.grammar.issues.length > 0) {
            const categories = result.grammar.categories || {};
            for (const [cat, count] of Object.entries(categories)) {
                message += `- ${cat}: ${count} шт.\n`;
            }

            message += '\n<strong>Примеры:</strong>\n';
            result.grammar.issues.slice(0, 5).forEach(issue => {
                message += `\n• <em>${issue.context}</em>\n`;
                message += `  ${issue.message}\n`;
                if (issue.suggestions && issue.suggestions.length > 0) {
                    message += `   Вариант: "${issue.suggestions[0]}"\n`;
                }
            });
        } else {
            message += ' Ошибок не найдено!\n';
        }
    } else if (result.grammar && result.grammar.status === 'disabled') {
        message += ' Проверка грамматики недоступна.\n';
    }


    if (result.style) {
        message += '\n<strong>Стилистический анализ:</strong>\n';
        message += `Найдено проблем: ${result.style.total_issues}\n\n`;

        if (result.style.statistics) {
            for (const [cat, count] of Object.entries(result.style.statistics)) {
                if (count > 0) {
                    message += `- ${cat}: ${count} шт.\n`;
                }
            }
        }

        if (result.style.recommendations && result.style.recommendations.length > 0) {
            message += '\n<strong>Рекомендации:</strong>\n';
            result.style.recommendations.forEach(rec => {
                message += `• ${rec}\n`;
            });
        }
    }

    addMessage(message);
}

function processRepeatsResponse(result) {
    let message = ' <strong>Анализ повторяющихся фраз:</strong>\n\n';

    if (result.exact_duplicates && result.exact_duplicates.length > 0) {
        message += `<strong>Точные повторы (${result.exact_duplicates.length}):</strong>\n`;
        result.exact_duplicates.slice(0, 5).forEach(dup => {
            message += `\n• "${dup.text}" (встречается ${dup.count} раз)\n`;
        });
    } else {
        message += ' Точных повторов не найдено\n';
    }

    if (result.common_words && result.common_words.length > 0) {
        message += `\n<strong>Часто встречающиеся слова:</strong>\n`;
        result.common_words.slice(0, 10).forEach(word => {
            message += `- ${word.word}: ${word.count} раз (${(word.frequency * 100).toFixed(1)}%)\n`;
        });
    }

    message += `\n <strong>Статистика:</strong>\n`;
    message += `- Всего предложений: ${result.total_sentences}\n`;
    message += `- Уникальных: ${result.unique_sentences}\n`;
    message += `- Коэффициент избыточности: ${(result.redundancy_score * 100).toFixed(1)}%\n`;

    addMessage(message);
}

function processStructureResponse(result) {
    let message = ' <strong>Анализ структуры документа:</strong>\n\n';

    if (result.document_type === 'Word') {
        message += `<strong>Заголовки:</strong>\n`;
        message += `- Всего: ${result.headings.total}\n`;

        if (result.headings.by_level) {
            for (const [level, count] of Object.entries(result.headings.by_level)) {
                message += `- Уровень ${level}: ${count} шт.\n`;
            }
        }

        message += `\n<strong>Содержание:</strong>\n`;
        message += `- Абзацев: ${result.content.paragraphs_count}\n`;
        message += `- Средняя длина: ${result.content.avg_paragraph_length} слов\n`;
        message += `- Таблиц: ${result.content.tables_count}\n`;
        message += `- Списков: ${result.content.lists_count}\n`;

        message += `\n<strong>Качество структуры:</strong>\n`;
        message += `- Оценка: ${result.structure_quality.score}/100 (${result.structure_quality.quality})\n`;

        if (result.recommendations && result.recommendations.length > 0) {
            message += `\n<strong>Рекомендации:</strong>\n`;
            result.recommendations.forEach(rec => {
                message += `• ${rec}\n`;
            });
        }
    } else if (result.document_type === 'Excel') {

        }

        if (result.recommendations && result.recommendations.length > 0) {
            
        }
    }

    addMessage(message);
}

function formatMessage(text) {

    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');


    text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');


    text = text.replace(/\n/g, '<br>');

    text = text.replace(/^\s*-\s+(.*)$/gm, '<li>$1</li>');
    text = text.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

    return text;
}


function autoResizeTextarea() {
    if (chatElements.userInput) {
        chatElements.userInput.style.height = 'auto';
        chatElements.userInput.style.height = (chatElements.userInput.scrollHeight) + 'px';
    }
}