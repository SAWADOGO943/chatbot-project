// ── SÉLECTION DES ÉLÉMENTS DU DOM ──────────────────────────────
const chatMessages = document.getElementById('chatMessages');
const userInput    = document.getElementById('userInput');
const sendBtn      = document.getElementById('sendBtn');
const loader       = document.getElementById('loader');

// ── URLS DES ENDPOINTS ─────────────────────────────────────────
const CHAT_URL    = 'http://localhost:8000/chat';
const RAG_URL     = 'http://localhost:8000/rag/query';
const INDEX_URL   = 'http://localhost:8000/rag/index';
const STATUS_URL  = 'http://localhost:8000/rag/status';

// ── ÉTAT DE L'APPLICATION ──────────────────────────────────────
let currentMode = 'chat';   // 'chat' ou 'rag'

// ── INITIALISATION ─────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    checkRagStatus();
});

// ══════════════════════════════════════════════════════════════
// GESTION DES MODES (CHAT / RAG)
// ══════════════════════════════════════════════════════════════

function switchMode(mode) {
    currentMode = mode;

    // Mise à jour des onglets
    document.getElementById('tabChat').classList.toggle('active', mode === 'chat');
    document.getElementById('tabRag').classList.toggle('active', mode === 'rag');

    // Affichage/masquage du panneau RAG
    document.getElementById('ragPanel').style.display = mode === 'rag' ? 'block' : 'none';

    // Mise à jour du placeholder
    userInput.placeholder = mode === 'rag'
        ? 'Posez une question sur vos documents...'
        : 'Tapez votre message...';

    // Message de transition dans le chat
    const modeMsg = mode === 'rag'
        ? '📚 Mode RAG activé — Je vais chercher dans vos documents pour répondre.'
        : '💬 Mode Chat activé — Je réponds sans base documentaire.';
    appendMessage(modeMsg, 'bot');
}

// ── VÉRIFICATION DU STATUT RAG ─────────────────────────────────
async function checkRagStatus() {
    try {
        const response = await fetch(STATUS_URL);
        const data = await response.json();
        updateRagStatusUI(data.ready, data.message);
    } catch (error) {
        updateRagStatusUI(false, 'Backend non accessible');
    }
}

function updateRagStatusUI(isReady, message) {
    const dot  = document.getElementById('statusDot');
    const text = document.getElementById('statusText');

    dot.textContent  = isReady ? '🟢' : '🔴';
    text.textContent = message;
}

// ── INDEXATION DES DOCUMENTS ──────────────────────────────────
async function indexDocuments() {
    const btn = document.getElementById('indexBtn');
    btn.disabled     = true;
    btn.textContent  = '⏳ Indexation en cours...';

    try {
        const response = await fetch(INDEX_URL, { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            updateRagStatusUI(true, `✅ ${data.message}`);

            // Affiche le résumé d'indexation
            const info = document.getElementById('ragInfo');
            info.style.display = 'block';
            info.textContent   = `📊 ${data.documents_indexed} chunks indexés et prêts`;

            appendMessage(`✅ Indexation réussie ! ${data.message}`, 'bot');
        } else {
            updateRagStatusUI(false, data.message);
            appendMessage(`❌ Indexation échouée : ${data.message}`, 'bot');
        }

    } catch (error) {
        appendMessage(`❌ Erreur : ${error.message}`, 'bot');
    } finally {
        btn.disabled    = false;
        btn.textContent = '🔄 Indexer les documents';
    }
}

// ══════════════════════════════════════════════════════════════
// ENVOI DES MESSAGES (logique principale)
// ══════════════════════════════════════════════════════════════

async function sendMessage() {
    const userText = userInput.value.trim();
    if (!userText) return;

    appendMessage(userText, 'user');
    userInput.value = '';
    userInput.style.height = 'auto';
    setLoading(true);

    try {
        if (currentMode === 'chat') {
            await sendChatMessage(userText);
        } else {
            await sendRagMessage(userText);
        }
    } finally {
        setLoading(false);
    }
}

// ── MODE CHAT (Semaine 1 — inchangé) ──────────────────────────
async function sendChatMessage(text) {
    try {
        const response = await fetch(CHAT_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || `Erreur ${response.status}`);
        }

        const data = await response.json();
        appendMessage(data.reply, 'bot');

    } catch (error) {
        appendMessage(`❌ Erreur Chat : ${error.message}`, 'bot');
    }
}

// ── MODE RAG (Semaine 2) ──────────────────────────────────────
async function sendRagMessage(question) {
    try {
        const response = await fetch(RAG_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: question })
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || `Erreur ${response.status}`);
        }

        const data = await response.json();

        // Affiche la réponse avec les sources
        appendRagMessage(data.answer, data.sources, data.chunks_used);

    } catch (error) {
        appendMessage(`❌ Erreur RAG : ${error.message}`, 'bot');
    }
}

// ══════════════════════════════════════════════════════════════
// AFFICHAGE DES MESSAGES
// ══════════════════════════════════════════════════════════════

// Fonction d'affichage standard (Semaine 1 — inchangée)
function appendMessage(text, sender) {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', `${sender}-message`);

    const bubble = document.createElement('div');
    bubble.classList.add('message-bubble');
    bubble.textContent = text;

    messageDiv.appendChild(bubble);
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

// Fonction d'affichage RAG — avec sources citées
function appendRagMessage(answer, sources, chunksUsed) {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', 'bot-message');

    const bubble = document.createElement('div');
    bubble.classList.add('message-bubble');

    // Réponse principale
    const answerText = document.createElement('div');
    answerText.textContent = answer;
    bubble.appendChild(answerText);

    // Section sources (si des sources existent)
    if (sources && sources.length > 0) {
        const sourcesSection = document.createElement('div');
        sourcesSection.classList.add('sources-section');

        const title = document.createElement('div');
        title.classList.add('sources-title');
        title.textContent = `📎 Sources (${chunksUsed} extraits consultés)`;
        sourcesSection.appendChild(title);

        // Déduplique les sources par nom de fichier
        const uniqueSources = [...new Set(sources.map(s => s.source))];
        uniqueSources.forEach(sourceName => {
            const chip = document.createElement('span');
            chip.classList.add('source-chip');
            chip.textContent = sourceName;
            sourcesSection.appendChild(chip);
        });

        // Affiche le premier extrait à titre d'illustration
        if (sources[0]) {
            const excerpt = document.createElement('div');
            excerpt.classList.add('source-excerpt');
            excerpt.textContent = `"${sources[0].content}"`;
            sourcesSection.appendChild(excerpt);
        }

        bubble.appendChild(sourcesSection);
    }

    messageDiv.appendChild(bubble);
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

// ══════════════════════════════════════════════════════════════
// UTILITAIRES (Semaine 1 — inchangés)
// ══════════════════════════════════════════════════════════════

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function setLoading(isLoading) {
    if (isLoading) {
        loader.style.display = 'flex';
        sendBtn.disabled     = true;
        userInput.disabled   = true;
    } else {
        loader.style.display = 'none';
        sendBtn.disabled     = false;
        userInput.disabled   = false;
        userInput.focus();
    }
}

// ── ÉVÉNEMENTS (inchangés) ─────────────────────────────────────
sendBtn.addEventListener('click', sendMessage);

userInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
});

userInput.addEventListener('input', () => {
    userInput.style.height = 'auto';
    userInput.style.height = userInput.scrollHeight + 'px';
});