function renderScorecard(model) {
  var source = model && model.scores ? model.scores : {};
  function scoreText(value) {
    return Number.isInteger(value) && value >= 0 && value <= 100 ? String(value) : "Unavailable";
  }
  function sentenceText(value) {
    return typeof value === "string" && value.trim() ? value : "Unavailable";
  }
  var reversion = document.getElementById("mr-reversion-score");
  var growth = document.getElementById("mr-growth-score");
  var overall = document.getElementById("mr-overall-score");
  var grade = document.getElementById("mr-reversion-grade");
  var growthSentence = document.getElementById("mr-growth-sentence");
  var positionSentence = document.getElementById("mr-position-sentence");
  var cycleSentence = document.getElementById("mr-cycle-sentence");
  var warning = document.getElementById("mr-random-walk-warning");
  if (reversion) reversion.textContent = scoreText(source.mean_reversion);
  if (growth) growth.textContent = scoreText(source.growth);
  if (overall) overall.textContent = scoreText(source.overall);
  if (grade) grade.textContent = model && model.random_walk ? "Random walk" :
    (model && ["Strong", "Moderate", "Weak"].includes(model.grade) ? model.grade : "Unavailable");
  if (growthSentence) growthSentence.textContent = sentenceText(model && model.trend_sentence);
  if (positionSentence) positionSentence.textContent = sentenceText(model && model.position_sentence);
  if (cycleSentence) cycleSentence.textContent = sentenceText(model && model.cycle_sentence);
  if (warning) warning.hidden = !(model && model.random_walk);
  var note = document.getElementById("mr-score-note");
  if (note) {
    note.textContent = model && model.score_note ? model.score_note : "";
    note.hidden = !note.textContent;
  }
}

(function () {
  "use strict";

  var chart = document.getElementById("chart");
  var chartContainer = document.getElementById("chart-container");
  var chartScroll = document.getElementById("chart-scroll");
  var status = document.getElementById("status");
  var statusMessage = document.getElementById("status-message");
  var errorPanel = document.getElementById("error-panel");
  var errorMessage = document.getElementById("error-message");
  var title = document.getElementById("chart-title");
  var emptyState = document.getElementById("empty-state");
  var caption = document.getElementById("chart-caption");
  var tooltip = document.getElementById("projection-tooltip");
  var heightSlider = document.getElementById("height-slider");
  var heightValue = document.getElementById("height-value");
  var widthSlider = document.getElementById("width-slider");
  var widthValue = document.getElementById("width-value");
  var resizeGrip = document.getElementById("resize-grip");
  var payload = null;
  var currentHeight = 680;
  var chartWidth = 100;
  var lastError = "";
  var resizeState = null;

  var COLORS = {
    price: "#2196F3",
    trend: "#59636a",
    upper: "#bd5b54",
    lower: "#348575",
    distance: "#557d77",
    grid: "#e8edef",
    text: "#69777d",
    overlay: "#80969c"
  };

  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (character) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[character];
    });
  }

  function validDate(value) {
    var date = new Date(value);
    return Number.isFinite(date.getTime()) ? date : null;
  }

  function isoDay(value) {
    var date = validDate(value);
    return date ? date.toISOString().slice(0, 10) : null;
  }

  function cleanSeries(dates, values) {
    if (!Array.isArray(dates) || !Array.isArray(values)) return { dates: [], values: [] };
    var resultDates = [];
    var resultValues = [];
    var count = Math.min(dates.length, values.length);
    for (var i = 0; i < count; i += 1) {
      var date = isoDay(dates[i]);
      var value = Number(values[i]);
      if (date && Number.isFinite(value)) {
        resultDates.push(date);
        resultValues.push(value);
      }
    }
    return { dates: resultDates, values: resultValues };
  }

  function setStatus(message, state) {
    statusMessage.textContent = message;
    status.className = "status " + state;
  }

  function reportError(error) {
    lastError = error && error.message ? error.message : "The chart data could not be interpreted.";
    errorMessage.textContent = lastError;
    errorPanel.hidden = false;
    emptyState.hidden = false;
    tooltip.classList.remove("visible");
    setStatus("Chart unavailable", "warning");
    if (window.Streamlit) window.Streamlit.setFrameHeight(currentHeight + 250);
  }

  function sendFrameHeight() {
    var height = Math.max(350, Math.min(1400, currentHeight));
    document.getElementById("chart").style.height = height + "px";
    chart.style.minHeight = height + "px";
    if (window.Streamlit) {
      window.Streamlit.setFrameHeight(Math.ceil(
        document.querySelector("main").getBoundingClientRect().height + 12
      ));
    }
  }

  function dateRangeEnd(model, selectedEnd) {
    var allDates = model && Array.isArray(model.dates) ? model.dates : [];
    if (!allDates.length) return null;
    var latest = allDates[allDates.length - 1];
    return selectedEnd && selectedEnd < latest ? selectedEnd : latest;
  }

  function selectedForecast(model) {
    if (!model || !Array.isArray(model.dates)) return { dates: [], trend: [], upper: [], lower: [], indices: [] };
    var end = dateRangeEnd(model);
    var sourceProbabilities = model.probabilities || {};
    var result = { dates: [], trend: [], upper: [], lower: [], indices: [], probabilities: { upper: [], trend: [], lower: [] } };
    for (var i = 0; i < model.dates.length; i += 1) {
      var day = isoDay(model.dates[i]);
      if (!day || (end && day > end)) continue;
      result.dates.push(day);
      result.trend.push(Number(model.trend && model.trend[i]));
      result.upper.push(Number(model.upper && model.upper[i]));
      result.lower.push(Number(model.lower && model.lower[i]));
      result.indices.push(i);
      result.probabilities.upper.push(Number(sourceProbabilities.upper && sourceProbabilities.upper[i]));
      result.probabilities.trend.push(Number(sourceProbabilities.trend && sourceProbabilities.trend[i]));
      result.probabilities.lower.push(Number(sourceProbabilities.lower && sourceProbabilities.lower[i]));
    }
    return result;
  }

  function lineTrace(name, x, y, color, options) {
    options = options || {};
    return {
      type: "scatter",
      mode: options.mode || "lines",
      x: x,
      y: y,
      xaxis: "x",
      yaxis: "y",
      name: name,
      line: { color: color, width: options.width || 1.7, dash: options.dash || "solid" },
      hovertemplate: options.hovertemplate || "%{x|%b %d, %Y}<br>" + escapeHtml(name) + ": %{y:$,.2f}<extra></extra>",
      connectgaps: false,
      ...(options.fill ? { fill: options.fill, fillcolor: options.fillcolor } : {}),
      ...(options.marker ? { marker: options.marker } : {}),
      ...(options.customdata ? { customdata: options.customdata } : {})
    };
  }

  function safeColor(value) {
    var candidate = String(value || "");
    return /^(#[0-9a-f]{3,8}|rgb[a]?\([\d\s.,%]+\)|hsl[a]?\([\d\s.,%deg]+\))$/i.test(candidate)
      ? candidate
      : COLORS.overlay;
  }

  function overlayTrace(overlay, baseDates, basePrices) {
    if (!overlay || !Array.isArray(overlay.dates) || !Array.isArray(overlay.prices)) return null;
    var byDate = Object.create(null);
    var cleaned = cleanSeries(overlay.dates, overlay.prices);
    for (var i = 0; i < cleaned.dates.length; i += 1) byDate[cleaned.dates[i]] = cleaned.values[i];
    var commonIndex = -1;
    var scale = 1;
    for (var j = 0; j < baseDates.length; j += 1) {
      var date = isoDay(baseDates[j]);
      var comparisonPrice = byDate[date];
      var targetPrice = Number(basePrices[j]);
      if (comparisonPrice > 0 && targetPrice > 0 && Number.isFinite(targetPrice)) {
        commonIndex = j;
        scale = targetPrice / comparisonPrice;
        break;
      }
    }
    if (commonIndex < 0) return null;
    var dates = [];
    var normalized = [];
    var actual = [];
    for (var k = 0; k < cleaned.dates.length; k += 1) {
      var itemDate = cleaned.dates[k];
      var itemPrice = cleaned.values[k];
      if (itemDate < isoDay(baseDates[commonIndex]) || itemPrice <= 0) continue;
      dates.push(itemDate);
      normalized.push(itemPrice * scale);
      actual.push(itemPrice);
    }
    var symbol = String(overlay.symbol || "Comparison");
    var scores = overlay.scores;
    var legendName = escapeHtml(symbol) + " (scaled)";
    if (scores && Number.isInteger(scores.overall) && scores.overall >= 0 && scores.overall <= 100 &&
        Number.isInteger(scores.mean_reversion) && scores.mean_reversion >= 0 && scores.mean_reversion <= 100 &&
        Number.isInteger(scores.growth) && scores.growth >= 0 && scores.growth <= 100) {
      legendName = escapeHtml(symbol) + " — Overall " + scores.overall +
        " · Reversion " + scores.mean_reversion + " · Growth " + scores.growth + " (scaled)";
    }
    return {
      type: "scatter",
      mode: "lines",
      x: dates,
      y: normalized,
      xaxis: "x",
      yaxis: "y",
      name: legendName,
      legendgroup: "overlays",
      line: { color: safeColor(overlay.color), width: 1.35, dash: "dot" },
      customdata: actual,
      hovertemplate: "%{x|%b %d, %Y}<br>" + escapeHtml(symbol) + " actual: %{customdata:$,.2f}<extra></extra>"
    };
  }

  function makeTraces(data) {
    var traces = [];
    var historical = cleanSeries(data.dates, data.prices);
    var validPriceDates = [];
    var validPrices = [];
    for (var i = 0; i < historical.dates.length; i += 1) {
      if (historical.values[i] > 0) {
        validPriceDates.push(historical.dates[i]);
        validPrices.push(historical.values[i]);
      }
    }
    if (!validPriceDates.length) throw new Error("No valid positive adjusted-close prices were supplied.");
    var priceName = String(data.symbol || "Price") + " adjusted close";
    traces.push(lineTrace(priceName, validPriceDates, validPrices, COLORS.price, {
      width: 2.15,
      hovertemplate: "%{x|%b %d, %Y}<br>" + escapeHtml(priceName) + ": %{y:$,.2f}<extra></extra>"
    }));

    var historicalModel = data.historical_trend;
    var modelVisible = !!historicalModel;
    if (historicalModel) {
      var ht = cleanSeries(historicalModel.dates, historicalModel.trend);
      var hu = cleanSeries(historicalModel.dates, historicalModel.upper);
      var hl = cleanSeries(historicalModel.dates, historicalModel.lower);
      if (ht.dates.length) traces.push(lineTrace("Historical trend", ht.dates, ht.values, COLORS.trend, { width: 1.5 }));
      if (hu.dates.length && hl.dates.length) {
        traces.push(lineTrace("Historical upper band", hu.dates, hu.values, COLORS.upper, {
          width: 1, hovertemplate: "%{x|%b %d, %Y}<br>Upper band: %{y:$,.2f}<extra></extra>"
        }));
        traces.push(lineTrace("Historical lower band", hl.dates, hl.values, COLORS.lower, {
          width: 1, fill: "tonexty", fillcolor: "rgba(91, 132, 124, .10)",
          hovertemplate: "%{x|%b %d, %Y}<br>Lower band: %{y:$,.2f}<extra></extra>"
        }));
      }
    }

    var forecast = selectedForecast(data.forecast);
    if (forecast && forecast.dates.length) {
      traces.push(lineTrace("Upper", forecast.dates, forecast.upper, COLORS.upper, {
        width: 1.65, hovertemplate: "%{x|%b %d, %Y}<br>Upper: %{y:$,.2f}<extra></extra>"
      }));
      traces.push(lineTrace("Lower", forecast.dates, forecast.lower, COLORS.lower, {
        width: 1.65, fill: "tonexty", fillcolor: "rgba(76, 141, 126, .09)",
        hovertemplate: "%{x|%b %d, %Y}<br>Lower: %{y:$,.2f}<extra></extra>"
      }));
      traces.push(lineTrace("Trend", forecast.dates, forecast.trend, COLORS.trend, {
        width: 1.7, hovertemplate: "%{x|%b %d, %Y}<br>Trend: %{y:$,.2f}<extra></extra>"
      }));
    }

    if (data.verdict && Array.isArray(data.verdict.residuals)) {
      var residuals = cleanSeries(validPriceDates, data.verdict.residuals);
      if (residuals.dates.length) {
        var distance = residuals.values.map(function (residual) { return (Math.exp(residual) - 1) * 100; });
        traces.push({
          type: "scatter", mode: "lines", x: residuals.dates, y: distance,
          xaxis: "x2", yaxis: "y2", name: "Distance from trend",
          line: { color: COLORS.distance, width: 1.25 },
          hovertemplate: "%{x|%b %d, %Y}<br>Distance: %{y:.2f}%<extra></extra>"
        });
      }
      var width = Number(data.verdict.band_width);
      if (Number.isFinite(width) && width >= 0) {
        var threshold = (Math.exp(2 * width) - 1) * 100;
        var lowerThreshold = (Math.exp(-2 * width) - 1) * 100;
        traces.push({
          type: "scatter", mode: "lines", x: validPriceDates, y: validPriceDates.map(function () { return threshold; }),
          xaxis: "x2", yaxis: "y2", name: "+2 band",
          line: { color: "#b9a19c", width: 1, dash: "dash" },
          hovertemplate: "+2 band: %{y:.2f}%<extra></extra>"
        });
        traces.push({
          type: "scatter", mode: "lines", x: validPriceDates, y: validPriceDates.map(function () { return lowerThreshold; }),
          xaxis: "x2", yaxis: "y2", name: "−2 band",
          line: { color: "#9fb8b2", width: 1, dash: "dash" },
          hovertemplate: "−2 band: %{y:.2f}%<extra></extra>"
        });
      }
    }
    // Comparisons remain usable even when the analyzed ticker fails the gate.
    (Array.isArray(data.overlays) ? data.overlays : []).forEach(function (overlay) {
      var trace = overlayTrace(overlay, validPriceDates, validPrices);
      if (trace) traces.push(trace);
    });
    if (validPrices.length) {
      var lastIndex = validPrices.length - 1;
      traces.push({
        type: "scatter", mode: "markers", x: [validPriceDates[lastIndex]], y: [validPrices[lastIndex]],
        xaxis: "x", yaxis: "y", name: "Current close", showlegend: false,
        marker: { color: COLORS.price, size: 8, line: { color: "#ffffff", width: 1.5 } },
        hovertemplate: "%{x|%b %d, %Y}<br>Current close: %{y:$,.2f}<extra></extra>"
      });
    }
    return { traces: traces, prices: validPrices, priceDates: validPriceDates, forecast: forecast, modelVisible: modelVisible };
  }

  function dollarTicks(traces) {
    var low = Infinity;
    var high = -Infinity;
    traces.forEach(function (trace) {
      if (trace.yaxis === "y2") return;
      (trace.y || []).forEach(function (price) {
        if (Number.isFinite(price) && price > 0) {
          low = Math.min(low, price);
          high = Math.max(high, price);
        }
      });
    });
    if (!Number.isFinite(low)) return {tickmode: "auto", tickprefix: "$", dtick: 1};
    var bottom = Math.log10(low);
    var span = Math.max(Math.log10(high) - bottom, .1);
    var values = [];
    var labels = [];
    for (var i = 0; i <= 5; i += 1) {
      var value = Math.pow(10, bottom + span * i / 5);
      values.push(value);
      labels.push("$" + Number(value.toPrecision(2)).toLocaleString("en-US", {maximumSignificantDigits: 2}));
    }
    return {tickmode: "array", tickvals: values, ticktext: labels};
  }

  function getLayout(data, prepared) {
    var dates = prepared.priceDates.slice();
    if (prepared.forecast && prepared.forecast.dates.length) dates = dates.concat(prepared.forecast.dates);
    var annotations = [];
    if (prepared.prices.length) {
      var position = data.verdict && data.verdict.position_text ? String(data.verdict.position_text) : "";
      annotations.push({
        x: prepared.priceDates[prepared.priceDates.length - 1],
        // Plotly annotations on logarithmic axes take log10 coordinates.
        y: Math.log10(prepared.prices[prepared.prices.length - 1]),
        xref: "x", yref: "y",
        text: escapeHtml(position),
        showarrow: true, arrowhead: 0, ax: 34, ay: -27,
        bgcolor: "rgba(255,255,255,.92)", bordercolor: "#d7e0e4", borderpad: 5,
        font: { size: 11, color: "#34434b" }
      });
    }
    return {
      // Layout and navigation follow the existing main chart, scoped here.
      template: "plotly_white",
      autosize: true,
      height: currentHeight,
      margin: { l: 66, r: 24, t: 24, b: 44 },
      paper_bgcolor: "#ffffff",
      plot_bgcolor: "#ffffff",
      font: { family: "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif", size: 11, color: COLORS.text },
      hovermode: "closest",
      dragmode: "pan",
      showlegend: true,
      legend: {
        orientation: "h", x: 0, y: 1.08, xanchor: "left", yanchor: "bottom",
        font: { size: 10, color: "#64727a" }, bgcolor: "rgba(255,255,255,.82)"
      },
      annotations: annotations,
      xaxis: {
        type: "date", domain: [0, 1], anchor: "y",
        showticklabels: !prepared.modelVisible, showgrid: true, gridcolor: COLORS.grid,
        linecolor: "#cbd5d8", rangeslider: { visible: false },
        range: dates.length ? [dates[0], dates[dates.length - 1]] : undefined,
        fixedrange: false
      },
      yaxis: {
        type: "log", domain: prepared.modelVisible ? [.285, 1] : [0, 1], anchor: "x",
        ...dollarTicks(prepared.traces),
        title: { text: "Adjusted close · log scale", font: { size: 10 } },
        showgrid: true, gridcolor: COLORS.grid, zeroline: false,
        linecolor: "#cbd5d8", fixedrange: false, automargin: true
      },
      xaxis2: {
        type: "date", domain: [0, 1], anchor: "y2", matches: "x",
        title: { text: "Date", font: { size: 10 } },
        showgrid: true, gridcolor: COLORS.grid, linecolor: "#cbd5d8",
        fixedrange: false, automargin: true, visible: prepared.modelVisible
      },
      yaxis2: {
        domain: [0, .19], anchor: "x2", visible: prepared.modelVisible,
        title: { text: "Distance from trend (%)", font: { size: 10 } },
        ticksuffix: "%", showgrid: true, gridcolor: COLORS.grid,
        zeroline: true, zerolinecolor: "#9eaaad", zerolinewidth: 1,
        linecolor: "#cbd5d8", fixedrange: false, automargin: true
      }
    };
  }

  function renderRemovalControls() {
    var controls = document.getElementById("remove-controls");
    if (!controls) return;
    controls.replaceChildren();
    var symbols = payload.removable_symbols || [payload.symbol];
    function addButton(label, action, symbol) {
      var button = document.createElement("button");
      button.type = "button";
      button.textContent = label;
      button.addEventListener("click", function () {
        controls.querySelectorAll("button").forEach(function (item) { item.disabled = true; });
        window.parent.postMessage({
          isStreamlitMessage: true, type: "streamlit:setComponentValue", dataType: "json",
          value: {action: action, symbol: symbol || null, nonce: Date.now() + ":" + Math.random()}
        }, "*");
      });
      controls.appendChild(button);
    }
    symbols.forEach(function (symbol) { addButton("Remove " + symbol, "remove", symbol); });
    addButton("Remove last added", "remove", symbols[symbols.length - 1]);
    addButton("Remove all charts", "remove_all");
  }

  function render() {
    renderScorecard(payload && payload.verdict);
    if (!payload) return;
    renderRemovalControls();
    if (!window.Plotly) {
      reportError(new Error("The Plotly chart library did not load. Check the network connection and retry."));
      return;
    }
    try {
      errorPanel.hidden = true;
      title.textContent = (payload.symbol ? String(payload.symbol) + " · " : "") + "Mean Reversion";
      var prepared = makeTraces(payload);
      emptyState.hidden = true;
      caption.hidden = true;
      var statusText = payload.verdict && payload.verdict.status ? String(payload.verdict.status) : "";
      setStatus(statusText || "Historical and projected trend bands shown.",
                payload.verdict && payload.verdict.random_walk ? "warning" : "ready");
      var layout = getLayout(payload, prepared);
      var config = {
        responsive: true, displaylogo: false, scrollZoom: false, doubleClick: false,
        modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d"],
        toImageButtonOptions: { format: "png", filename: "mean-reversion-chart", scale: 1 }
      };
      var operation = chart.data ? Plotly.react(chart, prepared.traces, layout, config) : Plotly.newPlot(chart, prepared.traces, layout, config);
      operation.then(function () {
        bindProjectionPointer(prepared.forecast, payload);
        sendFrameHeight();
      }).catch(reportError);
      if (payload.forecast) {
        var trend = payload.forecast.trend || [];
        var upper = payload.forecast.upper || [];
        var lower = payload.forecast.lower || [];
        if (!trend.length || !upper.length || !lower.length) {
          setStatus(statusText || "Forecast data is incomplete; displaying available price history.", "warning");
        }
      }
    } catch (error) {
      reportError(error);
    }
  }

  function formatPrice(value) {
    if (!Number.isFinite(value)) return "Unavailable";
    return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(value);
  }

  function formatPercent(value) {
    if (!Number.isFinite(value)) return "Unavailable";
    return (value * 100).toFixed(1) + "%";
  }

  function makeTooltipRow(label, value, probability, color) {
    var row = document.createElement("div");
    row.className = "tooltip-row";
    var swatch = document.createElement("span");
    swatch.className = "tooltip-swatch";
    swatch.style.backgroundColor = color;
    var name = document.createElement("span");
    name.className = "tooltip-line-name";
    name.textContent = label;
    var price = document.createElement("span");
    price.className = "tooltip-value";
    price.textContent = formatPrice(value);
    var chance = document.createElement("span");
    chance.className = "tooltip-probability";
    chance.textContent = "Cumulative touch probability: " + formatPercent(probability);
    row.appendChild(swatch);
    row.appendChild(name);
    row.appendChild(price);
    row.appendChild(chance);
    return row;
  }

  function showProjectionTooltip(index, pointerEvent, model) {
    if (!model || index < 0 || index >= model.dates.length) return;
    var probabilities = model.probabilities || {};
    var date = validDate(model.dates[index]);
    if (!date) return;
    tooltip.replaceChildren();
    var dateLabel = document.createElement("strong");
    dateLabel.className = "tooltip-date";
    dateLabel.textContent = new Intl.DateTimeFormat(undefined, { year: "numeric", month: "long", day: "numeric", timeZone: "UTC" }).format(date);
    tooltip.appendChild(dateLabel);
    tooltip.appendChild(makeTooltipRow("Upper", Number(model.upper[index]), Number(probabilities.upper && probabilities.upper[index]), COLORS.upper));
    tooltip.appendChild(makeTooltipRow("Trend", Number(model.trend[index]), Number(probabilities.trend && probabilities.trend[index]), COLORS.trend));
    tooltip.appendChild(makeTooltipRow("Lower", Number(model.lower[index]), Number(probabilities.lower && probabilities.lower[index]), COLORS.lower));
    var footer = document.createElement("div");
    footer.className = "tooltip-footer";
    footer.textContent = "Mean-reversion model estimates.";
    tooltip.appendChild(footer);
    tooltip.classList.add("visible");

    var box = chartContainer.getBoundingClientRect();
    var tipWidth = tooltip.offsetWidth;
    var tipHeight = tooltip.offsetHeight;
    var localX = pointerEvent.clientX - box.left + 14;
    var localY = pointerEvent.clientY - box.top + 14;
    var x = Math.min(Math.max(8, localX), Math.max(8, box.width - tipWidth - 8));
    var y = Math.min(Math.max(8, localY), Math.max(8, box.height - tipHeight - 8));
    tooltip.style.left = x + "px";
    tooltip.style.top = y + "px";
  }

  function bindProjectionPointer(model, data) {
    if (!model || !model.dates || !model.dates.length || !chart._fullLayout) {
      tooltip.classList.remove("visible");
      return;
    }
    var forecastStart = new Date(model.dates[0]).getTime();
    var selectedEnd = new Date(model.dates[model.dates.length - 1]).getTime();
    function onPointerMove(event) {
      var fullLayout = chart._fullLayout;
      var size = fullLayout._size;
      var bounds = chart.getBoundingClientRect();
      var px = event.clientX - bounds.left - size.l;
      var py = event.clientY - bounds.top;
      if (px < 0 || px > size.w || py < size.t || py > size.t + size.h * .70) {
        tooltip.classList.remove("visible");
        return;
      }
      // Use the live axis, not the initial history range: hovering must remain
      // correct after pan, zoom, width resizing, or a changed projection date.
      var pointerTime = new Date(fullLayout.xaxis.p2d(px)).getTime();
      if (pointerTime < forecastStart || pointerTime > selectedEnd) {
        tooltip.classList.remove("visible");
        return;
      }
      var low = 0;
      var high = model.dates.length - 1;
      while (low < high) {
        var mid = Math.floor((low + high) / 2);
        if (new Date(model.dates[mid]).getTime() < pointerTime) low = mid + 1;
        else high = mid;
      }
      var candidate = low;
      if (candidate > 0) {
        var previousDistance = Math.abs(new Date(model.dates[candidate - 1]).getTime() - pointerTime);
        var candidateDistance = Math.abs(new Date(model.dates[candidate]).getTime() - pointerTime);
        if (previousDistance < candidateDistance) candidate -= 1;
      }
      showProjectionTooltip(candidate, event, model);
    }
    if (chart._meanReversionPointerHandler) chart.removeEventListener("pointermove", chart._meanReversionPointerHandler);
    chart._meanReversionPointerHandler = onPointerMove;
    chart.addEventListener("pointermove", onPointerMove);
  }

  function setHeight(value) {
    currentHeight = Math.max(350, Math.min(1400, Number(value) || 680));
    heightSlider.value = String(currentHeight);
    heightValue.value = currentHeight + " px";
    heightValue.textContent = currentHeight + " px";
    resizeGrip.setAttribute("aria-valuenow", String(currentHeight));
    chart.style.height = currentHeight + "px";
    chart.style.minHeight = currentHeight + "px";
    if (window.Plotly && chart.data) Plotly.relayout(chart, { height: currentHeight });
    sendFrameHeight();
  }

  function setWidth(value) {
    chartWidth = Math.max(50, Math.min(200, Number(value) || 100));
    widthSlider.value = String(chartWidth);
    widthValue.value = chartWidth + "%";
    widthValue.textContent = chartWidth + "%";
    chartContainer.style.width = chartWidth + "%";
    chartScroll.scrollLeft = 0;
    if (window.Plotly && chart.data) Plotly.Plots.resize(chart);
    sendFrameHeight();
  }

  heightSlider.addEventListener("input", function () { setHeight(heightSlider.value); });
  widthSlider.addEventListener("input", function () { setWidth(widthSlider.value); });
  chart.addEventListener("pointerleave", function () { tooltip.classList.remove("visible"); });
  document.getElementById("retry-chart").addEventListener("click", function () {
    errorPanel.hidden = true;
    if (payload) render();
    else setStatus("Waiting for chart data…", "loading");
  });

  resizeGrip.addEventListener("pointerdown", function (event) {
    resizeState = { y: event.clientY, height: currentHeight, id: event.pointerId };
    resizeGrip.setPointerCapture(event.pointerId);
    event.preventDefault();
  });
  resizeGrip.addEventListener("pointermove", function (event) {
    if (!resizeState || resizeState.id !== event.pointerId) return;
    setHeight(resizeState.height + event.clientY - resizeState.y);
  });
  function finishResize(event) {
    if (resizeState && resizeState.id === event.pointerId) {
      resizeState = null;
      sendFrameHeight();
    }
  }
  resizeGrip.addEventListener("pointerup", finishResize);
  resizeGrip.addEventListener("pointercancel", finishResize);
  resizeGrip.addEventListener("keydown", function (event) {
    if (event.key === "ArrowUp" || event.key === "ArrowDown") {
      event.preventDefault();
      setHeight(currentHeight + (event.key === "ArrowUp" ? 25 : -25));
    }
  });

  window.addEventListener("resize", function () {
    if (window.Plotly && chart.data) Plotly.Plots.resize(chart);
    sendFrameHeight();
  });

  window.addEventListener("message", function (event) {
    var message = event.data;
    if (!message || message.type !== "streamlit:render") return;
    var args = message.args || {};
    if (!args.payload || typeof args.payload !== "object") {
      payload = null;
      renderScorecard(payload);
      emptyState.hidden = false;
      setStatus("Waiting for chart data…", "loading");
      return;
    }
    payload = args.payload;
    render();
  });

  window.Streamlit = {
    setFrameHeight: function (height) {
      window.parent.postMessage({ isStreamlitMessage: true, type: "streamlit:setFrameHeight", height: height }, "*");
    }
  };
  window.parent.postMessage({ isStreamlitMessage: true, type: "streamlit:componentReady", apiVersion: 1 }, "*");
  sendFrameHeight();
})();
