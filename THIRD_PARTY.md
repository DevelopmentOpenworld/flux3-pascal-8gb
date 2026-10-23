# Внешние компоненты

Репозиторий и исходный пакет содержат собственные скрипты, документацию и результаты генерации. Модельные веса, stable-diffusion.cpp и CUDA в них не входят. Отдельный Windows-пакет включает Python/Tk и их runtime DLL с лицензиями в папке licenses; веса, CUDA и sd.cpp в него не включены. Загрузка выполняется пользователем из закреплённых источников в assets.lock.json; существующие файлы можно переиспользовать.

- [stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp) – отдельный движок; MIT-лицензия движка опубликована [в закреплённом исходном дереве](https://github.com/leejet/stable-diffusion.cpp/blob/39bc9d0b4bad86750fcb1fd2d711bc57a4c6018f/LICENSE). Наличие текста лицензии в бинарном ZIP не предполагается.
- [FLUX.3 Image Klein](https://huggingface.co/black-forest-labs/flux-3-image-klein) и [квантованные веса](https://huggingface.co/leejet/flux-3-image-klein-GGUF) – применяются условия соответствующих upstream-поставок. Лицензия исходного кода BFL не заменяет условия весов.
- [Qwen3-VL 4B GGUF](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF) – отдельный текстовый кодировщик.
- [FLUX.2 VAE](https://huggingface.co/Comfy-Org/Flux-2-Dev/blob/ca4ac7c84eb42f3200fffc85b5fbee67129e6ffa/split_files/vae/flux2-vae.safetensors) – отдельный файл декодировщика, совпадающий по SHA256 с использованным в опыте.
- [NVIDIA CUDA](https://developer.nvidia.com/cuda-toolkit) – существующая среда переиспользуется. Manager может скачать CUDA Runtime 12.6.77 и cuBLAS 12.6.4.1 из [официального манифеста CUDA 12.6.3](https://developer.download.nvidia.com/compute/cuda/redist/redistrib_12.6.3.json), проверить SHA256 и распаковать DLL с лицензиями в выбранную локальную папку. Драйвер, системный Toolkit и PATH не меняются. Веса и эти библиотеки в исходный пакет/Windows EXE не включены.
- [Python](https://www.python.org/) / Tcl-Tk входят в отдельный Windows-пакет со своими лицензиями. Для сборки используется [PyInstaller 6.22.3](https://pyinstaller.org/en/stable/usage.html); он не требуется пользователю готового EXE. Лицензии сборщика с исключением для упакованных приложений и собственных компонентов сохраняют своё действие.

MIT-лицензия этого проекта относится к его собственным исходникам и документации. Она не перелицензирует перечисленные внешние компоненты или изображения, сгенерированные моделью. Условия использования весов и результатов сверяются по upstream-материалам пользователем; здесь не предоставляется отдельная юридическая оценка.

Windows runtime также содержит OpenSSL 3.0.19 и zlib 1.3.1; тексты лицензий и notices добавлены отдельно. Точная опись файлов с SHA256 – в манифесте Windows ZIP. Список и ссылки – [RUNTIME_NOTICES.md](desktop/licenses/RUNTIME_NOTICES.md).
