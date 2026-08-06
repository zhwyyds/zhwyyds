/**
 * 指标管理 — 与指标库规范表字段对齐，经 API 读写 metrics/*.csv
 */
(function (global) {
  function esc(s) {
    if (s == null) return '';
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/"/g, '&quot;');
  }

  var filterState = { q: '', domain: '', status: '' };

  function getMetrics() {
    return global.__DG_METRICS__ || global.__DG_METRIC_ROWS__ || [];
  }

  function getMetricById(id) {
    var list = getMetrics();
    for (var i = 0; i < list.length; i++) {
      if (list[i].metric_id === id) return list[i];
    }
    return null;
  }

  function apiFetch(path, options) {
    var base = (global.DG && global.DG.API_BASE) || global.DG_API_BASE || '';
    options = options || {};
    options.headers = options.headers || {};
    if (options.body && !options.headers['Content-Type']) {
      options.headers['Content-Type'] = 'application/json';
    }
    return fetch(base + path, options).then(function (res) {
      if (!res.ok) throw new Error(path + ' ' + res.status);
      return res.json();
    });
  }

  function reloadFromServer() {
    if (global.DG && global.DG.loadAll) return global.DG.loadAll(false);
    return Promise.resolve();
  }

  function applyFilters(metrics) {
    metrics = metrics || [];
    var q = (filterState.q || '').toLowerCase();
    return metrics.filter(function (m) {
      if (filterState.domain && m.domain_code !== filterState.domain) return false;
      if (filterState.status === 'approved' && m.review_status !== 'approved') return false;
      if (filterState.status === 'pending' && (m.review_status === 'approved' || m.review_status === 'offline')) {
        return false;
      }
      if (!q) return true;
      return (
        (m.metric_cn || '').toLowerCase().indexOf(q) >= 0 ||
        (m.metric_id || '').toLowerCase().indexOf(q) >= 0 ||
        (m.metric_en || '').toLowerCase().indexOf(q) >= 0
      );
    });
  }

  function metricTypeBadge(t) {
    if (t === 'atomic') return '<span class="badge badge-info">原子</span>';
    if (t === 'derived') return '<span class="badge badge-neutral">派生</span>';
    if (t === 'composite') return '<span class="badge badge-neutral">复合</span>';
    return '<span class="badge badge-neutral">' + esc(t || '—') + '</span>';
  }

  var GRADE_CLASS = { S: 'badge-s', A: 'badge-a', B: 'badge-b', C: 'badge-c', D: 'badge-d' };

  function gradeBadgeHtml(m) {
    var summary = global.__DG_SCORE_SUMMARY__ || [];
    var grade = '—';
    for (var i = 0; i < summary.length; i++) {
      if (summary[i].metric_id === m.metric_id) {
        grade = summary[i].quality_grade || '—';
        break;
      }
    }
    if (grade === '—') return '<span class="badge badge-neutral">—</span>';
    var cls = GRADE_CLASS[grade] || 'badge-neutral';
    return '<span class="badge ' + cls + '">' + esc(grade) + '</span>';
  }

  function reviewCell(status) {
    if (status === 'approved') {
      return '<span class="badge badge-pass">&#9989; 已通过</span>';
    }
    if (status === 'offline') {
      return '<span class="badge badge-neutral">&#11015; 已下线</span>';
    }
    return '<span class="badge badge-warn">&#9203; 待确认</span>';
  }

  function publishCell(status) {
    if (status === 'approved') {
      return '<span class="mgmt-status-tag published">已发布</span>';
    }
    if (status === 'offline') {
      return '<span class="mgmt-status-tag offline">已下线</span>';
    }
    return '<span class="mgmt-status-tag draft">草稿</span>';
  }

  function actionButtons(m) {
    var id = esc(m.metric_id);
    var approved = m.review_status === 'approved';
    var html =
      '<div class="mgmt-action-bar">' +
      '<button type="button" class="btn btn-sm" onclick="viewMetric(\'' +
      id +
      '\')">&#128065; 查看</button>' +
      '<button type="button" class="btn btn-sm" onclick="MetricMgmt.openEdit(\'' +
      id +
      '\')">&#9999;&#65039; 编辑</button>';
    if (approved) {
      html +=
        '<button type="button" class="btn btn-sm" onclick="showOfflineModal(\'' +
        id +
        '\')" style="color:var(--danger)">&#11015; 下线</button>';
    } else {
      html +=
        '<button type="button" class="btn btn-sm" onclick="submitReview(\'' +
        id +
        '\')">&#129302; 评审</button>' +
        '<button type="button" class="btn btn-sm btn-primary" onclick="publishMetric(\'' +
        id +
        '\')">&#128640; 发布</button>';
    }
    html += '</div>';
    return html;
  }

  function renderStatusFlow(metrics) {
    var all = metrics || getMetrics();
    var offline = 0;
    var pending = 0;
    var published = 0;
    all.forEach(function (m) {
      if (m.review_status === 'approved') published += 1;
      else if (m.review_status === 'offline') offline += 1;
      else pending += 1;
    });
    var elPending = document.getElementById('mgmt-flow-pending');
    var elPublished = document.getElementById('mgmt-flow-published');
    var elOffline = document.getElementById('mgmt-flow-offline');
    var elReviewed = document.getElementById('mgmt-flow-reviewed');
    if (elPending) elPending.textContent = String(pending);
    if (elPublished) elPublished.textContent = String(published);
    if (elOffline) elOffline.textContent = String(offline);
    if (elReviewed) elReviewed.textContent = '—';
  }

  function renderTable(metrics) {
    var tbody = document.getElementById('batchTableBody');
    var countEl = document.getElementById('mgmt-total-count');
    if (!tbody) return;
    var all = metrics || getMetrics();
    renderStatusFlow(all);
    var rows = applyFilters(all);
    if (countEl) countEl.textContent = String(all.length);
    var pageLabel = document.getElementById('mgmtPageSizeLabel');
    if (pageLabel) pageLabel.textContent = String(rows.length);
    if (!rows.length) {
      tbody.innerHTML = inlineRowHtml() +
        '<tr><td colspan="12" class="text-sm text-muted" style="padding:20px;">无匹配指标</td></tr>';
      return;
    }
    tbody.innerHTML = inlineRowHtml() +
      rows
      .map(function (m) {
        return (
          '<tr class="batch-row" data-metric-id="' +
          esc(m.metric_id) +
          '">' +
          '<td><div class="custom-checkbox" onclick="toggleRowSelect(this)"></div></td>' +
          '<td class="text-mono text-sm">' +
          esc(m.metric_id) +
          '</td><td>' +
          esc(m.metric_cn) +
          '</td><td class="text-mono text-sm">' +
          esc(m.metric_en) +
          '</td><td class="text-mono text-sm">' +
          esc(m.metric_abbr || '—') +
          '</td><td><span class="badge badge-neutral">' +
          esc(m.domain_code) +
          '</span></td><td>' +
          metricTypeBadge(m.metric_type) +
          '</td><td>' +
          reviewCell(m.review_status) +
          '</td><td><span class="text-mono text-sm">' +
          esc(m.version || '—') +
          '</span></td><td>' +
          gradeBadgeHtml(m) +
          '</td><td>' +
          publishCell(m.review_status) +
          '</td><td>' +
          actionButtons(m) +
          '</td></tr>'
        );
      })
      .join('');
  }

  function inlineRowHtml() {
    // 内联新增行（与表格查看同构）：可见时保留在表格最前，不可见时为空串
    var row = document.getElementById('newMetricInlineRow');
    if (!row) return '';
    if (row.style.display === 'none') return '';
    return row.outerHTML;
  }

  function bindMgmtFilters() {
    var search = document.getElementById('mgmtSearchInput');
    if (search && !search.dataset.bound) {
      search.dataset.bound = '1';
      search.addEventListener('input', function () {
        filterState.q = search.value.trim();
        renderTable();
      });
    }
    var domainSel = document.getElementById('mgmtFilterDomain');
    if (domainSel && !domainSel.dataset.bound) {
      domainSel.dataset.bound = '1';
      domainSel.addEventListener('change', function () {
        filterState.domain = domainSel.value;
        renderTable();
      });
    }
    var statusSel = document.getElementById('mgmtFilterStatus');
    if (statusSel && !statusSel.dataset.bound) {
      statusSel.dataset.bound = '1';
      statusSel.addEventListener('change', function () {
        filterState.status = statusSel.value;
        renderTable();
      });
    }
  }

  function field(id) {
    return document.getElementById(id);
  }

  function setFormValue(id, val) {
    var el = field(id);
    if (!el) return;
    el.value = val == null ? '' : String(val);
  }

  function getFormValue(id) {
    var el = field(id);
    return el ? el.value.trim() : '';
  }

  function fillEditForm(m) {
    if (!m) return;
    setFormValue('metricEditId', m.metric_id);
    setFormValue('metricEditCn', m.metric_cn);
    setFormValue('metricEditEn', m.metric_en);
    setFormValue('metricEditAbbr', m.metric_abbr);
    setFormValue('metricEditCatL1', m.category_l1);
    setFormValue('metricEditCatL2', m.category_l2);
    setFormValue('metricEditValueType', m.value_type);
    setFormValue('metricEditDimensions', m.dimensions);
    setFormValue('metricEditScenario', m.scenario);
    setFormValue('metricEditReports', m.reports);
    setFormValue('metricEditDesc', m.caliber_desc);
    setFormValue('metricEditFormulaCn', m.formula_cn);
    setFormValue('metricEditFormulaLogic', m.formula);
    setFormValue('metricEditAnalysis', m.analysis_methods);
    setFormValue('metricEditAlert', m.alert_rules);
    setFormValue('metricEditUnit', m.unit);
    setFormValue('metricEditFrequency', m.frequency);
    setFormValue('metricEditPrecision', m.precision);
    setFormValue('metricEditDataSources', m.data_sources);
    setFormValue('metricEditTechCaliber', m.tech_caliber);
    setFormValue('metricEditSourceTable', m.source_table);
    setFormValue('metricEditOwner', m.owner);
    setFormValue('metricEditVersion', m.version);
    setFormValue('metricEditVersionHistory', m.version_history);
    setFormValue('metricEditDomain', m.domain_code);
    setFormValue('metricEditType', m.metric_type || 'atomic');
  }

  function readEditForm(base) {
    base = base || {};
    return Object.assign({}, base, {
      metric_id: getFormValue('metricEditId'),
      metric_cn: getFormValue('metricEditCn'),
      metric_en: getFormValue('metricEditEn'),
      metric_abbr: getFormValue('metricEditAbbr'),
      domain_code: getFormValue('metricEditDomain'),
      metric_type: getFormValue('metricEditType'),
      category_l1: getFormValue('metricEditCatL1'),
      category_l2: getFormValue('metricEditCatL2'),
      value_type: getFormValue('metricEditValueType'),
      dimensions: getFormValue('metricEditDimensions'),
      scenario: getFormValue('metricEditScenario'),
      reports: getFormValue('metricEditReports'),
      caliber_desc: getFormValue('metricEditDesc'),
      formula_cn: getFormValue('metricEditFormulaCn'),
      formula: getFormValue('metricEditFormulaLogic'),
      analysis_methods: getFormValue('metricEditAnalysis'),
      alert_rules: getFormValue('metricEditAlert'),
      unit: getFormValue('metricEditUnit'),
      frequency: getFormValue('metricEditFrequency'),
      precision: getFormValue('metricEditPrecision'),
      data_sources: getFormValue('metricEditDataSources'),
      tech_caliber: getFormValue('metricEditTechCaliber'),
      source_table: getFormValue('metricEditSourceTable'),
      owner: getFormValue('metricEditOwner'),
      version: getFormValue('metricEditVersion'),
      version_history: getFormValue('metricEditVersionHistory')
    });
  }

  function openEdit(id) {
    var m = getMetricById(id);
    if (!m) {
      alert('未找到指标 ' + id);
      return;
    }
    fillEditForm(m);
    var modal = document.getElementById('metricEditModal');
    if (modal) modal.classList.add('show');
  }

  function saveEdit() {
    var id = getFormValue('metricEditId');
    if (!id) return;
    var base = getMetricById(id) || { metric_id: id, review_status: 'pending' };
    var row = readEditForm(base);
    apiFetch('/api/metrics/' + encodeURIComponent(id), {
      method: 'PUT',
      body: JSON.stringify(row)
    })
      .then(function () {
        closeModal('metricEditModal');
        return reloadFromServer();
      })
      .catch(function (e) {
        alert('保存失败: ' + e.message);
      });
  }

  function openNew() {
    var modal = document.getElementById('newMetricModal');
    if (!modal) return;
    modal.querySelectorAll('input, textarea, select').forEach(function (el) {
      if (el.id === 'newMetricDomain') el.value = 'sale';
      else if (el.id === 'newMetricType') el.value = 'atomic';
      else el.value = '';
    });
    // 重置 AI 状态与折叠区
    global.__DG_AI_SUGGEST__ = null;
    var status = document.getElementById('newMetricAiStatus');
    if (status) { status.style.display = 'none'; status.textContent = ''; }
    var rootsRow = document.getElementById('newMetricAiRootsRow');
    if (rootsRow) rootsRow.style.display = 'none';
    var moreBody = document.getElementById('newMetricMoreBody');
    var moreArrow = document.getElementById('newMetricMoreArrow');
    if (moreBody) moreBody.style.display = 'none';
    if (moreArrow) moreArrow.innerHTML = '&#9654;';
    document.querySelectorAll('#newMetricModal .ai-diff-tip').forEach(function (t) { t.remove(); });
    modal.classList.add('show');
  }

  function saveNew() {
    var cn = getFormValue('newMetricCn');
    if (!cn) {
      alert('请输入中文名称');
      return;
    }
    var dom = getFormValue('newMetricDomain') || 'sale';
    var domUp = dom.toUpperCase();
    var newId = 'M_' + domUp + '_N' + String(Math.floor(Math.random() * 900 + 100));
    var row = {
      metric_id: newId,
      metric_cn: cn,
      metric_en: getFormValue('newMetricEn') || 'pending_naming',
      metric_abbr: getFormValue('newMetricAbbr'),
      domain_code: dom,
      metric_type: getFormValue('newMetricType') || 'atomic',
      caliber_desc: getFormValue('newMetricDesc'),
      formula_cn: getFormValue('newMetricFormulaCn'),
      formula: getFormValue('newMetricFormulaLogic'),
      tech_caliber: getFormValue('newMetricTechCaliber'),
      source_table: getFormValue('newMetricSourceTable'),
      owner: getFormValue('newMetricOwner'),
      version: getFormValue('newMetricVersion') || '0.1.0',
      version_history:
        getFormValue('newMetricVersionHistory') ||
        '0.1.0|' + new Date().toISOString().slice(0, 10) + '|—|新建草稿',
      review_status: 'pending',
      category_l1: getFormValue('newMetricCatL1'),
      category_l2: getFormValue('newMetricCatL2'),
      value_type: getFormValue('newMetricValueType'),
      dimensions: getFormValue('newMetricDimensions'),
      scenario: getFormValue('newMetricScenario'),
      reports: getFormValue('newMetricReports'),
      analysis_methods: getFormValue('newMetricAnalysis'),
      alert_rules: getFormValue('newMetricAlert'),
      precision: getFormValue('newMetricPrecision'),
      data_sources: getFormValue('newMetricDataSources'),
      unit: getFormValue('newMetricUnit'),
      frequency: getFormValue('newMetricFrequency')
    };

    // 同步补词根（G5）：勾选的「建议新建词根」先创建，再关联到指标 root_ids
    var suggest = global.__DG_AI_SUGGEST__;
    var chosenRoots = [];
    if (suggest && suggest.suggested_roots && suggest.suggested_roots.length) {
      var boxes = document.querySelectorAll('#newMetricAiRoots input[type="checkbox"]:checked');
      for (var i = 0; i < boxes.length; i++) {
        var rt = suggest.suggested_roots[parseInt(boxes[i].getAttribute('data-idx'), 10)];
        if (rt) chosenRoots.push(rt);
      }
    }
    if (chosenRoots.length) {
      var chain = Promise.resolve();
      var rootIds = [];
      var firstErr = null;
      chosenRoots.forEach(function (rt) {
        chain = chain
          .then(function () {
            return apiFetch('/api/roots', {
              method: 'POST',
              body: JSON.stringify({
                root_cn: rt.root_cn,
                root_en: rt.root_en,
                root_abbr: rt.root_abbr || rt.root_en,
                root_type: rt.root_type || 'noun',
                domain_code: dom,
                description: rt.description || '',
                synonyms: ''
              })
            });
          })
          .then(function (created) {
            rootIds.push(created.root_id || created.rootId);
          })
          .catch(function (e) { firstErr = e; });
      });
      chain.then(function () {
        if (firstErr) { alert('部分词根创建失败: ' + firstErr.message + '（指标未保存）'); return; }
        if (rootIds.length) row.root_ids = rootIds.join(';');
        createMetricRow(row);
      });
    } else {
      createMetricRow(row);
    }
  }

  function createMetricRow(row) {
    apiFetch('/api/metrics', { method: 'POST', body: JSON.stringify(row) })
      .then(function () {
        closeModal('newMetricModal');
        global.__DG_AI_SUGGEST__ = null;
        var rootsRow = document.getElementById('newMetricAiRootsRow');
        if (rootsRow) rootsRow.style.display = 'none';
        var rootsEl = document.getElementById('newMetricAiRoots');
        if (rootsEl) rootsEl.innerHTML = '';
        return reloadFromServer();
      })
      .catch(function (e) {
        alert('创建失败: ' + e.message);
      });
  }

  function publish(id) {
    apiFetch('/api/metrics/' + encodeURIComponent(id), {
      method: 'PUT',
      body: JSON.stringify({ review_status: 'approved' })
    })
      .then(reloadFromServer)
      .catch(function (e) {
        alert('发布失败: ' + e.message);
      });
  }

  /* ==================== 批量新增指标（P4） ==================== */

  function toggleBatchMode() {
    var wrap = document.getElementById('newMetricBatchWrap');
    var single = document.getElementById('newMetricSingleWrap');
    var btn = document.getElementById('newMetricBatchToggle');
    var title = document.getElementById('newMetricModalTitle');
    if (!wrap || !single) return;
    var batch = wrap.style.display !== 'none';
    wrap.style.display = batch ? 'none' : '';
    single.style.display = batch ? '' : 'none';
    if (btn) btn.textContent = batch ? '📋 批量模式' : '📝 单个模式';
    if (title) title.innerHTML = batch ? '&#10133; 新增指标' : '&#128203; 批量新增指标';
  }

  function batchSuggestMetrics() {
    var raw = document.getElementById('batchMetricInput') ? document.getElementById('batchMetricInput').value.trim() : '';
    if (!raw) { alert('请输入指标（每行一个）'); return; }
    var domain = document.getElementById('batchMetricDomain') ? document.getElementById('batchMetricDomain').value : 'sale';
    var terms = raw.split('\n').map(function (l) { return l.trim(); }).filter(Boolean).map(function (l) {
      var p = l.split('|');
      return { metric_cn: (p[0] || '').trim(), caliber_desc: ((p[1] || '').trim()), unit: ((p[2] || '').trim()), frequency: ((p[3] || '').trim()) };
    }).filter(function (t) { return t.metric_cn; });
    if (!terms.length) { alert('请至少输入一个指标名称'); return; }
    var status = document.getElementById('batchStatus');
    var preview = document.getElementById('batchMetricPreview');
    var createBtn = document.getElementById('batchCreateBtn');
    if (status) status.textContent = '🤔 正在生成 0/' + terms.length + '…';
    if (preview) preview.innerHTML = '';
    if (createBtn) createBtn.style.display = 'none';
    var results = [];
    var chain = Promise.resolve();
    terms.forEach(function (t) {
      chain = chain
        .then(function () {
          return apiFetch('/api/metrics/suggest', {
            method: 'POST',
            body: JSON.stringify({ metric_cn: t.metric_cn, domain_code: domain, caliber_desc: t.caliber_desc, unit: t.unit, frequency: t.frequency })
          });
        })
        .then(function (r) {
          results.push(r);
          if (status) status.textContent = '🤔 正在生成 ' + results.length + '/' + terms.length + '…';
        })
        .catch(function (e) {
          results.push({ metric_cn: t.metric_cn, metric_en: '', error: e.message });
          if (status) status.textContent = '⚠️ 部分生成失败 ' + results.length + '/' + terms.length;
        });
    });
    chain.then(function () {
      global.__DG_BATCH_SUGGEST__ = results;
      renderBatchPreview(results);
      if (status) status.textContent = '✅ 生成完成，勾选后点击「批量创建」';
      if (createBtn) createBtn.style.display = '';
    });
  }

  function renderBatchPreview(items) {
    var el = document.getElementById('batchMetricPreview');
    if (!el) return;
    el.innerHTML = items.map(function (it, i) {
      var ok = !!it.metric_en;
      var err = it.error ? '<span style="color:var(--danger);margin-left:6px;">(' + esc(it.error) + ')</span>' : '';
      var meta = (it.unit || it.frequency) ? ' <span class="text-xs text-muted">' + esc([it.unit, it.frequency].filter(Boolean).join(' / ')) + '</span>' : '';
      var desc = it.caliber_desc ? '<div class="text-xs text-muted" style="flex-basis:100%;padding-left:24px;">' + esc(it.caliber_desc.slice(0, 64)) + '</div>' : '';
      return '<label class="revision-item">' +
        '<input type="checkbox" data-idx="' + i + '"' + (ok ? ' checked' : ' disabled') + '> ' +
        '<span class="revision-label" style="min-width:110px;">' + esc(it.metric_cn) + '</span>' +
        ' → <code class="revision-value">' + esc(it.metric_en || '生成失败') + '</code>' + meta + err + desc +
        '</label>';
    }).join('') || '<div class="text-sm text-muted">无结果</div>';
  }

  function batchCreateMetrics() {
    var items = global.__DG_BATCH_SUGGEST__ || [];
    var boxes = document.querySelectorAll('#batchMetricPreview input[type="checkbox"]:checked');
    var chosen = [];
    for (var i = 0; i < boxes.length; i++) {
      var it = items[parseInt(boxes[i].getAttribute('data-idx'), 10)];
      if (it && it.metric_en) chosen.push(it);
    }
    if (!chosen.length) { alert('请勾选要创建的指标'); return; }
    if (!confirm('确认批量创建 ' + chosen.length + ' 个指标？')) return;
    var status = document.getElementById('batchStatus');
    var created = 0;
    var failed = [];
    var chain = Promise.resolve();
    chosen.forEach(function (it) {
      chain = chain
        .then(function () { return apiFetch('/api/metrics', { method: 'POST', body: JSON.stringify(buildMetricRow(it)) }); })
        .then(function () { created++; if (status) status.textContent = '创建中 ' + created + '/' + chosen.length + '…'; })
        .catch(function (e) { failed.push(it.metric_cn + ': ' + e.message); });
    });
    chain.then(function () {
      if (status) {
        status.textContent = failed.length
          ? '✅ 创建 ' + created + ' 个，失败 ' + failed.length + ' 个：' + failed.join('；')
          : '✅ 已创建 ' + created + ' 个指标';
      }
      if (global.DG && global.DG.loadAll) global.DG.loadAll(false);
      reloadFromServer();
      if (created && !failed.length) setTimeout(function () { closeModal('newMetricModal'); }, 900);
    });
  }

  function buildMetricRow(it) {
    var dom = (document.getElementById('batchMetricDomain') || {}).value || 'sale';
    var domUp = dom.toUpperCase();
    var newId = 'M_' + domUp + '_B' + String(Math.floor(Math.random() * 900 + 100));
    return {
      metric_id: newId,
      metric_cn: it.metric_cn,
      metric_en: it.metric_en || 'pending_naming',
      metric_abbr: it.metric_abbr || '',
      domain_code: dom,
      metric_type: 'atomic',
      caliber_desc: it.caliber_desc || '',
      formula_cn: it.formula_cn || '',
      formula: it.formula || '',
      tech_caliber: it.tech_caliber || '',
      source_table: it.source_table || '',
      owner: it.owner || '',
      version: '0.1.0',
      version_history: '0.1.0|' + new Date().toISOString().slice(0, 10) + '|—|批量新建',
      review_status: 'pending',
      category_l1: it.category_l1 || '',
      category_l2: it.category_l2 || '',
      value_type: it.value_type || '',
      dimensions: it.dimensions || '',
      scenario: it.scenario || '',
      reports: it.reports || '',
      analysis_methods: it.analysis_methods || '',
      alert_rules: it.alert_rules || '',
      precision: it.precision || '',
      data_sources: it.data_sources || '',
      unit: it.unit || '',
      frequency: it.frequency || '月'
    };
  }

  /* ==================== 内联新增指标（与表格查看窗口同构 + AI） ==================== */

  function showNewMetricInline() {
    var row = document.getElementById('newMetricInlineRow');
    if (!row) return;
    ['inlineNewCn', 'inlineNewEn', 'inlineNewAbbr'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.value = '';
    });
    var dom = document.getElementById('inlineNewDomain');
    if (dom) dom.value = 'sale';
    var type = document.getElementById('inlineNewType');
    if (type) type.value = 'atomic';
    var idEl = document.getElementById('inlineNewId');
    if (idEl) idEl.textContent = 'M_SALE_N' + String(Math.floor(Math.random() * 900 + 100));
    global.__DG_INLINE_SUGGEST__ = null;
    row.style.display = '';
    var cn = document.getElementById('inlineNewCn');
    if (cn) cn.focus();
    if (row.scrollIntoView) row.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }

  function cancelInlineNew() {
    var row = document.getElementById('newMetricInlineRow');
    if (row) row.style.display = 'none';
    global.__DG_INLINE_SUGGEST__ = null;
  }

  function inlineSuggestMetric() {
    var cn = document.getElementById('inlineNewCn');
    if (!cn || !cn.value.trim()) { alert('请先填写中文名'); return; }
    var domain = document.getElementById('inlineNewDomain') ? document.getElementById('inlineNewDomain').value : 'sale';
    apiFetch('/api/metrics/suggest', {
      method: 'POST',
      body: JSON.stringify({ metric_cn: cn.value.trim(), domain_code: domain })
    })
      .then(function (r) {
        global.__DG_INLINE_SUGGEST__ = r;
        var enEl = document.getElementById('inlineNewEn');
        if (enEl && r.metric_en) enEl.value = r.metric_en;
        var abEl = document.getElementById('inlineNewAbbr');
        if (abEl && r.metric_abbr) abEl.value = r.metric_abbr;
        alert('🤖 AI 已生成：' + (r.metric_en || '英文名待手动填写') + '\n（口径/公式/负责人/分类已备好，保存时一并写入）');
      })
      .catch(function (e) { alert('AI 生成失败: ' + e.message); });
  }

  function saveInlineNew() {
    var cn = document.getElementById('inlineNewCn');
    if (!cn || !cn.value.trim()) { alert('请填写中文名'); return; }
    var dom = document.getElementById('inlineNewDomain') ? document.getElementById('inlineNewDomain').value : 'sale';
    var domUp = dom.toUpperCase();
    var it = global.__DG_INLINE_SUGGEST__ || {};
    var val = function (id) { var el = document.getElementById(id); return el ? el.value.trim() : ''; };
    var row = {
      metric_id: 'M_' + domUp + '_N' + String(Math.floor(Math.random() * 900 + 100)),
      metric_cn: cn.value.trim(),
      metric_en: val('inlineNewEn') || it.metric_en || 'pending_naming',
      metric_abbr: val('inlineNewAbbr') || it.metric_abbr || '',
      domain_code: dom,
      metric_type: val('inlineNewType') || 'atomic',
      caliber_desc: it.caliber_desc || '',
      formula_cn: it.formula_cn || '',
      formula: it.formula || '',
      tech_caliber: it.tech_caliber || '',
      source_table: it.source_table || '',
      owner: it.owner || '',
      version: '0.1.0',
      version_history: '0.1.0|' + new Date().toISOString().slice(0, 10) + '|—|新建草稿',
      review_status: 'pending',
      category_l1: it.category_l1 || '',
      category_l2: it.category_l2 || '',
      value_type: it.value_type || '',
      dimensions: it.dimensions || '',
      scenario: it.scenario || '',
      reports: it.reports || '',
      analysis_methods: it.analysis_methods || '',
      alert_rules: it.alert_rules || '',
      precision: it.precision || '',
      data_sources: it.data_sources || '',
      unit: it.unit || '',
      frequency: it.frequency || '月'
    };
    apiFetch('/api/metrics', { method: 'POST', body: JSON.stringify(row) })
      .then(function () {
        cancelInlineNew();
        return reloadFromServer();
      })
      .catch(function (e) { alert('创建失败: ' + e.message); });
  }

  /* ==================== 批量新增弹窗入口 ==================== */

  function showBatchMetricModal() {
    var modal = document.getElementById('newMetricModal');
    if (!modal) return;
    var wrap = document.getElementById('newMetricBatchWrap');
    var single = document.getElementById('newMetricSingleWrap');
    var title = document.getElementById('newMetricModalTitle');
    var btn = document.getElementById('newMetricBatchToggle');
    if (wrap) wrap.style.display = '';
    if (single) single.style.display = 'none';
    if (title) title.innerHTML = '&#128203; 批量新增指标';
    if (btn) btn.textContent = '📝 单个模式';
    modal.classList.add('show');
  }

  function offline(id, payload) {
    id = (id || '').trim();
    if (!id) return Promise.reject(new Error('缺少指标 ID'));
    payload = payload || { review_status: 'offline' };
    return apiFetch('/api/metrics/' + encodeURIComponent(id), {
      method: 'PUT',
      body: JSON.stringify(payload)
    }).then(reloadFromServer);
  }

  global.MetricMgmt = {
    renderTable: renderTable,
    bindFilters: bindMgmtFilters,
    openEdit: openEdit,
    saveEdit: saveEdit,
    openNew: openNew,
    saveNew: saveNew,
    publish: publish,
    offline: offline,
    getMetricById: getMetricById
  };

  global.toggleBatchMode = toggleBatchMode;
  global.batchSuggestMetrics = batchSuggestMetrics;
  global.batchCreateMetrics = batchCreateMetrics;
  global.showNewMetricInline = showNewMetricInline;
  global.cancelInlineNew = cancelInlineNew;
  global.inlineSuggestMetric = inlineSuggestMetric;
  global.saveInlineNew = saveInlineNew;
  global.showBatchMetricModal = showBatchMetricModal;

  global.editMetric = function (id) {
    openEdit(id);
  };

  document.addEventListener('DOMContentLoaded', bindMgmtFilters);
})(window);
