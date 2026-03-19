const chatBox = document.getElementById('chat-box');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const exportBtn = document.getElementById('export-btn');
const newChatBtn = document.getElementById('new-chat-btn');
const sidebarList = document.getElementById('sidebar-list');
const sidebarToggle = document.getElementById('sidebar-toggle');
const sidebar = document.getElementById('chat-sidebar');

let isWaiting = false;
let currentSessionId = typeof ACTIVE_SESSION_ID !== 'undefined' ? ACTIVE_SESSION_ID : null;

marked.setOptions({ breaks: true, gfm: true });

// Render any server-side bot messages as markdown
document.querySelectorAll('.message-row.bot .bot-bubble').forEach(bubble => {
    bubble.innerHTML = marked.parse(bubble.textContent);
});

userInput.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 120) + 'px';
});

userInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

document.querySelectorAll('.prompt-chip[data-prompt]').forEach(chip => {
    chip.addEventListener('click', () => {
        userInput.value = chip.dataset.prompt;
        sendMessage();
    });
});

// Sidebar toggle (works on both desktop and mobile)
sidebarToggle.addEventListener('click', () => {
    const isMobile = window.innerWidth <= 768;
    if (isMobile) {
        sidebar.classList.toggle('open');
    } else {
        sidebar.classList.toggle('collapsed');
        const isCollapsed = sidebar.classList.contains('collapsed');
        sidebarToggle.innerHTML = isCollapsed ? '&#9654;' : '&#9664;';
        localStorage.setItem('sidebar-collapsed', isCollapsed ? '1' : '0');
    }
});

// Restore sidebar state
if (localStorage.getItem('sidebar-collapsed') === '1' && window.innerWidth > 768) {
    sidebar.classList.add('collapsed');
    sidebarToggle.innerHTML = '&#9654;';
} else {
    sidebarToggle.innerHTML = '&#9664;';
}

// New chat
newChatBtn.addEventListener('click', async () => {
    const res = await fetch('/api/sessions/new', { method: 'POST' });
    const data = await res.json();
    if (data.session_id) {
        window.location.reload();
    }
});

// Switch chat
sidebarList.addEventListener('click', async (e) => {
    const item = e.target.closest('.sidebar-item');
    const deleteBtn = e.target.closest('.sidebar-item-delete');

    if (deleteBtn) {
        e.stopPropagation();
        const sid = deleteBtn.dataset.id;
        await fetch('/api/sessions/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: parseInt(sid) })
        });
        deleteBtn.closest('.sidebar-item').remove();
        if (parseInt(sid) === currentSessionId) {
            window.location.reload();
        }
        return;
    }

    if (item) {
        const sid = parseInt(item.dataset.id);
        if (sid === currentSessionId) return;

        const res = await fetch('/api/sessions/switch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sid })
        });
        const data = await res.json();

        sidebarList.querySelectorAll('.sidebar-item').forEach(i => i.classList.remove('active'));
        item.classList.add('active');
        currentSessionId = sid;

        chatBox.innerHTML = '';
        removeSuggestions();

        if (data.history && data.history.length > 0) {
            data.history.forEach(msg => addMessage(msg.role === 'user' ? 'user' : 'bot', msg.content));
        } else {
            chatBox.innerHTML = '<div class="empty-state" id="empty-state"><div class="empty-icon">&#128075;</div><h2>New conversation</h2><p>Ask Aptigenic anything about your career.</p></div>';
        }

        sidebar.classList.remove('open');
    }
});

// Export
exportBtn.addEventListener('click', async () => {
    const res = await fetch('/api/export');
    const data = await res.json();
    const blob = new Blob([data.text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'aptigenic-conversation.txt';
    a.click();
    URL.revokeObjectURL(url);
});

function addMessage(role, content) {
    removeSuggestions();

    const row = document.createElement('div');
    row.className = `message-row ${role}`;

    const avatar = document.createElement('div');
    avatar.className = `avatar ${role === 'user' ? 'user-avatar' : 'bot-avatar'}`;
    avatar.textContent = role === 'user' ? 'Y' : 'A';

    const bubble = document.createElement('div');
    bubble.className = `bubble ${role === 'user' ? 'user-bubble' : 'bot-bubble'}`;

    if (role === 'user') {
        bubble.textContent = content;
    } else {
        bubble.innerHTML = marked.parse(content);
    }

    row.appendChild(avatar);
    row.appendChild(bubble);
    chatBox.appendChild(row);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function removeSuggestions() {
    const existing = document.getElementById('follow-up-suggestions');
    if (existing) existing.remove();
}

function showFollowUpSuggestions(botReply) {
    removeSuggestions();
    const suggestions = generateSuggestions(botReply);
    if (!suggestions.length) return;

    const container = document.createElement('div');
    container.id = 'follow-up-suggestions';
    container.className = 'follow-up-suggestions';

    suggestions.forEach(s => {
        const chip = document.createElement('button');
        chip.className = 'prompt-chip';
        chip.textContent = s.label;
        chip.addEventListener('click', () => {
            userInput.value = s.prompt;
            sendMessage();
        });
        container.appendChild(chip);
    });

    chatBox.appendChild(container);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function generateSuggestions(reply) {
    const lower = reply.toLowerCase();
    const pool = [];

    if (lower.includes('career') || lower.includes('path') || lower.includes('role'))
        pool.push(
            { label: 'Compare these paths', prompt: 'Can you compare the pros and cons of each career path you suggested?' },
            { label: 'Day-in-the-life', prompt: "What does a typical day look like for the top career you recommended?" }
        );
    if (lower.includes('skill') || lower.includes('learn') || lower.includes('gap'))
        pool.push(
            { label: '30-day learning plan', prompt: 'Create a detailed 30-day learning plan for my most critical skill gap.' },
            { label: 'Free resources', prompt: 'What are the best free resources to start building these skills?' }
        );
    if (lower.includes('resume') || lower.includes('cv'))
        pool.push(
            { label: 'Tailor for a job posting', prompt: 'Can you tailor my resume for a specific job posting if I paste it here?' },
            { label: 'Rewrite bullet points', prompt: 'Can you rewrite my resume bullet points to be more impactful using the STAR method?' }
        );
    if (lower.includes('interview') || lower.includes('mock'))
        pool.push(
            { label: 'Behavioral questions', prompt: 'Give me 5 behavioral interview questions for this role and help me practice.' },
            { label: 'Technical prep', prompt: 'What technical questions should I prepare for, and how should I approach them?' }
        );
    if (lower.includes('salary') || lower.includes('offer') || lower.includes('negotiat'))
        pool.push(
            { label: 'Counter-offer script', prompt: 'Help me write a counter-offer script for salary negotiation.' },
            { label: 'Market rate check', prompt: "What's the current market rate for this role in my area?" }
        );
    if (lower.includes('network') || lower.includes('linkedin') || lower.includes('connect'))
        pool.push(
            { label: 'Outreach template', prompt: 'Draft a LinkedIn outreach message I can send to someone in my target field.' },
            { label: 'Networking plan', prompt: 'Give me a weekly networking plan to build connections in this industry.' }
        );

    pool.push(
        { label: "What should I do this week?", prompt: "Based on everything we've discussed, what are the 3 most important things I should do this week?" },
        { label: 'Mock interview', prompt: 'Run me through a mock interview for my target role.' },
        { label: '90-day action plan', prompt: 'Create a detailed 90-day action plan to reach my career goal.' }
    );

    const seen = new Set();
    return pool.filter(s => { if (seen.has(s.label)) return false; seen.add(s.label); return true; }).slice(0, 4);
}

function showTyping() {
    const row = document.createElement('div');
    row.className = 'message-row bot';
    row.id = 'typing-row';
    const avatar = document.createElement('div');
    avatar.className = 'avatar bot-avatar';
    avatar.textContent = 'A';
    const indicator = document.createElement('div');
    indicator.className = 'typing-indicator';
    indicator.innerHTML = '<span class="dot"></span><span class="dot"></span><span class="dot"></span>';
    row.appendChild(avatar);
    row.appendChild(indicator);
    chatBox.appendChild(row);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function hideTyping() {
    const row = document.getElementById('typing-row');
    if (row) row.remove();
}

async function sendMessage() {
    const text = userInput.value.trim();
    if (!text || isWaiting) return;

    const empty = document.getElementById('empty-state');
    if (empty) empty.remove();

    isWaiting = true;
    sendBtn.disabled = true;

    addMessage('user', text);
    userInput.value = '';
    userInput.style.height = 'auto';

    showTyping();

    try {
        const body = 'msg=' + encodeURIComponent(text) + (currentSessionId ? '&session_id=' + currentSessionId : '');
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: body,
        });
        const data = await res.json();
        hideTyping();

        if (data.reply) {
            addMessage('bot', data.reply);
            showFollowUpSuggestions(data.reply);
        } else if (data.error) {
            addMessage('bot', '\u26a0\ufe0f ' + data.error);
        }

        if (data.session_id && data.session_id !== currentSessionId) {
            currentSessionId = data.session_id;
        }
    } catch (err) {
        hideTyping();
        addMessage('bot', '\u26a0\ufe0f Connection error. Please check your network and try again.');
    }

    isWaiting = false;
    sendBtn.disabled = false;
    userInput.focus();
}

// Auto-scroll to bottom on load if there's history
if (chatBox.children.length > 0 && !document.getElementById('empty-state')) {
    chatBox.scrollTop = chatBox.scrollHeight;
}

// Auto-send from query parameter
const params = new URLSearchParams(window.location.search);
const autoPrompt = params.get('prompt');
if (autoPrompt) {
    window.history.replaceState({}, '', window.location.pathname);
    userInput.value = autoPrompt;
    setTimeout(() => sendMessage(), 300);
}
