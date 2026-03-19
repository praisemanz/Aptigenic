document.addEventListener('DOMContentLoaded', function () {
    const toggle = document.getElementById('dark-mode-toggle');
    const saved = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

    if (saved === 'dark' || (!saved && prefersDark)) {
        document.body.classList.add('dark-mode');
        if (toggle) toggle.checked = true;
    }

    if (toggle) {
        toggle.addEventListener('change', function () {
            document.body.classList.toggle('dark-mode', this.checked);
            localStorage.setItem('theme', this.checked ? 'dark' : 'light');
        });
    }
});
