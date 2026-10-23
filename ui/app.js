'use strict';
const $ = id => document.getElementById(id);
const messages = window.FLUX3_MESSAGES;
const validLanguage = value => value === 'ru' || value === 'en';
let storedLanguage;
try { storedLanguage = localStorage.getItem('flux3-language'); } catch (_) {}
const requestedLanguage = new URLSearchParams(location.search).get('lang');
let lang = validLanguage(requestedLanguage) ? requestedLanguage : validLanguage(storedLanguage) ? storedLanguage : 'ru';
const session = new URLSearchParams(location.hash.slice(1)).get('session') || '';
let presets = [], ready = false, busy = false, lastImage = null, blobUrl = null, resultJob = null;
let polling = false, stopped = false, connected = true, uiError = null, initialized = false;
let currentStatus = {key: 'checking_settings'}, statusError = false, configStatus = '';
const fields = {sd_cli:'engine_label', diffusion_model:'field_model', llm:'field_qwen', vae:'VAE', cuda_bin:'field_cuda', cuda_runtime_dir:'field_dll', max_vram_gib:'field_vram'};
const tr = (key, values = {}) => (messages[lang][key] ?? key).replace(/\{(\w+)\}/g, (_, name) => String(values[name] ?? ''));
function display(value) {
  if (value && typeof value === 'object') return value.key ? tr(value.key, value.values) : value[lang] ?? value.ru ?? '';
  return value ?? '';
}
function jobMessage(job) { return job.message_i18n || job.message; }
function errorDisplay(error) { return error.display || error.message; }
function localizedError(key) { const error = Error(tr(key)); error.display = {key}; return error; }
function persistLanguage() { try { localStorage.setItem('flux3-language', lang); } catch (_) {} }
function renderLanguage() {
  document.documentElement.lang = lang;
  document.title = tr('ui_title');
  for (const element of document.querySelectorAll('[data-i18n]')) element.textContent = tr(element.dataset.i18n);
  $('prompt').placeholder = tr('prompt_placeholder');
  $('progress').setAttribute('aria-label', tr('generation_progress'));
  $('result').alt = tr('result_alt');
  for (const language of ['ru', 'en']) $('language-' + language).setAttribute('aria-pressed', String(language === lang));
  for (const option of $('preset').options) {
    const preset = presets.find(p => p.id === option.value);
    option.textContent = preset ? display(preset.title_i18n || preset.title) : tr('custom_prompt');
  }
  $('status').textContent = display(currentStatus);
  $('status').classList.toggle('error', statusError);
  $('config-status').textContent = Array.isArray(configStatus) ? configStatus.map(display).join('; ') : display(configStatus);
  if (resultJob) $('result-meta').textContent = tr('result_meta', {...resultJob, seconds: Number(resultJob.seconds).toFixed(1)});
}
function setLanguage(value) {
  if (!validLanguage(value)) return;
  lang = value; persistLanguage();
  const address = new URL(location.href); address.searchParams.set('lang', lang);
  history.replaceState(null, '', address);
  renderLanguage();
}
for (const language of ['ru', 'en']) $('language-' + language).addEventListener('click', () => setLanguage(language));
persistLanguage();
renderLanguage();

async function request(path, body) {
  const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 15000);
  try {
    return await fetch(path, {method:body === undefined ? 'GET' : 'POST', headers:{'X-Session':session, 'Accept-Language':lang, ...(body === undefined ? {} : {'Content-Type':'application/json'})}, ...(body === undefined ? {} : {body:JSON.stringify(body)}), signal:controller.signal});
  } catch (cause) {
    connected = false;
    const error = localizedError('connection_error'); error.connection = true; throw error;
  } finally { clearTimeout(timeout); }
}
async function api(path, body) {
  const response = await request(path, body), value = await response.json();
  if (!response.ok) {
    const error = Error(value.error || tr('request_failed'));
    error.display = value.error_i18n || value.error || {key:'request_failed'};
    if (response.status === 403) { connected = false; error.connection = true; }
    throw error;
  }
  return value;
}
function status(message, error = false) {
  currentStatus = message; statusError = error;
  $('status').textContent = display(message); $('status').classList.toggle('error', error);
}
function buttons() {
  $('generate').disabled = !ready || busy || stopped || !connected;
  $('cancel').disabled = !busy || stopped || !connected;
  $('save-config').disabled = busy || stopped || !connected;
  $('reconnect').classList.toggle('hide', connected || stopped);
}
function showError(error) { uiError = errorDisplay(error); status(uiError, true); buttons(); }
function settings(config) {
  $('config-fields').replaceChildren();
  for (const [key, label] of Object.entries(fields)) {
    const l = document.createElement('label'), span = document.createElement('span');
    span.dataset.i18n = label; span.textContent = tr(label); l.append(span);
    const input = document.createElement('input'); input.id = 'path-' + key; input.value = config[key] ?? ''; input.type = key === 'max_vram_gib' ? 'number' : 'text';
    if (key === 'max_vram_gib') { input.min = '1'; input.max = '6'; input.step = '.5'; }
    l.htmlFor = input.id; l.append(input); $('config-fields').append(l);
  }
}
async function init() {
  try {
    const config = await api('/api/config');
    if (!$('config-fields').children.length) settings(config.config);
    ready = !config.errors.length; connected = true; uiError = null;
    if (!ready) {
      $('setup').open = true; uiError = {key:'set_paths'};
      configStatus = config.errors_i18n ? {ru:config.errors_i18n.ru.join('; '), en:config.errors_i18n.en.join('; ')} : config.errors.join('; ');
    }
    presets = await api('/api/presets');
    const oldPreset = $('preset').value;
    $('preset').replaceChildren();
    const custom = document.createElement('option'); custom.value = 'custom'; $('preset').append(custom);
    for (const p of presets) { const option = document.createElement('option'); option.value = p.id; $('preset').append(option); }
    $('preset').value = [...$('preset').options].some(o => o.value === oldPreset) ? oldPreset : 'custom';
    if (!initialized) { const first = presets.find(p => p.id === 'people-portrait'); if (first && !$('prompt').value) $('prompt').value = first.prompt; }
    initialized = true; status(uiError || {key:'ready'}, Boolean(uiError)); renderLanguage(); buttons(); await refresh();
  } catch (error) { showError(error); }
}
$('preset').addEventListener('change', () => {
  const p = presets.find(p => p.id === $('preset').value); if (!p) return;
  $('prompt').value = p.prompt; $('width').value = p.width; $('height').value = p.height; $('seed').value = p.seed;
  const size = p.width + 'x' + p.height; $('size-preset').value = [...$('size-preset').options].some(o => o.value === size) ? size : 'custom';
});
$('size-preset').addEventListener('change', () => { const value = $('size-preset').value; if (value === 'custom') return; const [width,height] = value.split('x'); $('width').value = width; $('height').value = height; });
for (const id of ['width','height']) $(id).addEventListener('input', () => { $('size-preset').value = 'custom'; });
$('save-config').addEventListener('click', async () => {
  const config = {}; for (const key of Object.keys(fields)) config[key] = key === 'max_vram_gib' ? Number($('path-' + key).value) : $('path-' + key).value;
  try {
    const result = await api('/api/config', config); ready = true; uiError = null; configStatus = result.message_i18n || result.message;
    status({key:'ready'}); $('setup').open = false;
  } catch (error) { ready = false; configStatus = errorDisplay(error); showError(error); }
  renderLanguage(); buttons();
});
$('generate').addEventListener('click', async () => {
  if (busy || !ready || !connected) return;
  busy = true; uiError = null; buttons(); status({key:'starting'});
  try {
    await api('/api/generate', {prompt:$('prompt').value, width:Number($('width').value), height:Number($('height').value), seed:Number($('seed').value), steps:Number($('steps').value), cfg_scale:Number($('cfg').value)});
    resetImage(); await refresh();
  } catch (error) { busy = false; showError(error); }
});
$('cancel').addEventListener('click', async () => { try { uiError = null; await api('/api/cancel', {}); await refresh(); } catch (error) { showError(error); } });
$('reconnect').addEventListener('click', () => init());
async function showImage(job) {
  resultJob = job;
  $('result-meta').textContent = tr('result_meta', {...job, seconds:Number(job.seconds).toFixed(1)});
  if (!job.image_url || lastImage === job.id) return;
  const response = await request(job.image_url); if (!response.ok) throw localizedError('image_unavailable');
  const blob = await response.blob(); if (blobUrl) URL.revokeObjectURL(blobUrl); blobUrl = URL.createObjectURL(blob);
  $('result').src = blobUrl; $('result').classList.remove('hide'); $('placeholder').classList.add('hide');
  $('download').href = blobUrl; $('download').download = job.id + '.png'; $('download').classList.remove('hide'); lastImage = job.id;
}
function resetImage() {
  if (blobUrl) URL.revokeObjectURL(blobUrl); blobUrl = null; lastImage = null; resultJob = null;
  $('result').removeAttribute('src'); $('result').classList.add('hide');
  $('download').removeAttribute('href'); $('download').classList.add('hide');
  $('result-meta').textContent = ''; $('placeholder').classList.remove('hide');
}
async function refresh() {
  if (polling || stopped) return; polling = true;
  try {
    const wasOffline = !connected, value = await api('/api/current'); connected = true;
    if (!initialized) { polling = false; await init(); return; }
    if (wasOffline) uiError = null;
    busy = Boolean(value.active);
    const job = value.job;
    if (job) {
      if (!uiError) status(jobMessage(job), job.status === 'FAILED');
      $('progress').value = job.progress || 0;
      if (job.status === 'DONE') await showImage(job);
      else if (lastImage && lastImage !== job.id) resetImage();
    } else {
      if (lastImage) resetImage();
      if (!uiError) status({key:ready ? 'ready' : 'set_paths'});
    }
    buttons();
  } catch (error) { showError(error); } finally { polling = false; }
}
$('shutdown').addEventListener('click', async () => { try { await api('/api/shutdown', {}); stopped = true; busy = false; buttons(); status({key:'app_stopped'}); } catch (error) { showError(error); } });
init(); setInterval(() => refresh(), 1200);
