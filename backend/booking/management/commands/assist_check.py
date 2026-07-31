"""Проверка связки с моделью: `python manage.py assist_check`.

Показывает, что именно настроено, делает один реальный запрос и говорит
человеческим языком, что не так. Нужна, чтобы не гадать на боевом сервере,
почему подбор отвечает «local» вместо «ai».
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from booking.assist import assist, model_uri
from booking.models import Resource


class Command(BaseCommand):
    help = 'Проверить настройку ИИ-подбора и сделать тестовый запрос к модели'

    def add_arguments(self, parser):
        parser.add_argument('--query', default='нужно определить примеси в субстанции',
                            help='Задача, на которой проверяем подбор')

    def handle(self, *args, **opts):
        ok, warn, err = self.style.SUCCESS, self.style.WARNING, self.style.ERROR

        key = getattr(settings, 'YANDEX_API_KEY', '')
        folder = getattr(settings, 'YANDEX_FOLDER_ID', '')

        self.stdout.write('Настройки:')
        self.stdout.write(f'  folder id : {folder or "— не задан —"}')
        # ключ не печатаем целиком: команду запускают в общих терминалах
        self.stdout.write(f'  API-ключ  : {(key[:6] + "…" + key[-4:]) if len(key) > 12 else ("задан" if key else "— не задан —")}')
        self.stdout.write(f'  модель    : {model_uri()}')
        self.stdout.write(f'  таймаут   : {getattr(settings, "ASSIST_TIMEOUT", "?")} с')

        if not key or not folder:
            self.stdout.write(warn(
                '\nМодель не настроена — подбор работает на встроенном алгоритме.\n'
                'Добавьте YANDEX_API_KEY и YANDEX_FOLDER_ID в backend/.env '
                'и перезапустите сервис.'))
            return

        resources = list(Resource.objects.filter(is_active=True))
        if not resources:
            self.stdout.write(err('\nКаталог пуст — сначала выполните import_catalog.'))
            return
        self.stdout.write(f'  позиций в каталоге: {len(resources)}')

        query = opts['query']
        self.stdout.write(f'\nЗапрос: «{query}»')
        picked, mode, reply = assist(query, resources)

        self.stdout.write(f'Ответ ассистента: {reply or "—"}')

        if mode == 'licensed':
            self.stdout.write(warn(
                '\nЗапрос отнесён к требующим разрешений — к модели не обращались.'))
        elif mode == 'ai':
            self.stdout.write(ok('\nМодель отвечает. Подбор работает через ИИ.'))
        else:
            self.stdout.write(err(
                '\nМодель не ответила — сработал запасной подбор.\n'
                'Частые причины:\n'
                '  401 — ключ неверный или от другого аккаунта;\n'
                '  403 — сервисному аккаунту не выдана роль ai.languageModels.user;\n'
                '  404 — опечатка в folder id или в названии модели;\n'
                '  429 — превышен лимит запросов, повторите позже;\n'
                '  таймаут — сервер не достучался до llm.api.cloud.yandex.net.\n'
                'Точная причина — в логе сервиса: journalctl -u pulsar -n 50'))

        self.stdout.write(f'\nПодобрано позиций: {len(picked)}')
        for r, why in picked:
            self.stdout.write(f'  · {r.title}')
            if why:
                self.stdout.write(f'      {why}')
