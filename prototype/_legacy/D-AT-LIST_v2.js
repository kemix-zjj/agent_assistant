/* ===== 助理列表：创建（手动 / 已有接入）、共享、下架、版本管理、授权范围、审批 ===== */
window.__pages['D-AT-LIST'] = function (container) {
  var store = window.__store;
  var S = window.__atState || (window.__atState = {
    scope: 'all',
    category: '全部',
    keyword: '',
    statusFilter: 'all',
    subFilter: 'all',
    selected: {},
    expandedReject: {}
  });

  var STATUS = {
    unshared: { cls: 'default', text: '未共享' },
    pending: { cls: 'warning', text: '待审批' },
    approved: { cls: 'success', text: '已共享' },
    rejected: { cls: 'error', text: '已拒绝' },
    offline_pending: { cls: 'warning', text: '下架审批中' },
    offline: { cls: 'gray', text: '已下架' },
    platform: { cls: 'default', text: '平台预置' }
  };
  var CATS = ['全部'].concat(store.categories);

  /* ---------- 基础工具 ---------- */
  function me() { return window.__roleUser(); }
  function nowStr() {
    var d = new Date();
    function p(n) { return n < 10 ? '0' + n : '' + n; }
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
  }
  function statusTag(e) {
    /* 共享助理没有共享状态，展示订阅状态 */
    if (e.source === 'shared') {
      return window.Tag(e.subscribed ? 'success' : 'default', e.subscribed ? '已订阅' : '已移除');
    }
    var s = STATUS[e.status] || STATUS.unshared;
    return window.Tag(s.cls, s.text);
  }
  function verTag(e) {
    return e.version ? '<span class="ver-tag">' + window.esc(e.version) + '</span>' : '';
  }
  /* 自建与第三方接入的助理都归创建人所有 */
  function isMine(e) {
    return (e.source === 'custom' || e.source === 'thirdparty') && e.owner === me().name;
  }
  function nameOf(catalog, ids) {
    return (ids || []).map(function (id) {
      var hit = catalog.filter(function (x) { return x.id === id; })[0];
      return hit ? hit.name : id;
    }).join('、') || '未配置';
  }

  /* ---------- 数据切片 ---------- */
  function myAssistants() { return store.assistants.filter(isMine); }
  function sharedAssistants() { return store.assistants.filter(function (e) { return e.source === 'shared'; }); }
  function allAssistants() {
    return store.assistants.filter(function (e) {
      if (e.source === 'platform') return true;
      if (e.source === 'custom' || e.source === 'thirdparty') return e.owner === me().name;
      return e.subscribed;
    });
  }
  function scopeList() {
    if (S.scope === 'mine') return myAssistants();
    if (S.scope === 'shared') return sharedAssistants();
    return allAssistants();
  }
  function filtered() {
    return scopeList().filter(function (e) {
      if (S.category !== '全部' && e.category !== S.category) return false;
      if (S.keyword) {
        var k = S.keyword.toLowerCase();
        var hit = (e.name || '').toLowerCase().indexOf(k) >= 0 ||
          (e.tags || []).some(function (t) { return t.toLowerCase().indexOf(k) >= 0; });
        if (!hit) return false;
      }
      if (S.scope === 'mine' && S.statusFilter !== 'all' && e.status !== S.statusFilter) return false;
      if (S.scope === 'shared') {
        if (S.subFilter === 'subscribed' && !e.subscribed) return false;
        if (S.subFilter === 'removed' && e.subscribed) return false;
      }
      /* all 时不做订阅状态过滤 */
      return true;
    });
  }
  function pendingCount() {
    return store.approvals.filter(function (a) { return a.status === 'pending'; }).length;
  }

  /* ---------- 版本 / 记录 ---------- */
  function nextVersion(cur) {
    var parts = String(cur || 'v1.0').replace('v', '').split('.');
    var major = parts[0] || '1';
    var minor = (parseInt(parts[1], 10) || 0) + 1;
    return 'v' + major + '.' + minor;
  }
  function logHistory(e, version, action, remark) {
    e.history = e.history || [];
    e.history.unshift({
      version: version, action: action, operator: me().name, time: nowStr(), remark: remark || ''
    });
  }
  function pushApproval(payload) {
    store.approvals.push(payload);
  }

  /* ---------- 页面骨架 ---------- */
  var headActions =
    (window.__isAdmin()
      ? '<button class="btn btn-default" id="btnApproval">' + window.Icon('icon-share') + '审批中心' +
        (pendingCount() ? '<span class="head-badge">' + pendingCount() + '</span>' : '') + '</button>'
      : '') +
    '<button class="btn btn-primary" id="btnAdd">' + window.Icon('icon-plus') + '添加助理</button>';

  container.innerHTML =
    '<div class="page-card">' +
      '<div class="page-head">' +
        '<div>' +
          '<div class="page-title">助理<span class="beta-badge">BETA</span></div>' +
          '<div class="page-subtitle">手动创建或接入第三方助理，配置提示词与能力后可共享给团队；已共享的助理支持版本管理与下架。</div>' +
        '</div>' +
        '<div class="page-head-actions">' + headActions + '</div>' +
      '</div>' +
      '<div class="scope-bar">' +
        '<div class="seg-group" id="scopeTabs">' +
          '<div class="seg" data-scope="all">全部</div>' +
          '<div class="seg" data-scope="mine">我的助理</div>' +
          '<div class="seg" data-scope="shared">共享助理</div>' +
        '</div>' +
        '<div class="scope-right">' +
          '<div class="scope-search">' + window.Icon('icon-search') +
            '<input id="kwInput" placeholder="搜索助理名称或标签" value="' + window.esc(S.keyword) + '"></div>' +
          '<select class="scope-select" id="filterSelect"></select>' +
        '</div>' +
      '</div>' +
      '<div class="cat-tabs" id="catTabs">' +
        CATS.map(function (c) {
          return '<div class="cat-tab' + (S.category === c ? ' active' : '') + '" data-cat="' + c + '">' + c + '</div>';
        }).join('') +
      '</div>' +
      '<div class="list-meta">' +
        '<span id="metaText"></span>' +
        '<div class="sel-bar" id="selBar">已选 <span class="count-num" id="selCount">0</span> 个助理' +
          '<button class="btn btn-primary" id="btnShare">' + window.Icon('icon-share') + '共享</button>' +
          '<button class="btn btn-text" id="btnClearSel">清空</button></div>' +
      '</div>' +
      '<div class="assistant-grid" id="grid"></div>' +
    '</div>';

  /* ---------- 顶部事件 ---------- */
  container.querySelectorAll('#scopeTabs .seg').forEach(function (el) {
    el.addEventListener('click', function () {
      S.scope = el.getAttribute('data-scope');
      S.selected = {};
      if (S.scope !== 'mine') S.statusFilter = 'all';
      if (S.scope === 'shared') S.subFilter = 'all';
      paint();
    });
  });
  container.querySelectorAll('#catTabs .cat-tab').forEach(function (el) {
    el.addEventListener('click', function () {
      S.category = el.getAttribute('data-cat');
      container.querySelectorAll('#catTabs .cat-tab').forEach(function (t) { t.classList.toggle('active', t === el); });
      paint();
    });
  });
  var kwTimer = null;
  container.querySelector('#kwInput').addEventListener('input', function (e) {
    clearTimeout(kwTimer);
    var v = e.target.value.trim();
    kwTimer = setTimeout(function () { S.keyword = v; paint(); }, 200);
  });
  container.querySelector('#filterSelect').addEventListener('change', function (e) {
    if (S.scope === 'mine') S.statusFilter = e.target.value;
    else if (S.scope === 'shared') S.subFilter = e.target.value;
    paint();
  });
  container.querySelector('#btnAdd').addEventListener('click', function () { openCreateChooser(); });
  var btnApproval = container.querySelector('#btnApproval');
  if (btnApproval) btnApproval.addEventListener('click', function () { openApprovalList(); });

  container.querySelector('#btnShare').addEventListener('click', function () {
    var ids = Object.keys(S.selected).filter(function (k) { return S.selected[k]; });
    if (!ids.length) { window.toast('请先勾选需要共享的助理', 'error'); return; }
    openShare(ids, null);
  });
  container.querySelector('#btnClearSel').addEventListener('click', function () {
    S.selected = {};
    paint();
  });

  /* ---------- 渲染 ---------- */
  paint();

  function paint() {
    container.querySelectorAll('#scopeTabs .seg').forEach(function (el) {
      el.classList.toggle('active', el.getAttribute('data-scope') === S.scope);
    });

    var fs = container.querySelector('#filterSelect');
    if (S.scope === 'mine') {
      fs.style.display = '';
      fs.innerHTML = '<option value="all">状态：全部</option><option value="unshared">状态：未共享</option>' +
        '<option value="pending">状态：待审批</option><option value="approved">状态：已共享</option>' +
        '<option value="rejected">状态：已拒绝</option><option value="offline_pending">状态：下架审批中</option>' +
        '<option value="offline">状态：已下架</option>';
      fs.value = S.statusFilter;
    } else if (S.scope === 'shared') {
      fs.style.display = '';
      fs.innerHTML = '<option value="all">订阅状态：全部</option>' +
        '<option value="subscribed">状态：已订阅</option><option value="removed">状态：已移除</option>';
      fs.value = S.subFilter;
    } else {
      fs.style.display = 'none';
    }

    var list = filtered();
    var grid = container.querySelector('#grid');
    grid.innerHTML = list.length ? list.map(cardHtml).join('') : emptyHtml();

    var scopeName = S.scope === 'mine' ? '我的助理' : S.scope === 'shared' ? '共享助理' : '助理';
    container.querySelector('#metaText').textContent = '共 ' + list.length + ' 个' + scopeName + ' · 点击卡片标题查看详情';
    var selIds = Object.keys(S.selected).filter(function (k) { return S.selected[k]; });
    var selBar = container.querySelector('#selBar');
    selBar.classList.toggle('show', S.scope === 'mine' && selIds.length > 0);
    container.querySelector('#selCount').textContent = selIds.length;

    bindCards();
  }

  function emptyHtml() {
    if (S.scope === 'mine') {
      return '<div class="empty-state"><div class="empty-icon">' + window.Icon('icon-users', 'icon-lg') + '</div>' +
        '<div class="empty-state-text">' + (S.keyword || S.category !== '全部' || S.statusFilter !== 'all'
          ? '没有符合条件的助理，试试调整筛选条件'
          : '你还没有创建助理，点击右上角「添加助理」开始') + '</div></div>';
    }
    if (S.scope === 'shared') {
      return '<div class="empty-state"><div class="empty-icon">' + window.Icon('icon-share', 'icon-lg') + '</div>' +
        '<div class="empty-state-text">' + (S.subFilter === 'removed'
          ? '没有已移除的共享助理'
          : S.subFilter === 'subscribed' ? '暂无已订阅的共享助理' : '暂无共享给你的助理') + '</div></div>';
    }
    return '<div class="empty-state"><div class="empty-icon">' + window.Icon('icon-search', 'icon-lg') + '</div>' +
      '<div class="empty-state-text">' + (S.keyword ? '未找到匹配的助理' : '暂无可用助理') + '</div></div>';
  }

  function cardHtml(e) {
    var mine = isMine(e);
    var shared = e.source === 'shared';
    var isPlatform = e.source === 'platform';
    var showCheck = mine && S.scope === 'mine' && e.status === 'unshared';
    var checked = !!S.selected[e.id];

    var tags = (e.tags || []).slice(0, 3).map(function (t) { return '<span class="mini-tag">' + window.esc(t) + '</span>'; }).join('');

    var ownerLine = shared
      ? '共享自 ' + window.esc(e.owner) + ' · ' + window.esc((e.ownerDept || '').split(' · ').pop())
      : (isPlatform
        ? '平台预置 · ' + window.esc(e.category)
        : (e.source === 'thirdparty' ? '第三方 · ' + window.esc(e.platform || '自定义接入') : window.esc(e.owner)));

    /* 操作按钮 */
    var act = [];
    if (isPlatform) {
      act.push(btn('detail', e, '详情'));
      act.push(btn('summon', e, '召唤', true));
    } else if (shared) {
      act.push(btn('detail', e, '详情'));
      act.push(e.subscribed ? btn('removeShared', e, '移除') : btn('resub', e, '重新订阅'));
      act.push(e.subscribed ? btn('summon', e, '召唤', true) : '');
    } else if (mine) {
      if (e.status === 'approved') {
        act.push(btn('scope', e, '授权范围'));
        act.push(btn('detail', e, '详情'));
        act.push(btn('offline', e, '下架', false, true));
        act.push(btn('summon', e, '召唤', true));
      } else if (e.status === 'pending') {
        act.push(btn('detail', e, '详情'));
        act.push(btn('summon', e, '召唤', true));
      } else if (e.status === 'rejected') {
        act.push(btn('detail', e, '详情'));
        act.push(btn('resubmit', e, '重新提交'));
        act.push(btn('delete', e, '删除', false, true));
      } else if (e.status === 'offline_pending') {
        act.push(btn('detail', e, '详情'));
      } else if (e.status === 'offline') {
        act.push(btn('detail', e, '详情'));
        act.push(btn('resubmit', e, '重新共享', true));
      } else {
        act.push(btn('detail', e, '详情'));
        act.push(btn('delete', e, '删除', false, true));
        act.push(btn('summon', e, '召唤', true));
      }
    }

    var rejectBar = '';
    if (mine && e.status === 'rejected') {
      var open = !!S.expandedReject[e.id];
      rejectBar = '<div class="reject-bar' + (open ? ' expanded' : '') + '">' + window.Icon('icon-alert') +
        '<span class="r-text">拒绝原因：' + window.esc(e.rejectReason || '管理员未填写拒绝原因') + '</span>' +
        '<span class="r-toggle" data-act="toggleReject" data-id="' + e.id + '">' + (open ? '收起' : '展开') + '</span></div>';
    }

    return '<div class="assistant-card' + (showCheck ? ' has-check' : '') + (checked ? ' selected' : '') + '">' +
      (showCheck ? '<label class="checkbox-item card-check"><input type="checkbox" data-check="' + e.id + '"' + (checked ? ' checked' : '') + '></label>' : '') +
      '<div class="assistant-card-top">' +
        '<div class="assistant-avatar" style="background:' + (e.color || '#3685F2') + '">' + window.esc(e.avatar || e.name.slice(0, 1)) + '</div>' +
        '<div class="assistant-name-wrap">' +
          '<div class="assistant-name" data-act="detail" data-id="' + e.id + '">' + window.esc(e.name) +
            statusTag(e) + verTag(e) + '</div>' +
          '<div class="assistant-tags">' + tags + '</div>' +
        '</div>' +
      '</div>' +
      '<div class="assistant-desc">' + window.esc((e.desc || '').slice(0, 60)) + ((e.desc || '').length > 60 ? '…' : '') + '</div>' +
      rejectBar +
      '<div class="assistant-foot"><span class="assistant-owner">' + window.Icon('icon-user') + ownerLine + '</span>' +
        '<span class="assistant-actions">' + act.join('') + '</span></div>' +
    '</div>';
  }

  function btn(act, e, label, primary, danger) {
    return '<button class="btn ' + (primary ? 'btn-primary' : danger ? 'btn-danger-text' : 'btn-text') +
      '" data-act="' + act + '" data-id="' + e.id + '">' + label + '</button>';
  }

  function bindCards() {
    container.querySelectorAll('[data-check]').forEach(function (cb) {
      cb.addEventListener('change', function () {
        S.selected[cb.getAttribute('data-check')] = cb.checked;
        paint();
      });
    });
    container.querySelectorAll('[data-act]').forEach(function (el) {
      el.addEventListener('click', function (ev) {
        ev.stopPropagation();
        var id = el.getAttribute('data-id');
        var act = el.getAttribute('data-act');
        var e = store.assistants.filter(function (x) { return x.id === id; })[0];
        if (act === 'toggleReject') {
          S.expandedReject[id] = !S.expandedReject[id];
          paint();
          return;
        }
        if (!e) return;
        if (act === 'summon') summon(e);
        if (act === 'detail') openDetail(e);
        if (act === 'delete') deleteAssistant(e);
        if (act === 'offline') requestOffline(e);
        if (act === 'scope') openScope(e);
        if (act === 'resubmit') openShare([id], e);
        if (act === 'removeShared') removeShared(e);
        if (act === 'resub') resubscribe(e);
      });
    });
  }

  /* ============================================================
   * 召唤：进入新建任务页，输入框底部带上助理
   * ============================================================ */
  function summon(a) {
    if (a.status === 'offline' || a.status === 'offline_pending') {
      window.toast('该助理已下架，无法召唤', 'error');
      return;
    }
    store.session = {
      assistantId: a.id, title: '与' + a.name + '的对话',
      at: nowStr(), messages: []
    };
    window.__renderTasks();
    window.toast('已进入新建任务，可在输入框底部查看「' + a.name + '」');
    setTimeout(function () { window.__switchPage('D-AT-NEWTASK'); }, 260);
  }

  /* ============================================================
   * 助理详情（含版本记录、授权范围、编辑入口）
   * ============================================================ */
  function openDetail(e) {
    var mine = isMine(e);
    var canEdit = mine && e.status !== 'offline_pending' && e.status !== 'offline';
    var canScope = (e.status === 'approved' || e.status === 'offline_pending') && (mine || window.__isAdmin());

    var orgNames = (e.scope && e.scope.orgs || []).map(function (id) {
      var n = window.findOrg(id); return n ? n.name : id;
    });
    var userNames = (e.scope && e.scope.users || []).map(function (id) {
      var u = window.findUser(id); return u ? u.name : id;
    });
    var scopeChips = orgNames.map(function (n) { return '<span class="scope-chip">组织 · ' + window.esc(n) + '</span>'; })
      .concat(userNames.map(function (n) { return '<span class="scope-chip">人员 · ' + window.esc(n) + '</span>'; })).join('');

    var history = (e.history || []).map(function (h) {
      return '<div class="ver-item">' +
        '<span class="ver-no">' + window.esc(h.version) + '</span>' +
        '<div class="ver-main"><div class="ver-action">' + window.esc(h.action) + '</div>' +
          '<div class="ver-meta">' + window.esc(h.operator || '') + ' · ' + window.esc(h.time || '') +
            (h.remark ? ' · ' + window.esc(h.remark) : '') + '</div></div></div>';
    }).join('') || '<div class="scope-empty">暂无版本记录</div>';

    var body =
      '<div class="detail-head">' +
        '<div class="assistant-avatar" style="width:52px;height:52px;flex:0 0 52px;font-size:20px;background:' + (e.color || '#3685F2') + '">' +
          window.esc(e.avatar || e.name.slice(0, 1)) + '</div>' +
        '<div style="flex:1;min-width:0">' +
          '<div class="detail-name">' + window.esc(e.name) + statusTag(e) + verTag(e) + '</div>' +
          '<div class="detail-meta">' + window.esc(e.category || '') + ' · ' +
            (e.source === 'platform' ? '平台预置' : e.source === 'shared' ? '共享自 ' + e.owner
              : (e.source === 'thirdparty' ? '第三方接入 · ' + (e.platform || '自定义') : '创建人 ' + e.owner)) +
            ' · 更新于 ' + window.esc(e.updateTime || e.createTime || '-') + '</div>' +
          '<div class="assistant-tags">' + (e.tags || []).map(function (t) { return '<span class="mini-tag">' + window.esc(t) + '</span>'; }).join('') + '</div>' +
        '</div>' +
      '</div>' +

      '<div class="detail-section">' +
        '<div class="detail-section-title">基础信息</div>' +
        '<div class="cap-item"><div class="cap-title">描述</div><div class="cap-body">' + window.esc(e.desc || '未填写') + '</div></div>' +
        (e.source === 'thirdparty'
          ? '<div class="cap-item"><div class="cap-title">接入信息</div><div class="cap-body">平台：' + window.esc(e.platform || '自定义') +
            '\n接入地址：' + window.esc(e.endpoint || '-') + '\nAppID：' + window.esc(e.appId || '-') + '</div></div>'
          : '') +
        (e.status === 'rejected' && e.rejectReason
          ? '<div class="reject-bar"><span class="r-text">拒绝原因：' + window.esc(e.rejectReason) + '</span></div>' : '') +
        (e.status === 'offline_pending' && e.offlineReason
          ? '<div class="notice-bar">' + window.Icon('icon-alert') + '<span>下架原因：' + window.esc(e.offlineReason) + '（等待管理员审批）</span></div>' : '') +
      '</div>' +

      '<div class="detail-section">' +
        '<div class="detail-section-title">能力组成（只读）</div>' +
        '<div class="cap-item"><div class="cap-title">提示词</div><div class="cap-body">' + window.esc(e.prompt || '未配置') + '</div></div>' +
        '<div class="cap-item"><div class="cap-title">技能</div><div class="cap-body">' + window.esc(nameOf(store.skills, e.skills)) + '</div></div>' +
        '<div class="cap-item"><div class="cap-title">连接器</div><div class="cap-body">' + window.esc(nameOf(store.mcps, e.mcps)) + '</div></div>' +
        '<div class="cap-item"><div class="cap-title">知识库</div><div class="cap-body">' + window.esc(nameOf(store.kbs, e.kbs)) + '</div></div>' +
        '<div class="cap-item"><div class="cap-title">召唤快速问题</div><div class="cap-body">' +
          (e.quickQuestions && e.quickQuestions.length
            ? '· ' + e.quickQuestions.map(function (q) { return window.esc(q); }).join('<br>· ')
            : '<span class="scope-empty">未配置</span>') +
        '</div></div>' +
      '</div>' +

      (e.status === 'approved' || e.status === 'offline_pending'
        ? '<div class="detail-section">' +
            '<div class="detail-section-title">授权范围' +
              '<button class="btn btn-text" id="btnEditScope">' + (canScope ? '修改授权范围' : '查看') + '</button></div>' +
            '<div class="scope-chips">' + (scopeChips || '<span class="scope-empty">未设置授权范围</span>') + '</div>' +
            '<div class="form-hint">已授权 ' + (e.authorizedCount || 0) + ' 个对象</div>' +
          '</div>'
        : '') +

      '<div class="detail-section">' +
        '<div class="detail-section-title">版本记录<span class="form-hint" style="margin-left:8px;font-weight:400">编辑保存会生成新版本，已共享的助理需重新审批</span></div>' +
        '<div class="ver-list">' + history + '</div>' +
      '</div>';

    var footer = (canEdit ? '<button class="btn btn-default" id="btnEdit">' + window.Icon('icon-edit') + '编辑</button>' : '') +
      '<button class="btn btn-default" data-close>关闭</button>' +
      (e.status === 'offline' || e.status === 'offline_pending' ? '' : '<button class="btn btn-primary" id="btnSummon">召唤</button>');

    window.openDrawer({
      title: '助理详情 · ' + e.name,
      width: 760,
      body: body,
      footer: footer,
      onMount: function (root, api) {
        var btnSummon = root.querySelector('#btnSummon');
        if (btnSummon) {
          btnSummon.addEventListener('click', function () {
            api.close();
            summon(e);
          });
        }
        var btnEdit = root.querySelector('#btnEdit');
        if (btnEdit) {
          btnEdit.addEventListener('click', function () {
            api.close();
            openWizard(e);
          });
        }
        var btnScope = root.querySelector('#btnEditScope');
        if (btnScope) {
          btnScope.addEventListener('click', function () {
            if (!canScope) { window.toast('仅创建人或公司管理员可修改授权范围', 'error'); return; }
            api.close();
            openScope(e);
          });
        }
      }
    });
  }

  /* ============================================================
   * 删除（仅未共享 / 已拒绝 / 已下架）
   * ============================================================ */
  function deleteAssistant(e) {
    window.confirmDialog({
      title: '确认删除该助理？',
      text: '删除后该助理将从你的助理库中永久移除，且不可恢复。',
      impact: e.status === 'pending'
        ? '该助理存在待审批的共享申请，删除后申请将被终止。'
        : '当前助理尚未共享，删除仅影响你自己。',
      okText: '确认删除',
      danger: true,
      onOk: function () {
        store.assistants = store.assistants.filter(function (x) { return x.id !== e.id; });
        store.approvals.forEach(function (a) {
          if (a.assistantId === e.id && a.status === 'pending') a.status = 'terminated';
        });
        delete S.selected[e.id];
        paint();
        window.toast('已删除「' + e.name + '」');
      }
    });
  }

  /* ============================================================
   * 下架：填写原因 → 提交申请
   * ============================================================ */
  function requestOffline(e) {
    var modal = window.openModal({
      title: '申请下架 · ' + e.name,
      width: 560,
      body:
        '<div class="notice-bar">' + window.Icon('icon-alert') +
          '<span>已共享的助理不能直接删除。提交下架申请后，管理员审批通过即从授权对象的助理库中移除。</span></div>' +
        '<div class="form-item"><label class="form-label"><span class="req">*</span>下架原因</label>' +
          '<textarea class="form-textarea" id="offlineReason" rows="4" maxlength="200" ' +
            'placeholder="请说明下架原因，例如：规则调整、内容过期、能力合并等（1-200 字）"></textarea>' +
          '<div class="input-counter"><span id="offlineCount">0</span>/200</div></div>' +
        '<div class="form-hint">当前版本：' + window.esc(e.version || 'v1.0') + ' · 授权对象 ' + (e.authorizedCount || 0) + ' 个</div>',
      footer: '<button class="btn btn-default" data-close>取消</button>' +
        '<button class="btn btn-danger" id="offlineOk" disabled>提交下架申请</button>',
      onMount: function (root, api) {
        var ta = root.querySelector('#offlineReason');
        var ok = root.querySelector('#offlineOk');
        ta.addEventListener('input', function () {
          root.querySelector('#offlineCount').textContent = ta.value.length;
          ok.disabled = ta.value.trim().length === 0;
        });
        ta.focus();
        ok.addEventListener('click', function () {
          var reason = ta.value.trim();
          if (!reason) { window.toast('请填写下架原因', 'error'); return; }
          e.status = 'offline_pending';
          e.offlineReason = reason;
          logHistory(e, e.version, '提交下架申请', reason);
          pushApproval({
            id: 'AP' + Date.now(), type: 'offline',
            assistantId: e.id, assistantName: e.name, avatar: e.avatar, color: e.color,
            category: e.category, tags: e.tags, desc: e.desc, version: e.version,
            owner: e.owner, ownerDept: e.ownerDept,
            submitter: me().name, submitterDept: me().dept, submitTime: nowStr(),
            reason: reason, scope: e.scope || { orgs: [], users: [] }, status: 'pending'
          });
          api.close();
          window.__reload();
          window.toast('已提交下架申请，等待管理员审批');
        });
      }
    });
    return modal;
  }

  /* ============================================================
   * 授权范围：管理员直接改，创建人提交变更申请
   * ============================================================ */
  function openScope(e) {
    var isAdmin = window.__isAdmin();
    var selOrg = {}, selUser = {};
    ((e.scope && e.scope.orgs) || []).forEach(function (o) { selOrg[o] = true; });
    ((e.scope && e.scope.users) || []).forEach(function (u) { selUser[u] = true; });

    var body =
      '<div class="notice-bar info">' + window.Icon('icon-info') +
        '<span>' + (isAdmin ? '你是公司管理员，修改后立即生效。' : '修改授权范围需提交审批，管理员通过后生效。') + '</span></div>' +
      '<div class="scope-block">' +
        '<div class="scope-block-title">选择组织<span class="text-xs tertiary">最多 50 个节点</span></div>' +
        '<div class="picker-box" id="orgPicker">' + orgRows(store.orgTree, selOrg, 0) + '</div>' +
        '<div class="scope-chips" id="orgChips"></div>' +
      '</div>' +
      '<div class="scope-block">' +
        '<div class="scope-block-title">选择人员<span class="text-xs tertiary">最多 200 人</span></div>' +
        '<div class="picker-box" id="userPicker">' + userRows(store.users, selUser) + '</div>' +
        '<div class="scope-chips" id="userChips"></div>' +
      '</div>' +
      '<div class="scope-block">' +
        '<div class="scope-block-title">调整后范围预览</div>' +
        '<div class="scope-chips" id="previewChips"></div>' +
        '<div class="scope-empty" id="previewEmpty">尚未选择授权对象</div>' +
      '</div>';

    window.openModal({
      title: '修改授权范围 · ' + e.name,
      width: 640,
      body: body,
      footer: '<button class="btn btn-default" data-close>取消</button>' +
        '<button class="btn btn-primary" id="scopeSave" disabled>' + (isAdmin ? '保存并生效' : '提交变更申请') + '</button>',
      onMount: function (root, api) {
        var save = root.querySelector('#scopeSave');

        function refresh() {
          var orgIds = Object.keys(selOrg).filter(function (k) { return selOrg[k]; });
          var userIds = Object.keys(selUser).filter(function (k) { return selUser[k]; });

          root.querySelector('#orgChips').innerHTML = orgIds.map(function (id) {
            var n = window.findOrg(id);
            return '<span class="scope-chip">' + window.esc(n ? n.name : id) + '<span class="x" data-del-org="' + id + '">×</span></span>';
          }).join('');
          root.querySelector('#userChips').innerHTML = userIds.map(function (id) {
            var u = window.findUser(id);
            return '<span class="scope-chip">' + window.esc(u ? u.name : id) + '<span class="x" data-del-user="' + id + '">×</span></span>';
          }).join('');

          var all = orgIds.map(function (id) {
            var n = window.findOrg(id);
            return '<span class="scope-chip">组织 · ' + window.esc(n ? n.name : id) + '</span>';
          }).concat(userIds.map(function (id) {
            var u = window.findUser(id);
            return '<span class="scope-chip">人员 · ' + window.esc(u ? u.name : id) + '</span>';
          })).join('');
          root.querySelector('#previewChips').innerHTML = all;
          root.querySelector('#previewEmpty').style.display = (orgIds.length + userIds.length) ? 'none' : '';
          save.disabled = (orgIds.length + userIds.length) === 0;

          root.querySelectorAll('[data-del-org]').forEach(function (el) {
            el.addEventListener('click', function () {
              var id = el.getAttribute('data-del-org');
              delete selOrg[id];
              var cb = root.querySelector('input[data-oid="' + id + '"]');
              if (cb) cb.checked = false;
              refresh();
            });
          });
          root.querySelectorAll('[data-del-user]').forEach(function (el) {
            el.addEventListener('click', function () {
              var id = el.getAttribute('data-del-user');
              delete selUser[id];
              var cb = root.querySelector('input[data-uid="' + id + '"]');
              if (cb) cb.checked = false;
              refresh();
            });
          });
        }

        root.querySelectorAll('#orgPicker input[data-oid]').forEach(function (cb) {
          cb.addEventListener('change', function () {
            var node = window.findOrg(cb.getAttribute('data-oid'));
            collectIds(node).forEach(function (id) { selOrg[id] = cb.checked; });
            root.querySelectorAll('#orgPicker input[data-oid]').forEach(function (x) {
              if (selOrg[x.getAttribute('data-oid')]) x.checked = true;
            });
            refresh();
          });
        });
        root.querySelectorAll('#userPicker input[data-uid]').forEach(function (cb) {
          cb.addEventListener('change', function () {
            selUser[cb.getAttribute('data-uid')] = cb.checked;
            refresh();
          });
        });

        save.addEventListener('click', function () {
          var orgIds = Object.keys(selOrg).filter(function (k) { return selOrg[k]; });
          var userIds = Object.keys(selUser).filter(function (k) { return selUser[k]; });
          if (!orgIds.length && !userIds.length) { window.toast('请至少选择一个组织或人员', 'error'); return; }

          if (isAdmin) {
            e.scope = { orgs: orgIds, users: userIds };
            e.authorizedCount = orgIds.length + userIds.length;
            e.updateTime = nowStr();
            logHistory(e, e.version, '授权范围变更（管理员直接生效）', '对象 ' + e.authorizedCount + ' 个');
            api.close();
            window.__reload();
            window.toast('授权范围已更新并立即生效');
          } else {
            pushApproval({
              id: 'AP' + Date.now(), type: 'scope',
              assistantId: e.id, assistantName: e.name, avatar: e.avatar, color: e.color,
              category: e.category, tags: e.tags, desc: e.desc, version: e.version,
              owner: e.owner, ownerDept: e.ownerDept,
              submitter: me().name, submitterDept: me().dept, submitTime: nowStr(),
              scope: { orgs: orgIds, users: userIds },
              oldScope: e.scope || { orgs: [], users: [] },
              status: 'pending'
            });
            api.close();
            window.toast('已提交授权范围变更申请，等待管理员审批');
          }
        });

        refresh();
      }
    });
  }

  /* ============================================================
   * 共享助理：移除 / 重新订阅
   * ============================================================ */
  function removeShared(e) {
    window.confirmDialog({
      title: '从你的助理库移除该助理？',
      text: '移除后该助理不再出现在你的「共享助理」与「全部」列表中，也不可召唤。',
      impact: '移除不影响该助理本身，也不影响创建人的共享状态；你可以在「已移除」中随时重新订阅。',
      okText: '确认移除',
      onOk: function () {
        e.subscribed = false;
        paint();
        window.toast('已从你的助理库移除', 'success', '去查看', function () {
          S.scope = 'shared';
          S.subFilter = 'removed';
          paint();
        });
      }
    });
  }
  function resubscribe(e) {
    e.subscribed = true;
    paint();
    window.toast('已重新订阅「' + e.name + '」', 'success', '去查看', function () {
      S.scope = 'shared';
      S.subFilter = 'subscribed';
      paint();
    });
  }

  /* ============================================================
   * 添加助理：三种方式（手动 / 已有接入 / 模板即将上线）
   * ============================================================ */
  function openCreateChooser() {
    window.openModal({
      title: '添加助理',
      width: 720,
      body:
        '<div class="create-opts">' +
          '<div class="create-opt" data-mode="manual">' +
            '<div class="create-opt-icon">' + window.Icon('icon-edit') + '</div>' +
            '<div class="create-opt-body"><div class="create-opt-title">手动创建<span class="create-opt-flag">推荐</span></div>' +
              '<div class="create-opt-desc">通过表单逐步配置助理：基础信息 → 能力配置 → 共享设置</div></div>' +
            window.Icon('icon-chevron-right') +
          '</div>' +
          '<div class="create-opt" data-mode="thirdparty">' +
            '<div class="create-opt-icon">' + window.Icon('icon-link') + '</div>' +
            '<div class="create-opt-body"><div class="create-opt-title">已有接入</div>' +
              '<div class="create-opt-desc">接入已在第三方平台运行的助理，如飞书、钉钉、企业微信、自定义 API</div></div>' +
            window.Icon('icon-chevron-right') +
          '</div>' +
          '<div class="create-opt disabled">' +
            '<div class="create-opt-icon">' + window.Icon('icon-message') + '</div>' +
            '<div class="create-opt-body"><div class="create-opt-title">自然语言创建<span class="create-opt-flag gray">研发中</span></div>' +
              '<div class="create-opt-desc">用一句话描述你需要的助理，系统自动生成提示词与能力配置</div></div>' +
          '</div>' +
        '</div>',
      footer: '<button class="btn btn-default" data-close>取消</button>',
      onMount: function (root, api) {
        root.querySelectorAll('[data-mode]').forEach(function (el) {
          el.addEventListener('click', function () {
            var mode = el.getAttribute('data-mode');
            api.close();
            if (mode === 'manual') openWizard(null);
            if (mode === 'thirdparty') openThirdParty();
          });
        });
      }
    });
  }

  /* ---------- 手动创建 / 编辑：三步向导 ---------- */
  var AVATARS = [
    { a: '助', c: '#3685F2' }, { a: '招', c: '#5E9DF5' }, { a: '薪', c: '#04D999' }, { a: '勤', c: '#FF813B' },
    { a: '环', c: '#FF4D5D' }, { a: '会', c: '#2468F2' }, { a: '面', c: '#00B780' }, { a: '效', c: '#D46B08' }
  ];

  function openWizard(editing) {
    var isEdit = !!editing;
    var step = 1;
    var draft = {
      avatar: editing ? editing.avatar : '助',
      color: editing ? editing.color : '#3685F2',
      tags: editing ? (editing.tags || []).slice() : [],
      quickQuestions: editing ? (editing.quickQuestions || []).slice() : [],
      skills: editing ? (editing.skills || []).slice() : [],
      mcps: editing ? (editing.mcps || []).slice() : [],
      kbs: editing ? (editing.kbs || []).slice() : []
    };
    var resTab = 'skill';
    var needReapprove = isEdit && editing.status === 'approved';

    var body =
      '<div class="wizard-steps">' +
        '<div class="wz-step active" data-step="1"><span class="wz-no">1</span>基础信息</div>' +
        '<span class="wz-line"></span>' +
        '<div class="wz-step" data-step="2"><span class="wz-no">2</span>能力配置</div>' +
        '<span class="wz-line"></span>' +
        '<div class="wz-step" data-step="3"><span class="wz-no">3</span>' + (isEdit ? '确认提交' : '共享设置') + '</div>' +
      '</div>' +

      /* --- 步骤 1 --- */
      '<div class="wz-pane" data-pane="1">' +
        '<div class="modal-form-row"><div class="modal-form-item">' +
          '<label class="modal-form-label required">头像</label>' +
          '<div class="avatar-picker" id="avatarPicker">' + AVATARS.map(function (v, i) {
            return '<div class="avatar-opt' + (draft.avatar === v.a ? ' active' : '') + '" data-avatar="' + i +
              '" style="background:' + v.c + '">' + v.a + '</div>';
          }).join('') + '</div></div></div>' +
        '<div class="modal-form-row">' +
          '<div class="modal-form-item"><label class="modal-form-label required">助理名称</label>' +
            '<input class="modal-form-input" id="wzName" maxlength="20" placeholder="2-20 个字符，同一公司内唯一" value="' +
              window.esc(editing ? editing.name : '') + '">' +
            '<div class="input-counter"><span id="nameCount">0</span>/20</div></div>' +
          '<div class="modal-form-item"><label class="modal-form-label required">所属分类</label>' +
            '<select class="modal-form-select" id="wzCat">' + store.categories.map(function (c) {
              return '<option' + (editing && editing.category === c ? ' selected' : '') + '>' + c + '</option>';
            }).join('') + '</select></div>' +
        '</div>' +
        '<div class="modal-form-row"><div class="modal-form-item">' +
          '<label class="modal-form-label required">描述</label>' +
          '<textarea class="modal-form-textarea" id="wzDesc" rows="3" maxlength="200" placeholder="10-200 个字符，说明该助理能解决什么问题">' +
            window.esc(editing ? editing.desc : '') + '</textarea></div></div>' +
        '<div class="modal-form-row"><div class="modal-form-item">' +
          '<label class="modal-form-label">自定义标签</label>' +
          '<div class="tag-input-wrap" id="tagWrap"></div>' +
          '<div class="form-hint">最多 5 个，单个标签不超过 8 个字符</div></div></div>' +
      '</div>' +

      /* --- 步骤 2 --- */
      '<div class="wz-pane" data-pane="2" style="display:none">' +
        '<div class="prompt-tools"><label class="modal-form-label required" style="margin:0">提示词</label>' +
          '<span class="prompt-counter"><span id="promptCount">0</span>/4000</span></div>' +
        '<textarea class="modal-form-textarea" id="wzPrompt" rows="6" maxlength="4000" placeholder="描述助理的角色设定、回答规则与能力边界">' +
          window.esc(editing ? editing.prompt : '') + '</textarea>' +
        '<div class="divider"></div>' +
        '<div class="flex-between mb-base">' +
          '<div class="seg-group" id="resTabs">' +
            '<div class="seg active" data-res="skill">技能<span class="seg-count" id="cntSkill">0</span></div>' +
            '<div class="seg" data-res="mcp">连接器<span class="seg-count" id="cntMcp">0</span></div>' +
            '<div class="seg" data-res="kb">知识库<span class="seg-count" id="cntKb">0</span></div>' +
          '</div>' +
          '<span class="form-hint">均为选填，每项最多 20 个</span>' +
        '</div>' +
        '<div class="res-list" id="resList"></div>' +
        '<div class="divider"></div>' +
        '<div class="flex-between mb-base">' +
          '<label class="modal-form-label" style="margin:0">召唤快速问题</label>' +
          '<span class="form-hint">选填，最多 6 条；召唤后展示在新建任务页，可一键填入</span>' +
        '</div>' +
        '<div class="tag-input-wrap" id="qqWrap"></div>' +
      '</div>' +

      /* --- 步骤 3 --- */
      '<div class="wz-pane" data-pane="3" style="display:none">' +
        (needReapprove
          ? '<div class="notice-bar">' + window.Icon('icon-alert') +
              '<span>该助理已共享（' + window.esc(editing.version || 'v1.0') + '）。保存后将生成新版本并重新提交审批，审批通过后新版本才生效。</span></div>' +
            '<div class="form-item"><label class="form-label"><span class="req">*</span>变更说明</label>' +
              '<textarea class="form-textarea" id="wzNote" rows="3" maxlength="200" placeholder="向审批人说明本次修改内容，例如：补充校招场景提示词"></textarea></div>'
          : (isEdit
            ? '<div class="notice-bar info">' + window.Icon('icon-info') + '<span>该助理当前未在共享中，保存后仅更新你自己可见的版本。</span></div>'
            : '<div class="form-item"><label class="form-label">是否立即申请共享</label>' +
                '<div class="flex gap-lg" style="margin-top:8px">' +
                  '<label class="checkbox-item"><input type="radio" name="shareMode" value="no" checked><span>暂不共享</span></label>' +
                  '<label class="checkbox-item"><input type="radio" name="shareMode" value="yes"><span>提交共享申请</span></label>' +
                '</div>' +
                '<div class="form-hint">选择「提交共享申请」后，需公司管理员审批通过才会出现在他人助理库。</div></div>' +
              '<div id="shareScopeBox" style="display:none">' +
                '<div class="divider"></div>' +
                '<div class="detail-section-title">共享范围</div>' +
                '<div class="scope-block">' +
                  '<div class="scope-block-title">选择组织<span class="text-xs tertiary">最多 50 个节点</span></div>' +
                  '<div class="picker-box" id="wzOrgPicker">' + orgRows(store.orgTree, {}, 0) + '</div>' +
                '</div>' +
                '<div class="scope-block">' +
                  '<div class="scope-block-title">选择人员<span class="text-xs tertiary">最多 200 人</span></div>' +
                  '<div class="picker-box" id="wzUserPicker">' + userRows(store.users, {}) + '</div>' +
                '</div>' +
                '<div class="scope-block"><div class="scope-block-title">授权范围预览</div>' +
                  '<div class="scope-chips" id="wzScopePreview"></div>' +
                  '<div class="scope-empty" id="wzScopeEmpty">尚未选择授权对象</div></div>' +
              '</div>')) +
        (isEdit ? '' : '<div class="form-hint mt-base">创建后将生成版本 v1.0</div>') +
      '</div>';

    var api = window.openDrawer({
      title: (isEdit ? '编辑助理 · ' + editing.name : '手动创建助理'),
      width: 760,
      body: body,
      footer: '<button class="btn btn-default" data-close>取消</button>' +
        '<button class="btn btn-default" id="wzPrev" style="display:none">上一步</button>' +
        '<button class="btn btn-primary" id="wzNext">下一步</button>',
      onMount: function (root) {
        var nameEl = root.querySelector('#wzName');
        var descEl = root.querySelector('#wzDesc');
        var promptEl = root.querySelector('#wzPrompt');
        var catEl = root.querySelector('#wzCat');
        var tagWrap = root.querySelector('#tagWrap');
        var prevBtn = root.querySelector('#wzPrev');
        var nextBtn = root.querySelector('#wzNext');

        var selOrg = {}, selUser = {};

        function syncCount() {
          root.querySelector('#nameCount').textContent = nameEl.value.length;
          root.querySelector('#promptCount').textContent = promptEl.value.length;
        }
        syncCount();
        nameEl.addEventListener('input', syncCount);
        promptEl.addEventListener('input', syncCount);

        /* 头像 */
        root.querySelectorAll('.avatar-opt').forEach(function (opt) {
          opt.addEventListener('click', function () {
            var v = AVATARS[Number(opt.getAttribute('data-avatar'))];
            draft.avatar = v.a; draft.color = v.c;
            root.querySelectorAll('.avatar-opt').forEach(function (x) { x.classList.toggle('active', x === opt); });
          });
        });

        /* 标签 */
        function renderTags() {
          tagWrap.innerHTML = draft.tags.map(function (t) {
            return '<span class="tag-chip">' + window.esc(t) + '<span class="x" data-tag="' + window.esc(t) + '">×</span></span>';
          }).join('') + (draft.tags.length >= 5 ? '' : '<input id="tagInput" placeholder="输入后回车生成标签">');
          var inp = tagWrap.querySelector('#tagInput');
          if (inp) {
            inp.addEventListener('keydown', function (ev) {
              if (ev.key !== 'Enter') return;
              ev.preventDefault();
              var v = inp.value.trim();
              if (!v) return;
              if (v.length > 8) { window.toast('单个标签不超过 8 个字符', 'error'); return; }
              if (draft.tags.length >= 5) { window.toast('最多添加 5 个标签', 'error'); return; }
              if (draft.tags.indexOf(v) >= 0) { window.toast('标签已存在', 'error'); return; }
              draft.tags.push(v); renderTags();
              var n = tagWrap.querySelector('#tagInput'); if (n) n.focus();
            });
          }
          tagWrap.querySelectorAll('[data-tag]').forEach(function (x) {
            x.addEventListener('click', function () {
              var v = x.getAttribute('data-tag');
              draft.tags = draft.tags.filter(function (t) { return t !== v; });
              renderTags();
            });
          });
        }
        renderTags();

        /* 召唤快速问题清单 */
        var qqWrap = root.querySelector('#qqWrap');
        function renderQq() {
          qqWrap.innerHTML = draft.quickQuestions.map(function (q) {
            return '<span class="tag-chip">' + window.esc(q) +
              '<span class="x" data-qq="' + window.esc(q) + '">×</span></span>';
          }).join('') + (draft.quickQuestions.length >= 6 ? '' : '<input id="qqInput" placeholder="输入问题后回车添加">');
          var inp = qqWrap.querySelector('#qqInput');
          if (inp) {
            inp.addEventListener('keydown', function (ev) {
              if (ev.key !== 'Enter') return;
              ev.preventDefault();
              var v = inp.value.trim();
              if (!v) return;
              if (v.length > 30) { window.toast('单条问题不超过 30 个字符', 'error'); return; }
              if (draft.quickQuestions.length >= 6) { window.toast('最多添加 6 条快速问题', 'error'); return; }
              if (draft.quickQuestions.indexOf(v) >= 0) { window.toast('该问题已存在', 'error'); return; }
              draft.quickQuestions.push(v);
              renderQq();
              var n = qqWrap.querySelector('#qqInput'); if (n) n.focus();
            });
          }
          qqWrap.querySelectorAll('[data-qq]').forEach(function (x) {
            x.addEventListener('click', function () {
              var v = x.getAttribute('data-qq');
              draft.quickQuestions = draft.quickQuestions.filter(function (q) { return q !== v; });
              renderQq();
            });
          });
        }
        renderQq();

        /* 资源多选 */
        function renderRes() {
          var catalog = resTab === 'skill' ? store.skills : resTab === 'mcp' ? store.mcps : store.kbs;
          var selArr = resTab === 'skill' ? draft.skills : resTab === 'mcp' ? draft.mcps : draft.kbs;
          root.querySelector('#resList').innerHTML = catalog.map(function (x) {
            var checked = selArr.indexOf(x.id) >= 0;
            var sub = resTab === 'kb' ? (x.count + ' 篇文档') : (resTab === 'mcp' ? (x.type || '') : (x.desc || ''));
            return '<label class="res-item"><input type="checkbox" data-res="' + x.id + '"' + (checked ? ' checked' : '') + '>' +
              '<span class="res-main"><span class="res-name">' + window.esc(x.name) + '</span>' +
              '<span class="res-desc">' + window.esc(sub) + '</span></span></label>';
          }).join('');
          root.querySelectorAll('#resList input[data-res]').forEach(function (cb) {
            cb.addEventListener('change', function () {
              var id = cb.getAttribute('data-res');
              var arr = resTab === 'skill' ? draft.skills : resTab === 'mcp' ? draft.mcps : draft.kbs;
              if (cb.checked) arr.push(id);
              else { var i = arr.indexOf(id); if (i >= 0) arr.splice(i, 1); }
              syncBadges();
            });
          });
          syncBadges();
        }
        function syncBadges() {
          root.querySelector('#cntSkill').textContent = draft.skills.length;
          root.querySelector('#cntMcp').textContent = draft.mcps.length;
          root.querySelector('#cntKb').textContent = draft.kbs.length;
        }
        root.querySelectorAll('#resTabs .seg').forEach(function (seg) {
          seg.addEventListener('click', function () {
            resTab = seg.getAttribute('data-res');
            root.querySelectorAll('#resTabs .seg').forEach(function (x) { x.classList.toggle('active', x === seg); });
            renderRes();
          });
        });
        renderRes();

        /* 共享设置（仅创建） */
        var shareBox = root.querySelector('#shareScopeBox');
        if (shareBox) {
          root.querySelectorAll('input[name="shareMode"]').forEach(function (r) {
            r.addEventListener('change', function () {
              var on = root.querySelector('input[name="shareMode"]:checked').value === 'yes';
              shareBox.style.display = on ? '' : 'none';
            });
          });
          root.querySelectorAll('#wzOrgPicker input[data-oid]').forEach(function (cb) {
            cb.addEventListener('change', function () {
              var node = window.findOrg(cb.getAttribute('data-oid'));
              collectIds(node).forEach(function (id) { selOrg[id] = cb.checked; });
              root.querySelectorAll('#wzOrgPicker input[data-oid]').forEach(function (x) {
                if (selOrg[x.getAttribute('data-oid')]) x.checked = true;
              });
              refreshPreview();
            });
          });
          root.querySelectorAll('#wzUserPicker input[data-uid]').forEach(function (cb) {
            cb.addEventListener('change', function () {
              selUser[cb.getAttribute('data-uid')] = cb.checked;
              refreshPreview();
            });
          });
        }
        function refreshPreview() {
          if (!shareBox) return;
          var orgIds = Object.keys(selOrg).filter(function (k) { return selOrg[k]; });
          var userIds = Object.keys(selUser).filter(function (k) { return selUser[k]; });
          var all = orgIds.map(function (id) {
            var n = window.findOrg(id);
            return '<span class="scope-chip">组织 · ' + window.esc(n ? n.name : id) + '</span>';
          }).concat(userIds.map(function (id) {
            var u = window.findUser(id);
            return '<span class="scope-chip">人员 · ' + window.esc(u ? u.name : id) + '</span>';
          })).join('');
          root.querySelector('#wzScopePreview').innerHTML = all;
          root.querySelector('#wzScopeEmpty').style.display = (orgIds.length + userIds.length) ? 'none' : '';
        }

        /* 步骤切换 */
        function goStep(n) {
          step = n;
          root.querySelectorAll('.wz-pane').forEach(function (p) {
            p.style.display = Number(p.getAttribute('data-pane')) === n ? '' : 'none';
          });
          root.querySelectorAll('.wz-step').forEach(function (s) {
            var i = Number(s.getAttribute('data-step'));
            s.classList.toggle('active', i === n);
            s.classList.toggle('done', i < n);
          });
          prevBtn.style.display = n === 1 ? 'none' : '';
          nextBtn.textContent = n === 3 ? (isEdit ? '保存' : '完成创建') : '下一步';
          root.querySelector('.drawer-body').scrollTop = 0;
        }
        goStep(1);

        prevBtn.addEventListener('click', function () { goStep(Math.max(1, step - 1)); });

        nextBtn.addEventListener('click', function () {
          if (step === 1) {
            var name = nameEl.value.trim();
            var desc = descEl.value.trim();
            nameEl.classList.remove('invalid'); descEl.classList.remove('invalid');
            if (name.length < 2 || name.length > 20) {
              nameEl.classList.add('invalid'); window.toast('助理名称需为 2-20 个字符', 'error'); return;
            }
            var dup = store.assistants.filter(function (x) {
              return x.source === 'custom' && x.name === name && (!editing || x.id !== editing.id);
            })[0];
            if (dup) { nameEl.classList.add('invalid'); window.toast('助理名称已存在，请修改', 'error'); return; }
            if (desc.length < 10 || desc.length > 200) {
              descEl.classList.add('invalid'); window.toast('描述需为 10-200 个字符', 'error'); return;
            }
            goStep(2);
            return;
          }
          if (step === 2) {
            var prompt = promptEl.value.trim();
            promptEl.classList.remove('invalid');
            if (!prompt) { promptEl.classList.add('invalid'); window.toast('请填写提示词', 'error'); return; }
            goStep(3);
            return;
          }
          submit();
        });

        function submit() {
          var name = nameEl.value.trim();
          var desc = descEl.value.trim();
          var prompt = promptEl.value.trim();
          var noteEl = root.querySelector('#wzNote');
          var note = noteEl ? noteEl.value.trim() : '';

          if (needReapprove && !note) {
            if (noteEl) noteEl.classList.add('invalid');
            window.toast('请填写变更说明', 'error');
            return;
          }

          var payload = {
            name: name, desc: desc, category: catEl.value, prompt: prompt,
            avatar: draft.avatar, color: draft.color, tags: draft.tags.slice(),
            quickQuestions: draft.quickQuestions.slice(),
            skills: draft.skills.slice(), mcps: draft.mcps.slice(), kbs: draft.kbs.slice()
          };

          if (isEdit) {
            Object.keys(payload).forEach(function (k) { editing[k] = payload[k]; });
            editing.updateTime = nowStr();
            var nextVer = nextVersion(editing.version);

            if (needReapprove) {
              /* 已共享：升版本 + 重新提交审批 */
              editing.version = nextVer;
              editing.status = 'pending';
              logHistory(editing, nextVer, '编辑更新', note);
              pushApproval({
                id: 'AP' + Date.now(), type: 'share',
                assistantId: editing.id, assistantName: editing.name, avatar: editing.avatar, color: editing.color,
                category: editing.category, tags: editing.tags, desc: editing.desc, prompt: editing.prompt,
                skills: editing.skills, mcps: editing.mcps, kbs: editing.kbs, version: nextVer,
                owner: editing.owner, ownerDept: editing.ownerDept,
                submitter: me().name, submitterDept: me().dept, submitTime: nowStr(),
                changeNote: note, scope: editing.scope || { orgs: [], users: [] }, status: 'pending'
              });
              api.close();
              window.__reload();
              window.toast('已生成 ' + nextVer + ' 并重新提交审批');
            } else {
              editing.version = nextVer;
              logHistory(editing, nextVer, '编辑更新', '未共享状态下编辑');
              api.close();
              window.__reload();
              window.toast('已保存，当前版本 ' + nextVer);
            }
            return;
          }

          /* 新建 */
          var wantShare = shareBox && root.querySelector('input[name="shareMode"]:checked').value === 'yes';
          var orgIds = Object.keys(selOrg).filter(function (k) { return selOrg[k]; });
          var userIds = Object.keys(selUser).filter(function (k) { return selUser[k]; });
          if (wantShare && !orgIds.length && !userIds.length) {
            window.toast('请选择共享范围', 'error');
            return;
          }

          var created = {
            id: 'E' + Date.now(), source: 'custom', owner: me().name, ownerDept: me().dept,
            status: wantShare ? 'pending' : 'unshared', authorizedCount: 0,
            createTime: nowStr(), updateTime: nowStr(), version: 'v1.0',
            scope: wantShare ? { orgs: orgIds, users: userIds } : { orgs: [], users: [] },
            history: [{
              version: 'v1.0', action: wantShare ? '创建并申请共享' : '创建',
              operator: me().name, time: nowStr(),
              remark: wantShare ? '手动创建，提交共享申请' : '手动创建'
            }]
          };
          Object.keys(payload).forEach(function (k) { created[k] = payload[k]; });
          store.assistants.unshift(created);

          if (wantShare) {
            created.authorizedCount = orgIds.length + userIds.length;
            pushApproval({
              id: 'AP' + Date.now(), type: 'share',
              assistantId: created.id, assistantName: created.name, avatar: created.avatar, color: created.color,
              category: created.category, tags: created.tags, desc: created.desc, prompt: created.prompt,
              skills: created.skills, mcps: created.mcps, kbs: created.kbs, version: 'v1.0',
              owner: created.owner, ownerDept: created.ownerDept,
              submitter: me().name, submitterDept: me().dept, submitTime: nowStr(),
              changeNote: '首次申请共享', scope: created.scope, status: 'pending'
            });
          }

          api.close();
          S.scope = 'mine';
          S.category = '全部';
          S.keyword = '';
          window.__reload();
          window.toast(wantShare ? '创建成功，已提交共享审批' : '创建成功，已归入「我的助理」');
        }
      }
    });
    return api;
  }

  /* ---------- 已有接入：接入第三方助理 ---------- */
  function openThirdParty() {
    var PLATFORMS = ['飞书智能伙伴', '钉钉 AI 助理', '企业微信智能助手', '自定义 API'];
    var api = window.openDrawer({
      title: '已有接入 · 接入第三方助理',
      width: 640,
      body:
        '<div class="notice-bar info">' + window.Icon('icon-info') +
          '<span>接入后助理仍由第三方平台运行，本平台负责调用与授权管理。</span></div>' +
        '<div class="modal-form-row"><div class="modal-form-item">' +
          '<label class="modal-form-label required">来源平台</label>' +
          '<select class="modal-form-select" id="tpPlatform">' + PLATFORMS.map(function (p) {
            return '<option>' + p + '</option>';
          }).join('') + '</select></div></div>' +
        '<div class="modal-form-row"><div class="modal-form-item">' +
          '<label class="modal-form-label required">助理名称</label>' +
          '<input class="modal-form-input" id="tpName" maxlength="20" placeholder="与第三方平台展示名称一致，2-20 个字符"></div></div>' +
        '<div class="modal-form-row"><div class="modal-form-item">' +
          '<label class="modal-form-label required">接入地址</label>' +
          '<input class="modal-form-input" id="tpEndpoint" placeholder="https://open.example.com/assistant/api"></div></div>' +
        '<div class="modal-form-row">' +
          '<div class="modal-form-item"><label class="modal-form-label required">AppID</label>' +
            '<input class="modal-form-input" id="tpAppId" placeholder="平台应用的 AppID"></div>' +
          '<div class="modal-form-item"><label class="modal-form-label required">AppSecret</label>' +
            '<input class="modal-form-input" id="tpSecret" type="password" placeholder="平台应用的 AppSecret"></div>' +
        '</div>' +
        '<div class="modal-form-row"><div class="modal-form-item">' +
          '<label class="modal-form-label">能力说明</label>' +
          '<textarea class="modal-form-textarea" id="tpDesc" rows="3" maxlength="200" placeholder="简述该助理可解决的问题，用于助理卡片展示"></textarea></div></div>' +
        '<div class="flex-between mt-base">' +
          '<span class="form-hint" id="tpStatus">填写完成后可先测试连接</span>' +
          '<button class="btn btn-default" id="tpTest">' + window.Icon('icon-zap') + '测试连接</button>' +
        '</div>',
      footer: '<button class="btn btn-default" data-close>取消</button>' +
        '<button class="btn btn-primary" id="tpSubmit" disabled>提交接入</button>',
      onMount: function (root, drawerApi) {
        var nameEl = root.querySelector('#tpName');
        var epEl = root.querySelector('#tpEndpoint');
        var appIdEl = root.querySelector('#tpAppId');
        var secretEl = root.querySelector('#tpSecret');
        var descEl = root.querySelector('#tpDesc');
        var statusEl = root.querySelector('#tpStatus');
        var submitBtn = root.querySelector('#tpSubmit');
        var tested = false;

        function check() {
          var ok = nameEl.value.trim().length >= 2 && epEl.value.trim() && appIdEl.value.trim() && secretEl.value.trim();
          submitBtn.disabled = !(ok && tested);
        }
        [nameEl, epEl, appIdEl, secretEl].forEach(function (el) {
          el.addEventListener('input', function () { tested = false; submitBtn.disabled = true; statusEl.textContent = '信息已修改，请重新测试连接'; statusEl.className = 'form-hint'; check(); });
        });

        root.querySelector('#tpTest').addEventListener('click', function () {
          if (!nameEl.value.trim() || !epEl.value.trim() || !appIdEl.value.trim() || !secretEl.value.trim()) {
            window.toast('请先填写名称、接入地址与密钥', 'error');
            return;
          }
          statusEl.textContent = '正在测试连接…';
          statusEl.className = 'form-hint';
          setTimeout(function () {
            tested = true;
            statusEl.textContent = '连接成功，可提交接入';
            statusEl.className = 'form-hint tp-ok';
            check();
          }, 800);
        });

        submitBtn.addEventListener('click', function () {
          var platform = root.querySelector('#tpPlatform').value;
          var created = {
            id: 'E' + Date.now(), source: 'thirdparty', platform: platform,
            endpoint: epEl.value.trim(), appId: appIdEl.value.trim(),
            name: nameEl.value.trim(), desc: descEl.value.trim() || ('接入自' + platform + '的助理'),
            avatar: nameEl.value.trim().slice(0, 1), color: '#2468F2',
            category: store.categories[0], tags: [platform], owner: me().name, ownerDept: me().dept,
            prompt: '（由' + platform + '托管，提示词与能力在第三方平台维护）',
            skills: [], mcps: [], kbs: [],
            status: 'unshared', authorizedCount: 0, scope: { orgs: [], users: [] },
            createTime: nowStr(), updateTime: nowStr(), version: 'v1.0',
            history: [{
              version: 'v1.0', action: '接入创建', operator: me().name, time: nowStr(),
              remark: '接入 ' + platform
            }]
          };
          store.assistants.unshift(created);
          drawerApi.close();
          S.scope = 'mine';
          S.category = '全部';
          window.__reload();
          window.toast('接入成功，已归入「我的助理」');
        });

        check();
      }
    });
    return api;
  }

  /* ============================================================
   * 共享提交 / 重新提交
   * ============================================================ */
  function openShare(ids, resubmitassistant) {
    var targets = store.assistants.filter(function (e) { return ids.indexOf(e.id) >= 0; });
    if (!targets.length) return;

    var selOrg = {}, selUser = {};
    var init = resubmitassistant && resubmitassistant.lastScope ? resubmitassistant.lastScope : { orgs: [], users: [] };
    (init.orgs || []).forEach(function (o) { selOrg[o] = true; });
    (init.users || []).forEach(function (u) { selUser[u] = true; });

    var chips = targets.map(function (e) {
      return '<span class="scope-chip"><span class="assistant-avatar" style="width:18px;height:18px;flex:0 0 18px;font-size:11px;background:' +
        (e.color || '#3685F2') + '">' + window.esc(e.avatar || '') + '</span>' + window.esc(e.name) + '</span>';
    }).join('');

    var body =
      (resubmitassistant ? '<div class="notice-bar info">' + window.Icon('icon-info') +
        '<span>上次审批被拒绝，原因：' + window.esc(resubmitassistant.rejectReason || '管理员未填写拒绝原因') + '</span></div>' : '') +
      '<div class="confirm-text mb-base">已选 <b>' + targets.length + '</b> 个助理，提交后进入公司管理员审批，审批期间不可修改。</div>' +
      '<div class="scope-chips" style="margin-bottom:16px">' + chips + '</div>' +
      '<div class="detail-section-title">共享范围</div>' +
      '<div class="scope-block">' +
        '<div class="scope-block-title">选择组织<span class="text-xs tertiary">最多 50 个节点</span></div>' +
        '<div class="picker-box" id="orgPicker">' + orgRows(store.orgTree, selOrg, 0) + '</div>' +
        '<div class="scope-chips" id="orgChips"></div>' +
      '</div>' +
      '<div class="scope-block">' +
        '<div class="scope-block-title">选择人员<span class="text-xs tertiary">最多 200 人</span></div>' +
        '<div class="picker-box" id="userPicker">' + userRows(store.users, selUser) + '</div>' +
        '<div class="scope-chips" id="userChips"></div>' +
      '</div>' +
      '<div class="scope-block">' +
        '<div class="scope-block-title">授权范围预览</div>' +
        '<div class="scope-chips" id="previewChips"></div>' +
        '<div class="scope-empty" id="previewEmpty">尚未选择授权对象，请至少选择一个组织或人员</div>' +
      '</div>';

    var api = window.openModal({
      title: resubmitassistant ? '重新提交共享审批' : '共享提交',
      width: 640,
      body: body,
      footer: '<button class="btn btn-default" data-close>取消</button>' +
        '<button class="btn btn-primary" id="btnSubmitShare" disabled>提交审批</button>',
      onMount: function (root) {
        var btnSubmit = root.querySelector('#btnSubmitShare');

        function refresh() {
          var orgIds = Object.keys(selOrg).filter(function (k) { return selOrg[k]; });
          var userIds = Object.keys(selUser).filter(function (k) { return selUser[k]; });

          root.querySelector('#orgChips').innerHTML = orgIds.map(function (id) {
            var n = window.findOrg(id);
            return '<span class="scope-chip">' + window.esc(n ? n.name : id) +
              '<span class="x" data-del-org="' + id + '">×</span></span>';
          }).join('');
          root.querySelector('#userChips').innerHTML = userIds.map(function (id) {
            var u = window.findUser(id);
            return '<span class="scope-chip">' + window.esc(u ? u.name : id) +
              '<span class="x" data-del-user="' + id + '">×</span></span>';
          }).join('');

          var all = orgIds.map(function (id) {
            var n = window.findOrg(id);
            return '<span class="scope-chip">组织 · ' + window.esc(n ? n.name : id) + '</span>';
          }).concat(userIds.map(function (id) {
            var u = window.findUser(id);
            return '<span class="scope-chip">人员 · ' + window.esc(u ? u.name : id) + '</span>';
          })).join('');

          root.querySelector('#previewChips').innerHTML = all;
          root.querySelector('#previewEmpty').style.display = (orgIds.length + userIds.length) ? 'none' : '';
          btnSubmit.disabled = (orgIds.length + userIds.length) === 0;

          root.querySelectorAll('[data-del-org]').forEach(function (el) {
            el.addEventListener('click', function () {
              var id = el.getAttribute('data-del-org');
              delete selOrg[id];
              var cb = root.querySelector('input[data-oid="' + id + '"]');
              if (cb) cb.checked = false;
              refresh();
            });
          });
          root.querySelectorAll('[data-del-user]').forEach(function (el) {
            el.addEventListener('click', function () {
              var id = el.getAttribute('data-del-user');
              delete selUser[id];
              var cb = root.querySelector('input[data-uid="' + id + '"]');
              if (cb) cb.checked = false;
              refresh();
            });
          });
        }

        root.querySelectorAll('#orgPicker input[data-oid]').forEach(function (cb) {
          cb.addEventListener('change', function () {
            var node = window.findOrg(cb.getAttribute('data-oid'));
            collectIds(node).forEach(function (id) { selOrg[id] = cb.checked; });
            root.querySelectorAll('#orgPicker input[data-oid]').forEach(function (x) {
              if (selOrg[x.getAttribute('data-oid')]) x.checked = true;
            });
            refresh();
          });
        });
        root.querySelectorAll('#userPicker input[data-uid]').forEach(function (cb) {
          cb.addEventListener('change', function () {
            selUser[cb.getAttribute('data-uid')] = cb.checked;
            refresh();
          });
        });

        btnSubmit.addEventListener('click', function () {
          var orgIds = Object.keys(selOrg).filter(function (k) { return selOrg[k]; });
          var userIds = Object.keys(selUser).filter(function (k) { return selUser[k]; });
          if (!orgIds.length && !userIds.length) { window.toast('请至少选择一个组织或人员', 'error'); return; }

          targets.forEach(function (t) {
            t.status = 'pending';
            t.scope = { orgs: orgIds, users: userIds };
            t.authorizedCount = orgIds.length + userIds.length;
            t.rejectReason = '';
            t.updateTime = nowStr();
            logHistory(t, t.version || 'v1.0', resubmitassistant ? '重新提交共享申请' : '提交共享申请', '');
            pushApproval({
              id: 'AP' + Date.now() + Math.floor(Math.random() * 100),
              type: 'share',
              assistantId: t.id, assistantName: t.name, avatar: t.avatar, color: t.color,
              category: t.category, tags: t.tags, desc: t.desc, prompt: t.prompt,
              skills: t.skills, mcps: t.mcps, kbs: t.kbs, version: t.version || 'v1.0',
              owner: t.owner, ownerDept: t.ownerDept,
              submitter: me().name, submitterDept: me().dept, submitTime: nowStr(),
              changeNote: resubmitassistant ? '重新提交' : '首次申请共享',
              scope: { orgs: orgIds, users: userIds }, status: 'pending'
            });
          });
          S.selected = {};
          api.close();
          window.__reload();
          window.toast(resubmitassistant ? '已重新提交审批' : '已提交审批，等待管理员处理');
        });

        refresh();
      }
    });
    return api;
  }

  /* ============================================================
   * 审批中心（共享 / 下架 / 范围变更）
   * ============================================================ */
  var TYPE_TEXT = { share: ['blue', '共享申请'], offline: ['warning', '下架申请'], scope: ['default', '范围变更'] };

  function openApprovalList() {
    function listHtml() {
      var list = store.approvals.filter(function (a) { return a.status === 'pending'; });
      if (!list.length) {
        return '<div class="empty-state"><div class="empty-icon">' + window.Icon('icon-check-circle', 'icon-lg') + '</div>' +
          '<div class="empty-state-text">暂无待审批的申请</div></div>';
      }
      return list.map(function (a) {
        var t = TYPE_TEXT[a.type] || TYPE_TEXT.share;
        var sub = a.type === 'offline'
          ? '下架原因：' + (a.reason || '')
          : a.type === 'scope'
            ? '变更授权范围'
            : '授权范围：' + summarizeScope(a.scope);
        return '<div class="appr-item" data-appr="' + a.id + '">' +
          '<div class="assistant-avatar" style="background:' + (a.color || '#3685F2') + '">' + window.esc(a.avatar || a.assistantName.slice(0, 1)) + '</div>' +
          '<div class="appr-main">' +
            '<div class="appr-name">' + window.esc(a.assistantName) + window.Tag(t[0], t[1]) +
              '<span class="ver-tag" style="margin-left:6px">' + window.esc(a.version || 'v1.0') + '</span></div>' +
            '<div class="appr-meta">提交人：' + window.esc(a.submitter) + ' · ' + window.esc(a.submitTime) + '</div>' +
            '<div class="appr-scope">' + window.esc(sub) + '</div></div>' +
          window.Icon('icon-chevron-right') + '</div>';
      }).join('');
    }

    var api = window.openDrawer({
      title: '审批中心',
      width: 580,
      body: '<div class="text-sm muted mb-base" id="apprSummary"></div><div id="apprList"></div>',
      footer: '<button class="btn btn-default" data-close>关闭</button>',
      onMount: function (root, drawerApi) {
        function paintList() {
          var n = store.approvals.filter(function (a) { return a.status === 'pending'; }).length;
          root.querySelector('#apprSummary').textContent = '共 ' + n + ' 条待审批 · 按提交时间正序排列';
          root.querySelector('#apprList').innerHTML = listHtml();
          root.querySelectorAll('[data-appr]').forEach(function (el) {
            el.addEventListener('click', function () {
              var id = el.getAttribute('data-appr');
              var appr = store.approvals.filter(function (a) { return a.id === id; })[0];
              openApprovalDetail(appr, function () {
                paintList();
                drawerApi.close();
                window.__reload();
              });
            });
          });
        }
        paintList();
      }
    });
    return api;
  }

  function summarizeScope(scope) {
    var orgNames = ((scope && scope.orgs) || []).map(function (id) {
      var n = window.findOrg(id); return n ? n.name : id;
    });
    var userNames = ((scope && scope.users) || []).map(function (id) {
      var u = window.findUser(id); return u ? u.name : id;
    });
    var all = orgNames.concat(userNames);
    return (all.slice(0, 2).join('、') + (all.length > 2 ? ' +' + (all.length - 2) : '')) || '未设置';
  }

  function openApprovalDetail(appr, onDecided) {
    if (!appr || appr.status !== 'pending') {
      window.toast('该申请已被处理', 'error');
      if (onDecided) onDecided();
      return;
    }
    var type = appr.type || 'share';
    var selOrg = {}, selUser = {};
    ((appr.scope && appr.scope.orgs) || []).forEach(function (o) { selOrg[o] = true; });
    ((appr.scope && appr.scope.users) || []).forEach(function (u) { selUser[u] = true; });
    var adjusted = false;
    var editing = false;

    function capRow(title, content) {
      return '<div class="cap-item"><div class="cap-title">' + title + '</div><div class="cap-body">' + content + '</div></div>';
    }
    function scopeChips(scope, empty) {
      var orgIds = (scope.orgs || []), userIds = (scope.users || []);
      var chips = orgIds.map(function (id) {
        var n = window.findOrg(id);
        return '<span class="scope-chip">组织 · ' + window.esc(n ? n.name : id) + '</span>';
      }).concat(userIds.map(function (id) {
        var u = window.findUser(id);
        return '<span class="scope-chip">人员 · ' + window.esc(u ? u.name : id) + '</span>';
      })).join('');
      return chips || '<span class="scope-empty">' + (empty || '未设置') + '</span>';
    }

    function scopeViewHtml() {
      if (editing) {
        return '<div class="picker-box" id="apOrgPicker" style="margin-bottom:8px">' + orgRows(store.orgTree, selOrg, 0) + '</div>' +
          '<div class="picker-box" id="apUserPicker">' + userRows(store.users, selUser) + '</div>' +
          '<div class="flex gap-sm mt-base"><button class="btn btn-primary btn-sm" id="apScopeOk">确认调整</button>' +
            '<button class="btn btn-default btn-sm" id="apScopeCancel">取消</button></div>';
      }
      var orgIds = Object.keys(selOrg).filter(function (k) { return selOrg[k]; });
      var userIds = Object.keys(selUser).filter(function (k) { return selUser[k]; });
      return '<div class="scope-chips">' + scopeChips({ orgs: orgIds, users: userIds }) + '</div>' +
        '<div class="form-hint">组织 ' + orgIds.length + ' 个 · 人员 ' + userIds.length + ' 人</div>';
    }

    var typeTag = TYPE_TEXT[type] || TYPE_TEXT.share;
    var body =
      '<div class="text-sm muted mb-base">' + window.esc(typeTag[1]) + ' · 单号：' + window.esc(appr.id) +
        ' · 提交人：' + window.esc(appr.submitter) + '（' + window.esc(appr.submitterDept) + '） · ' + window.esc(appr.submitTime) + '</div>' +
      '<div class="detail-section-title">助理信息</div>' +
      '<div class="assistant-card-top" style="margin-bottom:12px">' +
        '<div class="assistant-avatar" style="background:' + (appr.color || '#3685F2') + '">' + window.esc(appr.avatar || '') + '</div>' +
        '<div class="assistant-name-wrap"><div class="assistant-name">' + window.esc(appr.assistantName) +
          window.Tag('blue', appr.category) + '<span class="ver-tag">' + window.esc(appr.version || 'v1.0') + '</span></div>' +
          '<div class="assistant-tags">' + (appr.tags || []).map(function (t) { return '<span class="mini-tag">' + window.esc(t) + '</span>'; }).join('') + '</div>' +
        '</div></div>' +
      '<div class="cap-item"><div class="cap-title">描述</div><div class="cap-body">' + window.esc(appr.desc || '') + '</div></div>' +
      (type === 'offline'
        ? '<div class="detail-section-title mt-base">下架原因</div>' +
          '<div class="notice-bar">' + window.Icon('icon-alert') + '<span>' + window.esc(appr.reason || '未填写') + '</span></div>' +
          '<div class="detail-section-title mt-base">当前授权范围</div>' +
          '<div class="scope-chips">' + scopeChips(appr.scope) + '</div>'
        : type === 'scope'
          ? '<div class="detail-section-title mt-base">授权范围变更</div>' +
            '<div class="scope-block"><div class="scope-block-title">变更前</div>' +
              '<div class="scope-chips">' + scopeChips(appr.oldScope, '无') + '</div></div>' +
            '<div class="scope-block"><div class="scope-block-title">变更后</div>' +
              '<div class="scope-chips">' + scopeChips(appr.scope) + '</div></div>'
          : '<div class="detail-section-title mt-base">能力组成（只读）</div>' +
            capRow('提示词', window.esc(appr.prompt || '未配置')) +
            capRow('技能', window.esc(nameOf(store.skills, appr.skills))) +
            capRow('连接器', window.esc(nameOf(store.mcps, appr.mcps))) +
            capRow('知识库', window.esc(nameOf(store.kbs, appr.kbs))) +
            (appr.changeNote ? capRow('变更说明', window.esc(appr.changeNote)) : '') +
            '<div class="detail-section-title mt-base">授权范围' +
              '<span class="tag tag-warning" id="adjustedFlag" style="display:none;margin-left:8px">已调整</span></div>' +
            '<div id="scopeArea">' + scopeViewHtml() + '</div>' +
            (type === 'share'
              ? '<div class="flex gap-sm mt-base"><button class="btn btn-default btn-sm" id="apEditScope">' +
                window.Icon('icon-edit') + '调整授权范围</button></div>'
              : ''));

    var api = window.openDrawer({
      title: '审批详情 · ' + appr.assistantName,
      width: 760,
      body: body,
      footer: '<button class="btn btn-default" data-close>稍后处理</button>' +
        '<button class="btn btn-danger" id="apReject">审批拒绝</button>' +
        '<button class="btn btn-primary" id="apPass">审批通过</button>',
      onMount: function (root, drawerApi) {
        var scopeArea = root.querySelector('#scopeArea');

        function paintScope() {
          if (!scopeArea) return;
          scopeArea.innerHTML = scopeViewHtml();
          var editBtn = root.querySelector('#apEditScope');
          if (editBtn) editBtn.style.display = editing ? 'none' : '';
          var flag = root.querySelector('#adjustedFlag');
          if (flag) flag.style.display = adjusted ? '' : 'none';

          root.querySelectorAll('#apOrgPicker input[data-oid]').forEach(function (cb) {
            cb.addEventListener('change', function () {
              var node = window.findOrg(cb.getAttribute('data-oid'));
              collectIds(node).forEach(function (id) { selOrg[id] = cb.checked; });
              root.querySelectorAll('#apOrgPicker input[data-oid]').forEach(function (x) {
                if (selOrg[x.getAttribute('data-oid')]) x.checked = true;
              });
            });
          });
          root.querySelectorAll('#apUserPicker input[data-uid]').forEach(function (cb) {
            cb.addEventListener('change', function () {
              selUser[cb.getAttribute('data-uid')] = cb.checked;
            });
          });
          var ok = root.querySelector('#apScopeOk');
          if (ok) {
            ok.addEventListener('click', function () {
              var n = Object.keys(selOrg).filter(function (k) { return selOrg[k]; }).length +
                Object.keys(selUser).filter(function (k) { return selUser[k]; }).length;
              if (!n) { window.toast('授权范围不可为空', 'error'); return; }
              editing = false; adjusted = true; paintScope();
              window.toast('授权范围已调整，将在审批通过时生效');
            });
          }
          var cancel = root.querySelector('#apScopeCancel');
          if (cancel) cancel.addEventListener('click', function () { editing = false; paintScope(); });
        }
        if (scopeArea) paintScope();

        var editScopeBtn = root.querySelector('#apEditScope');
        if (editScopeBtn) editScopeBtn.addEventListener('click', function () { editing = true; paintScope(); });

        /* 通过 */
        root.querySelector('#apPass').addEventListener('click', function () {
          var orgIds = Object.keys(selOrg).filter(function (k) { return selOrg[k]; });
          var userIds = Object.keys(selUser).filter(function (k) { return selUser[k]; });
          var target = store.assistants.filter(function (e) { return e.id === appr.assistantId; })[0];

          var passText = type === 'offline'
            ? '通过后该助理将立即下架，并从所有授权对象的助理库中移除。'
            : type === 'scope'
              ? '通过后新的授权范围立即生效。'
              : '通过后该助理将出现在授权对象的助理库中，并标识「共享」。';

          window.confirmDialog({
            title: '确认审批通过？',
            text: passText,
            impact: type === 'offline' ? '助理：' + appr.assistantName
              : '最终授权范围：组织 ' + orgIds.length + ' 个 · 人员 ' + userIds.length + ' 人' +
                (adjusted ? '（已按管理员调整结果生效）' : ''),
            okText: '确认通过',
            onOk: function () {
              appr.status = 'approved';
              appr.approver = me().name;
              appr.approveTime = nowStr();

              if (type === 'offline') {
                if (target) {
                  target.status = 'offline';
                  target.updateTime = nowStr();
                  logHistory(target, target.version, '下架生效', appr.reason || '');
                }
              } else if (type === 'scope') {
                if (target) {
                  target.scope = { orgs: appr.scope.orgs || [], users: appr.scope.users || [] };
                  target.authorizedCount = (appr.scope.orgs || []).length + (appr.scope.users || []).length;
                  target.updateTime = nowStr();
                  logHistory(target, target.version, '授权范围变更', '对象 ' + target.authorizedCount + ' 个');
                }
              } else {
                appr.scope = { orgs: orgIds, users: userIds };
                if (target) {
                  target.status = 'approved';
                  target.authorizedCount = orgIds.length + userIds.length;
                  target.scope = { orgs: orgIds, users: userIds };
                  target.rejectReason = '';
                  target.updateTime = nowStr();
                  logHistory(target, target.version, '共享审批通过', appr.changeNote || '');
                }
              }
              drawerApi.close();
              if (onDecided) onDecided();
              window.toast('已审批通过');
            }
          });
        });

        /* 拒绝 */
        root.querySelector('#apReject').addEventListener('click', function () {
          window.openModal({
            title: '审批拒绝',
            width: 520,
            body: '<div class="confirm-text mb-base">拒绝原因将展示在提交人的助理列表中，请说明具体问题。</div>' +
              '<textarea class="form-textarea" id="rjReason" rows="4" maxlength="200" placeholder="请输入拒绝原因（1-200 字）"></textarea>' +
              '<div class="input-counter" style="text-align:right"><span id="rjCount">0</span>/200</div>',
            footer: '<button class="btn btn-default" data-close>取消</button>' +
              '<button class="btn btn-danger" id="rjOk" disabled>确认拒绝</button>',
            onMount: function (root2, api2) {
              var ta = root2.querySelector('#rjReason');
              var ok = root2.querySelector('#rjOk');
              ta.addEventListener('input', function () {
                root2.querySelector('#rjCount').textContent = ta.value.length;
                ok.disabled = ta.value.trim().length === 0;
              });
              ta.focus();
              ok.addEventListener('click', function () {
                var reason = ta.value.trim();
                if (!reason) { window.toast('请填写拒绝原因', 'error'); return; }
                appr.status = 'rejected';
                appr.rejectReason = reason;
                appr.approver = me().name;
                appr.approveTime = nowStr();
                var target = store.assistants.filter(function (e) { return e.id === appr.assistantId; })[0];
                if (target) {
                  if (type === 'offline') {
                    target.status = 'approved';
                    target.offlineReason = '';
                    logHistory(target, target.version, '下架申请被拒绝', reason);
                  } else if (type === 'scope') {
                    logHistory(target, target.version, '范围变更被拒绝', reason);
                  } else {
                    target.status = 'rejected';
                    target.rejectReason = reason;
                    target.lastScope = { orgs: appr.scope.orgs || [], users: appr.scope.users || [] };
                    logHistory(target, target.version, '共享审批被拒绝', reason);
                  }
                  target.updateTime = nowStr();
                }
                api2.close();
                drawerApi.close();
                if (onDecided) onDecided();
                window.toast(type === 'offline' ? '已拒绝该下架申请' : '已拒绝该申请');
              });
            }
          });
        });
      }
    });
    return api;
  }

  /* ============================================================
   * 组织 / 人员选择器（共用）
   * ============================================================ */
  function orgRows(nodes, selObj, indent) {
    var html = '';
    nodes.forEach(function (n) {
      html += '<div style="padding-left:' + (indent || 0) + 'px;margin:3px 0">' +
        '<label class="checkbox-item" style="display:inline-flex;align-items:center;gap:6px;cursor:pointer">' +
        '<input type="checkbox" data-oid="' + n.id + '"' + (selObj[n.id] ? ' checked' : '') + '>' +
        '<span>' + window.esc(n.name) + '</span></label></div>';
      if (n.children && n.children.length) html += orgRows(n.children, selObj, (indent || 0) + 16);
    });
    return html;
  }
  function collectIds(node) {
    var out = [node.id];
    (function walk(ns) {
      (ns || []).forEach(function (n) { out.push(n.id); if (n.children) walk(n.children); });
    })(node.children);
    return out;
  }
  function userRows(list, selObj) {
    return list.map(function (u) {
      return '<label class="checkbox-item" style="display:flex;align-items:center;gap:6px;padding:4px 0;cursor:pointer">' +
        '<input type="checkbox" data-uid="' + u.id + '"' + (selObj[u.id] ? ' checked' : '') + '>' +
        '<span>' + window.esc(u.name) + '</span>' +
        '<span class="text-xs tertiary">' + window.esc(u.dept) + '</span></label>';
    }).join('');
  }
};
