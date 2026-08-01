"""Сборка документов из профиля проекта.

Резидент рассказал о проекте один раз — здесь этот рассказ раскладывается по
разным формам: разделы заявки, тизер инвестору, одна страница, презентация.

ГЛАВНОЕ ПРАВИЛО: модель не придумывает факты. Если в профиле нет данных для
раздела, в тексте остаётся прямая пометка «нужно дополнить», а не
правдоподобный вымысел. Выдуманная цифра рынка или несуществующая публикация
в заявке — это не неудобство, а основание для отклонения и удар по репутации
резидента. Поэтому:

  · в модель уходят только заполненные поля профиля (as_prompt);
  · в инструкции прямо запрещено домысливать;
  · перед генерацией сервер сам проверяет, каких полей не хватает, и
    сообщает об этом резиденту — до обращения к модели, а не после.

Разделы намеренно универсальные, а не под конкретную программу. Настоящая
заявка ФСИ или Сколково требует ручного разбора требований и ежегодного
сопровождения — это отдельная работа. Здесь то, что просят почти везде.
"""
import json
import logging

from django.conf import settings

from .assist import _parse_model_json, model_uri
from .models import PROFILE_LABELS

log = logging.getLogger(__name__)

MAX_OUT = 6000


# Форматы: какие поля профиля нужны и что должно получиться.
FORMATS = {
    'sections': {
        'title': 'Черновики разделов заявки',
        'needs': ['title', 'summary', 'problem', 'solution', 'stage', 'groundwork', 'team'],
        'wants': ['market', 'competitors', 'business_model', 'workplan', 'risks'],
        'about': (
            'Собери черновики универсальных разделов заявки на грант. Разделы: '
            'Аннотация проекта; Актуальность и постановка проблемы; '
            'Научно-техническая новизна; Имеющийся задел; Команда; '
            'План работ; Ожидаемые результаты; Коммерциализация. '
            'Каждый раздел — 3–6 предложений деловым языком.'),
    },
    'teaser': {
        'title': 'Тизер для инвестора',
        'needs': ['title', 'summary', 'problem', 'solution', 'stage'],
        'wants': ['market', 'team'],
        'about': (
            'Собери короткий тизер для первого письма инвестору или скауту: '
            '5–7 предложений. Без воды и превосходных степеней, по делу: '
            'что за проект, какую задачу решает, на какой стадии, что нужно.'),
    },
    'onepager': {
        'title': 'Одна страница о проекте',
        'needs': ['title', 'summary', 'problem', 'solution', 'stage', 'team'],
        'wants': ['market', 'competitors', 'business_model'],
        'about': (
            'Собери одностраничное описание проекта с подзаголовками: '
            'Проблема; Решение; Стадия; Команда; Что нужно. '
            'Объём — примерно на одну страницу.'),
    },
    'deck': {
        'title': 'План презентации',
        'needs': ['title', 'summary', 'problem', 'solution', 'stage', 'team'],
        'wants': ['market', 'competitors', 'business_model', 'workplan'],
        'about': (
            'Составь план презентации на 8–10 слайдов. Для каждого слайда: '
            'заголовок и 2–4 тезиса. Слайды по канве: титул, проблема, '
            'решение, как работает, стадия и задел, рынок, конкуренты, '
            'команда, план, запрос.'),
    },
}

SYSTEM_PROMPT = (
    'Ты — помощник резидента ИНТЦ МГУ «Воробьёвы горы» на платформе ПУЛЬСАР. '
    'Ты помогаешь оформить документы по проекту: разделы заявок на гранты, '
    'тизеры, описания для инвесторов.\n'
    '\n'
    'КТО ТЫ. Если спросят: ты помощник платформы ПУЛЬСАР, работаешь на '
    'языковой модели. Не выдавай себя за человека, эксперта или сотрудника '
    'МГУ. Твои черновики — заготовка для правки, а не готовый документ.\n'
    '\n'
    'ГЛАВНОЕ ПРАВИЛО — НИЧЕГО НЕ ПРИДУМЫВАТЬ.\n'
    'Ты пишешь только на основании профиля проекта, который тебе дали.\n'
    '1. Запрещено сочинять цифры: объёмы рынка, доли, сроки окупаемости, '
    'суммы, проценты. Если цифры нет в профиле — её нет.\n'
    '2. Запрещено сочинять публикации, патенты, награды, партнёров, '
    'заказчиков и результаты испытаний.\n'
    '3. Запрещено повышать заявленную стадию готовности проекта.\n'
    '4. Если для раздела не хватает данных — НЕ ДОГАДЫВАЙСЯ. Вместо текста '
    'напиши в квадратных скобках, что нужно дополнить, например: '
    '[Нужно дополнить: объём целевого рынка и источник оценки].\n'
    'Выдуманный факт в заявке — это отказ заявителю и удар по его репутации. '
    'Пустое место честнее.\n'
    '\n'
    'КАК ПИСАТЬ. По-русски, деловым языком, без рекламных превосходных '
    'степеней («уникальный», «не имеющий аналогов», «прорывной»). Короткими '
    'предложениями. Не пересказывай профиль дословно — формулируй под задачу.\n'
    '\n'
    'ФОРМАТ ОТВЕТА. Строго JSON, без markdown вокруг:\n'
    '{"blocks":[{"heading":"Заголовок раздела","text":"текст раздела"}],'
    '"gaps":["чего не хватило в профиле"]}\n'
    'Поле gaps — список того, что стоит дополнить в профиле; может быть пустым.'
)


def missing_for(profile, fmt):
    """Каких обязательных полей не хватает для формата."""
    spec = FORMATS[fmt]
    return profile.missing(spec['needs'])


def _ask_model(profile, fmt):
    key = getattr(settings, 'YANDEX_API_KEY', '')
    folder = getattr(settings, 'YANDEX_FOLDER_ID', '')
    if not key or not folder:
        return None

    import urllib.error
    import urllib.request

    spec = FORMATS[fmt]
    body = {
        'model': model_uri(),
        'temperature': 0.3,     # чуть свободнее, чем подбор: это текст
        'max_tokens': 2000,
        'messages': [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user',
             'content': f'ПРОФИЛЬ ПРОЕКТА:\n{profile.as_prompt()}\n\n'
                        f'ЗАДАНИЕ: {spec["about"]}'},
        ],
    }
    req = urllib.request.Request(
        settings.YANDEX_LLM_URL,
        data=json.dumps(body).encode('utf-8'),
        headers={'Content-Type': 'application/json',
                 'Authorization': f'Api-Key {key}',
                 'OpenAI-Project': folder},
        method='POST')
    try:
        with urllib.request.urlopen(req, timeout=settings.COMPOSE_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
        return payload['choices'][0]['message']['content']
    except (urllib.error.URLError, OSError, KeyError, IndexError, ValueError) as e:
        log.warning('Сборка документа: модель недоступна: %s', e)
        return None


def _parse(text):
    """Разбор ответа модели в (блоки, пробелы)."""
    if not text:
        return [], []
    import re
    m = re.search(r'\{.*\}', text, re.S)
    if not m:
        return [], []
    try:
        data = json.loads(m.group(0))
    except (ValueError, TypeError):
        return [], []
    if not isinstance(data, dict):
        return [], []
    blocks = []
    for b in (data.get('blocks') or []):
        if not isinstance(b, dict):
            continue
        head = str(b.get('heading') or '').strip()[:200]
        body = str(b.get('text') or '').strip()[:MAX_OUT]
        if head or body:
            blocks.append({'heading': head, 'text': body})
    gaps = [str(g).strip()[:200] for g in (data.get('gaps') or []) if str(g).strip()]
    return blocks, gaps


def compose(profile, fmt):
    """Собрать документ. Возвращает (блоки, пробелы, режим).

    Режимы:
      · ok        — собрано моделью;
      · need      — не хватает обязательных полей, к модели не обращались;
      · offline   — модель не настроена или не ответила.
    """
    if fmt not in FORMATS:
        return [], [], 'unknown'

    # Проверяем до обращения к модели: просить её писать раздел без данных —
    # значит толкать на выдумку, а платить за это будем мы.
    lack = missing_for(profile, fmt)
    if lack:
        return [], [PROFILE_LABELS[k] for k in lack], 'need'

    raw = _ask_model(profile, fmt)
    if raw is None:
        return [], [], 'offline'
    blocks, gaps = _parse(raw)
    if not blocks:
        log.info('Сборка документа: модель вернула пустой или неразборный ответ')
        return [], [], 'offline'
    return blocks, gaps, 'ok'
