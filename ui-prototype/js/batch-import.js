/**
 * 批量导入（H31 P1）：CSV 上传 → 待办任务 → 去重 + AI 生成 → 逐卡人工评审 → 草稿。
 * 卡包区完全参考《指标卡包系统 v1.0.0》设计规格（metric-card.html v8）：
 *   14 主题 × 3 类型 × 4 稀有度 × 7 分类 · 扇形堆叠 → 悬停查阅 → 点击抽出 → 评审 → 收回
 *   三种视图：扇形 / 白板模式 / 网格视图（全部取出）
 * 依赖 governance-api.js 的 resolveBase/fetchJson（全局）。
 */
(function (global) {
  var CURRENT_TASK = null;
  var frames = [];          // 当前渲染的卡片元素
  var activeIdx = -1;       // 当前抽出的卡（-1 = 无）
  var hoverIdx = -1;        // 当前查阅的卡（-1 = 无）
  var drawing = false;      // 动画进行中锁
  var gridMode = false;
  var boardMode = false;

  /* ============ 设计规格映射（metric-card-doc v1.0.0） ============ */
  // 14 主题
  var THEME_NAMES = {
    sale: '交易', mall: '商场', base: '基础', cont: '合同', cust: '消费者',
    fin: '财务', fund: '资金', hr: '人资', mkt: '营销', prod: '商品',
    ptnr: '商户', shop: '店铺', traf: '流量', wk: '流程'
  };
  // 7 二级分类
  var CAT_NAMES = {
    overview: '概览', report: '报表', detail: '明细', trend: '趋势',
    alert: '预警', standard: '口径', dimension: '维度'
  };
  var CAT_ALIAS = {
    '概览': 'overview', '报表': 'report', '明细': 'detail', '趋势': 'trend',
    '预警': 'alert', '口径': 'standard', '维度': 'dimension'
  };
  // 3 指标类型
  var TYPE_NAMES = { atomic: '原子', derived: '衍生', composite: '复合' };
  // 4 档评分稀有度
  var RARITIES = [
    { min: 90, key: 'excellent', name: '优秀' },
    { min: 75, key: 'good', name: '良好' },
    { min: 60, key: 'pass', name: '合格' },
    { min: 0, key: 'poor', name: '待改进' }
  ];
  function rarityOf(score) {
    for (var i = 0; i < RARITIES.length; i++) if (score >= RARITIES[i].min) return RARITIES[i];
    return RARITIES[3];
  }
  // 7 分类 SVG 图标（照参考）
  var ICONS = {
    overview: '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9" opacity="0.9"/><path d="M12 3.5v3M12 17.5v3M3.5 12h3M17.5 12h3" opacity="0.85"/><circle cx="12" cy="12" r="2.5"/></svg>',
    report: '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="3" width="16" height="18" rx="1.5" opacity="0.9"/><path d="M7 8h10M7 12h10M7 16h6" opacity="0.85"/></svg>',
    detail: '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="6" opacity="0.9"/><path d="M16 16l4 4" opacity="0.85"/><path d="M9 11h4M11 9v4" opacity="0.6"/></svg>',
    trend: '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 18l5-5 4 4 6-8" opacity="0.9"/><path d="M14 9h4v4" opacity="0.85"/><path d="M3 21h18" opacity="0.5"/></svg>',
    alert: '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l10 17H2z" opacity="0.9"/><path d="M12 10v5M12 17v0.5" opacity="0.85"/></svg>',
    standard: '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l2.4 5 5.6.7-4 4 1 5.5L12 16l-5 2.2 1-5.5-4-4 5.6-.7z" opacity="0.9"/></svg>',
    dimension: '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="1.5" opacity="0.9"/><path d="M3 9h18M9 3v18" opacity="0.85"/></svg>'
  };

  /* ============ 字段兜底映射（有真实字段用真实值，无则默认一般） ============ */
  function themeOf(row) {
    var d = String(row.domain_code || '').toLowerCase();
    return THEME_NAMES[d] ? d : 'base';
  }
  function catOf(row) {
    var cand = [row.category_l2, row.category_l1, row.cat, row.metric_cat, row.category];
    for (var i = 0; i < cand.length; i++) {
      var v = String(cand[i] || '').toLowerCase().trim();
      if (!v) continue;
      if (CAT_NAMES[v]) return v;
      if (CAT_ALIAS[v]) return CAT_ALIAS[v];
      // 模糊包含（如 "经营概览" → overview）
      for (var k in CAT_NAMES) {
        if (v.indexOf(k) >= 0 || v.indexOf(CAT_NAMES[k]) >= 0) return k;
      }
    }
    return 'overview';
  }
  function typeOf(row) {
    var t = String(row.metric_type || '').toLowerCase().trim();
    if (t === 'derived' || t === '衍生' || t === '派生') return 'derived';
    if (t === 'composite' || t === '复合') return 'composite';
    return 'atomic';
  }
  function scoreOf(row) {
    // 评分字段优先；无 → 默认一般（合格 70）；评审状态联动稀有度
    var raw = (row.score !== undefined && row.score !== null && row.score !== '') ? row.score
      : (row.governance_score !== undefined && row.governance_score !== null) ? row.governance_score
      : null;
    var s = raw === null ? NaN : parseFloat(raw);
    if (!isFinite(s)) {
      var st = row._status;
      if (st === 'draft') s = 95;
      else if (st === 'rejected' || st === 'error') s = 40;
      else if (st === 'skip') s = 55;
      else s = 70; // 默认一般 → 合格
    }
    return s;
  }
  function mapRow(row, i) {
    var st = row._status || 'pending';
    return {
      code: row.metric_id || row.metric_en || '—',
      name: row.metric_cn || '—',
      theme: themeOf(row),
      cat: catOf(row),
      type: typeOf(row),
      score: scoreOf(row),
      unit: row.unit || '—',
      cycle: row.frequency || '—',
      precision: row.precision || '—',
      table: row.physical_table || '—',
      dims: escTags(row.dimensions),
      desc: row.caliber_desc || '—',
      formula: row.formula_cn || row.formula || '—',
      tech: row.formula || row.tech_caliber || '—',
      source: row.data_sources || row.data_source || '—',
      owner: row.owner || '—',
      ver: row.version || 'v1.0.0',
      verNote: row.version_note || '',
      status: st
    };
  }

  function escTags(s) {
    return String(s || '').split(/[,，、;；]/).map(function (t) { return t.trim(); }).filter(Boolean);
  }

  /* ============ API 工具（复用全局） ============ */
  function resolveApiBase() {
    var cached = global.DG_API_BASE;
    if (cached) return Promise.resolve(cached);
    return fetch('/health', { method: 'GET' })
      .then(function (r) { return r.ok ? '' : (function () { throw new Error('no-api'); })(); })
      .catch(function () {
        global.DG_API_BASE = 'http://127.0.0.1:8765';
        return global.DG_API_BASE;
      });
  }
  function api(path, options) {
    options = options || {};
    options.headers = options.headers || {};
    if (options.body && !options.headers['Content-Type']) {
      options.headers['Content-Type'] = 'application/json';
    }
    return resolveApiBase().then(function (base) {
      return fetch(base + path, options).then(async function (r) {
        var text = await r.text();
        var data = null;
        try { data = JSON.parse(text); } catch (_) {
          var head = String(text || '').slice(0, 80).replace(/\s+/g, ' ');
          throw new Error(path + ' 返回非 JSON (status=' + r.status + ')：' + head);
        }
        if (!r.ok) throw new Error((data && data.detail) || (path + ' ' + r.status));
        return data;
      });
    });
  }
  function esc(s) {
    if (s == null) return '';
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  /* ---------- 上传 ---------- */
  function uploadImportTaskFile() {
    var fileInput = document.getElementById('importTaskFile');
    if (!fileInput || !fileInput.files || !fileInput.files[0]) {
      if (window.toast) toast('请先选择 CSV 文件');
      return;
    }
    var reader = new FileReader();
    reader.onload = function () {
      var csvText = String(reader.result || '');
      api('/api/import-tasks/upload', { method: 'POST', body: JSON.stringify({ csv: csvText }) })
        .then(function (data) {
          if (window.toast) toast('已生成 ' + data.created + ' 个待办任务', 'success');
          loadImportTasks();
        })
        .catch(function (e) {
          if (window.toast) toast('上传失败: ' + e.message);
        });
    };
    reader.readAsText(fileInput.files[0]);
  }

  /* ---------- 任务列表 ---------- */
  function loadImportTasks() {
    api('/api/import-tasks').then(function (data) {
      var tasks = data.tasks || [];
      var count = document.getElementById('importTaskCount');
      if (count) count.textContent = '共 ' + tasks.length + ' 个任务';
      var tbody = document.getElementById('importTaskBody');
      if (!tbody) return;
      if (!tasks.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-sm text-muted" style="padding:12px;">暂无任务，请先上传 CSV</td></tr>';
        return;
      }
      tbody.innerHTML = tasks.map(function (t) {
        var st = t.status;
        var badge = st === 'done' ? 'badge-pass' : (st === 'reviewing' ? 'badge-warn' : 'badge-neutral');
        var stLabel = { pending: '待处理', processing: '处理中', reviewing: '评审中', done: '已完成' }[st] || st;
        var dedup = t.dedup_result || {};
        var prog = t.review_progress || {};
        var dedupTxt = dedup.total
          ? (dedup.new_count + ' 新 / ' + dedup.dup_count + ' 重 / ' + dedup.suspect_count + ' 疑')
          : '未处理';
        var progTxt = prog.total ? (prog.reviewed + '/' + prog.total + '（通过 ' + prog.approved + '）') : '—';
        return (
          '<tr>' +
          '<td class="text-mono text-sm">' + esc(t.task_id) + '</td>' +
          '<td>' + t.group_no + '</td>' +
          '<td>' + t.total_rows + '</td>' +
          '<td><span class="badge ' + badge + '">' + stLabel + '</span></td>' +
          '<td class="text-sm">' + dedupTxt + '</td>' +
          '<td class="text-sm">' + progTxt + '</td>' +
          '<td><button class="btn btn-xs btn-primary" onclick="openImportTask(\'' + esc(t.task_id) + '\')">查看</button></td>' +
          '</tr>'
        );
      }).join('');
    }).catch(function (e) {
      if (window.toast) toast('加载任务失败: ' + e.message);
    });
  }

  /* ---------- 任务详情 ---------- */
  function openImportTask(taskId) {
    api('/api/import-tasks/' + encodeURIComponent(taskId)).then(function (task) {
      CURRENT_TASK = task;
      var card = document.getElementById('importTaskDetailCard');
      var title = document.getElementById('importTaskDetailTitle');
      var meta = document.getElementById('importTaskDetailMeta');
      if (title) title.textContent = '任务 ' + task.task_id + '（第 ' + task.group_no + ' 组）';
      if (meta) {
        var stLabel = { pending: '待处理', processing: '处理中', reviewing: '评审中', done: '已完成' }[task.status] || task.status;
        meta.textContent = '共 ' + task.total_rows + ' 条 | 状态: ' + stLabel;
      }
      if (card) card.style.display = '';
      renderTaskCards(task, 0); // 参考行为：打开任务自动抽出第一张
    }).catch(function (e) {
      if (window.toast) toast('加载任务失败: ' + e.message);
    });
  }

  /* ============ 渲染：卡包（参考 v8 状态机） ============ */
  function renderTaskCards(task, drawIdx) {
    var host = document.getElementById('importTaskCards');
    if (!host) return;
    var rows = task.generated || [];
    if (!rows.length) {
      host.innerHTML = '<div class="text-sm text-muted" style="padding:12px;">尚未处理，点击右上「去重 + AI 生成」开始。</div>';
      return;
    }
    activeIdx = -1; hoverIdx = -1; frames = [];

    // 结构：stage > pack-zone（panel 已移入任务详情 header，清单已去掉）
    host.innerHTML =
      '<div class="stage">' +
        '<div class="pack-zone">' +
          '<div class="pack-base" aria-hidden="true"></div>' +
          '<div class="pack" id="mc8pack" aria-label="指标卡包，悬停查阅，点击抽出"></div>' +
        '</div>' +
      '</div>' +
      '<div class="overlay" id="mc8overlay"></div>' +
      '<div class="draw-actions" id="mc8draw-actions">' +
        '<button class="act-btn reject" id="mc8btn-reject" type="button">✕ 打回</button>' +
        '<button class="act-btn ghost2" id="mc8btn-back" type="button">📥 收回卡包</button>' +
        '<button class="act-btn approve" id="mc8btn-approve" type="button">✓ 进入草稿</button>' +
        '<span class="draw-state" id="mc8draw-state"></span>' +
      '</div>';

    var pack = document.getElementById('mc8pack');
    // 30 张适配：错位 20px / 14 张以内 34px（参考值）
    var step = rows.length > 14 ? 20 : 34;
    pack.style.setProperty('--fan-w', ((rows.length - 1) * step + 384) + 'px');

    rows.forEach(function (row, i) {
      buildFrame(pack, row, i, rows.length, step);
    });

    bindEvents();


    // 初始/评审后自动抽出指定卡（参考行为）；drawIdx < 0 不抽
    if (drawIdx >= 0 && frames[drawIdx]) {
      var target = frames[drawIdx];
      requestAnimationFrame(function () {
        requestAnimationFrame(function () { draw(target); });
      });
    }
  }

  /* 控制面板已移入任务详情卡 header（panelHtml 不再使用） */

  /* 单卡构建：扇形堆叠几何（参考 ch10） */
  function buildFrame(pack, row, i, n, step) {
    var m = mapRow(row, i);
    var r = rarityOf(m.score);

    var baseAngle = -18 * i / (n - 1);
    var jitterA = ((i * 37) % 9) - 4;
    var jitterX = ((i * 53) % 13) - 6;
    var jitterY = ((i * 29) % 7) - 3;
    var fanDeg = baseAngle + jitterA;
    var stackX = (n - 1 - i) * step + jitterX;
    var stackY = jitterY;

    var els = document.createElement('div');
    els.className = 'frame';
    els.dataset.theme = m.theme;
    els.dataset.rarity = r.key;
    els.dataset.cat = m.cat;
    els.dataset.type = m.type;
    els.dataset.idx = i;
    els.style.setProperty('--stack-x', stackX + 'px');
    els.style.setProperty('--stack-y', stackY + 'px');
    els.style.setProperty('--fan-deg', fanDeg + 'deg');
    els.style.zIndex = i + 1;

    els.innerHTML = cardHtml(m, i, n);
    pack.appendChild(els);
    frames.push(els);
  }

  /* 卡面（参考 ch7：18 字段 10 区块；静态元素照抄，动态字段接入） */
  function cardHtml(m, i, n) {
    var st = m.status;
    var stLabel = { pending: '待评审', skip: '重复', rejected: '已打回', draft: '已入草稿', error: '生成失败' }[st] || '待评审';
    var r = rarityOf(m.score);
    var dims = m.dims.map(function (d) { return '<span class="tag">' + esc(d) + '</span>'; }).join('');
    return (
      '<span class="corner tl"></span><span class="corner tr"></span>' +
      '<span class="corner bl"></span><span class="corner br"></span>' +
      '<article class="card" data-id="' + esc(m.code) + '" data-theme="' + m.theme + '">' +
        '<span class="card-accent"></span>' +
        '<span class="type-badge ' + m.type + '">' + TYPE_NAMES[m.type] + '</span>' +
        '<span class="rare-badge"><span class="star">★</span>' + r.name + '</span>' +
        '<div class="topline">' +
          '<span class="faction">' + (THEME_NAMES[m.theme] || m.theme) + '<span class="sep">/</span>' + (CAT_NAMES[m.cat] || m.cat) + '</span>' +
          '<span class="quality"><span class="gem"></span>周期总量</span>' +
        '</div>' +
        '<div class="icon-zone">' +
          '<span class="icon-halo"></span>' +
          '<span class="icon-ring" aria-hidden="true">' + (ICONS[m.cat] || ICONS.overview) + '</span>' +
        '</div>' +
        '<div class="title-zone">' +
          '<h1>' + esc(m.name) + '</h1>' +
          '<div class="sub-id">' + esc(m.code) + '</div>' +
          '<div class="badge-row">' +
            '<span class="badge biz">业务</span>' +
            '<span class="badge tech">技术</span>' +
            '<span class="badge dm">数据管理</span>' +
          '</div>' +
        '</div>' +
        '<section class="stats">' +
          '<div class="stat"><div class="lbl">计量</div><div class="val">' + esc(m.unit) + '</div></div>' +
          '<div class="stat"><div class="lbl">周期</div><div class="val">' + esc(m.cycle) + '</div></div>' +
          '<div class="stat"><div class="lbl">精度</div><div class="val">' + esc(m.precision) + '</div></div>' +
          '<div class="stat"><div class="lbl">物理表</div><div class="val mono">' + esc(m.table) + '</div></div>' +
        '</section>' +
        (dims ? '<section class="affix"><div class="affix-head">统计维度</div><div class="affix-tags">' + dims + '</div></section>' : '') +
        '<section class="desc-box">' + esc(m.desc) + '</section>' +
        '<section class="skill-box">' +
          '<div class="sl">✦ 计算公式</div>' +
          '<div class="sd">' + esc(m.formula) + '</div>' +
          '<div class="sc">' + esc(m.tech) + '</div>' +
        '</section>' +
        '<section class="bars">' +
          '<div class="bar-row"><span class="bname">绿灯</span><div class="bar-track"><div class="bar-fill bar-green"><span class="tick">≥ 目标</span></div></div></div>' +
          '<div class="bar-row"><span class="bname">黄灯</span><div class="bar-track"><div class="bar-fill bar-yellow"><span class="tick">-10%</span></div></div></div>' +
          '<div class="bar-row"><span class="bname">红灯</span><div class="bar-track"><div class="bar-fill bar-red"><span class="tick">-20%</span></div></div></div>' +
        '</section>' +
        '<section class="meta">' +
          '<div class="row"><span class="k">来源</span><span class="v sans">' + esc(m.source) + '</span></div>' +
          '<div class="row"><span class="k">负责</span><span class="v sans">' + esc(m.owner) + '</span></div>' +
        '</section>' +
        '<footer class="foot">' +
          '<span class="lv"><span class="lvnum">' + esc(m.ver) + '</span>强化等级</span>' +
          '<span class="ver">' + esc(m.verNote || stLabel) + '</span>' +
        '</footer>' +
      '</article>'
    );
  }

  /* ============ 交互状态机（参考 ch8） ============ */
  function peek(el) {
    var idx = +el.dataset.idx;
    if (activeIdx >= 0) return;
    if (hoverIdx === idx) return;
    frames.forEach(function (f) { f.classList.remove('hovered'); });
    hoverIdx = idx;
    el.classList.add('hovered');
    var pack = document.getElementById('mc8pack');
    if (pack) pack.classList.add('dimmed');

  }
  function peekOut() {
    frames.forEach(function (f) { f.classList.remove('hovered'); });
    var pack = document.getElementById('mc8pack');
    if (pack) pack.classList.remove('dimmed');
    hoverIdx = -1;

  }
  function centerOffset(el, dy, scale) {
    var r = el.getBoundingClientRect();
    var vw = document.documentElement.clientWidth;
    var vh = document.documentElement.clientHeight;
    var cx = vw / 2 - (r.left + r.width / 2);
    var cy = vh / 2 - (r.top + r.height / 2) + dy;
    el.style.setProperty('--fly-x', cx + 'px');
    el.style.setProperty('--fly-y', cy + 'px');
    el.style.setProperty('--fly-scale', scale);
  }
  function clearFly(el) {
    el.style.removeProperty('--fly-x');
    el.style.removeProperty('--fly-y');
    el.style.removeProperty('--fly-scale');
  }
  function draw(el) {
    if (drawing) return;
    var idx = +el.dataset.idx;
    if (activeIdx === idx) return;
    drawing = true;
    peekOut();
    frames.forEach(function (f) {
      f.classList.remove('active-lock', 'retracting');
      clearFly(f);
    });
    centerOffset(el, 0, 1.15);
    el.classList.add('active-lock');
    activeIdx = idx;
    var overlay = document.getElementById('mc8overlay');
    var actions = document.getElementById('mc8draw-actions');
    if (overlay) overlay.classList.add('show');
    if (actions) actions.classList.add('show');
    updateReviewButtons();
    setTimeout(function () { drawing = false; }, 580);

  }
  function putBack() {
    if (drawing || activeIdx < 0) return;
    drawing = true;
    var el = frames[activeIdx];
    el.classList.add('retracting');
    setTimeout(function () {
      el.classList.remove('active-lock', 'retracting');
      clearFly(el);
      activeIdx = -1;
      var overlay = document.getElementById('mc8overlay');
      var actions = document.getElementById('mc8draw-actions');
      var pack = document.getElementById('mc8pack');
      if (overlay) overlay.classList.remove('show');
      if (actions) actions.classList.remove('show');
      if (pack) pack.classList.remove('dimmed');
      drawing = false;

    }, 520);
  }
  /* 评审按钮状态：抽出卡下方左右（打回 / 进入草稿） */
  function updateReviewButtons() {
    var actions = document.getElementById('mc8draw-actions');
    if (!actions || !CURRENT_TASK) return;
    var btnReject = document.getElementById('mc8btn-reject');
    var btnApprove = document.getElementById('mc8btn-approve');
    var btnBack = document.getElementById('mc8btn-back');
    var state = document.getElementById('mc8draw-state');
    var rows = CURRENT_TASK.generated || [];
    if (activeIdx < 0 || !rows[activeIdx]) return;
    var st = rows[activeIdx]._status || 'pending';
    var done = st === 'draft' || st === 'skip' || st === 'error';
    if (done) {
      btnReject.style.display = 'none';
      btnApprove.style.display = 'none';
      btnBack.style.display = 'none';
      state.style.display = '';
      state.textContent = st === 'draft' ? '✓ 已入草稿' : (st === 'skip' ? '重复 · 已跳过' : '生成失败');
    } else {
      btnReject.style.display = '';
      btnApprove.style.display = '';
      btnBack.style.display = '';
      state.style.display = 'none';
      btnReject.onclick = function () { reviewImportRow(activeIdx, 'reject'); };
      btnApprove.onclick = function () { reviewImportRow(activeIdx, 'approve'); };
    }
  }
  /* ============ 视图模式（参考 ch9） ============ */
  function setGrid(on) {
    gridMode = on;
    var pack = document.getElementById('mc8pack');
    var zone = document.querySelector('#importTaskCards .pack-zone');
    if (pack) pack.classList.toggle('grid-view', on);
    if (zone) zone.classList.toggle('grid-active', on);
    updateHeaderButtons();
    if (!on) {
      frames.forEach(function (f) {
        f.classList.remove('active-lock', 'retracting', 'hovered');
        clearFly(f);
      });
      var overlay = document.getElementById('mc8overlay');
      var actions = document.getElementById('mc8draw-actions');
      if (pack) pack.classList.remove('dimmed');
      if (overlay) overlay.classList.remove('show');
      if (actions) actions.classList.remove('show');
      activeIdx = -1;
    }
  }
  function toggleBoardMode() {
    if (gridMode) setGrid(false);
    boardMode = !boardMode;
    var pack = document.getElementById('mc8pack');
    if (pack) pack.classList.toggle('board-mode', boardMode);
    updateHeaderButtons();
    putBack();
  }
  function updateHeaderButtons() {
    var btnGrid = document.getElementById('mc8btn-grid');
    var btnBoard = document.getElementById('mc8btn-board');
    if (btnGrid) btnGrid.textContent = gridMode ? '📊 收起网格' : '📤 全部取出';
    if (btnBoard) btnBoard.textContent = boardMode ? '🎴 完整模式' : '📄 白板模式';
  }

  /* ============ 事件绑定 ============ */
  function bindEvents() {
    frames.forEach(function (f) {
      f.addEventListener('mouseenter', function () {
        if (!gridMode) peek(f);
      });
      f.addEventListener('mouseleave', function () {
        if (!gridMode) peekOut();
      });
      f.addEventListener('click', function () {
        if (gridMode) {
          setGrid(false);
          requestAnimationFrame(function () { draw(f); });
          return;
        }
        if (activeIdx === +f.dataset.idx) { putBack(); return; }
        draw(f);
      });
    });
    var overlay = document.getElementById('mc8overlay');
    if (overlay) overlay.addEventListener('click', putBack);
    var btnBack = document.getElementById('mc8btn-back');
    if (btnBack) btnBack.addEventListener('click', putBack);
  }

  /* 键盘：← → 切换抽出的卡（参考无，评审流程增益），Esc 收回 */
  document.addEventListener('keydown', function (e) {
    if (!CURRENT_TASK) return;
    var rows = CURRENT_TASK.generated || [];
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      if (activeIdx < 0) return;
      e.preventDefault();
      var ni = activeIdx + 1;
      while (ni < rows.length && ['draft', 'skip', 'error'].indexOf(rows[ni]._status) >= 0) ni++;
      if (ni < rows.length && frames[ni]) draw(frames[ni]);
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      if (activeIdx < 0) return;
      e.preventDefault();
      var pi = activeIdx - 1;
      while (pi >= 0 && ['draft', 'skip', 'error'].indexOf(rows[pi]._status) >= 0) pi--;
      if (pi >= 0 && frames[pi]) draw(frames[pi]);
    } else if (e.key === 'Escape') {
      if (activeIdx >= 0) putBack();
    }
  });
  window.addEventListener('resize', function () {
    if (activeIdx >= 0 && frames[activeIdx]) centerOffset(frames[activeIdx], 0, 1.15);
  });

  /* ---------- 处理任务：去重 + AI 生成 ---------- */
  function processImportTask() {
    if (!CURRENT_TASK) return;
    if (window.toast) toast('⏳ 去重 + AI 生成中（逐条生成，请稍候）…');
    api('/api/import-tasks/' + encodeURIComponent(CURRENT_TASK.task_id) + '/process', { method: 'POST', body: '{}' })
      .then(function (task) {
        CURRENT_TASK = task;
        if (window.toast) toast('✅ 处理完成：新增 ' + (task.dedup_result.new_count || 0) + '，重复 ' + (task.dedup_result.dup_count || 0) + '，疑似 ' + (task.dedup_result.suspect_count || 0), 'success');
        renderTaskCards(task, 0);
        loadImportTasks();
      })
      .catch(function (e) {
        if (window.toast) toast('处理失败: ' + e.message);
      });
  }

  /* ---------- 逐卡评审 ---------- */
  function reviewImportRow(rowIndex, action) {
    if (!CURRENT_TASK) return;
    api('/api/import-tasks/' + encodeURIComponent(CURRENT_TASK.task_id) + '/review', {
      method: 'POST',
      body: JSON.stringify({ row_index: rowIndex, action: action, reason: action === 'reject' ? '人工打回' : '' })
    }).then(function (task) {
      CURRENT_TASK = task;
      if (window.toast) toast(action === 'approve' ? '✓ 已通过，指标进入草稿' : '已打回', action === 'approve' ? 'success' : '');
      // 自动抽出下一张待评审卡（连续评审不卡壳）；审完则不抽
      var rows = task.generated || [];
      var nextIdx = -1;
      for (var i = 0; i < rows.length; i++) {
        var s = rows[i]._status;
        if (s === 'pending' || s === 'rejected') { nextIdx = i; break; }
      }
      renderTaskCards(task, nextIdx);
      loadImportTasks();
    }).catch(function (e) {
      if (window.toast) toast('评审失败: ' + e.message);
    });
  }

  function closeImportTaskDetail() {
    var card = document.getElementById('importTaskDetailCard');
    if (card) card.style.display = 'none';
    CURRENT_TASK = null;
    activeIdx = -1; hoverIdx = -1; frames = [];
  }

  /* ---------- 导出 ---------- */
  global.uploadImportTaskFile = uploadImportTaskFile;
  global.loadImportTasks = loadImportTasks;
  global.openImportTask = openImportTask;
  global.processImportTask = processImportTask;
  global.reviewImportRow = reviewImportRow;
  global.closeImportTaskDetail = closeImportTaskDetail;
  global.renderTaskCards = renderTaskCards;
  global.toggleGridMode = function () {
    if (drawing) return;
    peekOut();
    if (gridMode) { setGrid(false); return; }
    setGrid(true);
    activeIdx = -1;
  };
  global.toggleBoardMode = toggleBoardMode;
})(window);
