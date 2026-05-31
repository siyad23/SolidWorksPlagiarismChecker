/**
 * SolidWorks Plagiarism Checker — Frontend Logic
 * Two modes: Part Analysis (.sldprt) and Assembly Analysis (.zip Pack & Go)
 */
(() => {
    'use strict';

    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    // ---- State ----
    let currentMode = null;   // 'parts' | 'assemblies'
    let selectedFiles = [];
    let currentSessionId = null;

    // ---- DOM ----
    const modeSection     = $('#modeSection');
    const inputSection    = $('#inputSection');
    const progressSection = $('#progressSection');
    const resultsSection  = $('#resultsSection');
    const dropzone        = $('#dropzone');
    const fileInput       = $('#fileInput');
    const fileList        = $('#fileList');
    const btnAnalyze      = $('#btnAnalyze');
    const btnDriveAnalyze = $('#btnDriveAnalyze');
    const driveUrl        = $('#driveUrl');
    const thresholdSlider = $('#threshold');
    const thresholdValue  = $('#thresholdValue');
    const progressBar     = $('#progressBar');
    const progressText    = $('#progressText');
    const progressDetail  = $('#progressDetail');

    // ---- Mode Selection ----
    $$('.mode-card').forEach(btn => {
        btn.addEventListener('click', () => {
            currentMode = btn.dataset.mode;
            enterMode(currentMode);
        });
    });

    function enterMode(mode) {
        modeSection.classList.add('hidden');
        inputSection.classList.remove('hidden');

        selectedFiles = [];
        renderFileList();
        btnAnalyze.disabled = true;

        if (mode === 'parts') {
            $('#inputTitle').textContent = 'Part File Analysis';
            $('#dropzoneText').innerHTML = 'Drop <strong>.sldprt</strong> files here';
            $('#dropzoneHint').textContent = 'Each file represents one student submission';
            fileInput.setAttribute('accept', '.sldprt,.sldasm,.SLDPRT,.SLDASM');
            // Show Drive tab
            $('#tabDrive').classList.remove('hidden');
        } else {
            $('#inputTitle').textContent = 'Assembly Analysis (Pack & Go)';
            $('#dropzoneText').innerHTML = 'Drop <strong>.zip</strong> files here';
            $('#dropzoneHint').textContent = 'Each ZIP = one student\'s Pack and Go export';
            fileInput.setAttribute('accept', '.zip,.ZIP');
            // Hide Drive tab for assembly mode
            $('#tabDrive').classList.add('hidden');
        }
    }

    // ---- Back Button ----
    $('#backBtn').addEventListener('click', () => {
        inputSection.classList.add('hidden');
        modeSection.classList.remove('hidden');
        currentMode = null;
        selectedFiles = [];
        renderFileList();
    });

    // ---- Tabs ----
    $$('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            $$('.tab-btn').forEach(b => b.classList.remove('active'));
            $$('.tab-content').forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            const tab = btn.dataset.tab;
            const panelId = 'panel' + tab.charAt(0).toUpperCase() + tab.slice(1);
            const panel = document.getElementById(panelId);
            if (panel) panel.classList.add('active');
        });
    });

    // ---- Threshold ----
    thresholdSlider.addEventListener('input', () => {
        thresholdValue.textContent = thresholdSlider.value + '%';
    });

    // ---- Dropzone ----
    dropzone.addEventListener('click', () => fileInput.click());
    dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
    dropzone.addEventListener('drop', (e) => { e.preventDefault(); dropzone.classList.remove('dragover'); addFiles(e.dataTransfer.files); });
    fileInput.addEventListener('change', () => { addFiles(fileInput.files); fileInput.value = ''; });

    function addFiles(fileListObj) {
        const validExts = currentMode === 'assemblies'
            ? ['.zip']
            : ['.sldprt', '.sldasm'];

        for (const f of fileListObj) {
            const ext = f.name.substring(f.name.lastIndexOf('.')).toLowerCase();
            if (validExts.includes(ext) && !selectedFiles.find(sf => sf.name === f.name)) {
                selectedFiles.push(f);
            }
        }
        renderFileList();
        btnAnalyze.disabled = selectedFiles.length === 0;
    }

    function renderFileList() {
        fileList.innerHTML = '';
        selectedFiles.forEach((f, idx) => {
            const ext = f.name.substring(f.name.lastIndexOf('.') + 1).toUpperCase();
            const studentName = f.name.replace(/[_.](?:sldprt|sldasm|zip|SLDPRT|SLDASM|ZIP)$/i, '').replace(/[_.]/g, ' ');
            const chip = document.createElement('div');
            chip.className = 'file-chip';
            chip.innerHTML = `
                <span class="file-ext">${ext}</span>
                <span class="file-chip-name">${studentName}</span>
                <button class="file-chip-remove" data-idx="${idx}">&times;</button>
            `;
            fileList.appendChild(chip);
        });

        $$('.file-chip-remove').forEach(btn => {
            btn.addEventListener('click', () => {
                selectedFiles.splice(parseInt(btn.dataset.idx), 1);
                renderFileList();
                btnAnalyze.disabled = selectedFiles.length === 0;
            });
        });
    }

    // ---- Analyze ----
    btnAnalyze.addEventListener('click', async () => {
        if (selectedFiles.length === 0) return;

        const endpoint = currentMode === 'assemblies' ? '/api/upload/assemblies' : '/api/upload/parts';
        showProgress(currentMode === 'assemblies' ? 'Extracting and analyzing assemblies...' : 'Analyzing part files...');

        const formData = new FormData();
        selectedFiles.forEach(f => formData.append('files', f));

        try {
            simulateProgress(30, 'Uploading files...');
            const resp = await fetch(endpoint, { method: 'POST', body: formData });
            if (!resp.ok) {
                const err = await resp.json();
                throw new Error(err.detail || 'Analysis failed');
            }
            simulateProgress(80, 'Processing results...');
            const data = await resp.json();
            currentSessionId = data.session_id;
            simulateProgress(100, 'Complete!');
            setTimeout(() => showResults(data), 500);
        } catch (err) {
            hideProgress();
            alert('Error: ' + err.message);
        }
    });

    // ---- Drive ----
    btnDriveAnalyze.addEventListener('click', async () => {
        const url = driveUrl.value.trim();
        if (!url) return;
        showProgress('Downloading from Google Drive...');
        const formData = new FormData();
        formData.append('drive_url', url);
        try {
            simulateProgress(40, 'Downloading files from Drive...');
            const resp = await fetch('/api/drive', { method: 'POST', body: formData });
            if (!resp.ok) { const err = await resp.json(); throw new Error(err.detail || 'Drive failed'); }
            simulateProgress(85, 'Processing results...');
            const data = await resp.json();
            currentSessionId = data.session_id;
            simulateProgress(100, 'Complete!');
            setTimeout(() => showResults(data), 500);
        } catch (err) {
            hideProgress();
            alert('Error: ' + err.message);
        }
    });

    // ---- Progress ----
    function showProgress(text) {
        modeSection.classList.add('hidden');
        inputSection.classList.add('hidden');
        resultsSection.classList.add('hidden');
        progressSection.classList.remove('hidden');
        progressBar.style.width = '0%';
        progressText.textContent = text;
        progressDetail.textContent = '';
    }
    function simulateProgress(target, detail) {
        progressBar.style.width = target + '%';
        if (detail) progressDetail.textContent = detail;
    }
    function hideProgress() {
        progressSection.classList.add('hidden');
        inputSection.classList.remove('hidden');
    }

    // ---- Results ----
    function showResults(data) {
        progressSection.classList.add('hidden');
        resultsSection.classList.remove('hidden');

        const mode = data.mode || 'parts';
        const s = data.summary;

        // Summary stats
        if (mode === 'assemblies') {
            $('#statFiles').textContent = s.total_submissions || 0;
            $('#statFilesLabel').textContent = 'Submissions';
        } else {
            $('#statFiles').textContent = s.total_files || 0;
            $('#statFilesLabel').textContent = 'Files Analyzed';
        }
        $('#statPairs').textContent = s.total_pairs;
        $('#statHigh').textContent = s.high_risk;
        $('#statMedium').textContent = s.medium_risk;

        // Students table
        if (mode === 'assemblies') {
            renderAssemblyStudents(data.submissions || []);
            renderAssemblyComparisons(data.comparisons || []);
        } else {
            renderPartStudents(data.files || []);
            renderPartComparisons(data.comparisons || []);
        }

        // Clusters
        const clusters = data.clusters || [];
        if (clusters.length > 0) {
            $('#clustersPanel').classList.remove('hidden');
            renderClusters(clusters);
        } else {
            $('#clustersPanel').classList.add('hidden');
        }
    }

    function renderPartStudents(files) {
        $('#studentsTitle').innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            Students`;
        const thead = $('#studentsHead');
        thead.innerHTML = '<tr><th>File</th><th>Student</th><th>Type</th><th>Features</th></tr>';
        const tbody = $('#studentsTable tbody');
        tbody.innerHTML = '';
        files.forEach(f => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${f.file_name}</td>
                <td style="color:var(--accent-secondary);font-weight:600">${f.student_name}</td>
                <td><span class="file-ext">${(f.file_type||'').replace('.','').toUpperCase()}</span></td>
                <td>${f.feature_count}</td>`;
            tbody.appendChild(tr);
        });
    }

    function renderAssemblyStudents(subs) {
        $('#studentsTitle').innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            Student Submissions`;
        const thead = $('#studentsHead');
        thead.innerHTML = '<tr><th>Student</th><th>ZIP File</th><th>Parts</th><th>Assemblies</th><th>Total Features</th></tr>';
        const tbody = $('#studentsTable tbody');
        tbody.innerHTML = '';
        subs.forEach(s => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="color:var(--accent-secondary);font-weight:600">${s.student_name}</td>
                <td>${s.zip_filename}</td>
                <td>${s.total_parts}</td>
                <td>${s.assembly_count}</td>
                <td>${s.total_features}</td>`;
            tbody.appendChild(tr);
        });
    }

    function renderPartComparisons(comparisons) {
        const thead = $('#comparisonHead');
        thead.innerHTML = '<tr><th>Student A</th><th>Student B</th><th>Score</th><th>Risk</th><th>Flags</th></tr>';
        const tbody = $('#comparisonTable tbody');
        tbody.innerHTML = '';
        comparisons.forEach(c => renderCompRow(tbody, c.file_a, c.file_b, c));
    }

    function renderAssemblyComparisons(comparisons) {
        const thead = $('#comparisonHead');
        thead.innerHTML = '<tr><th>Student A</th><th>Student B</th><th>Overall</th><th>Assembly</th><th>Parts</th><th>Risk</th><th>Flags</th></tr>';
        const tbody = $('#comparisonTable tbody');
        tbody.innerHTML = '';
        comparisons.forEach(c => {
            const tr = document.createElement('tr');
            const scoreColor = riskColor(c.risk_level);
            const flagsHtml = (c.flags||[]).map(f => `<span class="flag-tag">${f}</span>`).join('');
            tr.innerHTML = `
                <td>${c.student_a}</td>
                <td>${c.student_b}</td>
                <td class="score-cell" style="color:${scoreColor}">${c.score}%</td>
                <td class="score-cell" style="color:var(--text-secondary)">${c.assembly_similarity}%</td>
                <td class="score-cell" style="color:var(--text-secondary)">${c.part_similarity}%</td>
                <td><span class="risk-badge risk-${c.risk_level}">${c.risk_level}</span></td>
                <td>${flagsHtml || '\u2014'}</td>`;
            tbody.appendChild(tr);
        });
    }

    function renderCompRow(tbody, nameA, nameB, c) {
        const tr = document.createElement('tr');
        const scoreColor = riskColor(c.risk_level);
        const flagsHtml = (c.flags||[]).map(f => `<span class="flag-tag">${f}</span>`).join('');
        tr.innerHTML = `
            <td>${nameA}</td>
            <td>${nameB}</td>
            <td class="score-cell" style="color:${scoreColor}">${c.score}%</td>
            <td><span class="risk-badge risk-${c.risk_level}">${c.risk_level}</span></td>
            <td>${flagsHtml || '\u2014'}</td>`;
        tbody.appendChild(tr);
    }

    function renderClusters(clusters) {
        const container = $('#clustersList');
        container.innerHTML = '';
        clusters.forEach((c, idx) => {
            const color = c.max_score >= 75 ? 'var(--risk-high)' : c.max_score >= 45 ? 'var(--risk-medium)' : 'var(--risk-low)';
            const div = document.createElement('div');
            div.className = 'cluster-card';
            div.innerHTML = `
                <div class="cluster-header" style="color:${color}">
                    Cluster ${idx+1} &mdash; ${c.size} files (max: ${c.max_score}%)
                </div>
                <div class="cluster-files">
                    ${c.files.map(f => `<span class="cluster-file">${f}</span>`).join('')}
                </div>`;
            container.appendChild(div);
        });
    }

    function riskColor(level) {
        return { HIGH: 'var(--risk-high)', MEDIUM: 'var(--risk-medium)', LOW: 'var(--risk-low)', NONE: 'var(--risk-none)' }[level] || 'var(--text-secondary)';
    }

    // ---- Downloads ----
    $('#btnDownloadPdf').addEventListener('click', () => { if (currentSessionId) window.open(`/api/report/${currentSessionId}/pdf`, '_blank'); });
    $('#btnDownloadCsv').addEventListener('click', () => { if (currentSessionId) window.open(`/api/report/${currentSessionId}/csv`, '_blank'); });

    // ---- Reset ----
    $('#btnReset').addEventListener('click', () => {
        selectedFiles = [];
        currentSessionId = null;
        currentMode = null;
        renderFileList();
        btnAnalyze.disabled = true;
        driveUrl.value = '';
        resultsSection.classList.add('hidden');
        progressSection.classList.add('hidden');
        inputSection.classList.add('hidden');
        modeSection.classList.remove('hidden');
    });
})();
