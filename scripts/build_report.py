"""Rebuild the self-contained report from stored evidence; never starts a model."""
import argparse
import base64
import csv
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import re
import statistics

ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def published_files():
    for p in sorted(ROOT.rglob('*')):
        if not p.is_file():continue
        rel=p.relative_to(ROOT).as_posix()
        if any(x in {'.git','.build-env','.build-work','dist','__pycache__','models','runtime','downloads','ui-data','outputs','local'} for x in p.relative_to(ROOT).parts):continue
        if p.name in {'MANIFEST.json','config.local.json','app-state.json','app-session.json','manager.json','server.log'} or p.name.endswith(('.tmp','.part','.part.json')) or p.suffix=='.pyc' or rel.startswith('results/local-'):continue
        yield p,rel

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--seal',action='store_true');args=ap.parse_args()
    cases={c['id']:c for name in ['cases.json','battle-cases.json','ui-cases.json'] for c in read(ROOT/name)['cases']}
    reviews={r['run_id']:r for r in read(ROOT/'visual-review.json')['reviews']}
    runs=[]
    for p in sorted((ROOT/'results').glob('*/record.json')):
        rec=read(p);c=cases[rec['case_id']];r=dict(c,**{k:v for k,v in rec.items() if k not in c})
        assert r['status']=='PASS' and sha(p.parent/'image.png')==r['image_sha256'],p
        r['review']=reviews[r['run_id']];assert r['review']['image_sha256']==r['image_sha256']
        if r['run_id'].startswith('toolkit-'):r['role']='cuda-check'
        if r['run_id'] in {'batch-fantasy-battle','batch-hitech-battle','batch-steampunk-battle'}:
            r.update(family={'batch-fantasy-battle':'fantasy','batch-hitech-battle':'robot','batch-steampunk-battle':'steampunk'}[r['run_id']],variant='original')
        r['image_file']='results/'+r['run_id']+'/image.png'
        r['prompt']=(ROOT/r['prompt_file']).read_text(encoding='utf-8')
        reductions=re.findall(r'Reducing VAE decode tiles from (\d+x\d+) to (\d+x\d+) image pixels',(p.parent/'engine.log').read_text(encoding='utf-8'))
        r['effective_vae']=dict(automatic_retry=bool(reductions),tile_reductions=reductions,explicit_tiling_flag=False)
        runs.append(r)
    primary=[r for r in runs if r['role']=='thematic-first-result'];assert len(primary)==18
    battles=[r for r in runs if r.get('family')];assert len(battles)==15
    extra=[r for r in runs if r['role']=='battle-recheck'];assert len(extra)==12
    baseline=next(r for r in runs if r['run_id']=='batch-people-portrait-512')
    toolkit=next(r for r in runs if r['role']=='cuda-check')
    summary=dict(runs=len(runs),primary=18,extra_battles=12,battle_images=15,ui_runs=sum(r['role']=='ui-proof' for r in runs),within_minute=sum(r['seconds']<=60 for r in primary),peak_gpu_mib=max(r['peak_gpu_used_mib'] for r in runs),toolkit_png_equal=baseline['image_sha256']==toolkit['image_sha256'],minimum_battle_seconds=min(r['seconds'] for r in extra),maximum_battle_seconds=max(r['seconds'] for r in extra),clear_connection_pass=sum(r['variant']=='clear' and r['review']['battle']['connection']=='PASS' for r in battles),clear_all_pass=sum(r['variant']=='clear' and r['review']['battle']['overall']=='PASS' for r in battles))
    dataset=dict(schema=3,date='2026-10-23',summary=summary,runs=runs,sources=read(ROOT/'sources.json'),gui=read(ROOT/'ui-proof/verification.json'),manager=read(ROOT/'desktop/verification.json'),input_sha256={name:sha(ROOT/name) for name in ['cases.json','battle-cases.json','ui-cases.json','visual-review.json']})
    write(ROOT/'results.json',dataset)
    fields=['run_id','role','category','width','height','seed','steps','seconds','sampling_seconds','vae_seconds','peak_gpu_used_mib','peak_engine_private_mib','minimum_available_mib','text_status','connection','instruction','overall','image_sha256']
    buf=io.StringIO(newline='');writer=csv.DictWriter(buf,fieldnames=fields);writer.writeheader()
    for r in runs:
        row={k:r.get(k) for k in fields};row['text_status']=r['review']['text_status'];row.update(r['review'].get('battle',{}));writer.writerow(row)
    (ROOT/'results.csv').write_text(buf.getvalue(),encoding='utf-8-sig',newline='')
    full=dict(dataset,runs=[dict(r,image_data='data:image/png;base64,'+base64.b64encode((ROOT/r['image_file']).read_bytes()).decode('ascii')) for r in runs],reproduction=(ROOT/'docs/REPRODUCE.md').read_text(encoding='utf-8'),interface=(ROOT/'docs/INTERFACE.md').read_text(encoding='utf-8'),gui_image='data:image/jpeg;base64,'+base64.b64encode((ROOT/'ui-proof/result-screenshot.jpg').read_bytes()).decode('ascii'))
    template=(ROOT/'report.template.html').read_text(encoding='utf-8');assert template.count('__REPORT_DATA__')==1
    (ROOT/'report.html').write_text(template.replace('__REPORT_DATA__',json.dumps(full,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')),encoding='utf-8',newline='\n')
    md=['# Наблюдавшиеся результаты','',f'{len(runs)} завершённых генераций: 25 исходных, 12 дополнительных боёв и {summary["ui_runs"]} через интерфейс.','',f'В исходных 18 тематических сценах {summary["within_minute"]} уложились в 60 секунд. Дополнительные бои: {summary["minimum_battle_seconds"]:.1f}–{summary["maximum_battle_seconds"]:.1f} с. Максимум всей занятой VRAM по выборке – {summary["peak_gpu_mib"]} МиБ.','', '| Размер | n | Минимум / медиана / максимум, с |','|---|---:|---:|']
    for wh in sorted({(r['width'],r['height']) for r in runs},key=lambda x:x[0]*x[1]):
        v=[r['seconds'] for r in runs if (r['width'],r['height'])==wh];md.append(f'| {wh[0]}×{wh[1]} | {len(v)} | {min(v):.1f} / {statistics.median(v):.1f} / {max(v):.1f} |')
    md+=['','Время относится к новому процессу движка, включает чтение весов и сохранение PNG; ожидание запуска не включено. Файловый кэш Windows не очищался. Разные сцены и одиночные seed не образуют статистический бенчмарк. Пик VRAM измеряет всю карту, включая рабочий стол, примерно раз в секунду. RAM – фактически 32 ГиБ, минимально необходимый объём не установлен.','', '## Качество','', 'В первоначальном наборе ожидаемые крупные русские надписи визуально прочитаны в 17/17 тематических запросах и 21/21 с дополнительными разрешениями. Это отдельная оценка текста: геометрия оружия, лишние мелкие слова и выполнение композиции проверяются независимо. Все 12 новых боевых надписей также читаются. Оценка автора ИИ не является независимой экспертизой. Два исходных дефекта указаны зрителем до перепроверки.','', 'Шесть упрощённых дуэлей показывают более читаемую связь кисть–рукоять–клинок, но у всех шести левый персонаж держит оружие левой рукой вместо заданной правой. Два новых воздушных боя показывают связный главный луч, но нарушают условия крепления оружия. Ни один из восьми уточнённых кадров не получил полного PASS по всем условиям. См. [BATTLES.md](BATTLES.md).','', 'Официальный prompt upsampler в этой серии не запускался: поданы заранее подробно описанные английские сцены. Поэтому здесь не измерены ни качество, ни полная задержка официального пайплайна с upsampler. Авторы BFL рекомендуют его использование; сравнение с такими captions остаётся отдельным следующим опытом. [Источник](https://github.com/black-forest-labs/flux-3-image-klein#prompt-upsampling).','', '## CUDA и VAE','', 'Toolkit-only проверка завершилась успешно; три CUDA DLL фактически загружены из установленного CUDA Toolkit 12.6.85. Дополнительные бои и интерфейс используют этот же каталог. Парный портрет Toolkit-only побайтно совпал с исходным условием; это проверка совместимости, не доказательство ускорения.','', 'Во всех трёх 1024² условиях первая попытка декодирования VAE не уложилась в бюджет, после чего движок автоматически перешёл на 9 перекрывающихся плиток 512². Предупреждения сохранены в журналах, итоговое время включает повтор. Явного --vae-tiling в команде не было.','', 'Не измерены другие Pascal-карты, Linux, минимальный RAM, холодный кэш, Base/BF16 качество, LoRA, редактирование по референсам и 4K. Изображения не ретушировались.']
    (ROOT/'docs/RESULTS.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    gallery=['# Первые тематические результаты','', 'Все исходные кадры сохранены, включая дефекты. Оценки качества – в visual-review.json.','']
    for r in primary:gallery += [f'## {r["category"]}: {r["title_ru"]}','',f'![{r["title_ru"]}](../{r["image_file"]})','',f'{r["width"]}×{r["height"]}, seed {r["seed"]}, {r["seconds"]:.2f} с.','',r['review']['observation_ru'],'']
    (ROOT/'docs/GALLERY.md').write_text('\n'.join(gallery),encoding='utf-8')
    md=['# Перепроверка боёв','', 'Три исходные сцены, 12 новых условий. Матрица battle-cases.json и её SHA зафиксированы до новых запусков; все первые результаты оставлены. Для фэнтези и роботов сохранены парные seed 42/7/123 исходного и упрощённого промптов. Для стимпанка – исходный seed42 и два уточнённых условия 42/7.','', 'connection проверяет читаемость связи оружия и руки либо основного луча с источником/целью. instruction проверяет другие конкретные условия: контакт, анатомическую сторону руки, состав оружия, кадрирование и место крепления. overall не получает PASS, если хотя бы одна обязательная часть нарушена или остаётся неоднозначной. PASS означает только видимую связность на данном PNG; физическая конструкция фантастического оружия не доказана. Это исследовательская визуальная оценка автора ИИ после просмотра, не независимая или статистическая метрика.','', 'Упрощение меняет саму задачу: у рыцарей убран щит, у роботов щит и посох заменены двумя мечами; композиция стала статичнее. Поэтому улучшение хвата нельзя считать исправлением исходного сложного действия без потерь.','']
    for r in sorted(battles,key=lambda r:(r['family'],r['variant'],r['seed'])):
        b=r['review']['battle'];md += [f'## {r["run_id"]}','',f'![{r["title_ru"]}, seed {r["seed"]}](../{r["image_file"]})','',f'{r["seconds"]:.2f} с; connection={b["connection"]}; instruction={b["instruction"]}; overall={b["overall"]}.','',r['review']['observation_ru'],'',f'[Точный промпт](../{r["prompt_file"]}) · [Параметры](../results/{r["run_id"]}/record.json)','']
    md += ['## Следующие опыты','', 'Сначала сравнить captions официального prompt upsampler с текущими подробными промптами на тех же seed. Затем отдельно проверить постановку поз и размещение объектов, если выбранный backend действительно поддерживает соответствующий механизм. Inpainting/референсы и LoRA здесь не испытаны. Нельзя обещать, что увеличение шагов, разрешения или перенос кода управления памятью исправит хват: причинный опыт для этого ещё не выполнен.']
    (ROOT/'docs/BATTLES.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    if args.seal:write(ROOT/'MANIFEST.json',dict(schema=2,created_at=dt.datetime.now(dt.timezone.utc).isoformat(),files=[dict(path=rel,bytes=p.stat().st_size,sha256=sha(p)) for p,rel in published_files()],excluded=['MANIFEST.json itself','local configuration, user outputs, weights, runtime, caches']))
    print(json.dumps(dict(status='PASS',summary=summary,html_bytes=(ROOT/'report.html').stat().st_size)))

if __name__=='__main__':main()
