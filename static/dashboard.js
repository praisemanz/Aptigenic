const loadingOverlay = document.getElementById('loading-overlay');

async function toggleAction(actionId) {
    const item = document.querySelector(`.action-item[data-id="${actionId}"]`);
    if (!item) return;

    await fetch('/api/actions/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action_id: actionId })
    });

    item.classList.toggle('completed');
    const check = item.querySelector('.action-check');
    check.innerHTML = item.classList.contains('completed') ? '&#10003;' : '';
}

document.getElementById('refresh-actions-btn')?.addEventListener('click', async function() {
    this.disabled = true;
    this.textContent = 'Generating...';

    try {
        const res = await fetch('/api/actions/refresh', { method: 'POST' });
        const data = await res.json();

        if (data.error) {
            alert(data.error);
            return;
        }

        window.location.reload();
    } catch (err) {
        alert('Failed to generate new actions: ' + err.message);
    } finally {
        this.disabled = false;
        this.textContent = '↻ Generate next week';
    }
});

document.getElementById('reanalyze-btn')?.addEventListener('click', async function() {
    loadingOverlay.classList.add('active');
    this.disabled = true;

    try {
        const res = await fetch('/api/analyze', { method: 'POST' });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.error || 'Re-analysis failed');
        }
        window.location.reload();
    } catch (err) {
        loadingOverlay.classList.remove('active');
        this.disabled = false;
        alert('Failed: ' + err.message);
    }
});

document.querySelectorAll('.path-card').forEach(card => {
    card.addEventListener('click', () => {
        const title = card.dataset.title;
        window.location.href = `/chat?prompt=${encodeURIComponent(`Tell me more about becoming a ${title}. What would a realistic 90-day plan look like?`)}`;
    });
});
