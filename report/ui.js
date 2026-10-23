'use strict';
const data=JSON.parse(document.getElementById('report-data').textContent);
const $=id=>document.getElementById(id),runs=data.runs,primary=runs.filter(r=>r.role==='thematic-first-result');
const state={tab:'overview',category:'',family:'fantasy',seed:'42',comparison:'people-portrait',openDetails:new Set()};
const requested=new URLSearchParams(location.hash.slice(1)).get('lang');
let language=['ru','en'].includes(requested)?requested:data.default_language;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const message=key=>data.messages[language][key];
const format=(key,values={})=>message(key).replace(/\{(\w+)\}/g,(_,k)=>String(values[k]??''));
const title=r=>language==='en'?data.english.runs[r.run_id].title:r.title_ru;
const observation=r=>language==='en'?data.english.runs[r.run_id].observation:r.review.observation_ru;
const category=value=>language==='en'?data.english.categories[value]:value;
function openTab(id){
 state.tab=id;
 for(const s of document.querySelectorAll('section[role=tabpanel]'))s.hidden=s.id!==id;
 for(const b of document.querySelectorAll('[data-tab]'))b.setAttribute('aria-selected',String(b.dataset.tab===id));
}
function card(r,label=''){
 if(!r)return '<div class="empty">'+esc(message('unmeasured'))+'</div>';
 const b=r.review.battle;
 return '<article class="card" data-run="'+esc(r.run_id)+'"><img loading="lazy" src="'+r.image_data+'" alt="'+esc(title(r)+', seed '+r.seed+(label?' · '+label:''))+'"><div class="body"><h3>'+esc(label||title(r))+'</h3><div class="meta">'+r.width+'×'+r.height+' · seed '+r.seed+' · '+r.seconds.toFixed(2)+' '+message('seconds')+' · VRAM '+r.peak_gpu_used_mib+' '+message('mib')+'</div>'+(b?Object.entries(b).map(([k,v])=>'<span class="badge '+v+'">'+esc(message(k))+' '+v+'</span>').join(''):'')+'<p>'+esc(observation(r))+'</p><p class="meta">'+esc(message('inscription'))+': '+esc(r.expected_text.length?r.review.observed_text.join(' / '):message('not_requested'))+' · '+esc(message('process_success'))+'</p><a download="'+esc(r.run_id)+'.png" href="'+r.image_data+'">'+esc(message('original_png'))+'</a><details><summary>'+esc(message('prompt_command'))+'</summary><pre>'+esc(r.prompt)+'</pre><pre>'+esc(JSON.stringify(r.command,null,2))+'</pre><p class="meta">SHA256 PNG: '+esc(r.image_sha256)+'</p></details></div></article>';
}
function drawGallery(){
 for(const button of $('category-filter').children)button.setAttribute('aria-pressed',String(button.dataset.category===state.category));
 const shown=primary.filter(r=>!state.category||r.category===state.category);
 $('gallery').innerHTML=shown.map(r=>card(r)).join('');
 $('gallery-count').textContent=format('gallery_count',{count:shown.length});
}
function battlePair(){
 state.family=$('battle-family').value;
 if(state.family==='steampunk'&&$('battle-seed').value==='123')$('battle-seed').value='42';
 state.seed=$('battle-seed').value;
 for(const o of $('battle-seed').options)o.disabled=state.family==='steampunk'&&o.value==='123';
 const seed=Number(state.seed),find=variant=>runs.find(r=>r.family===state.family&&r.variant===variant&&r.seed===seed);
 $('battle-pair').innerHTML=card(find('original'),message('original_prompt'))+card(find('clear'),message('simplified_prompt'));
}
function compare(){
 state.comparison=$('compare-scene').value;
 const id=state.comparison,selected=[id+'-512',id,id+'-1024'].map(cid=>runs.find(r=>r.run_id==='batch-'+cid));
 $('comparison').innerHTML=selected.map(r=>card(r,r.width+'×'+r.height+' · '+title(r))).join('');
}
function render(){
 $('report-shell').innerHTML=data.shells[language];
 document.documentElement.lang=language;document.title=message('title');
 for(const button of document.querySelectorAll('[data-language]'))button.setAttribute('aria-pressed',String(button.dataset.language===language));
 for(const b of document.querySelectorAll('[data-tab]'))b.addEventListener('click',()=>openTab(b.dataset.tab));
 for(const b of document.querySelectorAll('[data-open]'))b.addEventListener('click',()=>openTab(b.dataset.open));
 $('run-count').textContent=data.summary.runs;$('fast-count').textContent=data.summary.within_minute+' / 18';
 $('battle-time').textContent=data.summary.minimum_battle_seconds.toFixed(1)+'–'+data.summary.maximum_battle_seconds.toFixed(1);$('vram').textContent=data.summary.peak_gpu_mib;
 for(const value of ['',...new Set(primary.map(r=>r.category))]){
  const b=document.createElement('button');b.type='button';b.dataset.category=value;b.textContent=value?category(value):message('all_themes');
  b.addEventListener('click',()=>{state.category=value;drawGallery()});$('category-filter').append(b);
 }
 drawGallery();$('battle-family').value=state.family;$('battle-seed').value=state.seed;
 $('battle-family').addEventListener('change',battlePair);$('battle-seed').addEventListener('change',battlePair);battlePair();
 $('battle-all').innerHTML=runs.filter(r=>r.family).sort((a,b)=>a.family.localeCompare(b.family)||a.variant.localeCompare(b.variant)||a.seed-b.seed).map(r=>card(r,title(r)+' · '+message(r.variant==='original'?'original_prompt':'simplified_prompt'))).join('');
 $('compare-scene').value=state.comparison;$('compare-scene').addEventListener('change',compare);compare();
 const dimensions=[...new Set(runs.map(r=>r.width+'×'+r.height))].sort((a,b)=>a.split('×').reduce((x,y)=>x*y)-b.split('×').reduce((x,y)=>x*y));
 const maxTime=Math.max(...runs.map(r=>r.seconds));
 for(const wh of dimensions){
  const v=runs.filter(r=>r.width+'×'+r.height===wh).map(r=>r.seconds);
  $('time-bars').insertAdjacentHTML('beforeend','<div class="bar"><label>'+wh+' · n='+v.length+'</label><span style="width:'+Math.max(...v)/maxTime*55+'%"></span><b>'+Math.min(...v).toFixed(1)+'–'+Math.max(...v).toFixed(1)+' '+message('seconds')+'</b></div>');
 }
 $('gui-result').textContent=format('gui_result',{seconds:data.gui.public_smoke.seconds.toFixed(1)});
 $('manager-result').textContent=format('manager_result',{tests:data.manager.automated_tests.count,seconds:data.manager.real_worker.seconds.toFixed(1)});
 $('gui-screenshot').src=data.gui_image;
 $('reproduce-text').textContent=language==='en'?data.guides.en.reproduction:data.reproduction;
 $('interface-text').textContent=language==='en'?data.guides.en.interface:data.interface;
 $('toolkit-result').textContent=message(data.summary.toolkit_png_equal?'toolkit_equal':'toolkit_different');
 for(const r of runs){
  const tr=document.createElement('tr');tr.dataset.run=r.run_id;
  for(const [v,cls] of [[r.run_id,''],[r.width+'×'+r.height+' / '+r.seed,'num'],[r.seconds.toFixed(2),'num'],[r.sampling_seconds.toFixed(2),'num'],[r.peak_gpu_used_mib,'num'],[r.review.observed_text.join(' / ')||'–',''],[r.review.battle?.overall||message('not_assessed'),'']]){const td=document.createElement('td');td.textContent=v;td.className=cls;tr.append(td)}
  $('results-body').append(tr);
 }
 for(const s of data.sources){
  const translated=language==='ru'?data.source_translations[s.id]:null;
  const li=document.createElement('li'),a=document.createElement('a');a.href=s.url;a.textContent=translated?.title||s.title;
  li.append(a,document.createTextNode(' · '+(translated?.checked||s.checked)+' · '+(translated?.applied||s.applied)));$('sources').append(li);
 }
 openTab(state.tab);
}
for(const button of document.querySelectorAll('[data-language]'))button.addEventListener('click',()=>{
 const next=button.dataset.language;if(next===language)return;
 state.openDetails=new Set([...document.querySelectorAll('#report-shell details[open]')].map(el=>el.querySelector('pre')?.id||el.querySelector('#battle-all')?.id).filter(Boolean));
 const scroll=window.scrollY;language=next;render();
 for(const id of state.openDetails){const el=$(id);if(el?.closest('details'))el.closest('details').open=true}
 try{history.replaceState(null,'','#lang='+language)}catch{}
 if(window.scrollY!==scroll)window.scrollTo(0,scroll);
});
render();
