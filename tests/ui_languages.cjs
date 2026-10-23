/* Programmatic DOM regression checks. Requires jsdom; no browser/native UI or GPU. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM, VirtualConsole} = require('jsdom');
const root = path.resolve(__dirname, '..');
const catalog = JSON.parse(fs.readFileSync(path.join(root, 'ui/messages.json'), 'utf8'));
const html = fs.readFileSync(path.join(root, 'ui/index.html'), 'utf8').replace('__FLUX_MESSAGES__', JSON.stringify(catalog)).replace('<script src="/ui/app.js"></script>', '');
const script = fs.readFileSync(path.join(root, 'ui/app.js'), 'utf8');
const results = [];
function check(name, test) { test(); results.push({name, status:'PASS'}); }
const tick = () => new Promise(resolve => setImmediate(resolve));
async function settle() { for (let n = 0; n < 8; n++) await tick(); }
async function make({language, stored, failStorage = false} = {}) {
  const posts = [], errors = [];
  const current = {job:null, active:false};
  const state = {offline:false, failGeneration:false, generationDelay:null};
  const vc = new VirtualConsole(); vc.on('jsdomError', e => errors.push(String(e)));
  const dom = new JSDOM(html, {url:'http://127.0.0.1:8449/' + (language ? '?lang=' + language : '') + '#session=' + 'x'.repeat(43), runScripts:'dangerously', virtualConsole:vc});
  const w = dom.window;
  if (stored) w.localStorage.setItem('flux3-language',stored);
  if (failStorage) Object.defineProperty(w,'localStorage',{get(){throw Error('Storage blocked');}});
  w.setInterval = () => 1;
  w.URL.createObjectURL = () => 'blob:owned-test-image'; w.URL.revokeObjectURL = () => {};
  const preset = {id:'people-portrait', title:'Портрет мастерицы', title_i18n:{ru:'Портрет мастерицы',en:'Portrait of a craftswoman'}, prompt:'A portrait with a sign "МАСТЕР".', width:768,height:768,seed:42};
  const response = (value, ok = true, status = 200) => ({ok,status,json:async()=>value,blob:async()=>new w.Blob(['test PNG'])});
  w.fetch = async (url, options = {}) => {
    if (state.offline) throw Error('Failed to fetch');
    if (options.method === 'POST') posts.push({url, body:JSON.parse(options.body), language:options.headers['Accept-Language']});
    if (url === '/api/config') return response(options.method === 'POST' ? {message_i18n:{ru:'Пути проверены и сохранены',en:'Paths checked and saved'}} : {config:{max_vram_gib:6}, errors:[]});
    if (url === '/api/presets') return response([preset]);
    if (url === '/api/current') return response(current);
    if (url === '/api/generate') {
      if (state.generationDelay) await state.generationDelay;
      if (state.failGeneration) return response({error:'Ошибка', error_i18n:{ru:'Проверьте seed, шаги и CFG',en:'Check the seed, steps and CFG'}},false,400);
      current.active = true;
      current.job = {id:'ui-'+'a'.repeat(16),status:'RUNNING',message:'Генерация изображения: шаг 3 из 16',message_i18n:{ru:'Генерация изображения: шаг 3 из 16',en:'Generating image: step 3 of 16'},progress:33,width:512,height:512,seed:7,steps:16,seconds:30.2};
      return response(current.job,true,202);
    }
    if (url === '/api/cancel') { current.active=false; current.job.status='CANCELLED'; current.job.message_i18n={ru:'Отменено',en:'Cancelled'}; return response({ok:true}); }
    if (url === '/api/shutdown') return response({ok:true});
    if (url.startsWith('/api/image/')) return response({});
    throw Error('Unexpected request: '+url);
  };
  const executable=w.document.createElement('script'); executable.textContent=script; w.document.body.append(executable); await settle();
  const $ = id => w.document.getElementById(id);
  const switchTo = language => $('language-'+language).click();
  return {dom,w,$,switchTo,posts,current,state,errors};
}
(async () => {
  const a = await make();
  const {w,$,switchTo,posts,current,state} = a;
  check('Russian default and all controls enabled when ready',()=>{assert.equal(w.document.documentElement.lang,'ru');assert.equal($('generate').textContent,'Сгенерировать');assert.equal($('generate').disabled,false);});
  $('prompt').value='User text "СОХРАНИТЬ"'; $('width').value='864'; $('height').value='480'; $('seed').value='7'; $('path-llm').value='selected-model.gguf'; $('setup').open=true;
  const form = () => ['prompt','width','height','seed','steps','cfg','preset','size-preset','path-llm'].map(id=>$(id).value);
  const before = form(); switchTo('en');
  check('English labels, placeholders, aria labels, preset titles and status',()=>{assert.equal(w.document.documentElement.lang,'en');assert.equal($('generate').textContent,'Generate');assert.equal($('status').textContent,'Ready to generate');assert.equal($('progress').getAttribute('aria-label'),'Generation progress');assert.match($('prompt').placeholder,/Describe/);assert.equal($('preset').options[1].textContent,'Portrait of a craftswoman');});
  check('Switch preserves all entered fields and expanded settings; no POST',()=>{assert.deepEqual(form(),before);assert.equal($('setup').open,true);assert.equal(posts.length,0);});
  check('Every marked English label matches catalog',()=>{for(const e of w.document.querySelectorAll('[data-i18n]'))assert.equal(e.textContent,catalog.en[e.dataset.i18n]??e.dataset.i18n);});
  check('Language persists in browser and address without altering session',()=>{assert.equal(w.localStorage.getItem('flux3-language'),'en');assert.equal(new URL(w.location).searchParams.get('lang'),'en');assert.equal(w.location.hash,'#session='+'x'.repeat(43));});
  let release; state.generationDelay=new Promise(resolve=>release=resolve); $('generate').click(); await settle(); switchTo('ru');
  check('Switch during submission preserves busy controls and sends one exact payload',()=>{assert.equal(posts.length,1);assert.equal(posts[0].url,'/api/generate');assert.equal(posts[0].language,'en');assert.deepEqual(posts[0].body,{prompt:'User text "СОХРАНИТЬ"',width:864,height:480,seed:7,steps:16,cfg_scale:1});assert.equal($('generate').disabled,true);});
  release(); await settle(); switchTo('en');
  check('Active step translates immediately; progress and cancellation stay live',()=>{assert.equal($('status').textContent,'Generating image: step 3 of 16');assert.equal($('progress').value,33);assert.equal($('cancel').disabled,false);assert.equal(posts.length,1);});
  current.active=false; current.job={...current.job,status:'DONE',progress:100,message_i18n:{ru:'Готово',en:'Done'},image_url:'/api/image/'+current.job.id}; await w.eval('refresh()');
  const image=$('result').src, download=$('download').href;
  switchTo('ru');
  check('Completed PNG and metadata survive language switch',()=>{assert.equal($('result').src,image);assert.equal($('download').href,download);assert.match($('result-meta').textContent,/16 шагов · 30.2 с/);assert.equal($('status').textContent,'Готово');assert.equal(posts.length,1);});
  switchTo('en'); check('English result metadata and original prompt retained',()=>{assert.match($('result-meta').textContent,/16 steps · 30.2 s/);assert.equal($('prompt').value,'User text "СОХРАНИТЬ"');});
  state.failGeneration=true; $('generate').click(); await settle(); switchTo('ru');
  check('Validation error translates without retry and keeps input',()=>{assert.equal($('status').textContent,'Проверьте seed, шаги и CFG');assert.equal(posts.length,2);assert.equal($('prompt').value,'User text "СОХРАНИТЬ"');});
  state.offline=true; await w.eval('refresh()'); switchTo('en');
  check('Failed-to-fetch recovery message translates and never retries generation',()=>{assert.match($('status').textContent,/Cannot connect/);assert.equal($('reconnect').classList.contains('hide'),false);assert.equal(posts.length,2);});
  state.offline=false; $('reconnect').click(); await settle();
  check('Reconnect keeps form and current PNG; no duplicate POST',()=>{assert.deepEqual(form(),before);assert.equal(posts.length,2);assert.equal($('result').src,image);});
  await w.eval('refresh()'); $('shutdown').click(); await settle(); switchTo('ru');
  check('Stopped-app status translates and generate remains disabled',()=>{assert.match($('status').textContent,/Приложение завершено/);assert.equal($('generate').disabled,true);});
  check('No removed history API called and no DOM runtime errors',()=>{assert.equal(posts.some(p=>p.url.includes('/jobs')),false);assert.deepEqual(a.errors,[]);});
  const b=await make({stored:'en'});check('Saved English choice is restored on a fresh page',()=>assert.equal(b.$('generate').textContent,'Generate'));
  const c=await make({language:'ru',stored:'en'});check('Manager language argument overrides older browser preference',()=>assert.equal(c.$('generate').textContent,'Сгенерировать'));
  const d=await make({language:'bad',stored:'invalid'});check('Invalid language safely falls back to Russian',()=>assert.equal(d.w.document.documentElement.lang,'ru'));
  const e=await make({failStorage:true});e.switchTo('en');check('Blocked local storage still allows switching',()=>assert.equal(e.$('generate').textContent,'Generate'));
  for(const item of [a,b,c,d,e])item.dom.window.close();
  console.log(JSON.stringify({status:'PASS',method:'jsdom with mocked HTTP; no browser or native window',checks:results.length,results},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
