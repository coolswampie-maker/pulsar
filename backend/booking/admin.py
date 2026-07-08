"""
Админка = back-office оператора:
 • Каталог ресурсов — карточка ввода/редактирования оборудования и лабораторий.
 • Заявки — мини-CRM: статусы, состав, контакты, массовые действия.
 • Календарь занятости.
"""
from django.contrib import admin

from .models import BookingLine, BusySlot, Order, Resource


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ('title', 'type', 'category', 'price_value', 'price_unit', 'is_active')
    list_filter = ('type', 'category', 'is_active')
    search_fields = ('slug', 'title', 'lab')
    list_editable = ('is_active',)
    filter_horizontal = ('bundled_with',)
    fieldsets = (
        (None, {'fields': ('slug', 'type', 'category', 'book_mode', 'is_active')}),
        ('Карточка', {'fields': ('title', 'lab', 'clean_class', 'description', 'specs', 'image')}),
        ('Цена', {'fields': ('price_value', 'price_unit', 'min_units')}),
        ('Связи', {'fields': ('requires_operator', 'bundled_with')}),
    )


class BookingLineInline(admin.TabularInline):
    model = BookingLine
    extra = 0
    fields = ('resource', 'date', 'slot_start', 'slot_end', 'qty', 'hours', 'line_price', 'is_operator')
    autocomplete_fields = ('resource',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('number', 'org', 'contact_name', 'status', 'total', 'created_at')
    list_filter = ('status', 'resident', 'created_at')
    search_fields = ('number', 'org', 'contact_name', 'email', 'phone')
    readonly_fields = ('number', 'created_at', 'subtotal', 'discount', 'total')
    inlines = [BookingLineInline]
    actions = ['mark_confirmed', 'mark_rejected']

    def save_related(self, request, form, formsets, change):
        # позиции сохраняются после заявки — синхронизируем календарь уже с ними
        super().save_related(request, form, formsets, change)
        form.instance.sync_busy_slots()

    @admin.action(description='Подтвердить выбранные заявки')
    def mark_confirmed(self, request, queryset):
        for order in queryset:
            order.status = 'confirmed'
            order.save()  # save() сам заносит слоты в календарь
        self.message_user(request, f'Подтверждено заявок: {queryset.count()}')

    @admin.action(description='Отклонить выбранные заявки')
    def mark_rejected(self, request, queryset):
        for order in queryset:
            order.status = 'rejected'
            order.save()  # save() уберёт слоты этой заявки из календаря


GANTT_CSS = """
body{font-family:-apple-system,'Segoe UI',Roboto,sans-serif;margin:0;background:#f5f6f8;color:#1b2733}
.top{background:linear-gradient(90deg,#0E2A47,#0A1E33);color:#fff;padding:10px 18px;font-size:13px;display:flex;align-items:center;gap:2px;box-shadow:0 2px 10px rgba(10,30,51,.2)}
.top a{color:#cfe0f0;text-decoration:none;padding:5px 10px;border-radius:6px}
.top a:hover{color:#fff;background:rgba(255,255,255,.09)}
.top .brand{display:inline-flex;align-items:center;gap:8px;font-weight:800;letter-spacing:.05em;margin-right:8px}
.top .brand b{font-weight:500;color:#9db4cc;font-size:12px;letter-spacing:0}
.top .sp{flex:0 0 12px}
h1{font-size:23px;margin:20px 16px 4px;color:#0E2A47;letter-spacing:-.02em}
.sub{margin:0 16px 12px;color:#889;font-size:13px}
.filters{margin:0 16px 12px;font-size:13px;display:flex;align-items:center;flex-wrap:wrap;gap:6px}
.filters a{display:inline-block;padding:4px 11px;border:1px solid #cdd6df;border-radius:16px;color:#345;text-decoration:none}
.filters a.on{background:#264b63;color:#fff;border-color:#264b63}
.filters .hint{color:#96a0ab;border:none;margin-left:6px}
.wrap{overflow-x:auto;margin:0 16px 14px;border:1px solid #dde;border-radius:8px;background:#fff}
table{border-collapse:collapse;min-width:900px;font-size:12px;width:100%}
th,td{border:1px solid #eef}
th{background:#f0f3f7;position:sticky;top:0;text-align:center;padding:6px 4px;font-weight:600;min-width:118px}
th b{display:block}
th span{color:#8892a0;font-weight:400;font-size:11px}
th.wknd,td.wknd{background:#faf6f0}
.rescol{position:sticky;left:0;background:#fff;z-index:2;text-align:left;padding:9px 11px;min-width:240px;max-width:240px;border-right:2px solid #dde;font-weight:600;line-height:1.3}
th.rescol{z-index:3;background:#f0f3f7}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:8px;vertical-align:middle}
td.day{position:relative;height:34px;padding:0;cursor:copy;background-image:repeating-linear-gradient(90deg,transparent 0,transparent calc(8.333% - 1px),#e9edf3 calc(8.333% - 1px),#e9edf3 8.333%)}
td.day.wknd{background-color:#faf6f0}
.bar{position:absolute;top:4px;bottom:4px;border-radius:4px;color:#fff;font-size:10px;display:flex;align-items:center;justify-content:center;overflow:hidden;white-space:nowrap;padding:0 3px;box-shadow:0 1px 2px rgba(0,0,0,.18);font-variant-numeric:tabular-nums;cursor:grab;user-select:none;touch-action:none}
.bar.dragging{cursor:grabbing;opacity:.85;z-index:6;box-shadow:0 3px 10px rgba(0,0,0,.3)}
.bar .h{position:absolute;top:0;bottom:0;width:7px;cursor:ew-resize}
.bar .hl{left:0}
.bar .hr{right:0}
.bar .lbl{pointer-events:none}
.today{box-shadow:inset 0 3px 0 #c99b3f}
.empty{padding:30px;text-align:center;color:#889}
.legend{margin:0 16px 26px;font-size:12px;color:#556;display:flex;gap:18px;flex-wrap:wrap}
.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:middle}
#toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:#1b2733;color:#fff;padding:10px 18px;border-radius:8px;font-size:13px;opacity:0;transition:.25s;pointer-events:none;box-shadow:0 8px 24px rgba(0,0,0,.25);z-index:50}
#toast.show{opacity:1}
#toast.bad{background:#9a3b2b}
"""
GANTT_JS = """
(function(){
  var body=document.body, API=body.dataset.api, CSRF=body.dataset.csrf;
  var DS=8, DE=20, TOTAL=(DE-DS)*60, SNAP=30;
  function pad(n){return (n<10?'0':'')+n;}
  function m2s(m){return pad(Math.floor(m/60))+':'+pad(m%60);}
  function s2m(s){var p=s.split(':');return (+p[0])*60+(+p[1]);}
  function toast(msg,bad){var t=document.getElementById('toast');t.textContent=msg;t.className='show'+(bad?' bad':'');clearTimeout(t._t);t._t=setTimeout(function(){t.className='';},2600);}
  function post(p){return fetch(API,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':CSRF},body:JSON.stringify(p)}).then(function(r){return r.json();});}
  function place(bar,sM,eM){bar.style.left=((sM-DS*60)/TOTAL*100).toFixed(1)+'%';bar.style.width=Math.max(7,(eM-sM)/TOTAL*100).toFixed(1)+'%';bar.dataset.start=m2s(sM);bar.dataset.end=m2s(eM);bar.querySelector('.lbl').textContent=m2s(sM);bar.title=m2s(sM)+'–'+m2s(eM);}
  function mkBar(cell,res){var b=document.createElement('div');b.className='bar';b.dataset.id=res.id;b.dataset.href=res.href;b.style.background=res.color||cell.dataset.color;b.innerHTML='<span class="h hl"></span><span class="lbl"></span><span class="h hr"></span>';cell.appendChild(b);place(b,s2m(res.start),s2m(res.end));return b;}
  var drag=null, suppress=false;
  document.addEventListener('pointerdown',function(e){
    var bar=e.target.closest('.bar'); if(!bar) return; e.preventDefault();
    var mode=e.target.classList.contains('hl')?'resizeL':e.target.classList.contains('hr')?'resizeR':'move';
    drag={bar:bar,mode:mode,cell:bar.parentElement,x:e.clientX,moved:false,sM:s2m(bar.dataset.start),eM:s2m(bar.dataset.end)};
    bar.classList.add('dragging');
  });
  document.addEventListener('pointermove',function(e){
    if(!drag) return;
    var dx=e.clientX-drag.x; if(Math.abs(dx)>3) drag.moved=true;
    var w=drag.cell.getBoundingClientRect().width;
    var dM=Math.round((dx/w*TOTAL)/SNAP)*SNAP, sM=drag.sM, eM=drag.eM, dur=drag.eM-drag.sM;
    if(drag.mode==='move'){sM=drag.sM+dM;eM=drag.eM+dM;if(sM<DS*60){sM=DS*60;eM=sM+dur;}if(eM>DE*60){eM=DE*60;sM=eM-dur;}}
    else if(drag.mode==='resizeR'){eM=Math.max(sM+SNAP,Math.min(DE*60,drag.eM+dM));}
    else{sM=Math.min(eM-SNAP,Math.max(DS*60,drag.sM+dM));}
    place(drag.bar,sM,eM);
  });
  document.addEventListener('pointerup',function(){
    if(!drag) return; var d=drag; drag=null; d.bar.classList.remove('dragging');
    if(!d.moved){return;}
    suppress=true;
    post({action:d.mode==='move'?'move':'resize',id:d.bar.dataset.id,start:d.bar.dataset.start,end:d.bar.dataset.end})
      .then(function(res){if(res.ok){toast('Сохранено');}else{place(d.bar,d.sM,d.eM);toast(res.error||'Ошибка',true);}})
      .catch(function(){place(d.bar,d.sM,d.eM);toast('Сеть недоступна',true);});
  });
  document.addEventListener('click',function(e){
    if(suppress){suppress=false;return;}
    var bar=e.target.closest('.bar');
    if(bar){ if(bar.dataset.href) window.location=bar.dataset.href; return; }
    var cell=e.target.closest('td.day'); if(!cell) return;
    var rect=cell.getBoundingClientRect();
    var mins=DS*60+Math.round(((e.clientX-rect.left)/rect.width*TOTAL)/SNAP)*SNAP;
    var sM=Math.max(DS*60,Math.min(DE*60-60,mins)), eM=sM+60;
    post({action:'create',resource:cell.dataset.res,date:cell.dataset.date,start:m2s(sM),end:m2s(eM)})
      .then(function(res){if(res.ok){mkBar(cell,res);toast('Бронь создана');}else{toast(res.error||'Ошибка',true);}})
      .catch(function(){toast('Сеть недоступна',true);});
  });
  document.addEventListener('dblclick',function(e){
    var bar=e.target.closest('.bar'); if(!bar) return; e.preventDefault();
    if(!confirm('Удалить эту бронь из календаря?')) return;
    post({action:'delete',id:bar.dataset.id}).then(function(res){if(res.ok){bar.remove();toast('Удалено');}else{toast(res.error||'Ошибка',true);}});
  });
})();
"""
GANTT_COLORS = {'room': '#2e5b8a', 'equipment': '#8a5a2e', 'specialist': '#5a2e8a', 'service': '#2e8a6a'}
GANTT_LABELS = {'room': 'Лаборатории', 'equipment': 'Оборудование', 'specialist': 'Специалисты', 'service': 'Услуги'}
WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
DAY_START_MIN, DAY_END_MIN = 8 * 60, 20 * 60
TOTAL_MIN = DAY_END_MIN - DAY_START_MIN


def _times_overlap(a_start, a_end, b_start, b_end):
    """None (весь день) конфликтует с чем угодно в тот же день."""
    if a_start is None or b_start is None:
        return True
    return a_start < b_end and b_start < a_end


@admin.register(BusySlot)
class BusySlotAdmin(admin.ModelAdmin):
    date_hierarchy = 'date'
    list_display = ('date', 'slot_start', 'slot_end', 'resource', 'note')
    list_filter = ('date', 'resource__type', 'resource')
    search_fields = ('resource__title', 'note')
    autocomplete_fields = ('resource',)
    ordering = ('date', 'slot_start')
    change_list_template = 'admin/booking/busyslot/change_list.html'

    def get_urls(self):
        from django.urls import path
        extra = [
            path('gantt/', self.admin_site.admin_view(self.gantt_view), name='booking_busyslot_gantt'),
            path('gantt/api/', self.admin_site.admin_view(self.gantt_api), name='booking_busyslot_gantt_api'),
        ]
        return extra + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        # «Календарь занятости» = Гант-планировщик; сырой список записей — по ?list=1
        if request.GET.get('list'):
            return super().changelist_view(request, extra_context)
        return self.gantt_view(request)

    # ---------- конфликты ----------
    def _conflict(self, resource_id, d, start, end, exclude_pk=None):
        qs = BusySlot.objects.filter(resource_id=resource_id, date=d)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        return any(_times_overlap(start, end, o.slot_start, o.slot_end) for o in qs)

    # ---------- API планировщика (move/resize/create/delete) ----------
    def gantt_api(self, request):
        import json
        from datetime import datetime
        from django.http import JsonResponse
        from .models import Resource

        if request.method != 'POST':
            return JsonResponse({'ok': False, 'error': 'Только POST'}, status=405)
        try:
            data = json.loads((request.body or b'{}').decode('utf-8'))
        except ValueError:
            return JsonResponse({'ok': False, 'error': 'Некорректные данные'}, status=400)

        def ptime(s):
            return datetime.strptime(s, '%H:%M').time()

        def pdate(s):
            return datetime.strptime(s, '%Y-%m-%d').date()

        act = data.get('action')
        try:
            if act in ('move', 'resize'):
                slot = BusySlot.objects.get(pk=data['id'])
                st, en = ptime(data['start']), ptime(data['end'])
                if en <= st:
                    return JsonResponse({'ok': False, 'error': 'Окончание раньше начала'})
                if self._conflict(slot.resource_id, slot.date, st, en, exclude_pk=slot.pk):
                    return JsonResponse({'ok': False, 'error': 'Наложение с другой бронью'})
                slot.slot_start, slot.slot_end = st, en
                slot.save(update_fields=['slot_start', 'slot_end'])
                return JsonResponse({'ok': True, 'id': slot.pk, 'start': st.strftime('%H:%M'), 'end': en.strftime('%H:%M')})

            if act == 'create':
                r = Resource.objects.get(slug=data['resource'])
                d, st, en = pdate(data['date']), ptime(data['start']), ptime(data['end'])
                if en <= st:
                    return JsonResponse({'ok': False, 'error': 'Окончание раньше начала'})
                if self._conflict(r.pk, d, st, en):
                    return JsonResponse({'ok': False, 'error': 'Наложение с другой бронью'})
                slot = BusySlot.objects.create(resource=r, date=d, slot_start=st, slot_end=en,
                                               note='вручную (планировщик)')
                return JsonResponse({'ok': True, 'id': slot.pk, 'start': st.strftime('%H:%M'),
                                     'end': en.strftime('%H:%M'), 'color': GANTT_COLORS.get(r.type, '#555'),
                                     'href': f'/admin/booking/busyslot/{slot.pk}/change/'})

            if act == 'delete':
                BusySlot.objects.filter(pk=data['id']).delete()
                return JsonResponse({'ok': True})
        except BusySlot.DoesNotExist:
            return JsonResponse({'ok': False, 'error': 'Бронь не найдена'}, status=404)
        except Resource.DoesNotExist:
            return JsonResponse({'ok': False, 'error': 'Ресурс не найден'}, status=404)
        except (KeyError, ValueError) as ex:
            return JsonResponse({'ok': False, 'error': f'Ошибка данных: {ex}'}, status=400)
        return JsonResponse({'ok': False, 'error': 'Неизвестное действие'}, status=400)

    # ---------- страница Ганта ----------
    def gantt_view(self, request):
        from datetime import timedelta
        from django.http import HttpResponse
        from django.middleware.csrf import get_token
        from django.urls import reverse
        from django.utils import timezone
        from django.utils.html import escape
        from .models import Order, Resource

        api_url = reverse('admin:booking_busyslot_gantt_api')
        base = reverse('admin:booking_busyslot_changelist')

        try:
            span = max(7, min(60, int(request.GET.get('days', 14))))
        except ValueError:
            span = 14
        rtype = request.GET.get('type', 'equipment')
        if rtype not in ('room', 'equipment', 'specialist', 'service', 'busy'):
            rtype = 'equipment'

        today = timezone.localdate()
        days = [today + timedelta(days=i) for i in range(span)]

        slots = (BusySlot.objects.select_related('resource')
                 .filter(date__gte=days[0], date__lte=days[-1])
                 .order_by('resource__title', 'date', 'slot_start'))
        cells, res_with_slots = {}, {}
        for s in slots:
            res_with_slots.setdefault(s.resource_id, s.resource)
            cells.setdefault((s.resource_id, s.date), []).append(s)

        if rtype == 'busy':
            resources = list(res_with_slots.values())
        else:
            resources = list(Resource.objects.filter(is_active=True, type=rtype).order_by('title'))

        order_pk = dict(Order.objects.values_list('number', 'pk'))

        def href_for(slot):
            if slot.note and slot.note.startswith('Заявка '):
                pk = order_pk.get(slot.note[len('Заявка '):])
                if pk:
                    return f'/admin/booking/order/{pk}/change/'
            return f'/admin/booking/busyslot/{slot.pk}/change/'

        def daycls(d):
            c = 'wknd' if d.weekday() >= 5 else ''
            return (c + ' today').strip() if d == today else c

        def bar_html(slot, color):
            if slot.slot_start:
                s_min = slot.slot_start.hour * 60 + slot.slot_start.minute
                e_min = (slot.slot_end.hour * 60 + slot.slot_end.minute) if slot.slot_end else s_min + 60
            else:
                s_min, e_min = DAY_START_MIN, DAY_END_MIN
            s_min = max(DAY_START_MIN, min(DAY_END_MIN, s_min))
            e_min = max(s_min + 30, min(DAY_END_MIN, e_min))
            left = (s_min - DAY_START_MIN) / TOTAL_MIN * 100
            width = max(7, (e_min - s_min) / TOTAL_MIN * 100)
            lbl = slot.slot_start.strftime('%H:%M') if slot.slot_start else 'весь день'
            full = (slot.slot_start.strftime('%H:%M') + '–' +
                    (slot.slot_end.strftime('%H:%M') if slot.slot_end else '')) if slot.slot_start else 'весь день'
            title = full + (' · ' + slot.note if slot.note else '')
            return (f'<div class="bar" data-id="{slot.pk}" data-start="{lbl if slot.slot_start else "08:00"}" '
                    f'data-end="{slot.slot_end.strftime("%H:%M") if slot.slot_end else "20:00"}" '
                    f'data-href="{href_for(slot)}" style="left:{left:.1f}%;width:{width:.1f}%;background:{color}" '
                    f'title="{escape(title)}"><span class="h hl"></span>'
                    f'<span class="lbl">{escape(lbl)}</span><span class="h hr"></span></div>')

        head = '<th class="rescol">Ресурс</th>' + ''.join(
            f'<th class="{daycls(d)}"><b>{d.day:02d}.{d.month:02d}</b>'
            f'<span>{WEEKDAYS[d.weekday()]}</span></th>' for d in days)

        rows = ''
        for r in resources:
            color = GANTT_COLORS.get(r.type, '#555')
            tds = ''
            for d in days:
                items = cells.get((r.pk, d)) or []
                inner = ''.join(bar_html(s, color) for s in items)
                tds += (f'<td class="day {daycls(d)}" data-res="{r.slug}" '
                        f'data-date="{d.isoformat()}" data-color="{color}">{inner}</td>')
            rows += (f'<tr><td class="rescol"><span class="dot" style="background:{color}"></span>'
                     f'{escape(r.title)}</td>{tds}</tr>')
        if not resources:
            rows = f'<tr><td colspan="{span + 1}" class="empty">Нет ресурсов в этом разделе.</td></tr>'

        def flt(t, label):
            on = ' on' if t == rtype else ''
            return f'<a class="f{on}" href="{base}?type={t}&days={span}">{label}</a>'
        filters = (flt('equipment', 'Оборудование') + flt('room', 'Лаборатории') +
                   flt('specialist', 'Специалисты') + flt('service', 'Услуги') +
                   flt('busy', 'Только с бронями') +
                   '<span class="hint">· клик по пустому = создать · тянуть = двигать · края = длительность · 2× клик = удалить · клик по брони = открыть</span>')

        legend = ''.join(f'<span><i style="background:{GANTT_COLORS[t]}"></i>{GANTT_LABELS[t]}</span>'
                         for t in GANTT_COLORS)
        star = ('<svg class="star" viewBox="0 0 40 40" width="20" height="20" aria-hidden="true">'
                '<g transform="rotate(-28 20 20)"><ellipse cx="20" cy="20" rx="11.5" ry="4.6" fill="none" '
                'stroke="#cfe0f0" stroke-width="1.7" opacity=".5"/><path d="M20 16.4 L17.6 3 L22.4 3 Z" fill="#CBA968"/>'
                '<path d="M20 23.6 L17.6 37 L22.4 37 Z" fill="#CBA968"/><circle cx="20" cy="20" r="3.6" fill="#fff"/></g></svg>')

        html = (
            '<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>Планировщик · ПУЛЬСАР</title><style>' + GANTT_CSS + '</style></head>'
            f'<body data-api="{api_url}" data-csrf="{get_token(request)}">'
            '<div class="top"><span class="brand">' + star + 'ПУЛЬСАР<b>планировщик</b></span>'
            f'<span class="sp"></span><a href="{base}?list=1">☰ список записей</a>'
            f'<a href="{reverse("admin:index")}">админка</a>'
            f'<span class="sp"></span><a href="{base}?type={rtype}&days=7">7 дней</a>'
            f'<a href="{base}?type={rtype}&days=14">14</a><a href="{base}?type={rtype}&days=30">30</a></div>'
            '<h1>Календарь занятости</h1>'
            '<div class="sub">Шкала дня 8:00–20:00, шаг 30 мин · наложения блокируются автоматически.</div>'
            '<div class="filters">' + filters + '</div>'
            '<div class="wrap"><table><thead><tr>' + head + '</tr></thead><tbody>' + rows +
            '</tbody></table></div>'
            '<div class="legend">' + legend + '</div>'
            '<div id="toast"></div>'
            '<script>' + GANTT_JS + '</script>'
            '</body></html>')
        return HttpResponse(html)
