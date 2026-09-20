/* ============ VECTOR — API bilan ishlash uchun yordamchilar ============ */
(function (global) {
  "use strict";

  var API = "/api/auth";
  var STORE = {
    access: "vector_access",
    refresh: "vector_refresh",
    user: "vector_user",
    verification: "vector_verification"
  };

  /* ---------- Saqlash (localStorage xatolarga chidamli) ---------- */
  function save(key, value) {
    try { localStorage.setItem(key, typeof value === "string" ? value : JSON.stringify(value)); }
    catch (e) { /* private rejim — e'tiborsiz qoldiramiz */ }
  }
  function load(key, asJson) {
    try {
      var raw = localStorage.getItem(key);
      if (raw === null) return null;
      return asJson ? JSON.parse(raw) : raw;
    } catch (e) { return null; }
  }
  function clearAll() {
    try { Object.keys(STORE).forEach(function (k) { localStorage.removeItem(STORE[k]); }); }
    catch (e) { /* e'tiborsiz */ }
  }

  /* ---------- So'rov ---------- */
  function request(path, options) {
    options = options || {};
    var headers = { "Content-Type": "application/json" };
    var token = load(STORE.access);
    if (token && options.auth !== false) headers.Authorization = "Bearer " + token;

    return fetch(API + path, {
      method: options.method || "GET",
      headers: headers,
      body: options.body ? JSON.stringify(options.body) : undefined
    }).then(function (res) {
      return res.text().then(function (text) {
        var data = {};
        try {
          data = text ? JSON.parse(text) : {};
        } catch (e) {
          // Server HTML qaytardi (masalan, Django xato sahifasi) — uni foydalanuvchiga ko'rsatmaymiz
          console.error("Serverdan kutilmagan javob:", text.slice(0, 2000));
          data = { detail: "Serverda xatolik yuz berdi. Administratorga murojaat qiling." };
        }
        if (!res.ok) {
          var err = new Error(firstError(data));
          err.status = res.status;
          err.data = data;
          throw err;
        }
        return data;
      });
    }, function () {
      var err = new Error("Serverga ulanib bo'lmadi. Internetni tekshiring.");
      err.status = 0;
      throw err;
    });
  }

  /* Serverdan kelgan xatolardan birinchi o'qiladigan matnni ajratadi */
  function firstError(data) {
    if (!data) return "Noma'lum xato yuz berdi.";
    if (typeof data === "string") return data;
    if (data.detail) return typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    var keys = Object.keys(data);
    for (var i = 0; i < keys.length; i++) {
      var v = data[keys[i]];
      if (Array.isArray(v) && v.length) return String(v[0]);
      if (typeof v === "string") return v;
      if (v && typeof v === "object" && v.detail) return String(v.detail);
    }
    return "Ma'lumotlarda xatolik bor.";
  }

  /* ---------- Telefon raqam ---------- */
  function digitsOnly(value) { return (value || "").replace(/\D/g, ""); }

  /* (90)-123-45-67 ko'rinishida maska qo'yadi */
  function formatPhone(value) {
    var d = digitsOnly(value);
    if (d.indexOf("998") === 0) d = d.slice(3);
    d = d.slice(0, 9);
    if (!d) return "";
    var out = "(" + d.slice(0, 2);
    if (d.length >= 2) out += ")";
    if (d.length > 2) out += "-" + d.slice(2, 5);
    if (d.length > 5) out += "-" + d.slice(5, 7);
    if (d.length > 7) out += "-" + d.slice(7, 9);
    return out;
  }

  function attachPhoneMask(input) {
    if (!input) return;
    input.addEventListener("input", function () {
      input.value = formatPhone(input.value);
    });
    input.addEventListener("paste", function (e) {
      e.preventDefault();
      var text = (e.clipboardData || global.clipboardData).getData("text");
      input.value = formatPhone(text);
    });
  }

  function phoneIsValid(value) {
    var d = digitsOnly(value);
    if (d.indexOf("998") === 0) d = d.slice(3);
    return d.length === 9;
  }

  /* ---------- Sana: 07.05.2016 -> 2016-05-07 ---------- */
  function attachDateMask(input) {
    if (!input) return;
    input.addEventListener("input", function () {
      var d = digitsOnly(input.value).slice(0, 8);
      var out = d.slice(0, 2);
      if (d.length > 2) out += "." + d.slice(2, 4);
      if (d.length > 4) out += "." + d.slice(4, 8);
      input.value = out;
    });
  }

  function toIsoDate(value) {
    var m = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec((value || "").trim());
    if (!m) return null;
    var day = +m[1], month = +m[2], year = +m[3];
    if (month < 1 || month > 12 || day < 1 || day > 31) return null;
    var dt = new Date(Date.UTC(year, month - 1, day));
    if (dt.getUTCFullYear() !== year || dt.getUTCMonth() !== month - 1 || dt.getUTCDate() !== day) return null;
    if (year < 1940 || dt > new Date()) return null;
    return m[3] + "-" + m[2] + "-" + m[1];
  }

  /* ---------- UI yordamchilari ---------- */
  function showAlert(el, message, type) {
    if (!el) return;
    el.textContent = message;
    el.className = "alert alert--" + (type || "error") + " is-visible";
  }
  function hideAlert(el) { if (el) el.className = "alert"; }

  function markInvalid(input, message) {
    if (!input) return;
    var field = input.closest(".field") || input.parentElement;
    input.setAttribute("aria-invalid", "true");
    if (field) {
      field.classList.add("field--invalid");
      var err = field.querySelector(".field__error");
      if (err && message) err.textContent = message;
    }
  }
  function clearInvalid(form) {
    if (!form) return;
    form.querySelectorAll("[aria-invalid]").forEach(function (i) { i.removeAttribute("aria-invalid"); });
    form.querySelectorAll(".field--invalid").forEach(function (f) { f.classList.remove("field--invalid"); });
  }

  function setLoading(button, loading, textWhileLoading) {
    if (!button) return;
    var label = button.querySelector(".btn__label");
    if (loading) {
      button.disabled = true;
      button.classList.add("is-loading");
      if (label) {
        button.dataset.originalText = button.dataset.originalText || label.textContent;
        label.textContent = textWhileLoading || "Yuborilmoqda...";
      }
    } else {
      button.disabled = false;
      button.classList.remove("is-loading");
      if (label && button.dataset.originalText) label.textContent = button.dataset.originalText;
    }
  }

  /* Server xatolarini tegishli maydonlarga tarqatadi */
  function applyFieldErrors(form, data) {
    if (!form || !data || typeof data !== "object") return false;
    var applied = false;
    Object.keys(data).forEach(function (name) {
      var input = form.querySelector('[name="' + name + '"]');
      if (!input) return;
      var val = data[name];
      markInvalid(input, Array.isArray(val) ? val[0] : String(val));
      applied = true;
    });
    return applied;
  }

  global.VectorAPI = {
    STORE: STORE,
    request: request,
    save: save,
    load: load,
    clearAll: clearAll,
    firstError: firstError,
    formatPhone: formatPhone,
    attachPhoneMask: attachPhoneMask,
    attachDateMask: attachDateMask,
    phoneIsValid: phoneIsValid,
    toIsoDate: toIsoDate,
    digitsOnly: digitsOnly,
    showAlert: showAlert,
    hideAlert: hideAlert,
    markInvalid: markInvalid,
    clearInvalid: clearInvalid,
    setLoading: setLoading,
    applyFieldErrors: applyFieldErrors,
    saveSession: function (data) {
      if (data.tokens) {
        save(STORE.access, data.tokens.access);
        save(STORE.refresh, data.tokens.refresh);
      }
      if (data.user) save(STORE.user, data.user);
    }
  };
})(window);
