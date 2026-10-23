# Сборка Windows Manager

Пользователю готового EXE эти действия не нужны. Сборщик работает на Windows x64. Испытаны Python 3.14.4 x64, Tcl/Tk 8.6 и PyInstaller 6.22.3. Python-пакеты сборки закреплены в `desktop/build-requirements.txt`. Изолированное окружение сборки не меняет CUDA или другие проекты.

```powershell
python -m venv .build-env
.build-env/Scripts/python.exe -m pip install -r desktop/build-requirements.txt
.build-env/Scripts/python.exe -B -m unittest discover -s tests -v
.build-env/Scripts/python.exe desktop/build_windows.py --output dist --work .build-work
```

Результат – вся папка `dist/FLUX3-Manager`, включая `_internal`. Упакуйте её целиком в ZIP. Модели, движок, CUDA, пользовательская конфигурация, сессии, журналы и корпус из 39 изображений в EXE не включаются.

Для сборки нужен рабочий Python с Tcl/Tk. Одного успешного выхода PyInstaller недостаточно. Для preview 0.1.1-preview выполнены программные проверки переводов, настроек и жизненного цикла сервера из EXE; окно не открывалось. Визуальная проверка окна и системных диалогов остаётся ограничением preview.

Переводы для обоих интерфейсов находятся в `ui/messages.json`; браузерный код – в `ui/app.js`. Вся папка `ui` включается в EXE. Дополнительные DOM-проверки: Node.js 24 и jsdom 30.0.1, затем `node tests/ui_languages.cjs`. jsdom нужен только для проверки, не пользователю приложения.

Для отдельной проверки: `FLUX3-Manager.exe --settings-dir <отдельная-папка>`. Служебные `--server` и `--generate-worker` используются приложением. `--worker-check <файл.json>` проверяет включённые ресурсы и импорты без модели. Источники и EXE должны относиться к одной версии.

Побайтовая детерминированность повторной сборки EXE не заявлена. Конкретный выпуск закрепляется SHA256 и манифестом файлов; сведения – в `desktop/release.json`. После изменения исходников нужна новая сборка и проверка.

Сборщик теперь отклоняет недоступный Tcl до PyInstaller и неполный комплект Tcl/Tk после сборки. Эти проверки не создают окно.

```powershell
npm install --prefix "$env:TEMP/flux3-ui-tests" --no-audit --no-fund jsdom@30.0.1
$env:NODE_PATH = "$env:TEMP/flux3-ui-tests/node_modules"
node tests/ui_languages.cjs
```
