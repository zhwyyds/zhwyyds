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
    if (elReviewed) elReviewed.textContent = String(published);
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
      tbody.innerHTML =
        '<tr><td colspan="10" class="text-sm text-muted" style="padding:20px;">无匹配指标</td></tr>';
      return;
    }
    tbody.innerHTML = rows
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
      metric_abbr: '',
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
      category_l1: '',
      category_l2: '',
      unit: getFormValue('newMetricUnit'),
      frequency: getFormValue('newMetricFrequency')
    };
    apiFetch('/api/metrics', { method: 'POST', body: JSON.stringify(row) })
      .then(function () {
        closeModal('newMetricModal');
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

  global.editMetric = function (id) {
    openEdit(id);
  };

  document.addEventListener('DOMContentLoaded', bindMgmtFilters);
})(window);
