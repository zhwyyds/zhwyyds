// Page Navigation
const navItems = document.querySelectorAll('.nav-item[data-page]');
const pages = document.querySelectorAll('.page');
const pageTitle = document.getElementById('pageTitle');

const pageTitles = {
  'dashboard': '治理总览',
  'metrics': '指标库',
  'metric-mgmt': '指标管理',
  'roots': '词根库',
  'batch-gen': '批量生成',
  'review': '模型评审',
  'lineage': '字段血缘',
  'table-lineage': '表血缘',
  'naming': '命名规范',
  'caliber': '口径治理',
  'scoring': '评分看板'
};

navItems.forEach(item => {
  item.addEventListener('click', () => {
    const target = item.dataset.page;
    navItems.forEach(n => n.classList.remove('active'));
    item.classList.add('active');
    pages.forEach(p => p.classList.remove('active'));
    const targetPage = document.getElementById('page-' + target);
    if (targetPage) targetPage.classList.add('active');
    pageTitle.innerHTML = pageTitles[target] + ' <span class="crumb">› 数据治理平台</span>';
    window.scrollTo(0, 0);
    if (target === 'table-lineage') setTimeout(drawTableLineageGraph, 80);
    if (target === 'batch-gen') refreshBatchPreview();
    if (typeof DG !== 'undefined' && DG.loadAll) DG.loadAll(true);
  });
});

window.addEventListener('resize', function() {
  if (document.getElementById('page-table-lineage').classList.contains('active')) {
    drawTableLineageGraph();
  }
});

// Tree Toggle
function toggleTree(element) {
  const toggle = element.querySelector('.tree-toggle');
  const children = element.nextElementSibling;
  if (children && children.classList.contains('tree-children')) {
    children.classList.toggle('expanded');
    toggle.textContent = children.classList.contains('expanded') ? '▼' : '▶';
  }
}

// Legacy Score Toggle (kept for backward compat, now using toggleDetailScore)
function toggleScoreSection(element) {
  var card = element.closest('.metric-detail-card') || element.closest('.metric-card');
  if (!card) return;
  var section = card.querySelector('.metric-detail-score-section') || card.querySelector('.metric-card-score-section');
  if (!section) return;
  var arrow = element.querySelector('.toggle-arrow');
  section.classList.toggle('show');
  element.classList.toggle('expanded');
  if (arrow) arrow.textContent = section.classList.contains('show') ? '\u25BC' : '\u25B6';
}

// Batch Selection
function toggleSelectAll(element) {
  const rows = document.querySelectorAll('#batchTableBody .batch-row');
  const isChecked = !element.classList.contains('checked');
  rows.forEach(row => {
    const checkbox = row.querySelector('.custom-checkbox');
    if (isChecked) {
      checkbox.classList.add('checked');
      row.classList.add('row-selected');
    } else {
      checkbox.classList.remove('checked');
      row.classList.remove('row-selected');
    }
  });
  if (isChecked) {
    element.classList.add('checked');
  } else {
    element.classList.remove('checked');
    element.classList.remove('indeterminate');
  }
  updateBatchToolbar();
}

function toggleRowSelect(element) {
  const row = element.closest('.batch-row');
  element.classList.toggle('checked');
  row.classList.toggle('row-selected');
  updateSelectAllState();
  updateBatchToolbar();
}

function updateSelectAllState() {
  const selectAll = document.getElementById('selectAllCheckbox');
  const checkboxes = document.querySelectorAll('#batchTableBody .custom-checkbox.checked');
  const allCheckboxes = document.querySelectorAll('#batchTableBody .custom-checkbox');
  selectAll.classList.remove('checked', 'indeterminate');
  if (checkboxes.length === allCheckboxes.length && checkboxes.length > 0) {
    selectAll.classList.add('checked');
  } else if (checkboxes.length > 0) {
    selectAll.classList.add('indeterminate');
  }
}

function updateBatchToolbar() {
  const selected = document.querySelectorAll('#batchTableBody .custom-checkbox.checked');
  const count = selected.length;
  document.getElementById('batchCount').textContent = '已选择 ' + count + ' 个指标';
  document.getElementById('batchReviewStatus').textContent = count > 0 ? 'AI评审通过 · 可发布' : '—';
  const publishBtn = document.querySelector('.batch-toolbar-actions .btn-primary');
  if (publishBtn) {
    publishBtn.style.opacity = count > 0 ? '1' : '0.5';
    publishBtn.style.pointerEvents = count > 0 ? 'auto' : 'none';
  }
}

function clearSelection() {
  document.querySelectorAll('#batchTableBody .custom-checkbox.checked').forEach(cb => cb.classList.remove('checked'));
  document.querySelectorAll('#batchTableBody .row-selected').forEach(row => row.classList.remove('row-selected'));
  const selectAll = document.getElementById('selectAllCheckbox');
  selectAll.classList.remove('checked', 'indeterminate');
  updateBatchToolbar();
}

function selectAllReviewed() {
  const rows = document.querySelectorAll('#batchTableBody .batch-row');
  rows.forEach(row => {
    const checkbox = row.querySelector('.custom-checkbox');
    checkbox.classList.add('checked');
    row.classList.add('row-selected');
  });
  document.getElementById('selectAllCheckbox').classList.add('checked');
  updateBatchToolbar();
}

function batchPublish() {
  const selected = document.querySelectorAll('#batchTableBody .custom-checkbox.checked');
  if (selected.length === 0) return;
  alert('批量发布 ' + selected.length + ' 个指标\n\n发布流程：\n1. 校验指标完整性\n2. 更新指标状态为已发布\n3. 记录发布日志\n4. 通知相关下游');
}

function singlePublish(btn) {
  const row = btn.closest('.batch-row');
  const id = row.querySelector('td:nth-child(2)').textContent;
  const name = row.querySelector('td:nth-child(3)').textContent;
  alert('发布指标 ' + id + ' ' + name + '\n\n状态: 待发布 → 已发布');
}

// Checkbox Toggle
document.querySelectorAll('.checkbox-item').forEach(item => {
  if (item.classList.contains('disabled')) return;
  item.addEventListener('click', () => {
    item.classList.toggle('checked');
    refreshBatchPreview();
  });
});

document.querySelectorAll('#page-batch-gen .grid-2 tbody input[type=checkbox]').forEach(function(cb) {
  cb.addEventListener('change', refreshBatchPreview);
});
refreshBatchPreview();

// Tab Switching
document.querySelectorAll('.tabs').forEach(tabGroup => {
  tabGroup.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      tabGroup.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
    });
  });
});

// ========== Metric Card Mock Data & Navigation ==========
var metricCards = [];
var metricCardIndex = 0;
document.addEventListener('DOMContentLoaded', function () {
  if (typeof MetricSpec !== 'undefined') updateMetricCard();
});

function refreshMetricLibraryFromApi(metrics, domains) {
  if (typeof MetricSpec !== 'undefined') MetricSpec.setDomainMap(domains);
  if (!metrics || !metrics.length) return;
  metricCards = metrics.map(function (r) {
    return {
      id: r.metric_id,
      name: r.metric_cn,
      en: r.metric_en,
      desc: r.caliber_desc,
      formula: r.formula || '',
      unit: r.unit,
      freq: r.frequency,
      owner: r.owner,
      category: r.category_l2 || r.metric_type || '—',
      categoryL1: r.category_l1,
      categoryL2: r.category_l2,
      domain: r.domain_code,
      source: r.source_model,
      reviewStatus: r.review_status,
      status: r.review_status === 'approved' ? 'published' : 'pending',
      grade: 'A',
      score: 85,
      priority: 'A 级 · 重要',
      valueType: r.value_type,
      dimensions: r.dimensions,
      scenario: r.scenario,
      reports: r.reports,
      analysisMethods: r.analysis_methods,
      alertRules: r.alert_rules,
      precision: r.precision,
      dataSources: r.data_sources,
      techCaliber: r.tech_caliber,
      hasDispute: r.objection_status === 'open',
      _apiRow: r
    };
  });
  if (metricCardIndex >= metricCards.length) metricCardIndex = 0;
  var drawerBody = document.getElementById('metricDrawerBody');
  if (drawerBody) drawerBody.dataset.ready = '0';
  updateMetricCard();
  if (typeof MetricTreeUI !== 'undefined' && MetricTreeUI.applyMetricFilters) {
    MetricTreeUI.applyMetricFilters();
  }
}
window.refreshMetricLibraryFromApi = refreshMetricLibraryFromApi;

function updateMetricDetailHeader(m) {
  if (!m) return;
  var idEl = document.getElementById('libMetricId');
  var nameEl = document.getElementById('libMetricName');
  var enEl = document.getElementById('libMetricEn');
  if (idEl) idEl.textContent = m.id || '—';
  if (nameEl) nameEl.textContent = m.name || '—';
  if (enEl) {
    enEl.innerHTML = escTag(m.en);
  }
  var grade = (m.grade || 'A').toLowerCase();
  var gradeEl = document.getElementById('libMetricGrade');
  if (gradeEl) {
    gradeEl.className = 'badge badge-' + grade;
    gradeEl.textContent = m.grade || 'A';
  }
  var stEl = document.getElementById('libMetricStatus');
  if (stEl) {
    var rs = m.reviewStatus || m.status || 'pending';
    if (rs === 'approved' || m.status === 'published') {
      stEl.className = 'badge badge-pass';
      stEl.textContent = '✅ 已发布';
    } else if (rs === 'offline') {
      stEl.className = 'badge badge-neutral';
      stEl.textContent = '⬇ 已下线';
    } else {
      stEl.className = 'badge badge-warn';
      stEl.textContent = '⏳ 待确认';
    }
  }
  var versionChip = document.getElementById('libVersionChip');
  if (versionChip) {
    var ver = (m._apiRow && (m._apiRow.version || m._apiRow.version_history)) ? (m._apiRow.version || '已发布') : '';
    if (ver) {
      versionChip.className = 'badge badge-pass';
      versionChip.textContent = ver;
    } else {
      versionChip.className = 'badge badge-neutral';
      versionChip.textContent = '未发布';
    }
  }

  var tagsEl = document.getElementById('libMetricTags');
  if (tagsEl) {
    var typeLabel = m.parentMetric ? '派生指标' : '原子指标';
    if (m._apiRow && m._apiRow.metric_type === 'derived') typeLabel = '派生指标';
    if (m._apiRow && m._apiRow.metric_type === 'composite') typeLabel = '复合指标';
    tagsEl.innerHTML =
      '<span class="tag tag-primary">' +
      escTag(m.domain) +
      '</span>' +
      '<span class="tag">' +
      escTag(typeLabel) +
      '</span>' +
      '<span class="tag">' +
      escTag(m.categoryL2 || m.category || '—') +
      '</span>' +
      '<span class="tag">' +
      escTag(m.priority || 'A 级 · 重要') +
      '</span>' +
      '<span class="tag">' +
      escTag(m.source || 'manual') +
      '</span>';
  }
  var score = m.score != null ? m.score : 85;
  var scoreLabel = document.getElementById('libAiScoreLabel');
  if (scoreLabel) scoreLabel.textContent = score + ' 分 · ' + (m.grade || 'A') + ' 级';
  var circle = document.getElementById('libScoreCircle');
  if (circle) {
    circle.textContent = String(score);
    circle.className = 'score-circle-mini ' + grade;
  }
  var sg = document.getElementById('libScoreGrade');
  if (sg) sg.textContent = (m.priority || m.grade + ' 级 · 重要');
}

function updateMetricCard() {
  var m = metricCards[metricCardIndex];
  if (!m) {
    document.querySelectorAll('.metric-spec-host').forEach(function (host) {
      host.innerHTML =
        '<div class="text-sm text-muted" style="padding:24px;text-align:center;">暂无指标数据，请确认已启动 API 或从左侧管理树选择</div>';
    });
    return;
  }

  updateMetricDetailHeader(m);

  document.querySelectorAll('.metric-detail-nav-info .current').forEach(function (el) {
    el.textContent = String(metricCardIndex + 1);
  });
  document.querySelectorAll('.metric-detail-nav-info .metric-nav-total').forEach(function (el) {
    el.textContent = String(metricCards.length);
  });
  document.querySelectorAll('.metric-detail-nav-info .metric-nav-path').forEach(function (el) {
    el.textContent = (m.categoryL1 || m.domain || '—') + ' / ' + (m.categoryL2 || m.category || '—');
  });

  document.querySelectorAll('.metric-detail-card').forEach(function (card) {
    updateMetricCardElement(card, m);
  });
  if (window.MetricLibrary && MetricLibrary.refresh) MetricLibrary.refresh();
  if (window.MetricScore && MetricScore.loadForCurrentMetric) MetricScore.loadForCurrentMetric();
}

function updateMetricCardElement(card, m) {
  var host = card.querySelector('.metric-spec-host');
  if (host && typeof MetricSpec !== 'undefined') {
    var spec = m._apiRow
      ? MetricSpec.apiRowToSpec(m._apiRow, MetricSpec._domainMap || {})
      : MetricSpec.mockToSpec(m);
    MetricSpec.renderIndicatorSpecCard(host, spec);
  }
}

function editCurrentMetric() {
  var m = metricCards[metricCardIndex];
  if (!m || !m.id) return;
  switchToPage('metric-mgmt');
  setTimeout(function () {
    if (window.MetricMgmt && MetricMgmt.openEdit) MetricMgmt.openEdit(m.id);
  }, 100);
}

function escTag(s) {
  if (!s) return '—';
  return String(s).replace(/</g, '&lt;');
}

function prevMetric() {
  if (metricCardIndex > 0) metricCardIndex--;
  updateMetricCard();
}
function nextMetric() {
  if (metricCardIndex < metricCards.length - 1) metricCardIndex++;
  updateMetricCard();
}

// Score Sub-Section Toggle (within metric detail score)
function toggleSubSection(toggle, sectionId) {
  var section = document.getElementById(sectionId);
  if (!section) return;
  section.classList.toggle('show');
  toggle.classList.toggle('expanded');
}

// Detail Score Toggle
function toggleDetailScore(element) {
  var section = element.nextElementSibling;
  var arrow = element.querySelector('.toggle-arrow');
  section.classList.toggle('show');
  element.classList.toggle('expanded');
  arrow.textContent = section.classList.contains('show') ? '\u25BC' : '\u25B6';
  if (!section.classList.contains('show')) return;
  if (section.id === 'metricAiReviewSection') {
    if (window.MetricLibrary && MetricLibrary.loadReviewForCurrentMetric) MetricLibrary.loadReviewForCurrentMetric();
    if (window.MetricScore && MetricScore.loadForCurrentMetric) MetricScore.loadForCurrentMetric();
  } else if (section.id === 'metricVersionSection') {
    if (window.MetricScore && MetricScore.loadVersionForCurrentMetric) MetricScore.loadVersionForCurrentMetric();
  }
}

function submitReviewForCurrentMetric() {
  var m = metricCards[metricCardIndex];
  if (!m || !m.id) {
    alert('请先选择指标');
    return;
  }
  submitReview(m.id);
}

// Dispute Form Toggle — 实现见 js/metric-library.js

// Jump functions — navigate to the correct page and scroll to target
function switchToPage(target) {
  document.querySelectorAll('.nav-item[data-page]').forEach(function(n) { n.classList.remove('active'); });
  var navItem = document.querySelector('.nav-item[data-page="' + target + '"]');
  if (navItem) navItem.classList.add('active');
  document.querySelectorAll('.page').forEach(function(p) { p.classList.remove('active'); });
  var targetPage = document.getElementById('page-' + target);
  if (targetPage) targetPage.classList.add('active');
  var pageTitle = document.getElementById('pageTitle');
  var titles = { 'dashboard': '治理总览', 'metrics': '指标库', 'metric-mgmt': '指标管理', 'roots': '词根库', 'batch-gen': '批量生成', 'review': '模型评审', 'lineage': '字段血缘', 'table-lineage': '表血缘', 'naming': '命名规范', 'caliber': '口径治理', 'scoring': '评分看板', 'caliber-check': '口径核查', 'settings': '系统设置' };
  pageTitle.innerHTML = titles[target] + ' <span class="crumb">› 数据治理平台</span>';
  window.scrollTo(0, 0);
}

function setMetricIndexById(id) {
  for (var i = 0; i < metricCards.length; i++) {
    if (metricCards[i].id === id) { metricCardIndex = i; return true; }
  }
  return false;
}

function ensureMetricDrawerContent() {
  var body = document.getElementById('metricDrawerBody');
  if (!body || body.dataset.ready === '1') return;
  body.innerHTML = '';
  var src = document.getElementById('page-metrics');
  if (!src) return;
  var nav = src.querySelector('.metric-detail-nav');
  var card = src.querySelector('.metric-detail-card');
  if (nav) body.appendChild(nav.cloneNode(true));
  if (card) body.appendChild(card.cloneNode(true));
  body.dataset.ready = '1';
}

function openMetricDrawer(id) {
  if (id && !setMetricIndexById(id)) {
    if (window.__DG_METRIC_ROWS__) {
      for (var j = 0; j < window.__DG_METRIC_ROWS__.length; j++) {
        if (window.__DG_METRIC_ROWS__[j].metric_id === id) {
          metricCardIndex = j;
          break;
        }
      }
    } else return;
  }
  ensureMetricDrawerContent();
  updateMetricCard();
  document.getElementById('metricDetailDrawer').classList.add('show');
  document.body.style.overflow = 'hidden';
}

function closeMetricDrawer() {
  document.getElementById('metricDetailDrawer').classList.remove('show');
  document.body.style.overflow = '';
  var body = document.getElementById('metricDrawerBody');
  if (body) body.dataset.ready = '0';
}

function jumpToMetric(id) {
  openMetricDrawer(id);
}

function viewMetric(id) {
  openMetricDrawer(id);
}

function jumpToRoot(id) {
  switchToPage('roots');
  setTimeout(function() {
    // Flash the root row
    var rows = document.querySelectorAll('#page-roots table tbody tr');
    rows.forEach(function(r) {
      var firstCell = r.querySelector('td');
      if (firstCell && firstCell.textContent.trim() === id) {
        r.style.background = '#FEF3C7';
        setTimeout(function() { r.style.background = ''; }, 2000);
      }
    });
  }, 100);
}

function jumpToLineage(id) {
  // Check if it's a table name or lineage ID
  if (id.startsWith('dwd_') || id.startsWith('dws_') || id.startsWith('ads_') || id.startsWith('ods_')) {
    switchToPage('table-lineage');
    setTimeout(function() {
      var nodes = document.querySelectorAll('#page-table-lineage .ln-node');
      nodes.forEach(function(n) {
        var text = n.textContent || n.innerText;
        if (text.indexOf(id) !== -1) {
          n.style.outline = '3px solid var(--primary)';
          n.style.outlineOffset = '4px';
          setTimeout(function() { n.style.outline = ''; }, 3000);
          n.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      });
    }, 100);
  } else {
    switchToPage('lineage');
  }
}

// Metric Management Actions — 查看弹层；编辑见 MetricMgmt
function editMetric(id) {
  if (window.MetricMgmt && MetricMgmt.openEdit) MetricMgmt.openEdit(id);
}

function publishMetric(id) {
  if (window.MetricMgmt && MetricMgmt.publish) {
    MetricMgmt.publish(id);
  }
}

function getMetricsList() {
  return window.__DG_METRICS__ || window.__DG_METRIC_ROWS__ || [];
}

function submitReview(id) {
  var base = (typeof dgApiBase === 'function') ? dgApiBase() : '';
  var row = findMetricRow(id);
  if (row) {
    var reviewCell = row.querySelectorAll('td')[6];
    if (reviewCell) reviewCell.innerHTML = '<span class="badge badge-warn">&#9203; 评审中…</span>';
  }
  if (window.toast) {
    toast('🤖 评审进行中（多模型比对，约 1 分钟）…');
  }
  fetch(base + '/api/metrics/' + encodeURIComponent(id) + '/review', { method: 'POST' })
    .then(function (res) {
      if (!res.ok) throw new Error(res.status);
      return res.json();
    })
    .then(function (doc) {
      if (window.DGExt && DGExt.renderReviewDetail) DGExt.renderReviewDetail(doc);
      if (window.MetricLibrary && MetricLibrary.loadReviewForCurrentMetric) {
        MetricLibrary.loadReviewForCurrentMetric();
      }
      if (window.DG && DG.loadAll) return DG.loadAll(false);
    })
    .then(function () {
      switchToPage('review');
      if (window.toast) {
        toast('✅ 评审完成，结果已写入 reviews/metric_reviews/', 'success');
      }
    })
    .catch(function (e) {
      if (window.toast) toast('评审失败: ' + e.message);
      else alert('评审失败: ' + e.message);
      if (window.DG && DG.loadAll) DG.loadAll(false);
    });
}

function filterReviewQueue(filter) {
  var items = document.querySelectorAll('.review-queue-item');
  items.forEach(function(item) {
    var statusBadge = item.querySelector('.badge:last-child');
    var status = statusBadge ? statusBadge.textContent.trim() : '';
    var hasDanger = item.querySelector('.text-danger');
    if (filter === 'all') { item.style.display = ''; }
    else if (filter === 'pending') { item.style.display = status === 'pending' ? '' : 'none'; }
    else if (filter === 'conflict') { item.style.display = (hasDanger || status === 'pending') ? '' : 'none'; }
    else if (filter === 'auto_pass') { item.style.display = status === 'auto_pass' ? '' : 'none'; }
  });
  // Highlight active stat card
  document.querySelectorAll('#page-review .stat-card').forEach(function(c) { c.style.outline = ''; });
  var activeCard = event.currentTarget;
  if (activeCard) activeCard.style.outline = '2px solid var(--primary)';
}

// ========== Naming Page Actions ==========
function batchReplacePinyin() {
  if (!confirm('确认批量替换当前显示的拼音残留指标？\n\n将把拼音字段名替换为对应的英文词根命名。')) return;
  var table = document.querySelector('#page-naming table');
  if (!table) return;
  var rows = table.querySelectorAll('tbody tr');
  var count = 0;
  rows.forEach(function(row) {
    if (row.style.display !== 'none') {
      var cells = row.querySelectorAll('td');
      if (cells.length > 2) {
        cells[2].textContent = cells[1].textContent.toLowerCase().replace(/\s+/g, '_');
        count++;
      }
    }
  });
  alert('批量替换完成：' + count + ' 个指标已更新');
}

// ========== Batch Generation ==========
function countBatchAtoms() {
  return document.querySelectorAll('#page-batch-gen .grid-2 tbody input[type=checkbox]:checked').length;
}
function countBatchModifiers() {
  return document.querySelectorAll('#page-batch-gen .checkbox-item.checked:not(.disabled)').length;
}
function refreshBatchPreview() {
  var atoms = countBatchAtoms();
  var mods = countBatchModifiers();
  var total = atoms * mods;
  var el = document.getElementById('batchPreviewCount');
  if (el) {
    el.innerHTML = atoms + ' 个原子 × ' + mods + ' 个修饰词 = <strong style="color:var(--primary)">' + total + ' 个衍生指标</strong>';
  }
  var badge = document.querySelector('#page-batch-gen .card-header .badge-info');
  if (badge) badge.textContent = '已选 ' + atoms + ' 个';
}
function batchGenerate(ev) {
  var btn = ev && ev.currentTarget ? ev.currentTarget : null;
  if (btn) {
    btn.disabled = true;
    btn.textContent = '\u23f3 正在生成...';
  }
  refreshBatchPreview();
  var total = countBatchAtoms() * countBatchModifiers();

  setTimeout(function() {
    var previewTable = document.getElementById('batchPreviewTable');
    if (!previewTable) {
      if (btn) { btn.disabled = false; btn.textContent = '\u26a1 一键生成'; }
      return;
    }
    var tbody = previewTable.querySelector('tbody');
    var rows = tbody.querySelectorAll('tr');
    rows.forEach(function(row) {
      var statusCell = row.querySelector('td:last-child span');
      if (statusCell) {
        statusCell.className = 'badge badge-pass';
        statusCell.textContent = '\u2713 已生成';
      }
      row.style.background = '#D1FAE5';
      setTimeout(function() { row.style.background = ''; }, 1500);
    });
    if (btn) {
      btn.textContent = '\u2705 生成完成 (' + rows.length + ' 预览 / ' + total + ' 计划)';
      btn.disabled = false;
      btn.style.background = 'var(--success)';
      setTimeout(function() {
        btn.textContent = '\u26a1 一键生成';
        btn.style.background = '';
      }, 3000);
    }
  }, 1200);
}

// ========== Model Review Queue Interactions ==========
function loadReviewItem(id) {
  // Highlight selected item
  document.querySelectorAll('.review-queue-item').forEach(function(item) {
    item.style.background = '';
    item.style.borderColor = '';
  });
  var clicked = event.currentTarget;
  clicked.style.background = 'var(--primary-light)';
  clicked.style.borderColor = 'var(--primary)';

  // Update review detail area
  var detailArea = document.querySelector('#page-review .card:nth-child(3) .card-body');
  if (!detailArea) return;

  // Get item info from the clicked element
  var nameEl = clicked.querySelector('.text-13');
  var idEl = clicked.querySelector('.text-mono');
  var statusEl = clicked.querySelector('.badge:last-child');
  var name = nameEl ? nameEl.textContent : id;
  var metricId = idEl ? idEl.textContent : id;
  var status = statusEl ? statusEl.textContent : 'pending';

  var isConflict = clicked.querySelector('.text-danger');
  var conflictText = clicked.querySelector('.text-xs:last-child');
  var conflictMsg = conflictText ? conflictText.textContent : '';

  detailArea.innerHTML = '<div style="padding:16px;">' +
    '<div class="flex align-center justify-between mb-3">' +
    '<div><span class="text-lg text-bold">' + name + '</span><span class="text-mono text-sm ml-3">' + metricId + '</span></div>' +
    '<span class="badge badge-' + (status === 'auto_pass' ? 'pass' : 'warn') + '">' + (status === 'auto_pass' ? '\u2713 自动通过' : '\u23f3 待处理') + '</span>' +
    '</div>' +
    '<div class="text-xs text-muted mb-3">' + conflictMsg + '</div>' +
    '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:16px;">' +
    '<div style="padding:12px;background:#F0F9FF;border-radius:6px;border-left:3px solid #3B82F6;">' +
    '<div class="text-xs text-bold mb-1">GPT-4o</div>' +
    '<div class="text-xs text-muted mb-1">评分: 87 | 建议通过</div>' +
    '<div class="text-xs" style="color:var(--warning)">\u26a0 口径建议优化</div></div>' +
    '<div style="padding:12px;background:#F0FDF4;border-radius:6px;border-left:3px solid #10B981;">' +
    '<div class="text-xs text-bold mb-1">Claude-3.5</div>' +
    '<div class="text-xs text-muted mb-1">评分: 85 | 建议通过</div>' +
    '<div class="text-xs" style="color:var(--success)">\u2713 合格</div></div>' +
    '<div style="padding:12px;background:#FFF7ED;border-radius:6px;border-left:3px solid #F97316;">' +
    '<div class="text-xs text-bold mb-1">GLM-4</div>' +
    '<div class="text-xs text-muted mb-1">评分: 78 | 建议驳回</div>' +
    '<div class="text-xs" style="color:var(--danger)">\u2717 命名不规范</div></div>' +
    '</div>' +
    '<div class="flex gap-2" style="justify-content:flex-end;">' +
    '<button class="btn btn-sm" onclick="reviewAction(\'' + metricId + '\', \'reject\')" style="color:var(--danger)">\u274c 驳回</button>' +
    '<button class="btn btn-sm" onclick="reviewAction(\'' + metricId + '\', \'suggest\')">\ud83d\udcdd 采纳建议</button>' +
    '<button class="btn btn-sm btn-primary" onclick="reviewAction(\'' + metricId + '\', \'approve\')">\u2705 通过</button>' +
    '</div></div>';
}

function reviewAction(id, action) {
  var clicked = document.querySelector('.review-queue-item[style*="background: var(--primary-light)"]');
  var actions = { 'approve': '\u2705 已通过', 'reject': '\u274c 已驳回', 'suggest': '\ud83d\udcdd 建议优化' };
  if (clicked) {
    var statusBadge = clicked.querySelector('.badge:last-child');
    if (statusBadge) {
      statusBadge.className = action === 'approve' ? 'badge badge-pass' : action === 'reject' ? 'badge badge-fail' : 'badge badge-neutral';
      statusBadge.textContent = actions[action];
    }
    clicked.style.background = action === 'reject' ? '#FEE2E2' : action === 'approve' ? '#D1FAE5' : '#FEF3C7';
  }
  alert('评审操作完成: ' + id + '\n操作: ' + actions[action] + '\n\n已更新评审队列状态');
}

function showNewMetricModal() {
  if (window.MetricMgmt && MetricMgmt.openNew) MetricMgmt.openNew();
}

function saveNewMetric() {
  if (window.MetricMgmt && MetricMgmt.saveNew) MetricMgmt.saveNew();
}

function findMetricRow(id) {
  var rows = document.querySelectorAll('#batchTableBody tr');
  for (var i = 0; i < rows.length; i++) {
    var cells = rows[i].querySelectorAll('td');
    if (cells.length > 1 && cells[1].textContent.trim() === id) return rows[i];
  }
  return null;
}
function batchOffline() {
  var selected = document.querySelectorAll('.batch-row.selected');
  if (selected.length === 0) { alert('请先选择需要下线的指标'); return; }
  if (!confirm('确认批量下线 ' + selected.length + ' 个指标？\n\n状态将写回 CSV（review_status=offline）。')) return;
  var ids = [];
  selected.forEach(function (row) {
    var id = row.getAttribute('data-metric-id');
    if (id) ids.push(id);
  });
  var reason = 'batch';
  var done = 0;
  var failed = 0;
  function next(i) {
    if (i >= ids.length) {
      alert('批量下线完成\n\n成功: ' + done + ' 个\n失败: ' + failed + ' 个');
      if (window.DG && DG.loadAll) DG.loadAll(false);
      return;
    }
    var payload = { review_status: 'offline', offline_reason: reason, offline_note: '批量下线' };
    var p = (window.MetricMgmt && MetricMgmt.offline)
      ? MetricMgmt.offline(ids[i], payload)
      : (window.DG && DG.fetchJson
          ? DG.fetchJson('/api/metrics/' + encodeURIComponent(ids[i]), { method: 'PUT', body: JSON.stringify(payload) })
          : Promise.reject(new Error('API')));
    p.then(function () { done += 1; next(i + 1); })
      .catch(function () { failed += 1; next(i + 1); });
  }
  next(0);
}

// Modal helpers
function closeModal(modalId) {
  document.getElementById(modalId).classList.remove('show');
}

// Offline Modal (metric)
var metricData = {
  'M_SALE_020': { id: 'M_SALE_020', name: '实付订单金额', en: 'paid_order_amount' },
  'M_SALE_004': { id: 'M_SALE_004', name: '订单金额环比', en: 'mom_order_amount' },
  'M_MALL_001': { id: 'M_MALL_001', name: '出租率', en: 'occupancy_rate' },
  'M_CUST_001': { id: 'M_CUST_001', name: '活跃消费者数', en: 'active_customer_count' },
  'M_PTNR_001': { id: 'M_PTNR_001', name: '商户总数', en: 'partner_count' }
};
function showOfflineModal(metricId) {
  var apiRow = window.MetricMgmt && MetricMgmt.getMetricById ? MetricMgmt.getMetricById(metricId) : null;
  var m = apiRow
    ? { id: apiRow.metric_id, name: apiRow.metric_cn, en: apiRow.metric_en }
    : metricData[metricId] || { id: metricId, name: '', en: '' };
  document.getElementById('offlineMetricId').textContent = m.id;
  document.getElementById('offlineMetricName').textContent = m.name;
  document.getElementById('offlineMetricEn').textContent = m.en;
  document.getElementById('offlineReason').value = '';
  document.getElementById('offlineDesc').value = '';
  document.getElementById('offlineModal').classList.add('show');
}
function confirmOffline() {
  var reason = document.getElementById('offlineReason').value;
  if (!reason) { alert('请选择下线原因'); return; }
  var metricId = (document.getElementById('offlineMetricId').textContent || '').trim();
  var note = (document.getElementById('offlineDesc').value || '').trim();
  closeModal('offlineModal');
  var payload = {
    review_status: 'offline',
    offline_reason: reason,
    offline_note: note
  };
  var req = (window.MetricMgmt && MetricMgmt.offline)
    ? MetricMgmt.offline(metricId, payload)
    : (window.DG && DG.fetchJson
        ? DG.fetchJson('/api/metrics/' + encodeURIComponent(metricId), {
            method: 'PUT',
            body: JSON.stringify(payload)
          })
        : Promise.reject(new Error('API 未连接')));
  req
    .then(function () {
      if (window.DG && DG.loadAll) return DG.loadAll(false);
    })
    .then(function () {
      alert('指标 ' + metricId + ' 已下线并写回 CSV');
    })
    .catch(function (e) {
      alert('下线失败: ' + e.message + '\n\n请确认已执行 data-governance serve 且指标 ID 存在于 CSV。');
    });
}

// Root edit
var rootEditRow = null;
function showRootEditModal(btn) {
  var row = btn.closest('tr');
  if (!row) return;
  rootEditRow = row;
  var cells = row.querySelectorAll('td');
  document.getElementById('rootEditId').value = cells[0].textContent.trim();
  document.getElementById('rootEditCn').value = cells[1].textContent.trim();
  document.getElementById('rootEditEn').value = cells[2].textContent.trim();
  document.getElementById('rootEditAbbr').value = cells[3].textContent.trim();
  var typeBadge = cells[4].textContent.trim();
  var typeMap = { '名词': 'noun', '动词': 'verb', '形容词': 'adj' };
  document.getElementById('rootEditType').value = typeMap[typeBadge] || 'noun';
  document.getElementById('rootEditDesc').value = '';
  document.getElementById('rootEditModal').classList.add('show');
}
function saveRootEdit() {
  if (!rootEditRow) return;
  var cn = document.getElementById('rootEditCn').value.trim();
  var en = document.getElementById('rootEditEn').value.trim();
  var abbr = document.getElementById('rootEditAbbr').value.trim();
  if (!cn || !en || !abbr) { alert('请填写中文、英文与缩写'); return; }
  var cells = rootEditRow.querySelectorAll('td');
  cells[1].textContent = cn;
  cells[2].textContent = en;
  cells[3].textContent = abbr;
  closeModal('rootEditModal');
  rootEditRow.style.background = '#D1FAE5';
  setTimeout(function() { rootEditRow.style.background = ''; }, 1500);
  rootEditRow = null;
}

// Root Offline Modal
function showRootOfflineModal(rootId) {
  if (!confirm('词根下线后将标记为 deprecated，新指标不可再引用此词根。\n已被指标引用的词根下线后，存量引用不受影响。\n\n确认下线词根 ' + rootId + ' ？')) return;
  alert('词根 ' + rootId + ' 已下线');
}

// Delete Modal (metric + root)
function showDeleteModal(itemId, type) {
  var modal = document.getElementById('deleteModal');
  var idEl = document.getElementById('deleteMetricId');
  var nameEl = document.getElementById('deleteMetricName');
  var condGroup = document.getElementById('deleteConditionGroup');

  idEl.textContent = itemId;
  nameEl.textContent = type === 'root' ? '词根' : '';

  // Show condition check for offline metrics (archived), hide for draft
  if (type === 'root') {
    condGroup.style.display = 'none';
  } else {
    condGroup.style.display = 'block';
  }

  document.getElementById('deleteReason').value = '';
  modal.classList.add('show');
}
function confirmDelete() {
  var reason = document.getElementById('deleteReason').value.trim();
  if (!reason) { alert('请填写删除理由'); return; }
  if (!confirm('确认物理删除？此操作不可逆！')) return;
  var metricId = document.getElementById('deleteMetricId').textContent;
  var statusCell = document.getElementById('deleteMetricId').closest('.modal-body');
  closeModal('deleteModal');

  // Remove the row from the management table
  var row = findMetricRow(metricId);
  if (row) {
    row.style.background = '#FEE2E2';
    row.style.transition = 'all 0.3s';
    row.style.opacity = '0';
    setTimeout(function() {
      if (row.parentNode) row.parentNode.removeChild(row);
    }, 300);
  }
  alert('删除完成: ' + metricId + '\n理由: ' + reason + '\n操作日志已记录，不可恢复');
}

// Page Size Change & Pagination
var paginationState = {
  'mgmt': { page: 1, size: 12 },
  'log': { page: 1, size: 12 },
  'roots': { page: 1, size: 8 },
  'naming': { page: 1, size: 6 }
};

function changePageSize(select, pageId) {
  var size = parseInt(select.value);
  var label = document.getElementById(pageId + 'PageSizeLabel');
  if (label) label.textContent = size;
  paginationState[pageId] = paginationState[pageId] || {};
  paginationState[pageId].size = size;
  paginationState[pageId].page = 1; // Reset to first page
  applyPagination(pageId);
}

function goToPage(pageId, page) {
  paginationState[pageId] = paginationState[pageId] || {};
  paginationState[pageId].page = page;
  applyPagination(pageId);
}

function applyPagination(pageId) {
  var state = paginationState[pageId];
  if (!state) return;
  var size = state.size;
  var page = state.page;
  var rows;
  var isSpecial = false;

  if (pageId === 'mgmt') {
    rows = document.querySelectorAll('#page-metric-mgmt #batchTableBody > tr.batch-row');
  } else if (pageId === 'log') {
    rows = document.querySelectorAll('#page-metric-mgmt .card:nth-child(4) tbody tr');
    // More specific: find the operation log table
    var logTables = document.querySelectorAll('#page-metric-mgmt .card');
    var logTable = null;
    logTables.forEach(function(c) {
      var h = c.querySelector('.card-header');
      if (h && h.textContent.indexOf('操作记录') !== -1) {
        logTable = c.querySelector('tbody');
      }
    });
    if (logTable) rows = logTable.querySelectorAll('tr');
  } else if (pageId === 'roots') {
    rows = document.querySelectorAll('#page-roots table tbody tr');
  } else if (pageId === 'naming') {
    // Find the naming page's violation list table
    var namingTables = document.querySelectorAll('#page-naming table');
    var namingTable = null;
    for (var i = 0; i < namingTables.length; i++) {
      var ths = namingTables[i].querySelectorAll('th');
      for (var j = 0; j < ths.length; j++) {
        if (ths[j].textContent.indexOf('指标名') !== -1) { namingTable = namingTables[i]; break; }
      }
      if (namingTable) break;
    }
    if (namingTable) rows = namingTable.querySelectorAll('tbody tr');
  }

  if (!rows || rows.length === 0) return;

  var totalPages = Math.max(1, Math.ceil(rows.length / size));
  if (page > totalPages) { page = totalPages; state.page = page; }
  if (page < 1) { page = 1; state.page = page; }

  var start = (page - 1) * size;
  var end = start + size;

  rows.forEach(function(row, i) {
    if (i >= start && i < end) {
      row.style.display = '';
    } else {
      row.style.display = 'none';
    }
  });

  // Update all pagination bars for this page
  var selectEl = document.querySelector('#page-' + pageId + ' .page-size-selector select');
  var sizeHint = selectEl && ('all' in selectEl) ? selectEl.value : size;
  updatePaginationBar(pageId, page, totalPages, size, rows.length, sizeHint);
}

function updatePaginationBar(pageId, page, totalPages, size, totalRows) {
  // Find and update page indicators
  var bars = document.querySelectorAll('.pagination-bar[data-page-id="' + pageId + '"]');
  bars.forEach(function(bar) {
    // Update page info text
    var infoSpan = bar.querySelector('.text-sm.text-muted');
    if (infoSpan) {
      var displayed = Math.min(size, totalRows - (page - 1) * size);
      infoSpan.textContent = '共 ' + totalRows + ' 条，显示 ' + displayed + ' 条';
    }

    // Update page buttons
    var pageButtons = bar.querySelectorAll('.flex.gap-2 button');
    var btns = Array.from(pageButtons);
    // Remove old page number buttons (non-nav buttons)
    btns.forEach(function(b, i) {
      if (b.textContent.indexOf('上一页') === -1 && b.textContent.indexOf('下一页') === -1) {
        // Rebuild page buttons
      }
    });

    // Find the button container
    var btnContainer = bar.querySelector('.flex.gap-2');
    if (btnContainer) {
      // Keep prev/next, rebuild page buttons
      var prevBtn = btnContainer.querySelector('button:first-child');
      var nextBtn = btnContainer.querySelector('button:last-child');

      // Clear and rebuild
      var html = '';
      html += '<button class="btn btn-sm" onclick="goToPage(\'' + pageId + '\', ' + (page - 1) + ')"' + (page <= 1 ? ' disabled style="opacity:0.4"' : '') + '>&#8249; 上一页</button>';

      // Page number buttons
      var startPage = Math.max(1, page - 2);
      var endPage = Math.min(totalPages, page + 2);
      if (startPage > 1) { html += '<button class="btn btn-sm" onclick="goToPage(\'' + pageId + '\', 1)">1</button>'; if (startPage > 2) html += '<button class="btn btn-sm" disabled>&hellip;</button>'; }
      for (var p = startPage; p <= endPage; p++) {
        html += '<button class="btn btn-sm' + (p === page ? ' btn-primary' : '') + '" onclick="goToPage(\'' + pageId + '\', ' + p + ')">' + p + '</button>';
      }
      if (endPage < totalPages) { if (endPage < totalPages - 1) html += '<button class="btn btn-sm" disabled>&hellip;</button>'; html += '<button class="btn btn-sm" onclick="goToPage(\'' + pageId + '\', ' + totalPages + ')">' + totalPages + '</button>'; }

      html += '<button class="btn btn-sm" onclick="goToPage(\'' + pageId + '\', ' + (page + 1) + ')"' + (page >= totalPages ? ' disabled style="opacity:0.4"' : '') + '>下一页 &#8250;</button>';
      btnContainer.innerHTML = html;
    }
  });

  // Also update the simpler bars (naming)
  document.querySelectorAll('#page-naming .text-sm.text-muted').forEach(function(el) {
    if (el.textContent.indexOf('共') !== -1 && el.textContent.indexOf('条') !== -1) {
      var displayed = Math.min(size, totalRows - (page - 1) * size);
      el.textContent = '共 ' + totalRows + ' 条，显示 ' + displayed + ' 条';
    }
  });
}

// Auto-expand first tree node + initialize pagination
window.addEventListener('DOMContentLoaded', () => {
  const firstTreeItem = document.querySelector('.tree-item .tree-toggle');
  if (firstTreeItem) {
    toggleTree(firstTreeItem.parentElement);
    const secondLevel = firstTreeItem.parentElement.nextElementSibling;
    if (secondLevel) {
      const secondToggle = secondLevel.querySelector('.tree-item .tree-toggle');
      if (secondToggle) {
        toggleTree(secondToggle.parentElement);
      }
    }
  }
  // Initialize batch toolbar
  updateBatchToolbar();
  // Initialize pagination
  setTimeout(function() {
    Object.keys(paginationState).forEach(function(pageId) {
      applyPagination(pageId);
    });
  }, 200);
});

// ========== Lineage Graph Interactions ==========

// Lineage data store
const lineageData = {
  TL_001: { source: 'ods_sale_order_di', target: 'dwd_sale_order_df', type: 'join', logic: '清洗 + 字段补全 + JOIN 关联', fields: '5/12', update: '08-02 22:00',
    fieldMappings: [{src: 'order_id', tgt: 'order_id', type: 'direct'}, {src: 'order_amount', tgt: 'order_amount', type: 'direct'}, {src: 'order_status', tgt: 'order_status', type: 'direct'}, {src: 'create_time', tgt: 'create_time', type: 'direct'}, {src: 'mall_id', tgt: 'mall_id', type: 'direct'}] },
  TL_002: { source: 'ods_sale_payment_di', target: 'dwd_sale_order_df', type: 'join', logic: 'JOIN 关联 + 支付状态补全', fields: '4/12', update: '08-02 22:00',
    fieldMappings: [{src: 'payment_id', tgt: 'payment_id', type: 'direct'}, {src: 'order_id', tgt: 'order_id', type: 'join'}, {src: 'paid_amount', tgt: 'paid_amount', type: 'direct'}, {src: 'pay_time', tgt: 'pay_time', type: 'direct'}] },
  TL_003: { source: 'ods_sale_refund_di', target: 'dwd_sale_order_df', type: 'join', logic: 'LEFT JOIN 退款信息', fields: '3/12', update: '08-02 22:00',
    fieldMappings: [{src: 'refund_id', tgt: 'refund_id', type: 'direct'}, {src: 'order_id', tgt: 'order_id', type: 'join'}, {src: 'refund_amount', tgt: 'refund_amount', type: 'direct'}] },
  TL_004: { source: 'ods_sale_order_di', target: 'dwd_sale_payment_df', type: 'join', logic: '关联订单ID', fields: '2/8', update: '08-02 22:00',
    fieldMappings: [{src: 'order_id', tgt: 'order_id', type: 'join'}, {src: 'mall_id', tgt: 'mall_id', type: 'direct'}] },
  TL_005: { source: 'dwd_sale_order_df', target: 'dws_sale_order_mtd', type: 'aggregate', logic: 'SUM + COUNT 聚合，按月分组', fields: '5/8', update: '08-02 22:00',
    fieldMappings: [{src: 'order_amount', tgt: 'mtd_order_amount', type: 'aggregate', logic: 'SUM(order_amount)'}, {src: 'order_id', tgt: 'order_count', type: 'aggregate', logic: 'COUNT(DISTINCT order_id)'}, {src: 'paid_amount', tgt: 'mtd_paid_amount', type: 'aggregate', logic: 'SUM(paid_amount)'}, {src: 'order_amount, refund_amount', tgt: 'net_order_amount', type: 'calc', logic: 'SUM(order_amount)-SUM(refund_amount)'}, {src: 'mall_id', tgt: 'mall_id', type: 'direct', logic: '直接映射'}] },
  TL_006: { source: 'dwd_sale_payment_df', target: 'dws_sale_order_mtd', type: 'aggregate', logic: 'SUM 实付金额聚合', fields: '3/8', update: '08-02 22:00',
    fieldMappings: [{src: 'paid_amount', tgt: 'mtd_paid_amount', type: 'aggregate', logic: 'SUM(paid_amount)'}, {src: 'payment_count', tgt: 'payment_count', type: 'aggregate', logic: 'COUNT(*)'}, {src: 'mall_id', tgt: 'mall_id', type: 'direct', logic: '直接映射'}] },
  TL_007: { source: 'dwd_sale_order_df', target: 'dws_sale_order_ytd', type: 'aggregate', logic: 'SUM + COUNT 聚合，按年分组', fields: '4/6', update: '08-02 22:00',
    fieldMappings: [{src: 'order_amount', tgt: 'ytd_order_amount', type: 'aggregate', logic: 'SUM(order_amount)'}, {src: 'order_id', tgt: 'order_count', type: 'aggregate', logic: 'COUNT(DISTINCT order_id)'}, {src: 'paid_amount', tgt: 'ytd_paid_amount', type: 'aggregate', logic: 'SUM(paid_amount)'}, {src: 'mall_id', tgt: 'mall_id', type: 'direct', logic: '直接映射'}] },
  TL_008: { source: 'dws_sale_order_mtd', target: 'ads_sale_dashboard', type: 'direct', logic: '直接引用 + 计算字段', fields: '8/10', update: '08-02 22:00',
    fieldMappings: [{src: 'mtd_order_amount', tgt: 'mtd_order_amount', type: 'direct'}, {src: 'order_count', tgt: 'order_count', type: 'direct'}, {src: 'mtd_paid_amount', tgt: 'mtd_paid_amount', type: 'direct'}, {src: 'net_order_amount', tgt: 'net_order_amount', type: 'direct'}, {src: 'mall_id', tgt: 'mall_id', type: 'direct'}, {src: 'mtd_order_amount, order_count', tgt: 'avg_order_value', type: 'calc', logic: 'mtd_order_amount/order_count'}, {src: 'mtd_paid_amount, mtd_order_amount', tgt: 'payment_rate', type: 'calc', logic: 'mtd_paid_amount/mtd_order_amount'}, {src: 'mall_id', tgt: 'mall_name', type: 'lookup', logic: 'JOIN dim_mall'}] },
  TL_009: { source: 'dws_sale_order_ytd', target: 'ads_sale_dashboard', type: 'direct', logic: '直接引用', fields: '2/10', update: '08-02 22:00',
    fieldMappings: [{src: 'ytd_order_amount', tgt: 'ytd_order_amount', type: 'direct'}, {src: 'order_count', tgt: 'ytd_order_count', type: 'direct'}] }
};

const fieldLineageData = {
  FL_001: { source: 'dwd_sale_order_df', target: 'dws_sale_order_mtd', srcField: 'order_amount', tgtField: 'mtd_order_amount', type: 'aggregate', logic: 'SUM(order_amount) WHERE month=current', fields: '1→1' },
  FL_002: { source: 'dwd_sale_order_df', target: 'dws_sale_order_mtd', srcField: 'order_id', tgtField: 'order_count', type: 'aggregate', logic: 'COUNT(DISTINCT order_id)', fields: '1→1' },
  FL_003: { source: 'dwd_sale_order_df', target: 'dws_sale_order_mtd', srcField: 'paid_amount', tgtField: 'mtd_paid_amount', type: 'aggregate', logic: 'SUM(paid_amount) WHERE month=current', fields: '1→1' },
  FL_004: { source: 'dwd_sale_order_df', target: 'dws_sale_order_mtd', srcField: 'order_amount, refund_amount', tgtField: 'net_order_amount', type: 'calc', logic: 'SUM(order_amount) - SUM(refund_amount)', fields: '2→1' },
  FL_005: { source: 'dwd_sale_order_df', target: 'dws_sale_order_mtd', srcField: 'mall_id', tgtField: 'mall_id', type: 'direct', logic: '直接映射，无转换', fields: '1→1' }
};

const typeLabels = {
  direct: '直接映射',
  aggregate: '聚合',
  calc: '计算',
  join: '关联',
  lookup: '查找',
  coalesce: '合并',
  concat: '拼接',
  custom: '自定义'
};

const typeColors = {
  direct: '#10B981',
  aggregate: '#3B82F6',
  calc: '#F59E0B',
  join: '#8B5CF6',
  lookup: '#EC4899',
  coalesce: '#14B8A6',
  concat: '#F97316',
  custom: '#64748B'
};

var tableLineageEdgeIds = ['TL_001','TL_002','TL_003','TL_004','TL_005','TL_006','TL_007','TL_008','TL_009'];

function nodeAnchor(container, tableName, side) {
  var node = container.querySelector('.ln-node[data-table="' + tableName + '"]');
  if (!node) return null;
  var cr = container.getBoundingClientRect();
  var nr = node.getBoundingClientRect();
  var x = side === 'out' ? nr.right - cr.left : nr.left - cr.left;
  var y = nr.top - cr.top + nr.height / 2;
  return { x: x, y: y };
}

function drawTableLineageGraph() {
  var container = document.getElementById('tableLineageGraph');
  var group = document.getElementById('tableLineagePaths');
  var svg = container && container.querySelector('.lineage-svg-bg');
  if (!container || !group || !svg) return;

  var w = container.clientWidth;
  var h = Math.max(container.clientHeight, 460);
  svg.setAttribute('viewBox', '0 0 ' + w + ' ' + h);
  group.innerHTML = '';

  tableLineageEdgeIds.forEach(function(id) {
    var data = lineageData[id];
    if (!data) return;
    var src = nodeAnchor(container, data.source, 'out');
    var tgt = nodeAnchor(container, data.target, 'in');
    if (!src || !tgt) return;
    var mx = (src.x + tgt.x) / 2;
    var d = 'M' + src.x + ',' + src.y + ' C' + mx + ',' + src.y + ' ' + mx + ',' + tgt.y + ' ' + tgt.x + ',' + tgt.y;
    var type = data.type || 'direct';
    var marker = type === 'join' ? 'tl-arrow-join' : type === 'aggregate' ? 'tl-arrow-aggregate' : 'tl-arrow-direct';

    var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('class', 'lineage-path ' + type);
    path.setAttribute('d', d);
    path.setAttribute('marker-end', 'url(#' + marker + ')');
    path.setAttribute('data-id', id);
    path.setAttribute('data-source', data.source);
    path.setAttribute('data-target', data.target);
    path.onclick = function(e) { showLineagePopup(e, id, 'tableLineagePopup'); };
    group.appendChild(path);

    var flow = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    flow.setAttribute('class', 'lineage-path-flow ' + type);
    flow.setAttribute('d', d);
    group.appendChild(flow);
  });
}

function showLineagePopup(event, id, popupId) {
  event.stopPropagation();
  const data = lineageData[id];
  if (!data) return;

  const body = document.getElementById(popupId.replace('Popup', 'PopupBody'));
  if (!body) return;

  let html = '<div class="lineage-popup-flow">';
  html += '<span class="text-mono text-sm" style="font-weight:600;">' + data.source + '</span>';
  html += '<span class="lineage-popup-arrow">→</span>';
  html += '<span class="text-mono text-sm" style="font-weight:600;">' + data.target + '</span>';
  html += '</div>';

  html += '<div class="lineage-popup-row"><span class="lineage-popup-label">转换类型</span>';
  html += '<span class="lineage-popup-value"><span class="badge" style="background:' + (typeColors[data.type] || '#64748B') + '22; color:' + (typeColors[data.type] || '#64748B') + ';">' + (typeLabels[data.type] || data.type) + '</span></span></div>';

  html += '<div class="lineage-popup-row"><span class="lineage-popup-label">转换逻辑</span>';
  html += '<span class="lineage-popup-value text-mono">' + data.logic + '</span></div>';

  html += '<div class="lineage-popup-row"><span class="lineage-popup-label">字段映射</span>';
  html += '<span class="lineage-popup-value"><strong>' + data.fields + '</strong> 字段</span></div>';

  html += '<div class="lineage-popup-row"><span class="lineage-popup-label">更新时间</span>';
  html += '<span class="lineage-popup-value text-muted">' + data.update + '</span></div>';

  if (data.fieldMappings && data.fieldMappings.length > 0) {
    html += '<div class="lineage-popup-fields">';
    html += '<div class="text-sm text-muted mb-2">字段级映射明细</div>';
    data.fieldMappings.forEach(function(fm) {
      html += '<div class="lineage-popup-field-row">';
      html += '<span style="min-width:120px;">' + fm.src + '</span>';
      html += '<span class="lineage-popup-field-arrow">→</span>';
      html += '<span style="min-width:120px;">' + fm.tgt + '</span>';
      html += '<span class="badge" style="background:' + (typeColors[fm.type] || '#64748B') + '22; color:' + (typeColors[fm.type] || '#64748B') + '; font-size:9px; margin-left:auto;">' + (typeLabels[fm.type] || fm.type) + '</span>';
      html += '</div>';
      if (fm.logic) {
        html += '<div style="font-size:10px; color:var(--text-muted); padding-left:120px; margin-bottom:4px;">' + fm.logic + '</div>';
      }
    });
    html += '</div>';
  }

  body.innerHTML = html;

  const popup = document.getElementById(popupId);
  popup.style.display = 'block';

  // Position popup near click
  const container = popup.parentElement;
  const rect = container.getBoundingClientRect();
  let x = event.clientX - rect.left + 12;
  let y = event.clientY - rect.top + 12;
  if (x + 380 > rect.width) x = rect.width - 400;
  if (y + 300 > rect.height) y = event.clientY - rect.top - 280;
  popup.style.left = x + 'px';
  popup.style.top = y + 'px';

  // Highlight this path, dim others
  highlightPathById(id);
}

function showFieldLineagePopup(event, id) {
  event.stopPropagation();
  const data = fieldLineageData[id];
  if (!data) return;

  const body = document.getElementById('fieldLineagePopupBody');
  if (!body) return;

  let html = '<div class="lineage-popup-flow">';
  html += '<span class="text-mono text-sm" style="font-weight:600;">' + data.srcField + '</span>';
  html += '<span class="lineage-popup-arrow">→</span>';
  html += '<span class="text-mono text-sm" style="font-weight:600;">' + data.tgtField + '</span>';
  html += '</div>';

  html += '<div class="lineage-popup-row"><span class="lineage-popup-label">源表</span>';
  html += '<span class="lineage-popup-value text-mono">' + data.source + '</span></div>';

  html += '<div class="lineage-popup-row"><span class="lineage-popup-label">目标表</span>';
  html += '<span class="lineage-popup-value text-mono">' + data.target + '</span></div>';

  html += '<div class="lineage-popup-row"><span class="lineage-popup-label">转换类型</span>';
  html += '<span class="lineage-popup-value"><span class="badge" style="background:' + (typeColors[data.type] || '#64748B') + '22; color:' + (typeColors[data.type] || '#64748B') + ';">' + (typeLabels[data.type] || data.type) + '</span></span></div>';

  html += '<div class="lineage-popup-row"><span class="lineage-popup-label">转换逻辑</span>';
  html += '<span class="lineage-popup-value text-mono">' + data.logic + '</span></div>';

  html += '<div class="lineage-popup-row"><span class="lineage-popup-label">字段映射</span>';
  html += '<span class="lineage-popup-value">' + data.fields + '</span></div>';

  body.innerHTML = html;

  const popup = document.getElementById('fieldLineagePopup');
  popup.style.display = 'block';

  const container = popup.parentElement;
  const rect = container.getBoundingClientRect();
  let x = event.clientX - rect.left + 12;
  let y = event.clientY - rect.top + 12;
  if (x + 360 > rect.width) x = rect.width - 380;
  if (y + 250 > rect.height) y = event.clientY - rect.top - 230;
  popup.style.left = x + 'px';
  popup.style.top = y + 'px';

  highlightFieldPathById(id);
}

function closeLineagePopup(popupId) {
  document.getElementById(popupId).style.display = 'none';
  // Reset path highlights
  resetPathHighlights();
}

function highlightPathById(id) {
  const svg = document.querySelector('#tableLineageGraph svg');
  if (!svg) return;
  svg.querySelectorAll('.lineage-path').forEach(function(p) {
    if (p.getAttribute('data-id') === id) {
      p.classList.add('active');
      p.classList.remove('dimmed');
    } else {
      p.classList.add('dimmed');
      p.classList.remove('active');
    }
  });
}

function highlightFieldPathById(id) {
  const svg = document.querySelector('#fieldLineageGraph svg');
  if (!svg) return;
  svg.querySelectorAll('.lineage-path').forEach(function(p) {
    if (p.getAttribute('data-id') === id) {
      p.classList.add('active');
      p.classList.remove('dimmed');
    } else {
      p.classList.add('dimmed');
      p.classList.remove('active');
    }
  });
}

function resetPathHighlights() {
  document.querySelectorAll('.lineage-path').forEach(function(p) {
    p.classList.remove('active');
    p.classList.remove('dimmed');
  });
  document.querySelectorAll('.ln-node').forEach(function(n) {
    n.classList.remove('highlight');
  });
  document.querySelectorAll('.fl-field').forEach(function(f) {
    f.classList.remove('active');
  });
}

function highlightTablePaths(element, tableName) {
  // Toggle highlight
  const isHighlighted = element.classList.contains('highlight');
  resetPathHighlights();
  if (isHighlighted) return;

  element.classList.add('highlight');
  const svg = document.querySelector('#tableLineageGraph svg');
  if (!svg) return;
  svg.querySelectorAll('.lineage-path').forEach(function(p) {
    const src = p.getAttribute('data-source');
    const tgt = p.getAttribute('data-target');
    if (src === tableName || tgt === tableName) {
      p.classList.add('active');
      p.classList.remove('dimmed');
    } else {
      p.classList.add('dimmed');
    }
  });
}

function highlightFieldPath(element, pathId) {
  // Toggle
  const isActive = element.classList.contains('active');
  resetPathHighlights();
  if (isActive) return;

  element.classList.add('active');

  // Also highlight matching field on the other side
  const data = fieldLineageData[pathId];
  if (data) {
    document.querySelectorAll('.fl-field').forEach(function(f) {
      if (f.getAttribute('data-field') === data.srcField || f.getAttribute('data-field') === data.tgtField) {
        f.classList.add('active');
      }
    });
  }

  // Use simulated event position for popup
  const rect = element.getBoundingClientRect();
  const containerRect = element.closest('.field-lineage-container').getBoundingClientRect();
  const fakeEvent = {
    clientX: rect.left + rect.width / 2,
    clientY: rect.top + rect.height / 2,
    stopPropagation: function() {}
  };
  // Adjust to be relative to container
  showFieldLineagePopup({
    clientX: fakeEvent.clientX,
    clientY: fakeEvent.clientY,
    stopPropagation: function() {}
  }, pathId);
}

function toggleLineageAnimation(btn) {
  const flows = document.querySelectorAll('.lineage-path-flow');
  const isPaused = flows.length > 0 && flows[0].classList.contains('paused');
  flows.forEach(function(f) {
    if (isPaused) {
      f.classList.remove('paused');
    } else {
      f.classList.add('paused');
    }
  });
  btn.textContent = isPaused ? '⏸ 暂停动画' : '▶ 播放动画';
}

// Close popup when clicking outside
document.addEventListener('click', function(e) {
  if (!e.target.closest('.lineage-popup') && !e.target.closest('.lineage-path') && !e.target.closest('.ln-node') && !e.target.closest('.fl-field')) {
    document.querySelectorAll('.lineage-popup').forEach(function(p) {
      p.style.display = 'none';
    });
    resetPathHighlights();
  }
});

// ========== End Lineage Graph Interactions ==========
document.addEventListener('DOMContentLoaded', function() {
  drawTableLineageGraph();
});
