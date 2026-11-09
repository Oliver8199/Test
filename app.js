(() => {
  'use strict';

  const DEFAULTS = { work: 25, short: 5, long: 15, interval: 4, autoStart: false, sound: true, notify: false };
  const LABELS = { work: '作業中', short: '短い休憩', long: '長い休憩' };
  const SETTINGS_KEY = 'pomodoro.settings';
  const STATS_KEY = 'pomodoro.stats';

  const $ = (id) => document.getElementById(id);
  const els = {
    time: $('time'), label: $('label'), ring: $('ring'), toggle: $('toggle'),
    reset: $('reset'), skip: $('skip'), count: $('count'), dots: $('dots'),
    form: $('settings-form'), modes: document.querySelectorAll('.mode'),
  };

  const load = (key, fallback) => {
    try { return { ...fallback, ...JSON.parse(localStorage.getItem(key) || '{}') }; }
    catch { return { ...fallback }; }
  };
  const save = (key, value) => {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* ignore */ }
  };

  const today = () => new Date().toISOString().slice(0, 10);

  let settings = load(SETTINGS_KEY, DEFAULTS);
  let stats = load(STATS_KEY, { date: today(), count: 0, streak: 0 });
  if (stats.date !== today()) stats = { date: today(), count: 0, streak: 0 };

  const state = {
    mode: 'work',
    remaining: settings.work * 60 * 1000, // ms
    endAt: null,                          // timestamp while running
    tickId: null,
  };

  // ---- Ring setup ----
  const R = 54;
  const CIRC = 2 * Math.PI * R;
  els.ring.style.strokeDasharray = CIRC;

  const durationOf = (mode) => settings[mode] * 60 * 1000;
  const isRunning = () => state.endAt !== null;

  function format(ms) {
    const total = Math.max(0, Math.ceil(ms / 1000));
    const m = String(Math.floor(total / 60)).padStart(2, '0');
    const s = String(total % 60).padStart(2, '0');
    return `${m}:${s}`;
  }

  function render() {
    const remaining = isRunning() ? state.endAt - Date.now() : state.remaining;
    const text = format(remaining);
    const progress = 1 - Math.max(0, remaining) / durationOf(state.mode);

    els.time.textContent = text;
    els.label.textContent = LABELS[state.mode];
    els.ring.style.strokeDashoffset = CIRC * progress;
    els.toggle.textContent = isRunning() ? '一時停止' : (state.remaining < durationOf(state.mode) ? '再開' : '開始');
    document.body.dataset.mode = state.mode;
    document.title = `${text} - ${LABELS[state.mode]}`;
    els.modes.forEach((b) => b.setAttribute('aria-selected', String(b.dataset.mode === state.mode)));

    els.count.textContent = stats.count;
    els.dots.innerHTML = '';
    const cycleFull = stats.streak > 0 && stats.streak % settings.interval === 0;
    const filled = cycleFull ? settings.interval : stats.streak % settings.interval;
    for (let i = 0; i < settings.interval; i++) {
      const d = document.createElement('span');
      d.className = 'dot' + (i < filled ? ' on' : '');
      els.dots.appendChild(d);
    }
  }

  function tick() {
    if (state.endAt - Date.now() <= 0) {
      complete();
    } else {
      render();
    }
  }

  function start() {
    if (isRunning()) return;
    state.endAt = Date.now() + state.remaining;
    state.tickId = setInterval(tick, 250);
    unlockAudio();
    render();
  }

  function pause() {
    if (!isRunning()) return;
    state.remaining = Math.max(0, state.endAt - Date.now());
    state.endAt = null;
    clearInterval(state.tickId);
    render();
  }

  function stopTimer() {
    state.endAt = null;
    clearInterval(state.tickId);
  }

  function setMode(mode) {
    stopTimer();
    state.mode = mode;
    state.remaining = durationOf(mode);
    render();
  }

  function nextMode() {
    if (state.mode !== 'work') return 'work';
    return stats.streak > 0 && stats.streak % settings.interval === 0 ? 'long' : 'short';
  }

  function complete(skipped = false) {
    const finished = state.mode;
    stopTimer();

    if (finished === 'work' && !skipped) {
      stats.count += 1;
      stats.streak += 1;
      save(STATS_KEY, stats);
    }
    if (finished === 'long') { stats.streak = 0; save(STATS_KEY, stats); }

    if (!skipped) {
      if (settings.sound) beep();
      notify(finished === 'work' ? '作業終了！休憩しましょう。' : '休憩終了！作業を再開しましょう。');
    }

    setMode(nextMode());
    if (settings.autoStart && !skipped) start();
  }

  function reset() {
    setMode(state.mode);
  }

  // ---- Sound (Web Audio, no external file) ----
  let audioCtx = null;
  function unlockAudio() {
    if (!settings.sound) return;
    try {
      audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      if (audioCtx.state === 'suspended') audioCtx.resume();
    } catch { /* ignore */ }
  }
  function beep() {
    unlockAudio();
    if (!audioCtx) return;
    const now = audioCtx.currentTime;
    [0, 0.35, 0.7].forEach((offset) => {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'sine';
      osc.frequency.value = 880;
      gain.gain.setValueAtTime(0.0001, now + offset);
      gain.gain.exponentialRampToValueAtTime(0.3, now + offset + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + offset + 0.3);
      osc.connect(gain).connect(audioCtx.destination);
      osc.start(now + offset);
      osc.stop(now + offset + 0.32);
    });
  }

  // ---- Notifications ----
  function notify(body) {
    if (!settings.notify || !('Notification' in window)) return;
    if (Notification.permission === 'granted') {
      try { new Notification('ポモドーロタイマー', { body }); } catch { /* ignore */ }
    }
  }

  // ---- Settings form ----
  function fillForm() {
    const f = els.form.elements;
    ['work', 'short', 'long', 'interval'].forEach((k) => { f[k].value = settings[k]; });
    ['autoStart', 'sound', 'notify'].forEach((k) => { f[k].checked = settings[k]; });
  }

  els.form.addEventListener('submit', (e) => {
    e.preventDefault();
    const f = els.form.elements;
    const num = (k) => Math.max(1, parseInt(f[k].value, 10) || DEFAULTS[k]);
    settings = {
      work: num('work'), short: num('short'), long: num('long'), interval: num('interval'),
      autoStart: f.autoStart.checked, sound: f.sound.checked, notify: f.notify.checked,
    };
    save(SETTINGS_KEY, settings);
    if (settings.notify && 'Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
    if (!isRunning()) setMode(state.mode); else render();
  });

  // ---- Events ----
  els.toggle.addEventListener('click', () => (isRunning() ? pause() : start()));
  els.reset.addEventListener('click', reset);
  els.skip.addEventListener('click', () => complete(true));
  els.modes.forEach((b) => b.addEventListener('click', () => setMode(b.dataset.mode)));

  document.addEventListener('keydown', (e) => {
    if (e.target.matches('input, textarea')) return;
    if (e.code === 'Space') { e.preventDefault(); isRunning() ? pause() : start(); }
    else if (e.key === 'r' || e.key === 'R') reset();
    else if (e.key === 's' || e.key === 'S') complete(true);
  });

  fillForm();
  render();
})();
