/**
 * 批量导入（H31 P1）：CSV 上传 → 待办任务 → 去重 + AI 生成 → 逐卡人工评审 → 草稿。
 * 依赖 governance-api.js 的 resolveBase/fetchJson（全局）。
 */
(function (global) {
  var CURRENT_TASK = null;

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
    host.setAttribute('style', 'perspective:1800px;perspective-origin:50% 0%;padding:24px 16px 80px;');
    host.innerHTML = rows.map(function (row, i) {
      var st = row._status || 'pending';
      var stLabel = { pending: '待评审', skip: '已跳过(重复)', rejected: '已打回', draft: '已入草稿', error: '生成失败' }[st] || st;
      var stBadge = st === 'draft' ? 'badge-pass' : (st === 'rejected' || st === 'error' ? 'badge-danger' : (st === 'skip' ? 'badge-neutral' : 'badge-warn'));
      var dedupLabel = row._dedup === 'dup' ? '重复' : (row._dedup === 'suspect' ? '疑似重复' : '新增');
      var dedupBadge = row._dedup === 'dup' ? 'badge-danger' : (row._dedup === 'suspect' ? 'badge-warn' : 'badge-pass');

      // 透视层叠偏移（inline 强制生效；激进参数让重叠明显可见）
      var layerOffset = i * 40;           // 每张卡向上偏移 40px（够明显）
      var layerScale = Math.max(0.82, 1 - i * 0.06); // 缩小更明显
      var layerOpacity = Math.max(0.7, 1 - i * 0.12); // 透明度递减
      var layerMarginTop = (i === 0) ? 0 : -150;       // 后面卡往上叠 150px 真正重叠

      return (
        '<div class="import-card-wrap" ' +
          'style="--i:' + i + ';margin-top:' + layerMarginTop + 'px;' +
          'transform:translateY(-' + layerOffset + 'px) scale(' + layerScale.toFixed(3) + ');' +
          'opacity:' + layerOpacity.toFixed(2) + ';z-index:' + (100 - i) + ';" ' +
          'data-index="' + i + '">' +
          // 顶部状态条
          '<div class="import-card-status">' +
            '<span class="badge ' + dedupBadge + '">' + dedupLabel + '</span>' +
            '<span class="badge ' + stBadge + '">' + stLabel + '</span>' +
            (row._reject_reason ? '<span class="text-sm" style="color:var(--danger);">打回原因: ' + esc(row._reject_reason) + '</span>' : '') +
            '<span class="text-sm text-muted" style="margin-left:auto;">卡片 ' + (i + 1) + ' / ' + rows.length + '</span>' +
          '</div>' +
          // 指标卡片（复用指标库的 indicator-spec-card 完整渲染：全部字段值）
          '<div class="metric-spec-surface">' +
            buildImportSpecHtml(row) +
            (row._error ? '<div class="text-sm" style="color:var(--danger);padding:10px 16px;background:#fef2f2;">' + esc(row._error) + '</div>' : '') +
            // 评审按钮
            ((st === 'pending' || st === 'rejected') ?
              '<div class="import-card-actions">' +
                '<button class="btn" onclick="reviewImportRow(' + i + ',\'reject\')">✕ 打回</button>' +
                '<button class="btn btn-primary" onclick="reviewImportRow(' + i + ',\'approve\')">✓ 通过入草稿</button>' +
              '</div>' : '') +
          '</div>' +
        '</div>'
      );
    }).join('');
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
})(window);
