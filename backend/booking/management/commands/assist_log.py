"""Просмотр журнала запросов к ИИ-подбору.

Файл можно читать и обычным `tail`, но команда избавляет от необходимости
помнить путь и разбирать колонки глазами.

    manage.py assist_log                 последние 30 запросов
    manage.py assist_log --empty         только те, где ничего не нашлось
    manage.py assist_log --mode local    когда отвечала не модель
    manage.py assist_log --stats         сводка по всему файлу
    manage.py assist_log --clear         очистить журнал
"""
from django.core.management.base import BaseCommand

from booking import querylog

MODE_RU = {
    'ai': 'модель',
    'local': 'встроенный',
    'licensed': 'разрешения',
    'empty': 'пусто',
}


class Command(BaseCommand):
    help = 'Показать запросы, поступившие в ИИ-подбор'

    def add_arguments(self, p):
        p.add_argument('-n', '--limit', type=int, default=30, help='сколько строк (по умолчанию 30)')
        p.add_argument('--empty', action='store_true', help='только те, по которым ничего не нашлось')
        p.add_argument('--mode', help='ai | local | licensed')
        p.add_argument('--stats', action='store_true', help='сводка по всему файлу')
        p.add_argument('--clear', action='store_true', help='очистить журнал')

    def handle(self, *a, **o):
        path = querylog.log_path()
        if not path:
            self.stdout.write(self.style.WARNING(
                'Журнал выключен: в .env пустой ASSIST_LOG_FILE.'))
            return

        if o['clear']:
            try:
                open(path, 'w').close()
                self.stdout.write(self.style.SUCCESS(f'Журнал очищен: {path}'))
            except OSError as e:
                self.stdout.write(self.style.ERROR(f'Не удалось очистить: {e}'))
            return

        if o['stats']:
            s = querylog.stats()
            if not s:
                self.stdout.write(f'Журнал пуст или ещё не создан: {path}')
                return
            self.stdout.write(f"Файл:          {s['path']}  ({s['size'] // 1024} КБ)")
            self.stdout.write(f"Всего запросов: {s['total']}")
            pct = round(100 * s['empty'] / s['total']) if s['total'] else 0
            self.stdout.write(f"Без результата: {s['empty']}  ({pct}%)  ← чего не хватает каталогу")
            self.stdout.write('Чем отвечали:')
            for m, n in sorted(s['modes'].items(), key=lambda x: -x[1]):
                self.stdout.write(f'  {MODE_RU.get(m, m):<12} {n}')
            if s['modes'].get('local') and not s['modes'].get('ai'):
                self.stdout.write(self.style.WARNING(
                    '\nМодель не отвечала ни разу — проверьте: manage.py assist_check'))
            return

        rows = querylog.read(limit=o['limit'], only_empty=o['empty'], mode=o['mode'])
        if not rows:
            self.stdout.write('Подходящих записей нет.')
            return
        self.stdout.write(f'{"Когда":<20} {"Чем":<12} {"Найдено":>7}  Запрос')
        self.stdout.write('-' * 92)
        for r in rows:
            line = (f'{r["when"]:<20} {MODE_RU.get(r["mode"], r["mode"]):<12} '
                    f'{r["found"]:>7}  {r["query"][:48]}')
            # то, по чему ничего не нашлось, — самое интересное, выделяем
            self.stdout.write(self.style.WARNING(line) if not r['found'] else line)
