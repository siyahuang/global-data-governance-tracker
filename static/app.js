const state = {
  view: 'home', config: { sections: [], categories: {} }, dashboard: {},
  articles: [], featured: [], total: 0, sources: [],
  filters: { q: '', category: '', country: '', province: '', source: '', month: '' },
  digestDates: [], digest: null,
  heatmap: null, heatmapPeriod: 'week',
  spotlight: null,
  worldLand: null,
  favorites: (() => {
    try { const items = JSON.parse(localStorage.getItem('data-governance-favorites') || '[]'); return Array.isArray(items) ? items : []; }
    catch { return []; }
  })(),
  loading: false, requestSeq: 0,
};

const $ = selector => document.querySelector(selector);
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[c]));
const number = value => Number(value || 0).toLocaleString('zh-CN');
const safeHref = value => {
  try { const url = new URL(value); return ['http:', 'https:'].includes(url.protocol) ? escapeHtml(url.href) : '#'; }
  catch { return '#'; }
};
const date = value => {
  if (!value) return '日期未注明';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '日期未注明' : d.toLocaleDateString('zh-CN', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
  });
};
const monthDay = value => {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('zh-CN', {
    timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit',
  });
};
const validViews = new Set(['home', 'news', 'international', 'china', 'digest', 'favorites', 'heatmap', 'topics']);
const viewFromHash = () => validViews.has(window.location.hash.slice(1)) ? window.location.hash.slice(1) : 'home';
const filtersFromSearch = () => {
  const query = new URLSearchParams(window.location.search);
  const filters = { q: '', category: '', country: '', province: '', source: '', month: '' };
  Object.keys(filters).forEach(key => { filters[key] = query.get(key) || ''; });
  return filters;
};

async function request(url) {
  const response = await fetch(url);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || '加载失败，请稍后再试');
  return body;
}

async function loadAll() {
  try {
    const [config, dashboard, articles, sources, digests, heatmap, worldLand] = await Promise.all([
      request('/api/config'), request('/api/dashboard'),
      request('/api/articles?limit=12'), request('/api/sources'), request('/api/digests'),
      request('/api/heatmap?period=week'),
      request('/world-land.geojson'),
    ]);
    Object.assign(state, {
      config, dashboard, articles: articles.items, featured: articles.items.slice(0, 4),
      total: articles.total, sources: sources.items, digestDates: digests.items,
      heatmap, worldLand,
    });
    if (state.digestDates.length) state.digest = await request('/api/digest?week=' + state.digestDates[0].week_start);
    const initialView = viewFromHash();
    if (['news', 'international', 'china'].includes(initialView)) state.filters = filtersFromSearch();
    renderAll();
    if (initialView !== 'home') setView(initialView, true);
  } catch (error) { showError(error.message); }
}

function articleParams(offset = 0) {
  const params = new URLSearchParams({ limit: '12', offset: String(offset) });
  if (state.view === 'china') params.set('scope', 'china');
  if (state.view === 'international') params.set('scope', 'international');
  Object.entries(state.filters).forEach(([key, value]) => { if (value) params.set(key, value); });
  return params;
}

async function loadArticles(append = false) {
  if (append && state.loading) return;
  const seq = ++state.requestSeq;
  state.loading = true;
  try {
    const placeKind = state.view === 'china' ? 'province' : 'country';
    const placeName = state.view === 'china' ? state.filters.province : state.filters.country;
    const spotlightRequest = placeName && !append
      ? request('/api/spotlight?' + new URLSearchParams({ kind: placeKind, name: placeName }))
      : Promise.resolve(append ? state.spotlight : null);
    const [result, spotlight] = await Promise.all([
      request('/api/articles?' + articleParams(append ? state.articles.length : 0)), spotlightRequest,
    ]);
    if (seq !== state.requestSeq) return;
    state.articles = append ? state.articles.concat(result.items) : result.items;
    state.total = result.total;
    state.spotlight = spotlight;
    renderNews(state.view);
  } catch (error) { if (seq === state.requestSeq) showError(error.message); }
  finally { if (seq === state.requestSeq) state.loading = false; }
}

function renderAll() {
  const updated = state.dashboard.last_updated;
  const updatedAt = updated ? new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false
  }).format(new Date(updated)) : '';
  $('#header-update').textContent = updatedAt ? `更新于 ${updatedAt}` : '持续更新';
  renderHome(); renderNews('news'); renderNews('international'); renderNews('china');
  renderDigest(); renderFavorites(); renderHeatmap(); renderTopics();
}

function heading(kicker, title, intro) {
  return `<div class="page-heading"><span class="kicker">${kicker}</span><h1>${title}</h1><p>${intro}</p></div>`;
}

function articleCard(item, compact = false) {
  const category = state.config.categories[item.category_id] || '数据治理';
  const rawSummary = item.brief_zh || item.summary || (item.title_zh ? item.title : '打开原文阅读完整报道。');
  const summary = rawSummary.length > 170 ? rawSummary.slice(0, 170).replace(/[，、；\s]+$/, '') + '…' : rawSummary;
  const place = item.source_country === '中国' ? (item.province || '中国') : (item.source_country === '未定位' ? '国际来源' : (item.source_country || item.source_region));
  const dateLabel = item.date_kind === 'event' ? '事件日期' : '发布日期';
  const saved = state.favorites.some(entry => entry.id === item.id);
  return `<article class="article-card ${compact ? 'compact' : ''}">
    <div class="card-meta"><span class="topic-pill">${escapeHtml(category)}</span><span>${escapeHtml(item.record_type)}</span><span>${escapeHtml(place)}</span><span class="meta-dot">·</span><span>${dateLabel} ${date(item.published_at)}</span><button class="favorite-button ${saved ? 'saved' : ''}" data-action="favorite" data-id="${item.id}" aria-pressed="${saved}" aria-label="${saved ? '取消收藏' : '收藏这条资讯'}">${saved ? '★ 已收藏' : '☆ 收藏'}</button></div>
    <button class="article-title" data-action="detail" data-id="${item.id}">${escapeHtml(item.title_zh || item.title)}</button>
    <p class="article-summary">${escapeHtml(summary)}</p>
    <div class="card-bottom"><span class="source-name">${escapeHtml(item.source_name)}</span><button class="read-link" data-action="detail" data-id="${item.id}">了解详情 <span aria-hidden="true">→</span></button></div>
  </article>`;
}

function renderHome() {
  const d = state.dashboard;
  const top = (d.category_counts || []).slice(0, 6);
  $('#home-view').innerHTML = `
    <section class="hero">
      <div class="hero-copy"><span class="hero-eyebrow"><span class="pulse"></span> GLOBAL DATA GOVERNANCE</span>
        <h1>看见全球数据治理<br><em>正在发生什么</em></h1>
        <p>持续汇集各地公开发布的信息，追踪数据开放、共享、跨境流动与人工智能领域的政策和实践。</p>
        <div class="hero-actions"><button class="primary-button" data-view="international">浏览国际动态 <span aria-hidden="true">↗</span></button><button class="ghost-button" data-view="china">查看国内动态 <span aria-hidden="true">→</span></button></div>
      </div>
      <div class="hero-visual" aria-hidden="true"><div class="orbit orbit-one"></div><div class="orbit orbit-two"></div><div class="globe"><span>◎</span></div><i class="node n1"></i><i class="node n2"></i><i class="node n3"></i><i class="node n4"></i></div>
    </section>
    <div class="overview-strip"><div><strong>${number(d.total)}</strong><span>条全球资讯</span></div><div><strong>${number(d.total - d.china_count)}</strong><span>条国际动态</span></div><div><strong>${number(d.china_count)}</strong><span>条国内动态</span></div><div><strong>${number(d.province_count)}</strong><span>个有记录的中国省市</span></div></div>
    <section class="entry-cards"><button data-view="international"><span class="entry-icon">◎</span><span><small>GLOBAL COVERAGE</small><strong>国际动态</strong><em>查看国家地区、议题与最新资讯</em></span><b>↗</b></button><button data-view="china"><span class="entry-icon">▦</span><span><small>CHINA COVERAGE</small><strong>国内动态</strong><em>按省市追踪数据治理实践</em></span><b>↗</b></button><button data-view="digest"><span class="entry-icon">☷</span><span><small>WEEKLY BRIEF</small><strong>每周简报</strong><em>${state.digest ? `${escapeHtml(state.digest.from_date)}—${escapeHtml(state.digest.through_date)} · ${number(state.digest.total)} 条动态` : '按周整理与解读'}</em></span><b>↗</b></button></section>
    <section class="snapshot-grid"><div class="trend-panel"><div class="panel-title"><span class="kicker">ACTIVITY OVER TIME</span><h2>近 14 天动态</h2><p>按报道发布日期或政策事件日期统计</p></div>${miniTrend()}</div><div class="snapshot-note"><span class="kicker">THIS WEEK</span><h2>把一周变化放在一起看</h2><p>每周简报汇总本周全部已收录资讯，先梳理主要事件，再做有来源依据的整合分析。</p><button class="outline-button" data-view="digest">阅读本周简报 <span>→</span></button></div></section>
    <section class="home-section"><div class="section-title"><div><span class="kicker">LATEST UPDATES</span><h2>最新动态</h2><p>按报道发布日期或政策事件日期展示</p></div><button class="section-link" data-view="international">浏览国际动态 <span>→</span></button></div>
      <div class="home-grid"><div class="article-grid">${state.featured.length ? state.featured.map(x => articleCard(x, true)).join('') : emptyState('暂无动态', '请稍后再来看。')}</div>
      <aside class="topic-aside"><span class="kicker">EXPLORE BY TOPIC</span><h3>从感兴趣的主题开始</h3><p>选择一个主题，查看相关政策、案例与活动。</p><div class="topic-list">${top.map(x => `<button data-action="category" data-category="${x.category_id}"><span>${escapeHtml(state.config.categories[x.category_id])}</span><small>${number(x.count)} 条</small><b>→</b></button>`).join('')}</div><button class="all-topics" data-view="topics">浏览全部主题 →</button></aside></div>
    </section>
    <section class="about-band"><div><span class="kicker">ABOUT THIS TRACKER</span><h2>从各地发布，到清晰的全球视野</h2><p>汇集机构发布与公开报道，保留原文链接。你可以按主题、地区或月份查找，并直接阅读原始发布内容。</p></div><button class="outline-button" data-view="heatmap">查看活力热力图 <span>→</span></button></section>`;
}

function emptyState(title, text) {
  return `<div class="empty-state"><span>⌕</span><strong>${title}</strong><p>${text}</p></div>`;
}

const EU_MEMBER_COUNTRIES = [
  '奥地利', '比利时', '保加利亚', '克罗地亚', '塞浦路斯', '捷克', '丹麦', '爱沙尼亚',
  '芬兰', '法国', '德国', '希腊', '匈牙利', '爱尔兰', '意大利', '拉脱维亚', '立陶宛',
  '卢森堡', '马耳他', '荷兰', '波兰', '葡萄牙', '罗马尼亚', '斯洛伐克', '斯洛文尼亚',
  '西班牙', '瑞典',
];

function filterOptions() {
  const f = state.filters;
  const categories = state.config.sections.map(s => `<optgroup label="${escapeHtml(s.name)}">${s.categories.map(c => `<option value="${c.id}" ${f.category === c.id ? 'selected' : ''}>${escapeHtml(c.name)}</option>`).join('')}</optgroup>`).join('');
  const countries = [...new Set(['欧盟', ...EU_MEMBER_COUNTRIES].concat(state.sources.map(x => x.country), (state.dashboard.country_counts || []).map(x => x.name)))].filter(x => x && x !== '未定位').sort((a, b) => a.localeCompare(b, 'zh-CN'));
  const provinces = [...new Set(state.sources.map(x => x.province).filter(Boolean).concat((state.dashboard.province_counts || []).map(x => x.name)))].sort((a, b) => a.localeCompare(b, 'zh-CN'));
  return { categories, countries, provinces };
}

const countryLocations = {
  '欧盟': [474, 149], '英国': [447, 143], '法国': [463, 159], '西班牙': [445, 173],
  '德国': [476, 146], '韩国': [763, 181], '日本': [805, 182], '菲律宾': [776, 236],
  '美国': [194, 174], '加拿大': [153, 104], '澳大利亚': [812, 305], '巴西': [255, 285], '墨西哥': [159, 210],
  '意大利': [484, 174], '奥地利': [488, 157], '荷兰': [463, 144], '爱尔兰': [436, 145],
  '瑞典': [479, 120], '肯尼亚': [523, 282], '印度': [683, 224], '印度尼西亚': [766, 276],
  '新加坡': [743, 268], '南非': [506, 350], '土耳其': [543, 177], '新西兰': [880, 354],
};
const provinceNames = ['北京','天津','河北','山西','内蒙古','辽宁','吉林','黑龙江','上海','江苏','浙江','安徽','福建','江西','山东','河南','湖北','湖南','广东','广西','海南','重庆','四川','贵州','云南','西藏','陕西','甘肃','青海','宁夏','新疆','香港','澳门','台湾'];

function miniTrend() {
  const days = state.dashboard.trend || [];
  const max = Math.max(1, ...days.map(x => x.count));
  return `<div class="trend-bars" role="img" aria-label="近十四天按报道发布日期或事件日期统计的动态条数">${days.map(x => `<div title="${x.day}：${x.count} 条"><i style="height:${Math.max(7, x.count / max * 100)}%"></i><span>${x.day.slice(5)}</span></div>`).join('')}</div>`;
}

function geoPoint(point) {
  const [longitude, latitude] = point;
  return `${((longitude + 180) / 360 * 960).toFixed(2)},${((90 - latitude) / 180 * 410).toFixed(2)}`;
}

function geoPath(geometry) {
  if (!geometry) return '';
  const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
  return polygons.map(polygon => polygon.map(ring =>
    `M${ring.map(geoPoint).join('L')}Z`).join('')).join('');
}

function worldLandPaths() {
  return (state.worldLand?.features || []).map(feature =>
    `<path d="${geoPath(feature.geometry)}"/>`).join('');
}

function worldMap(data = state.dashboard.country_counts || [], heat = false) {
  const rows = data.filter(x => x.name !== '中国' && countryLocations[x.name])
    .sort((a, b) => b.count - a.count).slice(0, 9);
  const max = Math.max(1, ...rows.map(x => x.count));
  const labels = rows.map((x, index) => {
    const [px, py] = countryLocations[x.name];
    const score = heat ? x.index : Math.round(x.count / max * 100);
    const radius = 5 + Math.sqrt(score / 100) * 15;
    const tone = score >= 75 ? '#ff7657' : score >= 45 ? '#ffc45d' : '#55dfc0';
    const bloom = heat ? radius + 24 : radius + 12;
    return `<g class="map-marker ${heat ? 'heat-marker' : ''}" data-action="country" data-country="${escapeHtml(x.name)}" tabindex="0" role="button" aria-label="查看${escapeHtml(x.name)}的${x.count}条动态，活力指数${score}"><circle class="marker-bloom" cx="${px}" cy="${py}" r="${bloom}" fill="${tone}"/><circle class="marker-halo" cx="${px}" cy="${py}" r="${radius + 8}" fill="${tone}"/><circle class="marker-core" cx="${px}" cy="${py}" r="${radius}" fill="${tone}"/><text x="${px}" y="${py - radius - 13}" text-anchor="middle">${escapeHtml(x.name)} · ${heat ? x.index : x.count}</text></g>`;
  }).join('');
  const caption = heat ? '色晕与圆点共同表示资讯密度；颜色由青绿、金黄至橙红递进' : '展示资讯量较高的可定位地区，其余见右侧列表';
  return `<div class="world-map ${heat ? 'world-heatmap' : ''}" aria-label="国际数据治理动态热力图"><svg viewBox="0 0 960 410" role="img" aria-label="国际动态涉及地区的热力分布"><defs><pattern id="map-grid" width="60" height="50" patternUnits="userSpaceOnUse"><path d="M 60 0 L 0 0 0 50" fill="none" stroke="#2b5463" stroke-width="1" opacity=".45"/></pattern><filter id="heat-blur"><feGaussianBlur stdDeviation="10"/></filter></defs><rect width="960" height="410" fill="url(#map-grid)"/><g class="map-land">${worldLandPaths()}</g><g class="map-markers">${labels}</g></svg><div class="map-caption">${caption}</div></div>`;
}

function geoInsights(view) {
  const counts = view === 'china' ? (state.dashboard.province_counts || []) : (state.dashboard.country_counts || []).filter(x => x.name !== '中国');
  const max = Math.max(1, ...counts.map(x => x.count));
  const selectAction = view === 'china' ? 'province' : 'country';
  return `<div class="ranking"><div class="panel-title"><span class="kicker">GEOGRAPHIC DISTRIBUTION</span><h2>${view === 'china' ? '省市动态分布' : '国家与地区动态'}</h2><p>${view === 'china' ? '统计动态涉及的省市；固定地方来源以机构所在地标注。' : '报道主要按发布来源所在地标注，政策事件按平台记录的适用地区标注；欧盟单独列示。'}</p></div>
    <div class="ranking-list">${counts.length ? counts.slice(0, 10).map((x, i) => `<button class="rank-row" data-action="${selectAction}" data-${selectAction}="${escapeHtml(x.name)}"><span class="rank-number">${String(i + 1).padStart(2, '0')}</span><span class="rank-name">${escapeHtml(x.name)}<i style="width:${Math.max(7, x.count / max * 100)}%"></i></span><strong>${number(x.count)}</strong></button>`).join('') : '<p class="muted">暂无分布数据</p>'}</div></div>`;
}

function chinaTiles() {
  const counts = Object.fromEntries((state.dashboard.province_counts || []).map(x => [x.name, x.count]));
  const max = Math.max(1, ...Object.values(counts));
  return `<div class="china-tile-panel"><div class="panel-title"><span class="kicker">CHINA COVERAGE</span><h2>各省市动态</h2><p>选择有记录的地区，查看已接入来源发布的相关资讯。</p></div><div class="province-grid">${provinceNames.map(name => {
    const count = counts[name] || 0;
    const level = count ? Math.max(1, Math.ceil(count / max * 4)) : 0;
    return `<button class="province-tile level-${level}" data-action="province" data-province="${name}" ${count ? '' : 'disabled'} aria-label="${name}${count ? count + '条动态' : '暂无收录'}"><span>${name}</span><strong>${count || '—'}</strong></button>`;
  }).join('')}</div><p class="tile-footnote">颜色表示当前收录数量。暂无收录仅表示尚未从接入来源检出相关内容。</p></div>`;
}

function spotlightPanel(view) {
  const panel = state.spotlight;
  if (!panel || state.view !== view) return '';
  const placeLabel = panel.kind === 'province' ? `${panel.name}省市动态档案` : `${panel.name}动态档案`;
  const topicList = panel.topics.length
    ? panel.topics.map(topic => `<span>${escapeHtml(topic.name)} <b>${number(topic.count)}</b></span>`).join('')
    : '<span>暂无主题统计</span>';
  const sourceList = panel.sources.length
    ? panel.sources.map(source => `<span>${escapeHtml(source.source_name)} <b>${number(source.count)}</b></span>`).join('')
    : '<span>暂无来源统计</span>';
  const latest = panel.latest
    ? `${date(panel.latest.published_at)} · ${escapeHtml(panel.latest.title_zh || panel.latest.title)}`
    : '暂无可展示的最新动态';
  return `<section class="location-spotlight" aria-label="${escapeHtml(placeLabel)}"><div class="spotlight-title"><span class="kicker">LOCATION SNAPSHOT</span><h2>${escapeHtml(placeLabel)}</h2><p>基于当前已收录的公开资讯，帮助快速查看该地区的关注议题与来源构成。</p></div><div class="spotlight-stat"><strong>${number(panel.total)}</strong><span>条已收录动态</span></div><div class="spotlight-detail"><span>主要议题</span><div>${topicList}</div></div><div class="spotlight-detail"><span>活跃来源</span><div>${sourceList}</div></div><div class="spotlight-latest"><span>最近动态</span><p>${latest}</p></div></section>`;
}

function renderNews(view = 'news') {
  if (!['news', 'international', 'china'].includes(view)) return;
  const f = state.filters;
  const options = filterOptions();
  const active = Object.values(f).some(Boolean);
  const isActive = state.view === view;
  const items = isActive ? state.articles : [];
  const scopeTotal = view === 'news' ? state.dashboard.total : view === 'china' ? state.dashboard.china_count : state.dashboard.total - state.dashboard.china_count;
  const total = isActive ? state.total : scopeTotal;
  const title = view === 'international' ? '国际动态' : view === 'china' ? '国内动态' : '全部动态';
  const scopeDescription = view === 'international' ? '汇集各地机构发布与媒体报道，追踪国际数据治理政策和实践。' : view === 'china' ? '聚焦中国各省市数据治理进展，汇集机构发布与媒体报道。' : '从全球到中国，检索公开来源发布的数据治理资讯。';
  const geo = view === 'international' ? `<div class="geo-layout">${worldMap()}${geoInsights(view)}</div>` : view === 'china' ? `<div class="geo-layout china-layout">${chinaTiles()}${geoInsights(view)}</div>` : '';
  const countryRows = (state.dashboard.country_counts || []).filter(x => x.name !== '中国');
  const countryTabs = view === 'international' ? `<div class="country-tabs" aria-label="按国家或地区浏览"><button data-action="all-countries" class="${!f.country ? 'active' : ''}">全部地区 <small>${number(scopeTotal)}</small></button>${countryRows.sort((a, b) => (a.name === '欧盟' ? -1 : b.name === '欧盟' ? 1 : b.count - a.count)).map(x => `<button data-action="country" data-country="${escapeHtml(x.name)}" class="${f.country === x.name ? 'active' : ''}">${escapeHtml(x.name)} <small>${number(x.count)}</small></button>`).join('')}</div>` : '';
  const eligibleSources = state.sources.filter(x => x.total > 0 && (view === 'news' || x.scope === view || x.scope === 'mixed'));
  const sourceOptions = kind => eligibleSources.filter(x => kind === 'media' ? x.id.startsWith('media:') : !x.id.startsWith('media:')).map(x => `<option value="${escapeHtml(x.id)}" ${f.source === x.id ? 'selected' : ''}>${escapeHtml(x.name)} · ${number(x.total)}</option>`).join('');
  const exportParams = new URLSearchParams(articleParams());
  exportParams.delete('limit');
  exportParams.delete('offset');
  const exportLink = isActive && total ? `<a class="export-link" href="/api/articles.csv?${exportParams.toString()}" download>下载清单 CSV ↓</a>` : '';
  $(`#${view}-view`).innerHTML = `${heading(view === 'news' ? 'ALL UPDATES' : view === 'china' ? 'CHINA TRACKER' : 'GLOBAL TRACKER', title, scopeDescription)}
    ${view !== 'news' ? `<div class="section-stats"><div><strong>${number(scopeTotal)}</strong><span>条已收录动态</span></div><div><strong>${number(view === 'china' ? state.dashboard.province_count : (state.dashboard.country_counts || []).filter(x => x.name !== '中国').length)}</strong><span>${view === 'china' ? '个有记录的省市' : '类可定位地区或机构'}</span></div><div><strong>${number(eligibleSources.length)}</strong><span>个有记录的来源</span></div></div>${countryTabs}${spotlightPanel(view)}${geo}` : ''}
    <div class="feed-heading"><div><span class="kicker">EXPLORE UPDATES</span><h2>${view === 'news' ? '检索全部资讯' : `浏览${title}`}</h2></div><span>可按关键词、主题、地区和时间查找</span></div>
    <div class="filter-panel"><label class="search-field"><span aria-hidden="true">⌕</span><input id="search-input" type="search" placeholder="搜索标题、摘要或关键词" value="${escapeHtml(f.q)}" aria-label="搜索动态"></label>
      <select id="category-filter" aria-label="按主题筛选"><option value="">全部主题</option>${options.categories}</select>
      ${view === 'china' ? `<select id="province-filter" aria-label="按省市筛选"><option value="">全部省市</option>${options.provinces.map(x => `<option value="${escapeHtml(x)}" ${f.province === x ? 'selected' : ''}>${escapeHtml(x)}</option>`).join('')}</select>` : `<select id="country-filter" aria-label="按来源国家或机构筛选"><option value="">全部来源地区</option>${options.countries.filter(x => view === 'news' || x !== '中国').map(x => `<option value="${escapeHtml(x)}" ${f.country === x ? 'selected' : ''}>${escapeHtml(x)}</option>`).join('')}</select>`}
      <select id="source-filter" aria-label="按来源筛选"><option value="">全部来源</option><optgroup label="机构栏目">${sourceOptions('direct')}</optgroup><optgroup label="公开报道与政策事件">${sourceOptions('media')}</optgroup></select>
      <label class="month-filter"><span>月份</span><input id="month-filter" type="month" value="${escapeHtml(f.month)}" aria-label="按月份筛选"></label>
    </div>
    <div class="result-line"><span>找到 <strong>${number(total)}</strong> 条动态${f.category && isActive ? ` · ${escapeHtml(state.config.categories[f.category])}` : ''}</span><span class="result-actions">${exportLink}${active && isActive ? '<button class="clear-button" data-action="clear-filters">清除筛选 ×</button>' : '<span>按报道发布日期或事件日期从近到远</span>'}</span></div>
    <div class="feed-grid">${items.length ? items.map(x => articleCard(x)).join('') : isActive ? emptyState('没有找到匹配内容', '试试其他关键词，或清除部分筛选条件。') : ''}</div>
    ${isActive && items.length < total ? '<div class="load-more"><button class="outline-button" data-action="more">加载更多动态 <span>↓</span></button></div>' : ''}`;
}

function digestSourceRow(item) {
  const place = item.province || (item.source_country === '未定位' ? '国际来源' : item.source_country);
  return `<article class="digest-source-row"><span>${escapeHtml(place)} · ${escapeHtml(state.config.categories[item.category_id] || '数据治理')}</span><button data-action="detail" data-id="${item.id}">${escapeHtml(item.title_zh || item.title)}</button><small>${escapeHtml(item.source_name)} · ${item.date_kind === 'event' ? '事件日期' : '发布日期'} ${date(item.published_at)}</small></article>`;
}

function analysisSection(report) {
  const analysis = report?.analysis;
  if (!analysis) return `<section class="analysis-panel"><span class="kicker">WEEKLY ANALYSIS</span><h2>主要事件与整合解读</h2><p>本周来源索引已在下方列出，综合分析正在随新增资料更新。</p></section>`;
  const byId = Object.fromEntries(report.items.map(item => [item.id, item]));
  const evidence = ids => `<div class="evidence-links"><span>依据</span>${ids.filter(id => byId[id]).map(id => `<button data-action="detail" data-id="${id}">${escapeHtml(byId[id].title_zh || byId[id].title)} ↗</button>`).join('')}</div>`;
  return `<section class="analysis-panel"><div class="analysis-intro"><span class="kicker">WEEKLY BRIEF</span><h2>本周观察</h2><h3>${escapeHtml(analysis.headline)}</h3><p>${escapeHtml(analysis.overview)}</p></div>
    <div class="digest-events"><span class="kicker">KEY EVENTS</span><h3>主要事件</h3>${analysis.events.map((event, index) => `<article class="digest-event"><span class="point-index">${String(index + 1).padStart(2, '0')}</span><div><h4>${escapeHtml(event.title)}</h4><p>${escapeHtml(event.summary)}</p>${evidence(event.article_ids)}</div></article>`).join('')}</div>
    <div class="analysis-points"><span class="kicker">INTEGRATED ANALYSIS</span><h3>整合分析</h3>${analysis.insights.map((point, index) => `<article class="analysis-point"><span class="point-index">${String(index + 1).padStart(2, '0')}</span><div><h4>${escapeHtml(point.title)}</h4><p>${escapeHtml(point.analysis)}</p>${evidence(point.article_ids)}</div></article>`).join('')}</div></section>`;
}

function renderDigest() {
  const report = state.digest;
  const available = state.digestDates || [];
  const international = (report?.items || []).filter(x => x.source_country !== '中国');
  const china = (report?.items || []).filter(x => x.source_country === '中国');
  const topicText = (report?.topic_counts || []).slice(0, 4).map(x => `<span>${escapeHtml(x.name)} <b>${x.count}</b></span>`).join('');
  $('#digest-view').innerHTML = `${heading('WEEKLY BRIEF', '每周简报', '汇总本周全部已收录资讯，梳理主要事件，并形成有来源依据的整合分析。')}
    <div class="digest-toolbar"><label>选择周次 <select id="digest-date" aria-label="选择周报周次">${available.map(x => `<option value="${x.week_start}" ${x.week_start === report?.week_start ? 'selected' : ''}>${x.week_start}—${x.week_end} · ${x.count} 条</option>`).join('')}</select></label>${report ? `<a class="outline-button" href="/api/digest.md?week=${report.week_start}" download>下载本周简报 ↓</a>` : ''}</div>
    ${report ? `<div class="digest-cover"><div><span class="kicker">GLOBAL DATA GOVERNANCE · WEEKLY</span><h2>${escapeHtml(report.from_date)} — ${escapeHtml(report.through_date)}<br><em>数据治理每周简报</em></h2><p>依据本周已收录的公开来源信息生成，点击每条资讯可查看来源原文。</p></div><div class="digest-cover-stat"><span>本周动态</span><strong>${number(report.total)}</strong><span>记录来源 ${number(report.source_count)} 个</span></div></div>
    <div class="digest-summary"><div><strong>${international.length}</strong><span>国际动态</span></div><div><strong>${china.length}</strong><span>国内动态</span></div><div class="digest-topics"><span>涉及主题</span><div>${topicText || '暂无'}</div></div></div>
    ${analysisSection(report)}
    <section class="digest-section"><div class="section-title"><div><span class="kicker">SOURCE INDEX</span><h2>本周原文资讯</h2><p>保留原文标题、记录来源与直接链接。</p></div></div><div class="source-index-grid">${international.length ? `<div><h3>国际动态 <small>${international.length}</small></h3>${international.map(x => digestSourceRow(x)).join('')}</div>` : ''}${china.length ? `<div><h3>国内动态 <small>${china.length}</small></h3>${china.map(x => digestSourceRow(x)).join('')}</div>` : ''}</div></section>
    <div class="digest-history"><span class="kicker">RECENT WEEKS</span><h2>近期周报</h2><div>${available.slice(0, 10).map(x => `<button class="history-day ${x.week_start === report.week_start ? 'active' : ''}" data-action="digest-week" data-week="${x.week_start}"><span>${x.week_start}<br>${x.week_end}</span><strong>${x.count} 条</strong></button>`).join('')}</div></div>` : emptyState('暂无周报', '采集到公开资讯后即可按周查看。')}
    <div class="coverage-note"><strong>周次与覆盖范围</strong><p>追踪从 2026 年 9 月 1 日开始，周次按周一至周日计算；本周统计截至今天。报道按来源标注的发布日期归入周次，政策事件按事件发生日期归入；后续补录会更新对应周报。判断只针对已收录资料，具体信息请以原文为准。</p></div>`;
}

async function loadDigest(week) {
  try {
    state.digest = await request('/api/digest?week=' + encodeURIComponent(week));
    renderDigest();
    window.scrollTo(0, 0);
  } catch (error) { showError(error.message); }
}

function renderTopics() {
  const counts = Object.fromEntries((state.dashboard.category_counts || []).map(x => [x.category_id, x.count]));
  $('#topics-view').innerHTML = `${heading('TOPICS', '主题浏览', '从数据开放到跨境流动，按议题了解全球数据治理的不同侧面。')}
    ${state.config.sections.map(section => `<section class="topic-section"><div class="section-title"><div><span class="kicker">${section.id === 'open' ? 'OPEN DATA' : 'RELATED ISSUES'}</span><h2>${escapeHtml(section.name)}</h2></div></div><div class="topic-grid">${section.categories.map(c => `<button class="topic-card" data-action="category" data-category="${c.id}"><span class="topic-card-icon" aria-hidden="true">${topicIcon(c.id)}</span><strong>${escapeHtml(c.name)}</strong><small>${number(counts[c.id])} 条动态</small><b aria-hidden="true">↗</b></button>`).join('')}</div></section>`).join('')}`;
}

function renderFavorites() {
  const items = state.favorites;
  $('#favorites-view').innerHTML = `${heading('MY READING LIST', '收藏', '收藏仅保存在当前浏览器中。你可以随时回到这里继续阅读，或将不再需要的资讯移出清单。')}
    <div class="favorites-summary"><div><strong>${number(items.length)}</strong><span>条已收藏资讯</span></div><p>收藏时会保留标题、日期、来源和原文链接；资讯库更新不会影响已有收藏。</p></div>
    <section class="favorites-section"><div class="section-title"><div><span class="kicker">SAVED UPDATES</span><h2>稍后阅读</h2></div></div><div class="feed-grid">${items.length ? items.map(item => articleCard(item)).join('') : emptyState('还没有收藏的资讯', '在任意资讯卡片右上方选择“收藏”，即可把它加入这里。')}</div></section>`;
}

function heatRows(rows, action) {
  return `<div class="heat-list">${rows.length ? rows.map((row, index) => `<button data-action="${action}" data-${action}="${escapeHtml(row.name)}" title="${escapeHtml(row.name)}：${row.count} 条，指数 ${row.index}"><span class="heat-rank">${String(index + 1).padStart(2, '0')}</span><span class="heat-name">${escapeHtml(row.name)}<i style="width:${row.index}%"></i></span><strong>${row.index}</strong><small>${row.count} 条</small></button>`).join('') : '<p class="muted">所选时段暂无可定位资讯</p>'}</div>`;
}

function heatOverview(data) {
  const world = data.world[0];
  const china = data.china[0];
  const located = data.world.reduce((sum, row) => sum + row.count, 0) + data.china.reduce((sum, row) => sum + row.count, 0);
  return `<section class="heat-overview" aria-label="活力热力图摘要">
    <div><span>国际最高热区</span><strong>${world ? escapeHtml(world.name) : '暂无'}</strong><small>${world ? `${number(world.count)} 条 · 指数 ${world.index}` : '暂无可定位资讯'}</small></div>
    <div><span>国内最高热区</span><strong>${china ? escapeHtml(china.name) : '暂无'}</strong><small>${china ? `${number(china.count)} 条 · 指数 ${china.index}` : '暂无可定位资讯'}</small></div>
    <div><span>纳入热力计算</span><strong>${number(located)}</strong><small>${number(data.unlocated)} 条未定位记录未纳入</small></div>
  </section>`;
}

function renderHeatmap() {
  const data = state.heatmap;
  if (!data) return;
  const provinceCounts = Object.fromEntries(data.china.map(row => [row.name, row]));
  $('#heatmap-view').innerHTML = `${heading('DATA GOVERNANCE PULSE', '动态活力热力图', '观察各地近期公开发布的数据治理资讯密度。')}
    <div class="heat-toolbar"><div><span class="kicker">本周热度</span><strong>${data.from_date} — ${data.through_date}</strong></div><div class="heat-periods">${[['week','本周'],['previous','上周'],['all','9月以来']].map(([period,label]) => `<button data-action="heatmap-period" data-period="${period}" class="${state.heatmapPeriod === period ? 'active' : ''}">${label}</button>`).join('')}</div></div>
    <div class="coverage-note"><strong>动态活力指数如何计算</strong><p>${escapeHtml(data.method)}机构发布和报道主要按发布来源所在地归属；经原文核实的报道可按明确涉及的地区归属，政策事件按活动页标注的司法辖区归属。未能可靠定位的 ${number(data.unlocated)} 条动态不计入地区排名。不同语言与地区的来源覆盖尚不均衡，指数不是治理绩效评价。</p></div>
    ${heatOverview(data)}
    <section class="heat-section"><div class="section-title"><div><span class="kicker">GLOBAL PULSE</span><h2>全球地区分布</h2><p>按可定位的地区观察资讯活跃度；欧盟和国际组织单列。</p></div></div><div class="geo-layout">${worldMap(data.world, true)}<div class="ranking"><div class="panel-title"><span class="kicker">INDEX 0—100</span><h2>国际活力指数</h2><p>同一时间范围内相对最高地区计分</p></div>${heatRows(data.world, 'country')}</div></div></section>
    <section class="heat-section"><div class="section-title"><div><span class="kicker">CHINA PULSE</span><h2>中国省市热度矩阵</h2><p>每一格代表一个省级地区，颜色由浅至深表示相对资讯密度。</p></div><div class="heat-legend" aria-label="热力颜色说明"><span>低</span><i></i><i></i><i></i><i></i><span>高</span></div></div><div class="geo-layout china-layout"><div class="china-tile-panel"><div class="province-grid">${provinceNames.map(name => { const row = provinceCounts[name]; const index = row?.index || 0; return `<button class="province-tile level-${index ? Math.max(1, Math.ceil(index / 25)) : 0}" data-action="province" data-province="${name}" ${row ? '' : 'disabled'} title="${name}：${row ? row.count + ' 条，指数 ' + index : '暂无收录'}"><span>${name}</span><strong>${row ? index : '—'}</strong></button>`; }).join('')}</div><p class="tile-footnote">方格数字为相对指数；点击有记录的省市查看资讯。空格仅表示当前接入来源中暂无可靠定位记录。</p></div><div class="ranking"><div class="panel-title"><span class="kicker">INDEX 0—100</span><h2>省市活力指数</h2><p>同一时间范围内相对最高省市计分</p></div>${heatRows(data.china, 'province')}</div></div></section>`;
}

async function loadHeatmap(period) {
  try {
    state.heatmap = await request('/api/heatmap?period=' + period);
    state.heatmapPeriod = period;
    renderHeatmap();
  } catch (error) { showError(error.message); }
}

function topicIcon(id) {
  return ({ law: '§', plan: '↗', scope: '◫', platform: '▦', service: '◇', privacy: '◉',
    activity: '◎', outcome: '✦', international: '◉', dataspace: '⬡',
    intermediary: '↔', commons: '⊙', crossborder: '⇢', ai: '✳' })[id] || '•';
}

function setView(view, retainFilters = false) {
  if (!validViews.has(view)) return;
  if (!retainFilters && ['news', 'international', 'china'].includes(view) && view !== state.view) {
    state.filters = { q: '', category: '', country: '', province: '', source: '', month: '' };
  }
  state.view = view;
  document.querySelectorAll('.view').forEach(el => el.classList.toggle('active', el.id === view + '-view'));
  document.querySelectorAll('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.view === view));
  if (window.location.hash !== `#${view}`) history.replaceState(null, '', `#${view}`);
  $('.main-nav').classList.remove('open');
  $('#menu-button').setAttribute('aria-expanded', 'false');
  window.scrollTo(0, 0);
  if (['news', 'international', 'china'].includes(view)) loadArticles();
}

function toggleFavorite(id) {
  const item = state.articles.find(entry => entry.id === id) || state.featured.find(entry => entry.id === id) ||
    (state.digest?.items || []).find(entry => entry.id === id) || state.favorites.find(entry => entry.id === id);
  if (!item) return showError('请重新打开这条资讯后再收藏');
  const existing = state.favorites.some(entry => entry.id === id);
  state.favorites = existing ? state.favorites.filter(entry => entry.id !== id) : [item, ...state.favorites];
  try { localStorage.setItem('data-governance-favorites', JSON.stringify(state.favorites)); }
  catch { return showError('浏览器未能保存收藏'); }
  renderAll();
}

function openDetail(id) {
  const item = state.articles.find(x => x.id === id) || state.featured.find(x => x.id === id) ||
    (state.digest?.items || []).find(x => x.id === id) || state.favorites.find(x => x.id === id);
  if (!item) return showError('请重新打开这条动态');
  const category = state.config.categories[item.category_id] || '数据治理';
  $('#detail-drawer').innerHTML = `<div class="drawer-top"><span>资讯详情</span><button class="close-button" data-action="close-detail" aria-label="关闭详情">×</button></div><div class="drawer-content">
    <div class="card-meta"><span class="topic-pill">${escapeHtml(category)}</span><span>${escapeHtml(item.record_type)}</span><span>${escapeHtml(item.province || (item.source_country === '未定位' ? '国际来源' : item.source_country) || item.source_region)}</span><span class="meta-dot">·</span><span>${item.date_kind === 'event' ? '事件日期' : '发布日期'} ${date(item.published_at)}</span></div>
    <h2>${escapeHtml(item.title_zh || item.title)}</h2>${item.title_zh ? `<p class="original-title">${escapeHtml(item.title)}</p>` : ''}
    <div class="detail-summary"><span class="kicker">内容概览</span><p>${escapeHtml(item.brief_zh || item.summary || '可打开原文了解详情。')}</p></div>
    <div class="detail-source"><div><span>记录来源</span><strong>${escapeHtml(item.source_name)}</strong></div><div><span>${item.date_kind === 'event' ? '事件日期' : '发布日期'}</span><strong>${date(item.published_at)}</strong></div></div>
    <a class="primary-button detail-link" href="${safeHref(item.url)}" target="_blank" rel="noopener noreferrer">阅读来源原文 <span aria-hidden="true">↗</span></a>
    <p class="detail-footnote">页面内容为公开信息的简要整理。媒体报道的说法尚需以原文及相关机构发布核对。</p>
  </div>`;
  $('#drawer-backdrop').hidden = false;
  $('#detail-drawer').classList.add('open');
  $('#detail-drawer').setAttribute('aria-hidden', 'false');
  document.body.classList.add('drawer-open');
  $('.close-button').focus();
}

function closeDetail() {
  $('#drawer-backdrop').hidden = true;
  $('#detail-drawer').classList.remove('open');
  $('#detail-drawer').setAttribute('aria-hidden', 'true');
  document.body.classList.remove('drawer-open');
}

let toastTimer;
function showError(message) {
  const el = $('#toast');
  el.textContent = message;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 4000);
}

document.addEventListener('click', async event => {
  const el = event.target.closest('[data-action], [data-view]');
  if (!el) return;
  if (el.dataset.view) return setView(el.dataset.view);
  switch (el.dataset.action) {
    case 'category':
      state.filters.category = el.dataset.category;
      return setView('news', true);
    case 'country':
      state.filters = { q: '', category: '', country: el.dataset.country, province: '', source: '', month: '' };
      return setView('international', true);
    case 'all-countries':
      state.filters = { q: '', category: '', country: '', province: '', source: '', month: '' };
      return setView('international', true);
    case 'province':
      if (el.disabled) return;
      state.filters = { q: '', category: '', country: '', province: el.dataset.province, source: '', month: '' };
      return setView('china', true);
    case 'digest-week': return loadDigest(el.dataset.week);
    case 'heatmap-period': return loadHeatmap(el.dataset.period);
    case 'detail': return openDetail(el.dataset.id);
    case 'favorite': return toggleFavorite(el.dataset.id);
    case 'close-detail': return closeDetail();
    case 'clear-filters':
      state.filters = { q: '', category: '', country: '', province: '', source: '', month: '' };
      return loadArticles();
    case 'more': return loadArticles(true);
  }
});

document.addEventListener('change', event => {
  if (event.target.id === 'digest-date') return loadDigest(event.target.value);
  const names = { 'category-filter': 'category', 'country-filter': 'country',
    'province-filter': 'province', 'source-filter': 'source', 'month-filter': 'month' };
  if (!names[event.target.id]) return;
  state.filters[names[event.target.id]] = event.target.value;
  loadArticles();
});

let searchTimer;
document.addEventListener('input', event => {
  if (event.target.id !== 'search-input') return;
  const cursor = event.target.selectionStart;
  state.filters.q = event.target.value;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(async () => {
    await loadArticles();
    const input = $('.view.active #search-input');
    if (input) { input.focus(); input.setSelectionRange(cursor, cursor); }
  }, 300);
});

$('#drawer-backdrop').addEventListener('click', closeDetail);
$('#menu-button').addEventListener('click', () => {
  const open = $('.main-nav').classList.toggle('open');
  $('#menu-button').setAttribute('aria-expanded', String(open));
});
document.addEventListener('keydown', event => { if (event.key === 'Escape') closeDetail(); });
window.addEventListener('hashchange', () => setView(viewFromHash(), true));
loadAll();
