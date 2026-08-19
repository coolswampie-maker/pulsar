"""
Каталог исследований и испытаний для серверной части.

Источник один — `data/rnd.js`. Второй копии данных на сервере нет
намеренно: она разошлась бы с первой в первый же день правки, и модель
начала бы предлагать работы, которых на сайте уже нет.

Файл читается один раз при первом обращении. Если его нет или разбор не
удался, каталог пуст — подбор по работам просто не сработает и честно
скажет об этом, а остальной сайт продолжит жить.

В рабочей версии работы заводит оператор в CRM. Тогда этот модуль
заменяется выборкой из базы, а всё остальное — промпт, сверка
идентификаторов, ответ — останется как есть.
"""
import json
import logging
import re
import threading
from pathlib import Path

from django.conf import settings

log = logging.getLogger(__name__)

RND_JS = Path(settings.BASE_DIR).parent / 'data' / 'rnd.js'

_KEY = re.compile(r'([A-Za-z_$][\w$]*)\s*:')
_TRAIL = re.compile(r',\s*([}\]])')


def _scan(src, i, out=None):
    """Один шаг разбора: комментарии выбрасываем, строки переносим как JSON,
    голые ключи закавычиваем. Возвращает следующий индекс.

    Строки обрабатываются раньше всего остального: иначе `//` внутри
    названия («ASTM D2344/D2344M») будет принят за комментарий, а двоеточие
    в тексте — за ключ."""
    c = src[i]
    if c == '/' and src.startswith('/*', i):
        j = src.find('*/', i + 2)
        return len(src) if j < 0 else j + 2
    if c == '/' and src.startswith('//', i):
        j = src.find('\n', i)
        return len(src) if j < 0 else j
    if c in '"\'':
        j, buf = i + 1, []
        while j < len(src) and src[j] != c:
            if src[j] == '\\' and j + 1 < len(src):
                buf.append(src[j + 1]); j += 2; continue
            buf.append(src[j]); j += 1
        if out is not None:
            out.append(json.dumps(''.join(buf), ensure_ascii=False))
        return j + 1
    m = _KEY.match(src, i)
    if m:
        if out is not None:
            out.append('"%s":' % m.group(1))
        return m.end()
    if out is not None:
        out.append(c)
    return i + 1


def _array_after(src, name):
    """Текст массива `var <name> = [ ... ];` вместе со скобками."""
    m = re.search(r'\b(?:var|let|const)\s+%s\s*=\s*\[' % re.escape(name), src)
    if not m:
        raise ValueError('массив %s не найден' % name)
    start = m.end() - 1
    depth, i = 0, start
    while i < len(src):
        c = src[i]
        if c in '"\'' or src.startswith('/*', i) or src.startswith('//', i):
            i = _scan(src, i)
            continue
        if c in '[{':
            depth += 1
        elif c in ']}':
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1
    raise ValueError('массив %s не закрыт' % name)


def _to_json(js):
    out, i = [], 0
    while i < len(js):
        i = _scan(js, i, out)
    return _TRAIL.sub(r'\1', ''.join(out))


def _read():
    src = RND_JS.read_text(encoding='utf-8')
    works = json.loads(_to_json(_array_after(src, 'RND_WORKS')))
    if not isinstance(works, list):
        raise ValueError('RND_WORKS — не список')
    # Название — единственный идентификатор работы на сегодня, по нему же
    # фронт находит строку в каталоге. Без названия строка бесполезна.
    return [w for w in works if isinstance(w, dict) and w.get('n')]


_cache = None
_lock = threading.Lock()


def works():
    """Список работ. Пустой, если файл недоступен или испорчен."""
    global _cache
    if _cache is None:
        with _lock:
            if _cache is None:
                try:
                    _cache = _read()
                    log.info('Каталог работ прочитан: %d позиций', len(_cache))
                except (OSError, ValueError) as e:
                    log.warning('Каталог работ не прочитан (%s): %s', RND_JS, e)
                    _cache = []
    return _cache


def reset():
    """Сбросить кэш — нужно тестам и после правки данных без перезапуска."""
    global _cache
    _cache = None
