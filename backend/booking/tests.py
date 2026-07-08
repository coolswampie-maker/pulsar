"""
Приёмочные тесты ПУЛЬСАР-бэкенда. Запуск:  python manage.py test booking -v2
Покрывают: цены, лимит наличия, синхронизацию календаря, API планировщика,
рендер страниц админки. Демо-данные не трогаются — тесты идут в отдельной БД.
"""
import json
from datetime import date, time

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from booking.models import BookingLine, BusySlot, Order, Resource


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
        self.d = date(2026, 7, 20)

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
        newd = date(2026, 7, 22)
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

    def test_admin_pages_load(self):
        for name, args in [
            ('admin:index', []),
            ('admin:booking_order_changelist', []),
            ('admin:booking_order_add', []),
            ('admin:booking_resource_changelist', []),
            ('admin:booking_resource_add', []),
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
            'lines-0-resource': self.eq.slug, 'lines-0-date': '2026-07-20',
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
            'lines-0-resource': self.eq.slug, 'lines-0-date': '2026-07-20',
            'lines-0-slot_start': '09:00:00', 'lines-0-slot_end': '12:00:00',
            'lines-0-qty': '9', 'lines-0-hours': '3',
            '_save': 'Save',
        }
        r = self.c.post(url, data)
        self.assertEqual(r.status_code, 200)  # форма вернулась с ошибкой
        self.assertContains(r, 'в наличии')


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
            {'id': line.pk, 'resource': 'eq1', 'date': '2026-07-20',
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
            {'id': l1.pk, 'resource': 'eq1', 'date': '2026-07-20', 'start': '09:00:00', 'end': '11:00:00', 'hours': 2},
            {'id': l2.pk, 'resource': 'eq1', 'date': '2026-07-20', 'start': '10:00:00', 'end': '12:00:00', 'hours': 2},
        ])
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'пересек')

    def test_confirm_over_other_confirmed_blocked(self):
        self._order_line('confirmed', time(9), time(11))          # чужая подтверждённая бронь 9–11
        b, lb = self._order_line('new', time(9), time(10))
        r = self.order_change_post(b, 'confirmed', [
            {'id': lb.pk, 'resource': 'eq1', 'date': '2026-07-20', 'start': '09:00:00', 'end': '10:00:00', 'hours': 1}])
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'уже занят')

    def test_confirm_without_overlap_ok(self):
        self._order_line('confirmed', time(9), time(11))
        b, lb = self._order_line('new', time(13), time(14))
        r = self.order_change_post(b, 'confirmed', [
            {'id': lb.pk, 'resource': 'eq1', 'date': '2026-07-20', 'start': '13:00:00', 'end': '14:00:00', 'hours': 1}])
        self.assertEqual(r.status_code, 302)

    def test_new_request_over_confirmed_allowed(self):
        """Неподтверждённую заявку можно завести даже если слот занят (это лишь запрос)."""
        self._order_line('confirmed', time(9), time(11))
        b, lb = self._order_line('new', time(9), time(10))
        r = self.order_change_post(b, 'new', [
            {'id': lb.pk, 'resource': 'eq1', 'date': '2026-07-20', 'start': '09:00:00', 'end': '10:00:00', 'hours': 1}])
        self.assertEqual(r.status_code, 302)


class PlannerGuardTests(Base):
    def _create(self, slug='eq1', d=None, start='09:00', end='11:00'):
        return self.api_ok({'action': 'create', 'resource': slug,
                            'date': (d or self.d).isoformat(), 'start': start, 'end': end})

    def test_move_cross_day_into_conflict_blocked(self):
        day_b = date(2026, 7, 21)
        a = self._create(d=self.d)
        self._create(d=day_b)                                  # занятость на дне-приёмнике
        res = self.api_ok({'action': 'move', 'id': a['id'], 'start': '09:00', 'end': '11:00',
                           'date': day_b.isoformat()})
        self.assertFalse(res['ok'])
        self.assertIn('аложени', res['error'])

    def test_move_cross_day_free_ok(self):
        a = self._create(d=self.d)
        res = self.api_ok({'action': 'move', 'id': a['id'], 'start': '09:00', 'end': '11:00',
                           'date': date(2026, 7, 25).isoformat()})
        self.assertTrue(res['ok'])
        self.assertEqual(BusySlot.objects.get(pk=a['id']).date, date(2026, 7, 25))

    def test_create_in_past_blocked(self):
        res = self._create(d=date(2020, 1, 1))
        self.assertFalse(res['ok'])
        self.assertIn('прошл', res['error'])

    def test_move_into_past_blocked(self):
        a = self._create(d=self.d)
        res = self.api_ok({'action': 'move', 'id': a['id'], 'start': '09:00', 'end': '11:00',
                           'date': date(2020, 1, 1).isoformat()})
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
