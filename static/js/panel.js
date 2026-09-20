/* ============ VECTOR admin panel — umumiy skriptlar ============ */
(function () {
  "use strict";

  /* --- Mavzu (yorug'/tungi) --- */
  var root = document.documentElement;

  function applyTheme(theme) {
    root.setAttribute("data-theme", theme);
    try { localStorage.setItem("vector_theme", theme); } catch (e) {}
    document.querySelectorAll("[data-theme-icon]").forEach(function (el) {
      el.textContent = theme === "dark" ? "☀️" : "🌙";
    });
    // Serverda ham eslab qolamiz (cookie orqali)
    document.cookie = "vector_theme=" + theme + ";path=/;max-age=31536000;samesite=lax";
  }

  document.addEventListener("click", function (e) {
    var toggle = e.target.closest("[data-theme-toggle]");
    if (toggle) {
      e.preventDefault();
      applyTheme(root.getAttribute("data-theme") === "dark" ? "light" : "dark");
    }
  });

  /* --- Ochiluvchi menyular --- */
  document.addEventListener("click", function (e) {
    var trigger = e.target.closest("[data-dropdown]");
    document.querySelectorAll(".dropdown.is-open").forEach(function (d) {
      if (!trigger || d !== trigger.closest(".dropdown")) d.classList.remove("is-open");
    });
    if (trigger) {
      e.preventDefault();
      trigger.closest(".dropdown").classList.toggle("is-open");
    }
  });

  /* --- Mobil menyu --- */
  document.addEventListener("click", function (e) {
    if (e.target.closest("[data-burger]")) {
      e.preventDefault();
      document.body.classList.toggle("nav-open");
    } else if (document.body.classList.contains("nav-open") && !e.target.closest(".sidebar")) {
      document.body.classList.remove("nav-open");
    }
  });

  /* --- Til yorliqlari --- */
  document.addEventListener("click", function (e) {
    var tab = e.target.closest("[data-tab]");
    if (!tab) return;
    e.preventDefault();
    var group = tab.closest("[data-tabs]");
    var name = tab.getAttribute("data-tab");
    group.querySelectorAll("[data-tab]").forEach(function (t) { t.classList.toggle("is-active", t === tab); });
    group.querySelectorAll("[data-tabpane]").forEach(function (p) {
      p.classList.toggle("is-active", p.getAttribute("data-tabpane") === name);
    });
  });

  /* --- O'chirishni tasdiqlash --- */
  document.addEventListener("submit", function (e) {
    var form = e.target;
    var text = form.getAttribute("data-confirm");
    if (text && !window.confirm(text)) e.preventDefault();
  });

  /* --- Rasm tanlanganda oldindan ko'rsatish --- */
  document.addEventListener("change", function (e) {
    var input = e.target;
    if (input.type !== "file" || !input.files || !input.files[0]) return;
    var preview = input.closest(".upload") && input.closest(".upload").querySelector(".upload__preview");
    if (!preview || !/^image\//.test(input.files[0].type)) return;
    var reader = new FileReader();
    reader.onload = function (ev) { preview.src = ev.target.result; };
    reader.readAsDataURL(input.files[0]);
  });

  /* --- Xabarlarni avtomatik yopish --- */
  setTimeout(function () {
    document.querySelectorAll(".message").forEach(function (m) {
      m.style.transition = "opacity .4s";
      m.style.opacity = "0";
      setTimeout(function () { m.remove(); }, 400);
    });
  }, 5000);

  /* --- Filtr formasini avtomatik yuborish --- */
  document.addEventListener("change", function (e) {
    if (e.target.matches("[data-autosubmit]")) e.target.form.submit();
  });

  /* ================= Oddiy SVG grafiklar =================
     Tashqi kutubxonasiz — panel internetsiz ham ishlaydi. */

  /* Katta sonlarni qisqartiradi: 1 250 000 -> 1.3M */
  function shortNumber(value) {
    var n = Math.round(value);
    if (Math.abs(n) >= 1000000) return (n / 1000000).toFixed(n % 1000000 === 0 ? 0 : 1) + "M";
    if (Math.abs(n) >= 1000) return (n / 1000).toFixed(n % 1000 === 0 ? 0 : 1) + "k";
    return String(n);
  }

  function scale(values, height, padTop) {
    var max = Math.max.apply(null, values.concat([1]));
    var usable = height - padTop;
    return values.map(function (v) { return height - (v / max) * usable; });
  }

  function drawLine(el) {
    var data = JSON.parse(el.getAttribute("data-values") || "[]");
    var labels = JSON.parse(el.getAttribute("data-labels") || "[]");
    var color = el.getAttribute("data-color") || "#1f6feb";
    if (!data.length) return;

    var w = el.clientWidth || 600, h = el.clientHeight || 260;
    var padL = 44, padB = 26, padT = 16, padR = 12;
    var innerW = w - padL - padR, innerH = h - padB - padT;
    var max = Math.max.apply(null, data.concat([1]));
    var stepX = data.length > 1 ? innerW / (data.length - 1) : 0;

    var points = data.map(function (v, i) {
      return [padL + i * stepX, padT + innerH - (v / max) * innerH];
    });
    var path = points.map(function (p, i) { return (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1); }).join(" ");
    var area = path + " L" + points[points.length - 1][0].toFixed(1) + " " + (padT + innerH) +
               " L" + points[0][0].toFixed(1) + " " + (padT + innerH) + " Z";

    var gridLines = "", yLabels = "";
    for (var g = 0; g <= 4; g++) {
      var y = padT + (innerH / 4) * g;
      gridLines += '<line x1="' + padL + '" y1="' + y + '" x2="' + (w - padR) + '" y2="' + y +
                   '" stroke="currentColor" stroke-opacity=".12"/>';
      yLabels += '<text x="' + (padL - 8) + '" y="' + (y + 4) +
                 '" text-anchor="end" font-size="11" fill="currentColor" fill-opacity=".55">' +
                 shortNumber(max - (max / 4) * g) + '</text>';
    }

    var xLabels = labels.map(function (t, i) {
      if (labels.length > 10 && i % Math.ceil(labels.length / 8) !== 0) return "";
      return '<text x="' + (padL + i * stepX) + '" y="' + (h - 6) +
             '" text-anchor="middle" font-size="11" fill="currentColor" fill-opacity=".55">' + t + '</text>';
    }).join("");

    var dots = points.map(function (p, i) {
      return '<circle cx="' + p[0].toFixed(1) + '" cy="' + p[1].toFixed(1) + '" r="3.2" fill="' + color +
             '"><title>' + (labels[i] || "") + ": " + shortNumber(data[i]) + '</title></circle>';
    }).join("");

    el.innerHTML =
      '<svg viewBox="0 0 ' + w + ' ' + h + '" width="100%" height="100%" style="color:var(--muted)">' +
      '<defs><linearGradient id="g' + (el.id || "x") + '" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0%" stop-color="' + color + '" stop-opacity=".28"/>' +
      '<stop offset="100%" stop-color="' + color + '" stop-opacity="0"/></linearGradient></defs>' +
      gridLines + yLabels + xLabels +
      '<path d="' + area + '" fill="url(#g' + (el.id || "x") + ')"/>' +
      '<path d="' + path + '" fill="none" stroke="' + color + '" stroke-width="2.5" ' +
      'stroke-linejoin="round" stroke-linecap="round"/>' + dots + '</svg>';
  }

  function drawBars(el) {
    var data = JSON.parse(el.getAttribute("data-values") || "[]");
    var labels = JSON.parse(el.getAttribute("data-labels") || "[]");
    var color = el.getAttribute("data-color") || "#1f6feb";
    if (!data.length) return;

    var w = el.clientWidth || 600, h = el.clientHeight || 260;
    var padL = 44, padB = 28, padT = 16, padR = 12;
    var innerW = w - padL - padR, innerH = h - padB - padT;
    var max = Math.max.apply(null, data.concat([1]));
    var slot = innerW / data.length;
    var bw = Math.min(38, slot * 0.62);

    var bars = data.map(function (v, i) {
      var bh = (v / max) * innerH;
      var x = padL + slot * i + (slot - bw) / 2;
      var y = padT + innerH - bh;
      return '<rect x="' + x.toFixed(1) + '" y="' + y.toFixed(1) + '" width="' + bw.toFixed(1) +
             '" height="' + Math.max(bh, 1).toFixed(1) + '" rx="6" fill="' + color + '">' +
             '<title>' + (labels[i] || "") + ": " + shortNumber(v) + '</title></rect>';
    }).join("");

    var gridLines = "", yLabels = "";
    for (var g = 0; g <= 4; g++) {
      var y = padT + (innerH / 4) * g;
      gridLines += '<line x1="' + padL + '" y1="' + y + '" x2="' + (w - padR) + '" y2="' + y +
                   '" stroke="currentColor" stroke-opacity=".12"/>';
      yLabels += '<text x="' + (padL - 8) + '" y="' + (y + 4) + '" text-anchor="end" font-size="11" ' +
                 'fill="currentColor" fill-opacity=".55">' + shortNumber(max - (max / 4) * g) + '</text>';
    }
    var xLabels = labels.map(function (t, i) {
      return '<text x="' + (padL + slot * i + slot / 2) + '" y="' + (h - 8) +
             '" text-anchor="middle" font-size="11" fill="currentColor" fill-opacity=".55">' + t + '</text>';
    }).join("");

    el.innerHTML = '<svg viewBox="0 0 ' + w + ' ' + h + '" width="100%" height="100%" style="color:var(--muted)">' +
      gridLines + yLabels + xLabels + bars + '</svg>';
  }

  function drawDonut(el) {
    var data = JSON.parse(el.getAttribute("data-values") || "[]");
    var labels = JSON.parse(el.getAttribute("data-labels") || "[]");
    var colors = JSON.parse(el.getAttribute("data-colors") || '["#1f6feb","#ff6a00","#16a34a","#8b5cf6","#0ea5e9"]');
    var total = data.reduce(function (a, b) { return a + b; }, 0);
    var size = Math.min(el.clientWidth || 240, el.clientHeight || 240);
    var cx = size / 2, cy = size / 2, r = size / 2 - 12, thickness = 26;

    if (!total) {
      el.innerHTML = '<div class="empty" style="padding:30px">—</div>';
      return;
    }

    var angle = -Math.PI / 2, arcs = "";
    data.forEach(function (v, i) {
      var slice = (v / total) * Math.PI * 2;
      var end = angle + slice;
      var large = slice > Math.PI ? 1 : 0;
      var x1 = cx + r * Math.cos(angle), y1 = cy + r * Math.sin(angle);
      var x2 = cx + r * Math.cos(end), y2 = cy + r * Math.sin(end);
      arcs += '<path d="M' + x1.toFixed(2) + ' ' + y1.toFixed(2) + ' A' + r + ' ' + r + ' 0 ' + large + ' 1 ' +
              x2.toFixed(2) + ' ' + y2.toFixed(2) + '" fill="none" stroke="' + colors[i % colors.length] +
              '" stroke-width="' + thickness + '"><title>' + (labels[i] || "") + ": " + v + '</title></path>';
      angle = end;
    });

    el.innerHTML = '<svg viewBox="0 0 ' + size + ' ' + size + '" width="100%" height="100%">' + arcs +
      '<text x="' + cx + '" y="' + (cy - 2) + '" text-anchor="middle" font-size="22" font-weight="800" ' +
      'fill="currentColor">' + total + '</text></svg>';
  }

  function renderCharts() {
    document.querySelectorAll("[data-chart]").forEach(function (el) {
      var type = el.getAttribute("data-chart");
      try {
        if (type === "line") drawLine(el);
        else if (type === "bar") drawBars(el);
        else if (type === "donut") drawDonut(el);
      } catch (err) { /* grafik chizilmasa sahifa baribir ishlaydi */ }
    });
  }

  window.addEventListener("load", renderCharts);
  var resizeTimer;
  window.addEventListener("resize", function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(renderCharts, 200);
  });
})();
