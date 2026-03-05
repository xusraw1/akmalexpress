# AkmalExpress

Локальная CRM/панель для учета заказов карго: создание продукта, создание заказа, отслеживание статусов, управление модераторами и поиск по квитанции/трек-номеру.

## Что внутри

- Backend: `Django`
- Database: `PostgreSQL`
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

### 3) PostgreSQL

В `config/settings.py` сейчас используется:

- `NAME = AkmalExpress`
- `USER = postgres`
- `PASSWORD = root`
- `HOST = localhost`
- `PORT = 5432`

Создай БД:

```bash
createdb AkmalExpress
```

или через `psql`:

```sql
CREATE DATABASE "AkmalExpress";
```

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

## Frontend (Tailwind)

Установить зависимости:

```bash
npm install
```

Режим наблюдения за стилями:

```bash
npm run build
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

## Технические заметки

- Настройки БД и `SECRET_KEY` сейчас хардкодом в `config/settings.py`.
- Для production лучше вынести в `.env`.
- Проект в режиме `DEBUG=True` (только для локальной разработки).

---

Если нужно, добавлю в README блок с `.env`-конфигом и готовым `docker-compose` для PostgreSQL + Django.
