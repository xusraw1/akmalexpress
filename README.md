# AkmalExpress

Локальная CRM/панель для учета заказов карго: создание продукта, создание заказа, отслеживание статусов, управление модераторами и поиск по квитанции/трек-номеру.

Полная пошаговая настройка: [docs/SETUP.md](docs/SETUP.md)

## Что внутри

- Backend: `Django`
- Database: `PostgreSQL` (или `SQLite` через env)
- Forms: `django-crispy-forms` + `crispy-tailwind`
- UI: `Tailwind CSS` + `Flowbite`
- Адаптивный интерфейс (desktop/tablet/mobile)

## Основные возможности

- Создание продукта и заказа
- Изменение/удаление заказа (с проверкой прав)
- Статусы заказа: `Начат`, `В пути`, `Пришел`, `Отменен`
- Поиск заказов по:
  - квитанции
  - трек-номеру
  - имени/фамилии
  - названию продукта
- Пагинация списка заказов
- Логин/логаут
- Управление модераторами (для superuser)

## Роли и доступ

- `Гость`
  - главная и вход
- `Staff / Superuser`
  - создание продукта/заказа
  - список заказов
  - профиль
- `Superuser`
  - создание и активация/деактивация модераторов

## Маршруты

| URL | Назначение | Доступ |
|---|---|---|
| `/` | Главная + поиск | Все |
| `/login/` | Вход | Все |
| `/logout/` | Выход | Авторизованные |
| `/order/` | Список заказов | Staff/Superuser |
| `/order/<slug>/detail/` | Детали заказа | Все |
| `/order/<slug>/change/` | Изменить заказ | Staff/Superuser + владелец или superuser |
| `/order/<slug>/delete/` | Удалить заказ | Staff/Superuser + владелец или superuser |
| `/create/product/` | Создать продукт | Staff/Superuser |
| `/create/order/` | Создать заказ | Staff/Superuser |
| `/profile/<username>/` | Профиль | Staff/Superuser |
| `/create/admin/` | Управление модераторами | Superuser |

## Быстрый старт

### 1) Клонирование и переход

```bash
git clone <your-repo-url>
cd akmalexpress
```

### 2) Python-окружение

Рекомендуется Python `3.11` или `3.12`.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install django-crispy-forms crispy-tailwind
```

### 3) Конфигурация окружения (`.env`)

Можно взять шаблон:

```bash
cp .env.example .env
```

Минимум для локального запуска (PostgreSQL):

```bash
export DJANGO_DEBUG=1
export DJANGO_SECRET_KEY='change-me-long-random-secret'
export DJANGO_ALLOWED_HOSTS='127.0.0.1,localhost'
export DJANGO_ADMIN_URL='secure-admin/'
export DB_ENGINE='django.db.backends.postgresql_psycopg2'
export DB_NAME='AkmalExpress'
export DB_USER='postgres'
export DB_PASSWORD='your_db_password'
export DB_HOST='localhost'
export DB_PORT='5432'
```

Если хочешь быстро стартовать без PostgreSQL:

```bash
export DJANGO_DEBUG=1
export DB_ENGINE='django.db.backends.sqlite3'
```

Админка будет доступна не по `/admin/`, а по пути из `DJANGO_ADMIN_URL`.

### 4) Миграции

```bash
python manage.py migrate
```

### 5) Superuser (опционально)

```bash
python manage.py createsuperuser
```

### 6) Запуск

```bash
python manage.py runserver 127.0.0.1:8000
```

Открыть:

- http://127.0.0.1:8000/
- http://127.0.0.1:8000/login/
- http://127.0.0.1:8000/<DJANGO_ADMIN_URL>

### Запуск как локальный сервер для телефона/других устройств

В проекте есть готовый скрипт:

```bash
./run_lan_server.sh
```

Или с портом:

```bash
./run_lan_server.sh 8000
```

Скрипт запускает Django на `0.0.0.0` и показывает LAN-ссылку вида `http://<your-local-ip>:8000`.

## Frontend (Tailwind)

Установить зависимости:

```bash
npm install
```

Сборка стилей (production):

```bash
npm run build
```

Режим наблюдения (development):

```bash
npm run dev
```

Используемые файлы:

- `static/src/tailwind.css` — вход для Tailwind
- `static/output.css` — сгенерированный Tailwind CSS
- `static/css/main.css` — кастомный UI-слой (layout, компоненты, адаптив)

## Структура проекта

```text
.
├── akmalexpress/               # app: models, views, forms, templates
├── config/                     # settings, urls, wsgi/asgi
├── templates/                  # base, navbar, sidebar, messages, partials
├── static/
│   ├── src/tailwind.css
│   ├── output.css
│   └── css/main.css
├── manage.py
├── requirements.txt
└── package.json
```

## Частые проблемы

### `ModuleNotFoundError: No module named 'django'`

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### `OperationalError: database "AkmalExpress" does not exist`

Создай БД и снова выполни `python manage.py migrate`.

### Ошибка установки `pillow==10.2.0` на Python 3.13

Используй Python 3.11/3.12 для этого `requirements.txt`, либо обнови зависимости под 3.13.

### Статика не применяется

Проверь, что есть `static/output.css`, и при необходимости запусти:

```bash
npm run build
```

## Безопасность

- Для production запускай с `DJANGO_DEBUG=0`.
- Не используй дефолтные секреты и пароли.
- Перед релизом прогоняй:
  - `python manage.py check --deploy`
  - `bandit -q -r akmalexpress config`
  - `XDG_CACHE_HOME=/tmp pip-audit`

Подробный чеклист: [docs/SECURITY.md](docs/SECURITY.md)

## Сброс данных (очистка БД)

```bash
DB_PASSWORD='<your_db_password>' python manage.py flush --noinput
find media -mindepth 1 -delete 2>/dev/null || true
```

---

Если нужно, добавлю в README блок с `.env`-конфигом и готовым `docker-compose` для PostgreSQL + Django.
