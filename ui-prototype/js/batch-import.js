/**
 * 批量导入（H31 P1）：CSV 上传 → 待办任务 → 去重 + AI 生成 → 逐卡人工评审 → 草稿。
 * 依赖 governance-api.js 的 resolveBase/fetchJson（全局）。
 */
(function (global) {
  var CURRENT_TASK = null;
  // 网格平铺分页：每页 9 张（3×3），50 张时约 6 页
  var CURRENT_PAGE = 0;
  var PAGE_SIZE = 9;

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
      CURRENT_PAGE = 0; // 打开新任务回到第一页
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
    host.classList.add('import-cards-stack');

    // 分页切片：所有卡统一尺寸平铺网格，每页 PAGE_SIZE 张
    var totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
    if (CURRENT_PAGE >= totalPages) CURRENT_PAGE = totalPages - 1;
    var start = CURRENT_PAGE * PAGE_SIZE;
    var pageRows = rows.slice(start, start + PAGE_SIZE);

    var cardsHtml = pageRows.map(function (row, pi) {
      var gi = start + pi; // 全局索引（评审/翻页后仍指向正确行）
      var st = row._status || 'pending';
      var stLabel = { pending: '待评审', skip: '已跳过(重复)', rejected: '已打回', draft: '已入草稿', error: '生成失败' }[st] || st;
      var stBadge = st === 'draft' ? 'badge-pass' : (st === 'rejected' || st === 'error' ? 'badge-danger' : (st === 'skip' ? 'badge-neutral' : 'badge-warn'));
      var dedupLabel = row._dedup === 'dup' ? '重复' : (row._dedup === 'suspect' ? '疑似重复' : '新增');
      var dedupBadge = row._dedup === 'dup' ? 'badge-danger' : (row._dedup === 'suspect' ? 'badge-warn' : 'badge-pass');

      return (
        '<div class="import-card-wrap">' +
          // 炉石卡（H32 魔兽卡包）
          '<div class="warcraft-card" ' +
            'style="--art-c1:' + themeFor(row.domain_code).c1 + ';' +
            '--art-c2:' + themeFor(row.domain_code).c2 + ';">' +
            // 顶部状态条（卡牌上方：去重 / 状态 / 打回原因 / 序号）
            '<div class="import-card-status">' +
              '<span class="badge ' + dedupBadge + '">' + dedupLabel + '</span>' +
              '<span class="badge ' + stBadge + '">' + stLabel + '</span>' +
              (row._reject_reason ? '<span class="text-sm" style="color:var(--danger);">打回原因: ' + esc(row._reject_reason) + '</span>' : '') +
              '<span class="text-sm text-muted" style="margin-left:auto;">' + (gi + 1) + ' / ' + rows.length + '</span>' +
            '</div>' +
            // 左上角黄色水晶数字（成本）
            '<div class="warcraft-cost">' + cardCost(row) + '</div>' +
            // 顶部插画区（按主题域配色 + emoji）
            '<div class="warcraft-art"><span class="warcraft-art-icon">' + themeFor(row.domain_code).icon + '</span></div>' +
            // 卡名条（米色椭圆渐变，紧贴插画下方）
            '<div class="warcraft-name">' + esc(row.metric_cn || '—') + '</div>' +
            // 内容区（米色背景，复用指标库完整字段渲染，内部滚动保持卡片等大）
            '<div class="warcraft-body">' + buildImportSpecHtml(row) + '</div>' +
            // 右下角蓝色水晶数字（耐久）
            '<div class="warcraft-stat">' + cardStat(row) + '</div>' +
            // 错误提示 + 评审按钮
            (row._error ? '<div class="text-sm" style="color:var(--danger);padding:10px 12px;background:#fef2f2;border-radius:0 0 12px 12px;">' + esc(row._error) + '</div>' : '') +
            ((st === 'pending' || st === 'rejected') ?
              '<div class="import-card-actions">' +
                '<button class="btn" onclick="reviewImportRow(' + gi + ',\'reject\')">✕ 打回</button>' +
                '<button class="btn btn-primary" onclick="reviewImportRow(' + gi + ',\'approve\')">✓ 通过入草稿</button>' +
              '</div>' : '') +
          '</div>' +
        '</div>'
      );
    }).join('');

    // 分页控件（50 张时才有意义；少于 PAGE_SIZE 不显示）
    var pagerHtml = totalPages > 1 ? buildPagerHtml(rows.length, totalPages) : '';
    host.innerHTML = cardsHtml + pagerHtml;
  }

  /* 分页控件：上一页 / 页码 / 下一页 */
  function buildPagerHtml(total, totalPages) {
    var nums = [];
    for (var p = 0; p < totalPages; p++) {
      if (totalPages > 9 && p > 2 && p < totalPages - 3 && p !== CURRENT_PAGE) {
        if (nums[nums.length - 1] !== '…') nums.push('…');
        continue;
      }
      nums.push(
        '<span class="page-num' + (p === CURRENT_PAGE ? ' active' : '') + '" onclick="goImportPage(' + p + ')">' + (p + 1) + '</span>'
      );
    }
    return (
      '<div class="import-pager">' +
        '<button class="btn" onclick="goImportPage(' + (CURRENT_PAGE - 1) + ')" ' + (CURRENT_PAGE === 0 ? 'disabled' : '') + '>‹ 上一页</button>' +
        '<span class="page-nums">' + nums.join('') + '</span>' +
        '<button class="btn" onclick="goImportPage(' + (CURRENT_PAGE + 1) + ')" ' + (CURRENT_PAGE >= totalPages - 1 ? 'disabled' : '') + '>下一页 ›</button>' +
        '<span class="page-info">第 ' + (CURRENT_PAGE + 1) + ' / ' + totalPages + ' 页 · 共 ' + total + ' 张卡</span>' +
      '</div>'
    );
  }

  function goImportPage(page) {
    if (!CURRENT_TASK) return;
    var rows = CURRENT_TASK.generated || [];
    var totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
    if (page < 0 || page >= totalPages) return;
    CURRENT_PAGE = page;
    renderTaskCards(CURRENT_TASK);
  }

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
      // 当前卡评审完后，自动跳到下一条待评审/待打回卡所在页（50 张连续评审不卡壳）
      var rows = task.generated || [];
      var nextIdx = -1;
      for (var i = 0; i < rows.length; i++) {
        var s = rows[i]._status;
        if (s === 'pending' || s === 'rejected') { nextIdx = i; break; }
      }
      if (nextIdx >= 0) CURRENT_PAGE = Math.floor(nextIdx / PAGE_SIZE);
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
  }

  /* ---------- 导出 ---------- */
  global.uploadImportTaskFile = uploadImportTaskFile;
  global.loadImportTasks = loadImportTasks;
  global.openImportTask = openImportTask;
  global.processImportTask = processImportTask;
  global.reviewImportRow = reviewImportRow;
  global.closeImportTaskDetail = closeImportTaskDetail;
  global.goImportPage = goImportPage;
})(window);
