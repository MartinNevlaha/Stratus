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
  startTime = performance.now();
  animFrame = requestAnimationFrame(drawSwarm);
})();
