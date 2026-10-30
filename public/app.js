// Olympiad Problem Forge - Client Application Logic

document.addEventListener("DOMContentLoaded", () => {
    // State
    let currentProblemData = null;
    let activeTestIndex = 0;
    let timerInterval = null;
    let timerSeconds = 0;

    // DOM Elements
    const inputApiKey = document.getElementById("input-api-key");
    const selectModel = document.getElementById("select-model");
    const btnToggleKey = document.getElementById("btn-toggle-key");
    const btnVerifyKey = document.getElementById("btn-verify-key");
    const keyStatusMsg = document.getElementById("key-status-msg");

    const diffButtons = document.querySelectorAll(".diff-btn");
    const inputTheme = document.getElementById("input-theme");
    const inputCode = document.getElementById("input-code");
    const selectIoMode = document.getElementById("select-io-mode");
    const btnGenerate = document.getElementById("btn-generate");
    const btnLoadSample = document.getElementById("btn-load-sample");

    const agentStatusBox = document.getElementById("agent-status-box");
    const agentStepsList = document.getElementById("agent-steps-list");
    const agentTimer = document.getElementById("agent-timer");

    const btnDownloadZip = document.getElementById("btn-download-zip");
    const btnDownloadZipTests = document.getElementById("btn-download-zip-tests");
    const btnPrintExam = document.getElementById("btn-print-exam");
    const btnCopyMarkdown = document.getElementById("btn-copy-markdown");

    // Modal
    const helpModal = document.getElementById("help-modal");
    const btnOpenHelp = document.getElementById("btn-open-help");
    const btnCloseHelp = document.getElementById("btn-close-help");
    const btnCloseHelp2 = document.getElementById("btn-close-help-2");

    // 1. Exclusively Server .env Key Manager
    const badgeKeyCount = document.getElementById("badge-key-count");
    const labelKeyCount = document.getElementById("label-key-count");
    const keyStatusText = document.getElementById("key-status-text");
    const btnOpenKeyPool = document.getElementById("btn-open-key-pool");
    const btnCloseKeyPool = document.getElementById("btn-close-key-pool");
    const btnCloseModalBottom = document.getElementById("btn-close-modal-bottom");
    const modalKeyPool = document.getElementById("modal-key-pool");
    const serverKeysBadge = document.getElementById("server-keys-badge");
    const btnVerifyServerKeys = document.getElementById("btn-verify-server-keys");
    const poolDiagnosticsContainer = document.getElementById("pool-diagnostics-container");
    const diagnosticsSummaryBadge = document.getElementById("diagnostics-summary-badge");
    const poolDiagnosticsList = document.getElementById("pool-diagnostics-list");

    let serverKeysCount = 0;

    async function loadServerKeysStatus() {
        try {
            const resp = await fetch("/api/keys/status");
            const res = await resp.json();
            if (res.success && res.has_server_keys) {
                serverKeysCount = res.server_keys_count;
                if (labelKeyCount) labelKeyCount.textContent = `${serverKeysCount} Keys (.env)`;
                if (serverKeysBadge) {
                    serverKeysBadge.textContent = `${serverKeysCount} Key(s) Sẵn Sàng 🟢`;
                    serverKeysBadge.className = "px-3 py-1 rounded-full text-xs font-bold bg-emerald-950 text-emerald-300 border border-emerald-700";
                }
                if (keyStatusText) {
                    keyStatusText.innerHTML = `<span class="text-emerald-400 font-semibold flex items-center gap-1.5"><i class="fa-solid fa-shield-halved"></i> Đang dùng ${serverKeysCount} Keys (.env) tự động xoay vòng</span>`;
                }

                // Render current keys list in modal
                if (res.data && res.data.keys) {
                    renderKeysList(res.data.keys);
                }
            } else {
                serverKeysCount = 0;
                if (labelKeyCount) labelKeyCount.textContent = "0 Key (.env)";
                if (serverKeysBadge) {
                    serverKeysBadge.textContent = "Chưa cấu hình .env 🔴";
                    serverKeysBadge.className = "px-3 py-1 rounded-full text-xs font-bold bg-rose-950 text-rose-300 border border-rose-700";
                }
                if (keyStatusText) {
                    keyStatusText.innerHTML = `<span class="text-rose-400 font-semibold flex items-center gap-1.5"><i class="fa-solid fa-triangle-exclamation"></i> Chưa tìm thấy key trong file .env</span>`;
                }
            }
        } catch (err) {
            console.warn("Could not fetch server keys status:", err);
        }
    }

    function renderKeysList(keysList) {
        if (!poolDiagnosticsList) return;
        poolDiagnosticsList.innerHTML = "";
        keysList.forEach((k, idx) => {
            const item = document.createElement("div");
            item.className = "flex items-center justify-between p-2.5 rounded-xl bg-slate-900 border border-slate-800 transition hover:border-slate-700";
            const isGood = k.status === "healthy" || k.valid === true;
            let statusLabel = isGood ? "Sẵn sàng 🟢" : "Lỗi 🔴";
            if (k.status === "rate_limited") {
                statusLabel = `Tạm chờ quota (${k.cooldown_remaining || 30}s) ⏳`;
            } else if (k.error) {
                statusLabel = k.error.length > 25 ? k.error.slice(0, 25) + '...' : k.error;
            }

            const badgeClass = isGood ? "bg-emerald-950 text-emerald-300 border-emerald-800" : (k.status === "rate_limited" ? "bg-amber-950 text-amber-300 border-amber-800" : "bg-rose-950 text-rose-300 border-rose-800");

            item.innerHTML = `
                <div class="flex items-center gap-2.5">
                    <span class="w-5 h-5 rounded-full bg-slate-800 text-slate-400 text-[10px] flex items-center justify-center font-bold font-mono">#${idx+1}</span>
                    <span class="text-slate-200 font-semibold">${k.masked_key}</span>
                </div>
                <div class="flex items-center gap-2">
                    <span class="text-[10px] px-2 py-0.5 rounded-md font-semibold border ${badgeClass}">
                        ${statusLabel}
                    </span>
                </div>
            `;
            poolDiagnosticsList.appendChild(item);
        });
    }

    loadServerKeysStatus();

    // Verify all keys from server
    if (btnVerifyServerKeys) {
        btnVerifyServerKeys.addEventListener("click", async () => {
            btnVerifyServerKeys.disabled = true;
            btnVerifyServerKeys.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i><span>Đang kiểm tra kết nối...</span>';
            try {
                const resp = await fetch("/api/keys/verify-pool", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ model: selectModel ? selectModel.value : "gemini-3.6-flash" })
                });
                const res = await resp.json();
                if (res.success && res.diagnostics) {
                    if (diagnosticsSummaryBadge) {
                        diagnosticsSummaryBadge.textContent = `${res.healthy_count}/${res.total_count} keys hoạt động tốt`;
                    }
                    renderKeysList(res.diagnostics);
                } else {
                    alert(res.error || "Kiểm tra thất bại.");
                }
            } catch (err) {
                alert("Lỗi kết nối khi kiểm tra server keys: " + err.message);
            } finally {
                btnVerifyServerKeys.disabled = false;
                btnVerifyServerKeys.innerHTML = '<i class="fa-solid fa-stethoscope"></i><span>Kiểm Tra Sức Khỏe Toàn Bộ Key (.env)</span>';
            }
        });
    }

    // Modal controls
    if (btnOpenKeyPool) {
        btnOpenKeyPool.addEventListener("click", () => {
            if (modalKeyPool) {
                modalKeyPool.classList.remove("hidden");
                loadServerKeysStatus();
            }
        });
    }

    if (btnCloseKeyPool) {
        btnCloseKeyPool.addEventListener("click", () => {
            if (modalKeyPool) modalKeyPool.classList.add("hidden");
        });
    }

    if (btnCloseModalBottom) {
        btnCloseModalBottom.addEventListener("click", () => {
            if (modalKeyPool) modalKeyPool.classList.add("hidden");
        });
    }

    if (modalKeyPool) {
        modalKeyPool.addEventListener("click", (e) => {
            if (e.target === modalKeyPool) modalKeyPool.classList.add("hidden");
        });
    }

    // AI Engine Selector State (Ollama Local vs Gemini Cloud)
    const isCloudHost = window.location.hostname !== "localhost" && 
                        window.location.hostname !== "127.0.0.1" && 
                        !window.location.hostname.startsWith("192.168.");

    let currentEngine = isCloudHost ? "gemini" : (localStorage.getItem("ai_engine") || "gemini");
    const btnEngineOllama = document.getElementById("btn-engine-ollama");
    const btnEngineGemini = document.getElementById("btn-engine-gemini");
    const boxGeminiKeys = document.getElementById("box-gemini-keys");
    const labelEngineStatus = document.getElementById("label-engine-status");
    const labelModelBadge = document.getElementById("label-model-badge");
    const engineDesc = document.getElementById("engine-desc");

    let cachedGeminiModels = [
        { id: "gemini-3.6-flash", name: "Google Gemini 3.6 Flash (Khuyên dùng Cloud - Nhanh & Chuẩn)" },
        { id: "gemini-2.5-flash", name: "Google Gemini 2.5 Flash" },
        { id: "gemini-2.0-flash", name: "Google Gemini 2.0 Flash" },
        { id: "gemini-1.5-flash", name: "Google Gemini 1.5 Flash" }
    ];

    let cachedOllamaModels = [
        { id: "qwen2.5:7b", name: "Qwen 2.5:7B (Khuyên dùng Offline - Rất mạnh & Chuẩn)" },
        { id: "qwen2.5-coder:7b", name: "Qwen 2.5 Coder 7B" },
        { id: "qwen3:14b", name: "Qwen 3:14B" },
        { id: "deepseek-r1:latest", name: "DeepSeek R1 (Suy luận sâu)" }
    ];

    const navBtnOllama = document.getElementById("nav-btn-ollama");
    const navBtnGemini = document.getElementById("nav-btn-gemini");
    const ollamaLiveChip = document.getElementById("ollama-live-chip");
    const geminiLiveChip = document.getElementById("gemini-live-chip");
    const engineHealthDot = document.getElementById("engine-health-dot");
    const engineHealthText = document.getElementById("engine-health-text");
    const btnRefreshEngines = document.getElementById("btn-refresh-engines");
    const btnGenerateText = document.getElementById("btn-generate-text");

    let ollamaAvailable = false;
    let geminiKeysCount = 0;

    function resetGenerateButton() {
        if (!btnGenerate) return;
        btnGenerate.disabled = false;
        btnGenerate.classList.remove("opacity-50", "cursor-not-allowed");
        const btnText = currentEngine === "ollama" ? "BẮT ĐẦU TẠO ĐỀ (OLLAMA OFFLINE)" : "BẮT ĐẦU TẠO ĐỀ (GEMINI CLOUD)";
        btnGenerate.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles"></i><span id="btn-generate-text">${btnText}</span>`;
    }

    function updateEngineUI(engine, showToast = false) {
        if (engine === "ollama" && (isCloudHost || !ollamaAvailable)) {
            if (isCloudHost) {
                if (showToast) {
                    showNotification("Ollama Offline chỉ hoạt động khi bạn chạy cục bộ trên máy tính (qua file run.bat). Trên trang web đám mây Vercel, vui lòng dùng Google Gemini Cloud!", "warning");
                }
                engine = "gemini";
            }
        }

        currentEngine = engine;
        localStorage.setItem("ai_engine", engine);

        if (engine === "ollama") {
            // Sidebar buttons
            if (btnEngineOllama) {
                btnEngineOllama.className = "py-2.5 px-3 rounded-lg text-xs font-bold transition flex flex-col items-center justify-center gap-1 bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-md";
            }
            if (btnEngineGemini) {
                btnEngineGemini.className = "py-2.5 px-3 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-200 transition flex flex-col items-center justify-center gap-1";
            }

            // Top Nav buttons
            if (navBtnOllama) {
                navBtnOllama.className = "px-3 py-1.5 rounded-lg font-bold transition flex items-center gap-1.5 bg-gradient-to-r from-purple-600/40 to-indigo-600/40 text-purple-200 border border-purple-500/50";
                const dot = navBtnOllama.querySelector("span");
                if (dot) dot.className = "w-2 h-2 rounded-full bg-purple-400 animate-pulse";
            }
            if (navBtnGemini) {
                navBtnGemini.className = "px-3 py-1.5 rounded-lg font-medium transition flex items-center gap-1.5 text-slate-400 hover:text-slate-200";
                const dot = navBtnGemini.querySelector("span");
                if (dot) dot.className = "w-2 h-2 rounded-full bg-slate-600";
            }

            if (boxGeminiKeys) boxGeminiKeys.classList.add("hidden");
            if (labelEngineStatus) labelEngineStatus.textContent = "Ollama Local";
            if (labelModelBadge) {
                labelModelBadge.textContent = "Local Offline";
                labelModelBadge.className = "text-[10px] px-2 py-0.5 rounded-full bg-purple-900/50 text-purple-300 border border-purple-700/50 font-semibold";
            }
            if (engineDesc) {
                engineDesc.innerHTML = 'Chế độ Offline 100%: Sử dụng mô hình <strong class="text-purple-300">Qwen 2.5:7B</strong> chạy trực tiếp trên máy qua Ollama (Cổng 11434). Miễn phí, không tốn API key, bảo mật nội bộ.';
            }

            if (engineHealthDot && engineHealthText) {
                if (ollamaAvailable) {
                    engineHealthDot.className = "w-2 h-2 rounded-full bg-emerald-400 animate-pulse";
                    engineHealthText.textContent = "Ollama: Đang chạy sẵn sàng (Cổng 11434)";
                } else {
                    engineHealthDot.className = "w-2 h-2 rounded-full bg-amber-400 animate-pulse";
                    engineHealthText.textContent = "Ollama: Đang kết nối...";
                }
            }

            if (btnGenerate && !btnGenerate.disabled) {
                resetGenerateButton();
            }

            if (selectModel) {
                selectModel.innerHTML = "";
                cachedOllamaModels.forEach(m => {
                    const opt = document.createElement("option");
                    opt.value = m.id;
                    opt.textContent = m.name;
                    if (m.id === "qwen2.5:7b" || m.id.includes("qwen2.5:7b") || m.default) opt.selected = true;
                    selectModel.appendChild(opt);
                });
            }

            if (showToast) {
                showNotification("Đã chuyển sang chế độ Ollama Local (Offline 100% - Qwen 2.5:7B)", "info");
            }
        } else {
            // Sidebar buttons
            if (btnEngineGemini) {
                btnEngineGemini.className = "py-2.5 px-3 rounded-lg text-xs font-bold transition flex flex-col items-center justify-center gap-1 bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-md";
            }
            if (btnEngineOllama) {
                btnEngineOllama.className = "py-2.5 px-3 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-200 transition flex flex-col items-center justify-center gap-1";
            }

            // Top Nav buttons
            if (navBtnGemini) {
                navBtnGemini.className = "px-3 py-1.5 rounded-lg font-bold transition flex items-center gap-1.5 bg-gradient-to-r from-blue-600/40 to-indigo-600/40 text-blue-200 border border-blue-500/50";
                const dot = navBtnGemini.querySelector("span");
                if (dot) dot.className = "w-2 h-2 rounded-full bg-blue-400 animate-pulse";
            }
            if (navBtnOllama) {
                navBtnOllama.className = "px-3 py-1.5 rounded-lg font-medium transition flex items-center gap-1.5 text-slate-400 hover:text-slate-200";
                const dot = navBtnOllama.querySelector("span");
                if (dot) dot.className = "w-2 h-2 rounded-full bg-slate-600";
            }

            if (boxGeminiKeys) boxGeminiKeys.classList.remove("hidden");
            if (labelEngineStatus) labelEngineStatus.textContent = "Gemini Cloud";
            if (labelModelBadge) {
                labelModelBadge.textContent = "Google Cloud";
                labelModelBadge.className = "text-[10px] px-2 py-0.5 rounded-full bg-blue-900/50 text-blue-300 border border-blue-700/50 font-semibold";
            }
            if (engineDesc) {
                engineDesc.innerHTML = 'Chế độ Google Gemini Cloud: Tự động nạp và xoay vòng 10 API Keys từ file <code class="bg-slate-950 px-1.5 py-0.5 rounded text-amber-300 font-mono">.env</code> trên máy chủ.';
            }

            if (engineHealthDot && engineHealthText) {
                if (geminiKeysCount > 0) {
                    engineHealthDot.className = "w-2 h-2 rounded-full bg-emerald-400 animate-pulse";
                    engineHealthText.textContent = `Gemini Cloud: Đã nạp ${geminiKeysCount} Keys từ .env`;
                } else {
                    engineHealthDot.className = "w-2 h-2 rounded-full bg-amber-400 animate-pulse";
                    engineHealthText.textContent = "Gemini Cloud: Đang nạp key...";
                }
            }

            if (btnGenerate && !btnGenerate.disabled) {
                resetGenerateButton();
            }

            if (selectModel) {
                selectModel.innerHTML = "";
                cachedGeminiModels.forEach(m => {
                    const opt = document.createElement("option");
                    opt.value = m.id;
                    opt.textContent = m.name;
                    if (m.id === "gemini-3.6-flash" || m.default) opt.selected = true;
                    selectModel.appendChild(opt);
                });
            }

            if (showToast) {
                showNotification("Đã chuyển sang chế độ Google Gemini Cloud (Vòng xoay 10 Key)", "info");
            }
        }
    }

    async function checkBothEnginesHealth() {
        try {
            // 1. Check Ollama
            const respOllama = await fetch("/api/ollama/status");
            const dataOllama = await respOllama.json();
            ollamaAvailable = dataOllama.available === true;
            if (ollamaLiveChip) {
                if (isCloudHost) {
                    ollamaLiveChip.textContent = `○ Chỉ chạy khi mở run.bat`;
                    ollamaLiveChip.className = "text-[9px] font-normal text-slate-400";
                } else if (ollamaAvailable) {
                    ollamaLiveChip.textContent = `● Đang chạy (${dataOllama.models.length} mô hình)`;
                    ollamaLiveChip.className = "text-[9px] font-medium text-emerald-300";
                } else {
                    ollamaLiveChip.textContent = `○ Chưa kết nối (Cổng 11434)`;
                    ollamaLiveChip.className = "text-[9px] font-normal text-amber-300";
                }
            }
        } catch (e) {
            ollamaAvailable = false;
            if (ollamaLiveChip) {
                ollamaLiveChip.textContent = isCloudHost ? `○ Chỉ chạy khi mở run.bat` : `○ Không kết nối`;
                ollamaLiveChip.className = "text-[9px] font-normal text-slate-400";
            }
        }

        try {
            // 2. Check Gemini Keys
            const respKeys = await fetch("/api/keys/status");
            const dataKeys = await respKeys.json();
            geminiKeysCount = dataKeys.server_keys_count || 0;
            if (geminiLiveChip) {
                if (geminiKeysCount > 0) {
                    geminiLiveChip.textContent = `● ${geminiKeysCount} Keys .env sẵn sàng`;
                    geminiLiveChip.className = "text-[9px] font-medium text-emerald-300";
                } else {
                    geminiLiveChip.textContent = `○ Chưa cấu hình Key`;
                    geminiLiveChip.className = "text-[9px] font-normal text-amber-300";
                }
            }
        } catch (e) {
            geminiKeysCount = 0;
        }

        // Auto-select Gemini Cloud if on cloud host or local Ollama is offline
        if (isCloudHost || (!ollamaAvailable && geminiKeysCount > 0)) {
            currentEngine = "gemini";
        }

        // Re-render status text for current engine
        updateEngineUI(currentEngine, false);
    }

    async function loadEngineModels() {
        try {
            const resp = await fetch("/api/topics");
            const data = await resp.json();
            if (data.ollama_models && data.ollama_models.length > 0) {
                cachedOllamaModels = data.ollama_models;
            }
            if (data.gemini_models && data.gemini_models.length > 0) {
                cachedGeminiModels = data.gemini_models;
            }
            updateEngineUI(currentEngine, false);
        } catch (e) {
            console.warn("Error loading models:", e);
            updateEngineUI(currentEngine, false);
        }
    }

    // Bind Event Listeners for seamless switching
    if (btnEngineOllama) {
        btnEngineOllama.addEventListener("click", () => updateEngineUI("ollama", true));
    }
    if (btnEngineGemini) {
        btnEngineGemini.addEventListener("click", () => updateEngineUI("gemini", true));
    }
    if (navBtnOllama) {
        navBtnOllama.addEventListener("click", () => updateEngineUI("ollama", true));
    }
    if (navBtnGemini) {
        navBtnGemini.addEventListener("click", () => updateEngineUI("gemini", true));
    }
    if (btnRefreshEngines) {
        btnRefreshEngines.addEventListener("click", async () => {
            const icon = btnRefreshEngines.querySelector("i");
            if (icon) icon.classList.add("fa-spin");
            await checkBothEnginesHealth();
            setTimeout(() => {
                if (icon) icon.classList.remove("fa-spin");
            }, 600);
            showNotification("Đã kiểm tra lại trạng thái kết nối cả 2 động cơ AI!", "success");
        });
    }

    loadEngineModels();
    checkBothEnginesHealth();

    // 2. Topic and Difficulty Selection Management
    const topicContainer = document.getElementById('topic-container');
    if (topicContainer) {
        if (!document.querySelector('input[value="hinh_hoc_co_ban"]')) {
            const cardBasic = document.createElement('label');
            cardBasic.className = "topic-card flex items-center justify-between p-2.5 rounded-xl border border-slate-800 bg-slate-900/50 hover:bg-slate-800/60 cursor-pointer transition";
            cardBasic.innerHTML = `
                <div class="flex items-center">
                    <input type="radio" name="topic" value="hinh_hoc_co_ban" class="text-blue-600 focus:ring-blue-500">
                    <span class="ml-3 text-sm font-medium text-slate-200 flex items-center gap-2">
                        <span class="text-base">📐</span> Hình học cơ bản (Vector, Cross Product, Đa giác)
                    </span>
                </div>
                <i class="topic-check fa-solid fa-check text-blue-400 text-xs hidden"></i>
            `;
            topicContainer.appendChild(cardBasic);
        }
        if (!document.querySelector('input[value="hinh_hoc_nang_cao"]')) {
            const cardAdv = document.createElement('label');
            cardAdv.className = "topic-card flex items-center justify-between p-2.5 rounded-xl border border-slate-800 bg-slate-900/50 hover:bg-slate-800/60 cursor-pointer transition";
            cardAdv.innerHTML = `
                <div class="flex items-center">
                    <input type="radio" name="topic" value="hinh_hoc_nang_cao" class="text-blue-600 focus:ring-blue-500">
                    <span class="ml-3 text-sm font-medium text-slate-200 flex items-center gap-2">
                        <span class="text-base">🛰️</span> Hình học nâng cao (Bao lồi, Sweep-line, Calipers)
                    </span>
                </div>
                <i class="topic-check fa-solid fa-check text-blue-400 text-xs hidden"></i>
            `;
            topicContainer.appendChild(cardAdv);
        }
    }

    // Refresh Button Fallback Injection if missing in cached HTML
    if (!document.getElementById("btn-refresh-problem")) {
        const btnWord = document.getElementById("btn-download-word");
        if (btnWord && btnWord.parentNode) {
            const btnRef = document.createElement("button");
            btnRef.id = "btn-refresh-problem";
            btnRef.title = "Làm mới đề bài / Tạo lại đề mới theo cấu hình hiện tại";
            btnRef.className = "px-3.5 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold flex items-center gap-2 shadow-lg shadow-amber-900/20 transition";
            btnRef.innerHTML = `<i class="fa-solid fa-arrows-rotate text-sm"></i><span>Làm Mới Đề</span>`;
            btnWord.parentNode.insertBefore(btnRef, btnWord);
        }
    }

    let topicCards = document.querySelectorAll('.topic-card');
    let topicRadios = document.querySelectorAll('input[name="topic"]');
    const labelSelectedTopic = document.getElementById('label-selected-topic');
    const labelSelectedDiff = document.getElementById('label-selected-diff');

    const topicNames = {
        "xu_ly_so": "Xử lý số & Số học",
        "xu_ly_chuoi": "Xử lý chuỗi (String)",
        "qhd_co_ban": "Quy hoạch động cơ bản",
        "qhd_nang_cao": "Quy hoạch động nâng cao",
        "do_thi_co_ban": "Đồ thị cơ bản",
        "do_thi_nang_cao": "Đồ thị nâng cao",
        "hinh_hoc_co_ban": "Hình học tính toán cơ bản",
        "hinh_hoc_nang_cao": "Hình học tính toán nâng cao"
    };

    const diffNames = {
        "hsg_truong": "HSG Trường / Huyện",
        "hsg_tinh": "HSG Tỉnh / TP",
        "chon_doi_tuyen": "Chọn Đội Tuyển Tỉnh",
        "hsg_quoc_gia": "HSG Quốc Gia (VOI)"
    };

    function updateTopicSelectionUI() {
        const checkedRadio = document.querySelector('input[name="topic"]:checked');
        if (!checkedRadio) return;
        const selectedVal = checkedRadio.value;
        topicCards.forEach(card => {
            const radio = card.querySelector('input[name="topic"]');
            const checkIcon = card.querySelector('.topic-check');
            if (radio && radio.value === selectedVal) {
                card.classList.add('active', 'border-blue-500', 'bg-blue-950/40', 'ring-1', 'ring-blue-500');
                card.classList.remove('border-slate-800', 'bg-slate-900/50');
                if (checkIcon) checkIcon.classList.remove('hidden');
            } else {
                card.classList.remove('active', 'border-blue-500', 'bg-blue-950/40', 'ring-1', 'ring-blue-500');
                card.classList.add('border-slate-800', 'bg-slate-900/50');
                if (checkIcon) checkIcon.classList.add('hidden');
            }
        });
        if (labelSelectedTopic) {
            labelSelectedTopic.textContent = `Đã chọn: ${topicNames[selectedVal] || selectedVal}`;
        }
    }

    topicCards.forEach(card => {
        card.addEventListener('click', () => {
            const radio = card.querySelector('input[name="topic"]');
            if (radio) {
                radio.checked = true;
                updateTopicSelectionUI();
            }
        });
    });
    topicRadios.forEach(r => r.addEventListener('change', updateTopicSelectionUI));
    updateTopicSelectionUI();

    let selectedDifficulty = "hsg_tinh";
    function updateDiffSelectionUI(val) {
        selectedDifficulty = val;
        diffButtons.forEach(b => {
            if (b.dataset.diff === val) {
                b.classList.add("active", "border-blue-500", "bg-blue-950/40", "ring-1", "ring-blue-500");
                b.classList.remove("border-slate-800", "bg-slate-900/60");
            } else {
                b.classList.remove("active", "border-blue-500", "bg-blue-950/40", "ring-1", "ring-blue-500");
                b.classList.add("border-slate-800", "bg-slate-900/60");
            }
        });
        if (labelSelectedDiff) {
            labelSelectedDiff.textContent = `Đã chọn: ${diffNames[val] || val}`;
        }
    }

    diffButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            updateDiffSelectionUI(btn.dataset.diff);
        });
    });
    updateDiffSelectionUI("hsg_tinh");

    // 3. Tab Switching
    const navTabs = document.querySelectorAll(".nav-tab");
    navTabs.forEach(tab => {
        tab.addEventListener("click", () => {
            navTabs.forEach(t => {
                t.classList.remove("active");
                t.classList.add("text-slate-400");
            });
            tab.classList.add("active");
            tab.classList.remove("text-slate-400");

            const targetId = tab.dataset.tab;
            document.querySelectorAll(".tab-content").forEach(c => c.classList.add("hidden"));
            const activeContent = document.getElementById(targetId);
            if (activeContent) {
                activeContent.classList.remove("hidden");
            }
        });
    });

    // 4. Modal Handlers
    btnOpenHelp.addEventListener("click", () => helpModal.classList.remove("hidden"));
    btnCloseHelp.addEventListener("click", () => helpModal.classList.add("hidden"));
    btnCloseHelp2.addEventListener("click", () => helpModal.classList.add("hidden"));
    helpModal.addEventListener("click", (e) => {
        if (e.target === helpModal) helpModal.classList.add("hidden");
    });

    // 5. Safe String & Markdown Helpers
    function safeStr(val, fallback = "") {
        if (val === null || val === undefined) return fallback;
        if (typeof val === "string") return val;
        if (typeof val === "number" || typeof val === "boolean") return String(val);
        if (Array.isArray(val)) {
            return val.map(x => safeStr(x)).join("\n");
        }
        if (typeof val === "object") {
            try {
                return Object.entries(val)
                    .map(([k, v]) => `- **${k}**: ${typeof v === 'object' ? JSON.stringify(v) : v}`)
                    .join("\n");
            } catch (e) {
                return JSON.stringify(val);
            }
        }
        return String(val);
    }

    function safeMarkdown(val, fallback = "") {
        const text = safeStr(val, fallback);
        try {
            return (window.marked && window.marked.parse) ? window.marked.parse(text) : text;
        } catch (e) {
            console.warn("safeMarkdown error:", e);
            return `<p>${text}</p>`;
        }
    }

    function safeParseInline(val, fallback = "") {
        const text = safeStr(val, fallback);
        try {
            return (window.marked && window.marked.parseInline) ? window.marked.parseInline(text) : text;
        } catch (e) {
            console.warn("safeParseInline error:", e);
            return text;
        }
    }

    function formatExplanationHTML(text) {
        if (!text || !text.trim()) return '';
        let cleanText = safeStr(text).trim();

        // 1. Remove AI meta-talk / self-correction in parentheses or lines
        cleanText = cleanText.replace(/\((?:Lỗi|Nhầm lẫn|Sai sót|Sửa lại|Đã sửa|Tính lại|Self-correction|Note|Chú ý sửa|Xin lỗi)[^)]*\)/gi, '');
        
        // If there's a recalculation section at the end (e.g. "Tính lại: ..."), take the last section
        const calcAgainMatches = [...cleanText.matchAll(/(?:Tính lại|Sửa lại|Tính toán lại|Kết quả đúng là)\s*:\s*/gi)];
        if (calcAgainMatches.length > 0) {
            const lastMatch = calcAgainMatches[calcAgainMatches.length - 1];
            const tail = cleanText.substring(lastMatch.index + lastMatch[0].length).trim();
            if (tail.length > 15) {
                cleanText = tail;
            }
        }

        // 2. Break down into lines / steps
        let rawLines = [];
        if (cleanText.includes('\n')) {
            rawLines = cleanText.split('\n');
        } else if (cleanText.includes(' - ')) {
            rawLines = cleanText.split(/\s+-\s+/);
        } else if (cleanText.includes('; ')) {
            rawLines = cleanText.split(/;\s+/);
        } else {
            rawLines = [cleanText];
        }

        const lines = [];
        const metaLineRegex = /^\s*(?:[\(\[\-•*]\s*)?(?:lỗi\s*(?:tính toán|trong|khi)?|à,?\s*tôi|tôi\s*(?:đã\s*nhầm|xin\s*lỗi|cần\s*tính\s*lại)|self[- ]correction|chú ý sửa)/i;
        
        for (let l of rawLines) {
            l = l.trim();
            if (!l || metaLineRegex.test(l)) continue;
            lines.push(l);
        }

        if (lines.length === 0) return '';

        // 3. Build HTML with clean line-by-line structure
        let html = '<div class="space-y-1.5 text-xs text-slate-300">';
        lines.forEach((line, idx) => {
            let stripped = line.replace(/^[-*•–]\s*/, '').trim();
            const isNumbered = /^(\d+[\.)])\s+(.*)$/.exec(stripped);
            const isSummary = /^(?:Tổng|Tổng cộng|Do đó|Vậy|Kết luận|Kết quả)\s*[:=]/i.test(stripped);

            if (isNumbered) {
                html += `<div class="flex items-start gap-2 py-0.5 pl-1">
                    <span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-blue-900/60 text-blue-300 text-[10px] font-bold font-mono shrink-0">${isNumbered[1].replace(/[\.)]/, '')}</span>
                    <span class="flex-1 leading-relaxed">${safeParseInline(isNumbered[2])}</span>
                </div>`;
            } else if (isSummary) {
                html += `<div class="mt-2 pt-2 border-t border-slate-800 font-semibold text-emerald-400 flex items-center gap-2">
                    <i class="fa-solid fa-circle-check text-emerald-400 text-xs shrink-0"></i>
                    <span class="flex-1">${safeParseInline(stripped)}</span>
                </div>`;
            } else if (lines.length > 1 && idx > 0) {
                // Step bullet
                html += `<div class="flex items-start gap-2 py-0.5 pl-2 border-l border-blue-500/30">
                    <span class="text-blue-400 font-bold shrink-0">•</span>
                    <span class="flex-1 leading-relaxed">${safeParseInline(stripped)}</span>
                </div>`;
            } else {
                // First introductory line or single line
                html += `<div class="font-medium text-slate-200 pb-0.5 leading-relaxed">${safeParseInline(stripped)}</div>`;
            }
        });
        html += '</div>';
        return html;
    }

    // 5.1 Math & KaTeX Helper
    function renderMath(element) {
        if (!element) return;
        if (element.innerHTML) {
            // Escape underscores inside \text{...} to prevent KaTeX math-mode syntax errors
            element.innerHTML = element.innerHTML.replace(/\\text\{([^{}]+)\}/g, (m, p1) => {
                return '\\text{' + p1.replace(/_/g, '\\_') + '}';
            });
        }
        if (window.renderMathInElement) {
            window.renderMathInElement(element, {
                delimiters: [
                    { left: "$$", right: "$$", display: true },
                    { left: "$", right: "$", display: false },
                    { left: "\\(", right: "\\)", display: false },
                    { left: "\\[", right: "\\]", display: true }
                ],
                throwOnError: false,
                errorColor: '#94a3b8'
            });
        }
    }

    // 6. Populate Problem Data to UI
    function displayProblem(data) {
        currentProblemData = data;
        const problem = data.problem || {};
        const solution = data.solution || {};
        const tests = data.tests || [];
        const topic = data.topic || {};
        const difficulty = data.difficulty || {};

        const code = safeStr(problem.problem_code, "PROBLEM").toUpperCase();
        const name = safeStr(problem.problem_name, "Bài toán Tin học");

        // Top Badges & Title
        document.getElementById("display-problem-code").textContent = code;
        document.getElementById("display-topic-badge").textContent = safeStr(topic.name, "Chủ đề");
        document.getElementById("display-diff-badge").textContent = safeStr(difficulty.name, "Cấp độ");
        document.getElementById("display-time-badge").textContent = `${safeStr(problem.time_limit, "1.0s")} / ${safeStr(problem.memory_limit, "256MB")}`;
        document.getElementById("display-problem-title").textContent = name;

        // Exam Paper Header
        document.getElementById("paper-code").textContent = code;
        document.getElementById("paper-input-file").textContent = safeStr(problem.input_file, `${code}.INP`);
        document.getElementById("paper-output-file").textContent = safeStr(problem.output_file, `${code}.OUT`);
        document.getElementById("paper-time-limit").textContent = safeStr(problem.time_limit, "1.0 giây");
        document.getElementById("paper-memory-limit").textContent = safeStr(problem.memory_limit, "256 MB");

        // Statement Markdown
        const stmtBox = document.getElementById("paper-statement-text");
        stmtBox.innerHTML = safeMarkdown(problem.story_and_statement);
        renderMath(stmtBox);

        // Input & Output Format
        const inFormatBox = document.getElementById("paper-input-format");
        inFormatBox.innerHTML = safeMarkdown(problem.input_format);
        renderMath(inFormatBox);

        const outFormatBox = document.getElementById("paper-output-format");
        outFormatBox.innerHTML = safeMarkdown(problem.output_format);
        renderMath(outFormatBox);

        // Subtasks Table
        const subtasksTbody = document.getElementById("paper-subtasks-table");
        subtasksTbody.innerHTML = "";
        (problem.subtasks || []).forEach(st => {
            const tr = document.createElement("tr");
            tr.className = "hover:bg-slate-900/40";
            tr.innerHTML = `
                <td class="p-3 font-bold text-blue-400 font-mono">Subtask ${st.subtask_num || 1}</td>
                <td class="p-3"><span class="px-2 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800 font-semibold">${st.points_percent || 0}% điểm</span></td>
                <td class="p-3 text-slate-200">${safeParseInline(st.constraints)}</td>
            `;
            subtasksTbody.appendChild(tr);
        });
        renderMath(subtasksTbody);

        // Samples
        const samplesContainer = document.getElementById("paper-samples-container");
        samplesContainer.innerHTML = "";
        (problem.sample_tests || []).forEach(s => {
            const sampleDiv = document.createElement("div");
            sampleDiv.className = "bg-slate-900/60 p-4 rounded-xl border border-slate-800 space-y-3";
            sampleDiv.innerHTML = `
                <div class="font-bold text-xs text-slate-300 flex items-center gap-2">
                    <span class="w-5 h-5 rounded-full bg-blue-600/30 text-blue-400 flex items-center justify-center text-[10px] font-bold">${s.sample_num || 1}</span>
                    <span>Ví dụ ${s.sample_num || 1}</span>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-3 font-mono text-xs">
                    <div>
                        <div class="text-[11px] text-amber-400 font-semibold mb-1">Dữ liệu vào (${problem.input_file || 'INPUT.INP'}):</div>
                        <pre class="bg-slate-950 p-3 rounded-lg border border-slate-800 text-amber-200 overflow-x-auto whitespace-pre-wrap">${safeStr(s.input).trim()}</pre>
                    </div>
                    <div>
                        <div class="text-[11px] text-emerald-400 font-semibold mb-1">Kết quả (${problem.output_file || 'OUTPUT.OUT'}):</div>
                        <pre class="bg-slate-950 p-3 rounded-lg border border-slate-800 text-emerald-300 overflow-x-auto whitespace-pre-wrap">${safeStr(s.output).trim()}</pre>
                    </div>
                </div>
                ${s.explanation ? `
                <div class="text-xs text-slate-300 bg-slate-900/60 p-3.5 rounded-lg border-l-4 border-l-blue-500 border border-slate-800/80 mt-2">
                    <div class="font-semibold text-blue-400 mb-1.5 flex items-center gap-1.5">
                        <i class="fas fa-lightbulb text-amber-400 text-xs"></i>
                        <span>Giải thích ví dụ ${s.sample_num || 1}:</span>
                    </div>
                    <div class="text-slate-300 leading-relaxed explanation-content">
                        ${formatExplanationHTML(s.explanation)}
                    </div>
                </div>` : ''}
            `;
            samplesContainer.appendChild(sampleDiv);
        });
        renderMath(samplesContainer);

        // Editorial & Solutions
        const bruteBox = document.getElementById("editorial-brute-force");
        bruteBox.innerHTML = safeMarkdown(solution.brute_force_approach, "Đang cập nhật...");
        renderMath(bruteBox);

        const optBox = document.getElementById("editorial-optimal");
        optBox.innerHTML = safeMarkdown(solution.optimal_approach, "Đang cập nhật...");
        renderMath(optBox);

        // Codes
        const codeCpp = document.getElementById("code-cpp");
        codeCpp.textContent = safeStr(solution.cpp_solution, "// Chưa có mã nguồn C++");
        if (window.Prism) Prism.highlightElement(codeCpp);

        const codePy = document.getElementById("code-python");
        codePy.textContent = safeStr(solution.python_solution, "# Chưa có mã nguồn Python");
        if (window.Prism) Prism.highlightElement(codePy);

        // Generator code
        const codeGen = document.getElementById("code-generator");
        codeGen.textContent = safeStr(data.generator_code, "# Generator script");
        if (window.Prism) Prism.highlightElement(codeGen);

        // 10 Test Cases Browser
        renderTestSelector(tests, problem);

        // Reasoning Trace
        renderReasoningLogs(data.agent_logs || []);
    }

    // 7. Render 10 Test Cases Browser
    function renderTestSelector(tests, problem) {
        const selectorBar = document.getElementById("test-selector-bar");
        selectorBar.innerHTML = "";

        tests.forEach((t, idx) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = `p-2 rounded-lg text-center border font-mono text-xs transition ${
                idx === activeTestIndex 
                ? 'bg-blue-600 text-white border-blue-400 shadow-md font-bold' 
                : 'bg-slate-900 border-slate-800 text-slate-300 hover:bg-slate-800'
            }`;
            btn.innerHTML = `
                <div class="text-[10px] text-slate-400">T${t.test_num}</div>
                <div class="font-bold">#${t.test_num}</div>
            `;
            btn.addEventListener("click", () => {
                activeTestIndex = idx;
                renderTestSelector(tests, problem);
                displayActiveTest(tests[idx], problem);
            });
            selectorBar.appendChild(btn);
        });

        if (tests.length > 0) {
            if (activeTestIndex >= tests.length) activeTestIndex = 0;
            displayActiveTest(tests[activeTestIndex], problem);
        }
    }

    function displayActiveTest(test, problem) {
        if (!test) return;
        const code = problem.problem_code || "PROBLEM";
        document.getElementById("active-test-name").textContent = test.name || `Test${test.test_num}`;
        
        const subBadge = document.getElementById("active-test-subtask");
        subBadge.textContent = `Subtask ${test.subtask || 1}`;
        subBadge.className = `text-xs px-2.5 py-0.5 rounded-full font-semibold ${
            test.subtask === 1 ? 'badge-subtask-1' : (test.subtask === 2 ? 'badge-subtask-2' : 'badge-subtask-3')
        }`;

        document.getElementById("active-test-desc").textContent = test.description || "Mô tả dữ liệu";
        document.getElementById("themis-folder-name").textContent = `tests/Test${String(test.test_num).padStart(2, '0')}/${code}.INP`;

        document.getElementById("active-test-input").value = safeStr(test.input).trim();
        document.getElementById("active-test-output").value = safeStr(test.output).trim();
    }

    // 8. Render AI Agent Reasoning Logs
    function renderReasoningLogs(logs) {
        const timeline = document.getElementById("reasoning-timeline");
        timeline.innerHTML = "";

        logs.forEach(log => {
            const item = document.createElement("div");
            item.className = "flex items-start gap-3 bg-slate-900/60 p-4 rounded-xl border border-slate-800";
            item.innerHTML = `
                <div class="w-7 h-7 rounded-full bg-blue-900/60 border border-blue-500/50 flex items-center justify-center text-blue-400 text-xs font-bold shrink-0">
                    ${log.stage}
                </div>
                <div class="flex-1">
                    <div class="flex items-center justify-between">
                        <h4 class="font-bold text-xs text-white">${log.title}</h4>
                        <span class="text-[10px] text-emerald-400 flex items-center gap-1 font-semibold">
                            <i class="fa-solid fa-check"></i> Hoàn thành
                        </span>
                    </div>
                    <p class="text-xs text-slate-400 mt-1 leading-relaxed">${log.message}</p>
                </div>
            `;
            timeline.appendChild(item);
        });
    }

    // 9. Load Sample Problem on Startup
    async function loadSampleProblem() {
        try {
            const resp = await fetch("/api/sample-data");
            const res = await resp.json();
            if (res.success && res.data) {
                displayProblem(res.data);
            }
        } catch (err) {
            console.error("Không thể tải bài mẫu:", err);
        }
    }
    loadSampleProblem();
    btnLoadSample.addEventListener("click", loadSampleProblem);

    // 10. Generate Problem via AI Agent
    btnGenerate.addEventListener("click", async () => {
        if (btnGenerate.disabled) return;

        if (currentEngine === "ollama") {
            if (isCloudHost) {
                alert("Mô hình Ollama Offline chỉ chạy được trên máy tính cá nhân (khi bạn mở file 'run.bat').\n\nTrên trang web đám mây Vercel, hệ thống tự động chuyển sang chế độ 'Online (Gemini)' để tạo đề siêu tốc bằng 20 API Key!");
                updateEngineUI("gemini", true);
                return;
            }
            if (!ollamaAvailable) {
                alert("Không thể kết nối đến Ollama trên cổng 11434. Vui lòng mở ứng dụng Ollama hoặc chuyển sang chế độ 'Online (Gemini)' để tạo đề!");
                return;
            }
        }

        if (currentEngine === "gemini" && serverKeysCount === 0) {
            alert("Chưa tìm thấy Google Gemini API Key trong tệp .env trên máy chủ. Vui lòng kiểm tra lại tệp .env!");
            if (btnOpenKeyPool) btnOpenKeyPool.click();
            return;
        }

        const selectedTopicInput = document.querySelector('input[name="topic"]:checked');
        const topic = selectedTopicInput ? selectedTopicInput.value : "xu_ly_so";
        const difficulty = selectedDifficulty;
        const customTheme = inputTheme.value.trim();
        const problemCode = inputCode.value.trim();
        const ioMode = selectIoMode.value;
        const model = selectModel.value;

        // Immediately reflect user's chosen topic and difficulty in the top header
        document.getElementById("display-topic-badge").textContent = topicNames[topic] || topic;
        document.getElementById("display-diff-badge").textContent = diffNames[difficulty] || difficulty;
        document.getElementById("display-problem-title").textContent = `[AI Agent đang suy luận tạo đề: ${topicNames[topic]} (${diffNames[difficulty]})...]`;

        // UI Loading State
        btnGenerate.disabled = true;
        btnGenerate.classList.add("opacity-50", "cursor-not-allowed");
        btnGenerate.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i><span>AGENT ĐANG SUY LUẬN...</span>';

        agentStatusBox.classList.remove("hidden");
        agentStepsList.innerHTML = "";
        timerSeconds = 0;
        agentTimer.textContent = "0s";
        clearInterval(timerInterval);
        timerInterval = setInterval(() => {
            timerSeconds++;
            agentTimer.textContent = `${timerSeconds}s`;
        }, 1000);

        // Progressive steps simulation for UI feedback
        const steps = [
            "Đang nghiên cứu chủ đề & thiết lập bối cảnh đề thi...",
            "Đang phân hóa Subtasks và thiết kế giới hạn thời gian / bộ nhớ...",
            "Đang chứng minh thuật toán tối ưu và viết mã nguồn C++20...",
            "Đang tính toán 10 bộ Test Cases từ dễ đến cực đại...",
            "Đang hoàn thiện Contest Package chuẩn Themis..."
        ];

        let stepIndex = 0;
        const addStepUI = (text) => {
            const div = document.createElement("div");
            div.className = "flex items-center gap-2 text-slate-300 animate-pulse";
            div.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin text-blue-400 text-[10px]"></i><span>${text}</span>`;
            agentStepsList.appendChild(div);
        };
        addStepUI(steps[0]);

        if (currentEngine === "ollama") {
            const noticeDiv = document.createElement("div");
            noticeDiv.className = "p-2.5 rounded-xl bg-purple-950/70 border border-purple-600/50 text-purple-200 text-xs flex items-center justify-between gap-2 mb-2 shadow-sm";
            noticeDiv.innerHTML = `
                <div class="flex items-center gap-2 text-[11px]">
                    <i class="fa-solid fa-laptop-code text-purple-400"></i>
                    <span>Đang chạy Ollama Offline trên CPU (~2-3 phút)...</span>
                </div>
                <button id="btn-switch-to-gemini-fast" type="button" class="px-2.5 py-1 rounded-md bg-blue-600 hover:bg-blue-500 text-white font-bold text-[10px] flex items-center gap-1 transition shadow">
                    <i class="fa-brands fa-google text-blue-200"></i>
                    <span>Dùng Gemini (10s)</span>
                </button>
            `;
            agentStepsList.appendChild(noticeDiv);

            const btnFastSwitch = document.getElementById("btn-switch-to-gemini-fast");
            if (btnFastSwitch) {
                btnFastSwitch.addEventListener("click", () => {
                    updateEngineUI("gemini", true);
                    btnGenerate.click();
                });
            }
        }

        const stepTimer = setInterval(() => {
            stepIndex++;
            if (stepIndex < steps.length) {
                addStepUI(steps[stepIndex]);
            }
        }, 8000);

        try {
            const resp = await fetch("/api/generate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    ai_engine: currentEngine,
                    model: model,
                    topic: topic,
                    difficulty: difficulty,
                    custom_theme: customTheme,
                    problem_code: problemCode,
                    io_mode: ioMode
                })
            });

            clearInterval(stepTimer);
            clearInterval(timerInterval);

            let res;
            const contentType = resp.headers.get("content-type") || "";
            if (contentType.includes("application/json")) {
                res = await resp.json();
            } else {
                const rawText = await resp.text();
                if (resp.status === 504 || rawText.includes("FUNCTION_INVOCATION_TIMEOUT") || rawText.includes("An error occurred")) {
                    throw new Error("Máy chủ Vercel Serverless bị Timeout (>60s). Vui lòng thử lại với mô hình Google Gemini 3.6 Flash (siêu tốc ~10s) hoặc chạy file 'run.bat' trên máy tính để tạo đề không bị giới hạn thời gian!");
                }
                throw new Error(`Máy chủ đám mây trả về mã ${resp.status}: ${rawText.slice(0, 150)}`);
            }

            if (!res.success) {
                throw new Error(res.error || "Quá trình sinh đề thất bại.");
            }

            if (res.fallback_used) {
                showNotification("💡 " + (res.fallback_message || "Đã tự động chuyển sang Gemini Cloud và tạo đề thành công!"), "info");
                updateEngineUI("gemini", false);
            }

            if (res.rotation_events && res.rotation_events.length > 0) {
                res.rotation_events.forEach(ev => {
                    const rotDiv = document.createElement("div");
                    rotDiv.className = "p-2 rounded-lg bg-amber-950/80 border border-amber-600 text-amber-200 text-xs font-semibold flex items-center gap-2";
                    rotDiv.innerHTML = `<i class="fa-solid fa-arrows-rotate text-amber-400"></i><span>${ev}</span>`;
                    agentStepsList.appendChild(rotDiv);
                });
            }

            displayProblem(res.data);
            agentStepsList.innerHTML += `<div class="text-emerald-400 font-bold flex items-center gap-2 mt-2"><i class="fa-solid fa-circle-check"></i><span>Hoàn thành xuất sắc toàn bộ đề thi và 10 test cases!</span></div>`;
            setTimeout(() => {
                agentStatusBox.classList.add("hidden");
            }, 4000);

        } catch (err) {
            clearInterval(stepTimer);
            clearInterval(timerInterval);

            const isOllamaIssue = err.message && (err.message.includes("Ollama") || err.message.includes("240s") || err.message.includes("450s") || err.message.includes("Timeout"));

            if (isOllamaIssue) {
                agentStepsList.innerHTML = `
                    <div class="p-3.5 rounded-xl bg-amber-950/80 border border-amber-600/70 text-amber-200 text-xs space-y-2.5 shadow-lg">
                        <div class="font-bold flex items-center gap-2 text-amber-300">
                            <i class="fa-solid fa-triangle-exclamation"></i>
                            <span>Mô hình Ollama nội bộ xử lý quá lâu hoặc bận CPU</span>
                        </div>
                        <p class="text-slate-300 text-[11px] leading-relaxed">
                            ${err.message}
                        </p>
                        <p class="text-blue-200 text-[11px] font-semibold">
                            💡 Gợi ý: Bạn có thể chuyển sang <strong>Google Gemini Cloud (10s)</strong> với cụm 10 key .env có sẵn để tạo đề tức thì.
                        </p>
                        <button id="btn-fallback-gemini-now" type="button" class="w-full py-2 px-3 rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-lg transition">
                            <i class="fa-brands fa-google text-blue-300"></i>
                            <span>CHUYỂN SANG GEMINI CLOUD VÀ TẠO ĐỀ NGAY (10 GIÂY)</span>
                        </button>
                    </div>`;
                const btnFallback = document.getElementById("btn-fallback-gemini-now");
                if (btnFallback) {
                    btnFallback.addEventListener("click", () => {
                        updateEngineUI("gemini", true);
                        btnGenerate.click();
                    });
                }
            } else {
                alert(`Lỗi: ${err.message}`);
                agentStepsList.innerHTML = `<div class="text-rose-400 font-bold flex items-center gap-2"><i class="fa-solid fa-triangle-exclamation"></i><span>${err.message}</span></div>`;
            }
        } finally {
            resetGenerateButton();
            updateEngineUI(currentEngine, false);
        }
    });

    // 10.1 Refresh / Regenerate Problem Buttons
    const btnRefreshProblem = document.getElementById("btn-refresh-problem");
    if (btnRefreshProblem) {
        btnRefreshProblem.addEventListener("click", () => {
            btnGenerate.click();
        });
    }

    const btnRefreshInline = document.getElementById("btn-refresh-inline");
    if (btnRefreshInline) {
        btnRefreshInline.addEventListener("click", () => {
            btnGenerate.click();
        });
    }

    // 11. ZIP Download Logic
    async function triggerDownloadZip() {
        if (!currentProblemData) {
            alert("Chưa có dữ liệu bài toán để tải về.");
            return;
        }

        const originalText = btnDownloadZip.innerHTML;
        btnDownloadZip.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang nén ZIP...';

        try {
            const resp = await fetch("/api/download-zip", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(currentProblemData)
            });

            if (!resp.ok) throw new Error("Lỗi khi tải gói tệp ZIP");

            const blob = await resp.blob();
            const code = currentProblemData.problem.problem_code || "PROBLEM";
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = downloadUrl;
            a.download = `${code}_THEMIS_TESTS.zip`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(downloadUrl);
        } catch (err) {
            alert(`Tải file ZIP thất bại: ${err.message}`);
        } finally {
            btnDownloadZip.innerHTML = originalText;
        }
    }

    btnDownloadZip.addEventListener("click", triggerDownloadZip);
    btnDownloadZipTests.addEventListener("click", triggerDownloadZip);

    // 12. Word (.docx) Download Logic
    const btnDownloadWord = document.getElementById("btn-download-word");
    async function triggerDownloadWord() {
        if (!currentProblemData) {
            alert("Chưa có dữ liệu bài toán để xuất Word.");
            return;
        }

        const originalText = btnDownloadWord.innerHTML;
        btnDownloadWord.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang tạo Word...';

        try {
            const resp = await fetch("/api/download-word", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(currentProblemData)
            });

            if (!resp.ok) throw new Error("Lỗi khi xuất tệp Word (.docx)");

            const blob = await resp.blob();
            const code = currentProblemData.problem.problem_code || "PROBLEM";
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = downloadUrl;
            a.download = `${code}_DE_THI_HSG.docx`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(downloadUrl);
        } catch (err) {
            alert(`Xuất file Word thất bại: ${err.message}`);
        } finally {
            btnDownloadWord.innerHTML = originalText;
        }
    }

    if (btnDownloadWord) {
        btnDownloadWord.addEventListener("click", triggerDownloadWord);
    }

    // 12. Copy Buttons
    function copyText(text, btn) {
        navigator.clipboard.writeText(text).then(() => {
            const original = btn.innerHTML;
            btn.innerHTML = '<i class="fa-solid fa-check text-emerald-400"></i> Đã chép!';
            setTimeout(() => btn.innerHTML = original, 2000);
        });
    }

    document.getElementById("btn-copy-cpp").addEventListener("click", (e) => {
        const code = document.getElementById("code-cpp").textContent;
        copyText(code, e.currentTarget);
    });

    document.getElementById("btn-copy-python").addEventListener("click", (e) => {
        const code = document.getElementById("code-python").textContent;
        copyText(code, e.currentTarget);
    });

    document.getElementById("btn-copy-generator").addEventListener("click", (e) => {
        const code = document.getElementById("code-generator").textContent;
        copyText(code, e.currentTarget);
    });

    document.getElementById("btn-copy-test-in").addEventListener("click", (e) => {
        const val = document.getElementById("active-test-input").value;
        copyText(val, e.currentTarget);
    });

    document.getElementById("btn-copy-test-out").addEventListener("click", (e) => {
        const val = document.getElementById("active-test-output").value;
        copyText(val, e.currentTarget);
    });

    btnCopyMarkdown.addEventListener("click", (e) => {
        if (!currentProblemData) return;
        const p = currentProblemData.problem;
        const md = `# ${p.problem_name} (${p.problem_code})\n\n${p.story_and_statement}\n\n## Input:\n${p.input_format}\n\n## Output:\n${p.output_format}`;
        copyText(md, e.currentTarget);
    });

    btnPrintExam.addEventListener("click", () => {
        window.print();
    });
});
