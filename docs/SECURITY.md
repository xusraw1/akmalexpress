# Security Guide

Этот документ описывает минимальные практики безопасности для проекта AkmalExpress.

## 1) Базовый hardening Django

Критичные настройки берутся из env-переменных:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DJANGO_ADMIN_URL` (скрытый путь к админке)
- `DJANGO_STAFF_LOGIN_URL` (скрытый путь входа сотрудников)
- `DB_NAME` (SQLite-файл)

Рекомендация для production:

- `DJANGO_DEBUG=0`
- заполненный `DJANGO_SECRET_KEY`
- явный whitelist в `DJANGO_ALLOWED_HOSTS`
- HTTPS и прокси корректно настроены
- нестандартный путь `DJANGO_ADMIN_URL` задан
- нестандартный путь `DJANGO_STAFF_LOGIN_URL` задан

При `DJANGO_DEBUG=0` в приложении автоматически включаются:

- `SECURE_SSL_REDIRECT=True`
- `SESSION_COOKIE_SECURE=True`
- `CSRF_COOKIE_SECURE=True`
- HSTS (`SECURE_HSTS_SECONDS`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD`)

## 2) Проверки безопасности

### Проверка Django

```bash
python manage.py check --deploy
```

### Проверка robots/noindex

Убедиться, что:

- `/admin/` возвращает `404`
- `/login/` возвращает `404`
- `/<DJANGO_STAFF_LOGIN_URL>` ведет на служебный вход
- `/<DJANGO_ADMIN_URL>` ведет в Django admin
- `/robots.txt` содержит `Disallow` для private-paths

### Статический анализ Python-кода

```bash
bandit -q -r akmalexpress config
```

### Аудит зависимостей

```bash
XDG_CACHE_HOME=/tmp pip-audit
```

## 3) Загрузка файлов

В форме заказа разрешены только изображения; также ограничен размер файла.

- Максимум: 10MB на один файл.
- Неподходящий `content_type` отклоняется.

## 4) Operational checklist

Перед релизом:

1. Прогнать `check --deploy`, `bandit`, `pip-audit`.
2. Обновить зависимости и заново прогнать аудит.
3. Проверить логи доступа и ошибок.
4. Убедиться, что резервное копирование БД настроено.

## 5) Incident response (минимум)

Если обнаружена уязвимость:

1. Ограничить доступ (временно, если нужно).
2. Подготовить фикс в отдельной ветке.
3. Прогнать тесты/аудит.
4. Выложить фикс и сменить скомпрометированные секреты.
