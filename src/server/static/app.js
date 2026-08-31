let currentTaskId = null;
let currentTaskData = null;
let autoSyncInterval = null;

document.addEventListener("DOMContentLoaded", () => {
    setupEventListeners();
    loadTaskList();
    startAutoSync();
});

function setupEventListeners() {
    document.getElementById("task-form").addEventListener("submit", handleCreateTask);
    document.getElementById("btn-step-unit").addEventListener("click", handleStepUnit);
    document.getElementById("btn-run-all").addEventListener("click", handleRunAll);
    document.getElementById("btn-refresh-dashboard").addEventListener("click", () => {
        loadTaskList();
        if (currentTaskId) loadTaskDetails(currentTaskId);
    });
    document.getElementById("btn-clear-logs").addEventListener("click", () => {
        document.getElementById("terminal-logs").replaceChildren();
    });
    document.getElementById("btn-close-artifact-modal").addEventListener("click", () => {
        document.getElementById("artifact-modal").style.display = "none";
    });
}

function appendLog(message, type = "info") {
    const entry = document.createElement("div");
    entry.className = `log-entry log-${type}`;
    entry.textContent = `${new Date().toLocaleTimeString()} · ${message}`;
    const feed = document.getElementById("terminal-logs");
    feed.appendChild(entry);
    feed.scrollTop = feed.scrollHeight;
}

function startAutoSync() {
    if (autoSyncInterval) clearInterval(autoSyncInterval);
    autoSyncInterval = setInterval(() => {
        loadTaskList(true);
        if (currentTaskId) loadTaskDetails(currentTaskId, true);
    }, 2500);
}

async function handleCreateTask(event) {
    event.preventDefault();
    const button = document.getElementById("btn-initialize-task");
    const prompt = document.getElementById("input-prompt").value.trim();
    if (!prompt) return;

    button.disabled = true;
    button.textContent = "Төлөвлөгөө гаргаж байна…";
    const filesText = document.getElementById("input-files").value.trim();
    try {
        const response = await fetch("/api/tasks", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                prompt,
                repository: document.getElementById("input-repo").value.trim() || ".",
                // This is an internal guardrail for the engine. It is not
                // presented as a price or a payment in the local UI.
                budget: 5,
                execution_mode: document.getElementById("select-mode").value,
                provider: document.getElementById("select-provider").value,
                files: filesText ? filesText.split(",").map(item => item.trim()).filter(Boolean) : [],
            }),
        });
        if (!response.ok) throw new Error((await response.json()).detail || "Task эхлүүлж чадсангүй");
        const data = await response.json();
        currentTaskId = data.task_id;
        updateTaskUI(data);
        appendLog("Шинэ task-ийн төлөвлөгөө бэлэн боллоо.", "success");
        loadTaskList(true);
    } catch (error) {
        appendLog(error.message, "error");
    } finally {
        button.disabled = false;
        button.textContent = "Ажил эхлүүлэх";
    }
}

async function handleStepUnit() {
    if (!currentTaskId) return;
    await runTaskAction("step", "Дараагийн алхам ажиллаж байна…");
}

async function handleRunAll() {
    if (!currentTaskId) return;
    await runTaskAction("run", "Task дуусгах ажиллаж байна…");
}

async function runTaskAction(action, message) {
    const buttons = [document.getElementById("btn-step-unit"), document.getElementById("btn-run-all")];
    buttons.forEach(button => { button.disabled = true; });
    appendLog(message, "info");
    try {
        const response = await fetch(`/api/tasks/${encodeURIComponent(currentTaskId)}/${action}`, { method: "POST" });
        if (!response.ok) throw new Error((await response.json()).detail || "Task ажиллуулж чадсангүй");
        const data = await response.json();
        updateTaskUI(data);
        appendLog(`Ажил ${readableStatus(String(data.status || "").toLowerCase())} төлөвт байна.`, "success");
        loadTaskList(true);
    } catch (error) {
        appendLog(error.message, "error");
    } finally {
        const status = String(currentTaskData?.status || "").toLowerCase();
        const finished = ["completed", "failed", "blocked"].includes(status);
        buttons.forEach(button => { button.disabled = finished; });
    }
}

async function loadTaskDetails(taskId, silent = false) {
    try {
        const response = await fetch(`/api/tasks/${encodeURIComponent(taskId)}`);
        if (!response.ok) return;
        const data = await response.json();
        currentTaskId = taskId;
        updateTaskUI(data);
        if (!silent) appendLog("Task-ийн мэдээллийг шинэчиллээ.");
    } catch (error) {
        if (!silent) appendLog(error.message, "error");
    }
}

async function loadTaskList(silent = false) {
    try {
        const response = await fetch("/api/tasks");
        if (!response.ok) return;
        const { tasks = [] } = await response.json();
        renderTaskList(tasks);
        if (!currentTaskId && tasks.length) loadTaskDetails(tasks[0].task_id, true);
    } catch (error) {
        if (!silent) appendLog("Task жагсаалтыг авч чадсангүй.", "error");
    }
}

function updateTaskUI(data) {
    currentTaskData = data;
    const status = String(data.status || "initialized").toLowerCase();
    const taskPrompt = data.manifest?.task_context?.user_prompt || "Одоогийн ажил";
    document.getElementById("current-task-display").textContent = taskPrompt;
    const badge = document.getElementById("task-status-badge");
    badge.textContent = readableStatus(status);
    badge.className = `status-badge status-${status}`;
    const infoBadge = document.getElementById("task-info-status");
    infoBadge.textContent = readableStatus(status);
    infoBadge.className = `status-badge status-${status}`;
    const finished = ["completed", "failed", "blocked"].includes(status);
    document.getElementById("btn-step-unit").disabled = finished;
    document.getElementById("btn-run-all").disabled = finished;
    document.getElementById("task-control-help").textContent = finished
        ? "Энэ ажил дууссан. Үр дүн болон файлуудыг баруун талаас нээгээрэй."
        : "Ажлын явц автоматаар шинэчлэгдэж байна. Хүсвэл дараагийн алхам эсвэл дуусгахыг сонгоно.";
    renderDAG(data.work_units || []);
    renderSummary(data);
    renderArtifacts(data.outputs || [], data.task_id);
}

function renderDAG(units) {
    const placeholder = document.getElementById("dag-placeholder");
    const list = document.getElementById("dag-nodes-list");
    list.replaceChildren();
    if (!units.length) {
        placeholder.style.display = "grid";
        list.style.display = "none";
        return;
    }
    placeholder.style.display = "none";
    list.style.display = "grid";
    units.forEach(unit => {
        const node = document.createElement("article");
        const status = String(unit.status || "pending").toLowerCase();
        node.className = `unit-node unit-${status}`;
        const main = document.createElement("div");
        main.className = "unit-main-info";
        const priority = document.createElement("span");
        priority.className = "priority-badge";
        priority.textContent = unit.priority || "P1";
        const details = document.createElement("div");
        details.className = "unit-details";
        const title = document.createElement("h4");
        title.textContent = unit.instruction || unit.description || unit.id;
        const meta = document.createElement("div");
        meta.className = "unit-meta-row";
        meta.textContent = readableUnitType(unit.type);
        details.append(title, meta);
        main.append(priority, details);
        const state = document.createElement("span");
        state.className = "unit-status-indicator";
        state.textContent = status.toUpperCase();
        node.append(main, state);
        list.appendChild(node);
    });
}

function renderSummary(data) {
    const total = (currentTaskData?.work_units || []).length;
    const completed = (currentTaskData?.work_units || []).filter(unit => unit.status === "completed").length;
    document.getElementById("val-units-done").textContent = `${completed} / ${total}`;
    const source = data.source || data.manifest?.orchestration?.source || "local_web";
    document.getElementById("val-source").textContent = readableSource(source);
}

function readableUnitType(type) {
    return ({ parse: "Шалгаж байна", code: "Код дээр ажиллаж байна", analyze: "Шинжилж байна", test: "Баталгаажуулж байна", output: "Үр дүн бэлтгэж байна" })[type] || "Ажиллаж байна";
}

function readableStatus(status) {
    return ({ initialized: "БЭЛЭН", in_progress: "АЖИЛЛАЖ БАЙНА", running: "АЖИЛЛАЖ БАЙНА", completed: "ДУУССАН", failed: "АЛДААТАЙ", blocked: "ЗОГССОН", idle: "ХҮЛЭЭЖ БАЙНА" })[status] || "АЖИЛЛАЖ БАЙНА";
}

function readableSource(source) {
    return ({ cli: "Terminal", terminal: "Terminal", mcp: "Гадаад AI", local_web: "Энэ хуудас", agentcore_skill: "AgentCore skill" })[source] || "Локал";
}

function renderArtifacts(outputs, taskId) {
    const list = document.getElementById("artifacts-list");
    list.replaceChildren();
    document.getElementById("artifacts-count").textContent = String(outputs.length);
    if (!outputs.length) {
        const empty = document.createElement("p");
        empty.className = "empty-copy";
        empty.textContent = "Ажил дуусахад үүссэн файл, тайлан энд гарна.";
        list.appendChild(empty);
        return;
    }
    outputs.forEach(path => {
        const item = document.createElement("button");
        item.type = "button";
        item.className = "artifact-item";
        item.textContent = path.split(/[\\/]/).pop() || path;
        item.addEventListener("click", () => openArtifactModal(taskId, path));
        list.appendChild(item);
    });
}

async function openArtifactModal(taskId, path) {
    try {
        const response = await fetch(`/api/tasks/${encodeURIComponent(taskId)}/artifacts/${encodeURIComponent(path)}`);
        if (!response.ok) throw new Error("Файлыг нээж чадсангүй");
        const data = await response.json();
        document.getElementById("modal-artifact-title").textContent = data.filename || "Файл";
        document.getElementById("modal-artifact-content").textContent = data.content || "Файл хоосон байна.";
        document.getElementById("artifact-modal").style.display = "grid";
    } catch (error) {
        appendLog(error.message, "error");
    }
}

function renderTaskList(tasks) {
    const list = document.getElementById("task-list-container");
    list.replaceChildren();
    if (!tasks.length) {
        const empty = document.createElement("p");
        empty.className = "empty-copy";
        empty.textContent = "Одоогоор хадгалсан ажил алга.";
        list.appendChild(empty);
        return;
    }
    tasks.forEach(task => {
        const item = document.createElement("button");
        item.type = "button";
        item.className = "task-item-card";
        const title = document.createElement("span");
        title.className = "task-item-top";
        title.textContent = readableStatus(String(task.status || "idle").toLowerCase());
        const prompt = document.createElement("span");
        prompt.className = "task-item-prompt";
        prompt.textContent = task.prompt || "Task";
        const source = document.createElement("span");
        source.className = "task-item-source";
        source.textContent = `Эх сурвалж: ${readableSource(task.source)}`;
        item.append(title, prompt, source);
        item.addEventListener("click", () => loadTaskDetails(task.task_id));
        list.appendChild(item);
    });
}
