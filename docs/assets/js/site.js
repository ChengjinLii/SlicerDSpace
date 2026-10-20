/* SlicerDDSurfer project site. Small vanilla script. Everything here is an enhancement:
   the page is complete without it. */
(function () {
  'use strict';

  var reduceMotion = window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- The js class ----------
     This file sets it, not an inline script in the page, so a page whose script fails to load keeps every
     section and the full nav visible. Sections already on screen are marked shown first, so they do not
     blink when the hidden state starts to apply. */
  Array.prototype.forEach.call(document.querySelectorAll('.reveal'), function (el) {
    var r = el.getBoundingClientRect();
    if (r.top < (window.innerHeight || document.documentElement.clientHeight) && r.bottom > 0) {
      el.classList.add('in');
    }
  });
  document.documentElement.classList.add('js');

  /* ---------- Section reveal (fade and rise once) ---------- */
  function initReveal() {
    var items = Array.prototype.slice.call(document.querySelectorAll('.reveal'));
    if (!items.length) { return; }
    if (reduceMotion || !('IntersectionObserver' in window)) {
      items.forEach(function (el) { el.classList.add('in'); });
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('in');
          io.unobserve(entry.target);
        }
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.05 });
    items.forEach(function (el) { io.observe(el); });
  }

  /* ---------- Mobile menu ---------- */
  function initMenu() {
    var btn = document.getElementById('menu-btn');
    var nav = document.getElementById('site-nav');
    if (!btn || !nav) { return; }

    function setOpen(open, returnFocus) {
      nav.classList.toggle('open', open);
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      if (!open && returnFocus) { btn.focus(); }
    }
    btn.addEventListener('click', function () {
      setOpen(btn.getAttribute('aria-expanded') !== 'true');
    });
    nav.addEventListener('click', function (e) {
      if (e.target.closest && e.target.closest('a')) { setOpen(false); }
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && btn.getAttribute('aria-expanded') === 'true') {
        setOpen(false, true);
      }
    });
    /* Tab out of the open menu closes it, so focus never sits on controls under the panel. Only a move to a known
       element counts: a focus change to nothing does not close it (relatedTarget null, e.g. a tap on the status chip
       or on plain text). */
    function onFocusOut(e) {
      var to = e.relatedTarget;
      if (btn.getAttribute('aria-expanded') === 'true' && to && to !== btn && !nav.contains(to)) {
        setOpen(false);
      }
    }
    nav.addEventListener('focusout', onFocusOut);
    btn.addEventListener('focusout', onFocusOut);
    /* Leaving the narrow layout closes the menu state. */
    if (window.matchMedia) {
      var mq = window.matchMedia('(min-width: 1024px)');
      var onChange = function () { if (mq.matches) { setOpen(false); } };
      if (mq.addEventListener) { mq.addEventListener('change', onChange); }
      else if (mq.addListener) { mq.addListener(onChange); }
    }
  }

  /* ---------- Current section in the nav ---------- */
  function initScrollSpy() {
    if (!('IntersectionObserver' in window)) { return; }
    var links = Array.prototype.slice.call(document.querySelectorAll('.site-nav li a'));
    var map = {};
    links.forEach(function (a) { map[a.getAttribute('href').slice(1)] = a; });
    var visible = {};
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) { visible[entry.target.id] = entry.isIntersecting; });
      var current = null;
      Object.keys(map).forEach(function (id) { if (visible[id]) { current = id; } });
      links.forEach(function (a) { a.removeAttribute('aria-current'); });
      if (current) { map[current].setAttribute('aria-current', 'true'); }
    }, { rootMargin: '-35% 0px -55% 0px', threshold: 0 });
    Object.keys(map).forEach(function (id) {
      var el = document.getElementById(id);
      if (el) { io.observe(el); }
    });
  }

  /* ---------- Film: play button ---------- */
  function initFilm() {
    var video = document.getElementById('film-video');
    var frame = document.getElementById('film-frame');
    if (!video || !frame) { return; }

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'film-play';
    btn.innerHTML =
      '<span class="play-circle" aria-hidden="true">' +
      '<svg viewBox="0 0 24 24" width="30" height="30" focusable="false"><path d="M6 3.5v17l14-8.5z" fill="currentColor"></path></svg>' +
      '</span><span class="play-label"></span>';
    var label = btn.querySelector('.play-label');

    function show(text) {
      label.textContent = text;
      btn.setAttribute('aria-label', text + ' (SlicerDDSurfer film)');
      btn.hidden = false;
    }
    function start() {
      btn.hidden = true;
      video.setAttribute('controls', '');
      var p = video.play();
      if (p && typeof p.catch === 'function') {
        p.catch(function () { /* the native controls stay for a manual start */ });
      }
    }

    video.removeAttribute('controls');
    frame.appendChild(btn);
    show('Play film · 1:05');

    btn.addEventListener('click', function () {
      if (video.ended) { video.currentTime = 0; }
      start();
      video.focus({ preventScroll: true });
    });
    video.addEventListener('ended', function () {
      /* Without controls the video cannot hold focus, so focus would fall to <body>. If the video had it, move it to
         the play button; focus anywhere else (a control, or <body> after a click on plain text) stays where it is. */
      var hadFocus = document.activeElement === video;
      video.removeAttribute('controls');
      show('Play again');
      if (hadFocus) { btn.focus({ preventScroll: true }); }
    });

    /* Hero button: scroll to the film and start it. */
    var heroBtn = document.querySelector('[data-play-film]');
    if (heroBtn) {
      heroBtn.addEventListener('click', function (e) {
        e.preventDefault();
        var target = document.getElementById('film');
        if (target) {
          target.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
          if (history.replaceState) { history.replaceState(null, '', '#film'); }
        }
        if (video.paused) {
          if (video.ended) { video.currentTime = 0; }
          start();
        }
      });
    }
  }

  /* ---------- Copy buttons ---------- */
  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.top = '-1000px';
      document.body.appendChild(ta);
      ta.select();
      var ok = false;
      try { ok = document.execCommand('copy'); } catch (err) { ok = false; }
      document.body.removeChild(ta);
      if (ok) { resolve(); } else { reject(new Error('copy failed')); }
    });
  }

  function initCopy() {
    Array.prototype.forEach.call(document.querySelectorAll('[data-code]'), function (box) {
      var btn = box.querySelector('.copy');
      var code = box.querySelector('pre code');
      if (!btn || !code) { return; }
      btn.hidden = false;
      var timer = null;
      btn.addEventListener('click', function () {
        copyText(code.textContent).then(function () {
          btn.textContent = 'Copied';
        }, function () {
          btn.textContent = 'Press Ctrl+C';
          var range = document.createRange();
          range.selectNodeContents(code);
          var sel = window.getSelection();
          sel.removeAllRanges();
          sel.addRange(range);
        });
        clearTimeout(timer);
        timer = setTimeout(function () { btn.textContent = 'Copy'; }, 2000);
      });
    });
  }

  function init() {
    initReveal();
    initMenu();
    initScrollSpy();
    initFilm();
    initCopy();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
