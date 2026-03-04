const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const messagesContainer = document.getElementById('messages');
const connectionDot = document.getElementById('connection-dot');
const connectionStatus = document.getElementById('connection-status');
const typingIndicator = document.getElementById('typing-indicator');
const typingText = document.getElementById('typing-text');

// Modal Elements
const authModal = document.getElementById('auth-modal');
const authAction = document.getElementById('auth-action');
const authDetails = document.getElementById('auth-details');
const btnReject = document.getElementById('btn-reject');
const btnApprove = document.getElementById('btn-approve');

let ws;
let currentAuthId = null;

// Adjust textarea height dynamically
userInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
});

// Press Enter to send (Shift+Enter for new line)
userInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

sendBtn.addEventListener('click', sendMessage);

// Config marked options for secure markdown rendering
marked.setOptions({
    gfm: true,
    breaks: true,
    highlight: function(code, lang) {
        const language = hljs.getLanguage(lang) ? lang : 'plaintext';
        return hljs.highlight(code, { language }).value;
    }
});

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

    ws.onopen = () => {
        connectionDot.className = 'dot connected';
        connectionStatus.textContent = 'Connected to Core';
        connectionStatus.style.color = '#3fb950';
    };

    ws.onclose = () => {
        connectionDot.className = 'dot disconnected';
        connectionStatus.textContent = 'Disconnected. Reconnecting...';
        connectionStatus.style.color = '#f85149';
        setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = (error) => {
        console.error('WebSocket Error:', error);
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'message') {
            appendMessage(data.role, data.content);
            hideTypingIndicator();
        } 
        else if (data.type === 'status') {
            if (data.content === 'idle') {
                hideTypingIndicator();
            } else {
                showTypingIndicator(data.content);
            }
        }
        else if (data.type === 'auth_request') {
            showAuthModal(data.auth_id, data.action, data.details);
        }
        else if (data.type === 'error') {
            appendMessage('error', data.content);
            hideTypingIndicator();
        }
    };
}

function sendMessage() {
    const content = userInput.value.trim();
    if (!content || !ws || ws.readyState !== WebSocket.OPEN) return;

    appendMessage('user', content);
    ws.send(JSON.stringify({
        type: 'chat',
        content: content
    }));

    userInput.value = '';
    userInput.style.height = 'auto';
    showTypingIndicator("thinking...");
}

function appendMessage(role, content) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;
    
    let htmlContent = content;
    if (role === 'agent' || role === 'user') {
        // Parse markdown for agent and user messages
        htmlContent = marked.parse(content);
    } else if (role === 'error') {
        htmlContent = `<p style="color:var(--danger)">⚠️ ${content}</p>`;
    }

    msgDiv.innerHTML = `
        <div class="message-bubble">
            ${htmlContent}
        </div>
    `;
    
    messagesContainer.appendChild(msgDiv);
    // Scroll to bottom
    const chatContainer = document.getElementById('chat-container');
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function showTypingIndicator(status) {
    typingIndicator.classList.remove('hidden');
    typingText.textContent = status;
    const chatContainer = document.getElementById('chat-container');
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function hideTypingIndicator() {
    typingIndicator.classList.add('hidden');
}

// --- Auth Modal Logic ---

function showAuthModal(authId, action, details) {
    currentAuthId = authId;
    authAction.textContent = action;
    authDetails.textContent = details;
    
    // Add glowing effect to the modal content
    const modalContent = document.querySelector('.modal');
    modalContent.style.boxShadow = `0 25px 50px rgba(0,0,0,0.8), 0 0 20px rgba(248, 81, 73, 0.4)`;
    
    authModal.classList.remove('hidden');
    // Ensure modal isn't ignored by preventing pointer events on background
    authModal.classList.add('active'); 
}

function closeAuthModal() {
    authModal.classList.add('hidden');
    authModal.classList.remove('active');
    
    const modalContent = document.querySelector('.modal');
    modalContent.style.boxShadow = `0 25px 50px rgba(0,0,0,0.8), 0 0 0 1px var(--glass-border)`;
}

function constructAuthResponse(approved) {
    if (!currentAuthId || !ws) return;
    
    ws.send(JSON.stringify({
        type: 'auth_response',
        auth_id: currentAuthId,
        approved: approved
    }));
    
    closeAuthModal();
    currentAuthId = null;
}

btnApprove.addEventListener('click', () => constructAuthResponse(true));
btnReject.addEventListener('click', () => constructAuthResponse(false));

// Initialize connection on load
window.addEventListener('load', connectWebSocket);
