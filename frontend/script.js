// ── CONFIGURATION ───────────────────────────────────────────────────
//const API_URL = 'https://chatbot-project-n3q5.onrender.com'
  //const API_URL = 'http://localhost:8000'
  const API_URL = `${API_URL}/memory-agent/sessions`


// ── ÉTAT DE L'APPLICATION ────────────────────────────────────────────
let currentSessionId = null   // ID de la session active
let isWaiting = false         // Empêche d'envoyer pendant qu'on attend


// ── ÉLÉMENTS DU DOM ──────────────────────────────────────────────────
const sessionsList     = document.getElementById('sessionsList')
const messagesContainer = document.getElementById('messagesContainer')
const userInput        = document.getElementById('userInput')
const sendBtn          = document.getElementById('sendBtn')
const btnNewChat       = document.getElementById('btnNewChat')
const chatTitle        = document.getElementById('chatTitle')


// ══════════════════════════════════════════════════════════════════════
// SIDEBAR — GESTION DES SESSIONS
async function loadSessions() {
    /**
     * Charge toutes les sessions depuis le backend
     * et les affiche dans la sidebar.
     */
    try {
        const response = await fetch(`${API_URL}/memory-agent/sessions`)
        
        // Vérifier si la réponse est OK
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`)
        }
        
        const data = await response.json()
        
        // Structure attendue du JSON (comme dans la capture) :
        // {
        //     "active_sessions": 3,
        //     "sessions": [
        //         {
        //             "session_id": "abc123",
        //             "created_at": "2025-01-15T18:30:00",
        //             "total_turns": 4
        //         }
        //     ]
        // }
        
        const sessions = data.sessions || []
        const activeSessionsCount = data.active_sessions || 0
        
        console.log(`📊 ${activeSessionsCount} session(s) active(s) chargée(s)`)
        console.log('📋 Détails des sessions :', sessions)

        // Appel à renderSessions avec le tableau des sessions
        renderSessions(sessions)
        
    } catch (error) {
        console.error('❌ Erreur chargement sessions :', error)
        // Optionnel : afficher un message d'erreur dans l'UI
        // showErrorMessage('Impossible de charger les sessions')
    }
}

function renderSessions(sessions) {
    /**
     * Affiche les sessions dans la sidebar.
     * Les groupe par période : Aujourd'hui, Cette semaine, Plus ancien.
     */
    if (sessions.length === 0) {
        sessionsList.innerHTML = '<p class="sessions-empty">Aucune conversation</p>'
        return
    }

    // Grouper les sessions par période
    const groups = groupSessionsByPeriod(sessions)
    let html = ''

    for (const [label, items] of Object.entries(groups)) {
        if (items.length === 0) continue

        html += `<div class="session-group-label">${label}</div>`

        for (const session of items) {
            const isActive = session.session_id === currentSessionId
            const date = formatDate(session.created_at)
            const turns = session.total_turns || 0

            html += `
                <div class="session-item ${isActive ? 'active' : ''}"
                     data-id="${session.session_id}"
                     onclick="selectSession('${session.session_id}')">
                    <span class="session-item-title">
                        Session du ${date}
                    </span>
                    <span class="session-item-meta">${turns} msg</span>
                    <button class="session-item-delete"
                            onclick="deleteSession(event, '${session.session_id}')"
                            title="Supprimer">
                        ✕
                    </button>
                </div>
            `
        }
    }

    sessionsList.innerHTML = html
}

function groupSessionsByPeriod(sessions) {
    /**
     * Regroupe les sessions par période.
     * Retourne un objet { "Aujourd'hui": [...], "Cette semaine": [...], ... }
     */
    const now = new Date()
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000)

    const groups = {
        "Aujourd'hui": [],
        "Cette semaine": [],
        "Plus ancien": [],
    }

    for (const session of sessions) {
        const date = new Date(session.created_at)

        if (date >= today) {
            groups["Aujourd'hui"].push(session)
        } else if (date >= weekAgo) {
            groups["Cette semaine"].push(session)
        } else {
            groups["Plus ancien"].push(session)
        }
    }

    return groups
}

async function selectSession(sessionId) {
    /**
     * Sélectionne une session et charge son historique.
     * Appelé quand l'utilisateur clique sur une session dans la sidebar.
     */
    currentSessionId = sessionId

    // Mettre à jour la sidebar visuellement
    document.querySelectorAll('.session-item').forEach(el => {
        el.classList.toggle('active', el.dataset.id === sessionId)
    })

    // Charger l'historique de cette session
    await loadSessionHistory(sessionId)
}

async function loadSessionHistory(sessionId) {
    /**
     * Charge et affiche tous les messages d'une session.
     */
    try {
        const response = await fetch(`${API_URL}/memory-agent/sessions/${sessionId}`)

        if (!response.ok) {
            console.error('Session introuvable')
            return
        }

        const data = await response.json()

        // Vider la zone de chat
        messagesContainer.innerHTML = ''

        // Mettre à jour le titre
        chatTitle.textContent = `Session du ${formatDate(data.created_at || new Date().toISOString())}`

        // Afficher chaque message de l'historique
        const history = data.history || []

        if (history.length === 0) {
            messagesContainer.innerHTML = `
                <div class="welcome-message">
                    <p>Conversation vide — envoyez un message pour commencer.</p>
                </div>
            `
            return
        }

        for (const msg of history) {
            // Le backend retourne role: 'user' ou 'assistant'
            const role = msg.role === 'user' ? 'user' : 'agent'
            appendMessage(role, msg.content)
        }

        scrollToBottom()

    } catch (error) {
        console.error('Erreur chargement historique :', error)
    }
}

async function deleteSession(event, sessionId) {
    /**
     * Supprime une session après confirmation.
     * event.stopPropagation() empêche de sélectionner la session en même temps.
     */
    event.stopPropagation()

    if (!confirm('Supprimer cette conversation ?')) return

    try {
        await fetch(`${API_URL}/memory-agent/sessions/${sessionId}`, {
            method: 'DELETE'
        })

        // Si c'était la session active, réinitialiser
        if (currentSessionId === sessionId) {
            currentSessionId = null
            messagesContainer.innerHTML = `
                <div class="welcome-message">
                    <p>Conversation supprimée.</p>
                    <p>Démarrez une nouvelle conversation.</p>
                </div>
            `
            chatTitle.textContent = 'Nouvelle conversation'
        }

        // Rafraîchir la sidebar
        await loadSessions()

    } catch (error) {
        console.error('Erreur suppression :', error)
    }
}

function startNewChat() {
    /**
     * Réinitialise l'interface pour une nouvelle conversation.
     * Ne crée pas de session en base — elle sera créée au premier message.
     */
    currentSessionId = null

    // Désélectionner toutes les sessions dans la sidebar
    document.querySelectorAll('.session-item').forEach(el => {
        el.classList.remove('active')
    })

    // Réinitialiser la zone de chat
    messagesContainer.innerHTML = `
        <div class="welcome-message">
            <p>Bonjour 👋 Je suis votre agent IA avec mémoire.</p>
            <p>Je me souviens de nos conversations précédentes.</p>
        </div>
    `

    chatTitle.textContent = 'Nouvelle conversation'
    userInput.focus()
}


// ══════════════════════════════════════════════════════════════════════
// CHAT — ENVOI ET RÉCEPTION DES MESSAGES
// ══════════════════════════════════════════════════════════════════════

async function sendMessage() {
    /**
     * Envoie le message au backend et affiche la réponse.
     */
    const message = userInput.value.trim()
    if (!message || isWaiting) return

    // Vider la zone de saisie
    userInput.value = ''
    autoResizeTextarea()

    // Supprimer le message de bienvenue s'il est encore là
    const welcome = messagesContainer.querySelector('.welcome-message')
    if (welcome) welcome.remove()

    // Afficher le message utilisateur immédiatement
    appendMessage('user', message)
    scrollToBottom()

    // Afficher "en train d'écrire..."
    const typingId = appendTyping()

    // Désactiver le bouton pendant l'attente
    isWaiting = true
    sendBtn.disabled = true

    try {
        const response = await fetch(`${API_URL}/memory-agent/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
                session_id: currentSessionId,  // null si nouvelle conversation
            })
        })

        if (!response.ok) {
            throw new Error(`Erreur serveur : ${response.status}`)
        }

        const data = await response.json()

        // Récupérer l'ID de session (important pour les nouvelles conversations)
        if (!currentSessionId) {
            currentSessionId = data.session_id
            chatTitle.textContent = `Session du ${formatDate(new Date().toISOString())}`
            // Rafraîchir la sidebar pour afficher la nouvelle session
            await loadSessions()
        }

        // Supprimer le "en train d'écrire..." et afficher la vraie réponse
        removeTyping(typingId)
        appendMessage('agent', data.response)
        scrollToBottom()

    } catch (error) {
        removeTyping(typingId)
        appendMessage('agent', 'Une erreur est survenue. Veuillez réessayer.')
        console.error('Erreur envoi message :', error)
    } finally {
        isWaiting = false
        sendBtn.disabled = false
        userInput.focus()
    }
}


// ══════════════════════════════════════════════════════════════════════
// UTILITAIRES — AFFICHAGE
// ══════════════════════════════════════════════════════════════════════

function appendMessage(role, content) {
    /**
     * Ajoute une bulle de message dans la zone de chat.
     * role : 'user' ou 'agent'
     */
    const avatar = role === 'user' ? '👤' : '🤖'

    const div = document.createElement('div')
    div.className = `message ${role}`
    div.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-bubble">${escapeHtml(content)}</div>
    `

    messagesContainer.appendChild(div)
    return div
}

function appendTyping() {
    /**
     * Affiche un indicateur "en train d'écrire..."
     * Retourne un ID unique pour pouvoir le supprimer ensuite.
     */
    const id = 'typing-' + Date.now()

    const div = document.createElement('div')
    div.className = 'message agent message-typing'
    div.id = id
    div.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-bubble">En train d'écrire...</div>
    `

    messagesContainer.appendChild(div)
    scrollToBottom()
    return id
}

function removeTyping(id) {
    /**
     * Supprime l'indicateur "en train d'écrire..."
     */
    const el = document.getElementById(id)
    if (el) el.remove()
}

function scrollToBottom() {
    /**
     * Fait défiler la zone de chat vers le bas.
     * Appelé après chaque nouveau message.
     */
    messagesContainer.scrollTop = messagesContainer.scrollHeight
}

function escapeHtml(text) {
    /**
     * Sécurise le texte avant de l'injecter dans le DOM.
     * Empêche les injections HTML/XSS.
     */
    const div = document.createElement('div')
    div.appendChild(document.createTextNode(text))
    return div.innerHTML
}

function formatDate(isoString) {
    /**
     * Formate une date ISO en format lisible.
     * "2025-01-15T18:30:00" → "15/01 à 18h30"
     */
    try {
        const date = new Date(isoString)
        const day  = date.getDate().toString().padStart(2, '0')
        const month = (date.getMonth() + 1).toString().padStart(2, '0')
        const hours = date.getHours().toString().padStart(2, '0')
        const mins  = date.getMinutes().toString().padStart(2, '0')
        return `${day}/${month} à ${hours}h${mins}`
    } catch {
        return 'date inconnue'
    }
}

function autoResizeTextarea() {
    /**
     * Ajuste automatiquement la hauteur du textarea
     * selon le contenu (jusqu'à max-height défini en CSS).
     */
    userInput.style.height = 'auto'
    userInput.style.height = userInput.scrollHeight + 'px'
}


// ══════════════════════════════════════════════════════════════════════
// ÉVÉNEMENTS
// ══════════════════════════════════════════════════════════════════════

// Bouton envoyer
sendBtn.addEventListener('click', sendMessage)

// Entrée clavier — Shift+Enter pour nouvelle ligne, Enter pour envoyer
userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        sendMessage()
    }
})

// Redimensionner le textarea à la saisie
userInput.addEventListener('input', autoResizeTextarea)

// Bouton nouvelle conversation
btnNewChat.addEventListener('click', startNewChat)


// ══════════════════════════════════════════════════════════════════════
// INITIALISATION AU CHARGEMENT DE LA PAGE
// ══════════════════════════════════════════════════════════════════════

async function init() {
    /**
     * Point d'entrée — s'exécute quand la page est chargée.
     * Charge les sessions existantes et affiche la plus récente.
     */
    await loadSessions()

    // Mettre le curseur dans le champ de saisie
    userInput.focus()
}

// Lancer l'initialisation
init()