/*
  ווידג'ט הצ'אט לאתר הפניקס.

  הטמעה בכל אתר בשורה אחת:
    <script src="https://<הכתובת>/widget.js" defer></script>
  -> מופיעה בועת צ'אט בפינה. אפשרויות: data-color="#..." (צבע מותג),
     data-open="auto" (החלון נפתח לבד), data-mount="#מזהה" (הצ'אט בתוך הדף במקום בועה).

  מבנה הקובץ:
    עזרים            - יצירת אלמנטים, עיצוב טקסט, קישור מדגיש, "פתוח עכשיו"
    Chat             - חלון הצ'אט: שליחת שאלה ל-/api/ask והצגת התשובה
    שאלות נפוצות     - תשובות שהוכנו ונבדקו מראש (faq.json)
    הרכבה בדף        - בועה צפה בפינה, או בתוך הדף
*/
(function () {
  "use strict";

  var script = document.currentScript;
  var BASE = script && script.src ? new URL(script.src).origin : location.origin;
  var opts = (script && script.dataset) || {};

  // טוענים את קובץ העיצוב (אם עוד לא נטען)
  if (!document.querySelector("[data-mk-css]")) {
    var css = document.createElement("link");
    css.rel = "stylesheet"; css.href = BASE + "/widget.css"; css.setAttribute("data-mk-css", "");
    document.head.appendChild(css);
  }

  var ICON = {
    send: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
    close: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>',
    reset: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12a8 8 0 1 0 2.4-5.7"/><path d="M4 4v4h4"/></svg>',
    book: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z"/><path d="M4 19V5"/><path d="M9 8h6"/></svg>',
    back: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>',
    phone: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 4h4l2 5-3 2a11 11 0 0 0 5 5l2-3 5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/></svg>',
    mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>',
    speaker: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9h4l5-4v14l-5-4H4z"/><path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12"/></svg>',
    ext: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4h6v6"/><path d="M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>'
  };

  // הסמל המונפש: עיגול בצבע המותג עם שלוש "שורות טקסט".
  // נח = נושם בעדינות · קורא = מרקר צהוב עובר על השורות · עונה = השורות "נכתבות"
  function orb(cls) {
    return '<span class="mk-orb' + (cls ? " " + cls : "") + '" data-state="idle" aria-hidden="true">' +
      '<svg viewBox="0 0 24 24"><rect class="hl h1" x="4" y="6" width="16" height="3" rx="1.5"/>' +
      '<rect class="hl h2" x="9" y="10.5" width="11" height="3" rx="1.5"/><rect class="hl h3" x="6" y="15" width="14" height="3" rx="1.5"/>' +
      '<rect class="ln l1" x="4" y="6" width="16" height="3" rx="1.5"/><rect class="ln l2" x="9" y="10.5" width="11" height="3" rx="1.5"/>' +
      '<rect class="ln l3" x="6" y="15" width="14" height="3" rx="1.5"/></svg></span>';   // שורות מיושרות לימין, כמו עברית
  }

  // כיתובים לפי שפת התשובה (הבוט עונה בשפה שבה שאלו)
  var LABELS = {
    he: { answered: "✓ נמצא באתר", not_found: "לא מופיע באתר", personal: "שאלה אישית", source: "מקור",
          open: "לראות באתר", openHl: "לראות באתר, מודגש", rep: "צריכים נציג? ", prepare: "מה להכין",
          ready: "מוכן", listen: "הקראה", stop: "עצירה" },
    ru: { answered: "✓ Есть на сайте", not_found: "Нет на сайте", personal: "Личный вопрос", source: "Источник",
          open: "Открыть на сайте", openHl: "Открыть на сайте (с выделением)", rep: "Нужен представитель? ",
          prepare: "Что подготовить", ready: "готово", listen: "Прослушать", stop: "Стоп" },
    ar: { answered: "✓ موجود في الموقع", not_found: "غير موجود في الموقع", personal: "سؤال شخصي", source: "المصدر",
          open: "فتح في الموقع", openHl: "فتح في الموقع مع التظليل", rep: "تحتاج إلى ممثل؟ ",
          prepare: "ما يجب تحضيره", ready: "جاهز", listen: "استماع", stop: "إيقاف" },
    en: { answered: "✓ Found on the site", not_found: "Not on the site", personal: "Personal question", source: "Source",
          open: "Open on the site", openHl: "Open on the site, highlighted", rep: "Need an agent? ",
          prepare: "What to prepare", ready: "done", listen: "Listen", stop: "Stop" }
  };
  // שפת טקסט לפי האותיות שבו
  function langOf(text) {
    var t = String(text);
    var count = function (re) { return (t.match(re) || []).length; };
    var scores = { he: count(/[\u0590-\u05FF]/g), ru: count(/[\u0400-\u04FF]/g),
                   ar: count(/[\u0600-\u06FF]/g), am: count(/[\u1200-\u137F]/g), en: count(/[a-zA-Z]/g) };
    var best = "he";
    Object.keys(scores).forEach(function (k) { if (scores[k] > scores[best]) best = k; });
    return best;
  }
  function labels(lang) { return LABELS[lang] || LABELS.en; }
  var SPEECH_LANG = { he: "he-IL", ru: "ru-RU", ar: "ar-SA", en: "en-US", am: "am-ET" };

  // מה כתוב מתחת לאנימציה בזמן שהבוט עובד
  var THINKING = ["קורא באתר הפניקס…", "מאתר את המשפט המדויק…", "מנסח תשובה…"];

  // ---------- עזרים ----------
  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  var reduceMotion = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

  // הדגשה **כך** -> מודגש (אחרי escape, כך שאין סכנה של HTML)
  function inline(t) { return esc(t).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>"); }

  // טקסט פשוט -> פסקאות ורשימות (שורות שמתחילות ב-"- ")
  function formatAnswer(text) {
    var out = "", list = false;
    String(text).split("\n").forEach(function (line) {
      var t = line.trim();
      if (!t) return;
      var item = t.match(/^([-•*]|\d+[.)])\s+(.*)$/);
      if (item) {
        if (!list) { out += '<ul dir="auto">'; list = true; }
        out += '<li dir="auto">' + inline(item[2]) + "</li>";
      } else {
        if (list) { out += "</ul>"; list = false; }
        out += '<p dir="auto">' + inline(t) + "</p>";
      }
    });
    return out + (list ? "</ul>" : "");
  }

  // הפיצ'ר "הקישור שמדגיש": פותח את העמוד באתר עם המשפט מסומן.
  // משתמש ב-Text Fragment, תכונה מובנית של הדפדפן: כתובת#:~:text=המשפט
  function highlightLink(url, quote) {
    if (!quote) return url;
    var enc = encodeURIComponent(quote).replace(/-/g, "%2D");
    return url.split("#")[0] + "#:~:text=" + enc;
  }

  // הפיצ'ר "המוקד הנכון": האם המוקד פתוח עכשיו, לפי שעון ישראל
  function openNow(hours) {
    if (!hours) return null;
    if (hours.always) return true;
    var parts = new Intl.DateTimeFormat("en-US", {
      timeZone: "Asia/Jerusalem", weekday: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23"
    }).formatToParts(new Date());
    var get = function (t) { return (parts.find(function (p) { return p.type === t; }) || {}).value; };
    var day = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].indexOf(get("weekday"));
    var now = get("hour") + ":" + get("minute");
    return hours.days.indexOf(day) !== -1 && now >= hours.from && now < hours.to;
  }
  function telHref(number) { return "tel:" + number.replace(/[^\d*+]/g, "").replace("*", "%2A"); }
  function waHref(number) { return "https://wa.me/972" + number.replace(/\D/g, "").replace(/^0/, ""); }

  // כרטיסי המקורות: שם העמוד, המשפט המודגש, וכפתור לפתיחה באתר
  function sourcesBlock(sources, L) {
    L = L || LABELS.he;
    var list = el("div", "mk-sources");
    sources.forEach(function (s) {
      var card = el("div", "mk-src");
      card.appendChild(el("div", "mk-src-title", "<span>" + esc(L.source) + "</span>" + esc(s.title)));
      if (s.quote) card.appendChild(el("div", "mk-quote", "<mark>" + esc(s.quote) + "</mark>"));
      // כתובת העמוד, כמו שהאתגר ביקש ("המקור: fnx.co.il/…")
      var short = s.url.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "");
      card.appendChild(el("div", "mk-src-url", '<bdi dir="ltr">' + esc(short) + "</bdi>"));
      var a = el("a", "mk-src-link", esc(s.quote ? L.openHl : L.open) + ICON.ext);
      a.href = highlightLink(s.url, s.quote); a.target = "_blank"; a.rel = "noopener";
      card.appendChild(a);
      list.appendChild(card);
    });
    return list;
  }

  // כרטיס המוקד: שם, פתוח/סגור עכשיו, שעות, וכפתורי חיוג ווואטסאפ
  function deptCard(d) {
    var card = el("div", "mk-dept");
    var top = el("div", "mk-dept-top");
    top.appendChild(el("span", "mk-dept-ico", ICON.phone));
    top.appendChild(el("span", "mk-dept-name", esc(d.name)));
    var isOpen = openNow(d.hours);
    if (isOpen !== null) {
      top.appendChild(el("span", "mk-open " + (isOpen ? "is-open" : "is-closed"),
        isOpen ? "פתוח עכשיו" : "סגור עכשיו"));
    }
    card.appendChild(top);
    if (d.hours) card.appendChild(el("div", "mk-hours", "שעות פעילות: " + esc(d.hours.text)));
    var contacts = el("div", "mk-contacts");
    (d.phones || []).forEach(function (p) {
      var wa = p.label === "וואטסאפ";
      var a = el("a", "mk-contact" + (wa ? " is-wa" : ""));
      a.href = wa ? waHref(p.number) : telHref(p.number);
      if (wa) { a.target = "_blank"; a.rel = "noopener"; }
      a.innerHTML = "<small>" + esc(p.label) + "</small><bdi>" + esc(p.number) + "</bdi>";
      contacts.appendChild(a);
    });
    card.appendChild(contacts);
    return card;
  }

  // טבלת השוואה ("מה ההבדל בין...")
  function tableBlock(t) {
    var wrap = el("div", "mk-table-wrap");
    var html = '<table class="mk-table" dir="auto"><thead><tr>' +
      t.columns.map(function (c) { return "<th>" + esc(c) + "</th>"; }).join("") + "</tr></thead><tbody>" +
      t.rows.map(function (row) {
        return "<tr>" + row.map(function (c, i) { return (i ? "<td>" : "<th scope=\"row\">") + esc(c) + (i ? "</td>" : "</th>"); }).join("") + "</tr>";
      }).join("") + "</tbody></table>";
    wrap.innerHTML = html;
    return wrap;
  }

  // רשימת "מה להכין" עם תיבות סימון - הלקוחה מסמנת תוך כדי הכנה
  function checklistBlock(items, L) {
    var box = el("div", "mk-check");
    var head = el("div", "mk-check-head");
    head.appendChild(el("b", null, "📋 " + esc(L.prepare)));
    var count = el("span", "mk-check-count", "0/" + items.length + " " + esc(L.ready));
    head.appendChild(count);
    box.appendChild(head);
    items.forEach(function (text) {
      var row = el("label", "mk-check-item");
      row.setAttribute("dir", "auto");
      var cb = document.createElement("input"); cb.type = "checkbox";
      cb.addEventListener("change", function () {
        var done = box.querySelectorAll("input:checked").length;
        count.textContent = done + "/" + items.length + " " + L.ready;
        box.classList.toggle("is-done", done === items.length);
      });
      row.appendChild(cb);
      row.appendChild(el("span", null, esc(text)));
      box.appendChild(row);
    });
    return box;
  }

  // הקראת התשובה בקול - מנוע הדיבור שמובנה בדפדפן
  var synth = window.speechSynthesis;
  function voiceFor(lang) {
    if (!synth) return null;
    var code = SPEECH_LANG[lang] || "he-IL", voices = synth.getVoices();
    return voices.find(function (v) { return v.lang === code; }) ||
           voices.find(function (v) { return v.lang && v.lang.slice(0, 2) === code.slice(0, 2); }) || null;
  }
  function speakButton(text, lang, L) {
    if (!synth || !window.SpeechSynthesisUtterance) return null;
    var btn = el("button", "mk-speak", ICON.speaker + "<span>" + esc(L.listen) + "</span>"); btn.type = "button";
    btn.addEventListener("click", function () {
      if (synth.speaking) { synth.cancel(); return; }
      var u = new SpeechSynthesisUtterance(String(text).replace(/^[-•*]\s+/gm, ""));
      u.lang = SPEECH_LANG[lang] || "he-IL";
      var v = voiceFor(lang); if (v) u.voice = v;
      u.rate = 1;
      u.onstart = function () { btn.classList.add("is-on"); btn.querySelector("span").textContent = L.stop; };
      u.onend = u.onerror = function () { btn.classList.remove("is-on"); btn.querySelector("span").textContent = L.listen; };
      synth.speak(u);
    });
    // אם אין בדפדפן קול בשפה הזו - לא מציגים את הכפתור
    function check() { if (!voiceFor(lang)) btn.hidden = true; }
    if (synth.getVoices().length) check();
    else if (synth.addEventListener) synth.addEventListener("voiceschanged", check, { once: true });
    return btn;
  }

  // שאלה בקול - זיהוי הדיבור שמובנה בדפדפן (כרום / אדג')
  var Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  // ---------- הצ'אט ----------
  function Chat(host) {
    this.history = [];             // [{q, a, urls}] - כדי להבין שאלות המשך
    this.busy = false;
    this.root = host;
    host.classList.add("mk", "mk-auto-theme");
    if (opts.color) host.style.setProperty("--mk-accent", opts.color);
    this.render();
    this.warmUp();
  }

  Chat.prototype.render = function () {
    var self = this;
    var panel = el("div", "mk-panel");
    panel.innerHTML =
      '<div class="mk-head">' + orb() +
      '  <div class="mk-title"><b>שירות דיגיטלי</b>' +
      '    <span class="mk-status" data-state="warming" role="status"><span class="mk-dot"></span><span class="mk-status-text">מתחבר…</span></span></div>' +
      '  <div class="mk-head-actions">' +
      '    <button class="mk-faq-btn" type="button" aria-pressed="false">' + ICON.book + "<span>שאלות נפוצות</span></button>" +
      '    <button class="mk-icon-btn mk-reset" type="button" aria-label="שיחה חדשה" title="שיחה חדשה">' + ICON.reset + "</button>" +
      '    <button class="mk-icon-btn mk-close" type="button" aria-label="סגירה" title="סגירה" hidden>' + ICON.close + "</button>" +
      "  </div>" +
      "</div>" +
      '<div class="mk-body">' +
      '  <div class="mk-log" aria-live="polite"></div>' +
      '  <div class="mk-faq" hidden></div>' +
      "</div>" +
      '<form class="mk-form">' +
      '  <div class="mk-row">' +
      '    <textarea class="mk-input" aria-label="השאלה שלך" rows="1" placeholder="כתבו שאלה…"></textarea>' +
      '    <button class="mk-mic" type="button" aria-label="לשאול בקול" title="לשאול בקול" hidden>' + ICON.mic + "</button>" +
      '    <button class="mk-send" type="submit" aria-label="שליחה">' + ICON.send + "</button>" +
      "  </div>" +
      '  <div class="mk-note">התשובות מבוססות על המידע הציבורי באתר הפניקס · אין לשתף פרטים אישיים</div>' +
      "</form>";
    this.root.appendChild(panel);

    this.log = panel.querySelector(".mk-log");
    this.faq = panel.querySelector(".mk-faq");
    this.faqBtn = panel.querySelector(".mk-faq-btn");
    this.input = panel.querySelector(".mk-input");
    this.sendBtn = panel.querySelector(".mk-send");
    this.statusEl = panel.querySelector(".mk-status");
    this.closeBtn = panel.querySelector(".mk-close");
    this.orbs = [panel.querySelector(".mk-head .mk-orb")];

    panel.querySelector(".mk-form").addEventListener("submit", function (e) {
      e.preventDefault(); self.ask(self.input.value);
    });
    this.input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); self.ask(self.input.value); }
    });
    this.input.addEventListener("input", function () {
      self.input.style.height = "auto";
      self.input.style.height = Math.min(self.input.scrollHeight, 120) + "px";
    });
    panel.querySelector(".mk-reset").addEventListener("click", function () { self.reset(); });
    this.faqBtn.addEventListener("click", function () { self.toggleFaq(); });
    this.setupMic(panel.querySelector(".mk-mic"));
    this.welcome();
  };

  // שאלה בקול: הדיבור נכתב לתוך שדה הכתיבה, ולא נשלח לבד - אפשר לעצור לנשום, לתקן, ואז ללחוץ "שליחה".
  // לחיצה נוספת על המיקרופון עוצרת את ההאזנה.
  Chat.prototype.setupMic = function (btn) {
    var self = this;
    if (!Recognition) return;                       // דפדפן בלי זיהוי דיבור - אין כפתור
    btn.hidden = false;
    var rec = null, before = "";
    btn.addEventListener("click", function () {
      if (rec) { rec.stop(); return; }
      rec = new Recognition();
      rec.lang = "he-IL";
      rec.interimResults = true;
      rec.continuous = true;                        // לא נעצר בהפסקה קצרה
      before = self.input.value ? self.input.value.replace(/\s*$/, " ") : "";
      rec.onstart = function () { btn.classList.add("is-on"); self.input.placeholder = "מקשיב… כשמסיימים, לוחצים שליחה"; };
      rec.onresult = function (e) {
        var text = Array.prototype.map.call(e.results, function (r) { return r[0].transcript; }).join("");
        self.input.value = before + text;
        self.input.dispatchEvent(new Event("input"));   // התאמת גובה השדה
      };
      rec.onerror = function () { self.input.placeholder = "לא הצלחתי לשמוע. אפשר לנסות שוב או להקליד."; };
      rec.onend = function () {
        btn.classList.remove("is-on"); rec = null;
        if (self.input.placeholder.indexOf("מקשיב") === 0) self.input.placeholder = "כתבו שאלה…";
        self.input.focus();
      };
      rec.start();
    });
    this.stopMic = function () { if (rec) rec.stop(); };
  };

  Chat.prototype.welcome = function () {
    var box = el("div", "mk-msg mk-hello");
    box.innerHTML = orb() + "<h3>שלום, איך אפשר לעזור?</h3>" +
      "<p>אפשר לשאול כל שאלה על ביטוח, תביעות, פנסיה וחיסכון. התשובה מגיעה מתוך אתר הפניקס, עם קישור למקור.</p>";
    this.log.appendChild(box);
  };

  // מצב הסמל המונפש (בכותרת ובבועה): idle / reading / answering
  Chat.prototype.setState = function (state) {
    this.orbs.forEach(function (o) { if (o) o.dataset.state = state; });
  };

  Chat.prototype.reset = function () {
    this.history = []; this.log.innerHTML = ""; this.welcome();
    this.toggleFaq(false); this.input.focus();
  };

  Chat.prototype.setStatus = function (state, text) {
    this.statusEl.dataset.state = state;
    this.statusEl.querySelector(".mk-status-text").textContent = text;
  };

  // "חימום": השרת טוען את המודל כבר כשהדף נפתח, כדי שהשאלה הראשונה תהיה מהירה
  Chat.prototype.warmUp = function () {
    var self = this;
    fetch(BASE + "/api/ask", { method: "GET" })
      .then(function (r) { if (!r.ok) throw 0; self.setStatus("ready", "מוכן לשאלות"); })
      .catch(function () { self.setStatus("ready", "מוכן לשאלות"); });
  };

  // גלילה למטה - רק אם הלקוחה כבר למטה (לא "חוטפים" לה את המסך אם גללה למעלה לקרוא)
  Chat.prototype.scroll = function (force) {
    var log = this.log, near = log.scrollHeight - log.scrollTop - log.clientHeight < 120;
    if (force || near) log.scrollTop = log.scrollHeight;
  };

  // "חושב": סמל קטן שקורא, וטקסט מנצנץ שמתחלף
  Chat.prototype.thinking = function () {
    var box = el("div", "mk-thinking", orb("sm") + '<span class="mk-thinking-text">' + THINKING[0] + "</span>");
    box.querySelector(".mk-orb").dataset.state = "reading";
    var text = box.querySelector(".mk-thinking-text"), i = 0;
    var timer = setInterval(function () {
      i = Math.min(i + 1, THINKING.length - 1);
      text.textContent = THINKING[i];
    }, 1900);
    box.stop = function () { clearInterval(timer); box.remove(); };
    return box;
  };

  Chat.prototype.ask = function (raw) {
    var self = this;
    var question = (raw || "").trim();
    if (!question || this.busy) return Promise.resolve();
    if (this.stopMic) this.stopMic();
    this.toggleFaq(false);
    this.busy = true; this.sendBtn.disabled = true;
    this.input.value = ""; this.input.style.height = "auto";

    var user = el("div", "mk-msg mk-user"); user.textContent = question; user.setAttribute("dir", "auto");
    this.log.appendChild(user);
    this.scroll(true);
    var bot = el("div", "mk-msg mk-bot");
    this.setState("reading");
    var wait = this.thinking();
    bot.appendChild(wait);
    this.log.appendChild(bot);
    this.scroll();

    var body = JSON.stringify({ question: question, history: this.history.slice(-3) });
    // ניסיון שני שקט: אם השרת עמוס, מחכים 2.5 שניות ומנסים שוב לפני שמציגים הודעת שגיאה
    function send(attempt) {
      return fetch(BASE + "/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: body })
        .then(function (r) {
          return r.json().then(function (data) {
            if (!r.ok) throw new Error(data.error || "תקלה זמנית");
            return data;
          });
        })
        .catch(function (err) {
          if (attempt > 0) throw err;
          return new Promise(function (ok) { setTimeout(ok, 2500); }).then(function () { return send(1); });
        });
    }
    return send(0)
      .then(function (result) {
        wait.stop();
        self.history.push({ q: question, a: result.answer,     // + העמודים שמהם ענינו - לשאלת המשך
          urls: (result.sources || []).map(function (s) { return s.url; }) });
        return self.showAnswer(bot, result);
      })
      .catch(function (err) {
        wait.stop(); self.setState("idle");
        var e = el("div", "mk-bubble");
        e.appendChild(el("p", "mk-error", esc(err.message || "תקלה זמנית. נסו שוב.")));
        var retry = el("button", "mk-retry", "לנסות שוב"); retry.type = "button";
        retry.addEventListener("click", function () { bot.remove(); user.remove(); self.ask(question); });
        e.appendChild(retry);
        bot.appendChild(e);
      })
      .then(function () {
        self.busy = false; self.sendBtn.disabled = false; self.scroll();
      });
  };

  // התשובה: תג סטטוס, הטקסט נכתב מול העיניים, ואחריו - טבלה, רשימה, מקורות ומוקד, בזה אחר זה
  Chat.prototype.showAnswer = function (bot, r) {
    var self = this;
    var lang = langOf(r.answer), L = labels(lang);
    if (!r.unclear) {                               // "לא הבנתי את השאלה" - בלי תג ובלי הקראה
      var top = el("div", "mk-answer-top");
      top.appendChild(el("span", "mk-badge " + r.status, esc(L[r.status] || "")));
      var speak = speakButton(r.answer, lang, L);
      if (speak) top.appendChild(speak);
      bot.appendChild(top);
    }

    var bubble = el("div", "mk-bubble");
    bot.appendChild(bubble);
    var extras = [];
    if (r.table) extras.push(tableBlock(r.table));
    if (r.checklist) extras.push(checklistBlock(r.checklist, L));
    if (r.sources && r.sources.length) extras.push(sourcesBlock(r.sources, L));
    if (r.department) extras.push(this.deptBlock(r.department, r.status !== "answered", L));

    this.setState("answering");
    return this.typeOut(bubble, formatAnswer(r.answer)).then(function () {
      extras.forEach(function (x, i) {
        x.classList.add("mk-stage"); x.style.animationDelay = (i * 0.12) + "s";
        bot.appendChild(x);
      });
      self.setState("idle");
      self.scroll(true);
    });
  };

  // הקלדה מול העיניים: כל פסקה / פריט נכתבים מילה אחרי מילה, ובסוף מקבלים את העיצוב המלא.
  // (התשובה כבר הגיעה מהשרת - זו רק הצגה. מי שביקש "הפחתת תנועה" מקבל אותה מיד.)
  Chat.prototype.typeOut = function (bubble, html) {
    var self = this;
    bubble.innerHTML = html;
    if (reduceMotion) return Promise.resolve();
    var blocks = Array.prototype.slice.call(bubble.querySelectorAll("p, li"));
    var jobs = blocks.map(function (b) {
      var full = b.innerHTML, words = b.textContent.split(/(\s+)/);
      b.textContent = "";
      return { el: b, full: full, words: words };
    });
    var caret = el("span", "mk-caret");
    return jobs.reduce(function (prev, job) {
      return prev.then(function () {
        return new Promise(function (done) {
          var i = 0;
          job.el.appendChild(caret);
          (function step() {
            var chunk = "";
            for (var k = 0; k < 2 && i < job.words.length; k++) chunk += job.words[i++];   // 2 מילים בכל צעד
            caret.insertAdjacentText("beforebegin", chunk);
            self.scroll();
            if (i < job.words.length) setTimeout(step, 28);
            else { job.el.innerHTML = job.full; done(); }
          })();
        });
      });
    }, Promise.resolve());
  };

  // בשאלה אישית / כשאין תשובה: הכרטיס פתוח. בתשובה רגילה: שורה קטנה שנפתחת בלחיצה
  Chat.prototype.deptBlock = function (d, open, L) {
    var self = this;
    if (open) return deptCard(d);
    var mini = el("div", "mk-dept-mini", esc((L || LABELS.he).rep));
    var btn = el("button", null, esc(d.name)); btn.type = "button";
    btn.addEventListener("click", function () { mini.replaceWith(deptCard(d)); self.scroll(); });
    mini.appendChild(btn);
    return mini;
  };

  // ---------- שאלות נפוצות: תשובות שהוכנו ונבדקו מראש ----------
  Chat.prototype.toggleFaq = function (show) {
    var open = show === undefined ? this.faq.hidden : show;
    this.faq.hidden = !open;
    this.log.hidden = open;
    this.faqBtn.setAttribute("aria-pressed", String(open));
    if (open && !this.faqLoaded) this.loadFaq();
  };

  Chat.prototype.loadFaq = function () {
    var self = this;
    this.faqLoaded = true;
    this.faq.innerHTML = '<p class="mk-faq-loading">טוען…</p>';
    fetch(BASE + "/faq.json")
      .then(function (r) { return r.json(); })
      .then(function (data) { self.renderFaq(data); })
      .catch(function () {
        self.faqLoaded = false;
        self.faq.innerHTML = '<p class="mk-error">לא הצלחתי לטעון את השאלות הנפוצות.</p>';
      });
  };

  Chat.prototype.renderFaq = function (data) {
    var self = this;
    this.faq.innerHTML = "";
    var head = el("div", "mk-faq-head");
    head.appendChild(el("b", null, "שאלות נפוצות"));
    var back = el("button", "mk-back", ICON.back + "<span>חזרה לשיחה</span>"); back.type = "button";
    back.addEventListener("click", function () { self.toggleFaq(false); self.input.focus(); });
    head.appendChild(back);
    this.faq.appendChild(head);
    this.faq.appendChild(el("p", "mk-faq-intro",
      "התשובות הוכנו מראש מתוך האתר ונבדקו, עם המקור והמשפט המודגש."));

    data.topics.forEach(function (topic) {
      self.faq.appendChild(el("div", "mk-faq-topic", esc(topic.name)));
      topic.items.forEach(function (item) {
        var d = el("details", "mk-faq-item");
        d.appendChild(el("summary", null, esc(item.question)));
        var body = el("div", "mk-faq-body");
        body.appendChild(el("div", "mk-bubble", formatAnswer(item.answer)));
        if (item.sources && item.sources.length) body.appendChild(sourcesBlock(item.sources));
        d.appendChild(body);
        self.faq.appendChild(d);
      });
    });
  };

  // ---------- הרכבה בדף ----------
  // בועה בפינה (כמו באתרים אמיתיים). data-open="auto": החלון נפתח לבד אחרי רגע (במחשב),
  // ובטלפון מופיעה רק בועית "יש לך שאלה?" - כדי לא להסתיר את כל המסך.
  function mountFloating() {
    var launcher = el("button", "mk mk-auto-theme mk-launcher", orb());
    launcher.type = "button"; launcher.setAttribute("aria-label", "פתיחת הצ'אט");
    launcher.setAttribute("aria-expanded", "false");
    if (opts.color) launcher.style.setProperty("--mk-accent", opts.color);
    var box = el("div", "mk-float"); box.hidden = true;
    document.body.appendChild(launcher); document.body.appendChild(box);
    var chat = null, tip = null;
    function hideTip() { if (tip) { tip.remove(); tip = null; } }
    function toggle(show) {
      hideTip();
      box.hidden = !show;
      launcher.setAttribute("aria-expanded", String(show));
      document.documentElement.classList.toggle("mk-chat-open", show);   // הדף יכול לפנות מקום לחלון
      if (show && !chat) {
        chat = new Chat(box);
        chat.orbs.push(launcher.querySelector(".mk-orb"));
        chat.closeBtn.hidden = false;
        chat.closeBtn.addEventListener("click", function () { toggle(false); launcher.focus(); });
      }
      if (show) {
        box.style.animation = "none"; void box.offsetWidth; box.style.animation = "";   // אנימציית פתיחה בכל פעם
        if (window.innerWidth > 520) chat.input.focus();
      }
    }
    launcher.addEventListener("click", function () { toggle(box.hidden); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !box.hidden) toggle(false); });

    if (opts.open === "auto") {
      setTimeout(function () {
        if (window.innerWidth > 520) { toggle(true); return; }
        tip = el("div", "mk mk-auto-theme mk-tip", "יש לך שאלה? אפשר לשאול כאן");
        tip.addEventListener("click", function () { toggle(true); });
        document.body.appendChild(tip);
      }, 900);
    }
    return { open: function () { toggle(true); } };
  }

  function start() {
    var target = opts.mount && document.querySelector(opts.mount);
    window.Makor = target ? { chat: new Chat(target) } : mountFloating();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
