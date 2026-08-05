/**
 * 指标库 — 规范表下方「异议」分区 + 「AI 评审」折叠（接 API）
 */
(function (global) {
  var FIELD_LABEL = {
    caliber_desc: '口径描述',
    formula: '计算公式',
    metric_en: '英文命名',
    other: '其他'
  };

  function esc(s) {
    if (s == null) return '';
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/"/g, '&quot;');
  }

  function fetchJson(path, options) {
    if (global.DG && global.DG.fetchJson) return global.DG.fetchJson(path, options);
    var base = (global.DG && global.DG.API_BASE) || '';
    return fetch(base + path, options).then(function (res) {
      if (!res.ok) throw new Error(path + ' ' + res.status);
      return res.json();
    });
  }

  function currentMetricRow() {
    var cards = global.metricCards;
    var idx = global.metricCardIndex;
    if (!cards || idx == null || !cards[idx]) return null;
    return cards[idx]._apiRow || null;
  }

  function currentMetricId() {
    var m = currentMetricRow();
    return m ? m.metric_id : null;
  }

  function parseObjectionNote(note) {
    if (!note) return { field: 'other', text: '' };
    var idx = note.indexOf('：');
    if (idx < 0) idx = note.indexOf(':');
    if (idx > 0) {
      var prefix = note.slice(0, idx).trim();
      var text = note.slice(idx + 1).trim();
      var field = 'other';
      Object.keys(FIELD_LABEL).forEach(function (k) {
        if (FIELD_LABEL[k] === prefix || k === prefix) field = k;
      });
      return { field: field, text: text };
    }
    return { field: 'other', text: note };
  }

  function renderDisputeList(row) {
    var host = document.getElementById('metricDisputeList');
    var countEl = document.getElementById('libDisputeCount');
    var open = row && row.objection_status === 'open' && (row.objection_note || '').trim();
    if (countEl) {
      if (open) {
        countEl.style.display = '';
        countEl.textContent = '1 条';
      } else {
        countEl.style.display = 'none';
      }
    }
    if (!host) return;
    if (!row || row.objection_status !== 'open' || !(row.objection_note || '').trim()) {
      host.innerHTML = '<div class="text-sm text-muted">暂无异议</div>';
      return;
    }
    var parsed = parseObjectionNote(row.objection_note);
    var fieldLabel = FIELD_LABEL[parsed.field] || parsed.field || '其他';
    host.innerHTML =
      '<div class="dispute-item">' +
      '<span class="dispute-item-status open">待处理</span>' +
      '<div class="dispute-item-content">' +
      '<div class="dispute-item-field">异议字段 · ' +
      esc(fieldLabel) +
      '</div>' +
      '<div class="dispute-item-desc">' +
      esc(parsed.text || row.objection_note) +
      '</div>' +
      '<div class="dispute-item-meta">指标 ' +
      esc(row.metric_id) +
      ' · 写回 metrics CSV</div></div>' +
      '<div class="dispute-item-actions">' +
      '<button type="button" class="btn btn-sm" onclick="toggleDisputeForm(\'' +
      esc(parsed.field) +
      '\')">编辑</button>' +
      '<button type="button" class="btn btn-sm" onclick="clearMetricObjection()">关闭</button>' +
      '</div></div>';
  }

  function renderReviewPanelHtml(doc) {
    if (!doc || !doc.item) {
      return '<div class="text-sm text-muted" style="padding:8px 0;">暂无评审记录，点击下方「发起/刷新评审」。</div>';
    }
    var item = doc.item;
    var models = item.model_reviews || [];
    var cards = models
      .map(function (mr) {
        var pass = mr.naming_score >= 4 && mr.caliber_score >= 4;
        return (
          '<div class="ai-review-card">' +
          '<div class="ai-review-card-header">' +
          '<span class="ai-review-model-name">' +
          esc(mr.model) +
          '</span>' +
          '<span class="badge badge-' +
          (pass ? 'pass' : 'warn') +
          '">' +
          (pass ? '通过' : '需修改') +
          '</span></div>' +
          '<div class="ai-review-card-body">' +
          '<div class="ai-review-score">' +
          Math.round(((mr.naming_score + mr.caliber_score) / 2) * 20) +
          '</div>' +
          '<div class="text-xs text-muted">命名 ' +
          mr.naming_score +
          '/5 · 口径 ' +
          mr.caliber_score +
          '/5</div>' +
          (mr.caliber_issues && mr.caliber_issues.length
            ? '<div class="ai-review-issues">' +
              mr.caliber_issues
                .map(function (i) {
                  return '<div class="ai-review-issue">' + esc(i) + '</div>';
                })
                .join('') +
              '</div>'
            : '') +
          '<div class="ai-review-opinion">' +
          esc(mr.suggestions || '—') +
          '</div></div></div>'
        );
      })
      .join('');
    var decision = item.final_decision || {};
    return (
      '<div class="ai-review-status mb-3">' +
      '<div class="ai-review-status-item"><span class="text-xs text-muted">评审批次</span><span class="text-sm text-bold">' +
      esc(doc.review_id || '—') +
      '</span></div>' +
      '<div class="ai-review-status-item"><span class="text-xs text-muted">时间</span><span class="text-sm">' +
      esc(doc.created_at || '—') +
      '</span></div>' +
      '<div class="ai-review-status-item"><span class="text-xs text-muted">结论</span><span class="badge badge-' +
      (decision.approved ? 'pass' : 'warn') +
      '">' +
      (decision.approved ? '通过' : decision.review_status || '待确认') +
      '</span></div></div>' +
      '<div class="ai-review-models">' +
      cards +
      '</div>'
    );
  }

  function updateReviewSummary(doc) {
    var el = document.getElementById('metricAiReviewSummary');
    if (!el) return;
    if (!doc || !doc.item) {
      el.textContent = '暂无多模型评审';
      return;
    }
    var decision = doc.item.final_decision || {};
    el.textContent = decision.approved ? '评审已通过' : '评审待确认';
    var models = doc.item.model_reviews || [];
    if (models.length) {
      var sum = 0;
      models.forEach(function (mr) {
        sum += ((mr.naming_score + mr.caliber_score) / 2) * 20;
      });
      var avg = Math.round(sum / models.length);
      var circle = document.getElementById('libScoreCircle');
      var label = document.getElementById('libAiScoreLabel');
      if (circle) circle.textContent = String(avg);
      if (label) {
        var g = avg >= 90 ? 'S' : avg >= 80 ? 'A' : avg >= 70 ? 'B' : 'C';
        label.textContent = avg + ' 分 · ' + g + ' 级';
        circle.className = 'score-circle-mini ' + g.toLowerCase();
      }
    }
  }

  function loadReviewForCurrentMetric() {
    var host = document.getElementById('metricReviewPanelHost');
    if (!host) return Promise.resolve();
    var id = currentMetricId();
    if (!id) {
      host.innerHTML = '<div class="text-sm text-muted">请选择指标</div>';
      updateReviewSummary(null);
      return Promise.resolve();
    }
    host.innerHTML = '<div class="text-sm text-muted">加载评审明细…</div>';
    return fetchJson('/api/metrics/' + encodeURIComponent(id) + '/review/latest').then(
      function (doc) {
        host.innerHTML = renderReviewPanelHtml(doc);
        global.__DG_METRIC_REVIEW__ = doc;
        updateReviewSummary(doc);
      },
      function () {
        host.innerHTML = renderReviewPanelHtml(null);
        updateReviewSummary(null);
      }
    );
  }

  function refreshLibraryGovernance() {
    var row = currentMetricRow();
    renderDisputeList(row);
    loadReviewForCurrentMetric();
  }

  function toggleDisputeForm(field) {
    var form = document.getElementById('disputeForm');
    if (!form) return;
    if (field) {
      var select = document.getElementById('disputeFieldSelect') || form.querySelector('select');
      if (select) select.value = field;
    }
    var row = currentMetricRow();
    var ta = document.getElementById('disputeNoteInput');
    var selectEl = document.getElementById('disputeFieldSelect') || form.querySelector('select');
    if (ta && row && row.objection_note) {
      var parsed = parseObjectionNote(row.objection_note);
      if (selectEl && parsed.field) selectEl.value = parsed.field;
      ta.value = parsed.text || row.objection_note;
    }
    form.classList.toggle('show');
  }

  function submitDispute() {
    var id = currentMetricId();
    if (!id) {
      alert('请先选择指标');
      return;
    }
    var select = document.getElementById('disputeFieldSelect');
    var ta = document.getElementById('disputeNoteInput');
    var field = select ? select.value : 'other';
    var note = ta ? ta.value.trim() : '';
    if (!note) {
      alert('请填写异议说明');
      return;
    }
    var label = FIELD_LABEL[field] || field;
    fetchJson('/api/metrics/' + encodeURIComponent(id), {
      method: 'PUT',
      body: JSON.stringify({
        objection_status: 'open',
        objection_note: label + '：' + note
      })
    })
      .then(function () {
        var form = document.getElementById('disputeForm');
        if (form) form.classList.remove('show');
        if (global.DG && global.DG.loadAll) return global.DG.loadAll(false);
      })
      .then(function () {
        alert('异议已提交并写入指标记录');
      })
      .catch(function (e) {
        alert('异议提交失败: ' + e.message);
      });
  }

  function clearObjection() {
    var id = currentMetricId();
    if (!id) return;
    fetchJson('/api/metrics/' + encodeURIComponent(id), {
      method: 'PUT',
      body: JSON.stringify({ objection_status: 'resolved', objection_note: '' })
    })
      .then(function () {
        if (global.DG && global.DG.loadAll) return global.DG.loadAll(false);
      })
      .catch(function (e) {
        alert('操作失败: ' + e.message);
      });
  }

  global.MetricLibrary = {
    refresh: refreshLibraryGovernance,
    loadReviewForCurrentMetric: loadReviewForCurrentMetric
  };

  global.toggleDisputeForm = toggleDisputeForm;
  global.submitDispute = submitDispute;
  global.clearMetricObjection = clearObjection;
})(window);
