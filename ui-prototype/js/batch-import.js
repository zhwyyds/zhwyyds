/**
 * 批量导入（H31 P1）：CSV 上传 → 待办任务 → 去重 + AI 生成 → 逐卡人工评审 → 草稿。
 * 依赖 governance-api.js 的 resolveBase/fetchJson（全局）。
 */
(function (global) {
  var CURRENT_TASK = null;
  // 卡包桌：主题域筛选 + 抽出的卡在过滤结果中的索引（-1 = 未抽出）
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

    var packHtml = buildPackHtml(filtered);
    var drawHtml = buildDrawHtml(filtered);
    host.innerHTML = '<div class="mc-pack-zone">' + packHtml + drawHtml + '</div>';
  }

  /* ── 筛选：仅按主题域过滤（状态由卡片稀有度颜色识别） ── */
  function filterRows(rows) {
    return (rows || []).filter(function (r) {
      if (CUR_DOMAIN !== 'all' && String(r.domain_code || '').toLowerCase() !== CUR_DOMAIN) return false;
      return true;
    });
  }

  /* ── 卡包：3 张层叠 + 顶层完整卡（正常大小，露边缘暗示"包"） ── */
  function buildPackHtml(filtered) {
    if (!filtered.length) {
      return '<div class="mc-pack-empty">该主题域暂无指标卡<br/><span style="font-size:11px;">点击上方色点切换主题域</span></div>';
    }
    var r0 = filtered[0];
    var theme = mcTheme(r0.domain_code);
    return (
      '<div class="mc-pack ' + theme + '" onclick="drawCard()" title="点击抽出">' +
        '<div class="deck-bg d3"></div>' +
        '<div class="deck-bg d2"></div>' +
        '<div class="mc-pack-top">' + buildMcCard(r0, 0, 1, r0._status || 'pending') + '</div>' +
      '</div>'
    );
  }

  /* ── 抽出：完整大卡轻微放大（scale 1.05）+ 顶部主题域色点切换 ── */
  function buildDrawHtml(filtered) {
    if (DRAWN_IDX < 0 || !filtered[DRAWN_IDX]) return '';
    var dr = filtered[DRAWN_IDX];
    return (
      '<div class="mc-draw open">' +
        '<div class="mc-draw-controls">' +
          '<div class="mc-draw-dots">' + buildDotsHtml() + '</div>' +
          '<button class="mc-draw-close" onclick="closeDraw()" title="收回（Esc）">✕</button>' +
        '</div>' +
        buildMcCard(dr, DRAWN_IDX, filtered.length, dr._status || 'pending') +
      '</div>'
    );
  }

  /* 主题域色点（鼠标点选切换——抽出的卡顶部切换主题域） */
  function buildDotsHtml() {
    if (!CURRENT_TASK) return '';
    var rows = CURRENT_TASK.generated || [];
    var doms = [];
    rows.forEach(function (r) {
      var d = String(r.domain_code || '').toLowerCase();
      if (d && doms.indexOf(d) < 0) doms.push(d);
    });
    var themeMap = { sale: 'trade', cont: 'lease', fin: 'finance', mall: 'ops', mkt: 'marketing', cust: 'service', prod: 'service' };
    var activeAll = CUR_DOMAIN === 'all' ? ' active' : '';
    var html = '<span class="dot' + activeAll + '" style="background:linear-gradient(135deg,#9ca3af,#4b5563)" onclick="setDomain(\'all\')" title="全部"></span>';
    doms.forEach(function (d) {
      var th = themeMap[d] || 'ops';
      var active = (CUR_DOMAIN === d) ? ' active' : '';
      var label = (DOMAIN_CN[d] || d) + '域';
      html += '<span class="dot ' + th + active + '" onclick="setDomain(\'' + d + '\')" title="' + label + '"></span>';
    });
    return html;
  }

  /* ── 抽卡 / 切换 / 收回 ── */
  function drawCard() {
    if (!CURRENT_TASK) return;
    var filtered = filterRows(CURRENT_TASK.generated || []);
    if (!filtered.length) return;
    var pack = document.querySelector('.mc-pack');
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

  function setDomain(d) {
    CUR_DOMAIN = d;
    DRAWN_IDX = -1;
    if (CURRENT_TASK) renderTaskCards(CURRENT_TASK);
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
  global.setDomain = setDomain;
})(window);
