"""Таблица кэша.

Заводится миграцией, а не отдельной командой: без неё счётчики частоты
молча перестают работать, а забыть про ручной шаг легко. Команда
createcachetable идемпотентна — повторный запуск ничего не портит.
"""
from django.core.management import call_command
from django.db import migrations


def create(apps, schema_editor):
    call_command('createcachetable', 'pulsar_cache', verbosity=0)


def drop(apps, schema_editor):
    schema_editor.execute('DROP TABLE IF EXISTS pulsar_cache')


class Migration(migrations.Migration):
    dependencies = [('booking', '0012_composejob')]
    operations = [migrations.RunPython(create, drop)]
