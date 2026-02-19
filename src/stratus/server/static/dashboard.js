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
        var el = document.getElementById('vexor-status');
        if (!el || !data) return;
        el.textContent = 'Vexor: ' + (data.vexor_available ? 'available' : 'unavailable') +
          '  |  Governance: ' + (data.devrag_available ? 'available' : 'unavailable');
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
      return;
    }
    el.innerHTML = results.map(function(r) {
      var score = r.score !== undefined ? (r.score * 100).toFixed(0) + '%' : '';
      var title = escHtml(r.title || r.file_path || 'Result');
      var pathText = r.file_path || '';
      if (r.line_start) pathText += ':' + r.line_start + (r.line_end ? '-' + r.line_end : '');
      var path = pathText ? '<div class="result-path">' + escHtml(pathText) + '</div>' : '';
      var snippet = escHtml((r.excerpt || r.content || r.snippet || '').substring(0, 200));
      var docType = r.doc_type ? '<span class="tag ' + r.doc_type + '">' + r.doc_type + '</span>' : '';
      return '<div class="result-card">' +
        '<div class="result-header"><span class="result-title">' + title + '</span><span class="result-score">' + score + '</span></div>' +
        path +
        (docType ? '<div style="margin-bottom:0.3rem">' + docType + '</div>' : '') +
        '<div class="result-snippet">' + snippet + '</div>' +
        '</div>';
    }).join('');
  }

  // --- Memory tab ---

  function loadRecentMemory() {
    fetchMemory('');
    document.getElementById('memory-btn').addEventListener('click', function() {
      var q = document.getElementById('memory-query').value.trim();
      fetchMemory(q);
    });
    document.getElementById('memory-query').addEventListener('keydown', function(e) {
      if (e.key === 'Enter') {
        var q = document.getElementById('memory-query').value.trim();
        fetchMemory(q);
      }
    });
  }

  function fetchMemory(query) {
    var url = '/api/search?limit=20&query=' + encodeURIComponent(query);
    fetch(url)
      .then(function(r) { return r.ok ? r.json() : null; })
      .then(function(data) {
        var results = data && data.results ? data.results : [];
        renderMemoryEvents(results);
      })
      .catch(function() {});
  }

  function renderMemoryEvents(events) {
    var el = document.getElementById('memory-results');
    if (!el) return;
    if (!events.length) {
      el.innerHTML = '<span class="muted">No events found.</span>';
      return;
    }
    el.innerHTML = events.map(function(ev) {
      var title = escHtml(ev.title || ev.text.substring(0, 60));
      var text = escHtml(ev.text ? ev.text.substring(0, 120) : '');
      var ts = ev.ts ? new Date(ev.ts).toLocaleString() : '';
      var type = ev.type || 'event';
      var imp = ev.importance !== undefined ? ev.importance : 0.5;
      return '<div class="event-card">' +
        '<div class="event-header">' +
        '<span class="event-title">' + title + ' <span class="tag">' + escHtml(type) + '</span></span>' +
        '<span class="event-time">' + ts + '</span>' +
        '</div>' +
        '<div class="event-text">' + text + '</div>' +
        '<div class="importance-bar"><div class="importance-fill" style="width:' + Math.round(imp * 100) + '%"></div></div>' +
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
        renderChipsList(data.skills || [], 'skills-list');
        renderChipsList(data.rules || [], 'rules-list');
      })
      .catch(function() {});
  }

  function renderAgentsTable(agents) {
    var el = document.getElementById('agents-table-container');
    if (!el) return;
    if (!agents.length) {
      el.innerHTML = '<span class="muted">No agents found.</span>';
      return;
    }
    var rows = agents.map(function(a) {
      var phases = Array.isArray(a.phases) ? a.phases.join(', ') : (a.phases || '');
      var model = a.model ? '<span class="tag">' + escHtml(a.model) + '</span>' : '';
      var layer = a.layer ? '<span class="tag agent">' + escHtml(a.layer) + '</span>' : '';
      var write = a.can_write ? '<span class="tag yes">write</span>' : '<span class="tag no">read-only</span>';
      return '<tr><td><strong>' + escHtml(a.name) + '</strong></td><td>' + model + '</td><td>' + layer + '</td><td>' + escHtml(phases) + '</td><td>' + write + '</td></tr>';
    }).join('');
    el.innerHTML = '<table><thead><tr><th>Name</th><th>Model</th><th>Layer</th><th>Phases</th><th>Write</th></tr></thead><tbody>' + rows + '</tbody></table>';
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
      return '<div class="hotspot-item"><span title="' + escHtml(h.file_path) + '">' + escHtml(shortPath) + '</span><span class="hotspot-count">' + h.failure_count + '</span></div>';
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
