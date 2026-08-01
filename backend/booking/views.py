import threading

from django.contrib.auth import authenticate
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.response import Response
from rest_framework.views import APIView

from . import formal, querylog
from . import review as reviewer
from .assist import assist
from . import compose as composer
from .compose import FORMATS, missing_for
from .models import (KPI_KEYS, MAX_BUDGET_QTY, PROFILE_LABELS, BusySlot,
                     CustomRequest, Kpi,
                     ComposeJob, KpiEntry, Order, ProjectProfile, Resource,
                     profile_field_spec)
from .serializers import (BudgetLineSerializer, CompanySerializer,
                          CustomRequestSerializer,
                          KpiEntrySerializer, KpiSerializer,
                          OrderCreateSerializer, OrderListSerializer,
                          ProjectProfileSerializer, RegisterSerializer,
                          ResourceSerializer)


def _auth_payload(company):
    token, _ = Token.objects.get_or_create(user=company.user)
    return {'token': token.key, 'company': CompanySerializer(company).data}


# ---------- каталог ----------
class ResourceViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/resources/ и /api/resources/<slug>/ — каталог для фронта."""
    queryset = Resource.objects.filter(is_active=True)
    serializer_class = ResourceSerializer
    lookup_field = 'slug'
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = super().get_queryset()
        t = self.request.query_params.get('type')
        return qs.filter(type=t) if t else qs

    @action(detail=True, methods=['get'])
    def busy(self, request, slug=None):
        """GET /api/resources/<slug>/busy/ — занятые слоты (общий календарь)."""
        slots = BusySlot.objects.filter(resource_id=slug).values('date', 'slot_start', 'slot_end')
        return Response([
            {'date': str(s['date']),
             'slotStart': s['slot_start'].strftime('%H:%M') if s['slot_start'] else None,
             'slotEnd': s['slot_end'].strftime('%H:%M') if s['slot_end'] else None}
            for s in slots])


class AllBusyView(APIView):
    """GET /api/busy/ — вся занятость по всем ресурсам: {slug: [{date, slotStart, slotEnd}]}.
    Фронт забирает один раз при загрузке, чтобы показывать доступность в каталоге и календаре."""
    permission_classes = [AllowAny]

    def get(self, request):
        out = {}
        for s in BusySlot.objects.values('resource_id', 'date', 'slot_start', 'slot_end'):
            out.setdefault(s['resource_id'], []).append({
                'date': str(s['date']),
                'slotStart': s['slot_start'].strftime('%H:%M') if s['slot_start'] else None,
                'slotEnd': s['slot_end'].strftime('%H:%M') if s['slot_end'] else None,
            })
        return Response(out)


# UserRateThrottle, а не AnonRateThrottle: у последнего get_cache_key
# возвращает None для вошедших, то есть авторизованные запросы не
# ограничиваются вовсе. Сборка документа доступна только вошедшим, поэтому
# её лимит не срабатывал никогда — самый дорогой вызов модели оставался без
# потолка. UserRateThrottle считает по пользователю, а гостей — по адресу.
class AssistThrottle(UserRateThrottle):
    scope = 'assist'


class ComposeThrottle(UserRateThrottle):
    """Сборка документа — самый дорогой вызов модели на платформе:
    длинный ответ и объёмный профиль на входе."""
    scope = 'compose'


class SignupThrottle(AnonRateThrottle):
    """Ограничение на регистрацию и вход.

    Регистрация не была ограничена ничем. Это обходило все остальные лимиты
    разом: они считаются на пользователя, а завести нового — один запрос.
    Каждая новая учётка получала свою квоту платных обращений к модели, и
    заодно CRM засорялась мусорными компаниями.

    Считаем по адресу (AnonRateThrottle): регистрируется тот, у кого учётки
    ещё нет, по пользователю тут считать нечего.
    """
    scope = 'signup'


class CustomRequestThrottle(UserRateThrottle):
    """Отдельный лимит для индивидуальных заявок.

    Раньше форма делила лимит с подбором — и человек, перебравший несколько
    формулировок в подборе, упирался в отказ ровно на той форме, к которой
    подбор его и отправлял. Заявка — редкое действие, ей нужен свой запас.
    """
    scope = 'custom_request'


class AssistView(APIView):
    """POST /api/assist/ — подбор позиций по задаче, описанной словами.

    Принимает {"query": "нужно определить примеси в субстанции"} и возвращает
    до четырёх позиций каталога с коротким обоснованием. Поле "mode" говорит,
    чем подобрано: "ai" — моделью, "local" — встроенным алгоритмом (модель не
    настроена или недоступна). Позиции всегда реальные: идентификаторы от
    модели сверяются с каталогом, несуществующие отбрасываются.
    """
    permission_classes = [AllowAny]
    throttle_classes = [AssistThrottle]

    def post(self, request):
        query = request.data.get('query') if isinstance(request.data, dict) else None
        query = (query or '').strip()
        if not query:
            return Response({'detail': 'Опишите задачу.'}, status=400)

        resources = list(Resource.objects.filter(is_active=True))
        picked, mode, reply = assist(query, resources)
        # запись в журнал не должна влиять на ответ — внутри всё погашено
        querylog.record(query, mode, len(picked))
        return Response({
            'mode': mode,
            'reply': reply,
            'items': [{
                'id': r.slug,
                'type': r.type,
                'title': r.title,
                'lab': r.lab,
                'priceValue': r.price_value,
                'priceUnit': r.price_unit,
                'why': why,
            } for r, why in picked],
        })


# ---------- заявки ----------
class OrderViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """POST /api/orders/ — оформить заявку. GET /api/orders/ — заявки своей компании."""
    queryset = Order.objects.all()
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        return OrderListSerializer if self.action == 'list' else OrderCreateSerializer

    def get_queryset(self):
        company = getattr(self.request.user, 'company', None)
        if company:
            return (Order.objects.filter(company=company)
                    .prefetch_related('lines__resource').order_by('-created_at'))
        return Order.objects.none()

    def list(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({'detail': 'Требуется вход.'}, status=401)
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        ser = OrderCreateSerializer(data=request.data, context={'request': request})
        ser.is_valid(raise_exception=True)
        order = ser.save()
        # Отдаём итоговые суммы: скидку резидента считает сервер, поэтому экран
        # подтверждения должен показывать её цифры, а не расчёт корзины.
        return Response({'ok': True, 'id': order.number,
                         'subtotal': order.subtotal, 'discount': order.discount,
                         'total': order.total, 'resident': order.resident,
                         'status': order.status}, status=201)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """POST /api/orders/<id>/cancel/ — компания отменяет свою новую заявку."""
        if not request.user.is_authenticated:
            return Response({'detail': 'Требуется вход.'}, status=401)
        order = self.get_queryset().filter(pk=pk).first()
        if not order:
            return Response({'detail': 'Заявка не найдена.'}, status=404)
        if order.status != 'new':
            return Response({'detail': 'Отменить можно только новую заявку.'}, status=400)
        order.delete()
        return Response({'ok': True})

    @action(detail=True, methods=['post'], url_path='request-change')
    def request_change(self, request, pk=None):
        """POST /api/orders/<id>/request-change/ — компания просит оператора изменить даты/время."""
        if not request.user.is_authenticated:
            return Response({'detail': 'Требуется вход.'}, status=401)
        order = self.get_queryset().filter(pk=pk).first()
        if not order:
            return Response({'detail': 'Заявка не найдена.'}, status=404)
        msg = (request.data.get('message') or '').strip()
        if not msg:
            return Response({'detail': 'Опишите, что изменить.'}, status=400)
        order.change_request = msg
        order.save(update_fields=['change_request'])
        return Response({'ok': True, 'changeRequest': msg})


class CustomRequestView(APIView):
    """POST /api/custom-request/ — индивидуальная заявка на подбор.

    Клиент ничего не нашёл в каталоге и описывает потребность словами.
    Гость указывает контакты сам; у вошедшей компании они берутся из профиля.
    Форма публичная, поэтому частота ограничена — но своим счётчиком.
    """
    permission_classes = [AllowAny]
    throttle_classes = [CustomRequestThrottle]

    def post(self, request):
        ser = CustomRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        company = getattr(getattr(request, 'user', None), 'company', None)
        if company:
            org = company.name
            contact = company.contact_name
            email = company.user.email
            phone = company.phone
        else:
            org = (d.get('org') or '').strip()
            contact = (d.get('contact_name') or '').strip()
            email = (d.get('email') or '').strip()
            phone = (d.get('phone') or '').strip()
            if not contact or not (email or phone):
                return Response(
                    {'detail': 'Укажите контактное лицо и e-mail или телефон — '
                               'иначе мы не сможем ответить.'}, status=400)

        req = CustomRequest.objects.create(
            company=company, org=org, contact_name=contact, email=email, phone=phone,
            need=d['need'], period=(d.get('period') or '').strip()[:200],
            search_query=(d.get('search_query') or '').strip()[:300])
        return Response({'ok': True, 'id': req.number}, status=201)


# ---------- авторизация компании ----------
class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [SignupThrottle]

    def post(self, request):
        ser = RegisterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        company = ser.save()
        return Response(_auth_payload(company), status=201)


class LoginView(APIView):
    permission_classes = [AllowAny]
    # тот же счётчик: без него пароль можно подбирать перебором
    throttle_classes = [SignupThrottle]

    def post(self, request):
        user = authenticate(username=request.data.get('email'), password=request.data.get('password'))
        if user is None or not hasattr(user, 'company'):
            return Response({'detail': 'Неверный e-mail или пароль.'}, status=400)
        return Response(_auth_payload(user.company))


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def _company(self, request):
        return getattr(request.user, 'company', None)

    def get(self, request):
        company = self._company(request)
        if not company:
            return Response({'detail': 'Нет профиля компании.'}, status=404)
        return Response(CompanySerializer(company).data)

    def patch(self, request):
        company = self._company(request)
        if not company:
            return Response({'detail': 'Нет профиля компании.'}, status=404)
        ser = CompanySerializer(company, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


# ---------- показатели (KPI по методологии) ----------
def _company(request):
    return getattr(request.user, 'company', None)


def _kpi_year(request):
    try:
        y = int(request.query_params.get('year') or 0)
    except (TypeError, ValueError):
        y = 0
    return y or timezone.localdate().year


class KpiView(APIView):
    """GET /api/kpi/?year= — 6 показателей компании за год (автосоздание)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = _company(request)
        if not company:
            return Response({'detail': 'Нет профиля компании.'}, status=404)
        year = _kpi_year(request)
        existing = {k.key: k for k in company.kpis.filter(year=year)}
        for key in KPI_KEYS:
            if key not in existing:
                existing[key] = Kpi.objects.create(company=company, year=year, key=key)
        items = [existing[key] for key in KPI_KEYS]
        return Response({'year': year, 'items': KpiSerializer(items, many=True, context={'request': request}).data})


def _extract_from_pdf(f):
    """Эвристика: заголовок + первое денежное число из PDF. Умное распознавание —
    LLM (Qwen) на Yandex Cloud. Возвращает (title, amount)."""
    import io
    import re
    title, amount = None, None
    try:
        data = f.read()
        f.seek(0)
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        text = '\n'.join((p.extract_text() or '') for p in reader.pages[:3])
        for line in text.splitlines():
            line = line.strip()
            if len(line) > 4:
                title = line[:120]
                break
        m = re.search(r'(\d[\d\s]{2,}(?:[.,]\d+)?)\s*(?:руб|₽|р\.)', text.replace('\xa0', ' '))
        if m:
            amount = m.group(1).replace(' ', '').replace(',', '.')
    except Exception:
        pass
    return title, amount


class KpiEntriesView(APIView):
    """POST /api/kpi/<key>/entries/?year= — добавить позицию (вручную, можно с документом)."""
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request, key):
        company = _company(request)
        if not company:
            return Response({'detail': 'Нет профиля компании.'}, status=404)
        if key not in KPI_KEYS:
            return Response({'detail': 'Неизвестный показатель.'}, status=404)
        year = _kpi_year(request)
        kpi, _ = Kpi.objects.get_or_create(company=company, year=year, key=key)
        ser = KpiEntrySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save(kpi=kpi, source='manual')
        return Response(ser.data, status=201)


class KpiEntryView(APIView):
    """DELETE /api/kpi/<key>/entries/<id>/ — удалить позицию."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, key, entry_id):
        company = _company(request)
        if not company:
            return Response({'detail': 'Нет профиля компании.'}, status=404)
        entry = KpiEntry.objects.filter(pk=entry_id, kpi__company=company, kpi__key=key).first()
        if not entry:
            return Response({'detail': 'Позиция не найдена.'}, status=404)
        entry.delete()
        return Response(status=204)


class KpiExtractView(APIView):
    """POST /api/kpi/<key>/extract/?year= — прикрепить документ, система заводит позицию.

    Разбор здесь простой: сумма и дата вылавливаются из имени файла и текста
    правилами, без модели. Обещание «умное распознавание подключается на
    деплое» из прежней версии этого комментария было неверным — никакого
    распознавания за кнопкой нет, и оператору стоит об этом знать.
    Что не распозналось, человек вписывает руками — форма это и предлагает.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, key):
        company = _company(request)
        if not company:
            return Response({'detail': 'Нет профиля компании.'}, status=404)
        if key not in KPI_KEYS:
            return Response({'detail': 'Неизвестный показатель.'}, status=404)
        f = request.FILES.get('document')
        if not f:
            return Response({'detail': 'Прикрепите файл.'}, status=400)
        # тот же фильтр форматов, что и при обычном добавлении позиции
        from rest_framework.exceptions import ValidationError as DRFValidationError

        from .serializers import validate_document
        try:
            validate_document(f)
        except DRFValidationError as e:
            return Response({'detail': ' '.join(map(str, e.detail))}, status=400)
        year = _kpi_year(request)
        kpi, _ = Kpi.objects.get_or_create(company=company, year=year, key=key)
        title, amount = _extract_from_pdf(f)
        entry = KpiEntry.objects.create(kpi=kpi, title=(title or f.name)[:300],
                                        amount=amount, document=f, source='auto')
        return Response(KpiEntrySerializer(entry).data, status=201)


# ---------- помощник резидента: профиль проекта и сборка документов ----------
def _profile_for(request, create=False):
    """Профиль своей компании.

    По умолчанию НЕ создаёт строку: читающий запрос не должен ничего писать
    в базу. Пустой профиль отдаётся несохранённым объектом, а появляется в
    базе при первом сохранении.
    """
    company = getattr(getattr(request, 'user', None), 'company', None)
    if not company:
        return None
    if create:
        profile, _ = ProjectProfile.objects.get_or_create(company=company)
        return profile
    return (ProjectProfile.objects.filter(company=company).first()
            or ProjectProfile(company=company))


def _profile_payload(profile):
    """Всё, что нужно вкладке «Проект», одним ответом.

    Следующий вопрос и готовность форматов считаются из уже загруженного
    объекта, без обращений к базе, — отдавать их отдельными запросами значит
    трижды ходить на сервер там, где хватает одного. На заполнение профиля
    из тринадцати вопросов это разница между 42 запросами и 14.
    """
    field, question = profile.next_question()
    spec = next((f for f in profile_field_spec() if f['key'] == field), None)
    return {
        **ProjectProfileSerializer(profile).data,
        'fields': profile_field_spec(),
        'next': {'field': field, 'question': question,
                 'label': PROFILE_LABELS.get(field) if field else None,
                 'kind': spec['kind'] if spec else None,
                 'options': spec['options'] if spec else None},
        'formats': [{'key': k, 'title': spec_['title'],
                     'ready': not missing_for(profile, k),
                     'missing': [PROFILE_LABELS[m] for m in missing_for(profile, k)]}
                    for k, spec_ in FORMATS.items()],
    }


class ProfileView(APIView):
    """GET/PATCH /api/profile/ — профиль проекта резидента.

    Все поля необязательные: профиль заполняется по частям, и незаполненное —
    это не ошибка, а повод спросить в нужный момент.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _profile_for(request)
        if not profile:
            return Response({'detail': 'Нет профиля компании.'}, status=403)
        return Response(_profile_payload(profile))

    def patch(self, request):
        if not _profile_for(request):
            return Response({'detail': 'Нет профиля компании.'}, status=403)
        profile = _profile_for(request, create=True)
        ser = ProjectProfileSerializer(profile, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(_profile_payload(profile))


class ProfileNextView(APIView):
    """GET /api/profile/next/ — следующий вопрос интервью.

    Анкету на тринадцать полей не заполняет никто, поэтому спрашиваем по
    одному: сначала ядро, потом остальное.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _profile_for(request)
        if not profile:
            return Response({'detail': 'Нет профиля компании.'}, status=403)
        field, question = profile.next_question()
        spec = next((f for f in profile_field_spec() if f['key'] == field), None)
        return Response({
            'field': field,
            'question': question,
            'label': PROFILE_LABELS.get(field) if field else None,
            # вид поля и варианты выбора решает сервер: он знает, какое поле
            # строковое, какое многострочное, а какое со списком
            'kind': spec['kind'] if spec else None,
            'options': spec['options'] if spec else None,
            'completeness': profile.completeness,
        })


def _job_payload(job):
    return {'jobId': job.pk, 'format': job.fmt, 'title': FORMATS[job.fmt]['title'],
            'status': job.status, 'mode': job.mode,
            'blocks': job.blocks, 'gaps': job.gaps,
            # сколько ждать — решает сервер: иначе при смене COMPOSE_TIMEOUT
            # клиент сдавался бы раньше, чем задание успевает завершиться
            'timeoutMs': int((settings.COMPOSE_TIMEOUT + 30) * 1000)}


class ComposeView(APIView):
    """POST /api/profile/compose/ — поставить сборку документа в очередь.

    Тело: {"format": "sections" | "teaser" | "onepager" | "deck"}
    Ответ приходит не сразу: обращение к модели длится до полуминуты, а
    Gunicorn работает синхронными процессами — держать процесс всё это время
    значит останавливать сайт для остальных. Возвращаем номер задания,
    клиент опрашивает его через ComposeJobView.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ComposeThrottle]

    def post(self, request):
        profile = _profile_for(request)
        if not profile:
            return Response({'detail': 'Нет профиля компании.'}, status=403)
        data = request.data if isinstance(request.data, dict) else {}
        fmt = (data.get('format') or '').strip()
        if fmt not in FORMATS:
            return Response({'detail': 'Неизвестный формат документа.'}, status=400)

        # Нехватку полей видно без модели — отвечаем сразу, не заводя задание.
        lack = missing_for(profile, fmt)
        if lack:
            # несохранённым объектом — чтобы ответ собирался тем же _job_payload
            # и не разъехался с настоящим при следующей правке
            return Response(_job_payload(ComposeJob(
                company=profile.company, fmt=fmt, status='done', mode='need',
                gaps=[PROFILE_LABELS[k] for k in lack])))

        # заодно подчищаем старые: задание читают один раз, через минуту после
        # создания. Так же сделана чистка журнала запросов — планировщика в
        # проекте нет, и заводить его ради этого незачем.
        ComposeJob.objects.filter(
            created_at__lt=timezone.now() - timedelta(days=1)).delete()
        job = ComposeJob.objects.create(company=profile.company, fmt=fmt)
        # через модуль, а не по имени: связанное при импорте имя нельзя
        # подменить в тестах, и поток запускался бы по-настоящему
        threading.Thread(target=composer.run_job, args=(job.pk,), daemon=True).start()
        return Response(_job_payload(job), status=202)


class ComposeJobView(APIView):
    """GET /api/profile/compose/<id>/ — статус и результат сборки."""
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        company = _company(request)
        if not company:
            return Response({'detail': 'Нет профиля компании.'}, status=403)
        # фильтр по своей компании — чужое задание не отдаём
        job = ComposeJob.objects.filter(pk=job_id, company=company).first()
        if not job:
            return Response({'detail': 'Задание не найдено.'}, status=404)
        if job.stale:
            # процесс перезапустили посреди работы — иначе «выполняется» навсегда
            job.status, job.mode = 'failed', 'offline'
            job.save(update_fields=['status', 'mode'])
        return Response(_job_payload(job))


class ComposeFormatsView(APIView):
    """GET /api/profile/formats/ — что умеет собирать помощник и чего для
    этого не хватает. Нужно, чтобы кнопки в кабинете были честными: видно
    сразу, какой документ сейчас собрать нельзя и почему."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _profile_for(request)
        if not profile:
            return Response({'detail': 'Нет профиля компании.'}, status=403)
        out = []
        for key, spec in FORMATS.items():
            lack = missing_for(profile, key)
            out.append({
                'key': key,
                'title': spec['title'],
                'ready': not lack,
                'missing': [PROFILE_LABELS[k] for k in lack],
            })
        return Response(out)


# ==========================================================================
#  СМЕТА ПРОЕКТА (функция 12) и ПРОВЕРКА НА ФОРМАЛЬНЫЕ ОТКАЗЫ (функция 9)
# ==========================================================================

def _budget_payload(profile):
    """Смета целиком. Итог считает сервер по сохранённым строкам."""
    if not profile.pk:
        return {'lines': [], 'total': 0}
    lines = list(profile.budget.select_related('resource'))
    return {
        'lines': BudgetLineSerializer(lines, many=True).data,
        'total': sum(l.total for l in lines),
    }


class BudgetView(APIView):
    """GET/POST /api/profile/budget/ — позиции каталога в смете заявки.

    Замысел функции: резидент приходит за помощью с заявкой, а уходит
    с бронированием. Смета — то самое звено: список реальных позиций
    каталога по реальным ценам, который идёт в заявку статьёй расходов,
    а после гранта превращается в бронь.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _profile_for(request)
        if not profile:
            return Response({'detail': 'Нет профиля компании.'}, status=403)
        return Response(_budget_payload(profile))

    def post(self, request):
        if not _profile_for(request):
            return Response({'detail': 'Нет профиля компании.'}, status=403)
        profile = _profile_for(request, create=True)
        ser = BudgetLineSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        res_id = ser.validated_data['resource_id']
        # Повторное добавление той же позиции — не вторая строка, а
        # увеличение количества: две одинаковые строки в смете читаются
        # как ошибка и их всё равно пришлось бы складывать вручную.
        line = profile.budget.filter(resource_id=res_id).first()
        if line:
            line.qty = min(line.qty + ser.validated_data.get('qty', 1), MAX_BUDGET_QTY)
            if ser.validated_data.get('note'):
                line.note = ser.validated_data['note']
            line.save()
        else:
            ser.save(profile=profile)
        return Response(_budget_payload(profile), status=201)


class BudgetLineView(APIView):
    """PATCH/DELETE /api/profile/budget/<id>/ — количество, пояснение, удаление."""
    permission_classes = [IsAuthenticated]

    def _line(self, request, line_id):
        profile = _profile_for(request)
        if not profile or not profile.pk:
            return None, None
        return profile, profile.budget.filter(pk=line_id).first()

    def patch(self, request, line_id):
        profile, line = self._line(request, line_id)
        if not line:
            return Response({'detail': 'Строка не найдена.'}, status=404)
        ser = BudgetLineSerializer(line, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(_budget_payload(profile))

    def delete(self, request, line_id):
        profile, line = self._line(request, line_id)
        if not line:
            return Response({'detail': 'Строка не найдена.'}, status=404)
        line.delete()
        return Response(_budget_payload(profile))


class ProgramsView(APIView):
    """GET /api/programs/ — программы поддержки и проверка на формальные отказы.

    Проверку делает код, а не модель: у формального требования один ответ,
    одинаковый при каждом запуске, и его нужно уметь предъявить.
    Подробности — в booking/formal.py.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = _company(request)
        if not company:
            return Response({'detail': 'Нет профиля компании.'}, status=403)
        profile = ProjectProfile.objects.filter(company=company).first()
        total = _budget_payload(profile)['total'] if profile else 0
        return Response({
            'budgetTotal': total,
            # Готовность профиля — про заявителя, а не про конкурс: один пункт
            # над списком, а не повтор в каждой карточке.
            'profile': formal.check_profile_ready(profile),
            'programs': formal.check_all(company, profile, total),
        })


class HealthView(APIView):
    """GET /api/health/ — жив ли сайт целиком, а не только веб-сервер.

    Внешний монитор, дёргающий главную страницу, видит только Nginx: тот
    отдаёт статику и когда Django лежит, и когда база недоступна. Сайт при
    этом не работает — каталог пуст, войти нельзя, — а монитор молчит.

    Поэтому проверяем то, без чего сайта нет: отвечает ли база и есть ли
    в ней каталог. Пустой каталог — это авария (не та база, не прошёл
    импорт), и внешне она выглядит как исправный сайт.

    Отвечает 200 или 503; подробности — в теле, но по коду ответа монитор
    поймёт всё и без чтения.
    """
    permission_classes = [AllowAny]
    authentication_classes = []      # монитор ходит без токена

    def get(self, request):
        checks, ok = {}, True
        try:
            n = Resource.objects.filter(is_active=True).count()
            checks['catalog'] = n
            if not n:
                checks['db'] = 'каталог пуст'
                ok = False
            else:
                checks['db'] = 'ok'
        except Exception as e:                       # noqa: BLE001
            # Текст исключения наружу не отдаём: в нём бывает строка
            # подключения к базе. Монитору хватит слова «недоступна».
            checks['db'] = 'недоступна'
            checks['error'] = type(e).__name__
            ok = False
        return Response({'status': 'ok' if ok else 'fail', **checks},
                        status=200 if ok else 503)


class BudgetReviewThrottle(UserRateThrottle):
    """Проверка сметы — обращение к модели с каталогом на входе.
    Дешевле сборки документа, но дороже подбора; и то и другое платное."""
    scope = 'review'


class BudgetReviewView(APIView):
    """POST /api/profile/budget/review/ — чего не хватает в смете.

    Советы — только позиции каталога: идентификаторы от модели сверяются
    с базой, всё остальное отбрасывается. Подробности — в booking/review.py.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [BudgetReviewThrottle]

    def post(self, request):
        profile = _profile_for(request)
        if not profile:
            return Response({'detail': 'Нет профиля компании.'}, status=403)
        lines = list(profile.budget.select_related('resource')) if profile.pk else []
        items, mode = reviewer.review(profile, lines)
        return Response({'mode': mode, 'items': items})
