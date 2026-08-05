/* ============================================================
 * IT2 前端：批量生成（接真接口）/ 词根维护 / 口径核查中心
 * 依赖：governance-api.js 的 DG.fetchJson、app.js 的 switchToPage
 * 说明：本文件在 app.js 之后加载，同名函数覆盖旧的静态演示实现
 * ============================================================ */
(function (global) {
  'use strict';

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function api(path, options) {
    var base = global.DG_API_BASE || '';
    options = options || {};
    options.headers = options.headers || {};
    options.headers['Content-Type'] = 'application/json';
    return fetch(base + path, options).then(function (r) {
      return r.json().then(function (body) {
        if (!r.ok) throw new Error((body && body.detail) || r.statusText);
        return body;
      });
    });
  }

  /* ==================== 批量生成（IT2-1） ==================== */

  function loadBatchGenOptions() {
    api('/api/metrics').then(function (metrics) {
      var atomics = (metrics || []).filter(function (m) { return m.metric_type === 'atomic'; });
      var tbody = document.getElementById('batchAtomicBody');
      if (!tbody) return;
      if (!atomics.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-sm text-muted" style="padding:12px;">暂无原子指标，请先在「指标管理」创建</td></tr>';
        return;
      }
      tbody.innerHTML = atomics.map(function (m) {
        return '<tr><td><input type="checkbox" class="batch-atomic-cb" value="' + esc(m.metric_id) + '"></td>' +
          '<td>' + esc(m.metric_cn) + '</td>' +
          '<td><span class="badge badge-info">atomic</span></td>' +
          '<td class="text-mono text-sm">' + esc(m.metric_en) + '</td></tr>';
      }).join('');
    }).catch(function (e) {
      var tbody = document.getElementById('batchAtomicBody');
      if (tbody) tbody.innerHTML = '<tr><td colspan="4" class="text-sm text-muted" style="padding:12px;">加载失败: ' + esc(e.message) + '</td></tr>';
    });

    api('/api/modifier-rules').then(function (mods) {
      var wrap = document.getElementById('batchModifierWrap');
      if (!wrap) return;
      if (!mods || !mods.length) { wrap.innerHTML = '<div class="text-sm text-muted">无修饰词配置</div>'; return; }
      var groups = {};
      mods.forEach(function (m) { (groups[m.modifier_type] || (groups[m.modifier_type] = [])).push(m); });
      var cn = { time: '时间修饰词', compare: '对比修饰词', business: '业务维度修饰词' };
      var html = '';
      Object.keys(groups).forEach(function (g) {
        html += '<div class="text-sm text-muted mb-2">' + (cn[g] || g) + '</div>' +
          '<div class="checkbox-grid mb-3">' +
          groups[g].map(function (m) {
            return '<div class="checkbox-item checked" data-mid="' + esc(m.modifier_id) + '" onclick="toggleBatchModifier(this)">' +
              '<div class="checkbox-box"></div> ' + esc(m.modifier_cn) + ' (' + esc(m.modifier_en) + ')</div>';
          }).join('') + '</div>';
      });
      wrap.innerHTML = html;
    }).catch(function () { /* 忽略 */ });
  }

  function toggleBatchModifier(el) { el.classList.toggle('checked'); }

  function batchSelection() {
    return {
      atomic_ids: Array.prototype.map.call(document.querySelectorAll('.batch-atomic-cb:checked'), function (cb) { return cb.value; }),
      modifier_ids: Array.prototype.map.call(document.querySelectorAll('#batchModifierWrap .checkbox-item.checked'), function (el) { return el.getAttribute('data-mid'); })
    };
  }

  function renderBatchPreview(list, tag) {
    var table = document.getElementById('batchPreviewTable');
    if (!table) return;
    var tbody = table.querySelector('tbody');
    if (!list || !list.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-sm text-muted" style="padding:12px;">无生成结果</td></tr>';
      return;
    }
    tbody.innerHTML = list.map(function (m) {
      return '<tr><td>' + esc(tag) + '</td>' +
        '<td class="text-mono text-sm">' + esc(m.metric_en) + '</td>' +
        '<td class="text-mono text-sm">' + esc(m.metric_en) + '</td>' +
        '<td class="text-sm">' + esc(m.metric_cn) + '</td>' +
        '<td class="text-sm text-muted">—</td>' +
        '<td><span class="badge badge-info">待评审</span></td></tr>';
    }).join('');
  }

  function refreshBatchPreview() {
    var sel = batchSelection();
    if (!sel.atomic_ids.length || !sel.modifier_ids.length) {
      var tbody = document.querySelector('#batchPreviewTable tbody');
      if (tbody) tbody.innerHTML = '<tr><td colspan="6" class="text-sm text-muted" style="padding:12px;">请先选择原子指标与修饰词</td></tr>';
      return;
    }
    api('/api/metrics/batch-generate', { method: 'POST', body: JSON.stringify({ atomic_ids: sel.atomic_ids, modifier_ids: sel.modifier_ids, dry_run: true }) })
      .then(function (res) { renderBatchPreview(res.generated, '预览'); })
      .catch(function (e) { alert('预览失败: ' + e.message); });
  }

  function batchGenerate(ev) {
    var btn = ev && ev.currentTarget ? ev.currentTarget : null;
    var sel = batchSelection();
    if (!sel.atomic_ids.length || !sel.modifier_ids.length) { alert('请先选择原子指标与修饰词'); return; }
    if (btn) { btn.disabled = true; btn.textContent = '⏳ 正在生成...'; }
    api('/api/metrics/batch-generate', { method: 'POST', body: JSON.stringify(sel) })
      .then(function (res) {
        renderBatchPreview(res.generated, '✅ 已生成');
        var msg = '生成 ' + res.generated.length + ' 个派生指标';
        if (res.existing.length) msg += '，跳过已存在 ' + res.existing.length + ' 个';
        if (res.invalid_atomics.length || res.invalid_modifiers.length) msg += '，无效 ' + (res.invalid_atomics.length + res.invalid_modifiers.length) + ' 个';
        alert(msg);
        if (global.DG && DG.refresh) DG.refresh();
      })
      .catch(function (e) { alert('生成失败: ' + e.message); })
      .finally(function () {
        if (btn) { btn.disabled = false; btn.textContent = '⚡ 一键生成'; }
      });
  }

  /* ==================== 词根维护（IT2-2） ==================== */

  function loadRoots() {
    api('/api/roots').then(function (rows) {
      var tbody = document.getElementById('roots-table-body');
      if (!tbody) return;
      if (!rows || !rows.length) {
        tbody.innerHTML = '<tr><td colspan="9" class="text-sm text-muted" style="padding:16px;">暂无词根</td></tr>';
        return;
      }
      tbody.innerHTML = rows.map(function (r) {
        return '<tr>' +
          '<td class="text-mono text-sm">' + esc(r.root_id) + '</td>' +
          '<td>' + esc(r.root_cn) + '</td>' +
          '<td class="text-mono">' + esc(r.root_en) + '</td>' +
          '<td class="text-mono">' + esc(r.root_abbr) + '</td>' +
          '<td><span class="badge badge-neutral">' + esc(r.root_type) + '</span></td>' +
          '<td><span class="badge badge-info">' + esc(r.source_model) + '</span></td>' +
          '<td>—</td>' +
          '<td><span class="badge ' + (r.review_status === 'approved' ? 'badge-pass' : 'badge-warn') + '">' + esc(r.review_status) + '</span></td>' +
          '<td><button class="btn btn-sm" onclick="openRootEdit(\'' + esc(r.root_id) + '\')">编辑</button></td>' +
          '</tr>';
      }).join('');
    }).catch(function (e) { /* 静默 */ });
  }

  function openRootCreateModal() {
    var m = document.getElementById('rootCreateModal');
    if (m) m.classList.add('show');
  }

  function saveRootCreate() {
    var payload = {
      root_cn: document.getElementById('rootFormCn').value.trim(),
      root_en: document.getElementById('rootFormEn').value.trim(),
      root_abbr: document.getElementById('rootFormAbbr').value.trim(),
      root_type: document.getElementById('rootFormType').value,
      domain_code: document.getElementById('rootFormDomain').value.trim(),
      description: document.getElementById('rootFormDesc').value.trim(),
      synonyms: document.getElementById('rootFormSyn').value.trim()
    };
    if (!payload.root_cn || !payload.root_en || !payload.domain_code) { alert('中文名 / 英文名 / 主题域 必填'); return; }
    api('/api/roots', { method: 'POST', body: JSON.stringify(payload) })
      .then(function () {
        alert('词根已创建');
        closeModal('rootCreateModal');
        ['rootFormCn', 'rootFormEn', 'rootFormAbbr', 'rootFormDomain', 'rootFormDesc', 'rootFormSyn'].forEach(function (id) {
          var el = document.getElementById(id); if (el) el.value = '';
        });
        loadRoots();
        if (global.DG && DG.refresh) DG.refresh();
      })
      .catch(function (e) { alert('创建失败: ' + e.message); });
  }

  function openRootEdit(id) {
    var rows = global.__DG_ROOTS__ || [];
    var r = null;
    for (var i = 0; i < rows.length; i++) { if (rows[i].root_id === id) { r = rows[i]; break; } }
    if (!r) return;
    document.getElementById('rootEditId').value = r.root_id;
    document.getElementById('rootEditCn').value = r.root_cn;
    document.getElementById('rootEditEn').value = r.root_en;
    document.getElementById('rootEditAbbr').value = r.root_abbr;
    document.getElementById('rootEditType').value = r.root_type || 'noun';
    document.getElementById('rootEditDesc').value = r.description || '';
    document.getElementById('rootEditSyn').value = r.synonyms || '';
    closeModal('rootCreateModal');
    var m = document.getElementById('rootEditModal');
    if (m) m.classList.add('show');
  }

  function saveRootEdit() {
    var id = document.getElementById('rootEditId').value.trim();
    if (!id) return;
    var payload = {
      root_cn: document.getElementById('rootEditCn').value.trim(),
      root_en: document.getElementById('rootEditEn').value.trim(),
      root_abbr: document.getElementById('rootEditAbbr').value.trim(),
      root_type: document.getElementById('rootEditType').value,
      description: document.getElementById('rootEditDesc').value.trim(),
      synonyms: document.getElementById('rootEditSyn').value.trim()
    };
    if (!payload.root_cn || !payload.root_en) { alert('中文名 / 英文名 必填'); return; }
    api('/api/roots/' + encodeURIComponent(id), { method: 'PUT', body: JSON.stringify(payload) })
      .then(function () {
        alert('已保存');
        closeModal('rootEditModal');
        loadRoots();
        if (global.DG && DG.refresh) DG.refresh();
      })
      .catch(function (e) { alert('保存失败: ' + e.message); });
  }

  /* ==================== 口径核查中心（IT2-5/IT2-6） ==================== */

  function statusBadge(s) {
    var map = { pending: 'badge-warn', rejected: 'badge-danger', approved: 'badge-pass', edited: 'badge-info' };
    return '<span class="badge ' + (map[s] || 'badge-neutral') + '">' + esc(s || '—') + '</span>';
  }

  function loadCaliberQueue() {
    var tbody = document.getElementById('caliberQueueBody');
    var count = document.getElementById('caliberQueueCount');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="7" class="text-sm text-muted" style="padding:16px;">加载中…</td></tr>';
    api('/api/caliber/pending').then(function (rows) {
      rows = rows || [];
      if (count) count.textContent = '共 ' + rows.length + ' 条';
      var badge = document.getElementById('nav-badge-caliber-check');
      if (badge) badge.textContent = rows.length || '—';
      if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-sm text-muted" style="padding:16px;">🎉 没有待核查的口径</td></tr>';
        return;
      }
      tbody.innerHTML = rows.map(function (r) {
        var c = r.caliber || {};
        return '<tr>' +
          '<td class="text-sm"><strong>' + esc(r.metric_cn) + '</strong><br><span class="text-mono" style="font-size:11px;">' + esc(r.metric_id) + '</span></td>' +
          '<td>' + statusBadge(r.caliber_status) + (r.caliber_reject_reason ? '<div class="text-xs" style="color:var(--danger)">' + esc(r.caliber_reject_reason) + '</div>' : '') + '</td>' +
          '<td class="text-sm">' + esc(c.caliber_business || '—') + '</td>' +
          '<td class="text-sm">' + esc(c.caliber_period || '—') + '</td>' +
          '<td class="text-sm">' + esc(c.caliber_boundary || '—') + '</td>' +
          '<td class="text-xs text-muted">' + esc(r.caliber_ai_by || '—') + '</td>' +
          '<td>' +
          '<button class="btn btn-sm btn-primary" onclick="caliberApprove(\'' + esc(r.metric_id) + '\')">批准</button> ' +
          '<button class="btn btn-sm" onclick="caliberReject(\'' + esc(r.metric_id) + '\')">打回</button>' +
          '</td></tr>';
      }).join('');
    }).catch(function (e) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-sm text-muted" style="padding:16px;">加载失败: ' + esc(e.message) + '</td></tr>';
    });
  }

  function caliberApprove(id) {
    if (!confirm('批准该指标的口径草稿？将触发重新评分。')) return;
    api('/api/metrics/' + encodeURIComponent(id) + '/caliber/approve', { method: 'POST', body: JSON.stringify({ checked_by: 'console' }) })
      .then(function () { alert('已批准'); loadCaliberQueue(); if (global.DG && DG.refresh) DG.refresh(); })
      .catch(function (e) { alert('失败: ' + e.message); });
  }

  function caliberReject(id) {
    var reason = prompt('打回原因（必填）：');
    if (reason === null) return;
    api('/api/metrics/' + encodeURIComponent(id) + '/caliber/reject', { method: 'POST', body: JSON.stringify({ reason: reason, checked_by: 'console' }) })
      .then(function () { alert('已打回'); loadCaliberQueue(); })
      .catch(function (e) { alert('失败: ' + e.message); });
  }

  function caliberBackfill() {
    if (!confirm('对未起草口径的存量指标批量起草（mock/live 取决于配置）？')) return;
    api('/api/caliber/backfill', { method: 'POST', body: JSON.stringify({}) })
      .then(function (res) { alert('补全完成：起草 ' + res.drafted + ' 个'); loadCaliberQueue(); })
      .catch(function (e) { alert('补全失败: ' + e.message); });
  }

  /* ==================== 新增指标 AI 辅助（问题 2 / 内联面板） ==================== */

  function showAiPanel() {
    var panel = document.getElementById('newMetricAiPanel');
    if (panel) panel.style.display = '';
  }

  function suggestMetricFields() {
    var cn = document.getElementById('newMetricCn');
    if (!cn || !cn.value.trim()) { alert('请先填写中文名称'); return; }
    showAiPanel();
    var status = document.getElementById('newMetricAiSource');
    var fieldsEl = document.getElementById('newMetricAiFields');
    var rootsEl = document.getElementById('newMetricAiRoots');
    if (fieldsEl) fieldsEl.innerHTML = '<span class="text-sm text-muted">🤔 AI 生成中，请稍候…</span>';
    if (rootsEl) rootsEl.innerHTML = '';
    if (status) status.textContent = '';
    var domain = document.getElementById('newMetricDomain');
    var val = function (id) {
      var el = document.getElementById(id);
      return el ? el.value.trim() : '';
    };
    api('/api/metrics/suggest', {
      method: 'POST',
      body: JSON.stringify({
        metric_cn: cn.value.trim(),
        domain_code: domain ? domain.value : 'sale',
        caliber_desc: val('newMetricDesc'),
        formula: val('newMetricFormulaLogic'),
        unit: val('newMetricUnit'),
        frequency: val('newMetricFrequency')
      })
    }).then(function (r) {
      global.__DG_AI_SUGGEST__ = r;
      var src = { similar_metric: '· 复用同名指标', rule_hint: '· 词根组合提示(mock)', llm: '· AI 生成', llm_multi: '· AI 多模型生成' }[r.source] || '';
      if (status) status.textContent = src;
      renderAiFields(r);
      renderAiRoots(r.suggested_roots || []);
    }).catch(function (e) {
      if (fieldsEl) fieldsEl.innerHTML = '<span style="color:var(--danger);">AI 生成失败: ' + esc(e.message) + '</span>';
    });
  }

  function renderAiFields(r) {
    var el = document.getElementById('newMetricAiFields');
    if (!el) return;
    var rows = [
      ['英文名称', r.metric_en, 'newMetricEn'],
      ['指标描述', r.caliber_desc, 'newMetricDesc'],
      ['公式中文说明', r.formula_cn, 'newMetricFormulaCn'],
      ['计算公式', r.formula, 'newMetricFormulaLogic'],
      ['单位', r.unit, 'newMetricUnit'],
      ['统计频率', r.frequency, 'newMetricFrequency'],
      ['来源表', r.data_sources, 'newMetricSourceTable'],
      ['技术口径', r.tech_caliber, 'newMetricTechCaliber']
    ].filter(function (x) { return x[1]; });
    if (!rows.length) {
      el.innerHTML = '<span class="text-sm text-muted">（无建议字段）</span>';
      return;
    }
    el.innerHTML = rows.map(function (x) {
      return '<div class="revision-item" style="cursor:default;">' +
        '<span class="revision-label" style="min-width:84px;">' + x[0] + '</span>' +
        '<code class="revision-value">' + esc(x[1]) + '</code></div>';
    }).join('') +
      '<div style="margin-top:8px;"><button class="btn btn-sm btn-primary" onclick="fillAiSuggestion()">⬇ 一键填入表单</button>' +
      '<span class="text-xs text-muted" style="margin-left:8px;">填入后可修改，确认后保存</span></div>';
    var fillBtn = document.getElementById('newMetricAiFillBtn');
    if (fillBtn) fillBtn.style.display = '';
  }

  function renderAiRoots(roots) {
    var el = document.getElementById('newMetricAiRoots');
    var note = document.getElementById('newMetricAiNote');
    if (!el) return;
    if (!roots || !roots.length) {
      el.innerHTML = '';
      if (note) note.style.display = 'none';
      return;
    }
    var rows = roots.map(function (rt, i) {
      return '<label class="revision-item">' +
        '<input type="checkbox" data-idx="' + i + '" checked> ' +
        '<span class="revision-label" style="min-width:64px;">' + esc(rt.root_cn) + '</span>' +
        ' → <code class="revision-value">' + esc(rt.root_en) + ' (' + esc(rt.root_abbr || rt.root_en) + ')</code>' +
        '<span class="badge badge-warn">缺失·将新建</span>' +
        (rt.description ? '<div class="text-xs text-muted" style="flex-basis:100%;padding-left:24px;">' + esc(rt.description) + '</div>' : '') +
        '</label>';
    }).join('');
    el.innerHTML = '<div class="text-sm" style="font-weight:600;margin:8px 0 4px;">将同步新建词根（勾选保存时自动创建）</div>' + rows;
    if (note) note.style.display = '';
  }

  function fillAiSuggestion() {
    var r = global.__DG_AI_SUGGEST__;
    if (!r) return;
    var map = {
      newMetricEn: r.metric_en,
      newMetricDesc: r.caliber_desc,
      newMetricFormulaLogic: r.formula,
      newMetricFormulaCn: r.formula_cn,
      newMetricUnit: r.unit,
      newMetricFrequency: r.frequency,
      newMetricSourceTable: r.data_sources,
      newMetricTechCaliber: r.tech_caliber
    };
    Object.keys(map).forEach(function (id) {
      var el = document.getElementById(id);
      if (el && map[id]) el.value = map[id];
    });
  }

  /* ==================== 域级治理看板（IT3-2） ==================== */

  function loadDomainDashboard() {
    var tbody = document.getElementById('domainDashBody');
    if (!tbody) return;
    api('/api/dashboard/domains').then(function (rows) {
      var count = document.getElementById('domainDashCount');
      if (count) count.textContent = '共 ' + rows.length + ' 个域';
      if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-sm text-muted" style="padding:16px;">暂无数据</td></tr>';
        return;
      }
      tbody.innerHTML = rows.map(function (r) {
        var g = r.grade_dist || {};
        var lineage = r.lineage_ok ? '<span class="badge badge-pass">✓</span>' : '<span class="badge badge-warn">缺</span>';
        var caliber = r.caliber_pending > 0
          ? '<span class="badge badge-danger">' + r.caliber_pending + '</span>'
          : '<span class="badge badge-pass">0</span>';
        var ver = r.latest_version
          ? r.latest_version + (r.latest_released_at ? '<div class="text-xs text-muted">' + r.latest_released_at + '</div>' : '')
          : '<span class="text-muted">—</span>';
        return '<tr style="cursor:pointer;" onclick="drillDomain(\'' + esc(r.domain) + '\')" title="点击查看该域指标">' +
          '<td><strong>' + esc(r.domain) + '</strong></td>' +
          '<td>' + r.roots_count + '</td>' +
          '<td>' + r.metrics_count + '</td>' +
          '<td>' + (r.score_avg == null ? '<span class="text-muted">—</span>' : '<span class="text-bold">' + r.score_avg + '</span>') + '</td>' +
          '<td class="text-sm">' + ['S', 'A', 'B', 'C', 'D'].map(function (k) { return k + ':' + (g[k] || 0); }).join(' ') + '</td>' +
          '<td>' + lineage + '</td>' +
          '<td>' + caliber + '</td>' +
          '<td class="text-sm">' + ver + '</td>' +
          '</tr>';
      }).join('');
    }).catch(function (e) {
      tbody.innerHTML = '<tr><td colspan="8" class="text-sm text-muted" style="padding:16px;">加载失败: ' + esc(e.message) + '</td></tr>';
    });
  }

  /* 治理总览下探：统计卡与域行点击跳转对应页面 */
  function drillDomain(domain) {
    if (global.MetricMgmt && MetricMgmt.setDomainFilter) MetricMgmt.setDomainFilter(domain);
    switchToPage('metric-mgmt');
  }

  function bindDashboardDrilldown() {
    var map = {
      'dash-stat-metrics': 'metrics',
      'dash-stat-roots': 'roots',
      'dash-stat-domains': 'scoring'
    };
    Object.keys(map).forEach(function (id) {
      var el = document.getElementById(id);
      if (el && !el.getAttribute('data-drill')) {
        el.setAttribute('data-drill', '1');
        el.style.cursor = 'pointer';
        el.title = '点击查看明细';
        el.addEventListener('click', function () { switchToPage(map[id]); });
      }
    });
  }

  /* ==================== 导入导出（问题 3/6） ==================== */

  function readFileAsText(file) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function () { resolve(reader.result); };
      reader.onerror = function () { reject(new Error('文件读取失败')); };
      reader.readAsText(file, 'utf-8');
    });
  }

  function pickFile(accept, onText) {
    var input = document.createElement('input');
    input.type = 'file';
    input.accept = accept;
    input.style.display = 'none';
    input.onchange = function () {
      var f = input.files && input.files[0];
      if (f) readFileAsText(f).then(onText).catch(function (e) { alert(e.message); });
    };
    document.body.appendChild(input);
    input.click();
  }

  function importMetricsFile() {
    pickFile('.csv', function (csv) {
      api('/api/metrics/import', { method: 'POST', body: JSON.stringify({ csv: csv }) })
        .then(function (r) { alert('导入完成：新增 ' + r.created + ' 个，跳过 ' + r.skipped + ' 个'); if (DG.refresh) DG.refresh(); })
        .catch(function (e) { alert('导入失败: ' + e.message); });
    });
  }

  function exportRootsCsv() {
    var base = global.DG_API_BASE || '';
    window.open(base + '/api/roots/export', '_blank');
  }

  function importRootsFile() {
    pickFile('.csv', function (csv) {
      api('/api/roots/import', { method: 'POST', body: JSON.stringify({ csv: csv }) })
        .then(function (r) { alert('导入完成：新增 ' + r.created + ' 个，跳过 ' + r.skipped + ' 个' + (r.errors.length ? '，错误 ' + r.errors.length + ' 条' : '')); loadRoots(); if (DG.refresh) DG.refresh(); })
        .catch(function (e) { alert('导入失败: ' + e.message); });
    });
  }

  /* ==================== 系统设置：模型管理（问题 13） ==================== */

  function loadSettingsModels() {
    var tbody = document.getElementById('settingsModelBody');
    if (!tbody) return;
    api('/api/models').then(function (rows) {
      var count = document.getElementById('settingsModelCount');
      if (count) count.textContent = '共 ' + rows.length + ' 个';
      tbody.innerHTML = rows.map(function (m) {
        return '<tr>' +
          '<td class="text-sm"><strong>' + esc(m.model_name) + '</strong><br><span class="text-mono" style="font-size:11px;">' + esc(m.provider) + (m.api_endpoint ? ' · ' + esc(m.api_endpoint) : '') + '</span></td>' +
          '<td class="text-sm">' + esc(m.use_case) + '</td>' +
          '<td>' + esc(m.priority) + '</td>' +
          '<td><span class="badge ' + (m.enabled === 'true' ? 'badge-pass' : 'badge-neutral') + '">' + (m.enabled === 'true' ? '启用' : '停用') + '</span></td>' +
          '<td><button class="btn btn-sm" onclick="editModel(\'' + esc(m.model_id) + '\')">编辑</button> ' +
          '<button class="btn btn-sm" onclick="toggleModel(\'' + esc(m.model_id) + '\',\'' + (m.enabled === 'true' ? 'false' : 'true') + '\')">' + (m.enabled === 'true' ? '停用' : '启用') + '</button> ' +
          '<button class="btn btn-sm" style="color:var(--danger)" onclick="deleteModel(\'' + esc(m.model_id) + '\')">删除</button></td></tr>';
      }).join('');
    }).catch(function (e) { tbody.innerHTML = '<tr><td colspan="5" class="text-sm text-muted">加载失败: ' + esc(e.message) + '</td></tr>'; });
  }

  function toggleModel(id, enabled) {
    api('/api/models/' + encodeURIComponent(id), { method: 'PUT', body: JSON.stringify({ enabled: enabled }) })
      .then(loadSettingsModels).catch(function (e) { alert('操作失败: ' + e.message); });
  }

  function deleteModel(id) {
    if (!confirm('删除模型 ' + id + '？')) return;
    api('/api/models/' + encodeURIComponent(id), { method: 'DELETE' })
      .then(loadSettingsModels).catch(function (e) { alert('删除失败: ' + e.message); });
  }

  function openModelModal() {
    var modal = document.getElementById('modelEditModal');
    if (!modal) return;
    ['modelEditId', 'modelEditName', 'modelEditProvider', 'modelEditPriority', 'modelEditEndpoint', 'modelEditKeyEnv', 'modelEditRemark'].forEach(function (id) {
      var el = document.getElementById(id); if (el) el.value = '';
    });
    var uc = document.getElementById('modelEditUseCase'); if (uc) uc.value = 'metric_review';
    var en = document.getElementById('modelEditEnabled'); if (en) en.value = 'true';
    modal.classList.add('show');
  }

  function editModel(id) {
    api('/api/models').then(function (rows) {
      var m = null;
      rows.forEach(function (r) { if (r.model_id === id) m = r; });
      if (!m) return;
      var map = { modelEditId: m.model_id, modelEditName: m.model_name, modelEditProvider: m.provider, modelEditPriority: m.priority, modelEditEndpoint: m.api_endpoint, modelEditKeyEnv: m.api_key_env, modelEditRemark: m.remark };
      Object.keys(map).forEach(function (k) { var el = document.getElementById(k); if (el) el.value = map[k] || ''; });
      var uc = document.getElementById('modelEditUseCase'); if (uc) uc.value = m.use_case || 'metric_review';
      var en = document.getElementById('modelEditEnabled'); if (en) en.value = m.enabled === 'true' ? 'true' : 'false';
      document.getElementById('modelEditModal').classList.add('show');
    }).catch(function (e) { alert('加载失败: ' + e.message); });
  }

  function saveModelEdit() {
    var id = document.getElementById('modelEditId').value.trim();
    var payload = {
      model_name: document.getElementById('modelEditName').value.trim(),
      provider: document.getElementById('modelEditProvider').value.trim(),
      use_case: document.getElementById('modelEditUseCase').value,
      priority: document.getElementById('modelEditPriority').value.trim(),
      enabled: document.getElementById('modelEditEnabled').value,
      api_endpoint: document.getElementById('modelEditEndpoint').value.trim(),
      api_key_env: document.getElementById('modelEditKeyEnv').value.trim(),
      remark: document.getElementById('modelEditRemark').value.trim()
    };
    if (!payload.model_name || !payload.provider) { alert('模型名/厂商必填'); return; }
    var path = id ? '/api/models/' + encodeURIComponent(id) : '/api/models';
    api(path, { method: id ? 'PUT' : 'POST', body: JSON.stringify(payload) })
      .then(function () {
        alert(id ? '模型已更新' : '模型已新增');
        closeModal('modelEditModal');
        loadSettingsModels();
      })
      .catch(function (e) { alert('保存失败: ' + e.message); });
  }

  /* ==================== 系统设置：修饰词管理（问题 11） ==================== */

  function loadSettingsModifiers() {
    var tbody = document.getElementById('settingsModifierBody');
    if (!tbody) return;
    api('/api/modifier-rules').then(function (rows) {
      var count = document.getElementById('settingsModifierCount');
      if (count) count.textContent = '共 ' + rows.length + ' 个';
      tbody.innerHTML = rows.map(function (m) {
        return '<tr>' +
          '<td class="text-sm"><strong>' + esc(m.modifier_cn) + '</strong><br><span class="text-mono" style="font-size:11px;">' + esc(m.modifier_id) + '</span></td>' +
          '<td class="text-mono text-sm">' + esc(m.modifier_en) + '</td>' +
          '<td><span class="badge badge-info">' + esc(m.modifier_type) + '</span></td>' +
          '<td><button class="btn btn-sm" onclick="editModifier(\'' + esc(m.modifier_id) + '\')">编辑</button> ' +
          '<button class="btn btn-sm" style="color:var(--danger)" onclick="deleteModifier(\'' + esc(m.modifier_id) + '\')">删除</button></td></tr>';
      }).join('');
    }).catch(function (e) { tbody.innerHTML = '<tr><td colspan="4" class="text-sm text-muted">加载失败: ' + esc(e.message) + '</td></tr>'; });
  }

  function deleteModifier(id) {
    if (!confirm('删除修饰词 ' + id + '？')) return;
    api('/api/modifier-rules/' + encodeURIComponent(id), { method: 'DELETE' })
      .then(loadSettingsModifiers).catch(function (e) { alert('删除失败: ' + e.message); });
  }

  function openModifierModal() {
    var modal = document.getElementById('modifierEditModal');
    if (!modal) return;
    ['modifierEditId', 'modifierEditCn', 'modifierEditEn', 'modifierEditAbbr', 'modifierEditScope', 'modifierEditDesc', 'modifierEditExample'].forEach(function (id) {
      var el = document.getElementById(id); if (el) el.value = '';
    });
    var t = document.getElementById('modifierEditType'); if (t) t.value = 'time';
    modal.classList.add('show');
  }

  function editModifier(id) {
    api('/api/modifier-rules').then(function (rows) {
      var m = null;
      rows.forEach(function (r) { if (r.modifier_id === id) m = r; });
      if (!m) return;
      var map = { modifierEditId: m.modifier_id, modifierEditCn: m.modifier_cn, modifierEditEn: m.modifier_en, modifierEditAbbr: m.modifier_abbr, modifierEditScope: m.time_scope, modifierEditDesc: m.description, modifierEditExample: m.example_metric };
      Object.keys(map).forEach(function (k) { var el = document.getElementById(k); if (el) el.value = map[k] || ''; });
      var t = document.getElementById('modifierEditType'); if (t) t.value = m.modifier_type || 'time';
      document.getElementById('modifierEditModal').classList.add('show');
    }).catch(function (e) { alert('加载失败: ' + e.message); });
  }

  function saveModifierEdit() {
    var id = document.getElementById('modifierEditId').value.trim();
    var payload = {
      modifier_cn: document.getElementById('modifierEditCn').value.trim(),
      modifier_en: document.getElementById('modifierEditEn').value.trim(),
      modifier_abbr: document.getElementById('modifierEditAbbr').value.trim(),
      modifier_type: document.getElementById('modifierEditType').value,
      time_scope: document.getElementById('modifierEditScope').value.trim(),
      description: document.getElementById('modifierEditDesc').value.trim(),
      example_metric: document.getElementById('modifierEditExample').value.trim()
    };
    if (!payload.modifier_cn || !payload.modifier_en) { alert('中文/英文必填'); return; }
    var path = id ? '/api/modifier-rules/' + encodeURIComponent(id) : '/api/modifier-rules';
    api(path, { method: id ? 'PUT' : 'POST', body: JSON.stringify(payload) })
      .then(function () {
        alert(id ? '修饰词已更新' : '修饰词已新增');
        closeModal('modifierEditModal');
        loadSettingsModifiers();
        if (DG.refresh) DG.refresh();
      })
      .catch(function (e) { alert('保存失败: ' + e.message); });
  }

  /* ==================== 系统设置：评审记录查看（问题 12） ==================== */

  function loadSettingsReviews() {
    var tbody = document.getElementById('settingsReviewBody');
    if (!tbody) return;
    api('/api/metric-reviews/latest').then(function (doc) {
      var count = document.getElementById('settingsReviewCount');
      var items = (doc && doc.items) || [];
      if (count) count.textContent = '最近评审 ' + items.length + ' 个指标';
      if (!items.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-sm text-muted" style="padding:16px;">暂无评审记录</td></tr>';
        return;
      }
      var html = '';
      items.forEach(function (item, idx) {
        (item.model_reviews || []).forEach(function (mr) {
          html += '<tr>' +
            '<td class="text-mono text-sm">' + esc(doc.review_id || ('review-' + idx)) + '</td>' +
            '<td class="text-sm">' + esc(item.metric_id || '') + '</td>' +
            '<td class="text-sm">' + esc(mr.model) + '</td>' +
            '<td>' + (mr.naming_score || '—') + '</td>' +
            '<td>' + (mr.caliber_score || '—') + '</td>' +
            '<td>' + ((item.final_decision && item.final_decision.decision_type) || '—') + '</td>' +
            '<td class="text-sm text-muted">—</td></tr>';
        });
      });
      tbody.innerHTML = html || '<tr><td colspan="7" class="text-sm text-muted">无模型明细</td></tr>';
    }).catch(function (e) { tbody.innerHTML = '<tr><td colspan="7" class="text-sm text-muted">加载失败: ' + esc(e.message) + '</td></tr>'; });
  }

  /* ==================== 表血缘明细（问题 10） ==================== */

  function loadTableLineage() {
    var tbody = document.getElementById('tableLineageBody');
    if (!tbody) return;
    api('/api/lineage?domain=sale').then(function (payload) {
      var rows = (payload && payload.lineages) || [];
      var count = document.getElementById('tableLineageCount');
      if (count) count.textContent = '共 ' + rows.length + ' 条血缘';
      if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-sm text-muted" style="padding:16px;">该域暂无血缘数据（可 POST /api/lineage/upload 上传）</td></tr>';
        return;
      }
      tbody.innerHTML = rows.map(function (r) {
        var sources = (r.source_tables || []).map(function (s) { return s.table_name; }).join(', ') || '—';
        var cm = (r.column_mappings || []).length;
        var mids = (r.metric_ids || []).join(', ') || '—';
        return '<tr style="cursor:pointer;" onclick="showTableLineageDetail(\'' + esc(r.lineage_id) + '\', this)">' +
          '<td class="text-mono text-sm"><strong>' + esc(r.target_table) + '</strong></td>' +
          '<td><span class="badge badge-info">' + esc(r.target_layer || '—') + '</span></td>' +
          '<td class="text-sm">' + esc(sources) + '</td>' +
          '<td>' + cm + '</td>' +
          '<td class="text-sm">' + esc(mids) + '</td>' +
          '<td><button class="btn btn-sm" onclick="event.stopPropagation();showTableLineageDetail(\'' + esc(r.lineage_id) + '\', this)">查看映射</button></td></tr>';
      }).join('');
    }).catch(function (e) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-sm text-muted" style="padding:16px;">加载失败: ' + esc(e.message) + '</td></tr>';
    });
  }

  function showTableLineageDetail(lineageId, rowEl) {
    api('/api/lineage?domain=sale').then(function (payload) {
      var item = null;
      ((payload && payload.lineages) || []).forEach(function (r) { if (r.lineage_id === lineageId) item = r; });
      var detail = document.getElementById('tableLineageDetail');
      if (!item || !detail) return;
      var maps = item.column_mappings || [];
      var html = '<div class="text-sm text-bold mb-2">' + esc(item.target_table) + ' 字段映射（' + maps.length + ' 条）</div>';
      if (!maps.length) {
        html += '<div class="text-sm text-muted">无字段映射</div>';
      } else {
        html += '<table><thead><tr><th>目标字段</th><th>来源表</th><th>来源字段</th><th>转换</th><th>关联指标</th></tr></thead><tbody>';
        maps.forEach(function (m) {
          html += '<tr><td class="text-mono text-sm">' + esc(m.target_column) + '</td>' +
            '<td class="text-mono text-sm">' + esc(m.source_table || '—') + '</td>' +
            '<td class="text-mono text-sm">' + esc(m.source_column || '—') + '</td>' +
            '<td class="text-sm">' + esc(m.transform || '—') + '</td>' +
            '<td class="text-mono text-sm">' + esc(m.metric_id || '—') + '</td></tr>';
        });
        html += '</tbody></table>';
      }
      detail.innerHTML = html;
      detail.style.display = 'block';
      if (rowEl) {
        var tbody = document.getElementById('tableLineageBody');
        Array.prototype.forEach.call(tbody.querySelectorAll('tr'), function (tr) { tr.style.background = ''; });
        if (rowEl.tagName === 'TR') rowEl.style.background = 'var(--primary-light)';
        else rowEl.closest('tr').style.background = 'var(--primary-light)';
      }
    }).catch(function () { /* 忽略 */ });
  }

  /* ==================== AI 提示词查看 ==================== */

  function viewPrompt() {
    var sel = document.getElementById('promptTypeSelect');
    var ptype = sel ? sel.value : 'metric_review';
    var pre = document.getElementById('promptPreview');
    var meta = document.getElementById('promptMeta');
    if (!pre) return;
    pre.textContent = '加载中…';
    api('/api/prompts/' + encodeURIComponent(ptype)).then(function (r) {
      if (meta) meta.textContent = r.name + ' ｜ 位置: ' + r.location;
      pre.textContent = r.template || '（无模板）';
    }).catch(function (e) { pre.textContent = '加载失败: ' + e.message; });
  }

  /* ==================== 词根 AI 生成（问题 7） ==================== */

  function openRootGenModal() {
    var m = document.getElementById('rootGenModal');
    if (m) m.classList.add('show');
    var wrap = document.getElementById('rootGenResultWrap');
    if (wrap) wrap.style.display = 'none';
    var commitBtn = document.getElementById('rootGenCommitBtn');
    if (commitBtn) commitBtn.style.display = 'none';
    var runBtn = document.getElementById('rootGenRunBtn');
    if (runBtn) { runBtn.style.display = ''; runBtn.textContent = '🤖 生成'; runBtn.disabled = false; }
    var res = document.getElementById('rootGenResult');
    if (res) res.innerHTML = '';
  }

  function runRootGen() {
    var domainEl = document.getElementById('rootGenDomain');
    var domain = domainEl ? domainEl.value.trim() : 'sale';
    if (!domain) domain = 'sale';
    var raw = (document.getElementById('rootGenTerms') || {}).value || '';
    raw = raw.trim();
    if (!raw) { alert('请输入中文词根（每行一个）'); return; }
    var terms = raw.split('\n')
      .map(function (line) {
        line = line.trim();
        if (!line) return null;
        var p = line.split('|');
        return { cn_term: p[0].trim(), context: ((p[1] || '').trim()) };
      })
      .filter(Boolean);
    if (!terms.length) { alert('请输入中文词根（每行一个）'); return; }
    var btn = document.getElementById('rootGenRunBtn');
    btn.disabled = true;
    btn.textContent = '生成中…';
    var st = document.getElementById('rootGenStatus');
    if (st) st.innerHTML = '<span class=\"text-muted\">🤔 多模型生成中，请稍候…</span>';
    api('/api/roots/generate', { method: 'POST', body: JSON.stringify({ domain: domain, terms: terms }) })
      .then(function (doc) {
        global.__DG_ROOT_GEN_REVIEW__ = doc;
        var items = doc.items || [];
        var rows = items.map(function (it) {
          var fd = it.final_decision || {};
          var ok = !!it.auto_approved;
          var en = (fd.root_en || '').trim() || '—';
          var abbr = (fd.root_abbr || '').trim();
          var desc = (fd.description || '').trim().slice(0, 60);
          var reused = it.reused_root_id;
          var badge = reused
            ? '<span class="badge badge-info">已复用 ' + esc(reused) + '</span>'
            : '<span class="badge badge-' + (ok ? 'pass' : 'warn') + '">' + (ok ? '自动通过' : '待确认') + '</span>';
          return (
            '<label class="revision-item">' +
            '<input type="checkbox" data-cn="' + esc(it.cn_term) + '"' + (reused ? '' : (ok ? ' checked' : '')) + (reused ? ' disabled' : '') + '> ' +
            '<span style="min-width:64px;font-weight:600;">' + esc(it.cn_term) + '</span>' +
            ' → <code class="revision-value">' + esc(en) + (abbr && abbr !== en ? ' (' + esc(abbr) + ')' : '') + '</code> ' +
            badge +
            (desc ? '<div class="text-xs text-muted" style="flex-basis:100%;padding-left:24px;">' + esc(desc) + '</div>' : '') +
            '</label>'
          );
        }).join('');
        document.getElementById('rootGenResult').innerHTML =
          rows || '<div class="text-sm text-muted">无生成结果</div>';
        document.getElementById('rootGenResultWrap').style.display = '';
        document.getElementById('rootGenCommitBtn').style.display = '';
        btn.disabled = false;
        btn.textContent = '🤖 重新生成';
      })
      .catch(function (e) {
        btn.disabled = false;
        btn.textContent = '🤖 生成';
        var st = document.getElementById('rootGenStatus');
        if (st) st.innerHTML = '<span style=\'color:var(--danger);\'>生成失败: ' + esc(e.message) + '</span>';
      });
  }

  function commitRootGen() {
    var doc = global.__DG_ROOT_GEN_REVIEW__;
    if (!doc) { alert('请先生成词根'); return; }
    var boxes = document.querySelectorAll('#rootGenResult .revision-item input[type="checkbox"]:checked');
    var cn = [];
    for (var i = 0; i < boxes.length; i++) cn.push(boxes[i].getAttribute('data-cn'));
    if (!cn.length) { alert('请至少勾选一个词根'); return; }
    if (!confirm('确认将 ' + cn.length + ' 个词根写入词根库？')) return;
    api('/api/roots/generate/commit', {
      method: 'POST',
      body: JSON.stringify({ review_id: doc.review_id, cn_terms: cn })
    })
      .then(function (res) {
        var st = document.getElementById('rootGenStatus');
        if (st) st.innerHTML = '<span style=\'color:var(--success,#16a34a);font-weight:600;\'>✅ 已入库 ' + res.created.length + ' 个词根' + (res.skipped.length ? '，跳过 ' + res.skipped.length + ' 个' : '') + '</span>';
        loadRoots();
        if (global.DG && global.DG.refresh) global.DG.refresh();
      })
      .catch(function (e) {
        var st = document.getElementById('rootGenStatus');
        if (st) st.innerHTML = '<span style=\'color:var(--danger);\'>入库失败: ' + esc(e.message) + '</span>';
      });
  }

  /* ==================== 初始化 & 页面切换联动 ==================== */

  var origSwitch = global.switchToPage;
  global.switchToPage = function (target) {
    if (origSwitch) origSwitch(target);
    if (target === 'batch-gen') loadBatchGenOptions();
    if (target === 'roots') loadRoots();
    if (target === 'caliber-check') loadCaliberQueue();
    if (target === 'dashboard') loadDomainDashboard();
    if (target === 'table-lineage') loadTableLineage();
    if (target === 'settings') {
      loadSettingsModels();
      loadSettingsModifiers();
      loadSettingsReviews();
    }
  };

  function init() {
    bindDashboardDrilldown();
    if (document.querySelector('.nav-item[data-page="caliber-check"]')) {
      loadCaliberQueue(); // nav 徽标常驻
    }
  }

  global.loadBatchGenOptions = loadBatchGenOptions;
  global.toggleBatchModifier = toggleBatchModifier;
  global.refreshBatchPreview = refreshBatchPreview;
  global.batchGenerate = batchGenerate;
  global.loadRoots = loadRoots;
  global.openRootCreateModal = openRootCreateModal;
  global.saveRootCreate = saveRootCreate;
  global.openRootEdit = openRootEdit;
  global.saveRootEdit = saveRootEdit;
  global.suggestMetricFields = suggestMetricFields;
  global.fillAiSuggestion = fillAiSuggestion;
  global.loadCaliberQueue = loadCaliberQueue;
  global.caliberApprove = caliberApprove;
  global.caliberReject = caliberReject;
  global.caliberBackfill = caliberBackfill;
  global.loadDomainDashboard = loadDomainDashboard;
  global.drillDomain = drillDomain;
  global.importMetricsFile = importMetricsFile;
  global.exportRootsCsv = exportRootsCsv;
  global.importRootsFile = importRootsFile;
  global.loadSettingsModels = loadSettingsModels;
  global.toggleModel = toggleModel;
  global.deleteModel = deleteModel;
  global.openModelModal = openModelModal;
  global.editModel = editModel;
  global.saveModelEdit = saveModelEdit;
  global.loadSettingsModifiers = loadSettingsModifiers;
  global.deleteModifier = deleteModifier;
  global.openModifierModal = openModifierModal;
  global.editModifier = editModifier;
  global.saveModifierEdit = saveModifierEdit;
  global.loadSettingsReviews = loadSettingsReviews;
  global.loadTableLineage = loadTableLineage;
  global.showTableLineageDetail = showTableLineageDetail;
  global.viewPrompt = viewPrompt;
  global.openRootGenModal = openRootGenModal;
  global.runRootGen = runRootGen;
  global.commitRootGen = commitRootGen;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})(window);
