# Сборка Windows Manager

Пользователю готового EXE эти действия не нужны. Сборщик работает на Windows x64. Испытаны Python 3.14.4 x64, Tcl/Tk 8.6 и PyInstaller 6.22.3. Python-пакеты сборки закреплены в `desktop/build-requirements.txt`. Изолированное окружение сборки не меняет CUDA или другие проекты.

```powershell
python -m venv .build-env
.build-env/Scripts/python.exe -m pip install -r desktop/build-requirements.txt
.build-env/Scripts/python.exe -B -m unittest discover -s tests -v
.build-env/Scripts/python.exe desktop/build_windows.py --output dist --work .build-work
```

Результат – вся папка `dist/FLUX3-Manager`, включая `_internal`. Упакуйте её целиком в ZIP. Модели, движок, CUDA, пользовательская конфигурация, сессии, журналы и корпус из 39 изображений в EXE не включаются.

Перед сборкой `python -m tkinter` должен открывать тестовое окно. Сообщение `tkinter installation is broken` означает, что сборку нельзя считать пригодной: нужен рабочий Python с Tcl/Tk. Одного успешного выхода PyInstaller недостаточно; EXE проверяется открытием окна, сохранением настроек и циклом запуска/остановки сервера.

Для отдельной проверки: `FLUX3-Manager.exe --settings-dir <отдельная-папка>`. Служебные `--server` и `--generate-worker` используются приложением. `--worker-check <файл.json>` проверяет включённые ресурсы и импорты без модели. Источники и EXE должны относиться к одной версии.

Побайтовая детерминированность повторной сборки EXE не заявлена. Конкретный выпуск закрепляется SHA256 и манифестом файлов; сведения – в `desktop/release.json`. После изменения исходников нужна новая сборка и проверка.
