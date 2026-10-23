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
             ['ui/index.html', 'assets.lock.json', 'config.example.json', 'cases.json', 'battle-cases.json', 'prompts/people-portrait.txt']}))
        return
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--settings-dir', type=Path, default=Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'FLUX3Pascal')
    args = ap.parse_args()
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    from desktop.core import Cancelled, Installer, ServerController, detect_cuda, save

    class Window:
        def __init__(self):
            self.settings = args.settings_dir.resolve()
            self.settings.mkdir(parents=True, exist_ok=True)
            self.config_path = self.settings / 'config.local.json'
            self.manager_path = self.settings / 'manager.json'
            self.root = tk.Tk()
            self.root.title('FLUX.3 · Установка и запуск')
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
            self.storage = tk.StringVar(value=manager.get('storage', str(self.settings / 'data')))
            self.vars = {k: tk.StringVar(value=str(self.config.get(k, ''))) for k in ('sd_cli', 'diffusion_model', 'llm', 'vae', 'cuda_bin')}
            if not self.vars['cuda_bin'].get():
                self.vars['cuda_bin'].set(detect_cuda())
            self.port = tk.StringVar(value=str(self.config.get('port', 8440)))
            self.status = tk.StringVar(value='Выберите имеющиеся файлы или скачайте недостающие. Затем проверьте готовность.')
            self.server_status = tk.StringVar(value='Сервер остановлен')
            self.progress_text = tk.StringVar(value='')
            self.action_widgets = []
            self.edit_widgets = []
            self.render(ttk)
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
            ttk.Label(body, text='FLUX.3 на вашем компьютере', style='Heading.TLabel').grid(row=0, column=0, columnspan=3, sticky='w')
            ttk.Label(body, text='Установка и управление сервером · Windows x64 · профиль Pascal 8 ГБ').grid(row=1, column=0, columnspan=3, sticky='w', pady=(4, 18))
            ttk.Label(body, text='1. Где хранить скачанные файлы', style='Section.TLabel').grid(row=2, column=0, columnspan=3, sticky='w')
            entry = ttk.Entry(body, textvariable=self.storage)
            entry.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(8, 4))
            self.edit_widgets.append(entry)
            button = ttk.Button(body, text='Выбрать папку…', command=self.choose_storage)
            button.grid(row=3, column=2, padx=(10, 0))
            self.edit_widgets.append(button)
            size = sum(a['bytes'] for a in self.installer.lock['downloads']) / 1024**3
            ttk.Label(body, text=f'Движок и модели: до {size:.2f} ГиБ загрузки. Для установки оставьте около 10 ГиБ свободного места.').grid(row=4, column=0, columnspan=3, sticky='w', pady=(2, 18))
            ttk.Label(body, text='2. Уже есть файлы? Укажите их здесь', style='Section.TLabel').grid(row=5, column=0, columnspan=3, sticky='w')
            names = [('sd_cli', 'Папка движка'), ('diffusion_model', 'Модель FLUX.3'), ('llm', 'Кодировщик Qwen'), ('vae', 'Декодер VAE'), ('cuda_bin', 'Папка CUDA bin')]
            for row, (key, title) in enumerate(names, 6):
                ttk.Label(body, text=title).grid(row=row, column=0, sticky='w', padx=(0, 12), pady=5)
                entry = ttk.Entry(body, textvariable=self.vars[key])
                entry.grid(row=row, column=1, sticky='ew')
                button = ttk.Button(body, text='Обзор…', command=lambda k=key: self.choose(k))
                button.grid(row=row, column=2, padx=(10, 0))
                self.edit_widgets += [entry, button]
            ttk.Label(body, text='Пустые поля заполнятся при скачивании. Имеющаяся CUDA 12 используется без переустановки.').grid(row=11, column=0, columnspan=3, sticky='w', pady=(4, 10))
            actions = ttk.Frame(body)
            actions.grid(row=12, column=0, columnspan=3, sticky='w')
            self.download_button = ttk.Button(actions, text='Скачать недостающее', style='Primary.TButton', command=self.install)
            self.download_button.pack(side='left')
            self.check_button = ttk.Button(actions, text='Проверить и сохранить', command=self.verify)
            self.check_button.pack(side='left', padx=8)
            self.cancel_button = ttk.Button(actions, text='Отменить загрузку', command=self.cancel.set, state='disabled')
            self.cancel_button.pack(side='left')
            ttk.Button(actions, text='Условия использования', command=lambda: webbrowser.open('https://github.com/black-forest-labs/flux-3-image-klein')).pack(side='left', padx=(8, 0))
            self.action_widgets += [self.download_button, self.check_button]
            ttk.Label(body, textvariable=self.progress_text, wraplength=920).grid(row=13, column=0, columnspan=3, sticky='w', pady=(12, 4))
            self.bar = ttk.Progressbar(body, maximum=100)
            self.bar.grid(row=14, column=0, columnspan=3, sticky='ew')
            ttk.Label(body, textvariable=self.status, wraplength=920).grid(row=15, column=0, columnspan=3, sticky='w', pady=(8, 16))
            ttk.Separator(body).grid(row=16, column=0, columnspan=3, sticky='ew', pady=(0, 15))
            ttk.Label(body, text='3. Генерация изображений', style='Section.TLabel').grid(row=17, column=0, columnspan=3, sticky='w')
            server = ttk.Frame(body)
            server.grid(row=18, column=0, columnspan=3, sticky='ew', pady=10)
            self.start_button = ttk.Button(server, text='Запустить сервер', style='Primary.TButton', command=self.start)
            self.start_button.pack(side='left')
            self.open_button = ttk.Button(server, text='Открыть генератор', command=self.open_browser, state='disabled')
            self.open_button.pack(side='left', padx=8)
            self.stop_button = ttk.Button(server, text='Остановить сервер', command=self.stop, state='disabled')
            self.stop_button.pack(side='left')
            ttk.Label(server, text='  Порт:').pack(side='left', padx=(14, 4))
            port_entry = ttk.Entry(server, textvariable=self.port, width=7)
            port_entry.pack(side='left')
            self.edit_widgets.append(port_entry)
            self.action_widgets += [self.start_button, self.stop_button]
            ttk.Label(body, textvariable=self.server_status).grid(row=19, column=0, columnspan=3, sticky='w')
            ttk.Label(body, text='Закрытие этого окна останавливает его сервер. Скачайте готовый PNG до следующей генерации или выхода.', wraplength=920).grid(row=20, column=0, columnspan=3, sticky='w', pady=(8, 0))

        def choose_storage(self):
            selected = filedialog.askdirectory(parent=self.root, title='Папка для скачанных моделей и движка', initialdir=self.storage.get())
            if selected:
                self.storage.set(selected)

        def choose(self, key):
            if key in ('sd_cli', 'cuda_bin'):
                selected = filedialog.askdirectory(parent=self.root, title='Выберите папку ' + ('с sd-cli.exe' if key == 'sd_cli' else 'CUDA или CUDA bin'))
                if selected and key == 'sd_cli':
                    selected = str(Path(selected) / 'sd-cli.exe')
                if selected and key == 'cuda_bin':
                    from desktop.core import cuda_bin
                    found = cuda_bin(selected)
                    selected = str(found or Path(selected))
            else:
                selected = filedialog.askopenfilename(parent=self.root, title='Выберите ' + self.installer.lock['configured_assets'][key]['file'], filetypes=[('Файлы моделей', '*.gguf *.safetensors'), ('Все файлы', '*.*')])
            if selected:
                self.vars[key].set(selected)
                self.verified = None

        def values(self):
            values = dict(self.config)
            values.update({k: v.get().strip() for k, v in self.vars.items()})
            try:
                values['port'] = int(self.port.get())
            except ValueError:
                raise ValueError('Введите номер порта целым числом')
            values.update(max_vram_gib=6, timeout_seconds=900, cuda_runtime_dir='')
            return values

        def progress(self, done, total, text):
            self.events.put(('progress', (done, total, text)))

        def run(self, operation, success, allow_cancel=False):
            if self.busy:
                return
            self.busy = True
            self.cancel.clear()
            self.status.set('Операция выполняется…')
            for widget in self.action_widgets + self.edit_widgets:
                widget.configure(state='disabled')
            self.cancel_button.configure(state='normal' if allow_cancel else 'disabled')
            def work():
                try:
                    result = operation()
                    self.events.put(('success', (success, result)))
                except Exception as error:
                    self.events.put(('error', ('Отменено' if isinstance(error, Cancelled) else str(error))))
                finally:
                    self.events.put(('finished', None))
            threading.Thread(target=work, daemon=True).start()

        def persist(self, values):
            save(self.config_path, values)
            save(self.manager_path, dict(storage=self.storage.get()))
            self.config = values
            self.verified = dict(values)
            for k, v in self.vars.items():
                v.set(values[k])
            self.status.set('Готово. Файлы проверены, настройки сохранены. Можно запускать сервер.')
            self.bar['value'] = 100

        def verify_values(self, values):
            errors = self.installer.validate(values, self.cancel, self.progress)
            if errors:
                raise ValueError('\n'.join(errors[:4]) + (f'\nИ ещё {len(errors)-4} ошибок. Выберите полный каталог движка.' if len(errors)>4 else ''))
            return values

        def verify(self):
            try:
                values = self.values()
            except ValueError as e:
                self.status.set(str(e)); return
            self.run(lambda: self.verify_values(values), self.persist, True)

        def install(self):
            try:
                values = self.values()
            except ValueError as e:
                self.status.set(str(e)); return
            if self.controller.state():
                self.status.set('Сначала остановите сервер, чтобы изменить его файлы.'); return
            storage = self.storage.get().strip()
            if not storage:
                self.status.set('Выберите папку для скачивания.'); return
            self.run(lambda: self.installer.install(values, storage, self.cancel, self.progress), self.persist, True)

        def start(self):
            try:
                values = self.values()
            except ValueError as e:
                self.status.set(str(e)); return
            def operation():
                if self.verified != values:
                    self.verify_values(values)
                save(self.config_path, values)
                return self.controller.start()
            def started(state):
                self.config = values
                self.verified = dict(values)
                save(self.manager_path, dict(storage=self.storage.get()))
                self.status.set('Сервер запущен. Генератор открыт в браузере.')
                webbrowser.open(state['url'])
            self.run(operation, started)

        def open_browser(self):
            state = self.controller.state()
            if state:
                webbrowser.open(state['url'])
            else:
                self.status.set('Сервер остановлен. Нажмите «Запустить сервер».')

        def stop(self):
            self.run(self.controller.stop, lambda _: self.status.set('Сервер остановлен.'))

        def poll(self):
            if not self.busy:
                state = self.controller.state()
                running = bool(state)
                self.server_status.set('Сервер работает · ' + state['base_url'] if running else 'Сервер остановлен')
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
                    self.progress_text.set(text + (f' · {done / 1024**2:.1f} / {total / 1024**2:.1f} МиБ' if total > 1024 else ''))
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
                self.status.set('Завершение операции перед закрытием…')
                return
            if self.controller.state() or self.controller.process:
                self.run(self.controller.stop, lambda _: self.destroy())
            else:
                self.destroy()

        def destroy(self):
            self.destroyed = True
            self.root.destroy()

    window = Window()
    window.root.mainloop()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        import tkinter.messagebox
        tkinter.messagebox.showerror('FLUX.3', 'Не удалось открыть приложение: ' + str(error))
        raise
