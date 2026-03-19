const saveStatus = document.getElementById('save-status');
let saveTimeout;

const selections = {
    timeline: '',
    work_preference: '',
    education: ''
};

document.querySelectorAll('.chip.selected').forEach(chip => {
    const group = chip.closest('.option-chips');
    if (group.id === 'timeline-chips') selections.timeline = chip.dataset.value;
    if (group.id === 'work-chips') selections.work_preference = chip.dataset.value;
    if (group.id === 'education-chips') selections.education = chip.dataset.value;
});

function showSaved() {
    saveStatus.textContent = 'Saved';
    saveStatus.className = 'save-status visible';
    clearTimeout(saveTimeout);
    saveTimeout = setTimeout(() => saveStatus.className = 'save-status', 2000);
}

async function saveField(field, value) {
    await fetch('/api/profile/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [field]: value })
    });
    showSaved();
}

// Text fields: auto-save on blur
document.getElementById('target_role').addEventListener('blur', function () {
    saveField('target_role', this.value.trim());
});

document.getElementById('interests').addEventListener('blur', function () {
    saveField('interests', this.value.trim());
});

document.getElementById('resume').addEventListener('blur', function () {
    saveField('resume_text', this.value.trim());
});

// Chip selectors
document.querySelectorAll('.option-chips').forEach(group => {
    group.querySelectorAll('.chip').forEach(chip => {
        chip.addEventListener('click', () => {
            group.querySelectorAll('.chip').forEach(c => c.classList.remove('selected'));
            chip.classList.add('selected');

            const val = chip.dataset.value;
            if (group.id === 'timeline-chips') { selections.timeline = val; saveField('timeline', val); }
            if (group.id === 'work-chips') { selections.work_preference = val; saveField('work_preference', val); }
            if (group.id === 'education-chips') { selections.education = val; saveField('education', val); }
        });
    });
});

// File upload
const uploadZone = document.getElementById('upload-zone');
const resumeFile = document.getElementById('resume-file');

if (uploadZone && resumeFile) {
    uploadZone.addEventListener('click', () => resumeFile.click());
    uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.classList.add('dragover'); });
    uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
    uploadZone.addEventListener('drop', e => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
    });
    resumeFile.addEventListener('change', () => { if (resumeFile.files.length) handleFile(resumeFile.files[0]); });
}

async function handleFile(file) {
    const form = new FormData();
    form.append('file', file);
    uploadZone.innerHTML = '<div class="loading-spinner" style="width:24px;height:24px;margin:0 auto;"></div><p class="upload-label">Extracting text...</p>';

    try {
        const res = await fetch('/api/upload-resume', { method: 'POST', body: form });
        const data = await res.json();
        if (data.error) { alert(data.error); } else {
            document.getElementById('resume').value = data.text;
            showSaved();
        }
    } catch { alert('Upload failed.'); }

    uploadZone.innerHTML = '<div class="upload-icon">&#128196;</div><p class="upload-label">Upload a new resume (PDF, DOCX, TXT)</p>';
}
