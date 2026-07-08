"""
Демо-данные для проверки. Полный каталог позже импортируем из data/resources.js
(скриптом-конвертером) или заводим через админку.
Запуск:  python manage.py seed_demo
"""
from django.core.management.base import BaseCommand

from booking.models import Resource

DEMO = [
    dict(slug='sp-ms', type='specialist', category='analytics', book_mode='hour',
         title='Специалист масс-спектрометрии и хроматографии',
         lab='Центр химического анализа', price_value=2500, price_unit='час', min_units=2,
         specs=['ВЭЖХ-МС, QTOF, ГХ-МС', 'Разработка методик', 'Обработка спектров']),
    dict(slug='eq-massspec', type='equipment', category='analytics', book_mode='hour',
         title='Масс-спектрометр Agilent 6545 QTOF LC/MS', lab='Центр химического анализа',
         price_value=6500, price_unit='час', min_units=2, image='eq-massspec',
         specs=['ВЭЖХ + QTOF', 'Высокое разрешение', 'Работа с оператором']),
    dict(slug='room-cleanroom-a', type='room', category='pharma', book_mode='shift',
         title='Чистая комната А — производственная фармацевтическая',
         lab='Учебно-производственный фарм. блок', clean_class='GMP A/B · ISO 5',
         price_value=18000, price_unit='смена', image='room-a',
         specs=['Ламинарный поток A/B', '28 м²', 'Шлюзы персонала и материалов']),
    dict(slug='srv-icp', type='service', category='analytics', book_mode='sample',
         title='Элементный анализ (ICP-MS) — под ключ', lab='Центр химического анализа',
         price_value=3500, price_unit='образец', min_units=1,
         specs=['ICP-MS', 'Определение элементов на уровне ppb', 'Протокол с результатами']),
]


class Command(BaseCommand):
    help = 'Заполнить каталог демо-ресурсами'

    def handle(self, *args, **opts):
        for d in DEMO:
            op = d.pop('operator', None)
            obj, created = Resource.objects.update_or_create(slug=d['slug'], defaults=d)
            self.stdout.write(('+ ' if created else '· ') + obj.title)
        # прибор → оператор
        Resource.objects.filter(slug='eq-massspec').update(requires_operator_id='sp-ms')
        self.stdout.write(self.style.SUCCESS('Готово. Дальше: createsuperuser → /admin/'))
