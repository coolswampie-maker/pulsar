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
                     'Ждите следующего набора — условия обычно те же.')
    if left == 0:
        return _item(WARN, 'Сегодня последний день приёма заявок.')
    if left <= SOON_DAYS:
        return _item(WARN, f'До конца приёма {left} дн. ({program.deadline:%d.%m.%Y}).',
                     'Проверьте, что руководитель на месте и сможет подписать — '
                     'чаще всего срок срывается именно из-за этого.')
    return _item(OK, f'Приём заявок открыт до {program.deadline:%d.%m.%Y}.')


def _check_age(program, company, today):
    if program.min_age_months is None and program.max_age_months is None:
        return None
    if not company.founded:
        return _item(WARN, 'Не указана дата регистрации компании.',
                     'Программа ограничивает возраст заявителя — заполните дату '
                     'на вкладке «Профиль».')
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
                     f'Программа берёт компании до {program.max_staff} чел. — '
                     'укажите на вкладке «Профиль».')
    if company.staff > program.max_staff:
        return _item(STOP, f'У вас {company.staff} сотрудников, программа берёт '
                           f'не больше {program.max_staff}.')
    return _item(OK, f'Численность {company.staff} чел. — в пределах программы.')


def _check_revenue(program, company):
    if program.max_revenue is None:
        return None
    if company.revenue is None:
        return _item(WARN, 'Не указана выручка за прошлый год.',
                     f'Программа берёт компании с выручкой до '
                     f'{_rub(program.max_revenue)} — укажите на вкладке «Профиль».')
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
                     'Программа принимает коды ' + ', '.join(codes) +
                     ' — укажите свои на вкладке «Профиль».')
    ours = [c.strip() for c in company.okved.split(',') if c.strip()]
    # Сравниваем по началу кода: в положениях пишут «класс 72», а у компании
    # стоит «72.19». Обратное тоже бывает — программа называет подгруппу,
    # а у компании класс, — поэтому проверяем совпадение в обе стороны.
    hit = next((o for o in ours for c in codes
                if o.startswith(c) or c.startswith(o)), None)
    if hit:
        return _item(OK, f'ОКВЭД {hit} подходит программе.')
    return _item(STOP, 'Ваши ОКВЭД (' + ', '.join(ours) +
                 ') не подходят: программа принимает ' + ', '.join(codes) + '.',
                 'Если вы фактически этим занимаетесь, нужный код можно добавить '
                 'в ЕГРЮЛ заявлением — успеть надо до подачи.')


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
        return _item(WARN, 'Смета пустая — сравнивать не с чем.',
                     f'Программа даёт до {_rub(program.max_grant)}. '
                     'Добавьте позиции в смету выше.')
    if budget_total > program.max_grant:
        over = budget_total - program.max_grant
        return _item(STOP,
                     f'Смета {_rub(budget_total)} — это на {_rub(over)} больше, '
                     f'чем даёт программа ({_rub(program.max_grant)}).',
                     'Уберите что-нибудь из сметы или доложите разницу своими '
                     'средствами.')
    left = program.max_grant - budget_total
    return _item(OK, f'Смета {_rub(budget_total)} — укладывается в грант, '
                     f'остаётся ещё {_rub(left)}.')


def _check_cofinancing(program, budget_total):
    if not program.cofinancing_pct:
        return None
    need = round((budget_total or 0) * program.cofinancing_pct / 100)
    if not budget_total:
        return _item(WARN, f'Часть расходов ({program.cofinancing_pct}%) '
                           'программа требует покрыть своими средствами.',
                     'Сколько именно — посчитаем, когда появится смета.')
    return _item(WARN,
                 f'Помимо гранта нужно вложить свои {_rub(need)} '
                 f'({program.cofinancing_pct}% от сметы).',
                 'Это подтверждают выпиской со счёта или письмом инвестора — '
                 'подготовьте заранее.')


def check_profile_ready(profile):
    """Заполненность профиля — отдельно от программ.

    Пробел в профиле относится к заявителю, а не к конкретному конкурсу.
    Повторённый в каждой карточке, он тонул бы среди условий программ.

    Считаем поля, а не перечисляем их: подписи полей — это вопросы интервью
    («какую задачу решаете», «как решаете и в чём новизна»), и семь таких
    вопросов подряд через запятую читаются как каша. Что именно не заполнено,
    видно на самой вкладке «Проект».

    Всегда «стоит посмотреть», никогда не «отклонят»: профиль резидент
    дозаполняет за вечер, это не приговор заявке.
    """
    from .models import PROFILE_CORE

    total = len(PROFILE_CORE)
    done = 0 if profile is None else total - len(profile.missing(PROFILE_CORE))
    if done >= total:
        return _item(OK, 'Профиль проекта заполнен.')
    if done == 0:
        return _item(WARN, 'Профиль проекта пока пустой.',
                     'Без него заявку не собрать.')
    return _item(WARN, f'В профиле проекта заполнено {done} из {total} '
                       'основных полей.',
                 'Оставшиеся нужны, чтобы собрать разделы заявки.')


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
