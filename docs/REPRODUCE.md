Для установки и управления сервером без консоли используйте [Windows Manager](INTERFACE.md). Ниже сохранены точные команды для разработчиков и параметры измерений.

# Воспроизведение: FLUX.3 Image Klein на Pascal 8 ГБ

Проверенный путь: Windows x64, GTX 1070 Ti / sm_61, 32 ГиБ RAM, уже установленный CUDA Toolkit 12.6.85 и готовая сборка stable-diffusion.cpp CUDA 12. Исходники движка и весов в этом опыте не изменялись. Установка нового CUDA Toolkit, PyTorch, ComfyUI, Diffusers или FlashAttention-пакета для этого пути не требуется.

## 1. Проверить существующую CUDA

В PowerShell:

```powershell
nvidia-smi --query-gpu=name,memory.total,driver_version,compute_cap --format=csv,noheader
$cudaBin = 'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin'
& "$cudaBin\nvcc.exe" --version
Get-Item -LiteralPath "$cudaBin\cudart64_12.dll", "$cudaBin\cublas64_12.dll", "$cudaBin\cublasLt64_12.dll"
```

Измеренный ответ: GTX 1070 Ti, 8192 МиБ, driver 581.80, compute capability 6.1; `nvcc` – release 12.6, V12.6.85. Строка CUDA 13.0 в обычном заголовке `nvidia-smi` не означает, что используется Toolkit 13.

Путь `$cudaBin` можно заменить фактическим путём уже установленной CUDA 12.6. Не обновлять её ради этого проекта. CUDA 13 не подходит для новой сборки под Pascal: [разъяснение NVIDIA](https://developer.nvidia.com/blog/navigating-gpu-architecture-support-a-guide-for-nvidia-cuda-developers/). Готовая исполняемая сборка также должна содержать код для sm_61; произвольная современная CUDA-сборка не считается заменой проверенной.

Для первой серии использовались CUDA 12.6-совместимые библиотеки с теми же SHA256, что у установленного Toolkit. Опыт toolkit-only-portrait-512, вся дополнительная серия боёв и проверка интерфейса используют Toolkit bin без дополнительного каталога DLL. Загрузка трёх CUDA DLL из Toolkit подтверждена в toolkit-loaded-modules.json; хеши – в toolkit-dlls.json. Повторная установка CUDA не выполнялась.

## 2. Получить точные файлы или переиспользовать существующие

Движок: [релиз master-992-39bc9d0](https://github.com/leejet/stable-diffusion.cpp/releases/tag/master-992-39bc9d0), commit `39bc9d0b4bad86750fcb1fd2d711bc57a4c6018f`.

| Файл | Размер, байт | SHA256 |
|---|---:|---|
| sd-master-39bc9d0-bin-win-cuda12-x64.zip | 343795758 | b036d2174685050b2829ee660989a6548b300948930894f8a95a24b75380459a |
| flux3-image-klein-Q4_0.gguf | 3514023104 | 22d0b1fa05f5ef63fa68eebe801a680e0456cb786af28be5952e10fb5c9004b2 |
| Qwen3VL-4B-Instruct-Q4_K_M.gguf | 2497281664 | 66358cb18bb6b3b1b6675aa412c7a88ef01d228f481184d13668e5201c730a0a |
| flux2-vae.safetensors | 336213556 | d64f3a68e1cc4f9f4e29b6e0da38a0204fe9a49f2d4053f0ec1fa1ca02f9c4b5 |

Точные адреса и ревизии:

- DiT: [leejet/flux-3-image-klein-GGUF](https://huggingface.co/leejet/flux-3-image-klein-GGUF/tree/1c2ad2f9b9247ccca6506a23bdb033fdb0873321), revision `1c2ad2f9b9247ccca6506a23bdb033fdb0873321`.
- Кодировщик: [Qwen/Qwen3-VL-4B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF/tree/1cd86afb9a95c410a6038ab3b40d8b578c892266), revision `1cd86afb9a95c410a6038ab3b40d8b578c892266`.
- VAE: [Comfy-Org/Flux-2-Dev](https://huggingface.co/Comfy-Org/Flux-2-Dev/blob/ca4ac7c84eb42f3200fffc85b5fbee67129e6ffa/split_files/vae/flux2-vae.safetensors), revision `ca4ac7c84eb42f3200fffc85b5fbee67129e6ffa`.

Нужен именно Qwen3-VL 4B. Старый Qwen3-4B без VL, применявшийся с FLUX.2, не является проверенной заменой. Отдельный файл mmproj для этого текстового пути не использовался.

При размещении внутри проекта структура такая:

```text
runtime/
  sd-cli.exe
  stable-diffusion.dll
  ggml-cuda.dll
  ...остальные DLL из того же архива...
models/
  flux3-image-klein-Q4_0.gguf
  Qwen3VL-4B-Instruct-Q4_K_M.gguf
  flux2-vae.safetensors
prompts/
  people-portrait.txt
```

Архив распаковывается целиком. Не переносить один sd-cli.exe без соседних DLL. При наличии файлов в другом месте достаточно указать их пути в конфигурации; повторная загрузка и копирование не нужны.

Для загрузки с нуля предусмотрен скрипт только на стандартной библиотеке Python:

```powershell
python scripts/download_assets.py --list
# После ознакомления со ссылками и условиями upstream:
python scripts/download_assets.py
```

Скрипт закрепляет ревизии и проверяет SHA, существующие совпавшие файлы переиспользует, иной существующий файл не перезаписывает. Загрузка заново в дополнительной серии не выполнялась: использованы уже проверенные файлы. Саму сетевую загрузку этим новым скриптом на чистом ПК не испытывали.

## 3. Выполнить одну генерацию напрямую

Из каталога проекта; свободной карте нужны также запас RAM и закрытые конкурирующие модельные процессы:

```powershell
$cudaBin = 'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin'
$env:PATH = "$cudaBin;$env:PATH"
$env:OMP_NUM_THREADS = '8'
New-Item -ItemType Directory -Path outputs -ErrorAction Stop
& .\runtime\sd-cli.exe `
  --diffusion-model .\models\flux3-image-klein-Q4_0.gguf `
  --llm .\models\Qwen3VL-4B-Instruct-Q4_K_M.gguf `
  --vae .\models\flux2-vae.safetensors `
  --prompt-file .\prompts\people-portrait.txt `
  --steps 16 --cfg-scale 1.0 `
  --sampling-method euler --scheduler discrete `
  -W 512 -H 512 -s 42 `
  --flash-attn off,diffusion=on `
  --max-vram 6 --mmap --offload-to-cpu `
  -o .\outputs\portrait-512.png -v
if ($LASTEXITCODE -ne 0) { throw 'sd-cli завершился с ошибкой: проверьте журнал' }
```

Каталог outputs в этом примере новый. Для повторного опыта выбрать новое имя результата. Точный переносимый список аргументов каждого опубликованного опыта находится в `results/<run-id>/record.json`.

Значение ключевых параметров:

- `--steps 16 --cfg-scale 1.0` – профиль дистиллированной FLUX.3 Image Klein; это не профиль Base.
- `--offload-to-cpu` – исходные параметры хранятся в RAM, нужные вычислительные копии загружаются на GPU. Это не перевод всей генерации на CPU.
- `--max-vram 6` – управляемый бюджет 6 ГиБ. Фон, контекст драйвера и внешние выделения этим числом не ограничиваются.
- `--mmap` – отображение файлов весов в память; скорость чтения зависит от диска и кэша Windows.
- `--flash-attn off,diffusion=on` – Flash Attention движка включён для DiT и выключен для остальных модулей. Это собственные ядра GGML, а не отдельный Python-пакет flash-attn.
- Q4_0 – опубликованное квантование весов. FP8/NVFP4 и Tensor Cores для проверенного пути не требуются.

## 4. Запуск с протоколом замера

```powershell
Copy-Item -LiteralPath config.example.json -Destination config.local.json
# Отредактировать только пути к уже существующим файлам и cuda_bin.
# cuda_runtime_dir оставить пустым, если используются DLL из Toolkit bin.
python scripts/verify.py --config config.local.json
python scripts/generate.py --config config.local.json --case people-portrait-512 --run-id local-portrait-001
```

Обёртка измеряет новый процесс sd-cli, пишет PNG, очищенный от личных путей журнал, параметры, контрольные суммы и датчики. Она не импортирует torch. Прерывание по доступной RAM ниже 3072 МиБ, commit от 93% или общей VRAM выше 7680 МиБ в течение пяти секунд записывается как `MEMORY_GUARD`; это не утверждение о доказанном OOM модели. Тайм-аут одного процесса – 900 секунд. Завершается только собственный sd-cli.

Обёртка самостоятельно сохраняет датчики Windows и nvidia-smi в sensors.jsonl. Для воспроизведения нужен последовательный запуск на свободной карте. Других служебных программ переносимый проект не требует.

Для трёх сравнений разрешения используйте условия:

```text
people-portrait-512    people-portrait    people-portrait-1024
fantasy-weapon-512     fantasy-weapon     fantasy-weapon-1024
hitech-location-512    hitech-location    hitech-location-1024
```

Среднее условие – 768×768. Промпт и seed у каждой тройки совпадают. Изменение размеров меняет траекторию генерации, поэтому те же seed и описание не гарантируют пиксельно совпадающую композицию между разрешениями.

На проверенных 1024×1024 этот же список аргументов привёл к автоматическому повтору декодирования VAE плитками: из 1024×1024 в 512×512, сетка 3×3 с перекрытием. В engine.log сохранены предупреждение о нехватке места в бюджете и последующий успешный повтор. Профиль 1024² включает это поведение и его задержку; явно заданного `--vae-tiling` в команде не было.

## 5. Проверить результат и границы воспроизводимости

```powershell
python scripts/verify.py
```

Проверка сохранённого набора не запускает моделей и не требует CUDA. Для внешних весов добавляется `--config config.local.json`; это полное чтение файлов SHA256 и может прогреть кэш.

Сопоставляйте результат по файлам, настройкам и уровню качества. Побайтное совпадение изображения между разными версиями GPU-драйвера, CUDA, движка или картами не обещается. Сравнение двух одинаковых условий в этом стенде показано отдельно в результатах. Замеры относятся к прогретому или неконтролируемому файловому кэшу; задержка после простоя может быть выше.

32 ГиБ RAM – фактически испытанный объём, а не измеренный минимум. Другие Pascal-карты, Linux, иные квантовки, LoRA, Base, пакетная генерация и правка изображений в этой тематической серии не проверялись.


## 6. Генерация через окно

Основной графический путь – [Windows Manager](INTERFACE.md): выбор имеющихся файлов или скачивание, затем кнопка запуска сервера. Разработчик может использовать `Start-FLUX3.cmd` или `python scripts/app.py`. Нативные кнопки полного пути установки пока не подтверждены; сервер и worker проверены программно.

Дополнительные бои воспроизводятся так:

```powershell
python scripts/generate.py --config config.local.json --cases-file battle-cases.json --case fantasy-clear-7 --run-id local-battle-001
```

Все первые результаты серии сохранены; ограничения хвата, правой/левой руки и механики приведены в [BATTLES.md](BATTLES.md).

В Manager и генераторе доступны **Русский / English** с сохранением выбора. Порядок обновления Windows-пакета и переключения языка – в [инструкции интерфейса](INTERFACE.md#язык-интерфейса-и-обновление). Язык интерфейса не меняет точные промпты, команды и параметры контрольных генераций.
