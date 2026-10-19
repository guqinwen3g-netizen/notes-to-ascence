/* 一霁千山 · 阅读交互：顶栏、进度、阅读设置、记住读到哪里 */
(function () {
  var d = document.documentElement, body = document.body;
  var store = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  };
  var page = location.pathname.split('/').pop() || 'index.html';

  /* 渐显 */
  var rv = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
    }, { threshold: 0.18 });
    rv.forEach(function (el) { io.observe(el); });
  } else { rv.forEach(function (el) { el.classList.add('in'); }); }

  /* 首页：继续阅读 */
  if (body.classList.contains('home')) {
    try {
      var last = JSON.parse(store.get('as-last') || 'null');
      var r = document.querySelector('.resume');
      if (last && last.p && r && last.r > 0.02 && last.r < 0.98 && document.querySelector('a[href="' + last.p + '"]')) {
        r.href = last.p + '#resume';
        r.querySelector('span').textContent = last.t ? '：' + last.t : '';
        r.hidden = false;
      }
    } catch (e) {}
    return;
  }

  /* 阅读页 */
  var bar = document.querySelector('.bar'), prog = document.querySelector('.progress i');
  var panel = document.querySelector('.panel'), aa = document.querySelector('.aa');
  var lastY = window.scrollY, ticking = false, saveT = 0;
  var title = (document.querySelector('.bar-now') || {}).textContent || '';

  function ratio() {
    var h = d.scrollHeight - window.innerHeight;
    return h > 0 ? Math.min(1, Math.max(0, window.scrollY / h)) : 0;
  }
  function update() {
    ticking = false;
    var y = window.scrollY;
    if (prog) prog.style.transform = 'scaleX(' + ratio() + ')';
    if (bar) {
      bar.classList.toggle('solid', y > 40);
      var goingDown = y > lastY + 4, goingUp = y < lastY - 4;
      if (y < 80 || goingUp) bar.classList.remove('away');
      else if (goingDown && panel && panel.hidden) bar.classList.add('away');
    }
    lastY = y;
    var now = Date.now();
    if (now - saveT > 800) { saveT = now; store.set('as-last', JSON.stringify({ p: page, t: title, r: ratio() })); }
  }
  window.addEventListener('scroll', function () { if (!ticking) { ticking = true; requestAnimationFrame(update); } }, { passive: true });
  update();

  /* 从上次读到的位置继续 */
  if (location.hash === '#resume') {
    try {
      var s = JSON.parse(store.get('as-last') || 'null');
      if (s && s.p === page) {
        var go = function () { window.scrollTo(0, s.r * (d.scrollHeight - window.innerHeight)); };
        (document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(function () { setTimeout(go, 60); });
      }
    } catch (e) {}
    history.replaceState(null, '', location.pathname);
  }

  /* 阅读设置 */
  function mark() {
    var t = d.getAttribute('data-theme') || 'paper';
    if (!panel) return;
    panel.querySelectorAll('[data-theme]').forEach(function (b) { b.classList.toggle('on', b.getAttribute('data-theme') === t); });
    var m = document.querySelector('meta[name="theme-color"]');
    if (m) m.setAttribute('content', t === 'night' ? '#1B1A18' : '#FBFAF7');
  }
  if (aa && panel) {
    aa.addEventListener('click', function (e) { e.stopPropagation(); panel.hidden = !panel.hidden; bar.classList.remove('away'); });
    document.addEventListener('click', function (e) { if (!panel.hidden && !panel.contains(e.target)) panel.hidden = true; });
    panel.addEventListener('click', function (e) {
      var b = e.target.closest('button'); if (!b) return;
      if (b.hasAttribute('data-size')) {
        var keep = ratio();
        var cur = parseInt(d.getAttribute('data-size') || '3', 10);
        var n = Math.min(5, Math.max(1, cur + parseInt(b.getAttribute('data-size'), 10)));
        d.setAttribute('data-size', n); store.set('as-size', n);
        window.scrollTo(0, keep * (d.scrollHeight - window.innerHeight));
      }
      if (b.hasAttribute('data-theme')) {
        var t = b.getAttribute('data-theme');
        d.setAttribute('data-theme', t); store.set('as-theme', t); mark();
      }
    });
    mark();
  }

  /* 键盘翻页 */
  document.addEventListener('keydown', function (e) {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    var a = e.key === 'ArrowLeft' ? document.querySelector('a[rel="prev"]') : e.key === 'ArrowRight' ? document.querySelector('a[rel="next"]') : null;
    if (a) location.href = a.href;
    if (e.key === 'Escape' && panel) panel.hidden = true;
  });
})();
