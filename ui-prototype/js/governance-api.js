/**
 * 连接本地 FastAPI（data-governance serve）与 UI 原型。
 * 同源部署时 API_BASE 留空；file:// 打开时可设为 http://127.0.0.1:8765
 * 分离部署（静态页面 8080 + API 8765）：自动探测——同源无 API 时回退到 8765
 */
(function (global) {
  var API_BASE = global.DG_API_BASE || '';
  var API_FALLBACK = global.DG_API_FALLBACK || 'http://127.0.0.1:8765';
  var _baseProbe = null;

  // 探测 API 地址（H8）：同源 /health 不可达 → 回退 8765；结果缓存，避免重复探测
  function resolveBase() {
    if (API_BASE) return Promise.resolve(API_BASE);
    if (!_baseProbe) {
      _baseProbe = fetch('/health', { method: 'GET' })
        .then(function (r) { return r.ok ? '' : (function () { throw new Error('no-api'); })(); })
        .catch(function () {
          API_BASE = API_FALLBACK;
          global.DG_API_BASE = API_BASE;
          return API_BASE;
        });
    }
    return _baseProbe;
  }

  function url(path) {
    return API_BASE + path;
  }

  var ROOT_TYPE_LABEL = { noun: '名词', verb: '动词', adj: '形容词', unit: '单位', time: '时间' };
  var PROGRESS_COLOR = {
    '命名规范率': 'blue',
    '口径覆盖率': 'teal',
    '词根覆盖率': 'green',
    '血缘覆盖率': 'purple',
    '评审完成率': 'amber'
  };

  function fetchJson(path, options) {
    options = options || {};
    options.headers = options.headers || {};
    if (options.body && !options.headers['Content-Type']) {
      options.headers['Content-Type'] = 'application/json';
    }
    return resolveBase().then(function (base) {
      return fetch(base + path, options).then(function (res) {
        if (!res.ok) throw new Error(path + ' ' + res.status);
        return res.json();
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

  function dimByName(report, name) {
    if (!report || !report.dimensions) return null;
    for (var i = 0; i < report.dimensions.length; i++) {
      if (report.dimensions[i].name === name) return report.dimensions[i];
    }
    return null;
  }

  function pct(points, max) {
    if (!max) return 0;
    return Math.min(100, Math.round((points / max) * 1000) / 10);
  }

  function setStatValue(el, html) {
    if (el) el.innerHTML = html;
  }

  function updateProgressRow(labelText, percent) {
    var container = document.querySelector('#page-dashboard .grid-2-1 .card-body');
    if (!container) return;
    var all = container.children;
    for (var i = 0; i < all.length; i++) {
      var block = all[i];
      var label = block.querySelector('.text-sm.text-muted');
      if (label && label.textContent.indexOf(labelText) === 0) {
        var bold = block.querySelector('.text-bold');
        if (bold) bold.textContent = percent.toFixed(1) + '%';
        var fill = block.querySelector('.progress-fill');
        if (fill) {
          fill.style.width = percent + '%';
          var tone = PROGRESS_COLOR[labelText] || 'blue';
          fill.className = 'progress-fill ' + tone;
        }
        return;
      }
    }
  }

  function computeCaliberConflicts(metrics) {
    var byEn = {};
    metrics.forEach(function (m) {
      var en = (m.metric_en || '').trim();
      if (!en) return;
      if (!byEn[en]) byEn[en] = {};
      var cal = (m.caliber_desc || '').trim() || '（空）';
      byEn[en][cal] = true;
    });
    var homonyms = [];
    Object.keys(byEn).forEach(function (en) {
      var descs = Object.keys(byEn[en]);
      if (descs.length > 1) {
        homonyms.push({ metric_en: en, descs: descs });
      }
    });

    var byCal = {};
    metrics.forEach(function (m) {
      var cal = (m.caliber_desc || '').trim();
      if (!cal) return;
      if (!byCal[cal]) byCal[cal] = [];
      var en = (m.metric_en || '').trim();
      if (en && byCal[cal].indexOf(en) < 0) byCal[cal].push(en);
    });
    var synonyms = [];
    Object.keys(byCal).forEach(function (cal) {
      var ens = byCal[cal].sort();
      if (ens.length > 1) {
        synonyms.push({ caliber_desc: cal, names: ens, suggest: ens[0] });
      }
    });
    return { homonyms: homonyms, synonyms: synonyms };
  }

  function rootRefCount(metrics, rootId) {
    var n = 0;
    metrics.forEach(function (m) {
      var ids = (m.root_ids || '').split(/[;,]/);
      for (var i = 0; i < ids.length; i++) {
        if (ids[i].trim() === rootId) n++;
      }
    });
    return n;
  }

  function statusBadge(status) {
    if (status === 'approved') return '<span class="badge badge-pass">✅ 已通过</span>';
    if (status === 'rejected') return '<span class="badge badge-fail">已驳回</span>';
    return '<span class="badge badge-warn">待确认</span>';
  }

  function renderNavBadges(metricsLen, rootsLen, homonymCount, veto) {
    var m = document.getElementById('nav-badge-metrics');
    var r = document.getElementById('nav-badge-roots');
    var c = document.getElementById('nav-badge-caliber');
    if (m) m.textContent = String(metricsLen);
    if (r) r.textContent = String(rootsLen);
    if (c) {
      var n = homonymCount || (veto ? 1 : 0);
      c.textContent = String(n);
      c.style.display = n > 0 ? '' : 'none';
      c.className = 'nav-badge' + (n > 0 ? ' danger' : '');
    }
  }

  function renderDashboard(report, roots, metrics, domains) {
    setStatValue(document.getElementById('dash-stat-metrics'), metrics + '<span class="unit">个</span>');
    setStatValue(document.getElementById('dash-stat-roots'), roots + '<span class="unit">个</span>');
    var domainCount = domains.length || 1;
    var covered = new Set();
    global.__DG_ROOTS__ && global.__DG_ROOTS__.forEach(function (rt) {
      if (rt.domain_code) covered.add(rt.domain_code);
    });
    setStatValue(
      document.getElementById('dash-stat-domains'),
      covered.size + '<span class="unit">/ ' + domainCount + '</span>'
    );

    if (report) {
      var total = report.total_points != null ? report.total_points : '—';
      var grade = report.grade || '—';
      var veto = report.veto ? ' <span style="color:var(--rose)">⛔</span>' : '';
      setStatValue(document.getElementById('dash-stat-acceptance'), total + '<span class="unit">分 · ' + grade + '级</span>' + veto);

      var map = {
        '命名规范': '命名规范率',
        '口径完整': '口径覆盖率',
        '词根覆盖': '词根覆盖率',
        '血缘可查': '血缘覆盖率',
        '模型评审': '评审完成率'
      };
      Object.keys(map).forEach(function (dimName) {
        var d = dimByName(report, dimName);
        if (d) updateProgressRow(map[dimName], pct(d.points, d.max_points));
      });
    }

    var riskList = document.getElementById('dash-risk-list');
    var riskBadge = document.getElementById('dash-risk-badge');
    if (riskList && report) {
      riskList.innerHTML = '';
      var items = [];
      if (report.veto) items.push({ t: '同名异义一票否决', d: report.veto_reason || '存在同名异义', level: 'danger' });
      (report.findings || []).forEach(function (f) {
        items.push({ t: f.code, d: f.message, level: f.severity === 'error' ? 'danger' : 'warn' });
      });
      (report.skipped_notes || []).slice(0, 2).forEach(function (n) {
        items.push({ t: '未自动评估', d: n, level: 'neutral' });
      });
      if (!items.length) items.push({ t: '暂无高风险项', d: '当前验收扫描未发现阻断项', level: 'pass' });
      items.forEach(function (it) {
        var pri = it.level === 'danger' ? 'p0' : it.level === 'warn' ? 'p1' : 'p2';
        var tone = it.level === 'danger' ? 'danger-tone' : it.level === 'warn' ? 'warn-tone' : it.level === 'pass' ? 'pass-tone' : '';
        var li = document.createElement('div');
        li.className = 'issue-item ' + tone;
        li.innerHTML =
          '<span class="issue-priority ' +
          pri +
          '">' +
          (it.level === 'danger' ? 'P0' : it.level === 'warn' ? 'P1' : 'P2') +
          '</span><div class="issue-content"><div class="issue-title">' +
          esc(it.t) +
          '</div><div class="issue-desc">' +
          esc(it.d) +
          '</div></div>';
        riskList.appendChild(li);
      });
      if (riskBadge) {
        var p0 = items.filter(function (x) {
          return x.level === 'danger';
        }).length;
        riskBadge.textContent = p0 + ' 项';
        riskBadge.className = 'badge ' + (p0 ? 'badge-fail' : 'badge-pass');
      }
    }
  }

  function renderScoring(report) {
    if (!report) return;
    setStatValue(document.getElementById('scoring-avg'), String(report.total_points));
    var pass = report.total_points >= 85;
    setStatValue(document.getElementById('scoring-pass-rate'), pass ? '100' : '0');
    var sub = document.getElementById('scoring-pass-sub');
    if (sub) sub.textContent = '项目验收 ' + report.grade + ' 级';

    var rows = document.querySelectorAll('#scoring-dimension-rows .scoring-dim-row');
    var gradients = ['linear-gradient(90deg,#3B82F6,#6366F1)', 'linear-gradient(90deg,#22C55E,#14B8A6)', 'linear-gradient(90deg,#F59E0B,#F97316)', 'linear-gradient(90deg,#8B5CF6,#EC4899)', 'linear-gradient(90deg,#14B8A6,#06B6D4)', 'linear-gradient(90deg,#818CF8,#4F46E5)'];
    rows.forEach(function (row, idx) {
      var name = row.getAttribute('data-dim');
      var d = dimByName(report, name);
      if (!d) return;
      var valEl = row.querySelector('.scoring-dim-val');
      var bar = row.querySelector('.score-bar-fill');
      if (valEl) valEl.textContent = d.points.toFixed(1);
      if (bar) {
        var p = pct(d.points, d.max_points);
        bar.style.width = p + '%';
        bar.style.background = d.passed
          ? gradients[idx % gradients.length]
          : p >= 70
            ? 'linear-gradient(90deg,#FBBF24,#F59E0B)'
            : 'linear-gradient(90deg,#F87171,#E11D48)';
      }
    });

    var md = document.getElementById('acceptanceMarkdownPreview');
    if (md && report.markdown) md.textContent = report.markdown.slice(0, 4000);
  }

  function renderCaliberPage(report, metrics) {
    var conflicts = computeCaliberConflicts(metrics);
    var homonymN = conflicts.homonyms.length;
    var synonymN = conflicts.synonyms.length;

    var vetoEl = document.getElementById('caliber-veto-callout');
    var okEl = document.getElementById('caliber-ok-callout');
    var vetoText = document.getElementById('caliber-veto-text');
    if (homonymN > 0 || (report && report.veto)) {
      if (vetoEl) vetoEl.style.display = '';
      if (okEl) okEl.style.display = 'none';
      if (vetoText) {
        vetoText.innerHTML =
          '<strong>一票否决项：</strong>检测到 <strong>' +
          homonymN +
          ' 例同名异义</strong>，必须处理后才能通过验收。';
      }
    } else {
      if (vetoEl) vetoEl.style.display = 'none';
      if (okEl) okEl.style.display = '';
    }

    var filled = metrics.filter(function (m) {
      return (m.caliber_desc || '').trim();
    }).length;
    var fillPct = metrics.length ? Math.round((filled / metrics.length) * 1000) / 10 : 0;
    var emptyPct = metrics.length ? Math.round((1 - filled / metrics.length) * 1000) / 10 : 0;

    setStatValue(document.getElementById('caliber-stat-coverage'), String(fillPct));
    setStatValue(document.getElementById('caliber-stat-synonym'), String(synonymN));
    setStatValue(document.getElementById('caliber-stat-homonym'), String(homonymN));

    var hb = document.getElementById('caliber-homonym-badge');
    var sb = document.getElementById('caliber-synonym-badge');
    if (hb) hb.textContent = homonymN + ' 例';
    if (sb) sb.textContent = synonymN + ' 例';

    var htbody = document.getElementById('caliber-homonym-tbody');
    if (htbody) {
      if (!homonymN) {
        htbody.innerHTML =
          '<tr><td colspan="5" class="text-sm text-muted" style="padding:16px;">✅ 未发现同名异义</td></tr>';
      } else {
        htbody.innerHTML = conflicts.homonyms
          .map(function (h) {
            return (
              '<tr><td class="text-mono text-bold">' +
              esc(h.metric_en) +
              '</td><td class="text-sm">' +
              esc(h.descs[0]) +
              '</td><td class="text-sm">' +
              esc(h.descs[1] || h.descs.slice(1).join(' / ')) +
              '</td><td><span class="badge badge-fail">口径冲突</span></td><td><button type="button" class="btn btn-sm btn-primary">处理</button></td></tr>'
            );
          })
          .join('');
      }
    }

    var stbody = document.getElementById('caliber-synonym-tbody');
    if (stbody) {
      if (!synonymN) {
        stbody.innerHTML =
          '<tr><td colspan="5" class="text-sm text-muted" style="padding:16px;">暂无同义异名（精确 caliber_desc 匹配）</td></tr>';
      } else {
        stbody.innerHTML = conflicts.synonyms
          .slice(0, 20)
          .map(function (s) {
            return (
              '<tr><td class="text-sm">' +
              esc(s.caliber_desc.slice(0, 80)) +
              (s.caliber_desc.length > 80 ? '…' : '') +
              '</td><td class="text-mono">' +
              esc(s.names[0]) +
              '</td><td class="text-mono">' +
              esc(s.names[1]) +
              (s.names.length > 2 ? ' +' + (s.names.length - 2) : '') +
              '</td><td class="text-mono text-bold" style="color:var(--primary)">' +
              esc(s.suggest) +
              '</td><td><button type="button" class="btn btn-sm">统一</button></td></tr>'
            );
          })
          .join('');
      }
    }

    var barF = document.getElementById('caliber-bar-filled');
    var barE = document.getElementById('caliber-bar-empty');
    var pctF = document.getElementById('caliber-pct-filled');
    var pctE = document.getElementById('caliber-pct-empty');
    if (barF) {
      barF.style.width = fillPct + '%';
      barF.textContent = filled + ' (' + fillPct + '%)';
    }
    if (barE) {
      barE.style.width = emptyPct + '%';
      barE.textContent = metrics.length - filled + ' (' + emptyPct + '%)';
    }
    if (pctF) pctF.textContent = fillPct + '%';
    if (pctE) pctE.textContent = emptyPct + '%';
  }

  function renderRootsTable(roots, metrics, domains) {
    var tbody = document.getElementById('roots-table-body');
    var countEl = document.getElementById('roots-table-count');
    if (countEl) countEl.textContent = '共 ' + roots.length + ' 条（API）';
    if (!tbody) return;

    if (!roots.length) {
      tbody.innerHTML =
        '<tr><td colspan="9" class="text-sm text-muted" style="padding:20px;">暂无词根数据，请检查 roots/*_roots.csv</td></tr>';
      return;
    }

    tbody.innerHTML = roots
      .map(function (r) {
        var typeLabel = ROOT_TYPE_LABEL[r.root_type] || r.root_type || '—';
        var refs = rootRefCount(metrics, r.root_id);
        return (
          '<tr data-root-id="' +
          esc(r.root_id) +
          '"><td class="text-mono text-sm">' +
          esc(r.root_id) +
          '</td><td>' +
          esc(r.root_cn) +
          '</td><td class="text-mono">' +
          esc(r.root_en) +
          '</td><td class="text-mono">' +
          esc(r.root_abbr) +
          '</td><td><span class="badge badge-neutral">' +
          esc(typeLabel) +
          '</span></td><td><span class="badge badge-info">' +
          esc(r.source_model || '—') +
          '</span></td><td><span class="text-bold">' +
          refs +
          '</span></td><td>' +
          statusBadge(r.review_status) +
          '</td><td><button type="button" class="btn btn-sm" onclick="showRootEditModal(this)">编辑</button> <button type="button" class="btn btn-sm" onclick="showRootOfflineModal(\'' +
          esc(r.root_id) +
          '\')" style="color:var(--danger)">下线</button></td></tr>'
        );
      })
      .join('');
  }

  function renderRootsStats(roots, domains) {
    setStatValue(document.getElementById('roots-stat-total'), String(roots.length));
    var approved = roots.filter(function (r) {
      return r.review_status === 'approved';
    }).length;
    var pending = roots.filter(function (r) {
      return r.review_status !== 'approved' && r.review_status !== 'rejected';
    }).length;
    var pctA = roots.length ? Math.round((approved / roots.length) * 100) : 0;
    var el = document.getElementById('roots-stat-approved');
    if (el) el.innerHTML = approved + '<span class="unit">(' + pctA + '%)</span>';
    setStatValue(document.getElementById('roots-stat-pending'), String(pending));
    var covered = {};
    roots.forEach(function (r) {
      if (r.domain_code) covered[r.domain_code] = true;
    });
    var dc = domains.length || Object.keys(covered).length;
    setStatValue(document.getElementById('roots-stat-domains'), Object.keys(covered).length + '/' + dc);
  }

  function loadAll(refreshAcceptance) {
    var accPath = refreshAcceptance ? '/api/acceptance?refresh=true' : '/api/acceptance?refresh=true';
    return Promise.all([
      fetchJson(accPath).catch(function () {
        return null;
      }),
      fetchJson('/api/roots').catch(function () {
        return [];
      }),
      fetchJson('/api/metrics').catch(function () {
        return [];
      }),
      fetchJson('/api/domains').catch(function () {
        return [];
      }),
      fetchJson('/api/metric-tree').catch(function () {
        return null;
      }),
      fetchJson('/api/scores/summary').catch(function () {
        return [];
      })
    ]).then(function (arr) {
      var report = arr[0];
      var roots = arr[1];
      var metrics = arr[2];
      var domains = arr[3];
      var metricTree = arr[4];
      var scoreSummary = arr[5];
      global.__DG_ROOTS__ = roots;
      global.__DG_METRICS__ = metrics;
      global.__DG_METRIC_ROWS__ = metrics;
      global.__DG_DOMAINS__ = domains;
      global.__DG_SCORE_SUMMARY__ = scoreSummary || [];

      var conflicts = computeCaliberConflicts(metrics);
      renderNavBadges(metrics.length, roots.length, conflicts.homonyms.length, report && report.veto);
      renderDashboard(report, roots.length, metrics.length, domains);
      renderScoring(report);
      renderCaliberPage(report, metrics);
      renderRootsStats(roots, domains);
      renderRootsTable(roots, metrics, domains);
      if (global.MetricMgmt && global.MetricMgmt.renderTable) {
        global.MetricMgmt.renderTable(metrics);
        if (global.MetricMgmt.bindFilters) global.MetricMgmt.bindFilters();
      }
      if (typeof window.refreshMetricLibraryFromApi === 'function') {
        window.refreshMetricLibraryFromApi(metrics, domains);
      }
      if (metricTree && global.MetricTreeUI && global.MetricTreeUI.applyPayload) {
        global.MetricTreeUI.applyPayload(metricTree);
      } else if (global.MetricTreeUI && global.MetricTreeUI.applyMetricFilters) {
        global.MetricTreeUI.applyMetricFilters();
      }
      global.__DG_LAST_REPORT__ = report;
      var extras = [];
      if (global.DGExt && global.DGExt.loadReviewExtras) {
        extras.push(global.DGExt.loadReviewExtras(metrics));
      }
      if (global.DGExt && global.DGExt.loadModifierRules) {
        extras.push(global.DGExt.loadModifierRules());
      }
      if (global.DGExt && global.DGExt.loadLineageMeta) {
        extras.push(global.DGExt.loadLineageMeta().catch(function () {}));
      }
      return Promise.all(extras).then(function () {
        return report;
      });
    });
  }

  function runAcceptanceAndReload() {
    return fetchJson('/api/acceptance/run', { method: 'POST' }).then(function () {
      return loadAll(true);
    });
  }

  global.DG = {
    loadAll: loadAll,
    refresh: function () { return loadAll(false); },
    runAcceptanceAndReload: runAcceptanceAndReload,
    fetchJson: fetchJson,
    API_BASE: API_BASE
  };

  document.addEventListener('DOMContentLoaded', function () {
    loadAll(true).catch(function (e) {
      console.warn('DG API 未连接（请先 data-governance serve）:', e.message);
    });
  });
})(window);
