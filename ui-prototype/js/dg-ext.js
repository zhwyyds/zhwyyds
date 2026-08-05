/**
 * 模型评审 / 血缘 / 批量修饰词 — API 扩展
 */
(function (global) {
  function esc(s) {
    if (s == null) return '';
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/"/g, '&quot;');
  }

  function apiBase() {
    return (global.DG && global.DG.API_BASE) || global.DG_API_BASE || '';
  }

  function fetchJson(path, options) {
    if (global.DG && global.DG.fetchJson) return global.DG.fetchJson(path, options);
    return fetch(apiBase() + path, options).then(function (res) {
      if (!res.ok) throw new Error(path + ' ' + res.status);
      return res.json();
    });
  }

  function renderReviewStats(metrics) {
    metrics = metrics || [];
    var pending = 0;
    var approved = 0;
    var total = metrics.length;
    metrics.forEach(function (m) {
      if (m.review_status === 'approved') approved += 1;
      else if (m.review_status !== 'offline') pending += 1;
    });
    var rate = total ? Math.round((approved / total) * 1000) / 10 : 0;
    var elRate = document.getElementById('review-stat-rate');
    var elPending = document.getElementById('review-stat-pending');
    var elConflict = document.getElementById('review-stat-conflict');
    var elAuto = document.getElementById('review-stat-auto');
    if (elRate) elRate.innerHTML = rate + '<span class="unit">%</span>';
    if (elPending) elPending.innerHTML = String(pending) + '<span class="unit">个</span>';
    if (elConflict) elConflict.innerHTML = '0<span class="unit">个</span>';
    if (elAuto) elAuto.innerHTML = String(approved) + '<span class="unit">个</span>';
  }

  function renderReviewQueue(metrics) {
    var host = document.getElementById('reviewQueueHost');
    if (!host) return;
    var pending = (metrics || []).filter(function (m) {
      return m.review_status !== 'approved' && m.review_status !== 'offline';
    });
    var badge = document.getElementById('reviewQueueBadge');
    if (badge) badge.textContent = String(pending.length);
    if (!pending.length) {
      host.innerHTML = '<div class="text-sm text-muted" style="padding:16px;">暂无待评审指标</div>';
      return;
    }
    host.innerHTML = pending
      .map(function (m) {
        return (
          '<div class="review-queue-item issue-item" style="cursor:pointer;padding:12px 16px;border-bottom:1px solid var(--border);" onclick="submitReview(\'' +
          esc(m.metric_id) +
          '\')">' +
          '<span class="issue-priority p1">待审</span>' +
          '<div class="issue-content">' +
          '<div class="issue-title text-13">' +
          esc(m.metric_cn) +
          '</div>' +
          '<div class="issue-desc text-xs text-muted">' +
          esc(m.metric_id) +
          ' · ' +
          esc(m.metric_en) +
          '</div></div></div>'
        );
      })
      .join('');
  }

  function renderReviewDetail(doc) {
    var host = document.getElementById('reviewDetailHost');
    if (!host || !doc || !doc.items || !doc.items.length) return;
    var item = doc.items[0];
    var models = item.model_reviews || [];
    var cards = models
      .map(function (mr) {
        var avg = Math.round(((mr.naming_score + mr.caliber_score) / 2) * 20);
        var pass = mr.naming_score >= 4 && mr.caliber_score >= 4;
        return (
          '<div class="model-card">' +
          '<div class="model-card-header"><span class="model-name">' +
          esc(mr.model) +
          '</span><span class="badge badge-' +
          (pass ? 'pass' : 'warn') +
          '">' +
          (pass ? '通过' : '需修改') +
          '</span></div>' +
          '<div class="model-score" style="color:var(--' +
          (pass ? 'success' : 'warning') +
          ')">' +
          avg +
          '</div>' +
          '<div class="text-sm text-muted mb-2">命名' +
          mr.naming_score +
          '/5 · 口径' +
          mr.caliber_score +
          '/5</div>' +
          '<div class="text-sm">' +
          esc(mr.suggestions || '—') +
          '</div></div>'
        );
      })
      .join('');
    var decision = item.final_decision || {};
    host.innerHTML =
      '<div class="flex align-center justify-between mb-3">' +
      '<div><span class="text-lg text-bold">' +
      esc(item.metric_id) +
      '</span><span class="text-mono text-sm ml-3">' +
      esc(item.metric_en) +
      '</span></div>' +
      '<span class="badge badge-' +
      (decision.approved ? 'pass' : 'warn') +
      '">' +
      (decision.approved ? '已通过' : '待确认') +
      '</span></div>' +
      '<div class="grid-3 mb-4">' +
      cards +
      '</div>' +
      '<div class="callout info">🤝 <div><strong>评审批次：</strong>' +
      esc(doc.review_id) +
      ' · 模型：' +
      esc((doc.models_used || []).join(', ')) +
      '</div></div>';
    var title = document.getElementById('reviewDetailTitle');
    if (title) title.textContent = '指标评审 · ' + item.metric_id;
  }

  function loadReviewExtras(metrics) {
    renderReviewStats(metrics);
    renderReviewQueue(metrics);
    return fetchJson('/api/metric-reviews/latest?domain=sale').then(
      function (doc) {
        renderReviewDetail(doc);
        global.__DG_LAST_METRIC_REVIEW__ = doc;
      },
      function () {
        /* 尚无评审文件 */
      }
    );
  }

  function loadModifierRules() {
    return fetchJson('/api/modifier-rules').then(function (rows) {
      global.__DG_MODIFIER_RULES__ = rows;
      var host = document.getElementById('batchModifierList');
      if (!host || !rows.length) return rows;
      host.innerHTML = rows
        .map(function (r) {
          return (
            '<div class="checkbox-item" data-mod-id="' +
            esc(r.modifier_id) +
            '" onclick="this.classList.toggle(\'checked\'); refreshBatchPreview();">' +
            '<div class="checkbox-box"></div>' +
            '<span>' +
            esc(r.modifier_cn) +
            '(' +
            esc(r.modifier_abbr) +
            ')</span></div>'
          );
        })
        .join('');
      return rows;
    });
  }

  function loadLineageMeta() {
    return fetchJson('/api/lineage?domain=sale').then(function (payload) {
      global.__DG_LINEAGE_SALE__ = payload;
      var el = document.getElementById('lineageMetaLabel');
      if (el) {
        el.textContent =
          '来源: ' +
          (payload.source_project || '—') +
          ' · 更新: ' +
          (payload.parsed_at || '—');
      }
      return payload;
    });
  }

  function exportMetricsCsv() {
    window.open(apiBase() + '/api/metrics/export', '_blank');
  }

  global.DGExt = {
    loadReviewExtras: loadReviewExtras,
    loadModifierRules: loadModifierRules,
    loadLineageMeta: loadLineageMeta,
    exportMetricsCsv: exportMetricsCsv,
    renderReviewDetail: renderReviewDetail
  };

  global.exportMetricsCsv = exportMetricsCsv;
})(window);
