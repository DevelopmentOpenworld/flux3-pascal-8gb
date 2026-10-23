# FLUX.3 Image Klein на GTX 1070 Ti 8 ГБ

**Предварительный выпуск 0.1.0-preview.** Сервер и генерация проверены программно. Полный путь через кнопки нативного Manager и установка на чистой машине не подтверждены.

Воспроизводимый запуск на Windows и Pascal sm_61: stable-diffusion.cpp CUDA 12, FLUX.3 Q4_0, Qwen3-VL 4B Q4_K_M и FLUX.2 VAE. Измерения выполнены с уже установленным CUDA Toolkit 12.6.85. Графический Manager использует имеющуюся CUDA 12 или скачивает локальные библиотеки, когда их нет. PyTorch не требуется.

- [Скачать автономный интерактивный отчёт](https://github.com/DevelopmentOpenworld/flux3-pascal-8gb/releases/download/v0.1.0-preview/FLUX3-Pascal-Report.html) – шесть тем, сравнение боёв и разрешений.
- [Точные файлы, версии, SHA256 и команды](docs/REPRODUCE.md).
- [Публичный генератор](docs/INTERFACE.md) – настройки и только текущий результат.
- [Все контрольные бои](docs/BATTLES.md), [галерея](docs/GALLERY.md), [CSV](results.csv), [JSON](results.json).

## Фрагменты отчёта: изображения и замеры

**[Скачать полный интерактивный отчёт →](https://github.com/DevelopmentOpenworld/flux3-pascal-8gb/releases/download/v0.1.0-preview/FLUX3-Pascal-Report.html)** · [Все изображения и замечания](docs/GALLERY.md) · [Таблица результатов](docs/RESULTS.md)

Ниже шесть примеров из разных тематик и отдельная перепроверка боёв. Во всём корпусе сохранены 39 первых результатов заданных условий, включая неудачные. Это иллюстрации из ограниченной выборки, не гарантия качества на произвольном промпте. Нажатие на изображение открывает исходный PNG.

**Профиль этих кадров:** GTX 1070 Ti 8 ГБ, Windows 10, 32 ГиБ RAM; FLUX.3 Q4_0, 16 шагов, CFG1, Euler/discrete, seed42 и бюджет движка 6 ГиБ VRAM. Время включает чтение весов новым процессом и сохранение PNG. Файловый кэш Windows не очищался. «VRAM карты» – максимум занятой видеопамяти всей карты по выборке примерно раз в секунду, включая рабочий стол.

<table>
<tr>
<td width="50%" valign="top">
<p><strong>Персоны · Портрет мастерицы</strong></p>
<a href="results/batch-people-portrait/image.png"><img src="results/batch-people-portrait/image.png" width="420" alt="Персоны · Портрет мастерицы; seed 42"></a>
<p><strong>59,2 с</strong> · 768×768 · VRAM карты: 5408 МиБ</p>
<p>Лицо, фактура кожи и свет. Кисти рук в кадр не входят.</p>
<p><a href="prompts/people-portrait.txt">Промпт</a> · <a href="results/batch-people-portrait/record.json">Параметры и замеры</a></p>
</td>
<td width="50%" valign="top">
<p><strong>Хай-тек · Станция «Орбита»</strong></p>
<a href="results/batch-hitech-location/image.png"><img src="results/batch-hitech-location/image.png" width="420" alt="Хай-тек · Станция «Орбита»; seed 42"></a>
<p><strong>60,3 с</strong> · 768×768 · VRAM карты: 5402 МиБ</p>
<p>Надпись «ОРБИТА», панорамное окно и планета. Табло заметно доминирует в композиции.</p>
<p><a href="prompts/hitech-location.txt">Промпт</a> · <a href="results/batch-hitech-location/record.json">Параметры и замеры</a></p>
</td>
</tr>
<tr>
<td width="50%" valign="top">
<p><strong>Загородный пейзаж · Зимний дом у леса</strong></p>
<a href="results/batch-rural-winter/image.png"><img src="results/batch-rural-winter/image.png" width="420" alt="Загородный пейзаж · Зимний дом у леса; seed 42"></a>
<p><strong>46,4 с</strong> · 864×480 · VRAM карты: 4539 МиБ</p>
<p>Надпись «ТЁПЛЫЙ ДОМ», снег и тёплый свет окон.</p>
<p><a href="prompts/rural-winter.txt">Промпт</a> · <a href="results/batch-rural-winter/record.json">Параметры и замеры</a></p>
</td>
<td width="50%" valign="top">
<p><strong>Городской пейзаж · Москва после дождя</strong></p>
<a href="results/batch-urban-moscow/image.png"><img src="results/batch-urban-moscow/image.png" width="420" alt="Городской пейзаж · Москва после дождя; seed 42"></a>
<p><strong>49,1 с</strong> · 864×480 · VRAM карты: 4539 МиБ</p>
<p>Надпись «МОСКВА», трамвай и отражения. Это иллюстративная локализация, не проверенный вид реальной улицы.</p>
<p><a href="prompts/urban-moscow.txt">Промпт</a> · <a href="results/batch-urban-moscow/record.json">Параметры и замеры</a></p>
</td>
</tr>
<tr>
<td width="50%" valign="top">
<p><strong>Фэнтези · Звёздный предел</strong></p>
<a href="results/batch-fantasy-location/image.png"><img src="results/batch-fantasy-location/image.png" width="420" alt="Фэнтези · Звёздный предел; seed 42"></a>
<p><strong>43,1 с</strong> · 864×480 · VRAM карты: 4539 МиБ</p>
<p>Длинная надпись читается; структура двух горных пиков и водопады переданы не полностью.</p>
<p><a href="prompts/fantasy-location.txt">Промпт</a> · <a href="results/batch-fantasy-location/record.json">Параметры и замеры</a></p>
</td>
<td width="50%" valign="top">
<p><strong>Стимпанк · Паровой порт</strong></p>
<a href="results/batch-steampunk-location/image.png"><img src="results/batch-steampunk-location/image.png" width="420" alt="Стимпанк · Паровой порт; seed 42"></a>
<p><strong>43,0 с</strong> · 864×480 · VRAM карты: 4819 МиБ</p>
<p>Надпись «ПАРОВОЙ ПОРТ», дирижабли и пар. Правдоподобность механизмов отдельно не подтверждена.</p>
<p><a href="prompts/steampunk-location.txt">Промпт</a> · <a href="results/batch-steampunk-location/record.json">Параметры и замеры</a></p>
</td>
</tr>
</table>

### Как меняется время с разрешением

Один и тот же портрет: одинаковые промпт, seed42, 16 шагов и CFG1. Это три одиночных измерения, не усреднение повторов.

| Размер | Время, с | VRAM карты по выборке, МиБ | Исходные данные |
|---|---:|---:|---|
| 512×512 | 30,9 | 4733 | [PNG](results/batch-people-portrait-512/image.png) · [Замеры](results/batch-people-portrait-512/record.json) |
| 768×768 | 59,2 | 5408 | [PNG](results/batch-people-portrait/image.png) · [Замеры](results/batch-people-portrait/record.json) |
| 1024×1024 | 130,1 | 5322 | [PNG](results/batch-people-portrait-1024/image.png) · [Замеры](results/batch-people-portrait-1024/record.json) |

На 1024² движок автоматически уменьшал плитки декодирования VAE; дополнительное время включено. Для всех первых 18 тематических сцен 14 результатов уложились в 60 с. В [полном отчёте](https://github.com/DevelopmentOpenworld/flux3-pascal-8gb/releases/download/v0.1.0-preview/FLUX3-Pascal-Report.html) есть другие сцены, размеры и параметры.

### Бои: улучшение хвата ещё не означает корректную сцену

Обе пары ниже имеют seed42 и размер 864×480. Уточнённые промпты упрощают композицию: у рыцарей убран щит, у роботов щит и посох заменены двумя мечами. Поэтому это сравнение условий, а не доказательство исправления исходного сложного действия.

<table>
<tr>
<td width="50%" valign="top">
<p><strong>Бой на крепостном мосту · исходный промпт</strong></p>
<a href="results/batch-fantasy-battle/image.png"><img src="results/batch-fantasy-battle/image.png" width="420" alt="Бой на крепостном мосту · исходный промпт; seed 42"></a>
<p><strong>42,7 с</strong> · 864×480 · VRAM карты: 4545 МиБ</p>
<p>Исходная сцена: у правого воина меч висит без видимого хвата. Итог: FAIL.</p>
<p><a href="prompts/fantasy-battle.txt">Промпт</a> · <a href="results/batch-fantasy-battle/record.json">Параметры и замеры</a></p>
</td>
<td width="50%" valign="top">
<p><strong>Бой на крепостном мосту · упрощённый промпт</strong></p>
<a href="results/battle-fantasy-clear-42/image.png"><img src="results/battle-fantasy-clear-42/image.png" width="420" alt="Бой на крепостном мосту · упрощённый промпт; seed 42"></a>
<p><strong>45,4 с</strong> · 864×480 · VRAM карты: 4761 МиБ</p>
<p>Уточнённая сцена: хват обоих мечей читается, но левый персонаж держит меч неверной анатомической рукой. Итог: FAIL.</p>
<p><a href="prompts/fantasy-battle-clear.txt">Промпт</a> · <a href="results/battle-fantasy-clear-42/record.json">Параметры и замеры</a></p>
</td>
</tr>
<tr>
<td width="50%" valign="top">
<p><strong>Схватка машин · исходный промпт</strong></p>
<a href="results/batch-hitech-battle/image.png"><img src="results/batch-hitech-battle/image.png" width="420" alt="Схватка машин · исходный промпт; seed 42"></a>
<p><strong>42,6 с</strong> · 864×480 · VRAM карты: 4698 МиБ</p>
<p>Исходная сцена: оружие и кисти пересекаются; конструкция и принадлежность оружия не читаются надёжно. Итог: FAIL.</p>
<p><a href="prompts/hitech-battle.txt">Промпт</a> · <a href="results/batch-hitech-battle/record.json">Параметры и замеры</a></p>
</td>
<td width="50%" valign="top">
<p><strong>Схватка машин · упрощённый промпт</strong></p>
<a href="results/battle-robot-clear-42/image.png"><img src="results/battle-robot-clear-42/image.png" width="420" alt="Схватка машин · упрощённый промпт; seed 42"></a>
<p><strong>47,5 с</strong> · 864×480 · VRAM карты: 4717 МиБ</p>
<p>Уточнённая сцена: связь кисть–рукоять–клинок читается, но слева неверная рука; фигуры обрезаны снизу. Итог: FAIL.</p>
<p><a href="prompts/robot-battle-clear.txt">Промпт</a> · <a href="results/battle-robot-clear-42/record.json">Параметры и замеры</a></p>
</td>
</tr>
</table>

Полного PASS нет ни у одного из восьми уточнённых боевых кадров. Визуальную оценку выполнил автор ИИ; независимой оценки не было. [Все бои, seed42/7/123 и критерии](docs/BATTLES.md) сохранены вместе с исходными промптами и PNG.

**[Полный HTML-отчёт: фильтры тем, парные сравнения, разрешения и все 39 запусков →](https://github.com/DevelopmentOpenworld/flux3-pascal-8gb/releases/download/v0.1.0-preview/FLUX3-Pascal-Report.html)**. Скачайте HTML и откройте локально; обычный просмотр исходника на GitHub не запускает интерактивную часть.

## Установка и запуск без консоли

[Скачайте Windows Manager](https://github.com/DevelopmentOpenworld/flux3-pascal-8gb/releases/download/v0.1.0-preview/FLUX3-Manager-Windows-x64.zip), распакуйте весь ZIP и откройте **FLUX3-Manager.exe**. Python уже включён. Выберите папку для файлов; укажите имеющиеся движок, веса и CUDA кнопками «Обзор…» либо нажмите «Скачать недостающее». Окно проверит закреплённые SHA256 и сохранит настройки.

**«Запустить сервер»**, **«Открыть генератор»** и **«Остановить сервер»** управляют приложением из окна. Закрытие Manager останавливает его сервер. В генераторе выберите пример или свой промпт, размер, seed, шаги, CFG и нажмите «Сгенерировать». Адрес по умолчанию `127.0.0.1:8440` и локальная сессия сохраняются между перезапусками. [Пошаговая инструкция](docs/INTERFACE.md).

Для разработчиков сохранён `Start-FLUX3.cmd` / `python scripts/app.py`; нативное окно из исходников – `python desktop/launcher.py`. Испытан Windows Python 3.14.4 x64 / Tcl-Tk 8.6; приложение использует стандартную библиотеку. [Сборка Windows EXE](docs/BUILD_WINDOWS.md) выполняется отдельно, без моделей и CUDA в пакете.

Отображается одна текущая операция. **Сохраните PNG до следующей генерации или выхода.** Предыдущий результат удаляется из временной рабочей папки при следующем запуске; при нормальном завершении приложения эта папка удаляется целиком. Сохранённые ранее пользовательские каталоги не читаются и не удаляются. Перезапуск сервера открывает пустой результат.

Случайная сессия, конфигурация и служебное состояние запуска хранятся только локально и исключены из Git и пакетов. Manager использует `%LOCALAPPDATA%/FLUX3Pascal`, исходный сервер – выбранный каталог конфигурации. В публичном проекте нет настроек конкретного компьютера. Кнопка «Завершить приложение» в браузере также закрывает сервер; закрытие вкладки оставляет текущую операцию работающей.

![Публичный интерфейс: только текущая генерация](ui-proof/result-screenshot.jpg)

## Испытанные компоненты и параметры

GTX 1070 Ti 8192 МиБ, compute capability 6.1, driver 581.80; Intel i7-7700, 8 логических потоков; 32695 МиБ RAM; Windows 10 22H2 build 19045.6466. CUDA Toolkit 12.6.85 уже установлен.

Движок: stable-diffusion.cpp `master-992-39bc9d0`, commit `39bc9d0b4bad86750fcb1fd2d711bc57a4c6018f`. Веса: `flux3-image-klein-Q4_0.gguf`, `Qwen3VL-4B-Instruct-Q4_K_M.gguf`, `flux2-vae.safetensors`. Точные хеши – [assets.lock.json](assets.lock.json).

Измеренный профиль: 16 шагов, CFG1, Euler/discrete, `--max-vram 6 --mmap --offload-to-cpu --flash-attn off,diffusion=on`. Код модели и движка не менялся. FP8/NVFP4 и Tensor Cores этому пути не требуются. Веса, CUDA и движок не входят в репозиторий или Windows-пакет; Python/Tk и их библиотеки входят в Windows-пакет со своими лицензиями.

## Контрольный корпус

Сохранены 39 фиксированных исследовательских запусков: 18 первых тематических сцен, 6 условий по разрешению, 1 проверка Toolkit-only, 12 дополнительных боёв и 2 контрольные генерации через интерфейс. Это заранее подготовленные воспроизводимые материалы, с промптами и SHA256.

14 из первых 18 тематических сцен уложились в минуту. Дополнительные бои 864×480 заняли 40,8–47,5 с. На 1024² время составило 130–141 с с автоматическим повтором VAE плитками. Максимум всей VRAM по выборке – 5728 МиБ, включая рабочий стол. Кэш файлов Windows не очищался.

У исходных боёв есть дефекты оружия. В шести упрощённых дуэлях хват стал понятнее, но слева использована неверная анатомическая рука. В двух воздушных боях читается главный луч, но нарушено крепление. Ни одному из восьми уточнённых кадров не присвоен полный PASS. Все первые результаты оставлены, без ретуши и отбора удачных seed.

В серии не использовался официальный prompt upsampler: подавались заранее подробные английские сцены. Оценка качества выполнена автором ИИ; независимая экспертиза не проводилась. Другие GPU/ОС, минимум RAM, холодный кэш, обучение, LoRA, редактирование и 4K не испытаны.

## Команды

```powershell
Copy-Item -LiteralPath config.example.json -Destination config.local.json
# Указать существующие файлы и CUDA bin.
python scripts/verify.py --config config.local.json
python scripts/generate.py --config config.local.json --case people-portrait-512 --run-id local-portrait-001
```

Проверки без модели:

```powershell
python scripts/verify.py
python -B -m unittest discover -s tests -v
```

Пересборка автономного отчёта из контрольных материалов:

```powershell
python scripts/build_report.py --seal
python scripts/verify.py
```

[MIT](LICENSE) относится к собственному коду и документации. Условия изображений зависят от используемой модели; MIT не перелицензирует результаты модели. Отдельные условия внешних компонентов – [THIRD_PARTY.md](THIRD_PARTY.md), первичные источники – [SOURCES.md](SOURCES.md).

[Первый публичный выпуск](https://github.com/DevelopmentOpenworld/flux3-pascal-8gb/releases/tag/v0.1.0-preview) · [Описание выпуска](RELEASE_NOTES.md) · [SHA256 пакетов](https://github.com/DevelopmentOpenworld/flux3-pascal-8gb/releases/download/v0.1.0-preview/SHA256SUMS.txt).

HTML нужно скачать и открыть локально; обычный просмотр исходника HTML на GitHub не запускает интерактивный отчёт.
