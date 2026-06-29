// ── CONFIGURATION ───────────────────────────────────────────────────
// URL de base de votre backend sur Render
const BASE_API_URL = 'https://chatbot-project-n3q5.onrender.com';

// ── ÉTAT DE L'APPLICATION ────────────────────────────────────────────
let currentSessionId = null;
let isWaiting = false;

// ── ÉLÉMENTS DU DOM ──────────────────────────────────────────────────
const sessionsList      = document.getElementById('sessionsList');
const messagesContainer = document.getElementById('messagesContainer');
const userInput         = document.getElementById('userInput');
const sendBtn           = document.getElementById('sendBtn');
const btnNewChat        = document.getElementById('btnNewChat');
const chatTitle         = document.getElementById('chatTitle');

// ══════════════════════════════════════════════════════════════════════
// SIDEBAR — GESTION DES SESSIONS
async function loadSessions() {
    try {
        // Correction : URL propre
        const response = await fetch(`${BASE_API_URL}/memory-agent/sessions`);
        
        if (!response.ok) throw new Error(`Erreur HTTP: ${response.status}`);
        
        const data = await response.json();
        const sessions = data.sessions || [];
        
        renderSessions(sessions);
    } catch (error) {
        console.error('❌ Erreur chargement sessions :', error);
    }
}

function renderSessions(sessions) {
    if (sessions.length === 0) {
        sessionsList.innerHTML = '<p class="sessions-empty">Aucune conversation</p>';
        return;
    }

    const groups = groupSessionsByPeriod(sessions);
    let html = '';

    for (const [label, items] of Object.entries(groups)) {
        if (items.length === 0) continue;
        html += `<div class="session-group-label">${label}</div>`;
        for (const session of items) {
            const isActive = session.session_id === currentSessionId;
            html += `
                <div class="session-item ${isActive ? 'active' : ''}" data-id="${session.session_id}" onclick="selectSession('${session.session_id}')">
                    <span class="session-item-title">Session du ${formatDate(session.created_at)}</span>
                    <span class="session-item-meta">${session.total_turns || 0} msg</span>
                    <button class="session-item-delete" onclick="deleteSession(event, '${session.session_id}')">✕</button>
                </div>
            `;
        }
    }
    sessionsList.innerHTML = html;
}

// ... (Gardez vos fonctions groupSessionsByPeriod, formatDate ici) ...

async function loadSessionHistory(sessionId) {
    try {
        // Correction : URL propre sans doublon
        const response = await fetch(`${BASE_API_URL}/memory-agent/sessions/${sessionId}`);
        if (!response.ok) return;

        const data = await response.json();
        messagesContainer.innerHTML = '';
        chatTitle.textContent = `Session du ${formatDate(data.created_at || new Date().toISOString())}`;

        (data.history || []).forEach(msg => {
            appendMessage(msg.role === 'user' ? 'user' : 'agent', msg.content);
        });
        scrollToBottom();
    } catch (error) {
        console.error('Erreur chargement historique :', error);
    }
}

async function deleteSession(event, sessionId) {
    event.stopPropagation();
    if (!confirm('Supprimer cette conversation ?')) return;

    try {
        await fetch(`${BASE_API_URL}/memory-agent/sessions/${sessionId}`, { method: 'DELETE' });
        if (currentSessionId === sessionId) startNewChat();
        await loadSessions();
    } catch (error) {
        console.error('Erreur suppression :', error);
    }
}

// ══════════════════════════════════════════════════════════════════════
// CHAT — ENVOI MESSAGES
async function sendMessage() {
    const message = userInput.value.trim();
    if (!message || isWaiting) return;

    userInput.value = '';
    appendMessage('user', message);
    const typingId = appendTyping();

    isWaiting = true;
    sendBtn.disabled = true;

    try {
        // Correction : URL propre
        const response = await fetch(`${BASE_API_URL}/memory-agent/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, session_id: currentSessionId })
        });

        const data = await response.json();
        if (!currentSessionId) {
            currentSessionId = data.session_id;
            await loadSessions();
        }

        removeTyping(typingId);
        appendMessage('agent', data.response);
        scrollToBottom();
    } catch (error) {
        removeTyping(typingId);
        appendMessage('agent', 'Erreur serveur.');
    } finally {
        isWaiting = false;
        sendBtn.disabled = false;
    }
}

// ... (Gardez vos fonctions utilitaires : appendMessage, appendTyping, etc.)
// Assurez-vous d'appeler init() à la fin
init();