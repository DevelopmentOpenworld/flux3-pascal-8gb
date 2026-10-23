# FLUX.3 Pascal 8GB · 0.1.1-preview

Генератор и Windows Manager теперь переключаются между **Русский / English**. Переведены подписи, подсказки, примеры, проверки, ошибки и этапы операций. Выбор языка сохраняется; промпт, параметры, пути, текущий PNG и выполняющаяся операция сохраняются при переключении. Новый запрос генерации не отправляется.

Windows ZIP пересобран из этой версии исходников. Для обновления остановите сервер старым Manager, закройте его и распакуйте новый пакет отдельно. Настройки, выбранные модели и установленная CUDA переиспользуются. [Инструкция](docs/INTERFACE.md) · [English guide](docs/INTERFACE_EN.md).

Проверки выполнены программно, без computer use, открытия нативного окна и новых GPU-генераций: Python-тесты, DOM, встроенные ресурсы EXE и его отдельный сервер. В тестах Manager виджеты и диалоги заменены заглушками. Отрисовка окна, нажатия настоящих кнопок, системные диалоги и установка на чистой машине **не подтверждены**. EXE не подписан; статус preview сохранён.

39 контрольных PNG, промпты, замеры и автономные RU/EN отчёты из 0.1.0-preview сохранены. 14 из 18 исходных тематических кадров уложились в минуту; ни один из восьми уточнённых боевых кадров не получил полного PASS. Эти прежние измерения не являются новым бенчмарком сборки 0.1.1.

## English

The generator and Windows Manager now support **Русский / English** with a saved choice. Labels, hints, presets, validation, errors and operation stages are translated. Switching preserves prompts, paths, parameters, the current PNG and active operations; it never submits a new generation.

The Windows package is rebuilt from this source version. Stop the old server, close the old Manager and extract the new package into a separate folder. Existing settings, selected models and installed CUDA are reused.

Checks are programmatic: Python, DOM, bundled resources and an isolated server from the actual EXE. No computer use, native window or new GPU generations. Manager widgets/dialogs are replaced in tests; real native controls, layout, system dialogs and clean-machine setup remain **unverified**. The EXE is unsigned; this remains a preview.

The 39 control PNGs, prompts, measurements and standalone RU/EN reports from 0.1.0-preview are preserved. Prior performance/quality observations are not a new benchmark of 0.1.1. MIT covers project code/documentation; external components and model outputs retain their separate terms.
