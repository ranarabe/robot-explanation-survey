let records = JSON.parse(localStorage.getItem('robotStudyRecords') || '[]');
let selectedId = null;

const $ = selector => document.querySelector(selector);
const escapeHtml = value => String(value ?? '—').replace(/[&<>'"]/g, char => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' }[char]));
const languageName = code => ({ en:'English', fr:'Français', es:'Español', ar:'العربية' }[code] || code || '—');
const formatRecordedAt = value => { if (!value) return '—'; const date = new Date(value); return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }); };
const universityValues = ['University degree', 'Diplôme universitaire', 'Título universitario', 'شهادة جامعية'];
const noQuestionValue = '__NO_ADDITIONAL_QUESTION__';
const stageGroups = {
  baseline: { title: 'Stage 1 · Baseline — no explanation', keys: ['preUnderstanding', 'preInternal', 'preTrust', 'questionRobot', 'preExplanation'] },
  contrastive: { title: 'Stage 2 · Contrastive — why A instead of B?', keys: ['choiceQuestion', 'choiceQuestionAnswer', 'choiceQuestionRating', 'postInternal', 'questionHelped', 'postTrust', 'additionalQuestion', 'postExplanation'] },
  counterfactual: { title: 'Stage 3 · Counterfactual — what if A instead of B?', keys: ['counterfactualQuestion', 'counterfactualQuestionAnswer', 'counterfactualQuestionRating', 'counterfactualInternal', 'counterfactualHelped', 'counterfactualTrust', 'preferredQuestion', 'preferredQuestionWhy', 'counterfactualAdditional', 'counterfactualExplanation'] },
  mixed: { title: 'Stage 4 · Mixed questions', keys: ['mixedQuestion', 'mixedQuestionAnswer', 'mixedQuestionRating', 'mixedInternal', 'mixedHelped', 'mixedTrust', 'mixedAdditional', 'mixedExplanation'] },
  discovery: { title: 'Stage 5 · Discovery', keys: ['cubeOrder'] },
  validation: { title: 'Stage 6 · Validation', keys: ['robotObservation'] }
};

function persist() { localStorage.setItem('robotStudyRecords', JSON.stringify(records)); }
function upsert(record) { const index = records.findIndex(item => item.participantId === record.participantId); if (index >= 0) records[index] = record; else records.push(record); }
function renderStats() {
  const ages = records.map(record => Number(record.demographics?.age)).filter(Boolean);
  const languages = records.reduce((counts, record) => { const key = record.surveyLanguage || '—'; counts[key] = (counts[key] || 0) + 1; return counts; }, {});
  const popularLanguage = Object.entries(languages).sort((a,b) => b[1] - a[1])[0]?.[0];
  $('#stat-participants').textContent = records.length;
  $('#stat-age').textContent = ages.length ? Math.round(ages.reduce((a,b) => a + b, 0) / ages.length) : '—';
  $('#stat-language').textContent = popularLanguage ? languageName(popularLanguage) : '—';
  $('#stat-university').textContent = records.filter(record => universityValues.includes(record.demographics?.education)).length;
  $('#stage-baseline-count').textContent = `${records.filter(record => stageGroups.baseline.keys.some(key => record.responses?.[key])).length} participant${records.filter(record => stageGroups.baseline.keys.some(key => record.responses?.[key])).length === 1 ? '' : 's'}`;
  $('#stage-contrastive-count').textContent = `${records.filter(record => stageGroups.contrastive.keys.some(key => record.responses?.[key])).length} participant${records.filter(record => stageGroups.contrastive.keys.some(key => record.responses?.[key])).length === 1 ? '' : 's'}`;
  $('#stage-counterfactual-count').textContent = `${records.filter(record => stageGroups.counterfactual.keys.some(key => record.responses?.[key])).length} participant${records.filter(record => stageGroups.counterfactual.keys.some(key => record.responses?.[key])).length === 1 ? '' : 's'}`;
  $('#stage-mixed-count').textContent = `${records.filter(record => stageGroups.mixed.keys.some(key => record.responses?.[key])).length} participant${records.filter(record => stageGroups.mixed.keys.some(key => record.responses?.[key])).length === 1 ? '' : 's'}`;
  $('#stage-discovery-count').textContent = `${records.filter(record => stageGroups.discovery.keys.some(key => record.responses?.[key])).length} participant${records.filter(record => stageGroups.discovery.keys.some(key => record.responses?.[key])).length === 1 ? '' : 's'}`;
  $('#stage-validation-count').textContent = `${records.filter(record => stageGroups.validation.keys.some(key => record.responses?.[key])).length} participant${records.filter(record => stageGroups.validation.keys.some(key => record.responses?.[key])).length === 1 ? '' : 's'}`;
  $('#record-count').textContent = `${records.length} record${records.length === 1 ? '' : 's'}`;
}
function renderTable() {
  const table = $('#participant-table');
  $('#empty-state').style.display = records.length ? 'none' : 'block';
  table.innerHTML = records.map(record => `<tr class="${record.participantId === selectedId ? 'active' : ''}" data-id="${escapeHtml(record.participantId)}"><td>${escapeHtml(record.participantId)}</td><td>${escapeHtml(languageName(record.surveyLanguage))}</td><td>${escapeHtml(record.demographics?.age)}</td><td>${escapeHtml(record.demographics?.education)}</td><td>${escapeHtml(formatRecordedAt(record.updatedAt || record.exportedAt || record.startedAt))}</td></tr>`).join('');
  table.querySelectorAll('tr').forEach(row => row.addEventListener('click', () => { selectedId = row.dataset.id; render(); }));
}
function renderDetail() {
  const record = records.find(item => item.participantId === selectedId);
  if (!record) { $('#detail-title').textContent = 'Choose a participant'; $('#delete-record').hidden = true; $('#participant-detail').innerHTML = '<div class="empty-state">Select a participant from the table to view their answers.</div>'; return; }
  $('#delete-record').hidden = false;
  $('#detail-title').textContent = record.participantId;
  const demographics = Object.entries(record.demographics || {});
  const responses = record.responses || {};
  const rows = entries => entries.length ? entries.map(([key,value]) => `<div class="detail-row"><span>${escapeHtml(formatLabel(key))}</span><b>${escapeHtml(value === noQuestionValue ? 'No additional question' : value)}</b></div>`).join('') : '<div class="empty-state">No data saved.</div>';
  const stageRows = group => rows(group.keys.filter(key => responses[key]).map(key => [key, responses[key]]));
  $('#participant-detail').innerHTML = `<div class="detail-block"><h3>Participant profile</h3><div class="detail-row"><span>Survey language</span><b>${escapeHtml(languageName(record.surveyLanguage))}</b></div><div class="detail-row"><span>Last response saved</span><b>${escapeHtml(formatRecordedAt(record.updatedAt || record.exportedAt || record.startedAt))}</b></div>${record.dinosaurFact ? `<div class="detail-row"><span>Reward dinosaur fact</span><b>${escapeHtml(record.dinosaurFact)}</b></div>` : ''}${rows(demographics)}</div><div class="detail-block stage-detail baseline-detail"><h3>${stageGroups.baseline.title}</h3>${stageRows(stageGroups.baseline)}</div><div class="detail-block stage-detail contrastive-detail"><h3>${stageGroups.contrastive.title}</h3>${stageRows(stageGroups.contrastive)}</div><div class="detail-block stage-detail counterfactual-detail"><h3>${stageGroups.counterfactual.title}</h3>${stageRows(stageGroups.counterfactual)}</div><div class="detail-block stage-detail mixed-detail"><h3>${stageGroups.mixed.title}</h3>${stageRows(stageGroups.mixed)}</div><div class="detail-block stage-detail discovery-detail"><h3>${stageGroups.discovery.title}</h3>${stageRows(stageGroups.discovery)}</div><div class="detail-block stage-detail validation-detail"><h3>${stageGroups.validation.title}</h3>${stageRows(stageGroups.validation)}</div>`;
}
function formatLabel(key) { if (key.endsWith('Answer')) return 'Robot answer'; if (key.endsWith('Rating')) return 'Answer relevance'; return key.replace(/([A-Z])/g, ' $1').replace(/^./, char => char.toUpperCase()); }
function render() { renderStats(); renderTable(); renderDetail(); }

$('#import-files').addEventListener('change', event => { [...event.target.files].forEach(file => { const reader = new FileReader(); reader.onload = () => { try { const imported = JSON.parse(reader.result); if (Array.isArray(imported)) imported.forEach(upsert); else if (imported.participantId) upsert(imported); persist(); render(); } catch { window.alert(`Could not read ${file.name} as JSON.`); } }; reader.readAsText(file); }); event.target.value = ''; });
$('#export-all').addEventListener('click', () => { const blob = new Blob([JSON.stringify(records, null, 2)], { type: 'application/json' }); const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = 'robot-explanation-all-records.json'; link.click(); });
$('#delete-record').addEventListener('click', () => { const record = records.find(item => item.participantId === selectedId); if (!record) return; if (!window.confirm(`Delete all saved responses for ${record.participantId}? This cannot be undone.`)) return; records = records.filter(item => item.participantId !== selectedId); persist(); selectedId = null; render(); });
render();
