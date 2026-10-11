"use strict";
let csrf = "", active = null, busy = false;
const element = id => document.getElementById(id);
async function api(path, payload) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  let response;
  try { response = await fetch(path, payload === undefined ? {signal: controller.signal} : {
    signal: controller.signal,
    method: "POST", headers: {"Content-Type": "application/json", "X-Lab-CSRF": csrf},
    body: JSON.stringify(payload)
  }); } finally { clearTimeout(timeout); }
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Request unavailable.");
  return result;
}
function lock(value) {
  busy = value; element("send").disabled = value; element("identity").disabled = value;
  element("cancel").hidden = !value;
}
function message(kind, text, refs = []) {
  const block = document.createElement("article"); block.className = "message " + kind;
  const label = document.createElement("p"); label.className = "eyebrow";
  label.textContent = kind === "question" ? "YOU" : "COORDINATOR";
  const content = document.createElement("pre"); content.textContent = text;
  block.append(label, content);
  if (refs.length) {
    const references = document.createElement("p"); references.className = "fine";
    references.textContent = "Sources: " + refs.map(ref => ref.title).join(" · "); block.append(references);
  }
  element("messages").append(block);
}
function events(lines) {
  element("events").replaceChildren();
  for (const line of lines) {
    const item = document.createElement("li");
    // Server-controlled decision data is still rendered as text, never HTML.
    item.textContent = line; element("events").append(item);
  }
}
async function poll(taskId, display = true) {
  const deadline = Date.now() + 60000;
  while (Date.now() < deadline) {
    const task = await api("/api/task?id=" + encodeURIComponent(taskId));
    if (active === taskId) { element("status").textContent = task.state.replace("TASK_STATE_", ""); events(task.events); }
    if (["TASK_STATE_COMPLETED", "TASK_STATE_FAILED", "TASK_STATE_CANCELED", "TASK_STATE_REJECTED"].includes(task.state)) {
      if (display) message("answer", task.result ? task.result.answer : "Task " + task.state.replace("TASK_STATE_", "").toLowerCase() + ".", task.result ? task.result.references : []);
      return;
    }
    await new Promise(resolve => setTimeout(resolve, 350));
  }
  throw new Error("Task polling stopped at its time limit. Refresh to inspect the owned task; do not assume cancellation.");
}
element("question-form").addEventListener("submit", async event => {
  event.preventDefault(); if (busy || !csrf) return;
  const text = element("question").value.trim(); if (!text) return;
  element("error").textContent = ""; message("question", text); lock(true);
  try {
    const task = await api("/api/ask", {text}); active = task.task_id;
    element("question").value = ""; await poll(active);
  } catch (error) { element("error").textContent = error.message; }
  finally { active = null; lock(false); }
});
element("cancel").addEventListener("click", async () => {
  if (!active) return;
  try { await api("/api/cancel", {task_id: active}); }
  catch (error) { element("error").textContent = error.message; }
});
element("identity").addEventListener("change", async () => {
  try {
    const session = await api("/api/identity", {owner: element("identity").value}); csrf = session.csrf;
    element("messages").replaceChildren(); events([]); element("status").textContent = "Ready for a question";
  } catch (error) { element("error").textContent = error.message; }
});
document.querySelectorAll("[data-question]").forEach(button => button.addEventListener("click", () => {
  element("question").value = button.dataset.question; element("question").focus();
}));
(async () => {
  try {
    const session = await api("/api/session"); csrf = session.csrf; element("identity").value = session.owner;
    for (const taskId of session.tasks.filter(id => !id.startsWith("pending-"))) {
      lock(true); active = taskId; await poll(taskId);
    }
  } catch (error) { element("error").textContent = error.message; }
  finally { active = null; lock(false); }
})();
