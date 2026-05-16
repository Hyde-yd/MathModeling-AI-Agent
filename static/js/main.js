/**
 * 数学建模竞赛总调度智能体 - 前端交互脚本
 * 支持赛题文件上传 + 附件数据上传 + SSE进度监听 + 结果展示与下载
 */

(function () {
    "use strict";

    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    // === DOM元素 ===
    const problemFileUpload = $("#problemFileUpload");
    const problemFileList = $("#problemFileList");
    const problemUploadZone = $("#problemUploadZone");

    const dataFileUpload = $("#dataFileUpload");
    const dataFileList = $("#dataFileList");
    const dataUploadZone = $("#dataUploadZone");

    const submitBtn = $("#submitBtn");

    const progressSection = $("#progressSection");
    const progressBar = $("#progressBar");
    const progressMessage = $("#progressMessage");
    const stageAnalysis = $("#stageAnalysis");
    const stageCode = $("#stageCode");
    const stagePackaging = $("#stagePackaging");

    const resultSection = $("#resultSection");
    const emptyState = $("#emptyState");

    const analysisContent = $("#analysisContent");
    const codeTabs = $("#codeTabs");
    const codeFilename = $("#codeFilename");
    const codeContent = $("#codeContent");
    const btnCopy = $("#btnCopy");
    const btnDownload = $("#btnDownload");
    const btnNewTask = $("#btnNewTask");
    const summaryContent = $("#summaryContent");

    const configStatus = $("#configStatus");

    // === 状态 ===
    let problemFile = null;
    let dataFiles = [];
    let currentTaskId = null;
    let codeFilesData = {};
    let currentCodeFile = null;

    // === 初始化 ===
    function init() {
        checkConfig();
        bindEvents();
        updateSubmitButton();
    }

    function checkConfig() {
        fetch("/api/check-config")
            .then((r) => r.json())
            .then((data) => {
                if (data.configured) {
                    configStatus.innerHTML = `
                        <span class="status-dot ok"></span>
                        <span class="status-text">DeepSeek API 已配置 (${data.model})</span>`;
                } else {
                    configStatus.innerHTML = `
                        <span class="status-dot warn"></span>
                        <span class="status-text">⚠ 请先配置 DEEPSEEK_API_KEY 环境变量</span>`;
                }
            })
            .catch(() => {
                configStatus.innerHTML = `
                    <span class="status-dot error"></span>
                    <span class="status-text">无法连接后端服务</span>`;
            });
    }

    function bindEvents() {
        // 赛题文件上传
        problemFileUpload.addEventListener("change", handleProblemFile);
        bindDragDrop(problemUploadZone, problemFileUpload, "problem");

        // 数据附件上传
        dataFileUpload.addEventListener("change", handleDataFiles);
        bindDragDrop(dataUploadZone, dataFileUpload, "data");

        submitBtn.addEventListener("click", submitTask);

        $$(".tab-btn").forEach((btn) => {
            btn.addEventListener("click", () => switchTab(btn.dataset.tab));
        });

        btnCopy.addEventListener("click", copyCode);
        btnDownload.addEventListener("click", downloadResult);
        btnNewTask.addEventListener("click", resetTask);
    }

    function bindDragDrop(zone, fileInput, type) {
        zone.addEventListener("dragover", (e) => {
            e.preventDefault();
            zone.querySelector(".upload-placeholder").style.borderColor =
                "var(--accent)";
        });
        zone.addEventListener("dragleave", () => {
            zone.querySelector(".upload-placeholder").style.borderColor =
                "var(--border)";
        });
        zone.addEventListener("drop", (e) => {
            e.preventDefault();
            zone.querySelector(".upload-placeholder").style.borderColor =
                "var(--border)";
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                const dt = new DataTransfer();
                if (type === "problem") {
                    dt.items.add(files[0]);
                } else {
                    // 累积模式：拖入的文件追加到已有列表
                    const existingNames = new Set(dataFiles.map(f => f.name));
                    dataFiles.forEach(f => dt.items.add(f));
                    for (const f of Array.from(files)) {
                        if (!existingNames.has(f.name)) {
                            dt.items.add(f);
                        }
                    }
                }
                fileInput.files = dt.files;
                fileInput.dispatchEvent(new Event("change"));
            }
        });
    }

    function updateSubmitButton() {
        submitBtn.disabled = !problemFile;
    }

    // === 赛题文件处理 ===
    function handleProblemFile(e) {
        const files = e.target.files;
        if (files.length > 0) {
            problemFile = files[0];
        } else {
            problemFile = null;
        }
        renderProblemFile();
        updateSubmitButton();
    }

    function renderProblemFile() {
        if (!problemFile) {
            problemFileList.innerHTML = "";
            return;
        }
        problemFileList.innerHTML = `
            <div class="file-item">
                <span class="file-icon">📄</span>
                <span class="file-name">${escapeHtml(problemFile.name)}</span>
                <span class="file-size">${formatFileSize(problemFile.size)}</span>
                <span class="file-remove" title="移除">✕</span>
            </div>`;
        problemFileList.querySelector(".file-remove").addEventListener("click", () => {
            problemFile = null;
            problemFileUpload.value = "";
            renderProblemFile();
            updateSubmitButton();
        });
    }

    // === 数据文件处理 ===
    function handleDataFiles(e) {
        const newFiles = Array.from(e.target.files);
        // 累积模式：新选的文件追加到已有列表，不替换
        const existingNames = new Set(dataFiles.map(f => f.name));
        for (const f of newFiles) {
            if (!existingNames.has(f.name)) {
                dataFiles.push(f);
            }
        }
        renderDataFiles();
        // 重置 dataTransfer 保留累积的所有文件
        const dt = new DataTransfer();
        dataFiles.forEach(f => dt.items.add(f));
        dataFileUpload.files = dt.files;
    }

    function renderDataFiles() {
        if (dataFiles.length === 0) {
            dataFileList.innerHTML = "";
            return;
        }
        dataFileList.innerHTML = dataFiles
            .map(
                (file, i) => `
            <div class="file-item">
                <span class="file-icon">📊</span>
                <span class="file-name">${escapeHtml(file.name)}</span>
                <span class="file-size">${formatFileSize(file.size)}</span>
                <span class="file-remove" data-index="${i}" title="移除">✕</span>
            </div>`
            )
            .join("");
        dataFileList.querySelectorAll(".file-remove").forEach((btn) => {
            btn.addEventListener("click", (e) => {
                e.stopPropagation();
                const idx = parseInt(btn.dataset.index);
                dataFiles.splice(idx, 1);
                renderDataFiles();
                const dt = new DataTransfer();
                dataFiles.forEach((f) => dt.items.add(f));
                dataFileUpload.files = dt.files;
            });
        });
    }

    // === 提交任务 ===
    function submitTask() {
        if (!problemFile) return;

        emptyState.style.display = "none";
        resultSection.style.display = "none";
        progressSection.style.display = "block";
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="btn-icon">⏳</span> 处理中...';

        resetProgress();

        const formData = new FormData();
        formData.append("problem_file", problemFile);
        dataFiles.forEach((file) => formData.append("data_files", file));

        fetch("/api/upload", {
            method: "POST",
            body: formData,
        })
            .then((r) => r.json())
            .then((data) => {
                if (data.error) {
                    showError(data.error);
                    return;
                }
                currentTaskId = data.task_id;
                listenProgress(currentTaskId);
            })
            .catch((err) => {
                showError("上传失败: " + err.message);
            });
    }

    function resetProgress() {
        progressBar.style.width = "0%";
        stageAnalysis.textContent = "等待中";
        stageAnalysis.className = "stage-status";
        stageCode.textContent = "等待中";
        stageCode.className = "stage-status";
        stagePackaging.textContent = "等待中";
        stagePackaging.className = "stage-status";
        progressMessage.textContent = "正在启动智能体...";
    }

    // === SSE进度监听 ===
    function listenProgress(taskId) {
        const evtSource = new EventSource(`/api/progress/${taskId}`);
        let finalResult = null;
        let pollTimer = null;

        // 兜底轮询：SSE断线后定时查结果
        function startResultPolling() {
            if (pollTimer) return;
            let attempts = 0;
            pollTimer = setInterval(() => {
                attempts++;
                fetch(`/api/result/${taskId}`)
                    .then(r => r.json())
                    .then(data => {
                        if (data.analysis_doc || (data.code_files && Object.keys(data.code_files).length > 0)) {
                            clearInterval(pollTimer);
                            pollTimer = null;
                            displayResult(data);
                            updateDownloadLink(data);
                            restoreSubmitButton();
                        } else if (attempts > 30) {
                            clearInterval(pollTimer);
                            pollTimer = null;
                            showError("处理超时，请重试");
                        }
                    })
                    .catch(() => {
                        if (attempts > 30) {
                            clearInterval(pollTimer);
                            pollTimer = null;
                            restoreSubmitButton();
                        }
                    });
            }, 3000);
        }

        evtSource.onmessage = function (event) {
            try {
                const data = JSON.parse(event.data);

                switch (data.stage) {
                    case "analysis":
                        progressBar.style.width = "10%";
                        stageAnalysis.textContent = "分析中...";
                        stageAnalysis.className = "stage-status active";
                        progressMessage.textContent = data.message;
                        break;

                    case "analysis_done":
                        progressBar.style.width = "40%";
                        stageAnalysis.textContent = "✅ 完成";
                        stageAnalysis.className = "stage-status done";
                        progressMessage.textContent = data.message;
                        break;

                    case "code_gen":
                        progressBar.style.width = "50%";
                        stageCode.textContent = "生成中...";
                        stageCode.className = "stage-status active";
                        progressMessage.textContent = data.message;
                        break;

                    case "code_done":
                        progressBar.style.width = "80%";
                        stageCode.textContent = "✅ 完成";
                        stageCode.className = "stage-status done";
                        progressMessage.textContent = data.message;
                        break;

                    case "packaging":
                        progressBar.style.width = "90%";
                        stagePackaging.textContent = "打包中...";
                        stagePackaging.className = "stage-status active";
                        progressMessage.textContent = data.message;
                        break;

                    case "done":
                        progressBar.style.width = "100%";
                        stagePackaging.textContent = "✅ 完成";
                        stagePackaging.className = "stage-status done";
                        progressMessage.textContent = data.message;
                        break;

                    case "complete":
                        finalResult = data.result;
                        break;

                    case "error":
                        progressMessage.textContent = "❌ " + data.message;
                        evtSource.close();
                        restoreSubmitButton();
                        if (pollTimer) clearInterval(pollTimer);
                        return;

                    case "stream_end":
                        evtSource.close();
                        if (finalResult) {
                            if (pollTimer) clearInterval(pollTimer);
                            restoreSubmitButton();
                            displayResult(finalResult);
                        } else {
                            // SSE正常结束但没拿到结果，启动轮询
                            progressMessage.textContent = "正在获取结果...";
                            startResultPolling();
                        }
                        return;
                }
            } catch (e) {
                console.error("SSE解析错误:", e);
            }
        };

        evtSource.onerror = function () {
            evtSource.close();
            // SSE 异常断开，启动轮询兜底
            if (!finalResult) {
                progressMessage.textContent = "进度连接断开，正在查询结果...";
                startResultPolling();
            } else {
                restoreSubmitButton();
                displayResult(finalResult);
            }
        };
    }

    // === 展示结果 ===
    function displayResult(result) {
        progressSection.style.display = "none";
        resultSection.style.display = "block";
        emptyState.style.display = "none";

        if (result.analysis_doc) {
            analysisContent.innerHTML = renderMarkdown(result.analysis_doc);
        }

        codeFilesData = result.code_files || {};
        renderCodeTabs(codeFilesData);

        const fileNames = Object.keys(codeFilesData);
        summaryContent.innerHTML = `
            <div style="font-size:13px;line-height:2;">
                <p><strong>📝 分析文档：</strong> problem_analysis.md</p>
                <p><strong>📄 原始赛题：</strong> original_problem.txt</p>
                <p><strong>💻 求解代码：</strong></p>
                <ul style="padding-left:20px;">
                    ${fileNames.map((n) => `<li><code>${escapeHtml(n)}</code></li>`).join("")}
                </ul>
            </div>`;

        switchTab("analysis");
        updateDownloadLink(result);
    }

    function updateDownloadLink(result) {
        btnDownload.onclick = () => {
            if (currentTaskId) {
                window.location.href = `/api/download/${currentTaskId}`;
            }
        };
    }

    function renderCodeTabs(codeFiles) {
        const names = Object.keys(codeFiles);
        if (names.length === 0) {
            codeTabs.innerHTML =
                '<span style="font-size:12px;color:var(--text-tertiary)">无代码文件</span>';
            return;
        }

        codeTabs.innerHTML = names
            .map(
                (name, i) =>
                    `<button class="code-tab ${i === 0 ? "active" : ""}" data-file="${escapeHtml(name)}">${escapeHtml(name)}</button>`
            )
            .join("");

        codeTabs.querySelectorAll(".code-tab").forEach((btn) => {
            btn.addEventListener("click", () => {
                codeTabs
                    .querySelectorAll(".code-tab")
                    .forEach((b) => b.classList.remove("active"));
                btn.classList.add("active");
                selectCodeFile(btn.dataset.file);
            });
        });

        if (names.length > 0) {
            selectCodeFile(names[0]);
        }
    }

    function selectCodeFile(filename) {
        currentCodeFile = filename;
        codeFilename.textContent = filename;
        codeContent.textContent = codeFilesData[filename] || "";
    }

    function switchTab(tabName) {
        $$(".tab-btn").forEach((b) => b.classList.remove("active"));
        $$(".tab-content").forEach((c) => c.classList.remove("active"));

        const btn = document.querySelector(`.tab-btn[data-tab="${tabName}"]`);
        if (btn) btn.classList.add("active");

        const content = document.getElementById(
            `tab${tabName.charAt(0).toUpperCase() + tabName.slice(1)}`
        );
        if (content) content.classList.add("active");
    }

    function copyCode() {
        if (!currentCodeFile || !codeFilesData[currentCodeFile]) return;

        navigator.clipboard
            .writeText(codeFilesData[currentCodeFile])
            .then(() => {
                btnCopy.textContent = "✅ 已复制";
                setTimeout(() => {
                    btnCopy.textContent = "📋 复制";
                }, 2000);
            })
            .catch(() => {
                const ta = document.createElement("textarea");
                ta.value = codeFilesData[currentCodeFile];
                document.body.appendChild(ta);
                ta.select();
                document.execCommand("copy");
                document.body.removeChild(ta);
                btnCopy.textContent = "✅ 已复制";
                setTimeout(() => {
                    btnCopy.textContent = "📋 复制";
                }, 2000);
            });
    }

    function downloadResult() {
        if (currentTaskId) {
            window.location.href = `/api/download/${currentTaskId}`;
        }
    }

    function resetTask() {
        currentTaskId = null;
        codeFilesData = {};
        currentCodeFile = null;
        problemFile = null;
        dataFiles = [];
        progressSection.style.display = "none";
        resultSection.style.display = "none";
        emptyState.style.display = "flex";
        problemFileUpload.value = "";
        problemFileList.innerHTML = "";
        dataFileUpload.value = "";
        dataFileList.innerHTML = "";
        updateSubmitButton();
    }

    // === 辅助 ===
    function restoreSubmitButton() {
        submitBtn.disabled = !problemFile;
        submitBtn.innerHTML = '<span class="btn-icon">🚀</span> 启动智能体分析';
    }

    function showError(msg) {
        progressSection.style.display = "block";
        progressMessage.textContent = "❌ " + msg;
        restoreSubmitButton();
    }

    function escapeHtml(str) {
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    function formatFileSize(bytes) {
        if (bytes < 1024) return bytes + " B";
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
        return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    }

    function renderMarkdown(text) {
        let html = text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");

        html = html.replace(/^#### (.+)$/gm, "<h4>$1</h4>");
        html = html.replace(/^### (.+)$/gm, "<h3>$1</h3>");
        html = html.replace(/^## (.+)$/gm, "<h2>$1</h2>");
        html = html.replace(/^# (.+)$/gm, "<h1>$1</h1>");

        html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
        html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");

        html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

        html = html.replace(/```[\s\S]*?```/g, (match) => {
            const code = match.replace(/```\w*\n/, "").replace(/```$/, "");
            return `<pre><code>${code}</code></pre>`;
        });

        html = html.replace(/^- (.+)$/gm, "<li>$1</li>");
        html = html.replace(/(<li>.*<\/li>\n?)+/g, "<ul>$&</ul>");

        html = html.replace(/^\d+\. (.+)$/gm, "<li>$1</li>");

        html = html.replace(/\n\n/g, "</p><p>");
        html = "<p>" + html + "</p>";
        html = html.replace(/<p>\s*<\/p>/g, "");
        html = html.replace(/<p><h/g, "<h");
        html = html.replace(/<\/h([1-4])><\/p>/g, "</h$1>");
        html = html.replace(/<p><ul>/g, "<ul>");
        html = html.replace(/<\/ul><\/p>/g, "</ul>");
        html = html.replace(/<p><pre>/g, "<pre>");
        html = html.replace(/<\/pre><\/p>/g, "</pre>");

        html = html.replace(
            /\$\$([\s\S]*?)\$\$/g,
            "<div style='text-align:center;padding:8px 0;font-family:serif;font-style:italic;'>$1</div>"
        );

        return html;
    }

    // === 训练知识库管理 ===
    const trainingToggle = $("#trainingToggle");
    const trainingBody = $("#trainingBody");
    const trainingStats = $("#trainingStats");
    const trainingFileList = $("#trainingFileList");
    const trainingFileInput = $("#trainingFileInput");
    const trainingUploadBtn = $("#trainingUploadBtn");
    const trainingUploadHint = $("#trainingUploadHint");
    let currentTrainingCat = "frameworks";

    trainingToggle.addEventListener("click", () => {
        const isOpen = trainingBody.style.display !== "none";
        trainingBody.style.display = isOpen ? "none" : "block";
        trainingToggle.querySelector(".training-toggle-icon").className =
            "training-toggle-icon" + (isOpen ? "" : " open");
        if (!isOpen) {
            refreshTraining();
        }
    });

    $$(".training-cat-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            $$(".training-cat-btn").forEach((b) => b.classList.remove("active"));
            btn.classList.add("active");
            currentTrainingCat = btn.dataset.cat;
            refreshTraining();
            trainingUploadHint.textContent = (currentTrainingCat === "codes") 
                ? "支持 .py 文件" : "支持 .md .txt .pdf 文件";
            trainingFileInput.accept = (currentTrainingCat === "codes")
                ? ".py" : ".txt,.md,.pdf";
        });
    });

    trainingUploadBtn.addEventListener("click", () => trainingFileInput.click());

    trainingFileInput.addEventListener("change", () => {
        const file = trainingFileInput.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append("category", currentTrainingCat);
        formData.append("file", file);

        trainingUploadHint.textContent = "上传中...";
        fetch("/api/training/upload", { method: "POST", body: formData })
            .then((r) => r.json())
            .then((data) => {
                if (data.success) {
                    trainingUploadHint.textContent = "✅ 上传成功";
                    refreshTraining();
                } else {
                    trainingUploadHint.textContent = "❌ " + (data.error || "失败");
                }
            })
            .catch(() => {
                trainingUploadHint.textContent = "❌ 上传失败";
            });

        trainingFileInput.value = "";
        setTimeout(() => { trainingUploadHint.textContent = ""; }, 3000);
    });

    function refreshTraining() {
        fetch("/api/training/stats")
            .then((r) => r.json())
            .then((data) => {
                const total = (data.frameworks || 0) + (data.papers || 0) + (data.codes || 0);
                trainingStats.textContent = total > 0
                    ? `📐${data.frameworks || 0} 📖${data.papers || 0} 💻${data.codes || 0}`
                    : "空";
            });

        fetch("/api/training/list")
            .then((r) => r.json())
            .then((data) => {
                const files = data[currentTrainingCat] || [];
                if (files.length === 0) {
                    trainingFileList.innerHTML =
                        `<div class="training-empty">暂无数据，点击 "+ 上传" 添加</div>`;
                    return;
                }
                trainingFileList.innerHTML = files
                    .map(
                        (f) => `
                    <div class="training-file-item">
                        <span>📄</span>
                        <span class="file-name" title="${escapeHtml(f.name)}">${escapeHtml(f.name)}</span>
                        <span class="file-size">${formatFileSize(f.size)}</span>
                        <span class="file-delete" data-cat="${currentTrainingCat}" data-file="${escapeHtml(f.name)}">✕</span>
                    </div>`
                    )
                    .join("");

                trainingFileList.querySelectorAll(".file-delete").forEach((btn) => {
                    btn.addEventListener("click", (e) => {
                        e.stopPropagation();
                        const cat = btn.dataset.cat;
                        const fname = btn.dataset.file;
                        fetch("/api/training/delete", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ category: cat, filename: fname }),
                        })
                            .then((r) => r.json())
                            .then(() => refreshTraining());
                    });
                });
            });
    }

    init();
})();
