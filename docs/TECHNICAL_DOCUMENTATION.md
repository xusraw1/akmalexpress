# AkmalExpress — техническая документация и аудит

## 1. Общее описание проекта

### Назначение системы
AkmalExpress — это внутренняя CRM-система на Django для операционной работы с заказами: создание и редактирование заказов, управление статусами, работа с трек-номерами, печать квитанций/расчётов, профиль администраторов, импорт/экспорт Excel.

### Целевая аудитория
- Операторы/администраторы логистики
- Супер-администратор (управление админами и аналитикой)
- Клиенты (публичный поиск заказа и просмотр статуса)

### Ключевые возможности
- CRUD по заказам с товарными позициями (`Order` + `OrderItem`)
- Публичный точный поиск заказа (квитанция/ФИО/телефон/трек)
- Трек-центр для быстрых статусов по трек-номеру
- Массовая смена статусов (bulk-режим)
- Панель просрочек (принят > 3д, заказан > 10д, в пути > 20д)
- Импорт/экспорт `.xlsx`
- RU/UZ интерфейс

---

## 2. Архитектурный обзор

### Архитектурный стиль
Проект использует классическую Django MVC/MTV-архитектуру с частичным выделением слоёв:
- `views_*` — orchestration/контроллеры
- `selectors/` — переиспользуемые запросы/фильтры
- `services/` — внешние интеграции и прикладные сервисы (Excel, курсы валют, аналитика)
- `forms.py` — валидация и нормализация входных данных
- `models.py` — доменные сущности и вычисляемые свойства

### Взаимодействие компонентов
1. Запрос попадает в `config/urls.py` и далее в `akmalexpress/urls.py`.
2. View вызывает:
   - формы для валидации,
   - selectors для queryset-фильтрации,
   - services для тяжёлых операций.
3. Ответ рендерится шаблонами (`templates/`, `akmalexpress/templates/`) и статиками (`static/`).

### Сильные стороны текущей архитектуры
- Выделены `services` и `selectors` (уже есть разделение concerns)
- Чётко выраженные доменные сущности (`Order`, `OrderItem`, `OrderAttachment`)
- Повторно используемые фильтры для списков/экспортов
- Сильная серверная валидация форм

### Слабые стороны/риски
- Крупные FBV (особенно `views_orders.py`) — высокий риск регрессий
- `i18n.py` содержит большой словарь и пост-обработку HTML (техдолг)
- `tests.py` монолитный (сложно поддерживать и ускорять)
- Экспорт/импорт Excel реализован приватными функциями (`_...`) с высокой связностью

---

## 3. Структура проекта

```text
akmalexpress-main/
├── akmalexpress/
│   ├── admin.py
│   ├── context_processors.py
│   ├── forms.py
│   ├── i18n.py
│   ├── middleware.py
│   ├── models.py
│   ├── tests.py
│   ├── urls.py
│   ├── view_helpers.py
│   ├── views.py
│   ├── views_admins.py
│   ├── views_orders.py
│   ├── views_profile.py
│   ├── views_public.py
│   ├── selectors/
│   │   └── orders.py
│   ├── services/
│   │   ├── admins.py
│   │   ├── exchange_rates.py
│   │   ├── excel.py
│   │   └── images.py
│   ├── templates/akmalexpress/
│   └── templatetags/
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── templates/
├── static/
├── locale/
├── docs/
│   └── TECHNICAL_DOCUMENTATION.md
├── manage.py
├── requirements.txt
├── gunicorn.conf.py
├── render.yaml
└── README.md
```

### Назначение ключевых app-модулей
- `views_public.py`: главная, логин/логаут, lang-switch, публичные страницы
- `views_orders.py`: основной заказный workflow, трек-центр, экспорт/импорт
- `views_profile.py`: профиль и фильтрация заказов конкретного пользователя
- `views_admins.py`: супер-админ панель администраторов и аналитика
- `selectors/orders.py`: reusable фильтры и выборки
- `services/excel.py`: Excel-экспорт и импорт с транзакциями

---

## 4. Инструкция по запуску

### Требования
- Python 3.11+
- Node.js (только если требуется пересобирать Tailwind)

### Локальный запуск
```bash
cd /Users/developer/Desktop/akmalexpress-main
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8000
```

### Сборка frontend-стилей (опционально)
```bash
npm install
npm run build
```

### Production (Gunicorn)
```bash
python manage.py migrate --noinput
python manage.py collectstatic --noinput
gunicorn config.wsgi:application -c gunicorn.conf.py
```

---

## 5. Настройки и environment variables

Основные настройки в `config/settings.py`:
- БД: SQLite (`SQLITE_PATH` или `BASE_DIR/db.sqlite3`)
- Статика: WhiteNoise (`CompressedManifestStaticFilesStorage`)
- Медиа: `MEDIA_ROOT`, опция `SERVE_MEDIA_FILES`
- Безопасность: CSP, Permissions-Policy, HSTS, secure cookies
- i18n: `LANGUAGE_CODE='ru-ru'`, `LANGUAGES=[ru, uz]`, `LocaleMiddleware`

Ключевые ENV:
- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `ADMIN_URL`
- `STAFF_LOGIN_URL`
- `SQLITE_PATH`
- `MEDIA_ROOT`
- `SERVE_MEDIA_FILES`
- `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`
- `STAFF_LOGIN_RATE_LIMIT_ATTEMPTS`
- `STAFF_LOGIN_RATE_LIMIT_WINDOW_SECONDS`
- `STAFF_LOGIN_RATE_LIMIT_LOCK_SECONDS`

### Рекомендации безопасности
- Всегда `DEBUG=False` в production
- Заполнять `ALLOWED_HOSTS` и `CSRF_TRUSTED_ORIGINS` явно
- Регулярно ротировать `SECRET_KEY` при инцидентах
- Вынести `CONTENT_SECURITY_POLICY` и `PERMISSIONS_POLICY` в env

---

## 6. Модели и данные

## Сущности
- `Product`: legacy-модель товара (историческая совместимость)
- `Order`: основной агрегат заказа
- `OrderItem`: товарная позиция в заказе (новая модель данных)
- `OrderAttachment`: фото заказа
- `UserProfile`: профиль пользователя (аватар)

### Ключевые связи
- `Order.user -> User (SET_NULL)`
- `Order.product -> Product (SET_NULL, legacy)`
- `OrderItem.order -> Order (CASCADE, related_name='items')`
- `OrderAttachment.order -> Order (CASCADE, related_name='attachments')`
- `UserProfile.user -> User (OneToOne)`

### Индексация
- Индексы по `receipt_number`, `order_date`, `status`, `phone1`, `phone2`, `track_number`
- Композитные индексы (`status+order_date`, `user+order_date`, `status+come`)

### Бизнес-смысл важных полей
- `manual_total`: ручной override итоговой суммы
- `track_number` в `Order`: legacy fallback
- `track_number` в `OrderItem`: основной источник трека

---

## 7. Views / маршруты / forms

### Публичные маршруты
- `/` — поиск заказа
- `/about/`, `/faq/`, `/contacts/`
- `/staff-login/` — служебный вход
- `/lang/<lang_code>/` — смена языка

### Заказы (для staff/superuser)
- `/order/` — список заказов, фильтры, bulk-режим
- `/create/order/` — создание
- `/order/<slug>/change/` — изменение
- `/order/<slug>/detail/` — деталка
- `/order/<slug>/receipt/` — печать квитанции
- `/order/<slug>/settlement/` — расчёт клиента
- `/tracks/` — трек-центр
- `/order/export/excel/`, `/order/import/excel/`

### Профиль
- `/profile/` -> redirect на `/profile/<username>/`
- `/profile/<username>/` — профиль + AJAX-фильтры заказов
- `/profile/<username>/export/excel/`, `/profile/<username>/import/excel/`

### Администраторы (только superuser)
- `/create/admin/` — управление администраторами
- `/toggle_status/<id>/`, `/delete_admin/<id>/`

### Валидация
- Формы: `CreateOrderForm`, `ChangeOrderForm`, `OrderItemFormSet`
- Критичная валидация: телефоны, товары, валюта, Excel MIME/extension, upload size/content-type

---

## 8. Бизнес-логика (ключевые сценарии)

### Создание/изменение заказа
- Шапка заказа валидируется формой
- Товары валидируются formset'ом
- Если ручной итог == автоитог, `manual_total` очищается
- Если впервые добавлен трек, статус автоматически повышается до `В пути`

### Трек-центр
- Поиск сначала по `OrderItem.track_number`, затем fallback на `Order.track_number`
- Возможна быстрая смена статуса заказа прямо с найденного трека

### Excel импорт
- Заголовки нормализуются через alias-map
- Строки группируются в заказы
- Импорт выполняется в `transaction.atomic()`
- Возвращаются счетчики и ограниченный список ошибок по строкам

### Панель просрочек
- Подсветка зависших заказов:
  - `accepted` > 3 дней
  - `ordered` > 10 дней
  - `transit` > 20 дней

---

## 9. Интеграции

### Внешние API
- Курсы валют:
  - Ipak Yuli (`wi.ipakyulibank.uz`)
  - CBU (`cbu.uz`)
- Кеширование курсов через Django cache (`15 минут`)

### Файлы
- Фото оптимизируются в WEBP (`services/images.py`)
- Excel через `openpyxl`

### Что не обнаружено
- DRF/API router layer
- Celery/Redis/фоновые воркеры
- Sentry/Prometheus/централизованный мониторинг

---

## 10. i18n

### Текущая реализация
- `LocaleMiddleware` + шаблонные `{% trans %}`
- Дополнительно: `akmalexpress/i18n.py` с dictionary/regex post-processing для Uzbek

### Проблема
`locale/ru/LC_MESSAGES` и `locale/uz/LC_MESSAGES` не содержат `.po/.mo` (только `.gitkeep`).

### Рекомендация
Постепенно мигрировать на стандартный Django i18n pipeline:
1. `makemessages -l ru -l uz`
2. Перенести словарь из `i18n.py` в `.po`
3. `compilemessages`
4. Убрать HTML post-processing middleware после полного покрытия

---

## 11. Тестирование

### Наличие тестов
Файл `akmalexpress/tests.py` содержит тесты по ключевым сценариям:
- Профиль/фильтры
- Missing track
- Автопереход статуса при треке
- Bulk режим
- Пороги просрочек
- Публичный поиск
- Трек-центр
- Settlement print
- Импорт/экспорт Excel
- Регрессионная загрузка страниц

### Чего не хватает
- Разбиение тестов по модулям
- Явные unit-тесты `selectors` и `services` (частично покрыто через интеграционные)
- Тесты на security headers/CSP
- Нагрузочные тесты поиска/Excel импорта

---

## 12. Технический долг и рекомендации

### Приоритет P1
- Разделить `views_orders.py` на CBV/feature-модули
- Декомпозировать `tests.py` на пакет `tests/` с файлами по доменам
- Перевести i18n на `.po/.mo`

### Приоритет P2
- Вынести bulk/status update в service layer
- Ввести `TypedDict`/dataclass для Excel payload в services
- Добавить линтеры/форматтеры и CI (ruff + pytest + check --deploy)

### Приоритет P3
- Добавить аудит-лог (кто изменил статус/сумму)
- Добавить observability (Sentry, метрики)

---

## 13. Онбординг нового backend-разработчика

1. Прочитать `README.md` и этот документ
2. Запустить проект локально
3. Пройти руками сценарии:
   - создание заказа с несколькими товарами
   - изменение заказа + фото
   - поиск по треку
   - экспорт/импорт Excel
4. Изучить слои в порядке:
   - `models.py`
   - `forms.py`
   - `selectors/orders.py`
   - `services/*.py`
   - `views_*.py`

---

## 14. Ограничения анализа

- Анализ выполнен по исходному коду в репозитории и локальной конфигурации.
- Не анализировались внешние инфраструктурные секреты и облачные настройки вне репозитория.
- Для полного production-аудита отдельно нужны: логи, реальные профили нагрузки, правила WAF/CDN и политика бэкапов.
