# ПУЛЬСАР — бэкенд (изнанка): Django + DRF + Postgres

Скелет реального back-office для платформы: **CRM под брони** и **карточка ввода
оборудования** (через админку Django) + **API** для фронтенда.

> Ветка `backend`. Демо-фронт на `pulsar.zimermans.ru` (ветка `main`) не зависит от бэкенда
> и продолжает работать как есть. Подключение фронта к API — отдельный шаг (см. ниже).

## Что уже есть
- **Модели** (`booking/models.py`): `Resource` (лаборатория/прибор/специалист/услуга),
  `Order` (заявка) + `BookingLine` (позиции), `BusySlot` (общий календарь занятости).
  Зеркалят структуру `data/resources.js`.
- **Админка = CRM оператора** (`booking/admin.py`):
  - *Каталог ресурсов* — карточка ввода/редактирования оборудования и лабораторий.
  - *Заявки* — статусы (Новая/Подтверждена/Отклонена), состав, контакты; действие
    «Подтвердить» автоматически заносит слоты в общий календарь занятости.
  - *Календарь занятости*.
- **API** (`booking/urls.py`, DRF):
  - `GET  /api/resources/?type=equipment` — каталог (формат близок к фронту).
  - `GET  /api/resources/<slug>/` — карточка.
  - `GET  /api/resources/<slug>/busy/` — занятые слоты.
  - `POST /api/orders/` — приём заявки из корзины `{contact, resident, lines[]}`.

## Запуск локально (за 5 минут)
```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # можно оставить как есть — заведётся SQLite
python manage.py makemigrations booking
python manage.py migrate
python manage.py seed_demo      # немного демо-ресурсов
python manage.py createsuperuser
python manage.py runserver
```
- Админка (изнанка): http://127.0.0.1:8000/admin/
- API: http://127.0.0.1:8000/api/resources/

## Прод в РФ (152-ФЗ: персональные данные хранятся в России)
1. **Postgres в РФ** — Yandex Cloud Managed PostgreSQL / Timeweb / Selectel.
   В `.env`: `DATABASE_URL=postgres://user:pass@host:5432/db`.
2. **Сервер** — VPS в РФ (Timeweb/Yandex Cloud): `gunicorn config.wsgi` за nginx,
   `python manage.py collectstatic`, `DEBUG=0`, `ALLOWED_HOSTS=api.zimermans.ru`.
3. Домен под API, напр. `api.zimermans.ru` (или `pulsar-api.zimermans.ru`) — CNAME/A на сервер.
4. `CORS_ALLOWED_ORIGINS=https://pulsar.zimermans.ru` — чтобы фронт мог обращаться.

## Как подключить существующий фронт к этому API
Фронт уже готов: вся работа с данными — в `js/api.js` и `js/store.js`.
Нужно поменять только их «внутренности»:
- `P.getResources()` → `fetch(API + '/resources/')`
- `P.getBusy(id)` → `fetch(API + '/resources/'+id+'/busy/')`
- `Cart.checkout()` → `fetch(API + '/orders/', {method:'POST', body: JSON.stringify(...)})`
Разметка и логика UI не меняются. Сделаем отдельным коммитом, когда бэкенд поднимется.

## Дальше по плану
- Импорт полного каталога из `data/resources.js` (скрипт-конвертер JS→фиктуры).
- Роли (оператор/админ), уведомления по email при новой заявке.
- Проверка конфликтов слотов на сервере (сейчас — на фронте).
