"""Language regression checks. Tk is replaced; no native window or GPU is opened."""
import json
from pathlib import Path
import re
import socket
import string
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from scripts.i18n import MESSAGES, msg, joined, render
from desktop import launcher
import app


class Variable:
    def __init__(self, value='', **kwargs): self.value = value
    def get(self): return self.value
    def set(self, value): self.value = value
    def __str__(self): return 'test-variable'


class Widget:
    def __init__(self, *args, **kwargs): self.options = kwargs; self.bindings = {}
    def configure(self, *args, **kwargs): self.options.update(kwargs)
    def __setitem__(self, key, value): self.options[key] = value
    def grid(self, **kwargs): pass
    def pack(self, **kwargs): pass
    def columnconfigure(self, *args, **kwargs): pass
    def theme_use(self, *args): pass
    def title(self, value): self.options['title'] = value
    def geometry(self, *args): pass
    def minsize(self, *args): pass
    def protocol(self, *args): pass
    def after(self, *args): pass
    def destroy(self): pass
    def bind(self, event, callback): self.bindings[event] = callback


class CatalogTests(unittest.TestCase):
    def test_catalog_parity_placeholders_and_english_labels(self):
        self.assertEqual(set(MESSAGES['ru']), set(MESSAGES['en']))
        for key in MESSAGES['ru']:
            with self.subTest(key=key):
                def slots(text): return {n for _, n, _, _ in string.Formatter().parse(text) if n}
                self.assertEqual(slots(MESSAGES['ru'][key]), slots(MESSAGES['en'][key]))
                self.assertTrue(MESSAGES['ru'][key]); self.assertTrue(MESSAGES['en'][key])
                self.assertIsNone(re.search('[А-Яа-яЁё]', MESSAGES['en'][key]))
    def test_nested_validation_and_progress_keep_both_languages(self):
        error = joined([msg('file_missing', name=msg('model_label')), msg('port_range')])
        self.assertIn('FLUX.3 model: file not found', render(error, 'en'))
        self.assertIn('Модель FLUX.3: файл не найден', render(error, 'ru'))
        self.assertEqual(render(app.generation_progress('3/16 - 1.25s/it',16)[1], 'en'), 'Generating image: step 3 of 16')
        for number in (316,353,140):
            progress, label = app.generation_progress(f'{number}/{number} - 0.09MB/s',16)
            self.assertLess(progress,20); self.assertNotIn('step', render(label,'en'))
    def test_build_rejects_unavailable_tcl_and_incomplete_bundle(self):
        from desktop import build_windows
        import tkinter
        with patch.object(tkinter,'Tcl',side_effect=tkinter.TclError('unavailable')):
            with self.assertRaisesRegex(RuntimeError,'no package was built'): build_windows.check_tcl()
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(RuntimeError,'_tkinter.pyd'): build_windows.check_bundle(folder)
    def test_all_returned_presets_have_translated_titles_and_original_prompts(self):
        for source in ('cases.json','battle-cases.json'):
            for case in json.loads((ROOT/source).read_text(encoding='utf-8'))['cases']:
                if case.get('role')!='thematic-first-result' and not (case.get('variant')=='clear' and case['seed']==42): continue
                label=app.preset_title(case)
                self.assertEqual(str(label),case['title_ru'])
                self.assertIsNone(re.search('[А-Яа-яЁё]',render(label,'en')))
                self.assertTrue((ROOT/case['prompt_file']).is_file())


class ManagerLanguageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.base=Path(self.tmp.name)
        self.patches=[patch.object(launcher.tk,'Tk',Widget),patch.object(launcher.tk,'StringVar',Variable),patch.object(launcher,'detect_cuda',return_value='')]
        self.patches += [patch.object(launcher.ttk,name,Widget) for name in ('Frame','Label','Button','Entry','Combobox','Style','Progressbar','Separator')]
        for p in self.patches: p.start()
        self.window=launcher.Window(self.base)
    def tearDown(self):
        if self.window.controller.process: self.window.controller.stop()
        for p in reversed(self.patches): p.stop()
        self.tmp.cleanup()
    def switch(self, lang):
        self.window.language_var.set('English' if lang=='en' else 'Русский'); self.window.change_language()
    def finish(self):
        end=time.monotonic()+10
        while self.window.busy and time.monotonic()<end: self.window.drain(); time.sleep(.02)
        self.assertFalse(self.window.busy)
    def test_default_russian_and_restart_language_without_changing_paths(self):
        w=self.window; self.assertEqual(w.start_button.options['text'],'Запустить сервер')
        w.vars['llm'].set('user-selected-model.gguf'); w.port.set('8447')
        self.switch('en')
        self.assertEqual(w.start_button.options['text'],'Start server')
        self.assertEqual(w.vars['llm'].get(),'user-selected-model.gguf'); self.assertEqual(w.port.get(),'8447')
        self.assertFalse(w.config_path.exists())
        restarted=launcher.Window(self.base)
        self.assertEqual(restarted.lang,'en'); self.assertEqual(restarted.start_button.options['text'],'Start server')
        self.switch('ru'); self.assertEqual(w.root.options['title'],'FLUX.3 · Установка и запуск')
    def test_switch_during_operation_preserves_cancel_progress_and_errors(self):
        w=self.window; w.busy=True; w.cancel.set(); w.cancel_button.configure(state='normal')
        w.progress(2*1024**2,4*1024**2,msg('downloading',file='model.gguf')); w.drain()
        w.status.set(msg('selected_mismatch',file='existing.gguf')); self.switch('en')
        self.assertTrue(w.busy); self.assertTrue(w.cancel.is_set()); self.assertEqual(w.bar.options['value'],50)
        self.assertEqual(w.progress_text.get(),'Downloading: model.gguf · 2.0 / 4.0 MiB')
        self.assertIn('It was not replaced.',w.status.get()); self.assertEqual(w.cancel_button.options['state'],'normal')
        self.switch('ru'); self.assertIn('Он не заменён.',w.status.get())
    def test_selection_dialogs_use_language_without_opening_dialogs(self):
        self.switch('en'); w=self.window
        with patch.object(launcher.filedialog,'askdirectory',return_value=str(self.base/'chosen')) as dialog:
            w.choose_storage(); self.assertEqual(dialog.call_args.kwargs['title'],'Folder for downloaded models and engine')
            w.choose('sd_cli'); self.assertEqual(dialog.call_args.kwargs['title'],'Choose the folder containing sd-cli.exe')
            self.assertTrue(w.vars['sd_cli'].get().endswith('sd-cli.exe'))
        with patch.object(launcher.filedialog,'askopenfilename',return_value='chosen.gguf') as dialog:
            w.choose('llm'); self.assertEqual(dialog.call_args.kwargs['filetypes'][0][0],'Model files')
        self.assertEqual(w.vars['llm'].get(),'chosen.gguf')
    def test_settings_save_retains_language_and_unrelated_config(self):
        self.switch('en'); w=self.window; w.config['custom_value']='keep'
        for key in w.vars: w.vars[key].set(key+'.bin')
        values=w.values(); w.persist(values)
        self.assertEqual(json.loads(w.config_path.read_text())['custom_value'],'keep')
        self.assertEqual(json.loads(w.manager_path.read_text())['language'],'en')
        self.assertIn('Files verified',w.status.get())
    def test_bad_port_and_worker_error_translate_after_switch(self):
        w=self.window; w.port.set('invalid'); w.verify(); self.switch('en')
        self.assertEqual(w.status.get(),'Enter the port as an integer')
        def operation(): raise ValueError(msg('disk_download',file='model.gguf'))
        w.run(operation,lambda value: None); self.finish()
        self.assertEqual(w.status.get(),'Not enough free disk space for model.gguf')
        self.switch('ru'); self.assertIn('Недостаточно',w.status.get())
    @unittest.skipUnless(sys.platform=='win32','Windows lifecycle')
    def test_manager_callbacks_control_real_server_and_localized_http_without_window(self):
        w=self.window
        with socket.socket() as s: s.bind(('127.0.0.1',0)); w.port.set(str(s.getsockname()[1]))
        self.switch('en')
        with patch.object(w.installer,'validate',return_value=[]),patch.object(launcher.webbrowser,'open') as browser:
            w.start_button.options['command'](); self.finish()
            state=w.controller.state(); self.assertTrue(state)
            self.assertIn('?lang=en#session=',browser.call_args.args[0])
            def request(path, lang, authorized=True):
                headers={'Accept-Language':lang}
                if authorized: headers['X-Session']=state['url'].split('session=')[1]
                return urllib.request.urlopen(urllib.request.Request(state['base_url']+path,headers=headers),timeout=3)
            with request('/api/config','en') as response:
                config=json.load(response); self.assertIn('file not found',config['errors'][0]); self.assertIn('файл не найден',config['errors_i18n']['ru'][0])
            with request('/api/presets','en') as response:
                presets=json.load(response); self.assertEqual(len(presets),21); self.assertEqual(presets[0]['title'],'Portrait of a craftswoman')
            with request('/','en') as response: self.assertNotIn('__FLUX_MESSAGES__',response.read().decode())
            with request('/ui/app.js','en') as response: self.assertIn('setLanguage',response.read().decode())
            with self.assertRaises(urllib.error.HTTPError) as error: request('/api/current','en',False)
            with error.exception as response: self.assertIn('Session not verified',json.load(response)['error'])
            self.switch('ru'); w.poll(); self.assertIn('Сервер работает',w.server_status.get())
            self.assertEqual(w.controller.state()['instance'],state['instance'])
            with request('/api/current','en') as response: self.assertEqual(json.load(response),{'job':None,'active':False})
            w.stop_button.options['command'](); self.finish(); self.assertIsNone(w.controller.state())
            self.assertEqual(w.status.get(),'Сервер остановлен.')


if __name__=='__main__': unittest.main()
