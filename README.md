# AkmalExpress

Современная Django-система для управления заказами: создание/редактирование заказов, трек-центр, печать квитанций, профиль администратора, Excel импорт/экспорт.

## Возможности

- Полный цикл заказа: создание, редактирование, статусы, удаление
- Товары внутри заказа (несколько позиций)
- Поиск по квитанции, ФИО, телефону, трек-номеру
- Трек-центр (скан/быстрое обновление статуса)
- Печать квитанций и расчетов
- Профиль с фильтрами и пагинацией
- Импорт/экспорт Excel (.xlsx)
- RU/UZ интерфейс

## Стек

- Python 3.11+
- Django
- SQLite
- Gunicorn
- WhiteNoise

## Быстрый локальный запуск

```bash
cd /Users/developer/Desktop/akmalexpress-main
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

Открыть:

- Главная: `http://127.0.0.1:8000/`
- Вход админа: `http://127.0.0.1:8000/staff-login/`
- Django admin: `http://127.0.0.1:8000/secure-admin/`

## Основные переменные окружения

- `SECRET_KEY`
- `ALLOWED_HOSTS`
- `ADMIN_URL` (по умолчанию: `secure-admin/`)
- `STAFF_LOGIN_URL` (по умолчанию: `staff-login/`)
- `CSRF_TRUSTED_ORIGINS`
- `SQLITE_PATH` (опционально, путь к SQLite для продакшна)
- `SECURE_SSL_REDIRECT`
- `SESSION_COOKIE_SECURE`
- `CSRF_COOKIE_SECURE`

## Деплой на Render

Проект готов для деплоя через `render.yaml`.

1. Запушь код в GitHub.
2. В Render: `New +` -> `Blueprint` -> выбери репозиторий.
3. Render применит `render.yaml` автоматически.
4. После первого деплоя создай суперпользователя в Shell:

```bash
python manage.py createsuperuser
```

## Проверки перед релизом

```bash
python manage.py check
python manage.py check --deploy
python manage.py migrate
python manage.py collectstatic --noinput
```

## Структура проекта

```text
akmalexpress-main/
├── akmalexpress/
├── config/
├── templates/
├── static/
├── staticfiles/
├── media/
├── manage.py
├── requirements.txt
├── render.yaml
├── gunicorn.conf.py
└── README.md
```
