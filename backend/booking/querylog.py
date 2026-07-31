"""Журнал запросов к ИИ-подбору — обычный текстовый файл на сервере.

Намеренно НЕ база и НЕ раздел в CRM: это рабочая заметка, а не сущность
системы. Файл можно прочитать, скопировать, очистить или удалить одной
командой, ничего не сломав, — а строка в базе тянет за собой миграцию,
резервные копии и обязательства по хранению.

Зачем вообще: запросы, по которым ничего не нашлось, — это готовый список
того, чего не хватает в каталоге. Плюс видно, как часто подбор сваливается
на встроенный алгоритм: если это стало регулярным, значит с моделью что-то
не так, и узнать об этом лучше раньше жалоб.

Чего здесь нет осознанно: IP-адресов и любых сведений о посетителе. Текст
запроса и так свободный — люди иногда пишут туда лишнее.

Формат строки (разделитель — табуляция, чтобы открывалось и в Excel):
    2026-07-31 18:04:12	ai	3	нужно определить примеси в субстанции
"""
import logging
import os
from pathlib import Path

from django.conf import settings
from django.utils import timezone

log = logging.getLogger(__name__)

MAX_LINE = 500          # длиннее запрос и не принимается
MAX_BYTES = 5 * 1024 * 1024   # больше 5 МБ на маленьком VPS держать незачем


def log_path():
    """Куда писать. Пустое значение в настройках — журнал выключен."""
    p = getattr(settings, 'ASSIST_LOG_FILE', '')
    return Path(p) if p else None


def _rotate(path):
    """Разросшийся файл переименовываем в .old, начиная с чистого.

    Гонка между рабочими процессами здесь безобидна: худшее, что бывает, —
    несколько строк уедут в .old вместо нового файла.
    """
    try:
        if path.exists() and path.stat().st_size > MAX_BYTES:
            path.replace(path.with_suffix(path.suffix + '.old'))
    except OSError:
        pass


def record(query, mode, found):
    """Записать один запрос.

    Журнал не имеет права ломать ответ пользователю: любая ошибка записи
    (нет прав, кончилось место) гасится и уходит в системный лог.
    """
    path = log_path()
    if not path:
        return
    line = '{}\t{}\t{}\t{}\n'.format(
        timezone.localtime().strftime('%Y-%m-%d %H:%M:%S'),
        mode,
        found,
        (query or '').replace('\t', ' ').replace('\n', ' ')[:MAX_LINE])
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _rotate(path)
        # O_APPEND: три процесса gunicorn пишут в один файл, и запись строки
        # целиком (меньше 4 КБ) при таком открытии не перемешивается
        with open(path, 'a', encoding='utf-8') as f:
            f.write(line)
    except OSError as e:
        log.warning('Не удалось записать журнал подбора (%s): %s', path, e)


def read(limit=50, only_empty=False, mode=None):
    """Прочитать журнал: список словарей, свежие сверху."""
    path = log_path()
    if not path or not path.exists():
        return []
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            raw = f.readlines()
    except OSError:
        return []
    out = []
    for ln in reversed(raw):
        parts = ln.rstrip('\n').split('\t')
        if len(parts) != 4:
            continue                      # битая строка — пропускаем молча
        when, m, found, q = parts
        try:
            found = int(found)
        except ValueError:
            continue
        if only_empty and found:
            continue
        if mode and m != mode:
            continue
        out.append({'when': when, 'mode': m, 'found': found, 'query': q})
        if len(out) >= limit:
            break
    return out


def stats():
    """Короткая сводка по всему файлу — сколько всего и чем отвечали."""
    path = log_path()
    if not path or not path.exists():
        return {}
    total, empty, modes = 0, 0, {}
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            for ln in f:
                parts = ln.rstrip('\n').split('\t')
                if len(parts) != 4:
                    continue
                total += 1
                modes[parts[1]] = modes.get(parts[1], 0) + 1
                if parts[2] == '0':
                    empty += 1
    except OSError:
        return {}
    size = 0
    try:
        size = os.path.getsize(path)
    except OSError:
        pass
    return {'total': total, 'empty': empty, 'modes': modes, 'size': size, 'path': str(path)}
