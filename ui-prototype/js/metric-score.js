/**
 * 指标质量评分明细 + 多模型汇总 + 版本发布控制（接 FastAPI）
 * 依赖：DG.fetchJson（governance-api.js）
 * 数据来源：
 *   GET /api/metrics/{id}/score         -> ScoreResult（六维度 + 改进建议 + model_reviews）
 *   POST /api/metrics/{id}/score/refresh-> 重新评分并落盘
 *   GET /api/domains/{domain}/releases   -> 发布历史
 *   POST /api/domains/{domain}/publish   -> 按域批量发布（版本自增）
 */
(function (global) {
  function esc(s) {
    if (s == null) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
  }

  function fetchJson(path, options) {
    if (global.DG && global.DG.fetchJson) return global.DG.fetchJson(path, options);
    var base = (global.DG && global.DG.API_BASE) || '';
    return fetch(base + path, options).then(function (res) {
      if (!res.ok) throw new Error(path + ' ' + res.status);
      return res.json();
    });
  }

  function currentMetric() {
    var cards = global.metricCards;
    var idx = global.metricCardIndex;
    if (!cards || idx == null || !cards[idx]) return null;
    return cards[idx];
  }

  function currentMetricId() {
    var m = currentMetric();
    return m ? m.id : null;
  }

  function currentDomain() {
    var m = currentMetric();
    if (!m) return '';
    return m.domain || (m._apiRow && (m._apiRow.domain_code || m._apiRow.domain)) || '';
  }

  function gradeClass(g) {
    var x = (g || '').toLowerCase();
    return x === 's' || x === 'a' || x === 'b' || x === 'c' || x === 'd' ? x : 'd';
  }

  function pct(points, max) {
    if (!max) return 0;
    return Math.min(100, Math.round((points / max) * 1000) / 10);
  }

  function statusBadgeClass(status) {
    if (status === 'pass') return 'badge-pass';
    if (status === 'warn') return 'badge-warn';
    if (status === 'fail') return 'badge-fail';
    return 'badge-neutral';
  }

  function statusIcon(status) {
    if (status === 'pass') return '✓';
    if (status === 'fail') return '✕';
    return '!';
  }

  // ---------- 评分加载与渲染 ----------
  function loadForCurrentMetric() {
    var id = currentMetricId();
    if (!id) return Promise.resolve();
    setGradeBadge('—');
    return fetchJson('/api/metrics/' + encodeURIComponent(id) + '/score').then(
      function (res) { renderScore(res); },
      function () { renderScore(null); }
    );
  }

  function setGradeBadge(grade, total) {
    var badge = document.getElementById('libMetricGrade');
    var label = document.getElementById('libAiScoreLabel');
    var circle = document.getElementById('libScoreCircle');
    var trend = document.getElementById('libScoreTrend');
    if (badge) {
      badge.className = 'badge badge-' + (grade && grade !== '—' ? gradeClass(grade) : 'neutral');
      badge.textContent = grade || '—';
    }
    if (label) {
      label.textContent = (total != null ? total + ' 分 · ' : '') + (grade || '—') + ' 级';
    }
    if (circle) {
      circle.textContent = total != null ? String(total) : '—';
      circle.className = 'score-circle-mini ' + (grade && grade !== '—' ? gradeClass(grade) : '');
    }
    if (trend && total != null) {
      trend.textContent = '六维度质量评分 · 满分100';
    }
  }

  function renderScore(res) {
    if (!res || !res.dimensions) {
      setGradeBadge('—');
      var dh = document.getElementById('scoreDimensionsHost');
      if (dh) dh.innerHTML = '<div class="text-sm text-muted">尚未评分，点击右上角「重新评分」生成六维度明细。</div>';
      var ih = document.getElementById('scoreIssuesHost');
      if (ih) ih.innerHTML = '<div class="text-sm text-muted">暂无待整改项</div>';
      var mh = document.getElementById('metricScoreModelReviews');
      if (mh) mh.innerHTML = '';
      return;
    }

    setGradeBadge(res.grade, Math.round(res.total_score));

    // 六维度明细
    var dh = document.getElementById('scoreDimensionsHost');
    if (dh) {
      dh.innerHTML = res.dimensions.map(function (dim) {
        var items = (dim.items || []).map(function (it) {
          return (
            '<div class="score-dim-item">' +
            '<span class="score-dim-item-status ' + statusBadgeClass(it.status) + '">' + statusIcon(it.status) + '</span>' +
            '<div class="score-dim-item-body">' +
            '<div class="score-dim-item-name">' + esc(it.item) +
            '<span class="score-dim-item-score">' + it.score + '/' + it.max_score + '</span></div>' +
            (it.reason ? '<div class="score-dim-item-reason">' + esc(it.reason) + '</div>' : '') +
            '</div></div>'
          );
        }).join('');
        var p = pct(dim.score, dim.max_score);
        var barColor = dim.status === 'fail'
          ? 'linear-gradient(90deg,#F87171,#E11D48)'
          : dim.status === 'warn' ? 'linear-gradient(90deg,#FBBF24,#F59E0B)'
          : 'linear-gradient(90deg,#22C55E,#14B8A6)';
        return (
          '<div class="score-dim">' +
          '<div class="score-dim-head">' +
          '<span class="score-dim-name">' + esc(dim.dim_name) + '</span>' +
          '<span class="score-dim-val ' + statusBadgeClass(dim.status) + '">' + dim.score + ' / ' + dim.max_score + '</span>' +
          '</div>' +
          '<div class="score-bar"><div class="score-bar-fill" style="width:' + p + '%;background:' + barColor + '"></div></div>' +
          (items ? '<div class="score-dim-items">' + items + '</div>' : '') +
          '</div>'
        );
      }).join('');
    }

    // 改进建议
    var ih = document.getElementById('scoreIssuesHost');
    var countEl = document.getElementById('scoreIssueCount');
    if (ih) {
      var issues = res.issues || [];
      if (countEl) countEl.textContent = String(issues.length);
      if (!issues.length) {
        ih.innerHTML = '<div class="text-sm text-muted">✅ 暂无待整改项</div>';
      } else {
        ih.innerHTML = issues.map(function (iss) {
          var pri = (iss.priority || 'P2').toLowerCase();
          return (
            '<div class="issue-item warn-tone">' +
            '<span class="issue-priority ' + pri + '">' + esc(iss.priority || 'P2') + '</span>' +
            '<div class="issue-content">' +
            '<div class="issue-title">' + esc(iss.issue) + '</div>' +
            (iss.suggestion ? '<div class="issue-desc">建议：' + esc(iss.suggestion) + '</div>' : '') +
            (iss.fix_action ? '<div class="issue-desc" style="color:var(--primary)">操作：' + esc(iss.fix_action) + '</div>' : '') +
            '</div></div>'
          );
        }).join('');
      }
    }

    // 多模型汇总评审
    var mh = document.getElementById('metricScoreModelReviews');
    if (mh) {
      var mrs = res.model_reviews || [];
      if (!mrs.length) {
        mh.innerHTML = '<div class="text-sm text-muted">暂无多模型评审明细（请先在「模型评审页」发起评审）。</div>';
      } else {
        mh.innerHTML = mrs.map(function (mr) {
          var n = mr.naming_score != null ? mr.naming_score : '—';
          var c = mr.caliber_score != null ? mr.caliber_score : '—';
          var avg = (typeof n === 'number' && typeof c === 'number') ? Math.round(((n + c) / 2) * 20) : '—';
          return (
            '<div class="ai-review-card">' +
            '<div class="ai-review-card-header"><span class="ai-review-model-name">' + esc(mr.model || '模型') + '</span>' +
            (avg !== '—' ? '<span class="badge badge-info">' + avg + ' 分</span>' : '') + '</div>' +
            '<div class="ai-review-card-body">' +
            '<div class="text-xs text-muted">命名 ' + n + '/5 · 口径 ' + c + '/5</div>' +
            (mr.suggestions ? '<div class="ai-review-opinion">' + esc(mr.suggestions) + '</div>' : '') +
            '</div></div>'
          );
        }).join('');
      }
    }
  }

  function refreshCurrent() {
    var id = currentMetricId();
    if (!id) { toast('请先选择指标'); return; }
    var btn = document.getElementById('scoreRefreshBtn');
    if (btn) { btn.disabled = true; btn.textContent = '评分中…'; }
    fetchJson('/api/metrics/' + encodeURIComponent(id) + '/score/refresh', { method: 'POST' })
      .then(function (res) {
        renderScore(res);
        if (global.DG && global.DG.loadAll) global.DG.loadAll(false);
      })
      .catch(function (e) { toast('评分失败: ' + e.message); })
      .then(function () {
        if (btn) { btn.disabled = false; btn.innerHTML = '&#10227; 重新评分'; }
      });
  }

  // ---------- 版本与发布 ----------
  function countApprovedInDomain(domain) {
    var metrics = global.__DG_METRICS__ || global.__DG_METRIC_ROWS__ || [];
    var n = 0;
    metrics.forEach(function (m) {
      if ((m.domain_code || m.domain) === domain && m.review_status === 'approved') n++;
    });
    return n;
  }

  function loadVersionForCurrentMetric() {
    var domain = currentDomain();
    var historyHost = document.getElementById('metricReleaseHistory');
    var hint = document.getElementById('publishDomainHint');
    var btn = document.getElementById('publishDomainBtn');
    if (historyHost) historyHost.innerHTML = '<div class="text-sm text-muted">加载发布历史…</div>';
    if (!domain) {
      if (historyHost) historyHost.innerHTML = '<div class="text-sm text-muted">无法确定指标所属主题域</div>';
      return Promise.resolve();
    }
    return fetchJson('/api/domains/' + encodeURIComponent(domain) + '/releases').then(
      function (releases) {
        renderReleases(releases || []);
        var approved = countApprovedInDomain(domain);
        if (hint) {
          hint.textContent = approved > 0
            ? '本域 ' + approved + ' 个已通过指标将随发布获得同一版本'
            : '本域暂无已通过（approved）指标，暂不可发布';
        }
        if (btn) btn.disabled = (approved === 0);
      },
      function () {
        if (historyHost) historyHost.innerHTML = '<div class="text-sm text-muted">发布历史加载失败</div>';
      }
    );
  }

  function renderReleases(releases) {
    var host = document.getElementById('metricReleaseHistory');
    if (!host) return;
    if (!releases.length) {
      host.innerHTML = '<div class="text-sm text-muted">暂无发布记录</div>';
      return;
    }
    host.innerHTML = releases.slice().reverse().map(function (r) {
      var note = r.note ? esc(r.note) : '';
      return (
        '<div class="release-item">' +
        '<div class="release-item-head">' +
        '<span class="badge badge-pass">' + esc(r.version_label || r.version || '—') + '</span>' +
        '<span class="text-xs text-muted">' + esc(r.released_at || '') + '</span>' +
        '</div>' +
        '<div class="release-item-meta">发布人 ' + esc(r.released_by || 'system') + ' · ' + (r.metric_ids ? r.metric_ids.length : 0) + ' 个指标</div>' +
        (note ? '<div class="release-item-note">' + note + '</div>' : '') +
        '</div>'
      );
    }).join('');
  }

  function publishCurrentDomain() {
    var domain = currentDomain();
    if (!domain) { toast('无法确定主题域'); return; }
    var approved = countApprovedInDomain(domain);
    if (approved === 0) { toast('本域没有已通过（approved）的指标，无法发布'); return; }
    if (!confirm('确认发布主题域「' + domain + '」？\n将把 ' + approved + ' 个已通过指标统一升级到下一个版本并写入发布历史。')) return;
    var btn = document.getElementById('publishDomainBtn');
    if (btn) { btn.disabled = true; btn.textContent = '发布中…'; }
    fetchJson('/api/domains/' + encodeURIComponent(domain) + '/publish', {
      method: 'POST',
      body: JSON.stringify({ note: '前端一键发布' })
    })
      .then(function (res) {
        toast('发布成功：' + (res.version_label || res.version || '') + '，共 ' + (res.metric_ids ? res.metric_ids.length : 0) + ' 个指标');
        if (global.DG && global.DG.loadAll) return global.DG.loadAll(false).then(function () { return res; });
        return res;
      })
      .then(function () {
        var m = currentMetric();
        if (m && m._apiRow) {
          var badge = document.getElementById('libVersionChip');
          if (badge) { badge.className = 'badge badge-pass'; badge.textContent = (m._apiRow.version || '已发布'); }
        }
        loadVersionForCurrentMetric();
      })
      .catch(function (e) { toast('发布失败: ' + e.message); })
      .then(function () {
        if (btn) { btn.disabled = false; btn.innerHTML = '&#128640; 发布本域'; }
      });
  }

  global.MetricScore = {
    loadForCurrentMetric: loadForCurrentMetric,
    refreshCurrent: refreshCurrent,
    loadVersionForCurrentMetric: loadVersionForCurrentMetric,
    publishCurrentDomain: publishCurrentDomain
  };
})(window);
