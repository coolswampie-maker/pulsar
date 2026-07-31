"""
Приёмочные тесты ПУЛЬСАР-бэкенда. Запуск:  python manage.py test booking -v2
Покрывают: цены, лимит наличия, синхронизацию календаря, API планировщика,
рендер страниц админки. Демо-данные не трогаются — тесты идут в отдельной БД.
"""
import json
from datetime import time, timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from booking.models import (BookingLine, BusySlot, Company, CustomRequest, Kpi,
                            Order, Resource)

# Даты тестов считаем от сегодняшнего дня, а не фиксируем в календаре: модели и
# планировщик отклоняют бронь в прошлом, поэтому зашитые даты со временем
# становились прошлым и тесты начинали падать сами по себе.


def D(offset=0):
    """Дата теста: опорная (сегодня + 5 дней) плюс смещение в днях."""
    return timezone.localdate() + timedelta(days=5 + offset)


def S(offset=0):
    """Та же дата строкой ISO — для JSON-запросов и формсетов админки."""
    return D(offset).isoformat()


class Base(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('t', 't@t.t', 'pw')
        self.c = Client()
        self.c.force_login(self.admin)
        self.eq = Resource.objects.create(
            slug='eq1', type='equipment', book_mode='hour', title='Прибор',
            price_value=1000, units_total=1)
        self.srv = Resource.objects.create(
            slug='srv1', type='service', book_mode='sample', title='Услуга',
            price_value=500, units_total=3)
        self.api = reverse('admin:booking_busyslot_gantt_api')
        self.d = D()

    def post(self, payload):
        return self.c.post(self.api, data=json.dumps(payload), content_type='application/json')

    def api_ok(self, payload):
        r = self.post(payload)
        return json.loads(r.content)

    def order_change_post(self, o, status, lines, resident=False):
        """POST формы заявки с позициями. lines: список dict(id?, resource, date, start, end, qty, hours)."""
        initial = sum(1 for ln in lines if ln.get('id'))
        data = {
            'status': status, 'org': o.org or 'X', 'contact_name': '', 'email': '', 'phone': '', 'note': '',
            'lines-TOTAL_FORMS': str(len(lines)), 'lines-INITIAL_FORMS': str(initial),
            'lines-MIN_NUM_FORMS': '0', 'lines-MAX_NUM_FORMS': '1000', '_save': 'Save',
        }
        if resident:
            data['resident'] = 'on'
        for i, ln in enumerate(lines):
            p = f'lines-{i}-'
            data[p + 'order'] = str(o.pk)
            if ln.get('id'):
                data[p + 'id'] = str(ln['id'])
            data[p + 'resource'] = ln['resource']
            data[p + 'date'] = ln['date']
            data[p + 'slot_start'] = ln.get('start', '')
            data[p + 'slot_end'] = ln.get('end', '')
            data[p + 'qty'] = str(ln.get('qty', 1))
            data[p + 'hours'] = str(ln.get('hours') or '')
        return self.c.post(reverse('admin:booking_order_change', args=[o.pk]), data)


class PricingTests(Base):
    def test_units_total_default_is_one(self):
        r = Resource.objects.create(slug='x', type='room', book_mode='shift', title='Комната')
        self.assertEqual(r.units_total, 1)

    def test_line_price_hourly(self):
        line = BookingLine.objects.create(order=self._order(), resource=self.eq, hours=4, qty=1)
        self.assertEqual(line.line_price, 4000)  # 1000 × 4ч × 1

    def test_line_price_by_sample_qty(self):
        line = BookingLine.objects.create(order=self._order(), resource=self.srv, qty=3)
        self.assertEqual(line.line_price, 1500)  # 500 × 3 образца

    def test_qty_over_stock_rejected(self):
        line = BookingLine(order=self._order(), resource=self.eq, qty=2)
        with self.assertRaises(ValidationError):
            line.clean()

    def test_qty_within_stock_ok(self):
        line = BookingLine(order=self._order(), resource=self.srv, qty=3)
        line.clean()  # 3 ≤ 3 — без исключения

    def _order(self):
        return Order.objects.create(number='PLS-T', org='X', contact_name='X', email='', phone='')


class CalendarSyncTests(Base):
    def _confirmed_order_with_line(self, num='PLS-9001', **line_kw):
        o = Order.objects.create(number=num, status='confirmed', org='X', contact_name='X', email='', phone='')
        BookingLine.objects.create(order=o, resource=self.eq, date=self.d,
                                   slot_start=time(9), slot_end=time(11), **line_kw)
        o.sync_busy_slots()
        return o

    def test_confirmed_creates_slot(self):
        self._confirmed_order_with_line()
        self.assertEqual(BusySlot.objects.filter(note='Заявка PLS-9001').count(), 1)

    def test_rejected_removes_slots(self):
        o = self._confirmed_order_with_line()
        o.status = 'rejected'
        o.save()
        self.assertEqual(BusySlot.objects.filter(note='Заявка PLS-9001').count(), 0)

    def test_reedit_leaves_no_orphan_slot(self):
        """Перенос времени позиции у подтверждённой заявки не должен плодить старые слоты."""
        o = self._confirmed_order_with_line()
        line = o.lines.first()
        line.slot_start, line.slot_end = time(14), time(16)
        line.save()
        o.sync_busy_slots()
        slots = BusySlot.objects.filter(note='Заявка PLS-9001')
        self.assertEqual(slots.count(), 1, 'должен остаться один актуальный слот')
        self.assertEqual(slots.first().slot_start, time(14))


class PlannerApiTests(Base):
    def test_create_makes_order_and_slot(self):
        res = self.api_ok({'action': 'create', 'resource': 'eq1', 'date': self.d.isoformat(),
                           'start': '09:00', 'end': '12:00', 'org': 'ООО Тест'})
        self.assertTrue(res['ok'])
        self.assertEqual(res['kind'], 'order')
        order = Order.objects.get(note='Создано в планировщике')
        self.assertEqual(order.status, 'confirmed')
        line = order.lines.first()
        self.assertEqual(line.line_price, 3000)  # 1000 × 3ч
        self.assertEqual(order.total, 3000)
        self.assertEqual(BusySlot.objects.filter(note=f'Заявка {order.number}').count(), 1)

    def test_create_overlap_rejected(self):
        self.api_ok({'action': 'create', 'resource': 'eq1', 'date': self.d.isoformat(),
                     'start': '09:00', 'end': '12:00'})
        res = self.api_ok({'action': 'create', 'resource': 'eq1', 'date': self.d.isoformat(),
                           'start': '10:00', 'end': '11:00'})
        self.assertFalse(res['ok'])
        self.assertIn('аложени', res['error'])

    def test_create_bad_time_rejected(self):
        res = self.api_ok({'action': 'create', 'resource': 'eq1', 'date': self.d.isoformat(),
                           'start': '12:00', 'end': '10:00'})
        self.assertFalse(res['ok'])

    def test_move_same_day(self):
        c = self.api_ok({'action': 'create', 'resource': 'eq1', 'date': self.d.isoformat(),
                         'start': '09:00', 'end': '11:00'})
        res = self.api_ok({'action': 'move', 'id': c['id'], 'start': '13:00', 'end': '15:00',
                           'date': self.d.isoformat()})
        self.assertTrue(res['ok'])
        slot = BusySlot.objects.get(pk=c['id'])
        self.assertEqual(slot.slot_start, time(13))

    def test_move_cross_day_syncs_line(self):
        c = self.api_ok({'action': 'create', 'resource': 'eq1', 'date': self.d.isoformat(),
                         'start': '09:00', 'end': '11:00'})
        newd = D(2)
        res = self.api_ok({'action': 'move', 'id': c['id'], 'start': '09:00', 'end': '11:00',
                           'date': newd.isoformat()})
        self.assertTrue(res['ok'])
        slot = BusySlot.objects.get(pk=c['id'])
        self.assertEqual(slot.date, newd)
        line = BookingLine.objects.get(order__number=slot.note[len('Заявка '):])
        self.assertEqual(line.date, newd, 'позиция заявки должна переехать вместе со слотом')

    def test_resize(self):
        c = self.api_ok({'action': 'create', 'resource': 'eq1', 'date': self.d.isoformat(),
                         'start': '09:00', 'end': '11:00'})
        res = self.api_ok({'action': 'resize', 'id': c['id'], 'start': '09:00', 'end': '13:00',
                           'date': self.d.isoformat()})
        self.assertTrue(res['ok'])
        self.assertEqual(BusySlot.objects.get(pk=c['id']).slot_end, time(13))

    def test_delete_operator_order(self):
        c = self.api_ok({'action': 'create', 'resource': 'eq1', 'date': self.d.isoformat(),
                         'start': '09:00', 'end': '11:00'})
        res = self.api_ok({'action': 'delete', 'id': c['id']})
        self.assertTrue(res['ok'])
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(BusySlot.objects.count(), 0)

    def test_delete_customer_order_protected(self):
        o = Order.objects.create(number='PLS-C', status='confirmed', org='Клиент',
                                 contact_name='X', email='', phone='', note='с сайта')
        BookingLine.objects.create(order=o, resource=self.eq, date=self.d,
                                   slot_start=time(9), slot_end=time(11))
        o.sync_busy_slots()
        slot = BusySlot.objects.get(note='Заявка PLS-C')
        res = self.api_ok({'action': 'delete', 'id': slot.pk})
        self.assertFalse(res['ok'])
        self.assertTrue(Order.objects.filter(number='PLS-C').exists())


class RenderTests(Base):
    def test_gantt_renders_each_type(self):
        base = reverse('admin:booking_busyslot_changelist')
        for t in ('equipment', 'room', 'specialist', 'service', 'busy'):
            r = self.c.get(base, {'type': t, 'days': 7})
            self.assertEqual(r.status_code, 200, f'тип {t}')
            self.assertContains(r, 'Календарь занятости')

    def test_gantt_paging(self):
        base = reverse('admin:booking_busyslot_changelist')
        r = self.c.get(base, {'type': 'equipment', 'days': 14, 'off': 14})
        self.assertEqual(r.status_code, 200)

    def test_raw_list_available(self):
        base = reverse('admin:booking_busyslot_changelist')
        r = self.c.get(base, {'list': 1})
        self.assertEqual(r.status_code, 200)

    def test_order_form_carries_units_map(self):
        # карта наличия для ограничения «кол-ва» в форме
        r = self.c.get(reverse('admin:booking_order_add'))
        self.assertContains(r, 'res-units')
        self.assertContains(r, 'eq1')

    def test_admin_pages_load(self):
        # оператор видит все разделы: заявки, каталог, компании, показатели, планировщик
        for name, args in [
            ('admin:index', []),
            ('admin:booking_order_changelist', []),
            ('admin:booking_order_add', []),
            ('admin:booking_resource_changelist', []),
            ('admin:booking_resource_add', []),
            ('admin:booking_company_changelist', []),
            ('admin:booking_kpi_changelist', []),
            ('admin:booking_busyslot_changelist', []),
        ]:
            r = self.c.get(reverse(name, args=args))
            self.assertEqual(r.status_code, 200, name)


class AdminFormTests(Base):
    def test_order_form_recomputes_total(self):
        """Правка часов в позиции через форму → сумма и итог пересчитываются."""
        o = Order.objects.create(number='PLS-F', status='new', org='X', contact_name='X', email='', phone='')
        line = BookingLine.objects.create(order=o, resource=self.eq, date=self.d,
                                          slot_start=time(9), slot_end=time(12), hours=3, qty=1)
        url = reverse('admin:booking_order_change', args=[o.pk])
        data = {
            'status': 'confirmed', 'org': 'X', 'contact_name': 'X', 'email': '', 'phone': '', 'note': '',
            'lines-TOTAL_FORMS': '1', 'lines-INITIAL_FORMS': '1',
            'lines-MIN_NUM_FORMS': '0', 'lines-MAX_NUM_FORMS': '1000',
            'lines-0-id': str(line.pk), 'lines-0-order': str(o.pk),
            'lines-0-resource': self.eq.slug, 'lines-0-date': S(),
            'lines-0-slot_start': '09:00:00', 'lines-0-slot_end': '12:00:00',
            'lines-0-qty': '1', 'lines-0-hours': '5',
            '_save': 'Save',
        }
        r = self.c.post(url, data)
        if r.status_code != 302:
            af = r.context.get('adminform')
            fs = r.context.get('inline_admin_formsets')
            self.fail(f'form={dict(af.form.errors) if af else None} '
                      f'inline={[list(x.formset.errors) for x in (fs or [])]} '
                      f'nonform={[list(x.formset.non_form_errors()) for x in (fs or [])]}')
        o.refresh_from_db()
        self.assertEqual(o.subtotal, 5000)   # 1000 × 5ч
        self.assertEqual(o.total, 5000)      # резидент не отмечен → без скидки
        self.assertEqual(BusySlot.objects.filter(note='Заявка PLS-F').count(), 1)

    def test_order_form_qty_over_stock_blocked(self):
        o = Order.objects.create(number='PLS-Q', status='new', org='X', contact_name='X', email='', phone='')
        line = BookingLine.objects.create(order=o, resource=self.eq, date=self.d,
                                          slot_start=time(9), slot_end=time(12), hours=3, qty=1)
        url = reverse('admin:booking_order_change', args=[o.pk])
        data = {
            'status': 'new', 'org': 'X', 'contact_name': 'X', 'email': '', 'phone': '', 'note': '',
            'lines-TOTAL_FORMS': '1', 'lines-INITIAL_FORMS': '1',
            'lines-MIN_NUM_FORMS': '0', 'lines-MAX_NUM_FORMS': '1000',
            'lines-0-id': str(line.pk), 'lines-0-order': str(o.pk),
            'lines-0-resource': self.eq.slug, 'lines-0-date': S(),
            'lines-0-slot_start': '09:00:00', 'lines-0-slot_end': '12:00:00',
            'lines-0-qty': '9', 'lines-0-hours': '3',
            '_save': 'Save',
        }
        r = self.c.post(url, data)
        self.assertEqual(r.status_code, 200)  # форма вернулась с ошибкой
        self.assertContains(r, 'в наличии')


class CabinetApiTests(TestCase):
    """Личный кабинет компании: регистрация, вход, профиль, свои заявки."""

    def setUp(self):
        self.c = Client()
        Resource.objects.create(slug='eq1', type='equipment', book_mode='hour',
                                title='Прибор', price_value=1000, units_total=1)

    def _j(self, r):
        return json.loads(r.content)

    # пароль должен проходить AUTH_PASSWORD_VALIDATORS (8+ символов, не из
    # словаря утечек, не только цифры) — иначе регистрация вернёт 400
    def register(self, email='co@x.ru', **kw):
        data = {'email': email, 'password': 'Nauka2026lab', 'name': 'ООО Тест', 'resident': True}
        data.update(kw)
        return self.c.post('/api/auth/register/', data=json.dumps(data), content_type='application/json')

    def _auth(self, r):
        return {'HTTP_AUTHORIZATION': 'Token ' + self._j(r)['token']}

    def test_register_returns_token_and_company(self):
        r = self.register()
        self.assertEqual(r.status_code, 201)
        d = self._j(r)
        self.assertTrue(d['token'])
        self.assertEqual(d['company']['name'], 'ООО Тест')

    def test_register_duplicate_email_blocked(self):
        self.register()
        self.assertEqual(self.register().status_code, 400)

    def test_login_ok_and_bad(self):
        self.register(email='a@a.ru')
        ok = self.c.post('/api/auth/login/', data=json.dumps({'email': 'a@a.ru', 'password': 'Nauka2026lab'}),
                         content_type='application/json')
        self.assertEqual(ok.status_code, 200)
        self.assertTrue(self._j(ok)['token'])
        bad = self.c.post('/api/auth/login/', data=json.dumps({'email': 'a@a.ru', 'password': 'x'}),
                          content_type='application/json')
        self.assertEqual(bad.status_code, 400)

    def test_me_requires_auth(self):
        self.assertEqual(self.c.get('/api/auth/me/').status_code, 401)

    def test_me_get_and_update(self):
        auth = self._auth(self.register())
        self.assertEqual(self.c.get('/api/auth/me/', **auth).status_code, 200)
        upd = self.c.patch('/api/auth/me/', data=json.dumps({'phone': '+7 495 000-11-22'}),
                           content_type='application/json', **auth)
        self.assertEqual(upd.status_code, 200)
        self.assertEqual(self._j(upd)['phone'], '+7 495 000-11-22')

    def _order_payload(self):
        return {'contact': {}, 'resident': False, 'lines': [
            {'resourceId': 'eq1', 'date': S(), 'slotStart': '09:00', 'slotEnd': '11:00',
             'qty': 1, 'hours': 2, 'unitPrice': 1000, 'linePrice': 2000, 'isOperator': False}]}

    def test_registration_is_unconfirmed_and_not_resident(self):
        self.register()
        co = Company.objects.get(user__email='co@x.ru')
        self.assertFalse(co.confirmed)
        self.assertFalse(co.resident)   # статус ставит оператор

    def test_confirmed_resident_gets_discount(self):
        auth = self._auth(self.register())
        Company.objects.filter(user__email='co@x.ru').update(confirmed=True, resident=True)
        r = self.c.post('/api/orders/', data=json.dumps(self._order_payload()),
                        content_type='application/json', **auth)
        order = Order.objects.get(number=self._j(r)['id'])
        self.assertIsNotNone(order.company)
        self.assertEqual(order.discount, 500)   # подтверждён + резидент → 25%
        self.assertEqual(len(self._j(self.c.get('/api/orders/', **auth))), 1)

    def test_unconfirmed_company_no_discount(self):
        auth = self._auth(self.register())
        Company.objects.filter(user__email='co@x.ru').update(confirmed=False, resident=True)
        r = self.c.post('/api/orders/', data=json.dumps(self._order_payload()),
                        content_type='application/json', **auth)
        order = Order.objects.get(number=self._j(r)['id'])
        self.assertEqual(order.discount, 0)     # не подтверждён — без скидки

    def test_orders_list_requires_auth(self):
        self.assertEqual(self.c.get('/api/orders/').status_code, 401)

    def test_two_companies_see_only_their_orders(self):
        a = self._auth(self.register(email='a@a.ru'))
        b = self._auth(self.register(email='b@b.ru'))
        payload = {'contact': {}, 'resident': False, 'lines': [
            {'resourceId': 'eq1', 'date': S(), 'slotStart': '09:00', 'slotEnd': '10:00',
             'qty': 1, 'hours': 1, 'unitPrice': 1000, 'linePrice': 1000, 'isOperator': False}]}
        self.c.post('/api/orders/', data=json.dumps(payload), content_type='application/json', **a)
        self.assertEqual(len(self._j(self.c.get('/api/orders/', **a))), 1)
        self.assertEqual(len(self._j(self.c.get('/api/orders/', **b))), 0)

    def test_guest_order_not_linked(self):
        payload = {'contact': {'org': 'Гость', 'name': 'Иван', 'email': 'i@i.ru', 'phone': '123'},
                   'resident': False, 'lines': [
                       {'resourceId': 'eq1', 'date': S(), 'slotStart': '09:00', 'slotEnd': '10:00',
                        'qty': 1, 'hours': 1, 'unitPrice': 1000, 'linePrice': 1000, 'isOperator': False}]}
        r = self.c.post('/api/orders/', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(r.status_code, 201)
        order = Order.objects.get(number=self._j(r)['id'])
        self.assertIsNone(order.company)
        self.assertEqual(order.org, 'Гость')


class KpiApiTests(TestCase):
    """Показатели по методологии: автосоздание 6, ввод факта, статус."""

    def setUp(self):
        self.c = Client()
        r = self.c.post('/api/auth/register/',
                        data=json.dumps({'email': 'k@k.ru', 'password': 'Nauka2026lab', 'name': 'ООО КПЭ'}),
                        content_type='application/json')
        self.auth = {'HTTP_AUTHORIZATION': 'Token ' + json.loads(r.content)['token']}

    def test_kpi_requires_auth(self):
        self.assertEqual(self.c.get('/api/kpi/').status_code, 401)

    def test_kpi_get_autocreates_six(self):
        r = self.c.get('/api/kpi/?year=2026', **self.auth)
        self.assertEqual(r.status_code, 200)
        d = json.loads(r.content)
        self.assertEqual(d['year'], 2026)
        self.assertEqual(len(d['items']), 6)
        keys = [i['key'] for i in d['items']]
        self.assertIn('rid', keys)
        self.assertIn('export', keys)
        self.assertTrue(all(i['status'] == 'none' for i in d['items']))
        self.assertTrue(all(i['docs'] for i in d['items']))   # текст требуемых документов

    def _add(self, key, title, amount):
        return self.c.post('/api/kpi/' + key + '/entries/?year=2026',
                           data=json.dumps({'title': title, 'amount': amount}),
                           content_type='application/json', **self.auth)

    def test_entries_recompute_fact_and_status(self):
        co = Company.objects.get(user__email='k@k.ru')
        self.c.get('/api/kpi/?year=2026', **self.auth)
        Kpi.objects.filter(company=co, year=2026, key='rid').update(plan=3)   # план — оператор
        self.assertEqual(self._add('rid', 'Патент А', 1).status_code, 201)
        self._add('rid', 'Патент Б', 1)
        kpi = Kpi.objects.get(company=co, year=2026, key='rid')
        self.assertEqual(float(kpi.fact), 2)
        self.assertEqual(kpi.status, 'bad')          # 2/3 = 0.67
        self._add('rid', 'Патент В', 1)
        kpi.refresh_from_db()
        self.assertEqual(kpi.status, 'ok')           # 3/3

    def test_delete_entry_recomputes(self):
        co = Company.objects.get(user__email='k@k.ru')
        self.c.get('/api/kpi/?year=2026', **self.auth)
        eid = json.loads(self._add('revenue', 'Договор', 1000).content)['id']
        self.assertEqual(float(Kpi.objects.get(company=co, year=2026, key='revenue').fact), 1000)
        d = self.c.delete('/api/kpi/revenue/entries/%d/' % eid, **self.auth)
        self.assertEqual(d.status_code, 204)
        self.assertIsNone(Kpi.objects.get(company=co, year=2026, key='revenue').fact)

    def test_percent_indicator_from_revenue(self):
        co = Company.objects.get(user__email='k@k.ru')
        self.c.get('/api/kpi/?year=2026', **self.auth)
        self._add('revenue', 'Выручка', 100)
        self._add('rnd', 'НИОКР-расходы', 8)         # 8 / 100 = 8%
        self.assertEqual(Kpi.objects.get(company=co, year=2026, key='rnd').value, 8.0)

    def test_entry_requires_auth(self):
        r = self.c.post('/api/kpi/rid/entries/', data=json.dumps({'title': 'x', 'amount': 1}),
                        content_type='application/json')
        self.assertIn(r.status_code, (401, 403))


class ConnectivityTests(TestCase):
    """Сквозная связка: фронт (API) ↔ база ↔ оператор (CRM/ORM)."""

    def setUp(self):
        self.c = Client()
        Resource.objects.create(slug='eqc', type='equipment', book_mode='hour',
                                title='Прибор', price_value=1000, units_total=1)

    def _reg(self, email='c@c.ru'):
        r = self.c.post('/api/auth/register/',
                        data=json.dumps({'email': email, 'password': 'Nauka2026lab', 'name': 'ООО Связь'}),
                        content_type='application/json')
        return {'HTTP_AUTHORIZATION': 'Token ' + json.loads(r.content)['token']}

    def test_booking_reaches_crm_and_syncs_calendar(self):
        auth = self._reg()
        co = Company.objects.get(user__email='c@c.ru')
        co.confirmed, co.resident = True, True
        co.save()
        # фронт оформляет заявку
        payload = {'contact': {}, 'resident': False, 'lines': [
            {'resourceId': 'eqc', 'date': S(12), 'slotStart': '09:00', 'slotEnd': '11:00',
             'qty': 1, 'hours': 2, 'unitPrice': 1000, 'linePrice': 2000, 'isOperator': False}]}
        num = json.loads(self.c.post('/api/orders/', data=json.dumps(payload),
                                     content_type='application/json', **auth).content)['id']
        order = Order.objects.get(number=num)
        # оператор в CRM видит заявку с привязкой к компании и скидкой резидента
        self.assertEqual(order.company, co)
        self.assertEqual(order.discount, 500)
        # оператор подтверждает → общий календарь синхронизируется
        order.status = 'confirmed'
        order.save()
        self.assertEqual(BusySlot.objects.filter(note=f'Заявка {num}').count(), 1)
        # фронтовый эндпоинт занятости видит слот
        busy = json.loads(self.c.get('/api/resources/eqc/busy/').content)
        self.assertTrue(any(b['date'] == S(12) for b in busy))
        # компания видит подтверждённую заявку в своём ЛК
        mine = json.loads(self.c.get('/api/orders/', **auth).content)
        self.assertEqual(mine[0]['status'], 'confirmed')

    def test_operator_plan_reflects_in_company_cabinet(self):
        auth = self._reg('k2@k.ru')
        co = Company.objects.get(user__email='k2@k.ru')
        self.c.get('/api/kpi/?year=2026', **auth)                              # автосоздание 6
        Kpi.objects.filter(company=co, year=2026, key='rid').update(plan=3)    # план — оператор
        self.c.post('/api/kpi/rid/entries/?year=2026',
                    data=json.dumps({'title': 'Патент', 'amount': 2}),
                    content_type='application/json', **auth)                   # факт — компания
        d = json.loads(self.c.get('/api/kpi/?year=2026', **auth).content)
        rid = [i for i in d['items'] if i['key'] == 'rid'][0]
        self.assertEqual(float(rid['plan']), 3)
        self.assertEqual(rid['status'], 'bad')                                # 2/3 = 0.67

    def test_change_request_visible_to_operator(self):
        auth = self._reg('ch@ch.ru')
        order = Order.objects.create(number=Order.next_number(), status='confirmed',
                                     company=Company.objects.get(user__email='ch@ch.ru'), org='X')
        r = self.c.post(f'/api/orders/{order.pk}/request-change/',
                        data=json.dumps({'message': 'Перенести на другой день'}),
                        content_type='application/json', **auth)
        self.assertEqual(r.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.change_request, 'Перенести на другой день')


class CatalogImportTests(TestCase):
    def test_import_catalog_full(self):
        call_command('import_catalog')
        self.assertEqual(Resource.objects.count(), 35)
        self.assertEqual(Resource.objects.filter(type='equipment').count(), 19)


class ValidationTests(Base):
    def test_order_number_autogenerated(self):
        o = Order.objects.create(org='X')
        self.assertTrue(o.number.startswith('PLS-'), o.number)

    def test_order_numbers_unique_increment(self):
        a = Order.objects.create(org='A')
        b = Order.objects.create(org='B')
        self.assertNotEqual(a.number, b.number)

    def test_admin_add_order_without_number(self):
        data = {'status': 'new', 'org': 'ООО Новая', 'contact_name': '', 'email': '', 'phone': '', 'note': '',
                'lines-TOTAL_FORMS': '0', 'lines-INITIAL_FORMS': '0',
                'lines-MIN_NUM_FORMS': '0', 'lines-MAX_NUM_FORMS': '1000', '_save': 'Save'}
        r = self.c.post(reverse('admin:booking_order_add'), data)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Order.objects.filter(org='ООО Новая').exists())

    def test_line_end_before_start_rejected(self):
        line = BookingLine(order=Order.objects.create(org='X'), resource=self.eq,
                           date=self.d, slot_start=time(12), slot_end=time(10))
        with self.assertRaises(ValidationError):
            line.clean()

    def test_resident_gets_25_percent_discount(self):
        o = Order.objects.create(org='X', status='new', resident=True)
        line = BookingLine.objects.create(order=o, resource=self.eq, date=self.d,
                                          slot_start=time(9), slot_end=time(12), hours=3)
        r = self.order_change_post(o, 'confirmed', [
            {'id': line.pk, 'resource': 'eq1', 'date': S(),
             'start': '09:00:00', 'end': '12:00:00', 'hours': 3}], resident=True)
        self.assertEqual(r.status_code, 302)
        o.refresh_from_db()
        self.assertEqual((o.subtotal, o.discount, o.total), (3000, 750, 2250))


class OverlapFormTests(Base):
    def _order_line(self, status, start, end):
        o = Order.objects.create(org='X', status=status)
        line = BookingLine.objects.create(order=o, resource=self.eq, date=self.d,
                                          slot_start=start, slot_end=end, hours=2)
        if status == 'confirmed':
            o.sync_busy_slots()
        return o, line

    def test_two_lines_same_resource_overlap_blocked(self):
        o, l1 = self._order_line('new', time(9), time(11))
        l2 = BookingLine.objects.create(order=o, resource=self.eq, date=self.d,
                                        slot_start=time(13), slot_end=time(15), hours=2)
        r = self.order_change_post(o, 'new', [
            {'id': l1.pk, 'resource': 'eq1', 'date': S(), 'start': '09:00:00', 'end': '11:00:00', 'hours': 2},
            {'id': l2.pk, 'resource': 'eq1', 'date': S(), 'start': '10:00:00', 'end': '12:00:00', 'hours': 2},
        ])
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'пересек')

    def test_confirm_over_other_confirmed_blocked(self):
        self._order_line('confirmed', time(9), time(11))          # чужая подтверждённая бронь 9–11
        b, lb = self._order_line('new', time(9), time(10))
        r = self.order_change_post(b, 'confirmed', [
            {'id': lb.pk, 'resource': 'eq1', 'date': S(), 'start': '09:00:00', 'end': '10:00:00', 'hours': 1}])
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'уже занят')

    def test_confirm_without_overlap_ok(self):
        self._order_line('confirmed', time(9), time(11))
        b, lb = self._order_line('new', time(13), time(14))
        r = self.order_change_post(b, 'confirmed', [
            {'id': lb.pk, 'resource': 'eq1', 'date': S(), 'start': '13:00:00', 'end': '14:00:00', 'hours': 1}])
        self.assertEqual(r.status_code, 302)

    def test_new_request_over_confirmed_allowed(self):
        """Неподтверждённую заявку можно завести даже если слот занят (это лишь запрос)."""
        self._order_line('confirmed', time(9), time(11))
        b, lb = self._order_line('new', time(9), time(10))
        r = self.order_change_post(b, 'new', [
            {'id': lb.pk, 'resource': 'eq1', 'date': S(), 'start': '09:00:00', 'end': '10:00:00', 'hours': 1}])
        self.assertEqual(r.status_code, 302)


class PlannerGuardTests(Base):
    def _create(self, slug='eq1', d=None, start='09:00', end='11:00'):
        return self.api_ok({'action': 'create', 'resource': slug,
                            'date': (d or self.d).isoformat(), 'start': start, 'end': end})

    def test_move_cross_day_into_conflict_blocked(self):
        day_b = D(1)
        a = self._create(d=self.d)
        self._create(d=day_b)                                  # занятость на дне-приёмнике
        res = self.api_ok({'action': 'move', 'id': a['id'], 'start': '09:00', 'end': '11:00',
                           'date': day_b.isoformat()})
        self.assertFalse(res['ok'])
        self.assertIn('аложени', res['error'])

    def test_move_cross_day_free_ok(self):
        a = self._create(d=self.d)
        res = self.api_ok({'action': 'move', 'id': a['id'], 'start': '09:00', 'end': '11:00',
                           'date': S(5)})
        self.assertTrue(res['ok'])
        self.assertEqual(BusySlot.objects.get(pk=a['id']).date, D(5))

    def test_create_in_past_blocked(self):
        res = self._create(d=D(-100))
        self.assertFalse(res['ok'])
        self.assertIn('прошл', res['error'])

    def test_move_into_past_blocked(self):
        a = self._create(d=self.d)
        res = self.api_ok({'action': 'move', 'id': a['id'], 'start': '09:00', 'end': '11:00',
                           'date': S(-100)})
        self.assertFalse(res['ok'])
        self.assertIn('прошл', res['error'])

    def _narrow(self, slug):
        return Resource.objects.create(slug=slug, type='equipment', book_mode='hour',
                                       title='Узкий', price_value=100,
                                       work_start=time(9), work_end=time(18))

    def test_create_before_work_hours_blocked(self):
        self._narrow('eqn1')
        res = self._create(slug='eqn1', start='08:00', end='09:00')
        self.assertFalse(res['ok'])
        self.assertIn('рабочих часов', res['error'])

    def test_create_within_work_hours_ok(self):
        self._narrow('eqn2')
        res = self._create(slug='eqn2', start='09:00', end='12:00')
        self.assertTrue(res['ok'])

    def test_resize_beyond_work_hours_blocked(self):
        self._narrow('eqn3')
        c = self._create(slug='eqn3', start='09:00', end='17:00')
        res = self.api_ok({'action': 'resize', 'id': c['id'], 'start': '09:00', 'end': '19:00',
                           'date': self.d.isoformat()})
        self.assertFalse(res['ok'])
        self.assertIn('рабочих часов', res['error'])


class FormGuardTests(Base):
    def test_resource_default_work_hours(self):
        r = Resource.objects.create(slug='w', type='room', book_mode='shift', title='К')
        self.assertEqual((r.work_start, r.work_end), (time(8), time(20)))

    def test_form_line_outside_work_hours_blocked(self):
        narrow = Resource.objects.create(slug='eqn', type='equipment', book_mode='hour',
                                         title='Н', price_value=100, work_start=time(9), work_end=time(18))
        o = Order.objects.create(org='X', status='new')
        line = BookingLine.objects.create(order=o, resource=narrow, date=self.d,
                                          slot_start=time(9), slot_end=time(12), hours=3)
        r = self.order_change_post(o, 'new', [
            {'id': line.pk, 'resource': 'eqn', 'date': self.d.isoformat(),
             'start': '08:00:00', 'end': '12:00:00', 'hours': 4}])
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'рабочих часов')

    def test_form_new_line_in_past_blocked(self):
        o = Order.objects.create(org='X', status='new')
        good = BookingLine.objects.create(order=o, resource=self.eq, date=self.d,
                                          slot_start=time(9), slot_end=time(10), hours=1)
        r = self.order_change_post(o, 'new', [
            {'id': good.pk, 'resource': 'eq1', 'date': self.d.isoformat(),
             'start': '09:00:00', 'end': '10:00:00', 'hours': 1},
            {'resource': 'eq1', 'date': '2020-01-01', 'start': '09:00:00', 'end': '10:00:00', 'hours': 1},
        ])
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'прошлом')


class ActionTests(Base):
    def test_mark_confirmed_action_creates_slots(self):
        o = Order.objects.create(org='X', status='new')
        BookingLine.objects.create(order=o, resource=self.eq, date=self.d,
                                   slot_start=time(9), slot_end=time(11), hours=2)
        r = self.c.post(reverse('admin:booking_order_changelist'),
                        {'action': 'mark_confirmed', '_selected_action': [str(o.pk)]})
        self.assertIn(r.status_code, (200, 302))
        o.refresh_from_db()
        self.assertEqual(o.status, 'confirmed')
        self.assertEqual(BusySlot.objects.filter(note=f'Заявка {o.number}').count(), 1)


class AssistTests(TestCase):
    """ИИ-подбор позиций по описанию задачи.

    Настоящий YandexGPT в тестах не дёргаем — подменяем ask_yandex и проверяем
    то, что зависит от нас: разбор ответа, отсев выдуманных позиций и откат на
    локальный подбор при любой неудаче.
    """

    def setUp(self):
        self.c = Client()
        call_command('import_catalog')

    def _post(self, query):
        r = self.c.post('/api/assist/', data=json.dumps({'query': query}),
                        content_type='application/json')
        return r, (json.loads(r.content) if r.content else {})

    def test_empty_query_rejected(self):
        r, _ = self._post('   ')
        self.assertEqual(r.status_code, 400)

    def test_local_fallback_without_model(self):
        """Модель не настроена — подбор всё равно работает."""
        r, d = self._post('нужен ЯМР')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(d['mode'], 'local')
        self.assertTrue(any('ЯМР' in i['title'] for i in d['items']))

    def test_ai_answer_used(self):
        from booking import assist as A
        real = A.ask_yandex
        A.ask_yandex = lambda q, res: [{'id': 'eq-massspec', 'why': 'подходит для примесей'}]
        try:
            r, d = self._post('определить примеси')
        finally:
            A.ask_yandex = real
        self.assertEqual(d['mode'], 'ai')
        self.assertEqual(d['items'][0]['id'], 'eq-massspec')
        self.assertEqual(d['items'][0]['why'], 'подходит для примесей')

    def test_invented_resource_dropped(self):
        """Модель придумала прибор, которого нет — позиция не должна уйти клиенту."""
        from booking import assist as A
        real = A.ask_yandex
        A.ask_yandex = lambda q, res: [
            {'id': 'eq-kvantovyj-teleport', 'why': 'выдумка'},
            {'id': 'eq-massspec', 'why': 'реальная позиция'},
        ]
        try:
            r, d = self._post('что-нибудь')
        finally:
            A.ask_yandex = real
        ids = [i['id'] for i in d['items']]
        self.assertNotIn('eq-kvantovyj-teleport', ids)
        self.assertIn('eq-massspec', ids)

    def test_all_invented_falls_back_to_local(self):
        """Если реальных позиций у модели не оказалось — работает локальный подбор."""
        from booking import assist as A
        real = A.ask_yandex
        A.ask_yandex = lambda q, res: [{'id': 'nesushchestvuet', 'why': 'x'}]
        try:
            r, d = self._post('нужен ЯМР')
        finally:
            A.ask_yandex = real
        self.assertEqual(d['mode'], 'local')
        self.assertTrue(d['items'])

    def test_model_failure_falls_back(self):
        """Сеть отвалилась — пользователь всё равно получает ответ."""
        from booking import assist as A
        real = A.ask_yandex

        def boom(q, res):
            raise OSError('нет связи')

        A.ask_yandex = boom
        try:
            with self.assertRaises(OSError):
                A.ask_yandex('x', [])
        finally:
            A.ask_yandex = real
        # сам ask_yandex глушит ошибки внутри и возвращает None
        from django.test import override_settings
        with override_settings(YANDEX_API_KEY='k', YANDEX_FOLDER_ID='f',
                               YANDEX_LLM_URL='http://127.0.0.1:9/nope', ASSIST_TIMEOUT=1):
            r, d = self._post('нужен ЯМР')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(d['mode'], 'local')

    def test_markdown_wrapped_json_parsed(self):
        """Модели часто заворачивают JSON в ```json — разбор должен это переживать."""
        from booking.assist import _parse_model_json
        raw = '```json\n{"items":[{"id":"eq-nmr","why":"тест"}]}\n```'
        self.assertEqual(_parse_model_json(raw), [{'id': 'eq-nmr', 'why': 'тест'}])
        self.assertEqual(_parse_model_json('совсем не json'), [])
        self.assertEqual(_parse_model_json(''), [])

    def test_long_query_truncated(self):
        r, d = self._post('ЯМР ' + 'ы' * 5000)
        self.assertEqual(r.status_code, 200)

    def test_model_uri_accepts_both_forms(self):
        """YANDEX_MODEL можно задать слагом или полным адресом — результат один."""
        from django.test import override_settings

        from booking.assist import model_uri
        full = 'gpt://b1gtest/yandexgpt-lite/latest'
        with override_settings(YANDEX_FOLDER_ID='b1gtest', YANDEX_MODEL='yandexgpt-lite/latest'):
            self.assertEqual(model_uri(), full)
        # полный адрес не должен склеиваться с папкой второй раз
        with override_settings(YANDEX_FOLDER_ID='b1gtest', YANDEX_MODEL=full):
            self.assertEqual(model_uri(), full)
        # лишние пробелы при копировании из консоли
        with override_settings(YANDEX_FOLDER_ID='b1gtest', YANDEX_MODEL='  yandexgpt-lite/latest  '):
            self.assertEqual(model_uri(), full)


class CustomRequestTests(TestCase):
    """Индивидуальная заявка на подбор: клиент не нашёл нужного в каталоге."""

    def setUp(self):
        self.c = Client()

    def _post(self, **kw):
        data = {'need': 'Нужен источник синхротронного излучения для белковой кристаллографии'}
        data.update(kw)
        r = self.c.post('/api/custom-request/', data=json.dumps(data),
                        content_type='application/json')
        return r, (json.loads(r.content) if r.content else {})

    def test_guest_request_saved(self):
        r, d = self._post(contact_name='Иванов Иван', email='i@i.ru',
                          org='ООО Тест', period='до октября',
                          search_query='синхротрон')
        self.assertEqual(r.status_code, 201)
        self.assertTrue(d['id'].startswith('IND-'))
        req = CustomRequest.objects.get(number=d['id'])
        self.assertEqual(req.org, 'ООО Тест')
        self.assertEqual(req.period, 'до октября')
        # контекст поиска сохраняется: показывает, чего не хватает каталогу
        self.assertEqual(req.search_query, 'синхротрон')
        self.assertEqual(req.status, 'new')
        self.assertIsNone(req.company)

    def test_short_need_rejected(self):
        r, _ = self._post(need='мало', contact_name='И', email='i@i.ru')
        self.assertEqual(r.status_code, 400)

    def test_guest_without_contacts_rejected(self):
        """Без способа связи заявка бесполезна."""
        r, _ = self._post()
        self.assertEqual(r.status_code, 400)
        r, _ = self._post(contact_name='Иванов')      # имя есть, связи нет
        self.assertEqual(r.status_code, 400)

    def test_company_contacts_taken_from_profile(self):
        u = User.objects.create_user(username='co@x.ru', email='co@x.ru', password='Nauka2026lab')
        company = Company.objects.create(user=u, name='ООО «Из кабинета»',
                                         contact_name='Петров', phone='+79990001122')
        token = self.c.post('/api/auth/login/',
                            data=json.dumps({'email': 'co@x.ru', 'password': 'Nauka2026lab'}),
                            content_type='application/json')
        tok = json.loads(token.content)['token']
        r = self.c.post('/api/custom-request/',
                        data=json.dumps({'need': 'Нужна установка для криоэлектронной микроскопии'}),
                        content_type='application/json',
                        HTTP_AUTHORIZATION='Token ' + tok)
        self.assertEqual(r.status_code, 201)
        req = CustomRequest.objects.get(number=json.loads(r.content)['id'])
        self.assertEqual(req.company, company)
        self.assertEqual(req.org, 'ООО «Из кабинета»')
        self.assertEqual(req.email, 'co@x.ru')

    def test_numbers_increment(self):
        a, _ = self._post(contact_name='А', email='a@a.ru')
        b, _ = self._post(contact_name='Б', email='b@b.ru')
        na = json.loads(a.content)['id']
        nb = json.loads(b.content)['id']
        self.assertEqual(int(nb.split('-')[1]), int(na.split('-')[1]) + 1)

    def test_operator_sees_section(self):
        self._post(contact_name='И', email='i@i.ru')
        User.objects.create_superuser('op2', 'op2@t.t', 'pw')
        self.c.login(username='op2', password='pw')
        r = self.c.get('/admin/booking/customrequest/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'IND-')
