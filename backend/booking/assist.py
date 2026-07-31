"""
Подбор позиций каталога по задаче, описанной своими словами.

Работает в двух режимах:

  · «ai»    — задача уходит в YandexGPT вместе с полным каталогом. Весь
              каталог (35 позиций, ~3 000 токенов) помещается в один запрос,
              поэтому ни векторной базы, ни эмбеддингов не нужно.
  · «local» — если модель не настроена, не ответила или ответила мусором,
              подбор делается на месте по совпадению слов с учётом синонимов.
              Пользователь всегда получает результат, даже когда внешний
              сервис недоступен.

ГЛАВНОЕ ПРАВИЛО: что бы ни вернула модель, наружу уходят только те позиции,
которые реально есть в каталоге. Идентификаторы сверяются с базой, всё
остальное отбрасывается — иначе система однажды предложит клиенту прибор,
которого у нас нет.
"""
import json
import logging
import re

from django.conf import settings

log = logging.getLogger(__name__)

MAX_QUERY_LEN = 500      # длиннее — обрезаем: защита от раздувания запроса
MAX_RESULTS = 4          # больше четырёх вариантов человек уже не читает

# Синонимы для локального подбора. Умышленно короче фронтового словаря
# (data/synonyms.js): здесь нужны только группы, которые часто пишут
# по-английски или аббревиатурой.
SYNONYMS = [
    ['ямр', 'nmr', 'ядерный магнитный резонанс'],
    ['масс-спектрометр', 'масс-спектрометрия', 'ms', 'qtof', 'хромато-масс'],
    ['вэжх', 'hplc', 'жидкостная хроматография', 'хроматография'],
    ['сэм', 'sem', 'сканирующий электронный микроскоп', 'рэм'],
    ['пэм', 'tem', 'просвечивающий электронный микроскоп'],
    ['микроскопия', 'микроскоп', 'электронная микроскопия'],
    ['пцр', 'pcr', 'амплификатор', 'полимеразная цепная реакция'],
    ['цитометр', 'цитометрия', 'facs'],
    ['рентген', 'xrd', 'дифрактометр', 'фазовый анализ'],
    ['icp', 'исп', 'элементный анализ'],
    ['раман', 'raman', 'комбинационное рассеяние'],
    ['чистая комната', 'клинрум', 'cleanroom', 'gmp', 'асептика'],
    ['лиофилизация', 'лиофильная сушка', 'сублимационная сушка', 'сушка', 'высушить', 'сушить'],
    ['3d-печать', 'аддитивные технологии', 'fdm', 'прототип'],
    ['вакуум', 'термовакуум', 'вакуумная камера'],
    ['геномика', 'секвенирование', 'биоинформатика', 'генетика'],
    ['размер частиц', 'дзета-потенциал', 'dls', 'zetasizer'],
    ['теплопроводность', 'итс'],
    ['прочность', 'растяжение', 'механические испытания'],
    ['климатическая камера', 'тепло-холод', 'влажность'],
]


# Русские окончания: без их отсечения «микроскопом» не находит «микроскоп»,
# а «примеси» — «примесь». Грубо, но для поиска по каталогу достаточно.
_ENDINGS = ('иями', 'ами', 'ями', 'ого', 'ему', 'ому', 'ыми', 'ими', 'ей', 'ой',
            'ый', 'ий', 'ая', 'яя', 'ое', 'ее', 'ые', 'ие', 'ом', 'ем', 'ах',
            'ях', 'ов', 'ев', 'ью', 'и', 'ы', 'у', 'ю', 'а', 'я', 'е', 'о', 'ь')


def _stem(word):
    """Отбрасываем окончание, если основа остаётся достаточно длинной."""
    for end in _ENDINGS:
        if word.endswith(end) and len(word) - len(end) >= 4:
            return word[:-len(end)]
    return word


def _expand(word):
    """Слово вместе со всеми его синонимами (сравнение по основам)."""
    out = {word}
    stem = _stem(word)
    for group in SYNONYMS:
        if any(_stem(g).startswith(stem) or stem.startswith(_stem(g)) for g in group):
            out.update(group)
    return out


def _resource_text(r):
    specs = ' '.join(r.specs or []) if isinstance(r.specs, list) else ''
    return f'{r.title} {r.lab} {specs} {r.description} {r.clean_class}'.lower()


def rank_local(query, resources):
    """Подбор без модели: считаем, сколько слов запроса нашлось в позиции."""
    words = [w for w in re.split(r'[\s,;.]+', query.lower()) if len(w) > 2]
    scored = []
    for r in resources:
        text = _resource_text(r)
        title = r.title.lower()
        hits, bonus = 0, 0
        for w in words:
            # ищем по основам: и слово запроса, и его синонимы
            variants = {_stem(v) for v in _expand(w)}
            if any(v in text for v in variants):
                hits += 1
                # совпадение в названии весомее, чем в длинном описании
                if any(v in title for v in variants):
                    bonus += 1
        if hits:
            scored.append((hits * 10 + bonus, r))
    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored[:MAX_RESULTS]]


def _catalog_for_prompt(resources):
    """Компактное представление каталога для модели: только то, что нужно
    для выбора. Цены и картинки не передаём — они не влияют на подбор."""
    lines = []
    for r in resources:
        specs = '; '.join((r.specs or [])[:4]) if isinstance(r.specs, list) else ''
        lines.append(
            f'{r.slug} | {r.get_type_display()} | {r.title} | {r.lab} | '
            f'{r.clean_class} | {specs} | {r.description[:220]}')
    return '\n'.join(lines)


SYSTEM_PROMPT = (
    'Ты консультант платформы ПУЛЬСАР — она даёт доступ к научной инфраструктуре '
    'МГУ и ИНТЦ «Воробьёвы горы». Клиент описывает свою задачу. Подбери из каталога '
    'от одной до четырёх позиций, которые решают именно её.\n'
    'Правила:\n'
    '1. Выбирай ТОЛЬКО из идентификаторов, приведённых в каталоге. Ничего не придумывай.\n'
    '2. Если подходящего нет — верни пустой список.\n'
    '3. Объясняй коротко, одним предложением, по-русски, без общих слов.\n'
    '4. Отвечай строго в формате JSON, без markdown и пояснений вокруг:\n'
    '{"items":[{"id":"идентификатор","why":"почему подходит"}]}'
)


def _parse_model_json(text):
    """Достаём JSON из ответа модели. Модели любят обернуть его в ```json,
    поэтому берём первый блок от { до последней }."""
    if not text:
        return []
    m = re.search(r'\{.*\}', text, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except (ValueError, TypeError):
        return []
    items = data.get('items') if isinstance(data, dict) else None
    return items if isinstance(items, list) else []


def model_uri():
    """Адрес модели для API.

    YANDEX_MODEL можно задавать двумя способами, оба рабочие:
      · слаг            — yandexgpt-lite/latest (папка подставится сама);
      · полный адрес    — gpt://<folder>/yandexgpt-lite/latest.
    В документации Яндекса и в карточках моделей встречаются оба варианта,
    поэтому не заставляем помнить, какой именно нужен.
    """
    model = (getattr(settings, 'YANDEX_MODEL', '') or '').strip()
    if model.startswith('gpt://') or model.startswith('ds://'):
        return model
    return f'gpt://{getattr(settings, "YANDEX_FOLDER_ID", "")}/{model}'


def ask_yandex(query, resources):
    """Запрос к YandexGPT. Возвращает список {id, why} либо None при любой
    неудаче — вызывающий код в этом случае откатывается на локальный подбор."""
    key = getattr(settings, 'YANDEX_API_KEY', '')
    folder = getattr(settings, 'YANDEX_FOLDER_ID', '')
    if not key or not folder:
        return None

    import urllib.error
    import urllib.request

    body = {
        'modelUri': model_uri(),
        'completionOptions': {
            'stream': False,
            'temperature': 0.1,      # подбор, а не сочинение: нужна стабильность
            'maxTokens': 800,
        },
        'messages': [
            {'role': 'system', 'text': SYSTEM_PROMPT},
            {'role': 'user',
             'text': f'КАТАЛОГ (идентификатор | тип | название | подразделение | '
                     f'класс | характеристики | описание):\n{_catalog_for_prompt(resources)}\n\n'
                     f'ЗАДАЧА КЛИЕНТА: {query}'},
        ],
    }
    req = urllib.request.Request(
        settings.YANDEX_LLM_URL,
        data=json.dumps(body).encode('utf-8'),
        headers={'Content-Type': 'application/json',
                 'Authorization': f'Api-Key {key}'},
        method='POST')
    try:
        with urllib.request.urlopen(req, timeout=settings.ASSIST_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
        text = payload['result']['alternatives'][0]['message']['text']
    except (urllib.error.URLError, OSError, KeyError, IndexError, ValueError) as e:
        log.warning('YandexGPT недоступен, работаем на локальном подборе: %s', e)
        return None
    return _parse_model_json(text)


def assist(query, resources):
    """Точка входа. Возвращает (список позиций с обоснованием, режим)."""
    query = (query or '').strip()[:MAX_QUERY_LEN]
    if not query:
        return [], 'empty'

    by_id = {r.slug: r for r in resources}
    raw = ask_yandex(query, resources)

    if raw is not None:
        picked, seen = [], set()
        for item in raw:
            if not isinstance(item, dict):
                continue
            rid = str(item.get('id') or '').strip()
            # ключевая проверка: идентификатора нет в каталоге — позиция выдумана
            if rid not in by_id or rid in seen:
                continue
            seen.add(rid)
            picked.append((by_id[rid], str(item.get('why') or '').strip()[:300]))
            if len(picked) >= MAX_RESULTS:
                break
        if picked:
            return picked, 'ai'
        log.info('Модель не дала ни одной существующей позиции, откат на локальный подбор')

    return [(r, '') for r in rank_local(query, resources)], 'local'
