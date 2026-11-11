const labels = {
  up: 'Operacional',
  changed: 'Alteração detectada',
  down: 'Fora do ar',
  pending: 'Aguardando aprovação inicial',
  unverified: 'Integridade não verificada',
  none: 'Sem dados',
};
const timestamp = new Intl.DateTimeFormat('pt-BR', {
  dateStyle: 'short', timeStyle: 'short', timeZone: 'America/Sao_Paulo',
});
const percent = new Intl.NumberFormat('pt-BR', { style: 'percent', maximumFractionDigits: 2 });
const summary = document.querySelector('#summary');
const sites = document.querySelector('#sites');
const updated = document.querySelector('#updated');

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function link(text, value) {
  const node = element('a', text);
  const url = new URL(value, location.href);
  if (['https:', 'http:'].includes(url.protocol)) node.href = url.href;
  return node;
}

function renderSite(site) {
  const card = element('article', '', 'site');
  const header = element('div', '', 'site-header');
  const title = element('h2');
  title.append(link(site.name, site.url));
  const badge = element('span', labels[site.status], 'badge');
  badge.dataset.tone = site.status;
  header.append(title, badge);

  const meta = element('div', '', 'site-meta');
  meta.append(element('span', `${percent.format(site.uptime / 100)} de disponibilidade`));
  if (site.responseMs !== null) meta.append(element('span', `${site.responseMs} ms`));
  if (site.reason) meta.append(element('span', site.reason));
  if (site.approvalUrl) meta.append(link('Revisar hash inicial', site.approvalUrl));

  const bars = element('div', '', 'bars');
  bars.setAttribute('role', 'list');
  bars.setAttribute('aria-label', `Histórico diário de ${site.name}`);
  for (const day of site.days) {
    const tone = ['down', 'changed', 'pending', 'unverified', 'up'].find(key => day.checks[key]) ?? 'none';
    const bar = element('span', '', 'bar');
    const counts = Object.entries(day.checks).map(([status, count]) => `${labels[status]}: ${count}`);
    bar.dataset.tone = tone;
    bar.title = `${day.date.split('-').reverse().join('/')} · ${counts.join(' · ') || labels.none}`;
    bar.setAttribute('role', 'listitem');
    bar.setAttribute('aria-label', bar.title);
    bars.append(bar);
  }
  const axis = element('div', '', 'axis');
  axis.append(element('span', '90 dias'), element('span', 'Hoje'));
  card.append(header, meta, bars, axis);
  return card;
}

function render(data) {
  const date = new Date(data.updatedAt);
  const stale = Date.now() - date.getTime() > 35 * 60 * 1000;
  const active = new Set(data.sites.map(site => site.status));
  const tone = stale ? 'pending' : ['down', 'changed', 'unverified', 'pending', 'up'].find(key => active.has(key)) ?? 'none';
  const summaries = {
    down: 'Há sites fora do ar',
    changed: 'Há alterações para revisar',
    unverified: 'Há sites com integridade não verificada',
    pending: 'Há sites aguardando aprovação inicial',
    up: 'Todos os sites estão operacionais',
    none: 'Nenhum site configurado',
  };
  summary.dataset.tone = tone;
  summary.textContent = stale ? 'Dados desatualizados' : summaries[tone];
  sites.replaceChildren(...data.sites.map(renderSite));
  updated.textContent = `Última checagem · ${timestamp.format(date)} (Brasília)`;
}

async function refresh() {
  try {
    const response = await fetch('./status.json', { cache: 'no-store' });
    if (!response.ok) throw new Error('Status indisponível');
    render(await response.json());
  } catch {
    summary.dataset.tone = 'pending';
    summary.textContent = 'Não foi possível atualizar o status';
  }
}

refresh();
setInterval(refresh, 60_000);
