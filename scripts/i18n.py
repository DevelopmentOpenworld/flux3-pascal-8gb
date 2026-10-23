"""Shared RU/EN messages. Only explicit messages are translated, never user data."""
import json
from pathlib import Path
import sys

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
MESSAGES = json.loads((ROOT / 'ui/messages.json').read_text(encoding='utf-8'))
LANGUAGES = ('ru', 'en')


def language(value):
    return value if value in LANGUAGES else 'ru'


class Message(str):
    def __new__(cls, translations):
        obj = super().__new__(cls, translations['ru'])
        obj.translations = translations
        return obj


def render(value, lang='ru'):
    lang = language(lang)
    if isinstance(value, Message):
        return value.translations[lang]
    if isinstance(value, dict):
        return {k: render(v, lang) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [render(v, lang) for v in value]
    return value


def msg(key, **values):
    return Message({lang: MESSAGES[lang][key].format(**render(values, lang)) for lang in LANGUAGES})


def joined(values, separator='\n'):
    return Message({lang: separator.join(str(render(v, lang)) for v in values) for lang in LANGUAGES})


def error_message(error):
    if error.args and isinstance(error.args[0], Message):
        return error.args[0]
    return msg('operation_detail', detail=str(error))


def with_translations(value):
    """Keep the old Russian API fields and add translations for live UI switching."""
    if isinstance(value, dict):
        result = {k: with_translations(v) for k, v in value.items()}
        for key, item in value.items():
            if isinstance(item, Message):
                result[key + '_i18n'] = item.translations
        if 'errors' in value:
            result['errors_i18n'] = {lang: render(value['errors'], lang) for lang in LANGUAGES}
        return result
    if isinstance(value, (list, tuple)):
        return [with_translations(v) for v in value]
    return value
