"""Failure-oriented local application tests; no model or GPU is started."""
import ctypes
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.request
import urllib.error

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('flux_app',ROOT/'scripts/app.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class AppTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        dummy=self.base/'asset';dummy.write_bytes(b'test')
        self.config=self.base/'config.json'
        mod.save(self.config,dict(sd_cli=str(dummy),diffusion_model=str(dummy),llm=str(dummy),vae=str(dummy),cuda_bin=str(self.base),max_vram_gib=6))
        self.app=mod.App(self.config)
    def tearDown(self):self.app.close();self.tmp.cleanup()
    def test_invalid_input_never_starts_worker(self):
        with patch.object(self.app,'work') as work:
            for values in [dict(prompt=''),dict(prompt='x',width=511),dict(prompt='x',width=1536,height=1536),dict(prompt='x',seed=-1),dict(prompt='x',seed=1.5),dict(prompt='x',steps=65),dict(prompt='x',cfg_scale=0)]:
                with self.subTest(values=values),self.assertRaises(ValueError):self.app.create(values)
            work.assert_not_called();self.assertIsNone(self.app.active)
    def test_concurrent_submissions_create_only_one_job(self):
        release=threading.Event();barrier=threading.Barrier(8);results=[]
        def worker(jid):release.wait(5)
        def request():
            barrier.wait()
            try:self.app.create(dict(prompt='test'));results.append('accepted')
            except ValueError:results.append('blocked')
        with patch.object(self.app,'work',worker):
            ts=[threading.Thread(target=request) for _ in range(8)]
            for t in ts:t.start()
            for t in ts:t.join(5)
            self.assertEqual(results.count('accepted'),1);self.assertEqual(len(self.app.jobs),1)
            release.set()
    def test_restart_ignores_saved_runs_without_touching_user_files(self):
        old=self.base/'ui-data/ui-0000000000000000/job.json';old.parent.mkdir(parents=True)
        old.write_text('{"id":"old-run","status":"DONE"}')
        before=old.read_bytes();config=dict(self.app.config,data_dir=str(old.parent.parent));mod.save(self.config,config)
        recovered=mod.App(self.config)
        try:
            self.assertEqual(recovered.current_job(),dict(job=None,active=False))
            self.assertNotEqual(recovered.data,old.parent.parent)
            self.assertEqual(old.read_bytes(),before)
        finally:recovered.close()
        self.assertEqual(old.read_bytes(),before)
    def test_next_request_removes_only_previous_temporary_result(self):
        def worker(jid):
            with self.app.lock:
                (self.app.data/jid/'image.png').write_bytes(b'owned temporary image')
                self.app.jobs[jid].update(status='DONE',message='Done');self.app.active=None
        with patch.object(self.app,'work',worker):
            first=self.app.create(dict(prompt='first'));self.app.worker.join(3)
            first_file=self.app.data/first['id']/'image.png';self.assertTrue(first_file.exists())
            second=self.app.create(dict(prompt='second'));self.app.worker.join(3)
            self.assertFalse(first_file.exists());self.assertNotIn(first['id'],self.app.jobs)
            self.assertEqual(self.app.current_job()['job']['id'],second['id'])
            self.assertEqual(len(self.app.jobs),1);self.assertEqual(list(self.app.data.rglob('job.json')),[])
    def test_local_session_survives_app_restart(self):
        first=self.app.token
        other=mod.App(self.config)
        try:self.assertEqual(other.token,first)
        finally:other.close()
        session_file=self.config.parent/'app-session.json'
        mod.save(session_file,dict(token='invalid'))
        with self.assertRaises(ValueError):mod.App(self.config)
    def test_missing_files_reject_settings_and_keep_previous_config(self):
        before=self.config.read_bytes()
        with self.assertRaises(ValueError):self.app.update_config(dict(llm=str(self.base/'missing')))
        self.assertEqual(before,self.config.read_bytes())
    def test_relative_cuda_directory_uses_project_root(self):
        (self.base/'cuda').mkdir()
        config=dict(self.app.config,cuda_bin='cuda')
        with patch.object(mod,'ROOT',self.base):self.assertEqual(self.app.check_config(config),[])
    def test_progress_does_not_treat_weight_loading_as_sampling(self):
        for n in [316,353,140]:
            with self.subTest(n=n):
                progress,label=mod.generation_progress(f'loading {n}/{n} tensors from model\n {n}/{n} - 0.09MB/s',16)
                self.assertNotIn('шаг',label.lower());self.assertLess(progress,20)
        self.assertEqual(mod.generation_progress(' 3/16 - 1.25s/it',16)[1],'Генерация изображения: шаг 3 из 16')
        self.assertEqual(mod.generation_progress(' 5/32 - 2.38s/it',32)[1],'Генерация изображения: шаг 5 из 32')
        progress,label=mod.generation_progress(' 16/16 - 1.25s/it\ndecoding 1 latents\n140/140 - 894.41MB/s',16)
        self.assertEqual(progress,96);self.assertNotIn('шаг',label.lower())
    def test_prelaunch_cancellation_does_not_spawn(self):
        jid='ui-'+'f'*16
        self.app.jobs[jid]=dict(id=jid,status='QUEUED',prompt='test',width=512,height=512,seed=7,steps=16,cfg_scale=1)
        self.app.current=jid;(self.app.data/jid).mkdir()
        self.app.active=jid;self.app.cancel()
        with patch.object(subprocess,'Popen') as spawn:self.app.work(jid);spawn.assert_not_called()
        self.assertIsNone(self.app.active);self.assertEqual(self.app.jobs[jid]['status'],'CANCELLED')
    @unittest.skipUnless(os.name=='nt','Windows process ownership')
    def test_closing_job_terminates_only_owned_descendants(self):
        pidfile=self.base/'child.pid'
        script='import subprocess,sys,time;from pathlib import Path;p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(120)"]);Path(sys.argv[1]).write_text(str(p.pid));time.sleep(120)'
        p=subprocess.Popen([sys.executable,'-c',script,str(pidfile)],creationflags=subprocess.CREATE_NO_WINDOW)
        tree=mod.OwnedProcessTree(p);leaf=None
        try:
            deadline=time.monotonic()+5
            while not pidfile.exists() and time.monotonic()<deadline:time.sleep(.03)
            self.assertTrue(pidfile.exists())
            k=ctypes.WinDLL('kernel32');k.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];k.OpenProcess.restype=ctypes.c_void_p
            k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong];k.CloseHandle.argtypes=[ctypes.c_void_p]
            leaf=k.OpenProcess(0x100000,False,int(pidfile.read_text()));self.assertTrue(leaf)
            tree.close();p.wait(timeout=5);self.assertEqual(k.WaitForSingleObject(leaf,5000),0)
        finally:
            tree.close()
            if p.poll() is None:p.kill();p.wait()
            if leaf:k.CloseHandle(leaf)
    def test_http_authentication_origin_and_instance_reuse(self):
        p=subprocess.Popen([sys.executable,'-B',str(ROOT/'scripts/app.py'),'--config',str(self.config),'--port','0','--no-browser'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            state=self.base/'app-state.json';deadline=time.monotonic()+5
            while not state.exists() and time.monotonic()<deadline:time.sleep(.03)
            info=json.loads(state.read_text());base=info['base_url'];token=info['url'].split('session=')[1]
            def request(path,body=None,**headers):
                req=urllib.request.Request(base+path,data=None if body is None else json.dumps(body).encode(),headers=headers)
                return urllib.request.urlopen(req,timeout=3)
            with self.assertRaises(urllib.error.HTTPError) as error:request('/api/current')
            self.assertEqual(error.exception.code,403);error.exception.close()
            with self.assertRaises(urllib.error.HTTPError) as error:request('/api/cancel',{},**{'X-Session':token,'Origin':'https://example.invalid'})
            self.assertEqual(error.exception.code,403);error.exception.close()
            with self.assertRaises(urllib.error.HTTPError) as error:request('/api/current',**{'X-Session':token,'Host':'example.invalid'})
            self.assertEqual(error.exception.code,403);error.exception.close()
            with self.assertRaises(urllib.error.HTTPError) as error:request('/api/generate',dict(prompt='x',seed=-1),**{'X-Session':token})
            self.assertEqual(error.exception.code,400);error.exception.close()
            with request('/api/current',**{'X-Session':token}) as r:self.assertEqual(json.load(r),dict(job=None,active=False))
            with self.assertRaises(urllib.error.HTTPError) as error:request('/api/jobs',**{'X-Session':token})
            self.assertEqual(error.exception.code,404);error.exception.close()
            second=subprocess.run([sys.executable,str(ROOT/'scripts/app.py'),'--config',str(self.config),'--no-browser'],timeout=5,capture_output=True)
            self.assertEqual(second.returncode,0);self.assertIsNone(p.poll())
            with request('/api/shutdown',{},**{'X-Session':token}) as r:self.assertTrue(json.load(r)['ok'])
            p.wait(timeout=5);self.assertEqual(p.returncode,0)
        finally:
            if p.poll() is None:p.terminate();p.wait(timeout=5)

    def test_server_restart_keeps_existing_bookmark_and_authentication(self):
        children=[]
        def start(port,old_instance=None):
            p=subprocess.Popen([sys.executable,'-B',str(ROOT/'scripts/app.py'),'--config',str(self.config),'--port',str(port),'--no-browser'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            children.append(p);deadline=time.monotonic()+6
            while time.monotonic()<deadline:
                try:
                    state=json.loads((self.base/'app-state.json').read_text())
                    if state['instance']!=old_instance:
                        with urllib.request.urlopen(state['base_url']+'/api/health',timeout=.2) as r:
                            if json.load(r)['instance']==state['instance']:return p,state
                except (OSError,ValueError):pass
                time.sleep(.03)
            self.fail('Server did not start')
        def request(state,path,body=None):
            token=state['url'].split('session=')[1]
            req=urllib.request.Request(state['base_url']+path,data=None if body is None else json.dumps(body).encode(),headers={'X-Session':token})
            return urllib.request.urlopen(req,timeout=3)
        try:
            p,first=start(0)
            with request(first,'/api/shutdown',{}) as r:self.assertTrue(json.load(r)['ok'])
            p.wait(timeout=5)
            port=int(first['base_url'].rsplit(':',1)[1]);second_p,second=start(port,first['instance'])
            self.assertEqual(first['url'],second['url'])
            self.assertNotEqual(first['instance'],second['instance'])
            with request(first,'/api/current') as r:self.assertEqual(json.load(r),dict(job=None,active=False))
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(second['base_url']+'/api/current',timeout=3)
            self.assertEqual(error.exception.code,403);error.exception.close()
            with request(first,'/api/shutdown',{}) as r:self.assertTrue(json.load(r)['ok'])
            second_p.wait(timeout=5)
        finally:
            for p in children:
                if p.poll() is None:p.terminate();p.wait(timeout=5)

if __name__=='__main__':unittest.main()
