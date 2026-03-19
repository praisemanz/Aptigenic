const steps = document.querySelectorAll('.onboard-step');
const nextBtn = document.getElementById('next-btn');
const prevBtn = document.getElementById('prev-btn');
const progressFill = document.getElementById('progress-fill');
const progressText = document.getElementById('progress-text');
const loadingOverlay = document.getElementById('loading-overlay');
const loadingSub = document.getElementById('loading-sub');
const uploadZone = document.getElementById('upload-zone');
const resumeFile = document.getElementById('resume-file');
const uploadStatus = document.getElementById('upload-status');
const uploadFilename = document.getElementById('upload-filename');
const uploadRemove = document.getElementById('upload-remove');

let currentStep = 1;
const totalSteps = steps.length;

const selections = {
    timeline: '',
    work_preference: '',
    education: ''
};

// Pre-fill selections from existing chips marked .selected
document.querySelectorAll('.chip.selected').forEach(chip => {
    const group = chip.closest('.option-chips');
    if (group.id === 'timeline-chips') selections.timeline = chip.dataset.value;
    if (group.id === 'work-chips') selections.work_preference = chip.dataset.value;
    if (group.id === 'education-chips') selections.education = chip.dataset.value;
});

document.querySelectorAll('.option-chips').forEach(group => {
    group.querySelectorAll('.chip').forEach(chip => {
        chip.addEventListener('click', () => {
            group.querySelectorAll('.chip').forEach(c => c.classList.remove('selected'));
            chip.classList.add('selected');
            if (group.id === 'timeline-chips') selections.timeline = chip.dataset.value;
            if (group.id === 'work-chips') selections.work_preference = chip.dataset.value;
            if (group.id === 'education-chips') selections.education = chip.dataset.value;
        });
    });
});

// File upload
uploadZone.addEventListener('click', () => resumeFile.click());
uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.classList.add('dragover'); });
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
uploadZone.addEventListener('drop', e => {
    e.preventDefault();
    uploadZone.classList.remove('dragover');
    if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
});
resumeFile.addEventListener('change', () => { if (resumeFile.files.length) handleFile(resumeFile.files[0]); });

uploadRemove.addEventListener('click', () => {
    uploadStatus.style.display = 'none';
    uploadZone.style.display = '';
    document.getElementById('resume').value = '';
    resumeFile.value = '';
});

async function handleFile(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['pdf', 'docx', 'doc', 'txt'].includes(ext)) {
        alert('Please upload a PDF, DOCX, or TXT file.');
        return;
    }

    uploadZone.innerHTML = '<div class="loading-spinner" style="width:24px;height:24px;margin:0 auto;"></div><p class="upload-label">Extracting text...</p>';

    const form = new FormData();
    form.append('file', file);

    try {
        const res = await fetch('/api/upload-resume', { method: 'POST', body: form });
        const data = await res.json();

        if (data.error) {
            alert(data.error);
            resetUploadZone();
            return;
        }

        document.getElementById('resume').value = data.text;
        uploadFilename.textContent = file.name;
        uploadStatus.style.display = 'flex';
        uploadZone.style.display = 'none';
    } catch {
        alert('Upload failed. Please try again.');
        resetUploadZone();
    }
}

function resetUploadZone() {
    uploadZone.innerHTML = '<div class="upload-icon">&#128196;</div><p class="upload-label">Drop a file here or click to browse</p><p class="upload-hint">PDF, DOCX, or TXT — max 10 MB</p>';
}

function updateUI() {
    steps.forEach(s => s.classList.remove('active'));
    document.querySelector(`[data-step="${currentStep}"]`).classList.add('active');
    progressFill.style.width = `${(currentStep / totalSteps) * 100}%`;
    progressText.textContent = `Step ${currentStep} of ${totalSteps}`;
    prevBtn.style.visibility = currentStep === 1 ? 'hidden' : 'visible';

    if (currentStep === totalSteps) {
        nextBtn.innerHTML = 'Analyze my career &#8594;';
        buildConfirmation();
    } else {
        nextBtn.innerHTML = 'Continue &#8594;';
    }
}

function buildConfirmation() {
    const resume = document.getElementById('resume').value.trim();
    const target = document.getElementById('target_role').value.trim();
    const interests = document.getElementById('interests').value.trim();
    const rows = [];
    if (resume) rows.push(['Resume', resume.length > 200 ? resume.slice(0, 200) + '...' : resume]);
    if (target) rows.push(['Target Role', target]);
    if (interests) rows.push(['Interests', interests]);
    if (selections.timeline) rows.push(['Timeline', selections.timeline]);
    if (selections.work_preference) rows.push(['Work Style', selections.work_preference]);
    if (selections.education) rows.push(['Education', selections.education]);
    document.getElementById('confirm-summary').innerHTML = rows.map(([l, v]) =>
        `<div class="confirm-row"><span class="confirm-label">${l}</span><span>${v}</span></div>`
    ).join('') || '<p style="color:var(--text-muted)">No information provided yet.</p>';
}

function validate() {
    if (currentStep === 1) {
        if (!document.getElementById('resume').value.trim()) {
            document.getElementById('resume').focus();
            return false;
        }
    }
    return true;
}

nextBtn.addEventListener('click', async () => {
    if (!validate()) return;

    if (currentStep < totalSteps) { currentStep++; updateUI(); return; }

    const payload = {
        resume: document.getElementById('resume').value.trim(),
        target_role: document.getElementById('target_role').value.trim(),
        interests: document.getElementById('interests').value.trim(),
        timeline: selections.timeline,
        work_preference: selections.work_preference,
        education: selections.education
    };

    loadingOverlay.classList.add('active');
    nextBtn.disabled = true;

    const msgs = ['Building your personalized career map', 'Analyzing skill gaps', 'Generating career paths', 'Creating your weekly action plan', 'Calculating match scores'];
    let i = 0;
    const iv = setInterval(() => { i = (i + 1) % msgs.length; loadingSub.textContent = msgs[i]; }, 2500);

    try {
        const save = await fetch('/api/onboard', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        if (!save.ok) throw new Error('Failed to save profile');
        const analyze = await fetch('/api/analyze', { method: 'POST' });
        if (!analyze.ok) { const err = await analyze.json(); throw new Error(err.error || 'Analysis failed'); }
        window.location.href = '/dashboard';
    } catch (err) {
        clearInterval(iv);
        loadingOverlay.classList.remove('active');
        nextBtn.disabled = false;
        alert('Something went wrong: ' + err.message + '\nPlease try again.');
    }
});

prevBtn.addEventListener('click', () => { if (currentStep > 1) { currentStep--; updateUI(); } });

updateUI();
