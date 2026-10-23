"""FLUX3 Manager: native setup window and bundled worker entry points."""
import argparse
import json
import os
from pathlib import Path
import queue
import sys
import threading
import webbrowser

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT))

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from desktop.core import Cancelled, Installer, ServerController, detect_cuda, save
from scripts.i18n import msg, joined, render, language, error_message
UI_LANGUAGE = 'ru'


class TranslatedVar:
    """Retain the original message while Tk holds only its rendered string."""
    def __init__(self, owner, value=''):
        self.owner = owner
        self.var = tk.StringVar()
        owner.translated_vars.append(self)
        self.set(value)

    def __str__(self):
        return str(self.var)

    def set(self, value):
        self.message = value
        self.refresh()

    def get(self):
        return self.var.get()

    def refresh(self):
        self.var.set(render(self.message, self.owner.lang))


class Window:
    def __init__(self, settings_dir):
        global UI_LANGUAGE
        self.settings = settings_dir.resolve()
        self.settings.mkdir(parents=True, exist_ok=True)
        self.config_path = self.settings / 'config.local.json'
        self.manager_path = self.settings / 'manager.json'
        self.root = tk.Tk()
        self.text_widgets = []
        self.translated_vars = []
        self.root.geometry('1000x790')
        self.root.minsize(920, 720)
        self.root.configure(background='#eef3f3')
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.closing = False
        self.destroyed = False
        self.verified = None
        self.installer = Installer()
        self.controller = ServerController(self.config_path)
        self.config = json.loads(self.config_path.read_text(encoding='utf-8')) if self.config_path.is_file() else {}
        manager = json.loads(self.manager_path.read_text(encoding='utf-8')) if self.manager_path.is_file() else {}
        self.lang = language(manager.get('language'))
        UI_LANGUAGE = self.lang
        self.language_var = tk.StringVar(value='English' if self.lang == 'en' else 'Русский')
        self.storage = tk.StringVar(value=manager.get('storage', str(self.settings / 'data')))
        self.vars = {k: tk.StringVar(value=str(self.config.get(k, ''))) for k in ('sd_cli', 'diffusion_model', 'llm', 'vae', 'cuda_bin')}
        if not self.vars['cuda_bin'].get():
            self.vars['cuda_bin'].set(detect_cuda())
        self.port = tk.StringVar(value=str(self.config.get('port', 8440)))
        self.status = TranslatedVar(self, msg('initial_status'))
        self.server_status = TranslatedVar(self, msg('server_stopped'))
        self.progress_text = TranslatedVar(self)
        self.action_widgets = []
        self.edit_widgets = []
        self.render(ttk)
        self.apply_language()
        self.root.after(100, self.drain)
        self.root.after(500, self.poll)

    def render(self, ttk):
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 10))
        style.configure('TFrame', background='#eef3f3')
        style.configure('TLabel', background='#eef3f3', foreground='#203c42')
        style.configure('Heading.TLabel', font=('Segoe UI', 23, 'bold'))
        style.configure('Section.TLabel', font=('Segoe UI', 12, 'bold'))
        style.configure('TButton', padding=(12, 7))
        style.configure('Primary.TButton', foreground='white', background='#245867')
        body = ttk.Frame(self.root, padding=24)
        body.pack(fill='both', expand=True)
        body.columnconfigure(1, weight=1)
        selector = ttk.Combobox(body, textvariable=self.language_var, values=('Русский', 'English'), state='readonly', width=11)
        selector.grid(row=0, column=2, sticky='e')
        selector.bind('<<ComboboxSelected>>', self.change_language)
        self.label(body, text=msg('manager_heading'), style='Heading.TLabel').grid(row=0, column=0, columnspan=2, sticky='w')
        self.label(body, text=msg('manager_subtitle')).grid(row=1, column=0, columnspan=3, sticky='w', pady=(4, 18))
        self.label(body, text=msg('storage_heading'), style='Section.TLabel').grid(row=2, column=0, columnspan=3, sticky='w')
        entry = ttk.Entry(body, textvariable=self.storage)
        entry.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(8, 4))
        self.edit_widgets.append(entry)
        button = self.button(body, text=msg('choose_folder'), command=self.choose_storage)
        button.grid(row=3, column=2, padx=(10, 0))
        self.edit_widgets.append(button)
        size = sum(a['bytes'] for a in self.installer.lock['downloads']) / 1024**3
        self.label(body, text=msg('download_size', size=f'{size:.2f}')).grid(row=4, column=0, columnspan=3, sticky='w', pady=(2, 18))
        self.label(body, text=msg('existing_heading'), style='Section.TLabel').grid(row=5, column=0, columnspan=3, sticky='w')
        names = [('sd_cli', msg('engine_folder')), ('diffusion_model', msg('model_label')), ('llm', msg('qwen_short')), ('vae', msg('vae_label')), ('cuda_bin', msg('cuda_folder'))]
        for row, (key, title) in enumerate(names, 6):
            self.label(body, text=title).grid(row=row, column=0, sticky='w', padx=(0, 12), pady=5)
            entry = ttk.Entry(body, textvariable=self.vars[key])
            entry.grid(row=row, column=1, sticky='ew')
            button = self.button(body, text=msg('browse'), command=lambda k=key: self.choose(k))
            button.grid(row=row, column=2, padx=(10, 0))
            self.edit_widgets += [entry, button]
        self.label(body, text=msg('reuse_hint')).grid(row=11, column=0, columnspan=3, sticky='w', pady=(4, 10))
        actions = ttk.Frame(body)
        actions.grid(row=12, column=0, columnspan=3, sticky='w')
        self.download_button = self.button(actions, text=msg('download_missing'), style='Primary.TButton', command=self.install)
        self.download_button.pack(side='left')
        self.check_button = self.button(actions, text=msg('check_save'), command=self.verify)
        self.check_button.pack(side='left', padx=8)
        self.cancel_button = self.button(actions, text=msg('cancel_download'), command=self.cancel.set, state='disabled')
        self.cancel_button.pack(side='left')
        self.button(actions, text=msg('terms'), command=lambda: webbrowser.open('https://github.com/black-forest-labs/flux-3-image-klein')).pack(side='left', padx=(8, 0))
        self.action_widgets += [self.download_button, self.check_button]
        self.label(body, textvariable=self.progress_text, wraplength=920).grid(row=13, column=0, columnspan=3, sticky='w', pady=(12, 4))
        self.bar = ttk.Progressbar(body, maximum=100)
        self.bar.grid(row=14, column=0, columnspan=3, sticky='ew')
        self.label(body, textvariable=self.status, wraplength=920).grid(row=15, column=0, columnspan=3, sticky='w', pady=(8, 16))
        ttk.Separator(body).grid(row=16, column=0, columnspan=3, sticky='ew', pady=(0, 15))
        self.label(body, text=msg('generation_heading'), style='Section.TLabel').grid(row=17, column=0, columnspan=3, sticky='w')
        server = ttk.Frame(body)
        server.grid(row=18, column=0, columnspan=3, sticky='ew', pady=10)
        self.start_button = self.button(server, text=msg('start_server'), style='Primary.TButton', command=self.start)
        self.start_button.pack(side='left')
        self.open_button = self.button(server, text=msg('open_generator'), command=self.open_browser, state='disabled')
        self.open_button.pack(side='left', padx=8)
        self.stop_button = self.button(server, text=msg('stop_server'), command=self.stop, state='disabled')
        self.stop_button.pack(side='left')
        self.label(server, text=msg('port_label')).pack(side='left', padx=(14, 4))
        port_entry = ttk.Entry(server, textvariable=self.port, width=7)
        port_entry.pack(side='left')
        self.edit_widgets.append(port_entry)
        self.action_widgets += [self.start_button, self.stop_button]
        self.label(body, textvariable=self.server_status).grid(row=19, column=0, columnspan=3, sticky='w')
        self.label(body, text=msg('close_hint'), wraplength=920).grid(row=20, column=0, columnspan=3, sticky='w', pady=(8, 0))

    def localized_widget(self, kind, parent, **kwargs):
        message = kwargs.get('text')
        if message is not None:
            kwargs['text'] = render(message, self.lang)
        widget = kind(parent, **kwargs)
        if message is not None:
            self.text_widgets.append((widget, message))
        return widget

    def label(self, parent, **kwargs):
        return self.localized_widget(ttk.Label, parent, **kwargs)

    def button(self, parent, **kwargs):
        return self.localized_widget(ttk.Button, parent, **kwargs)

    def apply_language(self):
        self.root.title(render(msg('manager_title'), self.lang))
        for widget, message in self.text_widgets:
            widget.configure(text=render(message, self.lang))
        for value in self.translated_vars:
            value.refresh()

    def save_preferences(self, storage=False):
        data = json.loads(self.manager_path.read_text(encoding='utf-8')) if self.manager_path.is_file() else {}
        data['language'] = self.lang
        if storage:
            data['storage'] = self.storage.get()
        save(self.manager_path, data)

    def change_language(self, event=None):
        global UI_LANGUAGE
        self.lang = 'en' if self.language_var.get() == 'English' else 'ru'
        UI_LANGUAGE = self.lang
        self.apply_language()
        try:
            self.save_preferences()
        except OSError as error:
            self.status.set(error_message(error))

    def browser_url(self, state):
        base, fragment = state['url'].split('#', 1)
        return base + '?lang=' + self.lang + '#' + fragment

    def choose_storage(self):
        selected = filedialog.askdirectory(parent=self.root, title=render(msg('storage_dialog'), self.lang), initialdir=self.storage.get())
        if selected:
            self.storage.set(selected)

    def choose(self, key):
        if key in ('sd_cli', 'cuda_bin'):
            selected = filedialog.askdirectory(parent=self.root, title=render(msg('engine_dialog' if key == 'sd_cli' else 'cuda_dialog'), self.lang))
            if selected and key == 'sd_cli':
                selected = str(Path(selected) / 'sd-cli.exe')
            if selected and key == 'cuda_bin':
                from desktop.core import cuda_bin
                found = cuda_bin(selected)
                selected = str(found or Path(selected))
        else:
            selected = filedialog.askopenfilename(parent=self.root, title=render(msg('model_dialog', file=self.installer.lock['configured_assets'][key]['file']), self.lang), filetypes=[(render(msg('model_files'), self.lang), '*.gguf *.safetensors'), (render(msg('all_files'), self.lang), '*.*')])
        if selected:
            self.vars[key].set(selected)
            self.verified = None

    def values(self):
        values = dict(self.config)
        values.update({k: v.get().strip() for k, v in self.vars.items()})
        try:
            values['port'] = int(self.port.get())
        except ValueError:
            raise ValueError(msg('port_integer'))
        values.update(max_vram_gib=6, timeout_seconds=900, cuda_runtime_dir='')
        return values

    def progress(self, done, total, text):
        self.events.put(('progress', (done, total, text)))

    def run(self, operation, success, allow_cancel=False):
        if self.busy:
            return
        self.busy = True
        self.cancel.clear()
        self.status.set(msg('operation_running'))
        for widget in self.action_widgets + self.edit_widgets:
            widget.configure(state='disabled')
        self.cancel_button.configure(state='normal' if allow_cancel else 'disabled')
        def work():
            try:
                result = operation()
                self.events.put(('success', (success, result)))
            except Exception as error:
                self.events.put(('error', (msg('cancelled') if isinstance(error, Cancelled) else error_message(error))))
            finally:
                self.events.put(('finished', None))
        threading.Thread(target=work, daemon=True).start()

    def persist(self, values):
        save(self.config_path, values)
        self.save_preferences(storage=True)
        self.config = values
        self.verified = dict(values)
        for k, v in self.vars.items():
            v.set(values[k])
        self.status.set(msg('ready_saved'))
        self.bar['value'] = 100

    def verify_values(self, values):
        errors = self.installer.validate(values, self.cancel, self.progress)
        if errors:
            raise ValueError(joined(errors[:4] + ([msg('more_errors', count=len(errors)-4)] if len(errors)>4 else [])))
        return values

    def verify(self):
        try:
            values = self.values()
        except ValueError as e:
            self.status.set(error_message(e)); return
        self.run(lambda: self.verify_values(values), self.persist, True)

    def install(self):
        try:
            values = self.values()
        except ValueError as e:
            self.status.set(error_message(e)); return
        if self.controller.state():
            self.status.set(msg('stop_before_install')); return
        storage = self.storage.get().strip()
        if not storage:
            self.status.set(msg('choose_storage')); return
        self.run(lambda: self.installer.install(values, storage, self.cancel, self.progress), self.persist, True)

    def start(self):
        try:
            values = self.values()
        except ValueError as e:
            self.status.set(error_message(e)); return
        def operation():
            if self.verified != values:
                self.verify_values(values)
            save(self.config_path, values)
            return self.controller.start()
        def started(state):
            self.config = values
            self.verified = dict(values)
            self.save_preferences(storage=True)
            self.status.set(msg('server_started'))
            webbrowser.open(self.browser_url(state))
        self.run(operation, started)

    def open_browser(self):
        state = self.controller.state()
        if state:
            webbrowser.open(self.browser_url(state))
        else:
            self.status.set(msg('server_open_hint'))

    def stop(self):
        self.run(self.controller.stop, lambda _: self.status.set(msg('server_stopped_full')))

    def poll(self):
        if not self.busy:
            state = self.controller.state()
            running = bool(state)
            self.server_status.set(msg('server_running', url=state['base_url']) if running else msg('server_stopped'))
            self.open_button.configure(state='normal' if running else 'disabled')
            self.stop_button.configure(state='normal' if running else 'disabled')
            self.start_button.configure(state='disabled' if running else 'normal')
            for w in self.edit_widgets + [self.download_button, self.check_button]:
                w.configure(state='disabled' if running else 'normal')
        self.root.after(1200, self.poll)

    def drain(self):
        while True:
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'progress':
                done, total, text = value
                self.bar['value'] = min(100, 100 * done / max(1, total))
                self.progress_text.set(joined([text, msg('transfer_units', done=f'{done / 1024**2:.1f}', total=f'{total / 1024**2:.1f}')] if total > 1024 else [text], ''))
            elif kind == 'success':
                callback, result = value
                callback(result)
                if self.destroyed:
                    return
            elif kind == 'error':
                self.status.set(value)
                self.verified = None
            elif kind == 'finished':
                self.busy = False
                self.cancel_button.configure(state='disabled')
                for w in self.action_widgets + self.edit_widgets:
                    w.configure(state='normal')
                if self.closing:
                    self.closing = False
                    self.close()
        self.root.after(100, self.drain)

    def close(self):
        if self.busy:
            self.closing = True
            self.cancel.set()
            self.status.set(msg('closing'))
            return
        if self.controller.state() or self.controller.process:
            self.run(self.controller.stop, lambda _: self.destroy())
        else:
            self.destroy()

    def destroy(self):
        self.destroyed = True
        self.root.destroy()



def main():
    if len(sys.argv) > 1 and sys.argv[1] in ('--server', '--generate-worker'):
        mode = sys.argv.pop(1)
        if mode == '--server':
            import app
            app.main()
        else:
            import generate
            generate.main()
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--worker-check':
        # Tests the frozen dispatch/imports/resources without a model or GPU job.
        import app
        import generate
        from desktop.core import save
        save(Path(sys.argv[2]), dict(frozen=bool(getattr(sys, 'frozen', False)), app_root_ok=app.ROOT == ROOT,
             generator_root_ok=generate.ROOT == ROOT, resource_checks={p: (ROOT / p).is_file() for p in
             ['ui/index.html', 'ui/app.js', 'ui/messages.json', 'assets.lock.json', 'config.example.json', 'cases.json', 'battle-cases.json', 'prompts/people-portrait.txt']},
             languages=['ru','en'], english_step=render(msg('sample_step',step=3,steps=16),'en'),
             tcl_patchlevel=tk.Tcl().eval('info patchlevel')))
        return
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--settings-dir', type=Path, default=Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'FLUX3Pascal')
    args = ap.parse_args()
    window = Window(args.settings_dir)
    window.root.mainloop()


if __name__ == '__main__':
    service_mode = len(sys.argv) > 1 and sys.argv[1] in ('--server', '--generate-worker', '--worker-check')
    try:
        main()
    except Exception as error:
        if service_mode:
            raise
        import tkinter.messagebox
        tkinter.messagebox.showerror('FLUX.3', render(msg('open_failed', detail=error_message(error)), UI_LANGUAGE))
        raise
