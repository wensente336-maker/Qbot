// assets/charts.js — 技术方案评审图表
(function () {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var danger = style.getPropertyValue('--danger').trim();
  var ok = style.getPropertyValue('--ok').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();

  var axisLabel = { color: muted, fontSize: 12 };
  var splitLine = { lineStyle: { color: rule, opacity: 0.5 } };

  // ---------- 图 4：风险矩阵（可能性 × 影响） ----------
  // [可能性, 影响, 等级]
  var riskData = [
    { id: 'R1', x: 0.82, y: 0.9,  lvl: 'danger', name: '抖音数据源合法性' },
    { id: 'R2', x: 0.55, y: 0.85, lvl: 'danger', name: 'HTML 动效渲染引擎' },
    { id: 'R3', x: 0.58, y: 0.82, lvl: 'danger', name: 'ASR 词级时间轴' },
    { id: 'R4', x: 0.62, y: 0.5,  lvl: 'mid',   name: '粗剪自然度 / 时间轴重映射' },
    { id: 'R5', x: 0.5,  y: 0.68, lvl: 'mid',   name: '单实例服务器性能' },
    { id: 'R6', x: 0.75, y: 0.42, lvl: 'mid',   name: '个人号指标接口权限' },
    { id: 'R7', x: 0.42, y: 0.45, lvl: 'mid',   name: '任务队列 / 长任务可靠性' },
    { id: 'R8', x: 0.3,  y: 0.55, lvl: 'low',   name: '数据模型冗余与缺失' }
  ];

  var colorFor = { danger: danger, mid: accent2, low: ok };
  var chartRisk = echarts.init(document.getElementById('chart-risk'), null, { renderer: 'svg' });
  chartRisk.setOption({
    animation: false,
    tooltip: {
      trigger: 'item',
      appendToBody: true,
      formatter: function (p) {
        return '<b>' + p.data.id + ' · ' + p.data.name + '</b><br/>可能性 ' + (p.data.x * 100).toFixed(0) + '% · 影响 ' + (p.data.y * 100).toFixed(0) + '%';
      }
    },
    grid: { left: 64, right: 40, top: 40, bottom: 64 },
    xAxis: {
      name: '发生可能性 →',
      nameTextStyle: { color: muted, fontSize: 12 },
      min: 0, max: 1, interval: 0.25,
      axisLine: { lineStyle: { color: rule } },
      axisLabel: axisLabel,
      splitLine: splitLine
    },
    yAxis: {
      name: '影响程度 →',
      nameTextStyle: { color: muted, fontSize: 12 },
      min: 0, max: 1, interval: 0.25,
      axisLine: { lineStyle: { color: rule } },
      axisLabel: axisLabel,
      splitLine: splitLine
    },
    series: [{
      type: 'scatter',
      symbolSize: 22,
      data: riskData.map(function (r) {
        return {
          value: [r.x, r.y],
          id: r.id,
          name: r.name,
          itemStyle: {
            color: colorFor[r.lvl],
            borderColor: ink,
            borderWidth: 1,
            opacity: 0.88
          },
          label: {
            show: true,
            formatter: r.id,
            position: 'right',
            color: ink,
            fontFamily: 'GeistMono',
            fontWeight: 700,
            fontSize: 11
          }
        };
      })
    }]
  });
  window.addEventListener('resize', function () { chartRisk.resize(); });

  // ---------- 图 5：模块风险评分（1–5） ----------
  var mods = [
    { name: 'M5 视频制作中心', v: 4.5 },
    { name: 'M1 对标账号监测', v: 4.0 },
    { name: 'M6 数据监测与复盘', v: 3.0 },
    { name: 'M4 文案创作中心', v: 2.5 },
    { name: 'M2 智能素材库', v: 2.0 },
    { name: 'M3 智能选题中心', v: 1.5 },
    { name: 'M7 运营驾驶舱', v: 1.5 }
  ];
  var chartMods = echarts.init(document.getElementById('chart-modules'), null, { renderer: 'svg' });
  chartMods.setOption({
    animation: false,
    tooltip: {
      trigger: 'item',
      appendToBody: true,
      formatter: function (p) {
        return '<b>' + p.name + '</b><br/>技术实现风险：' + p.value.toFixed(1) + ' / 5';
      }
    },
    grid: { left: 60, right: 70, top: 16, bottom: 30 },
    xAxis: {
      type: 'value',
      min: 0, max: 5, interval: 1,
      axisLine: { lineStyle: { color: rule } },
      axisLabel: axisLabel,
      splitLine: splitLine
    },
    yAxis: {
      type: 'category',
      data: mods.map(function (m) { return m.name; }).reverse(),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: ink, fontSize: 13 }
    },
    series: [{
      type: 'bar',
      barWidth: 20,
      label: {
        show: true,
        position: 'right',
        formatter: function (p) { return p.value.toFixed(1); },
        color: ink,
        fontFamily: 'GeistMono',
        fontWeight: 700
      },
      itemStyle: {
        borderRadius: [0, 6, 6, 0],
        color: function (p) {
          var v = p.value;
          if (v >= 4) return danger;
          if (v >= 3) return accent2;
          if (v >= 2) return accent;
          return ok;
        }
      },
      data: mods.map(function (m) { return m.v; }).reverse()
    }]
  });
  window.addEventListener('resize', function () { chartMods.resize(); });
})();
