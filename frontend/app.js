const API = "http://localhost:8000";
const $ = (id) => document.getElementById(id);
const PARTIAL = / \(from character \d+\)$/;
const normalize = (p) => (String(p || ".").trim().replace(/\\/g, "/").replace(/^\.\//, "").replace(/\/+$/, "") || ".");

// ---------------------------------------------------------------- tree
const Graph = (() => {
  const pane = $("graph-pane");
  const svg = d3.select("#graph");
  const vp = svg.append("g");                      // everything inside here pans/zooms
  const linkG = vp.append("g"), trailG = vp.append("g"), nodeG = vp.append("g");
  const zoom = d3.zoom().scaleExtent([0.05, 4]).on("zoom", (e) => {
    vp.attr("transform", e.transform);
    svg.classed("far", e.transform.k < 0.45).style("--k", e.transform.k);   // far = hide small labels
  });
  svg.call(zoom).on("dblclick.zoom", null);

  const ROW = 18;    // vertical space between nodes
  const COL = 130;   // horizontal space between levels

  let byId = new Map(), kids = new Map(), laid = new Map();
  let open = new Set(["."]);
  let nodeSel = null, trail = [], pos = ".", active = false, intro = false;
  const sets = { listed: new Set(), read: new Set(), match: new Set(), seen: new Set() };

  // receive the flat list from the backend and draw the FULL tree (every folder open)
  function setTree(data) {
    clear();
    const nodes = data.nodes.map((n) => ({ ...n }));
    byId = new Map(nodes.map((n) => [n.id, n]));
    kids = new Map();
    nodes.forEach((n) => {
      if (n.parent === null) return;
      if (!kids.has(n.parent)) kids.set(n.parent, []);
      kids.get(n.parent).push(n);
    });
    kids.forEach((list) =>
      list.sort((a, b) => (a.type === b.type ? a.name.localeCompare(b.name) : a.type === "dir" ? -1 : 1))
    );
    open = new Set(kids.keys());
    intro = true;                                  // the first draw grows level by level
    render(true);
  }

  const radius = (n) => (n.id === "." ? 8 : n.type === "dir" ? 5 : 3);

  function fadeIn(sel, depthOf) {
    sel.style("opacity", 0)
      .transition().delay((d) => depthOf(d) * 140).duration(450)
      .style("opacity", 1)
      .on("end", function () { d3.select(this).style("opacity", null); });
  }

  function render(refit) {
    if (!byId.has(".")) return;
    const root = d3.hierarchy(byId.get("."), (d) => (open.has(d.id) ? kids.get(d.id) : null));
    d3.tree().nodeSize([ROW, COL])(root);
    const list = root.descendants();
    laid = new Map(list.map((d) => [d.data.id, d]));

    const links = linkG.selectAll("path")
      .data(root.links(), (d) => d.target.data.id)
      .join("path")
      .attr("class", "link")
      .attr("fill", "none")
      .attr("d", d3.linkHorizontal().x((d) => d.y).y((d) => d.x));

    nodeSel = nodeG.selectAll("g.node")
      .data(list, (d) => d.data.id)
      .join((enter) => {
        const g = enter.append("g")
          .attr("class", (d) => "node " + d.data.type)
          .on("click", (e, d) => toggle(d.data.id));
        g.append("circle").attr("class", "halo").attr("r", (d) => radius(d.data) + 3);
        g.append("circle").attr("class", "body").attr("r", (d) => radius(d.data));
        g.append("text").attr("x", (d) => radius(d.data) + 6).attr("y", 3);
        g.append("title").text((d) => d.data.id);
        return g;
      })
      .classed("show", true)
      .classed("top", (d) => d.depth <= 1 && d.data.type === "dir")
      .style("cursor", (d) => (kids.has(d.data.id) ? "pointer" : "default"))
      .attr("transform", (d) => `translate(${d.y},${d.x})`);

    nodeSel.select("text").text((d) => {
      const n = d.data;
      const closed = n.type === "dir" && kids.has(n.id) && !open.has(n.id);
      return n.name + (closed ? "  +" : "");
    });

    if (intro) {
      fadeIn(links, (d) => d.target.depth);
      fadeIn(nodeSel, (d) => d.depth);
      intro = false;
    }
    paint();
    if (refit) fit(list);
  }

  function paint() {
    if (!nodeSel) return;
    svg.classed("exploring", active);
    nodeSel
      .classed("seen", (d) => sets.seen.has(d.data.id))
      .classed("listed", (d) => sets.listed.has(d.data.id))
      .classed("match", (d) => sets.match.has(d.data.id))
      .classed("read", (d) => sets.read.has(d.data.id))
      .classed("visited", (d) => sets.listed.has(d.data.id) || sets.read.has(d.data.id) || sets.match.has(d.data.id))
      .classed("current", (d) => active && d.data.id === pos);

    trailG.selectAll("path")
      .data(trail)
      .join("path")
      .attr("class", "trail")
      .attr("d", (t) => {
        const a = laid.get(t.from), b = laid.get(t.to);
        if (!a || !b) return null;
        const mid = (a.y + b.y) / 2;
        return `M${a.y},${a.x}C${mid},${a.x} ${mid},${b.x} ${b.y},${b.x}`;
      });
  }

  // overview: the whole tree centred in the pane
  function fit(list) {
    if (!list || !list.length) return;
    const w = pane.clientWidth, h = pane.clientHeight;
    if (!w || !h) return;
    const [x0, x1] = d3.extent(list, (n) => n.x), [y0, y1] = d3.extent(list, (n) => n.y);
    const k = Math.max(0.05, Math.min(1.2, 0.92 * Math.min(w / (y1 - y0 + COL), h / (x1 - x0 + 40))));
    svg.transition().duration(600).call(
      zoom.transform,
      d3.zoomIdentity.translate(w / 2 - (k * (y0 + y1)) / 2, h / 2 - (k * (x0 + x1)) / 2).scale(k)
    );
  }

  // close-up on one node
  function follow(id) {
    const n = laid.get(id);
    if (!n) return;
    const w = pane.clientWidth, h = pane.clientHeight, k = 0.95;
    if (!w || !h) return;
    svg.transition().duration(500).call(
      zoom.transform,
      d3.zoomIdentity.translate(w * 0.4 - k * n.y, h / 2 - k * n.x).scale(k)
    );
  }

  // small tree: show all of it. big tree: follow the agent.
  function camera() {
    const list = Array.from(laid.values());
    if (!list.length) return;
    const w = pane.clientWidth, h = pane.clientHeight;
    if (!w || !h) return;
    const [x0, x1] = d3.extent(list, (n) => n.x), [y0, y1] = d3.extent(list, (n) => n.y);
    if ((y1 - y0 + COL) * 0.9 <= w && (x1 - x0 + 40) * 0.9 <= h) fit(list);
    else follow(pos);
  }

  const refit = () => fit(Array.from(laid.values()));

  function toggle(id) {
    if (!kids.has(id)) return;
    open.has(id) ? open.delete(id) : open.add(id);
    render(false);
  }

  function reveal(id) {
    let p = byId.get(id) && byId.get(id).parent;
    while (p !== null && p !== undefined) {
      open.add(p);
      p = byId.get(p).parent;
    }
  }

  function expandAll() { open = new Set(kids.keys()); render(false); }

  // close everything except the paths the agent has explored
  function collapse() {
    open = new Set(["."]);
    sets.listed.forEach((id) => open.add(id));
    [...sets.listed, ...sets.read, ...sets.match].forEach(reveal);
    render(false);
  }

  // jump to a file (used when you hover a step or click a file in the list)
  function focus(raw) {
    const id = normalize(String(raw).replace(PARTIAL, ""));
    if (!byId.has(id)) return;
    reveal(id);
    render(false);
    follow(id);
  }

  // called for every step the agent takes
  function apply(f) {
    const path = normalize(f.target.replace(PARTIAL, ""));
    let hits = [];
    if (f.action === "list_dir" && byId.has(path)) {
      sets.listed.add(path);
      (kids.get(path) || []).forEach((n) => sets.seen.add(n.id));
      open.add(path);
      hits = [path];
    } else if (f.action === "read_file" && byId.has(path)) {
      sets.read.add(path);
      hits = [path];
    } else if (f.action === "search_code") {
      const m = /^Matched files: (.*)$/m.exec(f.result_summary);
      hits = m ? m[1].split(" | ").map(normalize).filter((id) => byId.has(id)) : [];
      hits.forEach((id) => sets.match.add(id));
    }
    hits.forEach(reveal);
    if (hits.length) {
      if (pos !== hits[0]) trail.push({ from: pos, to: hits[0] });
      pos = hits[0];
    }
    render(false);
    if (hits.length) camera();
  }

  function reset(on = false) {            // forget the exploration, keep the tree as it is
    Object.values(sets).forEach((s) => s.clear());
    trail = []; pos = "."; active = on;
    render(false);
  }

  function clear() {
    byId = new Map(); kids = new Map(); nodeSel = null; laid = new Map();
    open = new Set(["."]);
    Object.values(sets).forEach((s) => s.clear());
    trail = []; pos = "."; active = false;
    [linkG, trailG, nodeG].forEach((g) => g.selectAll("*").remove());
  }

  return {
    setTree, apply, reset, clear, refit, camera, focus, expandAll, collapse,
    setActive: (on) => { active = on; paint(); },
  };
})();

// ---------------------------------------------------------------- page
const landing = $("landing"), workspace = $("workspace");
const repoUrlInput = $("repo-url"), loadBtn = $("load-btn"), repoStatus = $("repo-status");
const stepper = $("stepper"), stepEls = [...stepper.children], backBtn = $("back-btn");
const loader = $("loader"), loaderTitle = $("loader-title"), loaderTime = $("loader-time"), barFill = $("bar-fill");
const repoChip = $("repo-chip"), repoName = $("repo-name");
const changeBtn = $("change-btn"), mapBtn = $("map-btn"), fitBtn = $("fit-btn"), expandBtn = $("expand-btn");
const thread = $("thread"), inner = $("thread-inner");
const welcome = $("welcome"), welcomeRepo = $("welcome-repo");
const question = $("question"), askBtn = $("ask-btn"), hint = $("ask-status");
const graphEmpty = $("graph-empty"), pill = $("pill"), mapMeta = $("map-meta");
const srcList = $("src-list"), srcEmpty = $("src-empty");
const cta = $("cta"), ctaInput = $("cta-input"), ctaGo = $("cta-go"), ctaStats = $("cta-stats");

const DEFAULT_HINT = "The agent can make mistakes. Open the steps to check what it actually read.";

let repoId = localStorage.getItem("repoId");
let sessionId = localStorage.getItem("sessionId");
let repoReady = false, asking = false, shown = 0, timer = null, t0 = 0;
let repoGen = 0, askGen = 0, treeFor = null, treeReady = Promise.resolve();
let cur = null, stick = true, expanded = true, lastDesc = "";
const sources = new Set();

const post = (body) => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const setStatus = (text, kind = "") => { repoStatus.textContent = text; repoStatus.className = "status " + kind; };
const setHint = (text, kind = "") => { hint.textContent = text || DEFAULT_HINT; hint.className = "hint " + kind; };

function refresh() {
  question.disabled = !repoReady;
  askBtn.disabled = !repoReady || asking;
}

async function api(path, options) {
  let res;
  try { res = await fetch(API + path, options); }
  catch { throw new Error("Cannot reach the backend. Is it running?"); }
  if (!res.ok) {
    const err = new Error((await res.json().catch(() => ({}))).detail || "Server returned " + res.status);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

function ensureTree() {
  // the tree is measured on screen, so it can only be drawn while the workspace is visible
  if (repoId && treeFor !== repoId && !workspace.hidden) {
    const id = (treeFor = repoId);
    treeReady = api(`/repos/${id}/tree`)
      .then((d) => {
        Graph.setTree(d);
        graphEmpty.hidden = true;
        expanded = true; expandBtn.textContent = "Collapse";
        const dirs = d.nodes.filter((n) => n.type === "dir").length - 1;
        const files = d.nodes.filter((n) => n.type === "file").length;
        const stats = `${files} files · ${dirs} folders${d.truncated ? " (partial)" : ""}`;
        mapMeta.textContent = stats;
        ctaStats.textContent = "· " + stats;
      })
      .catch(() => { treeFor = null; });
  }
  return treeReady;
}

// ---- stages: "tree" = full-screen map, "chat" = map on the left + chat on the right
const stage = () => (workspace.classList.contains("stage-chat") ? "chat" : "tree");
const reframe = () => (stage() === "tree" ? Graph.refit() : Graph.camera());

function setStage(s) {
  workspace.classList.toggle("stage-tree", s === "tree");
  workspace.classList.toggle("stage-chat", s === "chat");
  mapBtn.hidden = workspace.hidden || s === "tree";
}

function repoLabel() {
  const u = (repoUrlInput.value || localStorage.getItem("repoUrl") || "")
    .trim().replace(/\/+$/, "").replace(/\.git$/, "");
  return u.split("/").slice(-2).join("/") || "this repository";
}

function showWorkspace(s) {
  if (s) setStage(s);                       // set the stage before showing, so nothing animates on arrival
  landing.hidden = true; workspace.hidden = false;
  repoChip.hidden = changeBtn.hidden = false;
  mapBtn.hidden = stage() === "tree";
  repoName.textContent = welcomeRepo.textContent = repoLabel();
  ensureTree();
  if (treeFor === repoId) setTimeout(reframe, 80);
  if (stage() === "chat") question.focus({ preventScroll: true });
  else ctaInput.focus({ preventScroll: true });
}

function leaveChat() {
  workspace.hidden = true; landing.hidden = false;
  repoChip.hidden = changeBtn.hidden = mapBtn.hidden = true;
  backBtn.hidden = !repoReady;
}

// move from the full-screen tree to the chat; the tree slides to the left
function goChat(q) {
  if (!repoReady) return;
  ctaInput.value = "";
  setStage("chat");
  setTimeout(() => Graph.camera(), 700);
  setTimeout(() => question.focus({ preventScroll: true }), 450);
  if (q) askQuestion(q);
}

const STAGES = {
  pending:  { pct: 6,   title: "Starting…" },
  cloning:  { pct: 25,  title: "Cloning the repository…" },
  parsing:  { pct: 55,  title: "Reading and parsing files…" },
  indexing: { pct: 80,  title: "Indexing the code for search…" },
  ready:    { pct: 100, title: "Done" },
};
let loadTimer = null, loadT0 = 0;

function startLoadTimer() {
  if (loadTimer) return;
  loadT0 = Date.now();
  const tick = () => { loaderTime.textContent = Math.round((Date.now() - loadT0) / 1000) + "s"; };
  tick();
  loadTimer = setInterval(tick, 1000);
}
function stopLoadTimer() { clearInterval(loadTimer); loadTimer = null; }
function hideLoader() { stopLoadTimer(); loader.hidden = true; }

function setStepper(status) {
  const info = STAGES[status] || STAGES.pending;
  loader.hidden = false;
  loaderTitle.textContent = info.title;
  barFill.style.width = info.pct + "%";
  const idx = status === "ready" ? stepEls.length : Math.max(0, ["cloning", "parsing", "indexing"].indexOf(status));
  stepEls.forEach((li, i) => { li.classList.toggle("done", i < idx); li.classList.toggle("active", i === idx); });
  if (status === "ready") stopLoadTimer(); else startLoadTimer();
}
// ---- thread helpers
thread.addEventListener("scroll", () => {
  stick = thread.scrollHeight - thread.scrollTop - thread.clientHeight < 140;
});
function scrollDown(force) {
  if (force) stick = true;
  if (stick) thread.scrollTop = thread.scrollHeight;
}

function autosize() {
  question.style.height = "auto";
  question.style.height = Math.min(question.scrollHeight, 160) + "px";
}

function clearThread() {
  inner.querySelectorAll(".msg").forEach((m) => m.remove());
  welcome.hidden = false;
  cur = null; shown = 0; lastDesc = "";
  resetSources();
}

function resetSources() {
  sources.clear(); srcList.innerHTML = ""; srcEmpty.hidden = false;
}
function addSource(path) {
  if (sources.has(path)) return;
  sources.add(path);
  srcEmpty.hidden = true;
  const li = document.createElement("li");
  const span = document.createElement("span");
  span.textContent = path;
  li.title = "Show in the map";
  li.appendChild(span);
  li.addEventListener("click", () => Graph.focus(path));
  srcList.appendChild(li);
}

function addUser(text) {
  const el = document.createElement("div");
  el.className = "msg user";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  el.appendChild(bubble);
  inner.appendChild(el);
}

function addAgent() {
  const el = document.createElement("div");
  el.className = "msg agent";
  el.innerHTML = `
    <div class="avatar">◈</div>
    <div class="body">
      <details class="trace" open>
        <summary><span class="spin"></span><span class="t-title">Exploring the repository…</span><span class="t-meta"></span></summary>
        <ol class="steps"></ol>
      </details>
      <div class="answer markdown" hidden></div>
      <div class="actions" hidden><button class="mini copy">Copy answer</button></div>
    </div>`;
  inner.appendChild(el);
  return {
    el,
    trace: el.querySelector(".trace"),
    title: el.querySelector(".t-title"),
    meta: el.querySelector(".t-meta"),
    steps: el.querySelector(".steps"),
    answer: el.querySelector(".answer"),
    actions: el.querySelector(".actions"),
    copy: el.querySelector(".copy"),
  };
}

function describe(f) {
  const t = f.target.replace(PARTIAL, "");
  if (f.action === "list_dir") return t === "." ? "Listing the project root" : `Listing ${t}`;
  if (f.action === "read_file") return `Reading ${t}`;
  if (f.action === "search_code") return `Searching “${t}”`;
  return f.action;
}

function tickMeta() {
  if (!cur || !t0) return;
  const s = Math.round((Date.now() - t0) / 1000);
  cur.meta.textContent = `${shown} step${shown === 1 ? "" : "s"} · ${s}s`;
}
function startTimer() { stopTimer(); tickMeta(); timer = setInterval(tickMeta, 1000); }
function stopTimer() { clearInterval(timer); timer = null; }

// ---- repository
async function loadRepo() {
  const url = repoUrlInput.value.trim();
  if (!url) return setStatus("Please enter a repository URL.", "error");

  loadBtn.disabled = true; repoReady = false; asking = false; askGen++; stopTimer(); refresh();
  clearThread(); Graph.clear(); treeFor = null; graphEmpty.hidden = false; pill.hidden = true;
  mapMeta.textContent = ""; ctaStats.textContent = "";
  sessionId = null; localStorage.removeItem("sessionId");
  backBtn.hidden = true;
  setStage("tree");
  setHint(""); setStatus("");
  hideLoader(); setStepper("pending");          // show the loading block right away
  try {
    const d = await api("/repos", post({ repo_url: url }));
    repoId = d.repo_id;
    localStorage.setItem("repoId", repoId);
    localStorage.setItem("repoUrl", url);
    pollRepo(++repoGen);
  } catch (e) {
    loadBtn.disabled = false;
    hideLoader();
    setStatus(e.message, "error");
  }
}

async function pollRepo(my) {
  try {
    const d = await api(`/repos/${repoId}/status`);
    if (my !== repoGen) return;

    if (d.status === "ready") {
      repoReady = true; loadBtn.disabled = false; refresh();
      const wasLoading = !loader.hidden;
      if (wasLoading) {
        setStepper("ready");                     // bar fills to 100%, every step ticked
        setTimeout(() => {                       // then the loader gives way to the Ready message
          if (my !== repoGen) return;
          hideLoader();
          setStatus(`Ready · ${d.chunk_count} chunks indexed`, "ok");
        }, 700);
        setTimeout(() => { if (my === repoGen) showWorkspace(sessionId ? "chat" : "tree"); }, 2200);
      } else {                                   // e.g. a page refresh on a repo that is already ready
        setStatus(`Ready · ${d.chunk_count} chunks indexed`, "ok");
        showWorkspace(sessionId ? "chat" : "tree");
      }
    } else if (d.status === "failed") {
      askGen++; loadBtn.disabled = false; hideLoader();
      setStatus("Failed: " + d.error, "error");
    } else {
      setStatus("");
      setStepper(d.status);
      setTimeout(() => pollRepo(my), 1500);
    }
  } catch (e) {
    if (my !== repoGen) return;
    askGen++; loadBtn.disabled = false; hideLoader();
    if (e.status === 404) { repoId = null; localStorage.removeItem("repoId"); }
    setStatus(e.status === 404 ? "The backend no longer has this repository. Click Load to add it again." : e.message, "error");
  }
}

// ---- questions
// ---- questions
const STEP_MS = 900;      // how long each step stays on screen before the next one
let queue = [], received = 0, pumping = false, pendingDone = null, instantOnce = false;

async function askQuestion(text) {
  const q = (typeof text === "string" ? text : question.value).trim();
  if (!repoReady || asking || !q) return;

  question.value = ""; autosize();
  welcome.hidden = true; setHint("");
  asking = true; refresh(); Graph.reset(); resetSources();
  shown = 0; received = 0; queue = []; pendingDone = null; pumping = false; instantOnce = false; lastDesc = "";
  addUser(q);
  cur = addAgent();
  scrollDown(true);
  t0 = Date.now();
  Graph.setActive(true);
  pill.hidden = false; pill.textContent = "Starting…";
  try {
    const d = await api("/ask", post({ repo_id: repoId, question: q }));
    sessionId = d.session_id;
    localStorage.setItem("sessionId", sessionId);
    startTimer();
    pollAnswer(++askGen);
  } catch (e) {
    fail(e.message);
  }
}

async function pollAnswer(my) {
  try {
    if (my !== askGen) return;
    if (!repoReady) return setTimeout(() => pollAnswer(my), 400);   // after a refresh, wait for the repo check
    const d = await api(`/ask/${sessionId}`);
    if (my !== askGen) return;
    await ensureTree();

    if (!cur) {                                   // restored after a page refresh
      instantOnce = true;                         // steps that already happened appear at once
      welcome.hidden = true;
      addUser(d.question);
      cur = addAgent();
    }

    const running = d.status === "running";
    if (running) {
      asking = true; refresh();
      Graph.setActive(true);
      if (!t0) t0 = Date.now();
      if (!timer) startTimer();
    }

    d.findings.slice(received).forEach((f) => queue.push(f));
    received = d.findings.length;
    pump(my);

    if (running) return setTimeout(() => pollAnswer(my), 1000);
    pendingDone = d;                              // finish once every step has been shown
    pump(my);
  } catch (e) {
    if (my !== askGen) return;
    if (e.status === 404) { sessionId = null; localStorage.removeItem("sessionId"); }
    if (!cur) { asking = false; refresh(); return; }
    fail(e.status === 404 ? "That session is gone (the backend was restarted). Please ask again." : e.message);
  }
}

// shows the queued steps one at a time, then finishes
function pump(my) {
  if (instantOnce) {
    instantOnce = false;
    while (queue.length) showStep(queue.shift());
  }
  if (pumping) return;
  pumping = true;
  const next = () => {
    if (my !== askGen) { pumping = false; return; }
    if (queue.length) {
      showStep(queue.shift());
      return setTimeout(next, STEP_MS);
    }
    pumping = false;
    if (pendingDone) { const d = pendingDone; pendingDone = null; finish(d); }
  };
  next();
}

function showStep(f) {
  addStep(f);
  shown++;
  lastDesc = describe(f);
  pill.hidden = false;
  pill.textContent = `${lastDesc} · step ${shown}`;
  tickMeta();
  scrollDown();
}

function addStep(f) {
  Graph.apply(f);
  if (f.action === "read_file") addSource(f.target.replace(PARTIAL, ""));
  const li = document.createElement("li");
  li.innerHTML = "<details><summary><span class='badge'></span><code></code></summary><pre></pre></details>";
  const badge = li.querySelector(".badge");
  badge.textContent = f.action;
  badge.classList.add(f.action);
  li.querySelector("code").textContent = f.target;
  li.querySelector("pre").textContent = f.result_summary;
  li.querySelector("summary").addEventListener("mouseenter", () => Graph.focus(f.target));
  cur.steps.appendChild(li);
}

// ---- wiring
loadBtn.addEventListener("click", loadRepo);
repoUrlInput.addEventListener("keydown", (e) => { if (e.key === "Enter") loadRepo(); });

askBtn.addEventListener("click", () => askQuestion());
question.addEventListener("input", autosize);
question.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); askQuestion(); }
});
welcome.addEventListener("click", (e) => {
  const b = e.target.closest("[data-q]");
  if (b) askQuestion(b.dataset.q);
});

ctaGo.addEventListener("click", () => goChat(ctaInput.value.trim()));
ctaInput.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.isComposing) goChat(ctaInput.value.trim()); });
cta.addEventListener("click", (e) => {
  const b = e.target.closest("[data-q]");
  if (b) goChat(b.dataset.q);
});

changeBtn.addEventListener("click", leaveChat);
$("brand").addEventListener("click", (e) => { e.preventDefault(); if (!workspace.hidden) leaveChat(); });
backBtn.addEventListener("click", () => showWorkspace());

mapBtn.addEventListener("click", () => {
  const off = workspace.classList.toggle("map-off");
  mapBtn.textContent = off ? "Show map" : "Hide map";
  setTimeout(reframe, 700);
});
fitBtn.addEventListener("click", () => Graph.refit());
expandBtn.addEventListener("click", () => {
  expanded = !expanded;
  if (expanded) Graph.expandAll(); else Graph.collapse();
  expandBtn.textContent = expanded ? "Collapse" : "Expand all";
  reframe();
});

let resizeTimer;
window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(reframe, 200); });

// ---- start
const small = matchMedia("(max-width: 900px)").matches;
workspace.classList.toggle("map-off", small);        // on a phone the map starts as a closed drawer
mapBtn.textContent = small ? "Show map" : "Hide map";
repoUrlInput.value = localStorage.getItem("repoUrl") || "";
setHint("");
refresh();
if (repoId) {
  loadBtn.disabled = true;
  setStatus("Checking saved repository…");
  pollRepo(++repoGen);
}
if (sessionId) pollAnswer(++askGen);