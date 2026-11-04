/* ===== 新建任务页：召唤助理后的对话入口（输入框底部展示所选助理，+ 内切换助理） ===== */
window.__pages['D-AT-NEWTASK'] = function (container) {
  var store = window.__store;
  var me = window.__roleUser();

  function nowStr() {
    var d = new Date();
    function p(n) { return n < 10 ? '0' + n : '' + n; }
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
  }

  var state = store.session;
  if (!state) {
    state = store.session = { assistantId: null, title: '新建任务', at: nowStr(), messages: [] };
  }
  if (!state.messages) state.messages = [];

  /* 可召唤的助理：我的助理（已共享 / 未共享 / 待审批）+ 平台预置 + 已订阅的共享助理 */
  function available() {
    return store.assistants.filter(function (e) {
      if (e.source === 'platform') return true;
      if (e.source === 'custom' || e.source === 'thirdparty') {
        return e.owner === me.name && e.status !== 'offline' && e.status !== 'offline_pending';
      }
      return e.subscribed;
    });
  }

  function findAssistant(id) {
    return store.assistants.filter(function (e) { return e.id === id; })[0] || null;
  }

  function current() { return findAssistant(state.assistantId); }

  container.innerHTML =
    '<div class="nt-wrap">' +
      '<div class="nt-head">' +
        '<div>' +
          '<div class="page-title">新建任务</div>' +
          '<div class="page-subtitle">先选择一位助理，再描述你的问题；助理会按提示词、技能与知识库作答。</div>' +
        '</div>' +
        '<button class="btn btn-default" id="btnToList">' + window.Icon('icon-users') + '助理列表</button>' +
      '</div>' +
      '<div class="nt-body" id="ntBody"></div>' +
      '<div class="nt-composer">' +
        '<div class="nt-card">' +
          '<textarea class="nt-input" id="ntInput" rows="2" placeholder="给助理发送消息，Enter 发送 / Shift + Enter 换行"></textarea>' +
          '<div class="nt-bar">' +
            '<div class="nt-bar-left">' +
              '<button class="nt-plus" id="btnPlus" title="选择助理">' + window.Icon('icon-plus') + '</button>' +
              '<div class="nt-select" id="ntSelect"></div>' +
              '<div class="nt-picker" id="ntPicker"></div>' +
            '</div>' +
            '<button class="btn btn-primary" id="btnSend">' + window.Icon('icon-send') + '发送</button>' +
          '</div>' +
        '</div>' +
        '<div class="nt-tip">当前为原型演示：回复为模拟内容；切换助理会开启新的任务。</div>' +
      '</div>' +
    '</div>';

  var bodyEl = container.querySelector('#ntBody');
  var chipEl = container.querySelector('#ntSelect');
  var pickerEl = container.querySelector('#ntPicker');
  var inputEl = container.querySelector('#ntInput');

  /* ---------- 输入框底部：已选助理 ---------- */
  function renderChip() {
    var a = current();
    if (!a) {
      chipEl.innerHTML = '<span class="nt-select-empty">未选择助理 · 点击左侧 + 选择</span>';
      return;
    }
    chipEl.innerHTML =
      '<span class="nt-avatar" style="background:' + (a.color || '#3685F2') + '">' + window.esc(a.avatar || a.name.slice(0, 1)) + '</span>' +
      '<span class="nt-select-name">' + window.esc(a.name) + '</span>' +
      '<span class="nt-select-ver">' + window.esc(a.version || 'v1.0') + '</span>' +
      '<span class="nt-select-x" id="chipClear">' + window.Icon('icon-x') + '</span>';
    var clear = chipEl.querySelector('#chipClear');
    if (clear) {
      clear.addEventListener('click', function () {
        state.assistantId = null;
        state.title = '新建任务';
        window.__renderTasks();
        renderChip();
        renderBody();
      });
    }
  }

  /* ---------- “+” 选择助理 ---------- */
  function renderPicker(keyword) {
    var kw = (keyword || '').trim();
    var list = available().filter(function (a) {
      return !kw || a.name.indexOf(kw) >= 0 || (a.tags || []).some(function (t) { return t.indexOf(kw) >= 0; });
    });
    function group(title, arr) {
      if (!arr.length) return '';
      return '<div class="nt-picker-group">' + title + '</div>' + arr.map(function (a) {
        return '<div class="nt-picker-item' + (a.id === state.assistantId ? ' active' : '') + '" data-pick="' + a.id + '">' +
          '<span class="nt-avatar" style="background:' + (a.color || '#3685F2') + '">' + window.esc(a.avatar || a.name.slice(0, 1)) + '</span>' +
          '<span class="nt-picker-name">' + window.esc(a.name) + '</span>' +
          '<span class="nt-picker-meta">' + window.esc(a.source === 'platform' ? '平台预置' : a.source === 'shared' ? '共享自' + a.owner : '我的助理') + '</span>' +
          '</div>';
      }).join('');
    }
    pickerEl.innerHTML =
      '<div class="nt-picker-search">' + window.Icon('icon-search') +
        '<input id="pickKw" placeholder="搜索助理名称或标签" value="' + window.esc(kw) + '"></div>' +
      '<div class="nt-picker-list">' +
        (list.length
          ? group('我的助理', list.filter(function (a) { return a.source === 'custom'; })) +
            group('共享助理', list.filter(function (a) { return a.source === 'shared'; })) +
            group('平台预置', list.filter(function (a) { return a.source === 'platform'; }))
          : '<div class="nt-picker-empty">没有匹配的助理</div>') +
      '</div>' +
      '<div class="nt-picker-foot"><span class="nt-picker-add" id="pickAdd">' + window.Icon('icon-plus') + '去助理列表添加助理</span></div>';

    pickerEl.querySelectorAll('[data-pick]').forEach(function (el) {
      el.addEventListener('click', function () { selectAssistant(el.getAttribute('data-pick')); });
    });
    pickerEl.querySelector('#pickAdd').addEventListener('click', function () {
      pickerEl.classList.remove('show');
      window.__switchPage('D-AT-LIST');
    });
    var kwEl = pickerEl.querySelector('#pickKw');
    kwEl.addEventListener('input', function () { renderPicker(kwEl.value); });
  }

  function selectAssistant(id) {
    var a = findAssistant(id);
    if (!a) return;
    state.assistantId = id;
    state.title = '与' + a.name + '的对话';
    state.at = nowStr();
    if (!state.messages.length) state.messages = [];
    pickerEl.classList.remove('show');
    window.__renderTasks();
    renderChip();
    renderBody();
    inputEl.focus();
  }

  /* ---------- 消息区 ---------- */
  function renderBody() {
    var a = current();
    if (!state.messages.length) {
      /* 优先使用助理配置的召唤快速问题 */
      var sugs = (a && a.quickQuestions && a.quickQuestions.length)
        ? a.quickQuestions
        : ['帮我梳理这个问题的处理路径', '按制度给出依据与条款', '输出一份可执行的清单'];
      bodyEl.innerHTML =
        '<div class="nt-hero">' +
          '<div class="nt-hero-avatar" style="background:' + (a ? (a.color || '#3685F2') : '#DDE6F2') + '">' +
            (a ? window.esc(a.avatar || a.name.slice(0, 1)) : window.Icon('icon-message', 'icon-lg')) + '</div>' +
          '<div class="nt-hero-title">' + (a ? '你好，我是' + window.esc(a.name) : '选择助理，开始一个新任务') + '</div>' +
          '<div class="nt-hero-sub">' + (a
            ? window.esc(a.desc || '直接描述你的问题，我会给出结论与依据。')
            : '点击输入框左侧的 + 选择一位助理，也可以用「助理列表」里的召唤直接开始。') + '</div>' +
          '<div class="nt-sugs">' +
            sugs.map(function (t) {
              return '<button class="nt-sug" data-sug="' + window.esc(t) + '">' + window.esc(t) + '</button>';
            }).join('') +
          '</div>' +
        '</div>';
      bodyEl.querySelectorAll('[data-sug]').forEach(function (b) {
        b.addEventListener('click', function () {
          inputEl.value = b.getAttribute('data-sug');
          inputEl.focus();
        });
      });
      return;
    }

    bodyEl.innerHTML = '<div class="nt-msgs">' + state.messages.map(function (m) {
      var who = m.me ? me : (a || { avatar: '助', color: '#3685F2' });
      return '<div class="msg' + (m.me ? ' me' : '') + '">' +
        '<div class="assistant-avatar" style="width:28px;height:28px;flex:0 0 28px;font-size:12px;background:' +
          (m.me ? '#7C8493' : (who.color || '#3685F2')) + '">' +
          (m.me ? '我' : window.esc(who.avatar || '助')) + '</div>' +
        '<div class="bubble">' + window.esc(m.text) + '</div></div>';
    }).join('') + '</div>';
    bodyEl.scrollTop = bodyEl.scrollHeight;
  }

  /* ---------- 发送 ---------- */
  function send() {
    var v = inputEl.value.trim();
    var a = current();
    if (!a) {
      window.toast('请先在 + 中选择一位助理', 'error');
      pickerEl.classList.add('show');
      renderPicker('');
      return;
    }
    if (!v) return;
    state.messages.push({ me: true, text: v });
    state.at = nowStr();
    inputEl.value = '';
    renderBody();
    renderChip();
    setTimeout(function () {
      state.messages.push({
        me: false,
        text: '（模拟回复）已收到你的问题：「' + v + '」。\n' +
          '我将按「' + a.name + '」的配置处理：先检索关联知识库（' +
          ((a.kbs || []).length ? a.kbs.length + ' 个' : '未配置') + '），再结合技能与连接器给出结论与依据。\n' +
          '涉及制度条款会附来源；无法确认的问题会提示「需人工确认」。'
      });
      renderBody();
    }, 600);
  }

  container.querySelector('#btnSend').addEventListener('click', send);
  container.querySelector('#btnToList').addEventListener('click', function () { window.__switchPage('D-AT-LIST'); });

  container.querySelector('#btnPlus').addEventListener('click', function (e) {
    e.stopPropagation();
    var willShow = !pickerEl.classList.contains('show');
    pickerEl.classList.toggle('show', willShow);
    if (willShow) {
      renderPicker('');
      var kwEl = pickerEl.querySelector('#pickKw');
      if (kwEl) kwEl.focus();
    }
  });
  document.addEventListener('click', function (e) {
    if (!pickerEl.contains(e.target) && !e.target.closest('#btnPlus')) pickerEl.classList.remove('show');
  });

  inputEl.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  });

  renderChip();
  renderBody();
  renderPicker('');
};
