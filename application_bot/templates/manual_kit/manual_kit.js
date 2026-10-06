'use strict';
async function copyText(id) {
  const value = document.getElementById(id).textContent;
  try { await navigator.clipboard.writeText(value); }
  catch (_) {
    const area = document.createElement('textarea');
    area.value = value;
    document.body.appendChild(area);
    area.select();
    const copied = document.execCommand('copy');
    area.remove();
    if (!copied) { document.getElementById('copy-status').textContent = '复制失败，请手动选择文本'; return; }
  }
  document.getElementById('copy-status').textContent = '已复制';
}
document.querySelectorAll('[data-copy]').forEach(button => {
  button.addEventListener('click', () => copyText(button.dataset.copy));
});
const campaign = document.getElementById('campaign');
if (campaign) {
  const cards = [...document.querySelectorAll('.card[data-rank]')];
  const prefix = campaign.dataset.progressKey;
  const statuses = new Set(['未开始', '填写中', '已提交', '受阻', '跳过']);
  let storageFailed = false;
  function updateProgress() {
    const count = cards.filter(c => document.getElementById('status-' + c.dataset.rank).value === '已提交').length;
    document.getElementById('progress').textContent = count + ' / ' + cards.length + ' 已提交（你本人登记）';
  }
  cards.forEach(card => {
    const rank = card.dataset.rank;
    const select = document.getElementById('status-' + rank);
    const receipt = document.getElementById('receipt-' + rank);
    try {
      const saved = JSON.parse(localStorage.getItem(prefix + rank) || 'null');
      if (saved && statuses.has(saved.status)) select.value = saved.status;
      if (saved && typeof saved.receipt === 'string') receipt.value = saved.receipt;
    } catch (_) { storageFailed = true; }
    const save = () => {
      try { localStorage.setItem(prefix + rank, JSON.stringify({status: select.value, receipt: receipt.value})); }
      catch (_) { document.getElementById('copy-status').textContent = '本地进度无法保存，请立即导出进度'; }
      updateProgress();
    };
    select.addEventListener('change', save);
    receipt.addEventListener('input', save);
  });
  if (storageFailed) document.getElementById('copy-status').textContent = '部分本地进度无法读取，请保留原记录并检查导出备份';
  document.querySelectorAll('[data-filter]').forEach(button => {
    button.addEventListener('click', () => cards.forEach(card => {
      card.hidden = button.dataset.filter !== 'all' && card.dataset.kind !== button.dataset.filter;
    }));
  });
  document.getElementById('export-progress').addEventListener('click', () => {
    const rows = cards.map(card => ({
      rank: Number(card.dataset.rank),
      status: document.getElementById('status-' + card.dataset.rank).value,
      receipt: document.getElementById('receipt-' + card.dataset.rank).value
    }));
    const url = URL.createObjectURL(new Blob([JSON.stringify(rows, null, 2)], {type: 'application/json'}));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'manual' + cards.length + '_progress.json';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  updateProgress();
}
