/**
 * 指标信息规范表 — 与 metric-spec-template.html + css/metric-spec.css 同一套 DOM
 */
(function (global) {
  var DOMAIN_CN = {};

  function esc(s) {
    if (s == null || s === '') return '—';
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function inferValueType(unit, explicit) {
    if (explicit) return explicit;
    if (unit === '%') return '时点比率、周期比率';
    if (unit === '元') return '周期总量';
    return '周期计数';
  }

  function pickFormulaCn(row) {
    if (row.formula_cn && String(row.formula_cn).trim()) {
      return String(row.formula_cn).trim();
    }
    return '—';
  }

  function pickFormulaLogic(row) {
    if (row.formula && String(row.formula).trim()) {
      return String(row.formula).trim();
    }
    return '—';
  }

  function formulaBlockHtml(spec) {
    var cn = spec.formula_cn || '—';
    var logic = spec.formula_logic || '—';
    return (
      '<div class="indicator-spec-formula-block">' +
      '<div class="indicator-spec-formula-part">' +
      '<div class="indicator-spec-formula-part-label">中文口径</div>' +
      '<div class="indicator-spec-formula-cn">' +
      esc(cn) +
      '</div></div>' +
      '<div class="indicator-spec-formula-part">' +
      '<div class="indicator-spec-formula-part-label">伪代码逻辑</div>' +
      '<div class="indicator-spec-formula-pseudo">' +
      esc(logic) +
      '</div></div></div>'
    );
  }

  function versionHistoryHtml(spec) {
    var raw = spec.version_history;
    var items = [];
    if (raw && String(raw).trim() && String(raw).trim() !== '—') {
      String(raw)
        .split(/\n+/)
        .forEach(function (line) {
          line = line.trim();
          if (!line) return;
          var p = line.split('|').map(function (s) {
            return s.trim();
          });
          if (p.length >= 4) {
            items.push(
              '<div class="indicator-spec-version-item">' +
                '<span class="indicator-spec-version-no">' +
                esc(p[0]) +
                '</span> ' +
                '<span class="indicator-spec-version-date">' +
                esc(p[1]) +
                '</span> · ' +
                esc(p[2]) +
                ' · ' +
                esc(p[3]) +
                '</div>'
            );
          } else {
            items.push('<div class="indicator-spec-version-item">' + esc(line) + '</div>');
          }
        });
    }
    if (!items.length && spec.version) {
      items.push(
        '<div class="indicator-spec-version-item">' +
          '<span class="indicator-spec-version-no">' +
          esc(spec.version) +
          '</span> ' +
          '<span class="indicator-spec-version-date">当前版本</span>' +
          '</div>'
      );
    }
    if (!items.length) return '—';
    return '<div class="indicator-spec-version-log">' + items.join('') + '</div>';
  }

  function apiRowToSpec(row, domainMap) {
    domainMap = domainMap || {};
    var dom = row.domain_code || '';
    var domCn = domainMap[dom] || DOMAIN_CN[dom] || dom;
    return {
      category_l1: row.category_l1 || domCn,
      category_l2: row.category_l2 || '—',
      metric_name: row.metric_cn || '—',
      metric_id: row.metric_id || '—',
      unit: row.unit || '—',
      value_type: inferValueType(row.unit, row.value_type),
      frequency: row.frequency || '—',
      dimensions: row.dimensions || '—',
      scenario: row.scenario || '—',
      owner: row.owner || '—',
      reports: row.reports || '—',
      description: row.caliber_desc || '—',
      formula_cn: pickFormulaCn(row),
      formula_logic: pickFormulaLogic(row),
      analysis_methods: row.analysis_methods || '—',
      alert_rules: row.alert_rules || '—',
      precision: row.precision || '—',
      data_sources: row.data_sources || '—',
      tech_caliber: row.tech_caliber || '',
      source_table: row.source_table || '—',
      version: row.version || '',
      version_history: row.version_history || ''
    };
  }

  function mockToSpec(m) {
    return {
      category_l1: m.categoryL1 || m.domain || '—',
      category_l2: m.categoryL2 || m.category || '—',
      metric_name: m.name || '—',
      metric_id: m.id || '—',
      unit: m.unit || '—',
      value_type: m.valueType || inferValueType(m.unit, ''),
      frequency: m.freq || '—',
      dimensions: m.dimensions || '—',
      scenario: m.scenario || '—',
      owner: m.owner || '—',
      reports: m.reports || '—',
      description: m.desc || '—',
      formula_cn: m.formulaCn || pickFormulaCn({ formula_cn: m.formulaCn }),
      formula_logic: m.formulaLogic || pickFormulaLogic({ formula: m.formula }),
      analysis_methods: m.analysisMethods || '—',
      alert_rules: m.alertRules || '—',
      precision: m.precision || '—',
      data_sources: m.dataSources || '—',
      tech_caliber: m.techCaliber || '',
      source_table: m.sourceTable || m.source_table || '—',
      version: m.version || '',
      version_history: m.versionHistory || m.version_history || ''
    };
  }

  /** 字段名 → 属性类型：mgmt 数据管理 | tech 技术 | biz 业务 */
  var LABEL_ATTR = {
    指标名称: 'biz',
    指标编号: 'biz',
    计量单位: 'tech',
    值类型: 'biz',
    时间周期: 'tech',
    统计维度: 'biz',
    应用场景: 'biz',
    指标负责单位: 'mgmt',
    应用报表: 'biz',
    指标描述: 'biz',
    计算公式: 'biz',
    分析方法: 'biz',
    预警标准: 'biz',
    精度: 'tech',
    数据来源: 'tech',
    技术来源: 'tech',
    所属物理表: 'tech',
    版本记录: 'mgmt'
  };

  function thClasses(label, block) {
    var attr = LABEL_ATTR[label] || 'biz';
    var cls = 'indicator-spec-th indicator-spec-th--' + attr;
    if (block) cls += ' indicator-spec-th-block';
    return cls;
  }

  function attrLegendHtml() {
    return (
      '<div class="indicator-spec-attr-legend" aria-label="字段属性图例">' +
      '<span><span class="legend-swatch legend-swatch--biz"></span>业务属性</span>' +
      '<span><span class="legend-swatch legend-swatch--tech"></span>技术属性</span>' +
      '<span><span class="legend-swatch legend-swatch--mgmt"></span>数据管理属性</span>' +
      '</div>'
    );
  }

  function buildSpecTableHtml(spec, options) {
    options = options || {};
    var stampHtml = options.showExampleStamp
      ? '<span class="indicator-spec-stamp" aria-hidden="true">示例</span>'
      : '';
    var techHtml = spec.tech_caliber ? esc(spec.tech_caliber) : '&nbsp;';

    // 顶部分类标签栏
    var headerHtml = '';
    if (options.showHeader !== false) {
      var badgeHtml = options.showBadge !== false
        ? '<div class="indicator-spec-card-badge">指标卡片</div>'
        : '';
      headerHtml =
        '<div class="indicator-spec-header">' +
        '<div class="indicator-spec-cat-tags">' +
        '<div class="indicator-spec-cat-tag"><span class="label">一级分类：</span><span class="value">' + esc(spec.category_l1) + '</span></div>' +
        '<div class="indicator-spec-cat-tag"><span class="label">二级分类：</span><span class="value">' + esc(spec.category_l2) + '</span></div>' +
        '</div>' +
        badgeHtml +
        '</div>';
    }

    var legendHtml = options.showAttrLegend !== false ? attrLegendHtml() : '';

    return (
      '<div class="metric-spec-surface">' +
      headerHtml +
      '<div class="indicator-spec-card">' +
      legendHtml +
      '<table class="indicator-spec-table" cellspacing="0" cellpadding="0">' +
      rowPair('指标名称', spec.metric_name, '指标编号', spec.metric_id) +
      rowPair('计量单位', spec.unit, '值类型', spec.value_type) +
      rowPair('时间周期', spec.frequency, '统计维度', spec.dimensions) +
      rowPair('应用场景', spec.scenario, '指标负责单位', spec.owner) +
      rowFull('应用报表', spec.reports) +
      rowFull('指标描述', spec.description) +
      rowFullHtml('计算公式', formulaBlockHtml(spec)) +
      rowFull('分析方法', spec.analysis_methods) +
      '<tr' +
      (options.showExampleStamp ? ' class="indicator-spec-row-stamp"' : '') +
      '>' +
      rowFullInner('预警标准', esc(spec.alert_rules) + stampHtml) +
      '</tr>' +
      rowFull('精度', spec.precision) +
      rowFull('数据来源', spec.data_sources) +
      rowFullHtml('技术来源', techHtml) +
      rowFull('所属物理表', spec.source_table) +
      rowFullHtml('版本记录', versionHistoryHtml(spec)) +
      '</table></div></div>'
    );
  }

  function rowFullInner(label, valueHtml) {
    return (
      '<th class="' +
      thClasses(label, true) +
      '">' +
      label +
      '</th><td class="indicator-spec-td indicator-spec-td-block" colspan="3">' +
      valueHtml +
      '</td>'
    );
  }

  function renderIndicatorSpecCard(container, spec, options) {
    if (!container) return;
    container.innerHTML = buildSpecTableHtml(spec, options);
  }

  function rowPair(l1, v1, l2, v2) {
    return (
      '<tr><th class="' +
      thClasses(l1, false) +
      '">' +
      l1 +
      '</th><td class="indicator-spec-td">' +
      esc(v1) +
      '</td><th class="' +
      thClasses(l2, false) +
      '">' +
      l2 +
      '</th><td class="indicator-spec-td">' +
      esc(v2) +
      '</td></tr>'
    );
  }

  function rowFull(label, value) {
    return '<tr>' + rowFullInner(label, esc(value)) + '</tr>';
  }

  function rowFullHtml(label, valueHtml) {
    return '<tr>' + rowFullInner(label, valueHtml) + '</tr>';
  }

  function setDomainMap(domains) {
    DOMAIN_CN = {};
    (domains || []).forEach(function (d) {
      var code = d.domain_code || d.code;
      var cn = d.domain_name_cn || d.name_cn;
      if (code) DOMAIN_CN[code] = cn || code;
    });
    global.MetricSpec._domainMap = DOMAIN_CN;
  }

  global.MetricSpec = {
    apiRowToSpec: apiRowToSpec,
    mockToSpec: mockToSpec,
    buildSpecTableHtml: buildSpecTableHtml,
    renderIndicatorSpecCard: renderIndicatorSpecCard,
    setDomainMap: setDomainMap,
    TEMPLATE_PATH: 'metric-spec-template.html'
  };
})(window);
