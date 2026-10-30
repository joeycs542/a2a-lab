// Run with node scripts/web-ui-smoke.cjs; no dependencies required.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
class Element {
  constructor() { this.childNodes = []; this._text = ""; this._html = ""; this.listeners = {}; this.dataset = {}; }
  get textContent() { return this._text; }
  set textContent(value) { this._text = value; this._html = ""; this.childNodes = []; }
  get innerHTML() { return this._html; }
  set innerHTML(value) { this._html = value; this._text = ""; this.childNodes = []; }
  get children() { return this.childNodes; }
  append(...nodes) { this.childNodes.push(...nodes); }
  replaceChildren() { this.childNodes = []; }
  addEventListener(name, action) { this.listeners[name] = action; }
  scrollIntoView() {}
  setAttribute() {}
  removeAttribute() {}
}
const elements = new Map();
const get = id => {
  if (!elements.has(id)) elements.set(id, new Element());
  return elements.get(id);
};
get("stages").append(...Array.from({length: 6}, () => new Element()));
const document = {getElementById: get, createElement: () => new Element(), createTextNode: text => ({textContent: text, childNodes: []}), querySelectorAll: () => []};
let finishIdentity, requests = 0, timerId = 0;
const timers = new Map();
const context = vm.createContext({document, AbortController, URL, location: {href: "http://127.0.0.1:8080/"},
  setTimeout: callback => { timers.set(++timerId, callback); return timerId; },
  clearTimeout: id => timers.delete(id),
  fetch: async path => {
    requests++;
    if (path === "/api/identity") await new Promise(resolve => { finishIdentity = resolve; });
    return {ok: true, json: async () => ({owner: "alice", csrf: "test", tasks: []})};
  }
});
vm.runInContext(fs.readFileSync(require("node:path").join(__dirname, "../src/a2a_lab/web/markdown-it.min.js"), "utf8"), context);
vm.runInContext(fs.readFileSync(require("node:path").join(__dirname, "../src/a2a_lab/web/app.js"), "utf8"), context);
const run = source => vm.runInContext(source, context);
context.sample = "# Heading\n\n**Bold** and *emphasis* with `code`.\n\n- First\n- Second\n\n| A | B |\n| - | - |\n| 1 | 2 |";
const formatted = run('markdown.render(sample)');
assert.match(formatted, /<h1>Heading<\/h1>/);
assert.match(formatted, /<strong>Bold<\/strong>/);
assert.match(formatted, /<em>emphasis<\/em>/);
assert.match(formatted, /<code>code<\/code>/);
assert.match(formatted, /<ul>/);
assert.match(formatted, /<table>/);
context.unsafe = '<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>\n\n[bad](javascript:alert(1)) [bad](data:text/html,evil) ![remote](https://example.com/image.png)';
const safe = run('markdown.render(unsafe)');
assert.doesNotMatch(safe, /<script|<img|href="(?:javascript|data):/i);
assert.match(run('markdown.render("[docs](https://example.com)")'), /href="https:\/\/example.com"/);
const task = {task_id: "root", question: "<img src=x onerror=alert(1)>", state: "TASK_STATE_COMPLETED",
  events: ["directory.search", "discovery.approved agent=runbook skill=operations-runbook",
    "selection.selected agent=runbook reason=topic-match", "rpc.send agent=runbook url=http://fixture",
    "delegation.started agent=runbook task='child-1'", "review.outcome agent=runbook state=completed"],
  result: {answer: "<script>untrusted answer</script>", references: [{title: "Service runbook"}]}
};
context.testTask = task;
const frames = run("buildFrames(testTask)");
assert.equal(frames[3].peers.runbook, "Selected");
assert.equal(frames[4].receipts.runbook, undefined, "send alone must not imply receipt");
assert.equal(frames[5].receipts.runbook, "child-1");
assert.equal(frames[3].receipts.runbook, undefined, "later evidence must not mutate earlier frames");
assert.equal(frames.at(-1).delivered, true);
context.testTask = {...task, state: "TASK_STATE_CANCELED", result: undefined, events: task.events.slice(0, 4)};
const canceled = run("buildFrames(testTask)");
assert.equal(canceled.at(-1).delivered, false);
assert.equal(canceled.at(-1).receipts.runbook, undefined);
context.testTask = {...task, events: ["selection.selected agent=runbook reason=topic-match", "review.outcome agent=runbook state=unknown"], result: {answer: "Incomplete review", references: []}};
assert.match(run("buildFrames(testTask)").at(-2).detail, /No validated finding/);
const nodeText = node => node.textContent + (node.innerHTML || "") + node.childNodes.map(nodeText).join("");
context.peerTask = {...task, result: {
  answer: "Engineering review\n\nrunbook: completed\nLiteral <img src=x> finding.\n\nsecurity: completed\nSecurity finding.",
  references: [{fixture_id: "runbook", title: "Service runbook"}]
}};
run("renderAgentWork(buildFrames(peerTask)[5], peerTask)");
assert.doesNotMatch(nodeText(get("agent-details")), /Literal <img/);
run("renderAgentWork(buildFrames(peerTask)[6], peerTask)");
assert.match(nodeText(get("agent-details")), /Literal &lt;img src=x&gt; finding/);
assert.doesNotMatch(nodeText(get("agent-details")), /Security finding/);
get("agent-details").children[0].open = true;
run("renderAgentWork(buildFrames(peerTask)[6], peerTask)");
assert.equal(get("agent-details").children[0].open, true, "polling preserves expanded agent");
assert.equal(run('peerFinding("Unexpected format", "runbook")'), null);
(async () => {
  await new Promise(resolve => setImmediate(resolve));
  context.testTask = task;
  run("recording = testTask; frames = buildFrames(recording); cursor = frames.length - 1; render()");
  assert.match(get("answer").innerHTML, /&lt;script&gt;untrusted answer&lt;\/script&gt;/);
  assert.equal(get("flow-question").textContent, task.question);
  const before = requests;
  get("replay").listeners.click();
  assert.equal(get("result").hidden, true);
  assert.equal(get("return-path").hidden, true);
  assert.equal(get("answer").textContent, "");
  assert.equal(get("events").childNodes.length, 0);
  assert.equal(run("timer"), null, "replay starts paused");
  assert.equal(get("previous").disabled, true);
  get("pause").listeners.click();
  assert.notEqual(run("timer"), null, "resume starts playback");
  get("pause").listeners.click();
  assert.equal(run("timer"), null);
  get("next").listeners.click();
  assert.equal(run("cursor"), 1);
  get("pause").listeners.click();
  get("previous").listeners.click();
  assert.equal(run("timer"), null, "previous pauses automatic playback");
  assert.equal(run("cursor"), 0);
  get("next").listeners.click();
  while (run("cursor < frames.length - 1")) get("next").listeners.click();
  assert.equal(get("result").hidden, false);
  assert.equal(get("return-path").hidden, false);
  get("previous").listeners.click();
  assert.equal(get("result").hidden, true, "stepping back hides future answer");
  assert.equal(get("return-path").hidden, true, "stepping back hides delivery arrow");
  while (run("cursor > 0")) get("previous").listeners.click();
  assert.equal(get("previous").disabled, true);
  assert.equal(get("events").childNodes.length, 0);
  get("previous").listeners.click();
  assert.equal(run("cursor"), 0, "cannot go before first frame");
  assert.equal(requests, before, "replay must not make requests");
  run('owner = "bob"; resetView()');
  assert.equal(get("client-label").textContent, "Client · Bob");
  assert.match(get("identity-permissions").textContent, /Security is not permitted/);
  run("recording = testTask; frames = buildFrames(recording); cursor = frames.length - 1; render()");
  assert.match(nodeText(get("specialists")), /Not permitted for Bob/);
  run('owner = "alice"; resetView()');
  const changing = get("identity").listeners.change();
  assert.equal(get("send").disabled, true);
  finishIdentity(); await changing;
  assert.equal(get("send").disabled, false);
  assert.equal(get("result").hidden, true);
  assert.equal(get("return-path").hidden, true);
  assert.equal(run("recording"), null);
  assert.equal(get("replay").disabled, true);
  get("identity").append(new Element(), new Element());
  run('applyScenario({demo_scenario:"team-lunch", specialists:{runbook:{name:"Food",section:"Food"},security:{name:"Budget",section:"Budget"},release:{name:"Place",section:"Place"}}}); owner="bob"; resetView()');
  assert.equal(get("page-heading").textContent, "Plan a team lunch.");
  assert.match(get("identity-permissions").textContent, /Only the organizer can see the budget/);
  assert.doesNotMatch(get("identity-permissions").textContent, /Security|runbook/);
  context.lunchText = "Team lunch plan:\n\nFood: completed\nMeal choices.\n\nBudget: completed\nBudget detail.";
  assert.equal(run('peerFinding(lunchText, "runbook")'), "Meal choices.");
  console.log("UI smoke passed: evidence ordering, receipts, unknown/cancel outcomes, inert text, replay isolation, identity reset.");
})().catch(error => { console.error(error); process.exitCode = 1; });
