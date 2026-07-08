"""
Импорт полного каталога из booking/data/catalog.json (выгрузка фронта data/resources.js).
Запуск:  python manage.py import_catalog
Идемпотентно — можно запускать повторно (update_or_create).
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand

from booking.models import Resource

DATA = Path(__file__).resolve().parent.parent.parent / 'data' / 'catalog.json'


class Command(BaseCommand):
    help = 'Импортировать полный каталог ресурсов из catalog.json'

    def handle(self, *args, **opts):
        payload = json.loads(DATA.read_text(encoding='utf-8'))
        items = payload['resources']

        # Пасс 1 — сами ресурсы (без связей)
        for it in items:
            Resource.objects.update_or_create(slug=it['id'], defaults=dict(
                type=it['type'], category=it.get('category', ''), book_mode=it['bookMode'],
                title=it['title'], lab=it.get('lab', ''), clean_class=it.get('cleanClass', ''),
                description=it.get('description', ''), specs=it.get('specs', []),
                price_value=it.get('priceValue', 0), price_unit=it.get('priceUnit', 'час'),
                min_units=it.get('minUnits', 1), image=it.get('img', ''), is_active=True,
            ))

        # Пасс 2 — связи (оператор + комплект), когда все объекты уже есть
        for it in items:
            r = Resource.objects.get(slug=it['id'])
            r.requires_operator_id = it.get('requiresOperator') or None
            r.save(update_fields=['requires_operator'])
            bundled = it.get('bundledWith') or []
            r.bundled_with.set(Resource.objects.filter(slug__in=bundled))

        self.stdout.write(self.style.SUCCESS(
            f'Импортировано ресурсов: {Resource.objects.count()} '
            f'(помещений {Resource.objects.filter(type="room").count()}, '
            f'оборудования {Resource.objects.filter(type="equipment").count()}, '
            f'специалистов {Resource.objects.filter(type="specialist").count()}, '
            f'услуг {Resource.objects.filter(type="service").count()})'))
