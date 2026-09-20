/* ============ VECTOR — ommaviy sayt/kabinet uchun umumiy JS ============ */
(function (global) {
  "use strict";
  var A = global.VectorAPI;

  /* ---------- Umumiy API so'rovi (/api/...) ---------- */
  function apiFetch(path, options) {
    options = options || {};
    var headers = { "Content-Type": "application/json" };
    var token = A.load(A.STORE.access);
    if (token && options.auth !== false) headers.Authorization = "Bearer " + token;

    return fetch("/api" + path, {
      method: options.method || "GET",
      headers: headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
    }).then(function (res) {
      return res.text().then(function (text) {
        var data = {};
        try { data = text ? JSON.parse(text) : {}; }
        catch (e) { data = { detail: "Serverda xatolik yuz berdi." }; }
        if (!res.ok) {
          var err = new Error(A.firstError(data));
          err.status = res.status; err.data = data;
          throw err;
        }
        return data;
      });
    }, function () {
      var err = new Error("Serverga ulanib bo'lmadi. Internetni tekshiring.");
      err.status = 0; throw err;
    });
  }

  function isLoggedIn() { return !!A.load(A.STORE.access); }

  function money(n) {
    n = Number(n) || 0;
    return n.toLocaleString("ru-RU").replace(/,/g, " ");
  }

  function starsHtml(rating, max) {
    max = max || 5;
    rating = Math.round(rating || 0);
    var out = "";
    for (var i = 1; i <= max; i++) out += "<span class=\"" + (i <= rating ? "on" : "") + "\">★</span>";
    return "<span class=\"stars\">" + out + "</span>";
  }

  function timeAgo() { return ""; }

  /* ---------- Navigatsiya: kirgan/kirmagan holatni ko'rsatish ---------- */
  function initNav() {
    var guestBox = document.querySelector("[data-nav-guest]");
    var userBox = document.querySelector("[data-nav-user]");
    var logoutBtn = document.querySelector("[data-nav-logout]");
    var toggle = document.querySelector("[data-nav-toggle]");
    var links = document.querySelector(".nav__links");

    if (toggle && links) {
      toggle.addEventListener("click", function () {
        links.classList.toggle("is-open");
      });
    }

    if (!isLoggedIn()) {
      if (guestBox) guestBox.style.display = "flex";
      if (userBox) userBox.style.display = "none";
      return Promise.resolve(null);
    }

    return A.request("/me/").then(function (user) {
      if (guestBox) guestBox.style.display = "none";
      if (userBox) {
        userBox.style.display = "flex";
        var nameEl = userBox.querySelector("[data-user-name]");
        var coinEl = userBox.querySelector("[data-user-coin]");
        var avatarEl = userBox.querySelector("[data-user-avatar]");
        if (nameEl) nameEl.textContent = user.full_name;
        if (coinEl) coinEl.textContent = money(user.coins) + " Coin";
        if (avatarEl && user.avatar) avatarEl.src = user.avatar;
      }
      document.querySelectorAll("[data-require-premium]").forEach(function (el) {
        el.classList.toggle("is-hidden", !user.is_premium);
      });
      A.save(A.STORE.user, user);
      return user;
    }).catch(function () {
      A.clearAll();
      if (guestBox) guestBox.style.display = "flex";
      if (userBox) userBox.style.display = "none";
      return null;
    });
  }

  /* ---------- Bildirishnomalar ro'yxati (qo'ng'iroq oynachasi) ---------- */
  function renderNotifList(list, listEl, dotEl) {
    if (!list.length) {
      listEl.innerHTML = '<div class="nav__notif-empty">Hozircha bildirishnoma yo\'q</div>';
      if (dotEl) dotEl.classList.remove("is-on");
      return;
    }
    listEl.innerHTML = list.map(function (n) {
      return '<div class="nav__notif' + (n.is_read ? "" : " is-unread") + '" data-notif-id="' + n.id + '">' +
        '<div class="nav__notif-title">' + n.title + "</div>" +
        '<div class="nav__notif-body">' + (n.body || "") + "</div></div>";
    }).join("");
    listEl.querySelectorAll("[data-notif-id]").forEach(function (el) {
      el.addEventListener("click", function () {
        if (!el.classList.contains("is-unread")) return;
        apiFetch("/notifications/" + el.dataset.notifId + "/read/", { method: "POST" }).then(function () {
          el.classList.remove("is-unread");
          if (dotEl && !listEl.querySelector(".is-unread")) dotEl.classList.remove("is-on");
        }).catch(function () { /* jim */ });
      });
    });
    if (dotEl) dotEl.classList.toggle("is-on", list.some(function (n) { return !n.is_read; }));
  }

  function loadNotifications(listEl, dotEl) {
    listEl.innerHTML = '<div class="nav__notif-loading">Yuklanmoqda...</div>';
    apiFetch("/notifications/").then(function (list) {
      renderNotifList(Array.isArray(list) ? list : (list.results || []), listEl, dotEl);
    }).catch(function () {
      listEl.innerHTML = '<div class="nav__notif-error">Yuklab bo\'lmadi. Qayta urinib ko\'ring.</div>';
    });
  }

  /* ---------- Sarlavhadagi qo'ng'iroq / profil menyulari ---------- */
  function initHeaderMenus() {
    var bellToggle = document.querySelector("[data-bell-toggle]");
    var notifPanel = document.querySelector("[data-notif-dropdown]");
    var notifList = document.querySelector("[data-notif-list]");
    var bellDot = document.querySelector("[data-bell-dot]");
    var userToggle = document.querySelector("[data-user-toggle]");
    var userPanel = document.querySelector("[data-user-dropdown]");
    var logoutBtn = document.querySelector("[data-nav-logout]");
    var notifLoaded = false;

    function closePanels(except) {
      if (notifPanel && notifPanel !== except) notifPanel.hidden = true;
      if (userPanel && userPanel !== except) userPanel.hidden = true;
    }

    if (bellToggle && notifPanel) {
      bellToggle.addEventListener("click", function (e) {
        e.stopPropagation();
        if (!isLoggedIn()) { window.location.href = "/kirish/"; return; }
        var opening = notifPanel.hidden;
        closePanels();
        notifPanel.hidden = !opening;
        if (opening && notifList) { loadNotifications(notifList, bellDot); notifLoaded = true; }
      });
    }

    if (userToggle && userPanel) {
      userToggle.addEventListener("click", function (e) {
        e.stopPropagation();
        var opening = userPanel.hidden;
        closePanels();
        userPanel.hidden = !opening;
      });
    }

    document.addEventListener("click", function () { closePanels(); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") closePanels(); });

    if (logoutBtn) {
      logoutBtn.addEventListener("click", function (e) {
        e.preventDefault();
        A.clearAll();
        window.location.href = "/kirish/";
      });
    }

    // Sahifa ochilganda, agar tizimga kirilgan bo'lsa — o'qilmagan bildirishnoma borligini tekshiramiz
    if (isLoggedIn() && bellDot) {
      apiFetch("/notifications/").then(function (list) {
        list = Array.isArray(list) ? list : (list.results || []);
        bellDot.classList.toggle("is-on", list.some(function (n) { return !n.is_read; }));
      }).catch(function () { /* jim — keyingi ochilishda qayta urinamiz */ });
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    initNav();
    initHeaderMenus();
    // FAQ akkordeon (istalgan sahifada ishlaydi)
    document.querySelectorAll(".faq-item__q").forEach(function (q) {
      q.addEventListener("click", function () {
        q.parentElement.classList.toggle("is-open");
      });
    });
  });

  global.VectorSite = {
    apiFetch: apiFetch,
    isLoggedIn: isLoggedIn,
    money: money,
    starsHtml: starsHtml,
    initNav: initNav,
    requireAuth: function () {
      if (!isLoggedIn()) { window.location.href = "/kirish/"; return false; }
      return true;
    },
  };
})(window);
