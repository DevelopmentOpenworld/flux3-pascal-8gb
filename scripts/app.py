"""Local FLUX.3 interface. Standard library only; binds to 127.0.0.1."""
import argparse
import ctypes
from ctypes import wintypes as wt
import datetime as dt
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import threading
import tempfile
import time
from urllib.parse import urlparse
import urllib.request
import uuid
import webbrowser
if not getattr(sys,'frozen',False):
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from process_env import external_dll_search
from scripts.i18n import MESSAGES, Message, msg, joined, render, with_translations

ROOT=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))
FIELDS=['sd_cli','diffusion_model','llm','vae','cuda_bin','cuda_runtime_dir','max_vram_gib','timeout_seconds']


def preset_title(case):
    return msg('preset_' + case['id'].replace('-', '_'))


class OwnedProcessTree:
    """Windows closes only this application's child tree after an unexpected exit."""
    def __init__(self,process):
        class Basic(ctypes.Structure):
            _fields_=[('process_time',ctypes.c_longlong),('job_time',ctypes.c_longlong),('flags',wt.DWORD),
                      ('min_ws',ctypes.c_size_t),('max_ws',ctypes.c_size_t),('active',wt.DWORD),
                      ('affinity',ctypes.c_size_t),('priority',wt.DWORD),('scheduling',wt.DWORD)]
        class Io(ctypes.Structure):
            _fields_=[(n,ctypes.c_ulonglong) for n in ['read_count','write_count','other_count','read_bytes','write_bytes','other_bytes']]
        class Limits(ctypes.Structure):
            _fields_=[('basic',Basic),('io',Io),('process_memory',ctypes.c_size_t),('job_memory',ctypes.c_size_t),
                      ('peak_process',ctypes.c_size_t),('peak_job',ctypes.c_size_t)]
        self.handle=None
        if os.name!='nt':return
        k=ctypes.WinDLL('kernel32',use_last_error=True)
        k.CreateJobObjectW.argtypes=[ctypes.c_void_p,wt.LPCWSTR];k.CreateJobObjectW.restype=wt.HANDLE
        k.SetInformationJobObject.argtypes=[wt.HANDLE,ctypes.c_int,ctypes.c_void_p,wt.DWORD]
        k.AssignProcessToJobObject.argtypes=[wt.HANDLE,wt.HANDLE]
        k.CloseHandle.argtypes=[wt.HANDLE]
        self.kernel=k;self.handle=k.CreateJobObjectW(None,None)
        limits=Limits();limits.basic.flags=0x2000
        if not self.handle or not k.SetInformationJobObject(self.handle,9,ctypes.byref(limits),ctypes.sizeof(limits)) or not k.AssignProcessToJobObject(self.handle,wt.HANDLE(int(process._handle))):
            if self.handle:k.CloseHandle(self.handle);self.handle=None
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            raise RuntimeError('Cannot attach owned child process tree')
    def close(self):
        if self.handle:self.kernel.CloseHandle(self.handle);self.handle=None


def save(path,value):
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    tmp.replace(path)


def session_token(path):
    """Keep bookmarks valid across local server restarts; never publish this file."""
    if path.exists():
        token=json.loads(path.read_text(encoding='utf-8'))['token']
        if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{32,128}',token):
            raise ValueError(msg('session_corrupt'))
        return token
    token=secrets.token_urlsafe(32)
    save(path,dict(token=token))
    return token


def safe_error(error):
    # Do not return a traceback containing machine paths to the page.
    return error.args[0] if isinstance(error,ValueError) and error.args and isinstance(error.args[0],Message) else msg('operation_failed')


def generation_progress(text,steps):
    """Native weight-loading counters use MB/s; only sampler iterations use s/it."""
    if re.search(r'decoding \d+ latents|computing vae decode|loading \d+/\d+ tensors from .*vae',text,re.I):
        return 96,msg('decode')
    matches=re.findall(r'(\d+)\s*/\s*(\d+)\s+-\s+[\d.]+\s*(?:s/it|it/s)',text)
    for a,b in reversed(matches):
        a,b=int(a),int(b)
        if b==steps and 1<=a<=b:return min(95,20+round(a/b*70)),msg('sample_step', step=a, steps=steps)
    if re.search(r'loading \d+/\d+ tensors from .*flux3',text,re.I):return 15,msg('load_image')
    if re.search(r'loading \d+/\d+ tensors from .*Qwen',text,re.I):return 8,msg('load_prompt')
    return 3,msg('load_models')


class App:
    def __init__(self,config_path):
        self.config_path=config_path.resolve();self.config_path.parent.mkdir(parents=True,exist_ok=True)
        self.config=json.loads(config_path.read_text(encoding='utf-8-sig')) if config_path.exists() else json.loads((ROOT/'config.example.json').read_text(encoding='utf-8'))
        self.token=session_token(self.config_path.parent/'app-session.json')
        self.workspace=tempfile.TemporaryDirectory(prefix='flux3-work-')
        self.data=Path(self.workspace.name).resolve()
        self.jobs={};self.active=None;self.current=None;self.worker=None;self.lock=threading.Lock()

    def exposed_config(self):
        return {k:self.config.get(k,'') for k in FIELDS}

    def check_config(self,config=None):
        config=config or self.config
        errors=[]
        for key,label in [('sd_cli',msg('engine_label')),('diffusion_model',msg('model_label')),('llm',msg('qwen_label')),('vae','VAE')]:
            p=Path(str(config.get(key,'')));p=p if p.is_absolute() else ROOT/p
            if not p.is_file():errors.append(msg('file_missing', name=label))
        cuda=Path(str(config.get('cuda_bin','')));cuda=cuda if cuda.is_absolute() else ROOT/cuda
        if not str(config.get('cuda_bin','')).strip() or not cuda.is_dir():errors.append(msg('cuda_missing'))
        if not 1<=float(config.get('max_vram_gib',6))<=6:errors.append(msg('vram_limit'))
        return errors

    def update_config(self,values):
        with self.lock:
            if self.active:raise ValueError(msg('wait_generation'))
            updated=dict(self.config)
            for key in FIELDS:
                if key in values:updated[key]=values[key]
            updated['max_vram_gib']=float(updated.get('max_vram_gib',6));updated['timeout_seconds']=900
            errors=self.check_config(updated)
            if errors:raise ValueError(joined(errors, '; '))
            save(self.config_path,updated);self.config=updated
        return {'ok':True,'message':msg('paths_saved')}

    def view_job(self,job):
        result={k:job.get(k) for k in ['id','status','message','progress','created_at','width','height','seed','steps','cfg_scale','prompt','seconds','image_sha256']}
        image=self.data/job['id']/'image.png'
        if image.is_file() and job['status']=='DONE':result['image_url']='/api/image/'+job['id']
        return result

    def current_job(self):
        with self.lock:return {'job':self.view_job(self.jobs[self.current]) if self.current else None,'active':bool(self.active)}

    def clear_workspace(self):
        # Only remove this process's own temporary workspace, never configured user folders.
        base=self.data.resolve()
        if base!=Path(self.workspace.name).resolve():raise ValueError(msg('temp_folder'))
        for p in base.iterdir():
            if not p.resolve().is_relative_to(base):raise ValueError(msg('temp_path'))
            if p.is_dir():shutil.rmtree(p)
            else:p.unlink()

    def close(self):
        self.cancel()
        if self.worker:self.worker.join(timeout=30)
        if self.worker and self.worker.is_alive():return
        self.workspace.cleanup()

    def create(self,values):
        errors=self.check_config()
        if errors:raise ValueError(joined(errors, '; '))
        prompt=str(values.get('prompt','')).strip()
        if not prompt or len(prompt)>12000:raise ValueError(msg('prompt_limit'))
        def integer(key,default):
            value=values.get(key,default)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or int(value)!=value:raise ValueError(msg('integer_parameters'))
            return int(value)
        width=integer('width',512);height=integer('height',512)
        if not 256<=width<=1536 or not 256<=height<=1536 or width%16 or height%16 or width*height>1024*1024:
            raise ValueError(msg('dimension_limit'))
        seed=integer('seed',42);steps=integer('steps',16);cfg=float(values.get('cfg_scale',1))
        if not 0<=seed<=2147483647 or not 1<=steps<=64 or not 1<=cfg<=8:raise ValueError(msg('parameter_limit'))
        with self.lock:
            if self.active:raise ValueError(msg('already_generating'))
            self.clear_workspace()
            jid='ui-'+uuid.uuid4().hex[:16]
            job=dict(id=jid,status='QUEUED',message=msg('queued'),progress=0,created_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                     width=width,height=height,seed=seed,steps=steps,cfg_scale=cfg,prompt=prompt)
            self.jobs={jid:job};self.active=jid;self.current=jid
            (self.data/jid).mkdir()
            self.worker=threading.Thread(target=self.guarded_work,args=(jid,),daemon=True);self.worker.start()
            return self.view_job(job)

    def guarded_work(self,jid):
        try:self.work(jid)
        except Exception as error:
            with self.lock:
                job=self.jobs[jid];job.update(status='FAILED',message=safe_error(error));job.pop('process',None)
                if self.active==jid:self.active=None

    def work(self,jid):
        job=self.jobs[jid];folder=self.data/jid
        # The generator creates its result directory, so input/job files have a separate directory.
        inputs=self.data/'inputs'/jid;inputs.mkdir(parents=True,exist_ok=False)
        (inputs/'prompt.txt').write_text(job['prompt']+'\n',encoding='utf-8',newline='\n')
        config=dict(self.config,output_root=str(self.data/'generated'))
        save(inputs/'config.json',config)
        case=dict(id=jid,title_ru='Своя генерация',category='Интерфейс',prompt_file=str(inputs/'prompt.txt'),
                  expected_text=[],width=job['width'],height=job['height'],seed=job['seed'],steps=job['steps'],cfg_scale=job['cfg_scale'])
        save(inputs/'case.json',dict(cases=[case]))
        worker=[sys.executable,'--generate-worker'] if getattr(sys,'frozen',False) else [sys.executable,str(ROOT/'scripts/generate.py')]
        cmd=worker+['--config',str(inputs/'config.json'),'--cases-file',str(inputs/'case.json'),'--case',jid,'--run-id',jid]
        prefix=self.config.get('execution_prefix',[])
        if not isinstance(prefix,list) or any(not isinstance(x,str) for x in prefix):raise ValueError(msg('prefix_invalid'))
        generated=self.data/'generated'/jid
        tree=None
        try:
            with (folder/'launcher.log').open('w',encoding='utf-8') as log:
                with self.lock:
                    if job['status']=='CANCELLED':return
                    worker_env=os.environ.copy()
                    if getattr(sys,'frozen',False):worker_env['PYINSTALLER_RESET_ENVIRONMENT']='1'
                    with external_dll_search():
                        p=subprocess.Popen(prefix+cmd,cwd=ROOT,env=worker_env,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                    tree=OwnedProcessTree(p);job['process']=p
                while p.poll() is None:
                    with self.lock:
                        if job['status']=='CANCELLED':break
                        if generated.exists() and job['status']!='STOPPING':
                            job['status']='RUNNING';job['message']=msg('generating')
                            live=generated/'live.log'
                            if live.exists():
                                text=live.read_text(encoding='utf-8',errors='replace')[-20000:]
                                job['progress'],job['message']=generation_progress(text,job['steps'])
                        
                    time.sleep(0.6)
                p.wait(timeout=30)
            with self.lock:
                if job['status'] in ['CANCELLED','STOPPING']:return
                record=generated/'record.json'
                r=json.loads(record.read_text(encoding='utf-8')) if record.exists() else {}
                if p.returncode==0 and r.get('status')=='PASS' and (generated/'image.png').is_file():
                    import shutil
                    shutil.copyfile(generated/'image.png',folder/'image.png')
                    job.update(status='DONE',message=msg('done'),progress=100,seconds=r['seconds'],image_sha256=r['image_sha256'])
                else:
                    save(folder/'runtime-status.json',dict(returncode=p.returncode,record_present=record.exists()))
                    job.update(status='FAILED',message=msg('generation_failed', detail=r.get('stop_reason') or msg('check_log')))
        except Exception as error:
            import traceback
            (folder/'error.log').write_text(traceback.format_exc(),encoding='utf-8')
            with self.lock:job.update(status='FAILED',message=safe_error(error))
        finally:
            if tree:tree.close()
            with self.lock:
                job.pop('process',None)
                if self.active==jid:self.active=None

    def cancel(self):
        with self.lock:
            if not self.active:return {'ok':True}
            job=self.jobs[self.active];p=job.get('process')
            job.update(status='STOPPING' if p else 'CANCELLED',message=msg('stopping'),progress=0)
        if p and p.poll() is None:
            subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                with self.lock:job.update(status='RUNNING',message=msg('stop_pending'))
                raise ValueError(msg('process_stop_failed'))
        with self.lock:job.update(status='CANCELLED',message=msg('cancelled'),progress=0)
        return {'ok':True}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--config',default=str(ROOT/'config.local.json'));ap.add_argument('--port',type=int,default=None);ap.add_argument('--no-browser',action='store_true')
    args=ap.parse_args();config=Path(args.config);state_path=config.parent/'app-state.json'
    if state_path.exists():
        try:
            old=json.loads(state_path.read_text(encoding='utf-8'))
            with urllib.request.urlopen(old['base_url']+'/api/health',timeout=2) as response:health=json.load(response)
            if health.get('instance')==old['instance']:
                if not args.no_browser:webbrowser.open(old['url'])
                return
        except (OSError,ValueError,KeyError):pass
    app=App(config)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,value,status=200,kind='application/json; charset=utf-8'):
            data=value if isinstance(value,bytes) else json.dumps(render(with_translations(value), 'en' if self.headers.get('Accept-Language','').lower().startswith('en') else 'ru'),ensure_ascii=False).encode('utf-8')
            self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(data)
        def allowed(self):
            return self.headers.get('Host')==f'127.0.0.1:{self.server.server_port}'
        def authorized(self):
            return self.allowed() and secrets.compare_digest(self.headers.get('X-Session',''),app.token)
        def do_GET(self):
            path=urlparse(self.path).path
            if not self.allowed():return self.send({'error':msg('host_rejected')},403)
            if path=='/api/health':return self.send({'app':'flux3-local','instance':instance})
            if path=='/ui/app.js':return self.send((ROOT/'ui/app.js').read_bytes(),kind='text/javascript; charset=utf-8')
            if path=='/':return self.send((ROOT/'ui/index.html').read_bytes().replace(b'__FLUX_MESSAGES__',json.dumps(MESSAGES,ensure_ascii=False).replace('<','\\u003c').encode('utf-8')),kind='text/html; charset=utf-8')
            if not self.authorized():return self.send({'error':msg('session_invalid')},403)
            if path=='/api/config':return self.send({'config':app.exposed_config(),'errors':app.check_config()})
            if path=='/api/presets':
                cases=json.loads((ROOT/'cases.json').read_text(encoding='utf-8'))['cases']
                result=[]
                for c in cases:
                    if c['role']!='thematic-first-result':continue
                    result.append(dict(id=c['id'],title=preset_title(c),prompt=(ROOT/c['prompt_file']).read_text(encoding='utf-8'),width=c['width'],height=c['height'],seed=c['seed']))
                extra=json.loads((ROOT/'battle-cases.json').read_text(encoding='utf-8'))['cases']
                for c in extra:
                    if c['variant']=='clear' and c['seed']==42:
                        result.append(dict(id=c['id'],title=msg('simple_composition', title=preset_title(c)),prompt=(ROOT/c['prompt_file']).read_text(encoding='utf-8'),width=c['width'],height=c['height'],seed=c['seed']))
                return self.send(result)
            if path=='/api/current':return self.send(app.current_job())
            if path.startswith('/api/image/'):
                jid=path.rsplit('/',1)[-1]
                if not re.fullmatch(r'ui-[a-f0-9]{16}',jid):return self.send({'error':msg('no_image')},404)
                p=app.data/jid/'image.png'
                if jid!=app.current or not p.is_file():return self.send({'error':msg('no_image')},404)
                return self.send(p.read_bytes(),kind='image/png')
            return self.send({'error':msg('not_found')},404)
        def do_POST(self):
            if not self.authorized():return self.send({'error':msg('forbidden')},403)
            origin=self.headers.get('Origin')
            if origin and origin!=f'http://127.0.0.1:{self.server.server_port}':return self.send({'error':msg('origin_rejected')},403)
            try:
                n=int(self.headers.get('Content-Length','0'))
                if n<0 or n>65536:raise ValueError(msg('large_request'))
                value=json.loads(self.rfile.read(n) or b'{}')
                if self.path=='/api/config':return self.send(app.update_config(value))
                if self.path=='/api/generate':return self.send(app.create(value),202)
                if self.path=='/api/cancel':return self.send(app.cancel())
                if self.path=='/api/shutdown':
                    app.cancel();self.send({'ok':True});threading.Thread(target=self.server.shutdown,daemon=True).start();return
                return self.send({'error':msg('not_found')},404)
            except (ValueError,TypeError,KeyError) as error:return self.send({'error':safe_error(error)},400)
            except Exception as error:return self.send({'error':safe_error(error)},500)
    port=args.port if args.port is not None else int(app.config.get('port',8440))
    if not 0<=port<=65535:raise SystemExit('Порт должен быть от 1 до 65535; 0 – только для отдельного теста')
    instance=secrets.token_hex(12)
    try:server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    except OSError as error:
        raise SystemExit(f'Не удалось открыть локальный порт {port}. Проверьте другой экземпляр приложения или задайте --port явно.') from error
    base=f'http://127.0.0.1:{server.server_port}';url=base+'/#session='+app.token
    save(state_path,dict(base_url=base,url=url,instance=instance,pid=os.getpid()))
    if not args.no_browser:webbrowser.open(url)
    try:server.serve_forever(poll_interval=0.2)
    finally:server.server_close();app.close()


if __name__=='__main__':main()
