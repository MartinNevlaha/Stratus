/* Stratus Swarm Monitor — Polling + Canvas + Panel updates */

(function () {
  "use strict";

  const POLL_INTERVAL = 3000;
  const API_URL = "/api/dashboard/state";

  // Category colors matching CSS vars
  const COLORS = {
    planning: "#42a5f5",
    implementation: "#66bb6a",
    review: "#ffa726",
    testing: "#ab47bc",
    delivery: "#26c6da",
  };

  let state = null;
  let pollTimer = null;
  let animFrame = null;
  let startTime = Date.now();

  // --- Polling ---

  async function fetchState() {
    try {
      const resp = await fetch(API_URL);
      if (resp.ok) {
        state = await resp.json();
        updatePanels(state);
      }
    } catch (_) {
      // Silently retry on next poll
    }
  }

  function startPolling() {
    fetchState();
    pollTimer = setInterval(fetchState, POLL_INTERVAL);
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  // Pause polling when tab is hidden
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) {
      stopPolling();
    } else {
      startPolling();
    }
  });

  // --- Panel updates ---

  function updatePanels(s) {
    // Version badge
    const versionEl = document.getElementById("version");
    if (versionEl) versionEl.textContent = "v" + s.version;

    // Status indicator
    const statusEl = document.getElementById("status-indicator");
    if (statusEl) {
      const mode = s.orchestration.mode;
      statusEl.textContent = mode;
      statusEl.className = "badge " + mode;
    }

    updatePhasePanel(s.orchestration);
    updateAgentList(s.agents);
    updateLearningPanel(s.learning);
    updateMemoryPanel(s.memory);
  }

  function updatePhasePanel(orch) {
    const el = document.getElementById("phase-content");
    if (!el) return;

    if (orch.mode === "inactive") {
      el.innerHTML = '<span class="muted">No active workflow</span>';
      return;
    }

    if (orch.mode === "spec" && orch.spec) {
      const spec = orch.spec;
      const pct = spec.total_tasks > 0
        ? Math.round((spec.completed_tasks / spec.total_tasks) * 100)
        : 0;
      el.innerHTML = [
        '<span class="phase-badge ' + spec.phase + '">' + spec.phase + "</span>",
        '<div class="stat-row"><span>Slug</span><span class="stat-value">' + spec.slug + "</span></div>",
        '<div class="stat-row"><span>Tasks</span><span class="stat-value">' + spec.completed_tasks + "/" + spec.total_tasks + "</span></div>",
        spec.review_iteration > 0
          ? '<div class="stat-row"><span>Review</span><span class="stat-value">#' + spec.review_iteration + "</span></div>"
          : "",
        '<div class="progress-bar"><div class="progress-fill" style="width:' + pct + '%"></div></div>',
      ].join("");
      return;
    }

    if (orch.mode === "delivery" && orch.delivery) {
      const d = orch.delivery;
      el.innerHTML = [
        '<span class="phase-badge implement">' + d.delivery_phase + "</span>",
        '<div class="stat-row"><span>Slug</span><span class="stat-value">' + d.slug + "</span></div>",
        '<div class="stat-row"><span>Lead</span><span class="stat-value">' + (d.phase_lead || "—") + "</span></div>",
      ].join("");
    }
  }

  function updateAgentList(agents) {
    const ul = document.getElementById("agent-list");
    if (!ul) return;

    if (!agents || agents.length === 0) {
      ul.innerHTML = '<li><span class="muted">No active agents</span></li>';
      return;
    }

    ul.innerHTML = agents
      .map(function (a) {
        var cat = a.category || "planning";
        var roleTag = a.role === "lead" ? " (lead)" : "";
        return (
          '<li><span class="agent-dot ' + cat + ' active"></span>' +
          a.label + roleTag +
          "</li>"
        );
      })
      .join("");
  }

  function updateLearningPanel(learn) {
    var el = document.getElementById("learning-content");
    if (!el) return;

    if (!learn.enabled) {
      el.innerHTML = '<span class="muted">Disabled</span>';
      return;
    }

    var pending = learn.proposals.pending ? learn.proposals.pending.length : 0;
    el.innerHTML = [
      '<div class="stat-row"><span>Sensitivity</span><span class="stat-value">' + learn.sensitivity + "</span></div>",
      '<div class="stat-row"><span>Candidates</span><span class="stat-value">' + learn.stats.candidates + "</span></div>",
      '<div class="stat-row"><span>Proposals</span><span class="stat-value">' + learn.stats.proposals + "</span></div>",
      '<div class="stat-row"><span>Pending</span><span class="stat-value">' + pending + "</span></div>",
    ].join("");
  }

  function updateMemoryPanel(mem) {
    var el = document.getElementById("memory-content");
    if (!el) return;
    el.innerHTML = [
      '<div class="stat-row"><span>Events</span><span class="stat-value">' + mem.total_events + "</span></div>",
      '<div class="stat-row"><span>Sessions</span><span class="stat-value">' + mem.total_sessions + "</span></div>",
    ].join("");
  }

  // --- Canvas swarm animation ---

  var canvas = document.getElementById("swarm");
  var ctx = canvas ? canvas.getContext("2d") : null;

  function resizeCanvas() {
    if (!canvas) return;
    var container = canvas.parentElement;
    var size = Math.min(container.clientWidth - 32, container.clientHeight - 32, 600);
    canvas.width = size;
    canvas.height = size;
  }

  function drawSwarm(timestamp) {
    if (!ctx || !canvas) return;
    var w = canvas.width;
    var h = canvas.height;
    var cx = w / 2;
    var cy = h / 2;
    var elapsed = (timestamp - startTime) / 1000;

    ctx.clearRect(0, 0, w, h);

    // Central hub
    var phase = "inactive";
    var pct = 0;
    if (state && state.orchestration) {
      if (state.orchestration.mode === "spec" && state.orchestration.spec) {
        phase = state.orchestration.spec.phase;
        var spec = state.orchestration.spec;
        pct = spec.total_tasks > 0 ? spec.completed_tasks / spec.total_tasks : 0;
      } else if (state.orchestration.mode === "delivery" && state.orchestration.delivery) {
        phase = state.orchestration.delivery.delivery_phase;
      } else {
        phase = state.orchestration.mode;
      }
    }

    // Progress ring
    var ringR = 40;
    ctx.beginPath();
    ctx.arc(cx, cy, ringR, 0, 2 * Math.PI);
    ctx.strokeStyle = "rgba(255,255,255,0.1)";
    ctx.lineWidth = 4;
    ctx.stroke();

    if (pct > 0) {
      ctx.beginPath();
      ctx.arc(cx, cy, ringR, -Math.PI / 2, -Math.PI / 2 + 2 * Math.PI * pct);
      ctx.strokeStyle = "#4fc3f7";
      ctx.lineWidth = 4;
      ctx.stroke();
    }

    // Phase label at center
    ctx.fillStyle = "#e0e0e0";
    ctx.font = "bold 14px monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(phase.toUpperCase(), cx, cy);

    // Agent nodes in orbit
    var agents = state ? state.agents || [] : [];
    var orbitR = Math.min(w, h) * 0.32;

    // Draw connection lines first
    for (var i = 0; i < agents.length; i++) {
      for (var j = i + 1; j < agents.length; j++) {
        if (agents[i].category === agents[j].category) {
          var ai = agentPosition(i, agents.length, orbitR, elapsed, cx, cy);
          var aj = agentPosition(j, agents.length, orbitR, elapsed, cx, cy);
          var breathe = 0.15 + 0.1 * Math.sin(elapsed * 1.5);
          ctx.beginPath();
          ctx.moveTo(ai.x, ai.y);
          ctx.lineTo(aj.x, aj.y);
          ctx.strokeStyle = "rgba(79,195,247," + breathe + ")";
          ctx.lineWidth = 1;
          ctx.stroke();
        }
      }
    }

    // Draw nodes
    for (var k = 0; k < agents.length; k++) {
      var agent = agents[k];
      var pos = agentPosition(k, agents.length, orbitR, elapsed, cx, cy);
      var color = COLORS[agent.category] || COLORS.planning;
      var nodeR = 18;

      // Glow
      if (agent.active) {
        var glowAlpha = 0.3 + 0.15 * Math.sin(elapsed * 2 + k);
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, nodeR + 6, 0, 2 * Math.PI);
        ctx.fillStyle = color.replace(")", "," + glowAlpha + ")").replace("rgb", "rgba");
        // color is hex, convert glow
        ctx.fillStyle = hexToRgba(color, glowAlpha);
        ctx.fill();
      }

      // Circle
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, nodeR, 0, 2 * Math.PI);
      ctx.fillStyle = hexToRgba(color, 0.85);
      ctx.fill();
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.stroke();

      // Line to center
      ctx.beginPath();
      ctx.moveTo(pos.x, pos.y);
      ctx.lineTo(cx, cy);
      ctx.strokeStyle = "rgba(255,255,255,0.05)";
      ctx.lineWidth = 1;
      ctx.stroke();

      // Label
      ctx.fillStyle = "#fff";
      ctx.font = "11px monospace";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      var shortLabel = agent.label.length > 12
        ? agent.label.substring(0, 11) + "\u2026"
        : agent.label;
      ctx.fillText(shortLabel, pos.x, pos.y + nodeR + 14);
    }

    animFrame = requestAnimationFrame(drawSwarm);
  }

  function agentPosition(index, total, radius, time, cx, cy) {
    var baseAngle = (2 * Math.PI * index) / Math.max(total, 1);
    var speed = 0.15 + index * 0.03;
    var angle = baseAngle + time * speed;
    var wobble = 8 * Math.sin(time * 0.7 + index * 1.3);
    var r = radius + wobble;
    return {
      x: cx + r * Math.cos(angle),
      y: cy + r * Math.sin(angle),
    };
  }

  function hexToRgba(hex, alpha) {
    var r = parseInt(hex.slice(1, 3), 16);
    var g = parseInt(hex.slice(3, 5), 16);
    var b = parseInt(hex.slice(5, 7), 16);
    return "rgba(" + r + "," + g + "," + b + "," + alpha + ")";
  }

  // --- Init ---

  window.addEventListener("resize", resizeCanvas);
  resizeCanvas();
  startPolling();
  initTabs();
  startTime = performance.now();
  animFrame = requestAnimationFrame(drawSwarm);

  // --- Tabs ---

  var tabLoaded = {};

  function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(function(btn) {
      btn.addEventListener('click', function() { switchTab(btn.dataset.tab); });
    });
  }

  function switchTab(name) {
    document.querySelectorAll('.tab-btn').forEach(function(b) {
      b.classList.toggle('active', b.dataset.tab === name);
    });
    document.querySelectorAll('.tab-content').forEach(function(s) {
      s.classList.toggle('active', s.id === 'tab-' + name);
    });
    loadTabData(name);
  }

  function loadTabData(name) {
    if (tabLoaded[name]) return;
    tabLoaded[name] = true;
    if (name === 'retrieve') loadRetrievalStatus();
    if (name === 'memory') loadRecentMemory();
    if (name === 'agents') loadRegistry();
    if (name === 'learning') loadLearning();
  }

  // --- Retrieve tab ---

  function loadRetrievalStatus() {
    fetch('/api/retrieval/status')
      .then(function(r) { return r.ok ? r.json() : null; })
      .then(function(data) {
        if (!data) return;
        renderVexorStats(data);
        renderGovStats(data);
      })
      .catch(function() {});

    document.getElementById('vexor-btn').addEventListener('click', doVexorSearch);
    document.getElementById('vexor-query').addEventListener('keydown', function(e) {
      if (e.key === 'Enter') doVexorSearch();
    });
    document.getElementById('gov-btn').addEventListener('click', doGovSearch);
    document.getElementById('gov-query').addEventListener('keydown', function(e) {
      if (e.key === 'Enter') doGovSearch();
    });
  }

  function renderVexorStats(data) {
    var el = document.getElementById('vexor-stats');
    if (!el) return;
    var avail = data.vexor_available;
    var is = data.index_state || {};
    var statusBadge = avail
      ? '<span class="badge-fresh">available</span>'
      : '<span class="badge-stale">unavailable</span>';
    var staleBadge = is.stale !== undefined
      ? (is.stale ? '<span class="badge-stale">stale</span>' : '<span class="badge-fresh">fresh</span>')
      : '';
    var commit = is.last_indexed_commit ? is.last_indexed_commit.substring(0, 8) : '—';
    var files = is.total_files !== undefined ? is.total_files : '—';
    var model = is.model || '—';
    var ts = is.last_indexed_at ? new Date(is.last_indexed_at).toLocaleString() : '—';

    el.innerHTML =
      '<div class="index-stat">' +
        '<span class="index-stat-label">Status</span>' +
        '<span class="index-stat-value">' + statusBadge + '</span>' +
      '</div>' +
      '<div class="index-stat">' +
        '<span class="index-stat-label">Index</span>' +
        '<span class="index-stat-value">' + staleBadge + '</span>' +
      '</div>' +
      '<div class="index-stat">' +
        '<span class="index-stat-label">Files</span>' +
        '<span class="index-stat-value">' + escHtml(String(files)) + '</span>' +
      '</div>' +
      '<div class="index-stat">' +
        '<span class="index-stat-label">Commit</span>' +
        '<span class="index-stat-value">' + escHtml(commit) + '</span>' +
      '</div>' +
      '<div class="index-stat">' +
        '<span class="index-stat-label">Model</span>' +
        '<span class="index-stat-value">' + escHtml(model) + '</span>' +
      '</div>' +
      '<div class="index-stat">' +
        '<span class="index-stat-label">Last indexed</span>' +
        '<span class="index-stat-value">' + escHtml(ts) + '</span>' +
      '</div>';
  }

  function renderGovStats(data) {
    var el = document.getElementById('gov-stats');
    if (!el) return;
    var avail = data.governance_available;
    var gs = data.governance_stats || {};
    var statusBadge = avail
      ? '<span class="badge-fresh">available</span>'
      : '<span class="badge-stale">unavailable</span>';
    var files = gs.total_files !== undefined ? gs.total_files : '—';
    var chunks = gs.total_chunks !== undefined ? gs.total_chunks : '—';
    var byType = gs.by_doc_type || {};
    var typeOrder = ['rule', 'adr', 'template', 'skill', 'agent', 'architecture', 'project'];
    var pills = typeOrder
      .filter(function(t) { return byType[t] > 0; })
      .map(function(t) {
        return '<span class="doc-type-pill tag ' + t + '">' + t + ' <strong>' + byType[t] + '</strong></span>';
      }).join('');
    Object.keys(byType).forEach(function(t) {
      if (typeOrder.indexOf(t) === -1 && byType[t] > 0) {
        pills += '<span class="doc-type-pill">' + escHtml(t) + ' <strong>' + byType[t] + '</strong></span>';
      }
    });

    el.innerHTML =
      '<div class="index-stat">' +
        '<span class="index-stat-label">Status</span>' +
        '<span class="index-stat-value">' + statusBadge + '</span>' +
      '</div>' +
      '<div class="index-stat">' +
        '<span class="index-stat-label">Files</span>' +
        '<span class="index-stat-value">' + escHtml(String(files)) + '</span>' +
      '</div>' +
      '<div class="index-stat">' +
        '<span class="index-stat-label">Chunks</span>' +
        '<span class="index-stat-value">' + escHtml(String(chunks)) + '</span>' +
      '</div>' +
      (pills ? '<div class="doc-type-pills">' + pills + '</div>' : '');
  }

  function doVexorSearch() {
    var q = document.getElementById('vexor-query').value.trim();
    if (!q) return;
    var el = document.getElementById('vexor-results');
    el.innerHTML = '<span class="muted">Searching...</span>';
    fetch('/api/retrieval/search?query=' + encodeURIComponent(q) + '&corpus=code&top_k=10')
      .then(function(r) { return r.ok ? r.json() : null; })
      .then(function(data) { renderResults(data, 'vexor-results'); })
      .catch(function() { document.getElementById('vexor-results').innerHTML = '<span class="muted">Search failed.</span>'; });
  }

  function doGovSearch() {
    var q = document.getElementById('gov-query').value.trim();
    if (!q) return;
    var el = document.getElementById('gov-results');
    el.innerHTML = '<span class="muted">Searching...</span>';
    fetch('/api/retrieval/search?query=' + encodeURIComponent(q) + '&corpus=governance&top_k=10')
      .then(function(r) { return r.ok ? r.json() : null; })
      .then(function(data) { renderResults(data, 'gov-results'); })
      .catch(function() { document.getElementById('gov-results').innerHTML = '<span class="muted">Search failed.</span>'; });
  }

  function renderResults(data, targetId) {
    var el = document.getElementById(targetId);
    if (!el) return;
    var results = data && data.results ? data.results : [];
    if (results.length === 0) {
      el.innerHTML = '<span class="muted">No results.</span>';
      // Remove any lingering click handler before returning
      el.onclick = null;
      return;
    }

    el.innerHTML = results.map(function(r, idx) {
      var score = r.score !== undefined ? (r.score * 100).toFixed(0) + '%' : '';
      var title = escHtml(r.title || r.file_path || 'Result');
      var pathText = r.file_path || '';
      if (r.line_start) pathText += ':' + r.line_start + (r.line_end ? '-' + r.line_end : '');
      var path = pathText ? '<div class="result-path">' + escHtml(pathText) + '</div>' : '';
      var snippet = escHtml((r.excerpt || r.content || r.snippet || '').substring(0, 200));
      var docType = r.doc_type ? '<span class="tag ' + r.doc_type + '">' + r.doc_type + '</span>' : '';

      // Detail section — full excerpt + metadata grid
      var fullExcerpt = r.excerpt || r.content || r.snippet || '';
      var metaRows = '';
      if (r.language) metaRows += '<div class="result-detail-meta-row"><span class="result-detail-meta-label">Language</span><span>' + escHtml(r.language) + '</span></div>';
      if (r.corpus)   metaRows += '<div class="result-detail-meta-row"><span class="result-detail-meta-label">Corpus</span><span>' + escHtml(r.corpus) + '</span></div>';
      if (r.rank !== undefined) metaRows += '<div class="result-detail-meta-row"><span class="result-detail-meta-label">Rank</span><span>' + escHtml(String(r.rank)) + '</span></div>';
      if (r.chunk_index !== undefined) metaRows += '<div class="result-detail-meta-row"><span class="result-detail-meta-label">Chunk</span><span>' + escHtml(String(r.chunk_index)) + '</span></div>';
      if (r.line_start !== undefined) {
        var lineRange = String(r.line_start) + (r.line_end ? '–' + r.line_end : '');
        metaRows += '<div class="result-detail-meta-row"><span class="result-detail-meta-label">Lines</span><span>' + escHtml(lineRange) + '</span></div>';
      }
      if (r.file_path) metaRows += '<div class="result-detail-meta-row result-detail-meta-full"><span class="result-detail-meta-label">Path</span><span>' + escHtml(r.file_path) + '</span></div>';

      var detailHtml =
        '<div class="result-detail">' +
          (metaRows ? '<div class="result-detail-meta">' + metaRows + '</div>' : '') +
          '<pre class="result-detail-excerpt">' + escHtml(fullExcerpt) + '</pre>' +
        '</div>';

      return '<div class="result-card" data-result-idx="' + idx + '">' +
        '<div class="result-header">' +
          '<span class="result-title">' + title + '</span>' +
          '<span class="result-header-right">' +
            '<span class="result-score">' + score + '</span>' +
            '<span class="result-chevron" aria-hidden="true">&#9654;</span>' +
          '</span>' +
        '</div>' +
        path +
        (docType ? '<div style="margin-bottom:0.3rem">' + docType + '</div>' : '') +
        '<div class="result-snippet">' + snippet + '</div>' +
        detailHtml +
        '</div>';
    }).join('');

    // Event delegation — one listener per container, replaces previous one
    el.onclick = function(evt) {
      var card = evt.target.closest('.result-card');
      if (!card) return;
      var isExpanded = card.classList.contains('expanded');
      // Collapse all cards in this container
      el.querySelectorAll('.result-card.expanded').forEach(function(c) {
        c.classList.remove('expanded');
      });
      // If the clicked card was not already expanded, expand it
      if (!isExpanded) {
        card.classList.add('expanded');
      }
    };
  }

  // --- Memory tab ---

  function loadRecentMemory() {
    fetchRecentMemory();
    fetchSessions();

    document.getElementById('memory-btn').addEventListener('click', function() {
      var q = document.getElementById('memory-query').value.trim();
      if (q) {
        fetchMemorySearch(q);
      } else {
        fetchRecentMemory();
      }
    });
    document.getElementById('memory-query').addEventListener('keydown', function(e) {
      if (e.key === 'Enter') {
        var q = document.getElementById('memory-query').value.trim();
        if (q) {
          fetchMemorySearch(q);
        } else {
          fetchRecentMemory();
        }
      }
    });
  }

  function fetchRecentMemory() {
    fetch('/api/memory/recent?limit=20')
      .then(function(r) { return r.ok ? r.json() : null; })
      .then(function(data) {
        var results = data && data.results ? data.results : [];
        renderMemoryEvents(results, 'Recent Memories');
      })
      .catch(function() {});
  }

  function fetchMemorySearch(query) {
    fetch('/api/search?limit=20&query=' + encodeURIComponent(query))
      .then(function(r) { return r.ok ? r.json() : null; })
      .then(function(data) {
        var results = data && data.results ? data.results : [];
        renderMemoryEvents(results, 'Search Results');
      })
      .catch(function() {});
  }

  function fetchSessions() {
    fetch('/api/sessions?limit=10')
      .then(function(r) { return r.ok ? r.json() : null; })
      .then(function(data) {
        var sessions = data && data.sessions ? data.sessions : [];
        renderSessions(sessions);
      })
      .catch(function() {});
  }

  function renderMemoryEvents(events, heading) {
    var el = document.getElementById('memory-results');
    if (!el) return;

    var headingHtml = heading
      ? '<h3 class="memory-section-heading">' + escHtml(heading) + '</h3>'
      : '';

    if (!events.length) {
      el.innerHTML = headingHtml + '<span class="muted">No events found.</span>';
      // Remove any lingering click handler before returning
      el.onclick = null;
      return;
    }
    el.innerHTML = headingHtml + events.map(function(ev, idx) {
      var title = escHtml(ev.title || ev.text.substring(0, 60));
      var text = escHtml(ev.text ? ev.text.substring(0, 200) : '');
      var ts = ev.ts ? new Date(ev.ts).toLocaleString() : '';
      var type = ev.type || 'event';
      var imp = ev.importance !== undefined ? ev.importance : 0.5;

      var typeBadge = '<span class="tag">' + escHtml(type) + '</span>';
      var scopeBadge = ev.scope
        ? ' <span class="tag tag-scope">' + escHtml(ev.scope) + '</span>'
        : '';
      var actorBadge = ev.actor
        ? ' <span class="tag tag-actor">' + escHtml(ev.actor) + '</span>'
        : '';

      var tagPills = '';
      if (ev.tags && ev.tags.length) {
        tagPills = '<div class="event-tag-pills">' +
          ev.tags.map(function(t) {
            return '<span class="tag-pill">' + escHtml(t) + '</span>';
          }).join('') +
          '</div>';
      }

      // Detail section — full text + metadata grid
      var metaRows = '';
      if (ev.id)         metaRows += '<div class="result-detail-meta-row"><span class="result-detail-meta-label">ID</span><span>' + escHtml(String(ev.id)) + '</span></div>';
      if (ev.project)    metaRows += '<div class="result-detail-meta-row"><span class="result-detail-meta-label">Project</span><span>' + escHtml(ev.project) + '</span></div>';
      if (ev.session_id) metaRows += '<div class="result-detail-meta-row result-detail-meta-full"><span class="result-detail-meta-label">Session</span><span>' + escHtml(ev.session_id) + '</span></div>';
      if (ev.dedupe_key) metaRows += '<div class="result-detail-meta-row result-detail-meta-full"><span class="result-detail-meta-label">Dedupe key</span><span>' + escHtml(ev.dedupe_key) + '</span></div>';
      if (ev.ttl != null) metaRows += '<div class="result-detail-meta-row"><span class="result-detail-meta-label">TTL</span><span>' + escHtml(String(ev.ttl)) + '</span></div>';
      if (ev.importance !== undefined) metaRows += '<div class="result-detail-meta-row"><span class="result-detail-meta-label">Importance</span><span>' + escHtml(String(ev.importance)) + '</span></div>';
      if (ev.created_at_epoch != null) {
        var createdAt = new Date(ev.created_at_epoch * 1000).toLocaleString();
        metaRows += '<div class="result-detail-meta-row"><span class="result-detail-meta-label">Created at</span><span>' + escHtml(createdAt) + '</span></div>';
      }

      var refsRows = '';
      if (ev.refs && typeof ev.refs === 'object' && Object.keys(ev.refs).length > 0) {
        refsRows = Object.keys(ev.refs).map(function(k) {
          return '<div class="result-detail-meta-row result-detail-meta-full"><span class="result-detail-meta-label">' + escHtml(k) + '</span><span>' + escHtml(String(ev.refs[k])) + '</span></div>';
        }).join('');
      }

      var detailHtml =
        '<div class="event-detail">' +
          (metaRows || refsRows ? '<div class="result-detail-meta">' + metaRows + refsRows + '</div>' : '') +
          '<pre class="event-detail-text">' + escHtml(ev.text || '') + '</pre>' +
        '</div>';

      return '<div class="event-card" data-event-idx="' + idx + '">' +
        '<div class="event-header">' +
          '<span class="event-title">' + title + '</span>' +
          '<span class="event-header-right">' +
            '<span class="event-time">' + escHtml(ts) + '</span>' +
            '<span class="result-chevron" aria-hidden="true">&#9654;</span>' +
          '</span>' +
        '</div>' +
        '<div class="event-badges">' + typeBadge + scopeBadge + actorBadge + '</div>' +
        (tagPills ? tagPills : '') +
        '<div class="event-text">' + text + '</div>' +
        '<div class="importance-bar"><div class="importance-fill" style="width:' + Math.round(imp * 100) + '%"></div></div>' +
        detailHtml +
        '</div>';
    }).join('');

    // Event delegation — one listener per container, replaces previous one
    el.onclick = function(evt) {
      var card = evt.target.closest('.event-card');
      if (!card) return;
      var isExpanded = card.classList.contains('expanded');
      // Collapse all cards in this container
      el.querySelectorAll('.event-card.expanded').forEach(function(c) {
        c.classList.remove('expanded');
      });
      // If the clicked card was not already expanded, expand it
      if (!isExpanded) {
        card.classList.add('expanded');
      }
    };
  }

  function renderSessions(sessions) {
    var el = document.getElementById('sessions-list');
    if (!el) return;
    if (!sessions.length) {
      el.innerHTML = '<span class="muted">No sessions found.</span>';
      return;
    }
    el.innerHTML = sessions.map(function(s) {
      var sessionId = escHtml((s.content_session_id || '').substring(0, 20));
      if ((s.content_session_id || '').length > 20) sessionId += '\u2026';
      var project = escHtml(s.project || '');
      var prompt = s.initial_prompt ? escHtml(s.initial_prompt.substring(0, 100)) : '';
      if (s.initial_prompt && s.initial_prompt.length > 100) prompt += '\u2026';
      var ts = s.started_at ? new Date(s.started_at).toLocaleString() : '';
      return '<div class="session-card">' +
        '<div class="session-header">' +
        '<span class="session-id" title="' + escHtml(s.content_session_id || '') + '">' + sessionId + '</span>' +
        '<span class="session-time">' + escHtml(ts) + '</span>' +
        '</div>' +
        (project ? '<div class="session-project">' + project + '</div>' : '') +
        (prompt ? '<div class="session-prompt">' + prompt + '</div>' : '') +
        '</div>';
    }).join('');
  }

  // --- Agents tab ---

  function loadRegistry() {
    fetch('/api/dashboard/registry')
      .then(function(r) { return r.ok ? r.json() : null; })
      .then(function(data) {
        if (!data) return;
        renderAgentsTable(data.agents || []);
        renderSkillsList(data.skills || []);
        renderChipsList(data.rules || [], 'rules-list');
      })
      .catch(function() {});
  }

  function renderAgentsTable(agents) {
    var el = document.getElementById('agents-table-container');
    if (!el) return;
    if (!agents.length) {
      el.innerHTML = '<span class="muted">No agents found.</span>';
      el.onclick = null;
      return;
    }

    el.innerHTML = agents.map(function(a, idx) {
      var model = a.model ? '<span class="tag">' + escHtml(a.model) + '</span>' : '';
      var layer = a.layer ? '<span class="tag agent">' + escHtml(a.layer) + '</span>' : '';
      var write = a.can_write
        ? '<span class="tag yes">write</span>'
        : '<span class="tag no">read-only</span>';

      // Detail metadata
      var phases = Array.isArray(a.phases) ? a.phases.join(', ') : (a.phases || '—');
      var metaRows = '';
      metaRows += '<div class="result-detail-meta-row"><span class="result-detail-meta-label">Filename</span><span>' + escHtml(a.filename || '—') + '</span></div>';
      metaRows += '<div class="result-detail-meta-row"><span class="result-detail-meta-label">Phases</span><span>' + escHtml(phases) + '</span></div>';

      var taskTypes = Array.isArray(a.task_types) && a.task_types.length
        ? a.task_types.map(function(t) { return '<span class="tag">' + escHtml(t) + '</span>'; }).join('')
        : '';
      if (taskTypes) {
        metaRows += '<div class="result-detail-meta-row"><span class="result-detail-meta-label">Task types</span><span>' + taskTypes + '</span></div>';
      }

      var stacks = Array.isArray(a.applicable_stacks) && a.applicable_stacks.length
        ? a.applicable_stacks.map(function(s) { return '<span class="tag">' + escHtml(s) + '</span>'; }).join('')
        : '<span class="muted">universal</span>';
      metaRows += '<div class="result-detail-meta-row"><span class="result-detail-meta-label">Stacks</span><span>' + stacks + '</span></div>';

      var modes = Array.isArray(a.orchestration_modes) && a.orchestration_modes.length
        ? a.orchestration_modes.map(function(m) { return '<span class="tag">' + escHtml(m) + '</span>'; }).join('')
        : '—';
      metaRows += '<div class="result-detail-meta-row"><span class="result-detail-meta-label">Modes</span><span>' + modes + '</span></div>';

      metaRows += '<div class="result-detail-meta-row"><span class="result-detail-meta-label">Optional</span><span>' + (a.optional ? 'yes' : 'no') + '</span></div>';

      var keywords = Array.isArray(a.keywords) && a.keywords.length
        ? a.keywords.map(function(k) { return '<span class="tag">' + escHtml(k) + '</span>'; }).join('')
        : '';
      if (keywords) {
        metaRows += '<div class="result-detail-meta-row"><span class="result-detail-meta-label">Keywords</span><span>' + keywords + '</span></div>';
      }

      return '<div class="agent-card" data-agent-idx="' + idx + '">' +
        '<div class="agent-card-header">' +
          '<span class="agent-card-name">' + escHtml(a.name) + '</span>' +
          '<span class="agent-card-tags">' + model + layer + write + '</span>' +
          '<span class="agent-card-chevron"><span class="result-chevron" aria-hidden="true">&#9654;</span></span>' +
        '</div>' +
        '<div class="agent-detail">' +
          '<div class="result-detail-meta">' + metaRows + '</div>' +
        '</div>' +
        '</div>';
    }).join('');

    el.onclick = function(evt) {
      var card = evt.target.closest('.agent-card');
      if (!card) return;
      var isExpanded = card.classList.contains('expanded');
      el.querySelectorAll('.agent-card.expanded').forEach(function(c) {
        c.classList.remove('expanded');
      });
      if (!isExpanded) {
        card.classList.add('expanded');
      }
    };
  }

  function renderSkillsList(skills) {
    var el = document.getElementById('skills-list');
    if (!el) return;
    if (!skills.length) {
      el.innerHTML = '<span class="muted">None found.</span>';
      el.onclick = null;
      return;
    }

    el.innerHTML = skills.map(function(s, idx) {
      var desc = s.description || '';
      var descShort = desc.length > 80 ? desc.substring(0, 80) + '\u2026' : desc;
      var agentTag = s.agent
        ? '<span class="tag agent">' + escHtml(s.agent) + '</span>'
        : '';
      var contextTag = s.context
        ? '<span class="tag">' + escHtml(s.context) + '</span>'
        : '';

      // Detail metadata
      var metaRows = '';
      if (desc) {
        metaRows += '<div class="result-detail-meta-row result-detail-meta-full"><span class="result-detail-meta-label">Description</span><span>' + escHtml(desc) + '</span></div>';
      }
      if (s.agent) {
        metaRows += '<div class="result-detail-meta-row"><span class="result-detail-meta-label">Agent</span><span>' + escHtml(s.agent) + '</span></div>';
      }
      if (s.context) {
        metaRows += '<div class="result-detail-meta-row"><span class="result-detail-meta-label">Context</span><span>' + escHtml(s.context) + '</span></div>';
      }
      metaRows += '<div class="result-detail-meta-row result-detail-meta-full"><span class="result-detail-meta-label">Path</span><span>' + escHtml(s.path || '—') + '</span></div>';

      var bodyHtml = s.body
        ? '<pre class="skill-detail-body">' + escHtml(s.body) + '</pre>'
        : '';

      return '<div class="skill-card" data-skill-idx="' + idx + '">' +
        '<div class="skill-card-header">' +
          '<span class="skill-card-name">' + escHtml(s.name) + '</span>' +
          (descShort ? '<span class="skill-card-desc">' + escHtml(descShort) + '</span>' : '') +
          '<span class="skill-card-tags">' + agentTag + contextTag + '</span>' +
          '<span class="skill-card-chevron"><span class="result-chevron" aria-hidden="true">&#9654;</span></span>' +
        '</div>' +
        '<div class="skill-detail">' +
          (metaRows ? '<div class="result-detail-meta">' + metaRows + '</div>' : '') +
          bodyHtml +
        '</div>' +
        '</div>';
    }).join('');

    el.onclick = function(evt) {
      var card = evt.target.closest('.skill-card');
      if (!card) return;
      var isExpanded = card.classList.contains('expanded');
      el.querySelectorAll('.skill-card.expanded').forEach(function(c) {
        c.classList.remove('expanded');
      });
      if (!isExpanded) {
        card.classList.add('expanded');
      }
    };
  }

  function renderChipsList(items, elId) {
    var el = document.getElementById(elId);
    if (!el) return;
    if (!items.length) {
      el.innerHTML = '<span class="muted">None found.</span>';
      return;
    }
    el.innerHTML = items.map(function(item) {
      return '<span class="chip" title="' + escHtml(item.path || '') + '">' + escHtml(item.name) + '</span>';
    }).join('');
  }

  // --- Learning tab ---

  function loadLearning() {
    Promise.all([
      fetch('/api/learning/proposals?max_count=20').then(function(r) { return r.ok ? r.json() : null; }),
      fetch('/api/learning/analytics/failures/summary?days=30').then(function(r) { return r.ok ? r.json() : null; }),
      fetch('/api/learning/analytics/failures/hotspots?limit=10').then(function(r) { return r.ok ? r.json() : null; }),
      fetch('/api/learning/analytics/rules/effectiveness').then(function(r) { return r.ok ? r.json() : null; }),
    ]).then(function(results) {
      renderProposals(results[0] ? results[0].proposals || [] : []);
      renderFailuresSummary(results[1]);
      renderHotspots(results[2]);
      renderEffectiveness(results[3]);
    }).catch(function() {});
  }

  function renderProposals(proposals) {
    var el = document.getElementById('proposals-list');
    if (!el) return;
    var pending = proposals.filter(function(p) { return p.status === 'pending'; });
    if (!pending.length) {
      el.innerHTML = '<span class="muted">No pending proposals.</span>';
      return;
    }
    el.innerHTML = pending.map(function(p) {
      var conf = (p.confidence || 0);
      var confPct = Math.round(conf * 100);
      var type = p.proposal_type || p.type || '';
      var desc = escHtml((p.description || p.rationale || '').substring(0, 160));
      return '<div class="proposal-card">' +
        '<div class="proposal-title">' + escHtml(p.title || 'Proposal') + ' <span class="tag">' + escHtml(type) + '</span></div>' +
        '<div class="confidence-bar"><div class="confidence-fill" style="width:' + confPct + '%"></div></div>' +
        '<div style="font-size:0.78rem;color:#888;margin-bottom:0.3rem">Confidence: ' + confPct + '%</div>' +
        '<div class="proposal-desc">' + desc + '</div>' +
        '<div class="proposal-actions">' +
        '<button class="btn btn-accept" data-id="' + p.proposal_id + '" data-decision="accept">Accept</button>' +
        '<button class="btn btn-reject" data-id="' + p.proposal_id + '" data-decision="reject">Reject</button>' +
        '<button class="btn btn-ignore" data-id="' + p.proposal_id + '" data-decision="ignore">Ignore</button>' +
        '</div>' +
        '</div>';
    }).join('');
    el.querySelectorAll('.btn[data-id]').forEach(function(btn) {
      btn.addEventListener('click', function() {
        var id = btn.dataset.id;
        var decision = btn.dataset.decision;
        fetch('/api/learning/decide', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({proposal_id: id, decision: decision}),
        }).then(function() {
          tabLoaded.learning = false;
          loadLearning();
        }).catch(function() {});
      });
    });
  }

  function renderFailuresSummary(data) {
    var el = document.getElementById('failures-summary');
    if (!el) return;
    if (!data) { el.innerHTML = '<span class="muted">No data.</span>'; return; }
    var cats = data.by_category || {};
    var trend = data.trend || 'stable';
    var trendColor = trend === 'increasing' ? '#ef5350' : trend === 'decreasing' ? '#66bb6a' : '#ffa726';
    var rows = Object.keys(cats).map(function(cat) {
      return '<div class="stat-row"><span>' + escHtml(cat) + '</span><span class="stat-value">' + cats[cat] + '</span></div>';
    }).join('');
    el.innerHTML = '<div class="stat-row"><span>Total</span><span class="stat-value">' + (data.total_failures || 0) + '</span></div>' +
      '<div class="stat-row"><span>Trend</span><span class="stat-value" style="color:' + trendColor + '">' + trend + '</span></div>' +
      rows;
  }

  function renderHotspots(data) {
    var el = document.getElementById('hotspots-list');
    if (!el) return;
    var spots = data && data.hotspots ? data.hotspots : [];
    if (!spots.length) { el.innerHTML = '<span class="muted">No hotspots.</span>'; return; }
    el.innerHTML = spots.map(function(h) {
      var parts = h.file_path.split('/');
      var shortPath = parts.slice(-2).join('/');
      return '<div class="hotspot-item"><span title="' + escHtml(h.file_path) + '">' + escHtml(shortPath) + '</span><span class="hotspot-count">' + h.total_failures + '</span></div>';
    }).join('');
  }

  function renderEffectiveness(data) {
    var el = document.getElementById('effectiveness-table-container');
    if (!el) return;
    var rules = data && data.rules ? data.rules : [];
    if (!rules.length) { el.innerHTML = '<span class="muted">No data.</span>'; return; }
    var rows = rules.map(function(r) {
      var score = Math.round((r.effectiveness_score || 0) * 100);
      var verdict = r.verdict || 'neutral';
      return '<tr><td>' + escHtml(r.rule_title || r.proposal_id) + '</td>' +
        '<td>' + score + '%</td>' +
        '<td class="verdict-' + verdict + '">' + verdict + '</td></tr>';
    }).join('');
    el.innerHTML = '<table><thead><tr><th>Rule</th><th>Score</th><th>Verdict</th></tr></thead><tbody>' + rows + '</tbody></table>';
  }

  // --- Utility ---

  function escHtml(str) {
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

})();
