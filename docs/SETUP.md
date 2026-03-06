# Полный гайд по настройке AkmalExpress

Этот гайд для запуска проекта с нуля на macOS/Linux.

## 1) Требования

- Python `3.11+` (рекомендуется `3.12`)
- `pip`
- `node` + `npm`
- (опционально) PostgreSQL

Проверка:

```bash
python3 --version
node -v
npm -v
```

## 2) Подготовка проекта

```bash
git clone <your-repo-url>
cd akmalexpress
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
```

## 3) Создание `.env`

```bash
cp .env.example .env
```

Далее выбери один режим БД.

## 4) Режим A: быстрый старт с SQLite (рекомендуется для теста)

В `.env`:

```env
DJANGO_DEBUG=1
DJANGO_SECRET_KEY=change-me-long-random-secret
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,0.0.0.0
DJANGO_ADMIN_URL=secure-admin/
DJANGO_STAFF_LOGIN_URL=staff-login/

DB_ENGINE=django.db.backends.sqlite3
DB_NAME=db.sqlite3
```

Применить миграции:

```bash
source .venv/bin/activate
set -a; source .env; set +a
python manage.py migrate
python manage.py createsuperuser
```

## 5) Режим B: PostgreSQL

Пример `.env`:

```env
DJANGO_DEBUG=1
DJANGO_SECRET_KEY=change-me-long-random-secret
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,0.0.0.0,192.168.1.50
DJANGO_ADMIN_URL=secure-admin/
DJANGO_STAFF_LOGIN_URL=staff-login/

DB_ENGINE=django.db.backends.postgresql_psycopg2
DB_NAME=AkmalExpress
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
```

Миграции и superuser:

```bash
source .venv/bin/activate
set -a; source .env; set +a
python manage.py migrate
python manage.py createsuperuser
```

## 6) Запуск проекта

Обычный локальный запуск:

```bash
source .venv/bin/activate
set -a; source .env; set +a
python manage.py runserver 127.0.0.1:8000
```

Доступ:

- Главная: `http://127.0.0.1:8000/`
- Служебный вход админов: `http://127.0.0.1:8000/<DJANGO_STAFF_LOGIN_URL>`
- Django admin superuser: `http://127.0.0.1:8000/<DJANGO_ADMIN_URL>`

Важно: `/admin/` отключен и отдает `404`.
Важно: `/login/` тоже скрыт и отдает `404`.

## 7) Запуск как сервер для телефона (LAN)

```bash
source .venv/bin/activate
set -a; source .env; set +a
./run_lan_server.sh 8000
```

Открой на телефоне URL вида:

`http://<ip_твоего_mac>:8000`

Условия:

- Mac и телефон в одной Wi‑Fi сети
- firewall не блокирует входящие на порт `8000`
- `DJANGO_ALLOWED_HOSTS` должен включать IP твоего Mac или `*` для локального теста

## 8) Сборка стилей (frontend)

Для production:

```bash
npm run build
```

Для разработки (watch):

```bash
npm run dev
```

## 9) Сброс данных (очистка)

```bash
source .venv/bin/activate
set -a; source .env; set +a
python manage.py flush --noinput
find media -mindepth 1 -delete 2>/dev/null || true
```

После этого база пустая, можно заново создавать пользователей/заказы.

## 10) Проверка, что все работает

```bash
source .venv/bin/activate
set -a; source .env; set +a
python manage.py check
python manage.py check --deploy
npm audit
```

## 11) Частые проблемы

`ModuleNotFoundError: No module named 'django'`:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

`OperationalError` по БД:

- проверь `DB_*` в `.env`
- проверь, что PostgreSQL запущен
- повтори `python manage.py migrate`

Админка не открывается:

- проверь `DJANGO_ADMIN_URL` в `.env`
- открывай именно этот путь, не `/admin/`

Вход админа не открывается:

- проверь `DJANGO_STAFF_LOGIN_URL` в `.env`
- открывай именно скрытый путь, не `/login/`

Телефон не открывает сайт:

- проверь одну сеть Wi‑Fi
- проверь IP из `run_lan_server.sh`
- временно поставь `DJANGO_ALLOWED_HOSTS=*` для теста
