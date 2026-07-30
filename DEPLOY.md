# Публикация ПУЛЬСАР на pulsar.jaglion.ru (VPS + Django + Nginx)

Эта версия — с бэкендом: фронт (сайт) + REST API + кабинет оператора (`/admin`) на
одном домене `pulsar.jaglion.ru`. Основной сайт `jaglion.ru` (Tilda) при этом не
трогаем — он продолжает работать через отдельную A-запись.

Готовые файлы конфигурации — в папке [`deploy/`](deploy/):
`nginx-pulsar.conf`, `gunicorn.service`. Переменные окружения — `backend/.env.example`.

Ниже `<ПУТЬ>` = `/srv/pulsar` (куда клонируем репозиторий на сервере).

---

## Этап 1. Подготовка (до смены DNS)

В Tilda в настройках домена `jaglion.ru` выпишите:
- **IP-адрес**, на который сейчас указывает `jaglion.ru` — понадобится, чтобы
  основной сайт не пропал после смены NS;
- все **TXT/MX** записи (почта, подтверждения владения), если они есть.

Ничего в коде для этого не нужно.

## Этап 2. Сервер (VPS)

После аренды VPS с Ubuntu и получения его IP:

```bash
# пакеты
sudo apt update && sudo apt install -y python3-venv python3-pip postgresql nginx git certbot python3-certbot-nginx

# база
sudo -u postgres psql -c "CREATE USER pulsar WITH PASSWORD 'СИЛЬНЫЙ_ПАРОЛЬ';"
sudo -u postgres psql -c "CREATE DATABASE pulsar OWNER pulsar;"

# код
sudo git clone https://github.com/coolswampie-maker/pulsar.git /srv/pulsar
cd /srv/pulsar && sudo git checkout backend

# окружение Django
cd /srv/pulsar/backend
sudo python3 -m venv .venv
sudo .venv/bin/pip install -r requirements.txt

# настройки: заполнить .env (см. backend/.env.example)
sudo cp .env.example .env && sudo nano .env
#   SECRET_KEY=...   DEBUG=0
#   ALLOWED_HOSTS=pulsar.jaglion.ru
#   DATABASE_URL=postgres://pulsar:СИЛЬНЫЙ_ПАРОЛЬ@127.0.0.1:5432/pulsar

# миграции, каталог, оператор, статика
sudo .venv/bin/python manage.py migrate
sudo .venv/bin/python manage.py import_catalog      # 35 позиций из booking/data/catalog.json
sudo .venv/bin/python manage.py createsuperuser     # логин в кабинет оператора
sudo .venv/bin/python manage.py collectstatic --noinput

# права на папки, которые отдаёт/пишет сервис
sudo chown -R www-data:www-data /srv/pulsar/backend/staticfiles /srv/pulsar/backend/media
```

**Gunicorn как сервис:**
```bash
sudo cp /srv/pulsar/deploy/gunicorn.service /etc/systemd/system/pulsar.service
sudo systemctl daemon-reload && sudo systemctl enable --now pulsar
sudo systemctl status pulsar        # active (running)
```

**Nginx:**
```bash
sudo cp /srv/pulsar/deploy/nginx-pulsar.conf /etc/nginx/sites-available/pulsar
sudo ln -s /etc/nginx/sites-available/pulsar /etc/nginx/sites-enabled/pulsar
sudo nginx -t && sudo systemctl reload nginx
```

## Этап 3. DNS (Reg.ru) — только когда сервер готов

В reg.ru у домена `jaglion.ru` смените NS-серверы с `ns1/ns2.tildadns.com`
на `ns1/ns2.hosting.reg.ru`. После появления управления зоной добавьте:

| Тип | Имя | Значение |
|-----|-----|----------|
| A | `@` | IP из Tilda (Этап 1) — сохраняет основной сайт |
| A | `www` | тот же IP из Tilda (если нужно) |
| A | `pulsar` | **IP вашего VPS** |
| TXT/MX | … | восстановить, если были в Tilda |

Распространение NS — до суток.

## Этап 4. HTTPS

Только после того как `pulsar.jaglion.ru` резолвится на IP VPS (проверьте
`dig pulsar.jaglion.ru`):
```bash
sudo certbot --nginx -d pulsar.jaglion.ru
```
Certbot допишет 443-блок, редирект с 80 и автопродление.

Путь отступления: если что-то с основным сайтом пойдёт не так — верните NS обратно
на `ns1/ns2.tildadns.com`, и через время всё восстановится.

---

## Обновление сайта в будущем
```bash
cd /srv/pulsar && sudo git pull
cd backend
sudo .venv/bin/pip install -r requirements.txt          # если менялись зависимости
sudo .venv/bin/python manage.py migrate                  # если менялись модели
sudo .venv/bin/python manage.py collectstatic --noinput  # если менялась статика Django
sudo systemctl restart pulsar
```
Изменения фронта (js/css/data в корне) подхватываются сразу — Nginx отдаёт файлы напрямую.

## Частые вопросы
- **Фронт и API на одном домене** → в `index.html` ничего не меняем: `PULSAR_API_BASE='/api'`
  и `/admin/` работают через Nginx как есть.
- **Не открывается кабинет оператора по HTTPS (ошибка CSRF)** → проверьте, что в `.env`
  указан `ALLOWED_HOSTS=pulsar.jaglion.ru`: домен автоматически попадает в
  `CSRF_TRUSTED_ORIGINS`.
- **Каталог пуст** → не выполнен `import_catalog`.
- **Заявки не сохраняются** → смотрите `journalctl -u pulsar -f` и `sudo nginx -t`.
