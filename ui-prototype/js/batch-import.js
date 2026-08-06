/**
 * 批量导入（H31 P1）：CSV 上传 → 待办任务 → 去重 + AI 生成 → 逐卡人工评审 → 草稿。
 * 依赖 governance-api.js 的 resolveBase/fetchJson（全局）。
 */
(function (global) {
  var CURRENT_TASK = null;
  // 卡包桌：筛选状态 + 抽出的卡在过滤结果中的索引（-1 = 未抽出）
  var CUR_FILTER = 'all';   // all / pending / draft / rejected
  var CUR_DOMAIN = 'all';   // all / domain_code
  var DRAWN_IDX = -1;

  // 主题域 → 炉石卡插画配色 + emoji 图标（H32 魔兽卡风格）
  var DOMAIN_THEMES = {
    sale: { icon: '💰', c1: '#8b6914', c2: '#3a2a08' },
    cust: { icon: '👥', c1: '#1e4a8a', c2: '#0a1f3a' },
    prod: { icon: '📦', c1: '#8a4513', c2: '#3a1f08' },
    mall: { icon: '🏛️', c1: '#5a3a8a', c2: '#2a1a4a' },
    mkt: { icon: '📢', c1: '#8a3a6a', c2: '#3a1a2a' },
    cont: { icon: '📜', c1: '#5a5a3a', c2: '#2a2a1a' },
    fin: { icon: '💎', c1: '#2a8a5a', c2: '#0a3a2a' },
    _default: { icon: '📊', c1: '#4a4a4a', c2: '#1a1a1a' }
  };
  // 主题域中文名（迷你卡属性标签用）
  var DOMAIN_CN = {
    sale: '交易', cust: '消费者', prod: '商品', mall: '运营',
    mkt: '营销', cont: '招商租赁', fin: '财务'
  };
  // 指标卡视觉系统 v5 映射：主题域 → 主题色 | 类型 → 纹样 | 状态 → 稀有度
  var MC_THEMES = { sale: 'trade', cont: 'lease', fin: 'finance', mall: 'ops', mkt: 'marketing', cust: 'service', prod: 'service' };
  var MC_RARITY_NAME = { legendary: '传说', epic: '史诗', rare: '稀有', uncommon: '精良', common: '普通' };
  function mcTheme(domain) { return MC_THEMES[String(domain || '').toLowerCase()] || 'ops'; }
  function mcCat(type) { return type === 'atomic' ? 'order' : 'contract'; }
  function mcRarity(st) {
    return ({ pending: 'uncommon', rejected: 'common', draft: 'epic', skip: 'common', error: 'common' }[st]) || 'uncommon';
  }
  function escTags(s) {
    // 逗号/顿号分隔 → 标签数组
    return String(s || '').split(/[,，、]/).map(function (t) { return t.trim(); }).filter(Boolean);
  }

  function themeFor(domain) {
    return DOMAIN_THEMES[(domain || '').toLowerCase()] || DOMAIN_THEMES._default;
  }

  function cardCost(row) {
    // 从 metric_id 末段取数字（如 M_SALE_001 → 1）；失败回退 5
    var parts = String(row.metric_id || '').split('_');
    var tail = parts[parts.length - 1] || '5';
    var n = parseInt(tail, 10);
    if (!isFinite(n) || n <= 0) n = (row.metric_cn || '').length % 9 + 1;
    return String(Math.max(1, Math.min(9, n)));
  }

  function cardStat(row) {
    return String(((row.metric_cn || '').length % 7) + 1);
  }

  // 复用全局 API 探测：DG_API_BASE 未设置时先探测（与 governance-api 同逻辑）
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
        // 先取 text 再 parse，避免 200/非2xx + HTML 时抛底层 SyntaxError
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
      DRAWN_IDX = -1; // 打开新任务未抽卡
      var card = document.getElementById('importTaskDetailCard');
      var title = document.getElementById('importTaskDetailTitle');
      var meta = document.getElementById('importTaskDetailMeta');
      if (title) title.textContent = '任务 ' + task.task_id + '（第 ' + task.group_no + ' 组）';
      if (meta) {
        var stLabel = { pending: '待处理', processing: '处理中', reviewing: '评审中', done: '已完成' }[task.status] || task.status;
        meta.textContent = '共 ' + task.total_rows + ' 条 | 状态: ' + stLabel;
      }
      if (card) card.style.display = '';
      renderTaskCards(task);
    }).catch(function (e) {
      if (window.toast) toast('加载任务失败: ' + e.message);
    });
  }

  function renderTaskCards(task) {
    var host = document.getElementById('importTaskCards');
    if (!host) return;
    var rows = task.generated || [];
    if (!rows.length) {
      host.innerHTML = '<div class="text-sm text-muted" style="padding:12px;">尚未处理，点击「去重 + AI 生成」开始。</div>';
      return;
    }
    host.classList.add('mc-table');

    var filtered = filterRows(rows);
    if (DRAWN_IDX < 0 || DRAWN_IDX >= filtered.length) DRAWN_IDX = -1;

    // 筛选器（状态 tabs + 主题域）
    var filterHtml = buildFilterHtml(rows);
    // 卡包
    var packHtml = buildPackHtml(filtered);
    // 抽出的完整卡
    var drawHtml = '';
    if (DRAWN_IDX >= 0 && filtered[DRAWN_IDX]) {
      var dr = filtered[DRAWN_IDX];
      drawHtml =
        '<div class="mc-draw open">' +
          '<button class="mc-draw-close" onclick="closeDraw()" title="收回（Esc）">✕</button>' +
          buildMcCard(dr, DRAWN_IDX, filtered.length, dr._status || 'pending') +
          '<div class="mc-draw-nav">' +
            '<button class="btn" onclick="switchDraw(-1)" ' + (DRAWN_IDX <= 0 ? 'disabled' : '') + '>← 上一张</button>' +
            '<span style="margin:0 12px;">' + (DRAWN_IDX + 1) + ' / ' + filtered.length + '</span>' +
            '<button class="btn" onclick="switchDraw(1)" ' + (DRAWN_IDX >= filtered.length - 1 ? 'disabled' : '') + '>下一张 →</button>' +
          '</div>' +
        '</div>';
    }
    var hint =
      '<div class="import-fan-hint">' +
        (task.status === 'pending' ? '⚠️ 任务未处理 · 点击右上「<b>去重 + AI 生成</b>」开始 → ' : '') +
        '点击卡包抽卡 · ← → 切换 · Esc 收回' +
      '</div>';
    host.innerHTML = filterHtml + '<div class="mc-pack-zone">' + packHtml + drawHtml + '</div>' + hint;
  }

  /* ── 筛选：按状态 + 主题域过滤 ── */
  function filterRows(rows) {
    return (rows || []).filter(function (r) {
      var st = r._status || 'pending';
      var group = st === 'draft' ? 'draft' : (st === 'rejected' ? 'rejected' : 'pending');
      if (CUR_FILTER === 'pending' && group !== 'pending') return false;
      if (CUR_FILTER === 'draft' && group !== 'draft') return false;
      if (CUR_FILTER === 'rejected' && group !== 'rejected') return false;
      if (CUR_DOMAIN !== 'all' && String(r.domain_code || '').toLowerCase() !== CUR_DOMAIN) return false;
      return true;
    });
  }

  function buildFilterHtml(rows) {
    var cnt = { pending: 0, draft: 0, rejected: 0 };
    rows.forEach(function (r) {
      var st = r._status || 'pending';
      var g = st === 'draft' ? 'draft' : (st === 'rejected' ? 'rejected' : 'pending');
      cnt[g]++;
    });
    var tabs = [
      ['all', '全部', rows.length],
      ['pending', '待评审', cnt.pending],
      ['draft', '已通过', cnt.draft],
      ['rejected', '已打回', cnt.rejected]
    ].map(function (t) {
      return '<button class="' + (CUR_FILTER === t[0] ? 'active' : '') + '" onclick="setFilter(\'' + t[0] + '\')">' + t[1] + ' ' + t[2] + '</button>';
    }).join('');
    var doms = ['all'];
    rows.forEach(function (r) {
      var d = String(r.domain_code || '').toLowerCase();
      if (d && doms.indexOf(d) < 0) doms.push(d);
    });
    var domOpts = doms.map(function (d) {
      var label = d === 'all' ? '全部主题域' : (DOMAIN_CN[d] ? DOMAIN_CN[d] + '域' : d);
      return '<option value="' + d + '"' + (CUR_DOMAIN === d ? ' selected' : '') + '>' + label + '</option>';
    }).join('');
    return (
      '<div class="mc-filter">' +
        '<span class="mc-filter-title">指标卡包</span>' +
        '<span class="mc-filter-count">共 ' + rows.length + ' 张</span>' +
        '<div class="mc-filter-tabs">' + tabs + '</div>' +
        '<select class="mc-filter-domain" onchange="setDomain(this.value)">' + domOpts + '</select>' +
        ((CUR_FILTER !== 'all' || CUR_DOMAIN !== 'all') ?
          '<button class="mc-filter-reset" onclick="setFilter(\'all\');setDomain(\'all\')">重置</button>' : '') +
      '</div>'
    );
  }

  function buildPackHtml(filtered) {
    if (!filtered.length) {
      return '<div class="mc-pack-empty">该筛选下暂无指标卡<br/><span style="font-size:11px;">切换筛选或重置查看全部</span></div>';
    }
    var theme = mcTheme(filtered[0].domain_code);
    var rarity = mcRarity(filtered[0]._status || 'pending');
    var groupLabel = { all: '全部指标', pending: '待评审指标', draft: '已通过指标', rejected: '已打回指标' }[CUR_FILTER] || '指标';
    return (
      '<div class="mc-pack ' + theme + ' ' + rarity + '" id="mcPack" onclick="drawCard()" title="点击抽卡">' +
        '<span class="deck-card d1"></span><span class="deck-card d2"></span><span class="deck-card d3"></span>' +
        '<div class="mc-pack-front">' +
          '<div class="mc-pack-count">' + filtered.length + '</div>' +
          '<div class="mc-pack-label">指标卡包</div>' +
          '<div class="mc-pack-sub">' + groupLabel + '</div>' +
        '</div>' +
        '<div class="mc-pack-hint">点击抽卡</div>' +
      '</div>'
    );
  }

  /* ── 抽卡 / 切换 / 收回 ── */
  function drawCard() {
    if (!CURRENT_TASK) return;
    var filtered = filterRows(CURRENT_TASK.generated || []);
    if (!filtered.length) return;
    var pack = document.getElementById('mcPack');
    if (pack) pack.classList.add('pop');
    DRAWN_IDX = 0;
    renderTaskCards(CURRENT_TASK);
  }

  function closeDraw() {
    DRAWN_IDX = -1;
    if (CURRENT_TASK) renderTaskCards(CURRENT_TASK);
  }

  function switchDraw(delta) {
    if (!CURRENT_TASK) return;
    var filtered = filterRows(CURRENT_TASK.generated || []);
    if (!filtered.length) return;
    var ni = DRAWN_IDX + delta;
    if (ni < 0 || ni >= filtered.length) return;
    DRAWN_IDX = ni;
    renderTaskCards(CURRENT_TASK);
  }

  function setFilter(f) {
    CUR_FILTER = f;
    DRAWN_IDX = -1;
    if (CURRENT_TASK) renderTaskCards(CURRENT_TASK);
  }

  function setDomain(d) {
    CUR_DOMAIN = d;
    DRAWN_IDX = -1;
    if (CURRENT_TASK) renderTaskCards(CURRENT_TASK);
  }

  /* 指标卡视觉系统 v5 卡面渲染（参考 ui-prototype/metric-card-ref.html） */
  function buildMcCard(row, i, n, st) {
    var stLabel = { pending: '待评审', skip: '重复', rejected: '已打回', draft: '已入草稿', error: '失败' }[st] || st;
    var dedupLabel = row._dedup === 'dup' ? '重复' : (row._dedup === 'suspect' ? '疑似' : '新增');
    var domCn = DOMAIN_CN[String(row.domain_code || '').toLowerCase()] || row.domain_code || '—';
    var typeCn = row.metric_type === 'derived' ? '派生指标' : '原子指标';
    var unit = row.unit || '—';
    var freq = row.frequency || '—';
    var vtype = row.value_type || '—';
    var prec = row.precision || '—';
    var dims = escTags(row.dimensions);
    var formula = row.formula || '';
    var formulaCn = row.formula_cn || '';
    var dataSources = row.data_sources || '—';
    var tech = row.tech_caliber || '—';
    var owner = row.owner || '—';
    var version = row.version || 'v1.0.0';
    var statusClass = { pending: 'b-pending', draft: 'b-draft', rejected: 'b-rejected', skip: 'b-skip' }[st] || 'b-pending';

    return (
      '<div class="mc-frame">' +
        '<span class="mc-corner tl"></span><span class="mc-corner tr"></span>' +
        '<span class="mc-corner bl"></span><span class="mc-corner br"></span>' +
        '<article class="mc-card" data-id="' + esc(row.metric_id || '') + '">' +
          '<div class="mc-status-row">' +
            '<span class="b ' + statusClass + '">' + stLabel + '</span>' +
            '<span class="b b-new">' + dedupLabel + '</span>' +
          '</div>' +
          '<span class="mc-rare-badge"><span class="star">★</span>' + (MC_RARITY_NAME[mcRarity(st)] || '') + '</span>' +
          '<div class="mc-topline">' +
            '<span class="mc-faction">' + esc(domCn) + '<span class="sep">/</span>' + typeCn + '</span>' +
            '<span class="mc-quality"><span class="gem"></span>' + esc(freq) + '</span>' +
          '</div>' +
          '<div class="mc-icon-zone">' +
            '<span class="mc-icon-halo"></span>' +
            '<span class="mc-icon-ring">' + themeFor(row.domain_code).icon + '</span>' +
          '</div>' +
          '<div class="mc-title-zone">' +
            '<h3 class="mc-title">' + esc(row.metric_cn || '—') + '</h3>' +
            '<div class="mc-sub-id">' + esc(row.metric_id || '—') + '</div>' +
          '</div>' +
          '<section class="mc-stats">' +
            '<div class="mc-stat"><div class="lbl">计量</div><div class="val">' + esc(unit) + '</div></div>' +
            '<div class="mc-stat"><div class="lbl">周期</div><div class="val">' + esc(freq) + '</div></div>' +
            '<div class="mc-stat"><div class="lbl">值类型</div><div class="val">' + esc(vtype) + '</div></div>' +
            '<div class="mc-stat"><div class="lbl">精度</div><div class="val">' + esc(prec) + '</div></div>' +
          '</section>' +
          (dims.length ?
            '<section class="mc-affix"><div class="mc-affix-head">统计维度</div><div class="mc-affix-tags">' +
              dims.map(function (d) { return '<span class="mc-tag">' + esc(d) + '</span>'; }).join('') +
            '</div></section>' : '') +
          '<section class="mc-desc-box">' + esc(row.caliber_desc || '—') + '</section>' +
          ((formula || formulaCn) ?
            '<section class="mc-skill-box">' +
              '<div class="sl">✦ 计算公式</div>' +
              (formulaCn ? '<div class="sd">' + esc(formulaCn) + '</div>' : '') +
              (formula ? '<div class="sc">' + esc(formula) + '</div>' : '') +
            '</section>' : '') +
          '<section class="mc-bars">' +
            '<div class="mc-bar-row"><span class="bname">绿灯</span><div class="mc-bar-track"><div class="mc-bar-fill mc-bar-green"><span class="tick">≥ 目标</span></div></div></div>' +
            '<div class="mc-bar-row"><span class="bname">黄灯</span><div class="mc-bar-track"><div class="mc-bar-fill mc-bar-yellow"><span class="tick">-10%</span></div></div></div>' +
            '<div class="mc-bar-row"><span class="bname">红灯</span><div class="mc-bar-track"><div class="mc-bar-fill mc-bar-red"><span class="tick">-20%</span></div></div></div>' +
          '</section>' +
          '<section class="mc-meta">' +
            '<div class="row"><span class="k">来源</span><span class="v sans">' + esc(dataSources) + '</span></div>' +
            '<div class="row"><span class="k">技术来源</span><span class="v">' + esc(tech) + '</span></div>' +
            '<div class="row"><span class="k">负责单位</span><span class="v sans">' + esc(owner) + '</span></div>' +
          '</section>' +
          '<footer class="mc-foot">' +
            '<span class="lv"><span class="lvnum">' + esc(version) + '</span>AI 生成</span>' +
            '<span class="ver">' + (i + 1) + '/' + n + '</span>' +
          '</footer>' +
          ((st === 'pending' || st === 'rejected') ?
            '<div class="mc-actions">' +
              '<button class="btn btn-reject" onclick="event.stopPropagation();reviewImportRow(' + i + ',\'reject\')">打回</button>' +
              '<button class="btn btn-approve" onclick="event.stopPropagation();reviewImportRow(' + i + ',\'approve\')">通过</button>' +
            '</div>' :
            (st === 'draft' ? '<div class="mc-done">已入草稿 · 可撤回</div>' : '')) +
        '</article>' +
      '</div>'
    );
  }

  /* 键盘导航：← → 切换抽出的卡，Esc 收回（任务详情打开时生效） */
  document.addEventListener('keydown', function (e) {
    if (!CURRENT_TASK) return;
    var filtered = filterRows(CURRENT_TASK.generated || []);
    if (!filtered.length || DRAWN_IDX < 0) return;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      switchDraw(1);
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      switchDraw(-1);
    } else if (e.key === 'Escape') {
      closeDraw();
    }
  });

  /* 复用指标库卡片的完整字段渲染（与指标库零差异：指标名称/编号、单位/值类型、
     时间周期/统计维度、应用场景/负责单位、报表、描述、公式、方法、预警、精度、
     数据来源、技术口径、物理表、版本记录 + 顶部分类栏） */
  function buildImportSpecHtml(row) {
    var MS = global.MetricSpec;
    if (MS && MS.apiRowToSpec && MS.buildSpecTableHtml) {
      try {
        var spec = MS.apiRowToSpec(row);
        return MS.buildSpecTableHtml(spec, { showBadge: false });
      } catch (_) { /* 降级走下方简版 */ }
    }
    // 降级简版（MetricSpec 未加载时兜底）
    var en = row.metric_en || '—';
    var cn = row.metric_cn || '—';
    var unit = row.unit || '—';
    var freq = row.frequency || '—';
    var desc = row.caliber_desc || '—';
    return (
      '<div class="indicator-spec-header">' +
        '<div class="indicator-spec-cat-tags">' +
          '<div class="indicator-spec-cat-tag"><span class="label">主题域：</span><span class="value">' + esc(row.domain_code || '—') + '</span></div>' +
        '</div>' +
        '<div class="indicator-spec-card-badge">指标卡片</div>' +
      '</div>' +
      '<div class="indicator-spec-card">' +
        '<table class="indicator-spec-table" cellspacing="0" cellpadding="0">' +
          '<tr><th class="indicator-spec-th indicator-spec-th--biz">指标名称</th><td class="indicator-spec-td">' + esc(cn) + '</td>' +
          '<th class="indicator-spec-th indicator-spec-th--biz">指标编号</th><td class="indicator-spec-td">' + esc(row.metric_id || '—') + '</td></tr>' +
          '<tr><th class="indicator-spec-th indicator-spec-th--tech">英文名</th><td class="indicator-spec-td" style="font-family:var(--font-mono);">' + esc(en) + '</td>' +
          '<th class="indicator-spec-th indicator-spec-th--biz">计量单位</th><td class="indicator-spec-td">' + esc(unit) + '</td></tr>' +
          '<tr><th class="indicator-spec-th indicator-spec-th--tech">时间周期</th><td class="indicator-spec-td">' + esc(freq) + '</td>' +
          '<th class="indicator-spec-th indicator-spec-th--biz">值类型</th><td class="indicator-spec-td">' + esc(row.value_type || '—') + '</td></tr>' +
          '<tr><th class="indicator-spec-th indicator-spec-th--biz indicator-spec-th-block">指标描述</th><td class="indicator-spec-td indicator-spec-td-block" colspan="3">' + esc(desc) + '</td></tr>' +
        '</table>' +
      '</div>'
    );
  }

  /* ---------- 处理任务：去重 + AI 生成 ---------- */
  function processImportTask() {
    if (!CURRENT_TASK) return;
    if (window.toast) toast('⏳ 去重 + AI 生成中（逐条生成，请稍候）…');
    api('/api/import-tasks/' + encodeURIComponent(CURRENT_TASK.task_id) + '/process', { method: 'POST', body: '{}' })
      .then(function (task) {
        CURRENT_TASK = task;
        if (window.toast) toast('✅ 处理完成：新增 ' + (task.dedup_result.new_count || 0) + '，重复 ' + (task.dedup_result.dup_count || 0) + '，疑似 ' + (task.dedup_result.suspect_count || 0), 'success');
        renderTaskCards(task);
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
      // 当前卡评审完后，自动抽下一张待评审卡（连续评审不卡壳）
      var filtered = filterRows(task.generated || []);
      var nextIdx = -1;
      for (var i = 0; i < filtered.length; i++) {
        var s = filtered[i]._status;
        if (s === 'pending' || s === 'rejected') { nextIdx = i; break; }
      }
      DRAWN_IDX = nextIdx;
      renderTaskCards(task);
      loadImportTasks();
    }).catch(function (e) {
      if (window.toast) toast('评审失败: ' + e.message);
    });
  }

  function closeImportTaskDetail() {
    var card = document.getElementById('importTaskDetailCard');
    if (card) card.style.display = 'none';
    CURRENT_TASK = null;
    DRAWN_IDX = -1;
  }

  /* ---------- 导出 ---------- */
  global.uploadImportTaskFile = uploadImportTaskFile;
  global.loadImportTasks = loadImportTasks;
  global.openImportTask = openImportTask;
  global.processImportTask = processImportTask;
  global.reviewImportRow = reviewImportRow;
  global.closeImportTaskDetail = closeImportTaskDetail;
  global.drawCard = drawCard;
  global.closeDraw = closeDraw;
  global.switchDraw = switchDraw;
  global.setFilter = setFilter;
  global.setDomain = setDomain;
})(window);
