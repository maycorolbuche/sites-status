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
const calendar = new Intl.DateTimeFormat('pt-BR', { timeZone: 'America/Sao_Paulo' });
const clock = new Intl.DateTimeFormat('pt-BR', {
  hour: '2-digit', minute: '2-digit', timeZone: 'America/Sao_Paulo',
});
const periodLinks = document.querySelectorAll('[data-period]');
const dayPriority = ['down', 'changed', 'pending', 'unverified', 'up'];
const selectedPeriod = new URLSearchParams(location.search).get('period') === 'today' ? 'today' : 'days';
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
  const siteLink = link(site.name, site.url);
  siteLink.target = '_blank';
  siteLink.rel = 'noopener noreferrer';
  title.append(siteLink);
  const badge = element('span', labels[site.status], 'badge');
  badge.dataset.tone = site.status;
  header.append(title, badge);

  const meta = element('div', '', 'site-meta');
  meta.append(element('span', `${percent.format(site.uptime / 100)} de disponibilidade`));
  if (site.responseMs !== null) meta.append(element('span', `${site.responseMs} ms`));
  if (site.reason) meta.append(element('span', site.reason));
  if (site.approvalUrl) meta.append(link('Revisar hash inicial', site.approvalUrl));

  card.append(header, meta, renderHistory(site));
  return card;
}

function formatSlot(index) {
  const hour = String(Math.floor(index / 4)).padStart(2, '0');
  const minute = String(index % 4 * 15).padStart(2, '0');
  return `${hour}:${minute}`;
}

function renderHistory(site) {
  const isToday = selectedPeriod === 'today';
  const history = element('div');
  const bars = element('div', '', isToday ? 'bars bars-today' : 'bars');
  bars.setAttribute('role', 'list');
  bars.setAttribute('aria-label', isToday ? `Checagens de hoje de ${site.name}` : `Histórico diário de ${site.name}`);
  const details = element('div', '', 'history-details');
  details.setAttribute('aria-live', 'polite');
  const currentDate = calendar.format(new Date());
  const timelineDate = site.today && calendar.format(new Date(`${site.today.date}T12:00:00Z`));
  const slots = timelineDate === currentDate ? site.today.slots : {};
  const entries = isToday ? Array.from({ length: 96 }, (_, index) => {
    const runs = slots[index] ?? [];
    return {
      tone: runs.at(-1)?.status ?? 'none',
      label: `${formatSlot(index)} · ${runs.map(run => `${clock.format(new Date(run.at))} ${labels[run.status]}`).join(' · ') || labels.none}`,
      interactive: runs.length > 0,
    };
  }) : site.days.map(day => ({
    tone: dayPriority.find(key => day.checks[key]) ?? 'none',
    label: `${day.date.split('-').reverse().join('/')} · ${Object.entries(day.checks)
      .map(([status, count]) => `${labels[status]}: ${count}`).join(' · ') || labels.none}`,
  }));

  for (const { tone, label, interactive } of entries) {
    const item = element('span', '', 'bar');
    item.dataset.tone = tone;
    item.title = label;
    item.setAttribute('role', 'listitem');
    if (interactive) {
      const button = element('button', '', 'bar-hit');
      button.type = 'button';
      button.setAttribute('aria-label', label);
      button.addEventListener('click', () => { details.textContent = label; });
      item.append(button);
    } else {
      item.setAttribute('aria-label', label);
    }
    bars.append(item);
  }
  const axis = element('div', '', 'axis');
  axis.append(element('span', isToday ? '00:00' : '90 dias'), element('span', isToday ? '23:45' : 'Hoje'));
  history.append(bars, axis);
  if (isToday) history.append(details);
  return history;
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

for (const option of periodLinks) {
  if (option.dataset.period === selectedPeriod) option.setAttribute('aria-current', 'page');
}

refresh();
setInterval(refresh, 60_000);
