"use strict";
const element = id => document.getElementById(id);
const terminalStates = ["TASK_STATE_COMPLETED", "TASK_STATE_CANCELED", "TASK_STATE_FAILED", "TASK_STATE_REJECTED"];
const specialists = {
  runbook: {name: "Operations", skill: "operations-runbook", source: "Service runbook", fixture: "runbook"},
  security: {name: "Security", skill: "secure-agent-design", source: "Secure delegation", fixture: "secure-delegation"},
  release: {name: "Release", skill: "release-readiness", source: "Release readiness checklist", fixture: "release-readiness"}
};
// Raw HTML and images stay inert; only ordinary web/mail links are navigable.
const markdown = markdownit({html: false, linkify: false, typographer: false}).disable("image");
markdown.validateLink = href => {
  try { return ["http:", "https:", "mailto:"].includes(new URL(href, location.href).protocol); }
  catch { return false; }
};
function renderMarkdown(target, text) {
  target.innerHTML = markdown.render(text);
}
let modelMode = false, pollTimeout = 60000;
let csrf = "", owner = "alice", active = null, busy = false, switching = false;
let recording = null, frames = [], cursor = 0, replaying = false, timer = null;
async function api(path, payload) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  let response;
  try {
    response = await fetch(path, payload === undefined ? {signal: controller.signal} : {
      signal: controller.signal, method: "POST",
      headers: {"Content-Type": "application/json", "X-Lab-CSRF": csrf}, body: JSON.stringify(payload)
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Request unavailable. Refresh to recover your task.");
    return result;
  } finally { clearTimeout(timeout); }
}
function lock(value) {
  busy = value;
  element("send").disabled = value || switching || !csrf;
  element("identity").disabled = value || switching;
  element("cancel").hidden = !value || !active;
  if (!value && recording && !replaying) element("replay-note").textContent = "Replay the captured steps without running the agents again.";
  controls();
}
// A presentation over existing evidence, not a second task lifecycle or simulated execution.
function buildFrames(task) {
  const result = [], peers = {}, receipts = {};
  const add = (stage, actor, title, detail, eventCount, peer = null, delivered = false) => {
    result.push({stage, actor, title, detail, eventCount, peer, delivered,
      peers: {...peers}, receipts: {...receipts}});
  };
  add(0, "client", "Client asked the coordinator", task.question, 0);
  task.events.forEach((line, index) => {
    const type = line.split(" ")[0];
    const peer = /(?:^| )agent=(runbook|security|release)(?: |$)/.exec(line)?.[1];
    const info = specialists[peer];
    const count = index + 1;
    if (type === "directory.search") {
      add(1, "coordinator", "Coordinator is finding suitable agents", "Search the approved capability directory for topics in this question. Results are filtered by the caller’s permissions.", count);
    } else if (type === "discovery.approved" && info) {
      peers[peer] = "Card checked";
      add(1, "coordinator", "Coordinator checked the " + info.name + " Agent Card", "Verified " + info.skill + ", the supported protocol and content modes, and the approved endpoint.", count, peer);
    } else if (type === "selection.selected" && info) {
      peers[peer] = "Selected";
      add(2, "coordinator", "Coordinator selected " + info.name, "The capability matches the topic, the card is compatible, and this identity is permitted to use the specialist.", count, peer);
    } else if (type === "selection.excluded" && info) {
      peers[peer] = "Unavailable";
      add(1, "coordinator", info.name + " was excluded", "The live Agent Card was unavailable or incompatible. No question was sent to this candidate.", count, peer);
    } else if (type === "rpc.send" && info) {
      peers[peer] = "Question sent";
      add(3, "coordinator", "Coordinator queried " + info.name, "Sent the question using recipient-scoped credentials. A send alone does not confirm receipt.", count, peer);
    } else if (type === "delegation.started" && info) {
      const child = / task='([^']+)'/.exec(line)?.[1];
      if (!child) return;
      receipts[peer] = child;
      peers[peer] = "Received · awaiting response";
      add(3, "specialist", info.name + " received the question", modelMode ? "The specialist acknowledged the task. Its configured workflow retrieves the topic note and requests a generated answer from the local model. Awaiting a response." : "The specialist acknowledged a task. Its fixture workflow checks the topic and retrieves “" + info.source + "”. Awaiting a response; no model is thinking.", count, peer);
    } else if (type === "review.outcome" && info) {
      const state = / state=([a-z]+)/.exec(line)?.[1] || "unknown";
      peers[peer] = state === "completed" ? "Responded" : state;
      add(4, "coordinator", state === "completed" ? info.name + " responded to the coordinator" : info.name + " outcome: " + state,
        state === "completed" ? "The coordinator accepted the structured finding within the review limits. It will combine the findings before returning them to the client." : "No validated finding from this specialist. The coordinator will report an incomplete review; it will not blindly retry.", count, peer);
    } else if ((type === "delegation.cancelled" || type === "delegation.cancel_unknown") && info) {
      const confirmed = type === "delegation.cancelled";
      peers[peer] = confirmed ? "Canceled" : "Cancel unknown";
      add(3, "specialist", info.name + (confirmed ? " cancellation confirmed" : " cancellation is unconfirmed"), "The coordinator attempted to stop its delegated work. Cancellation evidence is separate from the root task’s outcome.", count, peer);
    } else if (type === "selection.none") {
      add(1, "coordinator", "Coordinator found no suitable specialist", line.includes("no-topic") ? "This question does not match a supported topic. No directory or specialist request was needed." : "No authorized, compatible specialist is available. No specialist request was sent.", count);
    } else if (type === "selection.ambiguous") {
      add(2, "coordinator", "Coordinator needs a narrower question", "Several topics matched equally. No specialist was queried.", count);
    }
  });
  if (terminalStates.includes(task.state)) {
    const complete = task.state === "TASK_STATE_COMPLETED" && task.result;
    const incomplete = complete && task.result.answer.startsWith("Incomplete review");
    const state = task.state.replace("TASK_STATE_", "").toLowerCase();
    add(complete ? 5 : result.at(-1).stage, complete ? "client" : "coordinator",
      complete ? (incomplete ? "Coordinator returned an incomplete review" : "Coordinator delivered the response to the client") : "Review " + state,
      complete ? (task.result.references.length ? task.result.references.length + " cited specialist " + (task.result.references.length === 1 ? "finding" : "findings") + " returned. Read the final response above." : "The coordinator returned an explanation with no specialist findings.") : "No answer was delivered. A stopped root task does not prove every remote operation stopped; inspect the execution evidence.",
      task.events.length, null, Boolean(complete));
  }
  return result;
}
function controls() {
  const ready = !busy && !switching && recording && terminalStates.includes(recording.state);
  element("replay").disabled = !ready;
  element("pause").disabled = !ready || !replaying || cursor >= frames.length - 1;
  element("pause").textContent = replaying && !timer ? "Resume" : "Pause";
  element("previous").disabled = !ready || !replaying || cursor <= 0;
  element("next").disabled = !ready || !replaying || cursor >= frames.length - 1;
}
function stopTimer() { if (timer !== null) clearTimeout(timer); timer = null; }
// Review sections use the coordinator's fixed role headers; never reconstruct a peer answer.
function peerFinding(answer, peer) {
  const prefix = peer + ": completed\n";
  return (answer || "").split(/\n\n(?=(?:runbook|security|release): )/)
    .find(section => section.startsWith(prefix))?.slice(prefix.length) || null;
}
function renderAgentWork(frame, task) {
  const container = element("agent-details");
  const opened = new Set([...container.children].filter(node => node.open).map(node => node.dataset.peer));
  container.replaceChildren();
  for (const [peer, info] of Object.entries(specialists)) {
    if (!frame.peers[peer]) continue;
    const detail = document.createElement("details"), summary = document.createElement("summary");
    detail.dataset.peer = peer; detail.open = opened.has(peer);
    summary.textContent = info.name + " — " + frame.peers[peer]; detail.append(summary);
    const add = (label, text) => {
      const row = document.createElement("p"), heading = document.createElement("strong");
      heading.textContent = label + ": "; row.append(heading, document.createTextNode(text)); detail.append(row);
    };
    if (frame.receipts[peer]) {
      add("Question received", task.question);
      add("Task receipt", frame.receipts[peer]);
      add("Processing summary", modelMode
        ? "The configured model workflow uses the bundled note as context and validates the generated answer. This describes the workflow, not private model reasoning."
        : frame.peers[peer] === "Responded"
        ? "Matched the topic and returned the bundled “" + info.source + "” note with a source reference."
        : "The configured workflow applies fixture controls, matches the topic and retrieves “" + info.source + "”. Acknowledgment alone does not confirm completion.");
    } else add("Receipt", "No specialist task acknowledgment observed at this step.");
    if (frame.peers[peer] === "Responded") {
      const finding = peerFinding(task.result?.answer, peer);
      if (finding) {
        const heading = document.createElement("h3"), response = document.createElement("div");
        response.className = "markdown-response";
        heading.textContent = "Returned finding"; renderMarkdown(response, finding);
        detail.append(heading, response);
        const source = task.result.references.find(ref => ref.fixture_id === info.fixture);
        if (source) add("Source", source.title);
      } else add("Returned finding", "No individual response is available in the captured coordinator result.");
    } else add("Returned finding", "No validated response observed at this step.");
    container.append(detail);
  }
  element("agent-work").hidden = !container.children.length;
}
function render() {
  if (!recording || !frames.length) return;
  const frame = frames[cursor];
  const firstDelivery = frame.delivered && element("result").hidden;
  element("view-label").textContent = replaying ? "Recorded replay" : "Live execution";
  element("status").textContent = replaying ? (timer ? "Playing" : "Paused") : recording.state.replace("TASK_STATE_", "").toLowerCase();
  element("step-count").textContent = (replaying ? "Recorded step " : "Observed step ") + (cursor + 1) + " of " + frames.length;
  element("step-title").textContent = frame.title;
  element("step-detail").textContent = frame.detail;
  element("flow-question").textContent = recording.question;
  element("client-state").textContent = frame.delivered ? "Response received" : "Question sent";
  element("coordinator-state").textContent = ["Question received", "Checking suitability", "Choosing a specialist", "Delegating the question", "Collecting findings", "Response returned"][frame.stage];
  element("client-node").dataset.active = String(frame.actor === "client");
  element("coordinator-node").dataset.active = String(frame.actor === "coordinator");
  element("return-path").hidden = !frame.delivered;
  element("return-path").dataset.active = String(frame.delivered);
  [...element("stages").children].forEach((node, index) => {
    node.dataset.current = String(index === frame.stage);
    if (index === frame.stage) node.setAttribute("aria-current", "step"); else node.removeAttribute("aria-current");
  });
  const list = element("specialists"); list.replaceChildren();
  for (const [peer, info] of Object.entries(specialists)) {
    const row = document.createElement("div"); row.className = "specialist";
    row.dataset.active = String(frame.peer === peer);
    const label = document.createElement("div"), name = document.createElement("strong"), topic = document.createElement("small"), state = document.createElement("span");
    name.textContent = info.name; topic.textContent = info.skill;
    state.textContent = frame.peers[peer] || (frame.stage >= 2 ? "Not selected" : "Not queried");
    label.append(name, topic); row.append(label, state); list.append(row);
  }
  element("events").replaceChildren();
  for (const event of recording.events.slice(0, frame.eventCount)) {
    const item = document.createElement("li"); item.textContent = event; element("events").append(item);
  }
  element("task-id").textContent = "Coordinator task: " + recording.task_id + Object.entries(frame.receipts).map(([peer, id]) => " · " + specialists[peer].name + " task: " + id).join("");
  element("result").hidden = !frame.delivered;
  if (frame.delivered) {
    element("result-title").textContent = recording.result.answer.startsWith("Incomplete review") ? "Incomplete review delivered to client" : "Response delivered to client";
    element("result-summary").textContent = recording.result.references.length + " cited specialist " + (recording.result.references.length === 1 ? "finding" : "findings") + " returned by the coordinator.";
    renderMarkdown(element("answer"), recording.result.answer);
    element("sources").textContent = "Sources: " + (recording.result.references.map(ref => ref.title).join(" · ") || "No specialist sources");
  } else {
    element("answer").textContent = ""; element("sources").textContent = "";
  }
  element("replay-note").textContent = replaying ? "Recorded evidence only. No requests are sent." : busy ? "Live events are shown as observed; replay afterward to inspect each step." : "Replay the captured steps without running the agents again.";
  renderAgentWork(frame, recording);
  if (firstDelivery) element("result").scrollIntoView({block: "start", behavior: "instant"});
  controls();
}
function advanceReplay() {
  stopTimer();
  if (!replaying || cursor >= frames.length - 1) { render(); return; }
  timer = setTimeout(() => { timer = null; cursor += 1; advanceReplay(); }, 1400);
  render();
}
element("replay").addEventListener("click", () => {
  if (busy || switching || !recording || !terminalStates.includes(recording.state)) return;
  stopTimer(); replaying = true; cursor = 0; render();
});
element("pause").addEventListener("click", () => {
  if (!replaying) return;
  if (timer !== null) { stopTimer(); render(); } else advanceReplay();
});
element("previous").addEventListener("click", () => {
  if (!replaying || cursor <= 0) return;
  stopTimer(); cursor -= 1; render();
});
element("next").addEventListener("click", () => {
  if (!replaying || cursor >= frames.length - 1) return;
  stopTimer(); cursor += 1; render();
});
function resetView() {
  stopTimer(); replaying = false; recording = null; frames = []; cursor = 0;
  element("result").hidden = true; element("answer").textContent = ""; element("sources").textContent = "";
  element("events").replaceChildren(); element("task-id").textContent = "";
  element("agent-details").replaceChildren(); element("agent-work").hidden = true;
  element("view-label").textContent = "Live execution"; element("status").textContent = "Ready";
  element("step-count").textContent = "Ready for your question";
  element("step-title").textContent = "One question. The right specialist.";
  element("step-detail").textContent = "Start with one specialist, then compare Alice and Bob on the three-specialist review.";
  element("flow-question").textContent = "Run the demo to send your question.";
  element("client-state").textContent = "Ready to ask"; element("coordinator-state").textContent = "Find. Check. Delegate.";
  element("client-node").dataset.active = "false"; element("coordinator-node").dataset.active = "false";
  element("return-path").hidden = true;
  element("return-path").dataset.active = "false";
  for (const stage of element("stages").children) { stage.dataset.current = "false"; stage.removeAttribute("aria-current"); }
  element("specialists").replaceChildren();
  for (const info of Object.values(specialists)) {
    const row = document.createElement("div"); row.className = "specialist";
    const name = document.createElement("strong"), state = document.createElement("span");
    name.textContent = info.name; state.textContent = "Not queried"; row.append(name, state); element("specialists").append(row);
  }
  element("replay-note").textContent = "Replay becomes available after execution ends."; controls();
}
async function poll(taskId) {
  const deadline = Date.now() + pollTimeout;
  while (Date.now() < deadline) {
    const task = await api("/api/task?id=" + encodeURIComponent(taskId));
    if (active === taskId) { recording = task; frames = buildFrames(task); cursor = frames.length - 1; render(); }
    if (terminalStates.includes(task.state)) return;
    await new Promise(resolve => setTimeout(resolve, 350));
  }
  throw new Error("Polling timed out. Refresh to inspect your task; do not assume it was canceled.");
}
element("question-form").addEventListener("submit", async event => {
  event.preventDefault(); if (busy || switching || !csrf) return;
  const question = element("question").value.trim(); if (!question) return;
  resetView(); element("error").textContent = ""; lock(true);
  element("status").textContent = "Sending";
  try {
    const task = await api("/api/ask", {text: question}); active = task.task_id; lock(true);
    element("execution").scrollIntoView({block: "start", behavior: "instant"});
    await poll(active);
  } catch (error) { element("error").textContent = error.message; element("status").textContent = "Request needs attention"; }
  finally { active = null; lock(false); }
});
element("cancel").addEventListener("click", async () => {
  if (!active) return;
  try { await api("/api/cancel", {task_id: active}); }
  catch (error) { element("error").textContent = error.message; }
});
element("identity").addEventListener("change", async () => {
  if (busy || switching) return;
  switching = true; stopTimer(); lock(false); element("error").textContent = "";
  try {
    const session = await api("/api/identity", {owner: element("identity").value});
    csrf = session.csrf; owner = session.owner; resetView();
  } catch (error) { element("identity").value = owner; element("error").textContent = error.message; }
  finally { switching = false; lock(false); }
});
document.querySelectorAll("[data-question]").forEach(button => button.addEventListener("click", () => {
  element("question").value = button.dataset.question; element("question").focus();
}));
(async () => {
  resetView(); lock(false);
  try {
    const session = await api("/api/session"); csrf = session.csrf; owner = session.owner; element("identity").value = owner;
    modelMode = session.inference_backend === "ollama"; pollTimeout = session.poll_timeout_ms || 60000;
    if (modelMode) {
      document.querySelector("footer p").textContent = "Real A2A HTTP · Local model: " + session.model;
      document.querySelector("#agent-work .note").textContent = "Expand an agent to inspect its workflow summary and model-generated finding. Summaries are not private model reasoning.";
      document.querySelector(".technical details .note").textContent = "Task acknowledgments prove receipt. Processing summaries describe the configured workflow.";
    }
    const latest = session.tasks.filter(id => !id.startsWith("pending-")).at(-1);
    if (latest) { active = latest; lock(true); await poll(latest); }
  } catch (error) { element("error").textContent = error.message; }
  finally { active = null; lock(false); }
})();
