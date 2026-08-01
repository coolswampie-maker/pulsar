"""Проверка заявки на формальные отказы.

Почему это не языковая модель. Формальный отказ — это арифметика: срок
прошёл или не прошёл, сумма выше лимита или нет. У такой проверки должен
быть один ответ, одинаковый при каждом запуске, и его нужно уметь
предъявить: «смета выше лимита на 340 000 ₽» проверяется вычитанием.
Модель на тех же данных может ответить по-разному, а объяснение придумать.

Три состояния, а не два. Между «всё в порядке» и «откажут» есть большая
область «мы не знаем»: резидент не указал численность, не заполнил ОКВЭД,
у программы не задан лимит. Это не нарушение. Записать незаполненное поле
в отказ — худшее, что можно сделать: человек бросит подавать заявку,
которую бы прошёл.

Формулировки — человеческие. «Смета превышает лимит на 340 тыс. ₽»,
а не «нарушение п. 4.2.1»: у резидента нет под рукой положения о конкурсе,
а действие ему нужно понятное.
"""
from datetime import date

from .models import PROFILE_STAGES, Program

OK = 'ok'        # проверено, всё в порядке
WARN = 'warn'    # стоит посмотреть: данных нет или до границы близко
STOP = 'stop'    # данные есть, и они не проходят

_STAGE_LABEL = dict(PROFILE_STAGES)

# За сколько дней до конца приёма пора торопиться. Не «отказ» — но заявку
# такого объёма за неделю не собирают, и об этом честнее сказать заранее.
SOON_DAYS = 14


def _rub(n):
    """Сумма человеческим языком: в заявках счёт идёт на сотни тысяч.

    Миллионы называем миллионами: «3 989 тыс. ₽» формально верно, но такую
    сумму приходится пересчитывать в уме — а её читают, чтобы принять решение.
    До ста тысяч показываем точно: там важен каждый рубль.
    """
    n = int(n)
    if n >= 1_000_000:
        s = f'{n / 1_000_000:.2f}'.rstrip('0').rstrip('.')
        return s.replace('.', ',') + ' млн ₽'
    if n >= 100_000:
        return f'{round(n / 1000):,}'.replace(',', ' ') + ' тыс. ₽'
    return f'{n:,}'.replace(',', ' ') + ' ₽'


def _months_between(start, end):
    m = (end.year - start.year) * 12 + (end.month - start.month)
    return m - 1 if end.day < start.day else m


def _item(level, text, fix=''):
    return {'level': level, 'text': text, 'fix': fix}


# --- отдельные правила -----------------------------------------------------
# Каждое возвращает пункт или None (нечего сказать — программа не ограничивает).

def _check_dates(program, today):
    if program.opens_at and today < program.opens_at:
        return _item(WARN, f'Приём заявок откроется {program.opens_at:%d.%m.%Y}.',
                     'Пока можно готовить документы.')
    if not program.deadline:
        return None
    left = (program.deadline - today).days
    if left < 0:
        return _item(STOP, f'Приём заявок закончился {program.deadline:%d.%m.%Y}.',
                     'Дождитесь следующей волны — параметры обычно повторяются.')
    if left == 0:
        return _item(WARN, 'Сегодня последний день приёма заявок.')
    if left <= SOON_DAYS:
        return _item(WARN, f'До конца приёма {left} дн. ({program.deadline:%d.%m.%Y}).',
                     'Проверьте, что подписант на месте: это чаще всего и срывает срок.')
    return _item(OK, f'Приём заявок открыт до {program.deadline:%d.%m.%Y}.')


def _check_age(program, company, today):
    if program.min_age_months is None and program.max_age_months is None:
        return None
    if not company.founded:
        return _item(WARN, 'Не указана дата регистрации компании — возраст не проверить.',
                     'Заполните её в кабинете: программа ограничивает возраст заявителя.')
    age = _months_between(company.founded, today)
    if program.max_age_months is not None and age > program.max_age_months:
        return _item(STOP,
                     f'Компании {age} мес., программа принимает не старше '
                     f'{program.max_age_months} мес.',
                     'Это ограничение обойти нельзя — посмотрите программы без верхней '
                     'границы возраста.')
    if program.min_age_months is not None and age < program.min_age_months:
        return _item(STOP,
                     f'Компании {age} мес., программа принимает не моложе '
                     f'{program.min_age_months} мес.',
                     f'Подать можно будет через {program.min_age_months - age} мес.')
    return _item(OK, f'Возраст компании — {age} мес., в границах программы.')


def _check_staff(program, company):
    if program.max_staff is None:
        return None
    if company.staff is None:
        return _item(WARN, 'Не указана численность сотрудников.',
                     f'Программа принимает компании не более {program.max_staff} чел.')
    if company.staff > program.max_staff:
        return _item(STOP, f'Сотрудников {company.staff}, предел программы — '
                           f'{program.max_staff}.')
    return _item(OK, f'Численность {company.staff} чел. — в пределах программы.')


def _check_revenue(program, company):
    if program.max_revenue is None:
        return None
    if company.revenue is None:
        return _item(WARN, 'Не указана выручка за прошлый год.',
                     f'Программа принимает компании с выручкой до '
                     f'{_rub(program.max_revenue)}.')
    if company.revenue > program.max_revenue:
        return _item(STOP,
                     f'Выручка {_rub(company.revenue)} — выше предела программы '
                     f'({_rub(program.max_revenue)}).')
    return _item(OK, f'Выручка {_rub(company.revenue)} — в пределах программы.')


def _check_okved(program, company):
    codes = program.okved_list()
    if not codes:
        return None
    if not company.okved.strip():
        return _item(WARN, 'Не указан ОКВЭД.',
                     'Программа принимает заявки по кодам: ' + ', '.join(codes) + '.')
    ours = [c.strip() for c in company.okved.split(',') if c.strip()]
    # Сравниваем по началу кода: в положениях пишут «класс 72», а у компании
    # стоит «72.19». Обратное тоже бывает — программа называет подгруппу,
    # а у компании класс, — поэтому проверяем совпадение в обе стороны.
    hit = next((o for o in ours for c in codes
                if o.startswith(c) or c.startswith(o)), None)
    if hit:
        return _item(OK, f'ОКВЭД {hit} подходит программе.')
    return _item(STOP, 'Ни один из ваших ОКВЭД (' + ', '.join(ours) +
                 ') не входит в перечень программы (' + ', '.join(codes) + ').',
                 'Если деятельность фактически ведётся — код добавляется в ЕГРЮЛ '
                 'заявлением, это делается до подачи.')


def _check_stage(program, profile):
    allowed = program.stage_list()
    if not allowed:
        return None
    names = ', '.join(_STAGE_LABEL.get(s, s).lower() for s in allowed)
    if not profile or not profile.stage:
        return _item(WARN, 'В профиле проекта не указана стадия.',
                     f'Программа принимает проекты на стадии: {names}.')
    if profile.stage not in allowed:
        return _item(STOP,
                     f'Стадия проекта — «{_STAGE_LABEL.get(profile.stage, profile.stage)}», '
                     f'программа принимает: {names}.')
    return _item(OK, f'Стадия «{_STAGE_LABEL.get(profile.stage, profile.stage)}» '
                     'подходит программе.')


def _check_budget(program, budget_total):
    """Здесь смета встречается с лимитом программы."""
    if program.max_grant is None:
        return None
    if not budget_total:
        return _item(WARN, 'Смета пустая — сумму заявки не с чем сравнить.',
                     f'Предел гранта по программе — {_rub(program.max_grant)}. '
                     'Добавьте позиции каталога в смету.')
    if budget_total > program.max_grant:
        over = budget_total - program.max_grant
        return _item(STOP,
                     f'Смета {_rub(budget_total)} превышает предел гранта '
                     f'({_rub(program.max_grant)}) на {_rub(over)}.',
                     'Уберите позиции из сметы или заложите разницу в софинансирование.')
    left = program.max_grant - budget_total
    return _item(OK, f'Смета {_rub(budget_total)} — в пределах гранта '
                     f'(остаётся {_rub(left)}).')


def _check_cofinancing(program, budget_total):
    if not program.cofinancing_pct:
        return None
    need = round((budget_total or 0) * program.cofinancing_pct / 100)
    if not budget_total:
        return _item(WARN, f'Программа требует софинансирование '
                           f'{program.cofinancing_pct}% от суммы гранта.',
                     'Точную сумму посчитаем, когда появится смета.')
    return _item(WARN,
                 f'Нужно софинансирование {program.cofinancing_pct}% — '
                 f'это {_rub(need)} собственных или привлечённых средств.',
                 'Подтверждается письмом инвестора или выпиской; проверьте заранее.')


def check_profile_ready(profile):
    """Заявку не примут без описания проекта — это тоже формальное основание.

    Отдельно от программ, а не пунктом в каждой карточке: пробел в профиле
    относится к заявителю, а не к конкретному конкурсу. Повторённый в каждой
    карточке, он тонул бы среди условий программ, и одно и то же читалось бы
    по три раза.
    """
    if profile is None:
        return _item(STOP, 'Профиль проекта не заполнен.',
                     'Заполните его в кабинете — из него собираются разделы заявки.')
    if not profile.core_ready:
        from .models import PROFILE_CORE, PROFILE_LABELS
        gaps = [PROFILE_LABELS[k].lower() for k in profile.missing(PROFILE_CORE)]
        return _item(WARN, 'В профиле проекта не хватает: ' + ', '.join(gaps) + '.',
                     'Без этих полей разделы заявки собрать не из чего.')
    return _item(OK, 'Профиль проекта заполнен — разделы заявки есть из чего собрать.')


# --- сборка ----------------------------------------------------------------

def check_program(program, company, profile, budget_total=0, today=None):
    """Проверяет одну программу. Возвращает пункты и общий вывод."""
    today = today or date.today()
    checks = [
        _check_dates(program, today),
        _check_stage(program, profile),
        _check_age(program, company, today),
        _check_staff(program, company),
        _check_revenue(program, company),
        _check_okved(program, company),
        _check_budget(program, budget_total),
        _check_cofinancing(program, budget_total),
    ]
    items = [c for c in checks if c]
    # Итог — по худшему пункту: одного формального несоответствия достаточно,
    # чтобы заявку не приняли, сколько бы пунктов ни было в порядке.
    if any(i['level'] == STOP for i in items):
        verdict = STOP
    elif any(i['level'] == WARN for i in items):
        verdict = WARN
    else:
        verdict = OK
    return {
        'id': program.id,
        'name': program.name,
        'fund': program.fund,
        'url': program.url,
        'deadline': program.deadline.isoformat() if program.deadline else None,
        'maxGrant': program.max_grant,
        'notes': program.notes,
        'verdict': verdict,
        'stop': [i for i in items if i['level'] == STOP],
        'warn': [i for i in items if i['level'] == WARN],
        'ok': [i for i in items if i['level'] == OK],
    }


def check_all(company, profile, budget_total=0, today=None):
    """Все показываемые программы, сначала проходимые."""
    order = {OK: 0, WARN: 1, STOP: 2}
    res = [check_program(p, company, profile, budget_total, today)
           for p in Program.objects.filter(active=True)]
    res.sort(key=lambda r: (order[r['verdict']], r['deadline'] or '9999'))
    return res
