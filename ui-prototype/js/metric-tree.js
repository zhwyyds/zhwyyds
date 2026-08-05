/**
 * 指标管理树 — config/metric_tree.csv + metrics tree_node_id
 */
(function (global) {
  var state = {
    treePayload: null,
    filterNodeId: null,
    filterDomain: null,
    search: ''
  };

  function esc(s) {
    if (s == null) return '';
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/"/g, '&quot;');
  }

  function iconForType(nodeType, hasChildren) {
    if (nodeType === 'domain') return hasChildren ? '📁' : '📂';
    if (nodeType === 'module') return hasChildren ? '📁' : '📂';
    if (nodeType === 'category') return '📂';
    return '📊';
  }

  function buildChildrenMap(nodes) {
    var byParent = {};
    nodes.forEach(function (n) {
      var p = n.parent_id;
      if (!p) p = '__root__';
      if (!byParent[p]) byParent[p] = [];
      byParent[p].push(n);
    });
    Object.keys(byParent).forEach(function (k) {
      byParent[k].sort(function (a, b) {
        return (a.sort_order || 0) - (b.sort_order || 0);
      });
    });
    return byParent;
  }

  function countMetricsUnder(nodeId, byParent, metricsByNode, cache) {
    if (cache[nodeId] != null) return cache[nodeId];
    var n = 0;
    if (metricsByNode[nodeId]) n += metricsByNode[nodeId].length;
    (byParent[nodeId] || []).forEach(function (child) {
      n += countMetricsUnder(child.node_id, byParent, metricsByNode, cache);
    });
    cache[nodeId] = n;
    return n;
  }

  function renderNode(node, byParent, metricsByNode, domainNames, depth, cache) {
    var children = byParent[node.node_id] || [];
    var metrics = metricsByNode[node.node_id] || [];
    var count = countMetricsUnder(node.node_id, byParent, metricsByNode, cache);
    var label = node.node_name;
    if (node.node_type === 'domain' && node.domain_code) {
      var dn = domainNames[node.domain_code] || node.domain_code;
      label = node.domain_code + ' ' + dn;
    }
    var html = '<div class="tree-node">';
    var branchKids = children.length > 0;
    var leafMetrics = metrics.length > 0;
    if (branchKids || leafMetrics) {
      html +=
        '<div class="tree-item" onclick="toggleTree(this); selectTreeNode(\'' +
        esc(node.node_id) +
        '\', event)" data-node-id="' +
        esc(node.node_id) +
        '">' +
        '<span class="tree-toggle">' +
        (depth < 2 ? '▼' : '▶') +
        '</span>' +
        '<span class="tree-icon">' +
        iconForType(node.node_type, true) +
        '</span> ' +
        esc(label) +
        ' <span class="tree-count">' +
        count +
        '</span></div>';
      html += '<div class="tree-children' + (depth < 2 ? ' expanded' : '') + '">';
      children.forEach(function (c) {
        html += renderNode(c, byParent, metricsByNode, domainNames, depth + 1, cache);
      });
      metrics.forEach(function (m) {
        html +=
          '<div class="tree-item tree-metric-leaf" data-metric-id="' +
          esc(m.metric_id) +
          '" onclick="selectMetricFromTree(\'' +
          esc(m.metric_id) +
          '\', event)">' +
          '<span class="tree-toggle"></span><span class="tree-icon">📊</span> ' +
          esc(m.metric_cn) +
          ' <span class="text-mono text-sm text-muted">' +
          esc(m.metric_id) +
          '</span></div>';
      });
      html += '</div>';
    } else {
      html +=
        '<div class="tree-item" data-node-id="' +
        esc(node.node_id) +
        '" onclick="selectTreeNode(\'' +
        esc(node.node_id) +
        '\', event)">' +
        '<span class="tree-toggle"></span><span class="tree-icon">' +
        iconForType(node.node_type, false) +
        '</span> ' +
        esc(label) +
        ' <span class="tree-count">0</span></div>';
    }
    html += '</div>';
    return html;
  }

  function renderMetricTree(payload) {
    var host = document.getElementById('metricTree');
    if (!host || !payload) return;
    state.treePayload = payload;
    var nodes = payload.nodes || [];
    var domainNames = payload.domain_names || {};
    var metricsByNode = payload.metrics_by_node || {};
    var byParent = buildChildrenMap(nodes);
    var roots = byParent['__root__'] || nodes.filter(function (n) {
      return !n.parent_id;
    });
    var cache = {};
    var html = '';
    roots.forEach(function (r) {
      html += renderNode(r, byParent, metricsByNode, domainNames, 0, cache);
    });
    if (payload.unassigned_metrics && payload.unassigned_metrics.length) {
      html +=
        '<div class="tree-node"><div class="tree-item" onclick="toggleTree(this)"><span class="tree-toggle">▶</span><span class="tree-icon">📁</span> 未挂载节点 <span class="tree-count">' +
        payload.unassigned_metrics.length +
        '</span></div><div class="tree-children">';
      payload.unassigned_metrics.forEach(function (m) {
        html +=
          '<div class="tree-item tree-metric-leaf" data-metric-id="' +
          esc(m.metric_id) +
          '" onclick="selectMetricFromTree(\'' +
          esc(m.metric_id) +
          '\', event)"><span class="tree-toggle"></span><span class="tree-icon">📊</span> ' +
          esc(m.metric_cn) +
          '</div>';
      });
      html += '</div></div>';
    }
    if (!html) {
      html = '<div class="text-sm text-muted" style="padding:12px;">暂无管理树配置（config/metric_tree.csv）</div>';
    }
    host.innerHTML = html;
  }

  function renderMetricListPanel(metrics, filter) {
    var tbody = document.getElementById('metric-list-tbody');
    var countEl = document.getElementById('metric-list-count');
    if (!tbody) return;
    var rows = metrics || [];
    if (filter && filter.nodeId && state.treePayload) {
      var set = collectMetricIdsForNode(filter.nodeId);
      rows = rows.filter(function (m) {
        return set[m.metric_id];
      });
    } else if (filter && filter.domain) {
      rows = rows.filter(function (m) {
        return m.domain_code === filter.domain;
      });
    }
    if (filter && filter.search) {
      var q = filter.search.toLowerCase();
      rows = rows.filter(function (m) {
        return (
          (m.metric_cn || '').toLowerCase().indexOf(q) >= 0 ||
          (m.metric_id || '').toLowerCase().indexOf(q) >= 0 ||
          (m.metric_en || '').toLowerCase().indexOf(q) >= 0
        );
      });
    }
    if (countEl) countEl.textContent = '共 ' + rows.length + ' 条';
    if (!rows.length) {
      tbody.innerHTML =
        '<tr><td colspan="6" class="text-sm text-muted" style="padding:16px;">无匹配指标</td></tr>';
      return;
    }
    tbody.innerHTML = rows
      .map(function (m) {
        var st =
          m.review_status === 'approved'
            ? '<span class="badge badge-pass">已通过</span>'
            : '<span class="badge badge-warn">待确认</span>';
        return (
          '<tr class="metric-list-row" data-metric-id="' +
          esc(m.metric_id) +
          '"><td class="text-mono text-sm">' +
          esc(m.metric_id) +
          '</td><td>' +
          esc(m.metric_cn) +
          '</td><td class="text-mono text-sm">' +
          esc(m.metric_en) +
          '</td><td>' +
          esc(m.category_l1 || m.domain_code) +
          ' / ' +
          esc(m.category_l2 || '—') +
          '</td><td>' +
          st +
          '</td><td><button type="button" class="btn btn-sm btn-primary" onclick="selectMetricFromTree(\'' +
          esc(m.metric_id) +
          '\', event)">查看</button></td></tr>'
        );
      })
      .join('');
  }

  function collectMetricIdsForNode(nodeId) {
    var out = {};
    var payload = state.treePayload;
    if (!payload) return out;
    var byParent = buildChildrenMap(payload.nodes || []);
    var metricsByNode = payload.metrics_by_node || {};

    function walk(id) {
      (metricsByNode[id] || []).forEach(function (m) {
        out[m.metric_id] = true;
      });
      (byParent[id] || []).forEach(function (c) {
        walk(c.node_id);
      });
    }
    walk(nodeId);
    return out;
  }

  global.selectTreeNode = function (nodeId, ev) {
    if (ev) ev.stopPropagation();
    state.filterNodeId = nodeId;
    state.filterDomain = null;
    document.querySelectorAll('#metricTree .tree-item.active').forEach(function (el) {
      el.classList.remove('active');
    });
    if (ev && ev.currentTarget) ev.currentTarget.classList.add('active');
    applyMetricFilters();
  };

  global.selectMetricFromTree = function (metricId, ev) {
    if (ev) {
      ev.stopPropagation();
      document.querySelectorAll('#metricTree .tree-item.active').forEach(function (el) {
        el.classList.remove('active');
      });
      var leaf = ev.currentTarget;
      if (leaf && leaf.classList) leaf.classList.add('active');
    }
    if (typeof setMetricIndexById === 'function' && setMetricIndexById(metricId)) {
      if (typeof updateMetricCard === 'function') updateMetricCard();
    } else if (typeof openMetricDrawer === 'function') {
      openMetricDrawer(metricId);
      return;
    }
  };

  function applyTreeMetricVisibility() {
    var q = (state.search || '').toLowerCase();
    var nodeSet = null;
    if (state.filterNodeId && state.treePayload) {
      nodeSet = collectMetricIdsForNode(state.filterNodeId);
    }
    document.querySelectorAll('#metricTree .tree-metric-leaf').forEach(function (el) {
      var id = (el.getAttribute('data-metric-id') || '').toLowerCase();
      var text = (el.textContent || '').toLowerCase();
      var ok = true;
      if (nodeSet && !nodeSet[el.getAttribute('data-metric-id')]) ok = false;
      if (q && text.indexOf(q) < 0 && id.indexOf(q) < 0) ok = false;
      el.style.display = ok ? '' : 'none';
    });
  }

  function applyMetricFilters() {
    var metrics = global.__DG_METRICS__ || global.__DG_METRIC_ROWS__ || [];
    var tbody = document.getElementById('metric-list-tbody');
    if (tbody) {
      renderMetricListPanel(metrics, {
        nodeId: state.filterNodeId,
        domain: state.filterDomain,
        search: state.search
      });
    } else {
      applyTreeMetricVisibility();
    }
  }

  function bindMetricLibraryFilters() {
    var input = document.getElementById('metricLibrarySearch');
    if (input && !input.dataset.bound) {
      input.dataset.bound = '1';
      input.addEventListener('input', function () {
        state.search = input.value.trim();
        var treeInput = document.getElementById('metricTreeSearch');
        if (treeInput) treeInput.value = state.search;
        applyMetricFilters();
      });
    }
    var treeInput = document.getElementById('metricTreeSearch');
    if (treeInput && !treeInput.dataset.bound) {
      treeInput.dataset.bound = '1';
      treeInput.addEventListener('input', function () {
        state.search = treeInput.value.trim();
        if (input) input.value = state.search;
        applyMetricFilters();
      });
    }
  }

  function loadMetricTree(apiBase, fetchJson) {
    return fetchJson('/api/metric-tree').then(function (payload) {
      renderMetricTree(payload);
      bindMetricLibraryFilters();
      applyMetricFilters();
      return payload;
    });
  }

  global.MetricTreeUI = {
    load: loadMetricTree,
    applyPayload: function (payload) {
      renderMetricTree(payload);
      bindMetricLibraryFilters();
      applyMetricFilters();
    },
    renderMetricListPanel: renderMetricListPanel,
    applyMetricFilters: applyMetricFilters
  };
})(window);
