(function () {
  "use strict";

  var COLORS = { upper: "#bd554f", mean: "#56616f", lower: "#4f9165" };
  var DEFAULT_LABELS = {
    upper: "Upper trend",
    mean: "Mean trend",
    lower: "Lower trend"
  };
  var STORAGE_KEY = "mean-reversion-readout-layout-v1";

  function formatProbability(value, day, lastDate) {
    if (day && lastDate && day <= lastDate) return "Historical date — not a forecast";
    if (value === null || value === undefined || value === "") return "Not available";
    if (typeof value === "string") return value;
    var number = Number(value);
    if (!Number.isFinite(number)) return "Not available";
    if (number > 0 && number < 0.001) return "<0.1%";
    if (number < 1 && number > 0.999) return ">99.9%";
    return (number * 100).toFixed(1) + "%";
  }

  function formatPrice(value) {
    if (value === null || value === undefined || value === "") return "Not available";
    if (typeof value === "string" && value.trim()) {
      return value.charAt(0) === "$" ? value : value;
    }
    var number = Number(value);
    return Number.isFinite(number)
      ? "$" + number.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      : "Not available";
  }

  function bandRowsFromPoint(point, lastDate) {
    var custom = point && point.customdata;
    if (!Array.isArray(custom) || custom.length < 7) return null;
    var day = String(custom[0] || "");
    return [
      { kind: "upper", label: DEFAULT_LABELS.upper, target_price: custom[1],
        hit_probability: custom[2], date: day, probability_text: formatProbability(custom[2], day, lastDate) },
      { kind: "mean", label: DEFAULT_LABELS.mean, target_price: custom[3],
        hit_probability: custom[4], date: day, probability_text: formatProbability(custom[4], day, lastDate) },
      { kind: "lower", label: DEFAULT_LABELS.lower, target_price: custom[5],
        hit_probability: custom[6], date: day, probability_text: formatProbability(custom[6], day, lastDate) }
    ];
  }

  function normalizeKind(kind) {
    var value = String(kind || "").toLowerCase();
    if (value === "median" || value === "center" || value === "centre") return "mean";
    return value;
  }

  function panelDimensions(width, height, expanded) {
    var w = Math.max(180, Number(width) || 380);
    var h = Math.max(110, Number(height) || 330);
    if (expanded) {
      w = Math.max(w, 480);
      h = Math.max(h, 390);
    }
    return { width: w, height: h };
  }

  function clampPanelPosition(x, y, width, height, bounds) {
    var maxX = Math.max(0, Number(bounds && bounds.width) - Number(width));
    var maxY = Math.max(0, Number(bounds && bounds.height) - Number(height));
    return {
      x: Math.max(0, Math.min(maxX, Number(x) || 0)),
      y: Math.max(0, Math.min(maxY, Number(y) || 0))
    };
  }

  function clampPanelGeometry(x, y, width, height, bounds) {
    var boundWidth = Math.max(1, Number(bounds && bounds.width) || 1);
    var boundHeight = Math.max(1, Number(bounds && bounds.height) || 1);
    var w = Math.max(Math.min(180, boundWidth), Math.min(boundWidth, Number(width) || 380));
    var h = Math.max(Math.min(110, boundHeight), Math.min(boundHeight, Number(height) || 330));
    var nextX = Number(x) || 0;
    var nextY = Number(y) || 0;
    // Preserve the far edge while growing a panel already near the right/bottom boundary.
    if (nextX + w > boundWidth) nextX = Math.max(0, boundWidth - w);
    if (nextY + h > boundHeight) nextY = Math.max(0, boundHeight - h);
    var position = clampPanelPosition(nextX, nextY, w, h, {
      width: boundWidth,
      height: boundHeight
    });
    return { x: position.x, y: position.y, width: w, height: h };
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = {
      formatProbability: formatProbability,
      formatPrice: formatPrice,
      bandRowsFromPoint: bandRowsFromPoint,
      panelDimensions: panelDimensions,
      clampPanelPosition: clampPanelPosition,
      clampPanelGeometry: clampPanelGeometry
    };
  }
  if (typeof window === "undefined" || typeof document === "undefined") return;

  var workspace = document.getElementById("workspace");
  var stage = document.getElementById("plot-stage");
  var chart = document.getElementById("chart");
  var panel = document.getElementById("readout");
  var mobilePanel = document.getElementById("mobile-readout");
  var currentRows = document.getElementById("band-rows");
  var symbolNode = document.getElementById("panel-symbol");
  var dateNode = document.getElementById("panel-date");
  var runtimeError = document.getElementById("runtime-error");
  var collapseButton = document.getElementById("collapse-button");
  var expandButton = document.getElementById("expand-button");
  var pinButton = document.getElementById("pin-button");
  var returnButton = document.getElementById("return-button");
  var dockButton = document.getElementById("dock-button");
  var smallerButton = document.getElementById("smaller-button");
  var largerButton = document.getElementById("larger-button");
  var dragHandle = document.getElementById("drag-handle");
  var resizeHandle = document.getElementById("resize-handle");

  var latestArgs = null;
  var initialRows = [];
  var pinned = false;
  var expanded = false;
  var collapsed = false;
  var floating = false;
  var manualSize = false;
  var activeDate = "";
  var identityKey = "";
  var panelPosition = { x: 16, y: 24 };
  var lastDate = "";
  var chartHeight = 520;
  var resizeObserver = null;
  var savedNormalSize = null;
  var storage = null;

  function post(type, extra) {
    var message = Object.assign({ isStreamlitMessage: true, type: type }, extra || {});
    window.parent.postMessage(message, "*");
  }

  function readStorage() {
    try {
      storage = window.sessionStorage;
      if (!storage) return null;
      var raw = storage.getItem(STORAGE_KEY);
      if (!raw) return null;
      var value = JSON.parse(raw);
      return value && typeof value === "object" ? value : null;
    } catch (error) {
      storage = null;
      return null;
    }
  }

  function saveLayout() {
    if (!storage) return;
    try {
      var rect = panel.getBoundingClientRect();
      var data = {
        floating: floating,
        manualSize: manualSize,
        x: panelPosition.x,
        y: panelPosition.y,
        width: Math.round(rect.width || panel.offsetWidth || 420),
        height: Math.round(parseFloat(panel.style.height) || rect.height || panel.offsetHeight || 380),
        expanded: expanded,
        collapsed: collapsed,
        normalWidth: savedNormalSize && savedNormalSize.width,
        normalHeight: savedNormalSize && savedNormalSize.height,
        dockWidth: panel.style.width || ""
      };
      storage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch (error) {
      // Storage may be disabled or full; the component remains fully usable for this visit.
    }
  }

  var persisted = readStorage();
  if (persisted) {
    floating = Boolean(persisted.floating);
    manualSize = Boolean(persisted.manualSize);
    panelPosition = {
      x: Number.isFinite(Number(persisted.x)) ? Number(persisted.x) : 16,
      y: Number.isFinite(Number(persisted.y)) ? Number(persisted.y) : 24
    };
    expanded = Boolean(persisted.expanded);
    collapsed = Boolean(persisted.collapsed);
    if (Number(persisted.normalWidth) > 0 && Number(persisted.normalHeight) > 0) {
      savedNormalSize = {
        width: Number(persisted.normalWidth),
        height: Number(persisted.normalHeight)
      };
    }
    if (manualSize || floating || expanded) {
      if (persisted.dockWidth) panel.style.width = String(persisted.dockWidth);
      if (Number(persisted.width) > 0) panel.style.width = Math.round(Number(persisted.width)) + "px";
      if (Number(persisted.height) > 0) panel.style.height = Math.round(Number(persisted.height)) + "px";
    }
  }

  function setFrameHeight() {
    var mobile = window.matchMedia("(max-width: 720px)").matches;
    var legacyTotal = mobile
      ? chartHeight + (mobilePanel.offsetHeight || 0) + 20
      : Math.max(Number(latestArgs && latestArgs.readout_height) || 640,
          chartHeight + 24, expanded && !collapsed ? 824 : 0);
    // Use the real docked panel size when the browser exposes layout metrics. This keeps
    // the docked readout reachable in Streamlit while remaining safe in non-layout hosts.
    var hasLayoutMetric = typeof panel.scrollHeight === "number" && panel.scrollHeight > 0;
    var dockedTotal = hasLayoutMetric && !floating && !panel.hidden
      ? chartHeight + (panel.offsetHeight || 0) + 24
      : 0;
    post("streamlit:setFrameHeight", { height: Math.ceil(Math.max(legacyTotal, dockedTotal)) });
  }

  function safeColor(kind, candidate) {
    if (COLORS[kind]) return COLORS[kind];
    return /^#[0-9a-f]{3,8}$/i.test(String(candidate || "")) ? candidate : COLORS.mean;
  }

  function normalizedRows(rows, day) {
    var source = Array.isArray(rows) ? rows : [];
    var order = ["upper", "mean", "lower"];
    return order.map(function (kind) {
      var row = source.find(function (item) { return item && normalizeKind(item.kind) === kind; });
      if (!row) {
        return { kind: kind, label: DEFAULT_LABELS[kind], target_price: null,
          hit_probability: null, date: day };
      }
      return Object.assign({}, row, {
        kind: kind,
        label: row.label || DEFAULT_LABELS[kind],
        date: row.date || day
      });
    });
  }

  function makeElement(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = String(text);
    return node;
  }

  function renderRows(rows, day) {
    currentRows.replaceChildren();
    normalizedRows(rows, day).forEach(function (row) {
      var section = makeElement("section", "band-row");
      section.dataset.kind = row.kind;
      section.style.setProperty("--band-color", safeColor(row.kind, row.color));
      var label = makeElement("span", "band-label", row.label);
      var price = makeElement("strong", "band-price", "Price: " + formatPrice(row.target_price));
      var probabilityText = row.probability_text !== undefined
        ? row.probability_text
        : formatProbability(row.hit_probability, row.date || day, lastDate);
      var probability = makeElement("span", "band-probability", "Probability: " + probabilityText);
      probability.title = "Probability of hitting this price by or before the displayed date";
      section.append(label, price, probability);
      currentRows.appendChild(section);
    });
    setFrameHeight();
  }

  function setDateText(day, source) {
    activeDate = String(day || "");
    var prefix = source === "hover" ? "Hovered date" :
      source === "pinned" ? "Pinned date" : "Selected date";
    dateNode.textContent = activeDate ? prefix + ": " + activeDate : prefix + " unavailable";
  }

  function setPinned(value) {
    pinned = Boolean(value);
    pinButton.textContent = pinned ? "Unpin" : "Pin";
    pinButton.setAttribute("aria-pressed", String(pinned));
  }

  function showPoint(point, pin) {
    if (!latestArgs || !point) return;
    var rows = bandRowsFromPoint(point, lastDate);
    if (!rows) return;
    var day = String(point.customdata[0] || "");
    if (pin) setPinned(true);
    if (pinned && !pin) return;
    setDateText(day, pinned ? "pinned" : "hover");
    renderRows(rows, day);
  }

  function returnToSelected() {
    if (!latestArgs) return;
    setPinned(false);
    var day = String(latestArgs.selected_date || "");
    setDateText(day, "selected");
    renderRows(initialRows, day);
  }

  function stageBounds() {
    return {
      width: Math.max(1, stage.clientWidth || stage.getBoundingClientRect().width || 1),
      height: Math.max(1, stage.clientHeight || chartHeight || 1)
    };
  }

  function positionPanel() {
    if (!floating) return;
    var bounds = stageBounds();
    var width = panel.offsetWidth || 420;
    var height = panel.offsetHeight || 380;
    var geometry = clampPanelGeometry(panelPosition.x, panelPosition.y, width, height, bounds);
    panelPosition = { x: geometry.x, y: geometry.y };
    panel.style.width = geometry.width + "px";
    if (!collapsed) panel.style.height = geometry.height + "px";
    panel.style.left = geometry.x + "px";
    panel.style.top = geometry.y + "px";
    panel.style.right = "auto";
  }

  function mountPanel() {
    if (floating) {
      if (panel.parentElement !== stage) stage.appendChild(panel);
      panel.classList.toggle("is-floating", true);
      panel.classList.toggle("is-docked", false);
      panel.style.width = panel.style.width || "420px";
      panel.style.height = panel.style.height || "380px";
      positionPanel();
    } else {
      if (panel.parentElement !== workspace) workspace.appendChild(panel);
      panel.classList.toggle("is-floating", false);
      panel.classList.toggle("is-docked", true);
      panel.style.left = "";
      panel.style.top = "";
      panel.style.right = "";
      panel.style.height = !manualSize && !expanded ? "auto" : panel.style.height || "auto";
      panel.style.maxHeight = "";
      panel.style.width = panel.style.width || "";
    }
    dockButton.textContent = floating ? "Dock below chart" : "Float over chart";
    dockButton.setAttribute("aria-pressed", String(floating));
  }

  function applyVisualState() {
    stage.style.minHeight = chartHeight + "px";
    [panel, mobilePanel].forEach(function (node) {
      node.classList.toggle("is-expanded", expanded);
      node.classList.toggle("is-collapsed", collapsed);
    });
    expandButton.textContent = expanded ? "Restore" : "Expand";
    expandButton.setAttribute("aria-pressed", String(expanded));
    collapseButton.textContent = collapsed ? "Show readout" : "Collapse";
    collapseButton.setAttribute("aria-expanded", String(!collapsed));
    mountPanel();
    positionPanel();
    saveLayout();
    setFrameHeight();
  }

  function setupChartEvents() {
    if (chart.__meanReversionEventsReady) return;
    chart.__meanReversionEventsReady = true;
    chart.on("plotly_hover", function (event) {
      if (!event || !event.points || !event.points.length) return;
      var point = event.points[0];
      if (point && point.customdata && Array.isArray(point.customdata) && point.customdata.length >= 7) {
        showPoint(point, false);
      }
    });
    chart.on("plotly_click", function (event) {
      if (!event || !event.points || !event.points.length) return;
      var point = event.points[0];
      if (point && point.customdata && Array.isArray(point.customdata) && point.customdata.length >= 7) {
        showPoint(point, true);
      }
    });
  }

  function renderPlot(args) {
    if (!window.Plotly) {
      if (window.__plotlyLoadFailed) runtimeError.hidden = false;
      return;
    }
    var figure = args.figure || {};
    var data = Array.isArray(figure.data) ? figure.data : [];
    var layout = Object.assign({}, figure.layout || {});
    chartHeight = Math.max(520, Number(args.readout_height) || 640, Number(layout.height) || 520);
    layout.height = chartHeight;
    chart.style.height = chartHeight + "px";
    chart.style.minHeight = chartHeight + "px";
    var config = Object.assign({}, figure.config || {}, args.config || {});
    if (config.displaylogo === undefined) config.displaylogo = false;
    if (config.scrollZoom === undefined) config.scrollZoom = true;
    // The parent supplies an immutable figure; only its own band hover settings are used.
    window.Plotly.react(chart, data, layout, config).then(function () {
      runtimeError.hidden = true;
      setupChartEvents();
      setFrameHeight();
    }).catch(function () {
      runtimeError.hidden = false;
    });
  }

  function receiveRender(args) {
    args = args || {};
    var nextSymbol = String(args.symbol || "");
    var nextDate = String(args.selected_date || "");
    var nextIdentity = nextSymbol + "\u0000" + nextDate;
    var changed = identityKey !== nextIdentity;
    latestArgs = args;
    lastDate = String(args.last_date || "");
    initialRows = normalizedRows(args.rows, nextDate);
    var hasBands = Boolean(nextSymbol && Array.isArray(args.rows) && args.rows.length);
    panel.hidden = !hasBands;
    mobilePanel.hidden = true;
    symbolNode.textContent = nextSymbol || "Stock";
    if (changed || (!pinned && activeDate === nextDate)) {
      identityKey = nextIdentity;
      setPinned(false);
      setDateText(nextDate, "selected");
      renderRows(initialRows, nextDate);
    }
    applyVisualState();
    renderPlot(args);
  }

  function currentPanelSize() {
    var rect = panel.getBoundingClientRect();
    return {
      width: Math.max(180, rect.width || panel.offsetWidth || 420),
      height: Math.max(110, rect.height || panel.offsetHeight || 380)
    };
  }

  function setFloating(nextFloating) {
    var rect = panel.getBoundingClientRect();
    if (nextFloating && !floating) {
      var stageRect = stage.getBoundingClientRect();
      panelPosition = {
        x: Math.max(0, rect.left - stageRect.left),
        y: Math.max(0, rect.top - stageRect.top)
      };
      panel.style.width = Math.min(420, stageBounds().width) + "px";
      panel.style.height = Math.min(380, stageBounds().height) + "px";
    }
    floating = Boolean(nextFloating);
    if (!floating) {
      manualSize = false;
      panelPosition = { x: 0, y: 0 };
      panel.style.left = "";
      panel.style.top = "";
      panel.style.right = "";
      panel.style.height = "auto";
      panel.style.width = "";
    }
    applyVisualState();
  }

  function resizePanel(width, height, x, y) {
    if (collapsed) return;
    manualSize = true;
    var bounds = stageBounds();
    var size = panelDimensions(width, height, false);
    if (floating) {
      var old = panelPosition || { x: 0, y: 0 };
      var geometry = clampPanelGeometry(
        x === undefined ? old.x : x,
        y === undefined ? old.y : y,
        size.width,
        size.height,
        bounds
      );
      panelPosition = { x: geometry.x, y: geometry.y };
      panel.style.width = geometry.width + "px";
      panel.style.height = geometry.height + "px";
      positionPanel();
    } else {
      var maxWidth = Math.max(180, bounds.width);
      panel.style.width = Math.min(maxWidth, size.width) + "px";
      panel.style.height = Math.min(Math.max(110, bounds.height), size.height) + "px";
    }
    // Resizing may wrap the controls onto additional rows. Keep every action
    // reachable, and scroll the price rows instead of clipping the toolbar.
    var controls = document.getElementById("panel-actions");
    var minimumHeight = (dragHandle.offsetHeight || 64) + (controls.offsetHeight || 80) + 48;
    if (parseFloat(panel.style.height) < minimumHeight) {
      panel.style.height = minimumHeight + "px";
      if (floating) positionPanel();
    }
    saveLayout();
    setFrameHeight();
  }

  function startDrag(event) {
    if (!floating || event.button !== 0) return;
    if (event.target && event.target.closest && event.target.closest("button")) return;
    event.preventDefault();
    var bounds = panel.getBoundingClientRect();
    var stageRect = stage.getBoundingClientRect();
    var originX = event.clientX;
    var originY = event.clientY;
    var startX = bounds.left - stageRect.left;
    var startY = bounds.top - stageRect.top;
    var pointerId = event.pointerId;
    if (dragHandle.setPointerCapture && pointerId !== undefined) {
      try { dragHandle.setPointerCapture(pointerId); } catch (error) { /* Optional host support. */ }
    }
    function move(moveEvent) {
      if (moveEvent.pointerId !== undefined && pointerId !== undefined && moveEvent.pointerId !== pointerId) return;
      var geometry = clampPanelGeometry(
        startX + moveEvent.clientX - originX,
        startY + moveEvent.clientY - originY,
        panel.offsetWidth || bounds.width,
        panel.offsetHeight || bounds.height,
        stageBounds()
      );
      panelPosition = { x: geometry.x, y: geometry.y };
      panel.style.left = geometry.x + "px";
      panel.style.top = geometry.y + "px";
    }
    function stop(stopEvent) {
      if (stopEvent && stopEvent.pointerId !== undefined && pointerId !== undefined && stopEvent.pointerId !== pointerId) return;
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
      window.removeEventListener("pointercancel", stop);
      if (dragHandle.releasePointerCapture && pointerId !== undefined) {
        try { dragHandle.releasePointerCapture(pointerId); } catch (error) { /* Capture may already be lost. */ }
      }
      saveLayout();
    }
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
    window.addEventListener("pointercancel", stop);
  }

  function startResize(event) {
    if (collapsed || event.button !== 0) return;
    event.preventDefault();
    var size = currentPanelSize();
    var startX = event.clientX;
    var startY = event.clientY;
    var origin = panelPosition || { x: 0, y: 0 };
    var pointerId = event.pointerId;
    if (resizeHandle.setPointerCapture && pointerId !== undefined) {
      try { resizeHandle.setPointerCapture(pointerId); } catch (error) { /* Optional host support. */ }
    }
    function move(moveEvent) {
      if (moveEvent.pointerId !== undefined && pointerId !== undefined && moveEvent.pointerId !== pointerId) return;
      resizePanel(
        size.width + moveEvent.clientX - startX,
        size.height + moveEvent.clientY - startY,
        origin.x,
        origin.y
      );
    }
    function stop(stopEvent) {
      if (stopEvent && stopEvent.pointerId !== undefined && pointerId !== undefined && stopEvent.pointerId !== pointerId) return;
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
      window.removeEventListener("pointercancel", stop);
      if (resizeHandle.releasePointerCapture && pointerId !== undefined) {
        try { resizeHandle.releasePointerCapture(pointerId); } catch (error) { /* Capture may already be lost. */ }
      }
      saveLayout();
    }
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
    window.addEventListener("pointercancel", stop);
  }

  dragHandle.addEventListener("pointerdown", startDrag);
  pinButton.addEventListener("click", function () { setPinned(!pinned); });
  returnButton.addEventListener("click", returnToSelected);
  dockButton.addEventListener("click", function () { setFloating(!floating); });
  expandButton.addEventListener("click", function () {
    if (expanded) {
      expanded = false;
      if (savedNormalSize) {
        panel.style.width = savedNormalSize.width + "px";
        panel.style.height = savedNormalSize.height + "px";
      }
      savedNormalSize = null;
    } else {
      var current = currentPanelSize();
      savedNormalSize = { width: current.width, height: current.height };
      expanded = true;
      resizePanel(Math.max(480, current.width), Math.max(560, current.height));
    }
    if (expanded && collapsed) collapsed = false;
    applyVisualState();
  });
  collapseButton.addEventListener("click", function () {
    collapsed = !collapsed;
    if (!collapsed) expanded = false;
    applyVisualState();
  });
  smallerButton.addEventListener("click", function () {
    var size = currentPanelSize();
    resizePanel(size.width - 48, size.height - 42);
  });
  largerButton.addEventListener("click", function () {
    var size = currentPanelSize();
    resizePanel(size.width + 48, size.height + 42);
  });
  resizeHandle.addEventListener("pointerdown", startResize);
  resizeHandle.addEventListener("keydown", function (event) {
    var horizontal = { ArrowLeft: -20, ArrowRight: 20 }[event.key] || 0;
    var vertical = { ArrowUp: -20, ArrowDown: 20 }[event.key] || 0;
    if (!horizontal && !vertical) return;
    event.preventDefault();
    resizePanel(currentPanelSize().width + horizontal, currentPanelSize().height + vertical);
  });

  window.addEventListener("resize", function () {
    positionPanel();
    setFrameHeight();
    saveLayout();
  });
  window.addEventListener("message", function (event) {
    var message = event.data;
    if (!message || message.type !== "streamlit:render") return;
    receiveRender(message.args || {});
  });

  if (window.__plotlyLoadFailed) runtimeError.hidden = false;
  post("streamlit:componentReady", { apiVersion: 1 });
  post("streamlit:setFrameHeight", { height: 640 });

  if (typeof ResizeObserver !== "undefined") {
    resizeObserver = new ResizeObserver(function () {
      if (floating) positionPanel();
      setFrameHeight();
    });
    resizeObserver.observe(stage);
  }
})();
