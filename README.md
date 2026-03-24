# AkmalExpress

Django-проект для ежедневной работы с заказами: создание и изменение заказов, трек-центр, печать квитанций, профиль администраторов, импорт/экспорт Excel и публичный поиск заказа.

## Ключевые функции
- Заказы с несколькими товарами (`Order` + `OrderItem`)
- Публичный точный поиск по квитанции/ФИО/телефону/треку
- Трек-центр с быстрым обновлением статуса
- Bulk-обновление статусов в списке заказов
- Панель просрочек по порогам статусов
- Импорт/экспорт `.xlsx`
- RU/UZ интерфейс

## Технологии
- Python 3.11+
- Django 6.0.3
- SQLite
- OpenPyXL
- Pillow
- WhiteNoise + Gunicorn
- Tailwind CSS

## Структура
```text
akmalexpress-main/
├── akmalexpress/          # Основное приложение (models/views/forms/services/selectors)
├── config/                # settings/urls/wsgi/asgi
├── templates/             # Базовые шаблоны проекта
├── static/                # Статические ресурсы
├── locale/                # i18n каталоги
├── docs/                  # Техническая документация
├── manage.py
├── requirements.txt
├── render.yaml
└── gunicorn.conf.py
```

Подробный аудит и архитектура: [docs/TECHNICAL_DOCUMENTATION.md](docs/TECHNICAL_DOCUMENTATION.md)

## Локальный запуск
```bash
cd /Users/developer/Desktop/akmalexpress-main
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8000
```

Открыть:
- Главная: `http://127.0.0.1:8000/`
- Вход для админов: `http://127.0.0.1:8000/staff-login/`
- Django admin: `http://127.0.0.1:8000/secure-admin/` (или `ADMIN_URL`)

## Frontend (опционально)
```bash
npm install
npm run dev
# или
npm run build
```

## Переменные окружения
Минимальный набор:
- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`

Часто используемые:
- `ADMIN_URL` (default: `secure-admin/`)
- `STAFF_LOGIN_URL` (default: `staff-login/`)
- `CSRF_TRUSTED_ORIGINS`
- `SQLITE_PATH`
- `MEDIA_ROOT`
- `SERVE_MEDIA_FILES`
- `SECURE_SSL_REDIRECT`
- `SESSION_COOKIE_SECURE`
- `CSRF_COOKIE_SECURE`
- `LANGUAGE_COOKIE_SECURE`
- `TELEGRAM_CONTACT_NOTIFICATIONS_ENABLED` (`True`/`False`)
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CONTACT_CHAT_IDS` (например: `613701273` или `613701273,-1001234567890`)
- `TELEGRAM_CONTACT_THREAD_ID` (опционально, для topic в группе)

## Проверки перед деплоем
```bash
python manage.py check
python manage.py check --deploy
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

## Production запуск
```bash
python manage.py migrate --noinput
python manage.py collectstatic --noinput
gunicorn config.wsgi:application -c gunicorn.conf.py
```

## Render
В проекте есть `render.yaml` c готовыми командами build/start.

## Лицензия
В репозитории лицензия явно не задана. При публикации добавьте `LICENSE`.
