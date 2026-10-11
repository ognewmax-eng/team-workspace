# Конфигурация экземпляра

Секреты хранятся в `.env` с правами 600 либо в файле из `WORKSPACE_CONFIG`. Не коммитьте их. Для настройки используйте `.env.example`; после изменения перезапустите web и обработчик рассылок.

- `ORGANIZATION_NAME`: подпись организации в интерфейсе и письмах.
- `SITE_URL`: адрес без пути. Внешний сайт — HTTPS, локальный просмотр — HTTP на localhost.
- `ALLOWED_HOSTS`: допустимые имена хостов через запятую, без схемы; не используйте `*`.
- `TIME_ZONE`: IANA-имя, например Asia/Yekaterinburg.
- `SECRET_KEY`: индивидуальный ключ установщика. Сохраняйте его при переездах; смена сбросит подписи и сессии.
- `DATA_DIR`: закрытый каталог SQLite, вложений и статики. В Docker задан /app/data.
- `DEBUG`: False для работы с пользователями.

## Почта

Заполните `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`. Обычно порт 587 использует `EMAIL_USE_TLS=True`, `EMAIL_USE_SSL=False`; порт 465 — обратные значения. Оба режима одновременно включать нельзя. Настройте SPF/DKIM/DMARC у своего почтового провайдера.

Без EMAIL_HOST отправка явно отключена. Для очереди нужны контейнер mailings или cron process_mailings. Перед запуском рассылки используется существующее тестовое письмо и подтверждение аудитории. Все адреса и ссылки берутся из вашего экземпляра.

## Synology

По умолчанию `FILE_STORAGE=local`. Для своего NAS задайте `FILE_STORAGE=synology` и `SYNOLOGY_CONFIG_FILE=/закрытый/путь/synology.json`. Формат JSON описан в `accounts/synology_storage.py` (url, username, password). В url включите путь общей папки, например https://nas.example.org:5006/WorkspaceMedia/. Используйте HTTPS WebDAV с проверяемым сертификатом и отдельную учётную запись с ограниченным доступом. Не включайте пароль в URL.

Смена backend не переносит существующие файлы. Перед переключением скопируйте все вложения с сохранением относительных путей и проверьте доступ. Внешние файлы не входят в backup_instance.

## Telegram и Google

Они не нужны для основных функций. Для Python установите `requirements-integrations.txt`. Для Docker добавьте установку этого файла в свой Dockerfile и пересоберите образ. Используйте свои `TELEGRAM_BOT_TOKEN`, `GOOGLE_CALENDAR_CLIENT_ID`, `GOOGLE_CALENDAR_CLIENT_SECRET`. Google callback — `/google-calendar/callback/`, Telegram webhook — `/telegram/webhook/` на вашем SITE_URL. Зарегистрируйте callback/webhook в соответствующих сервисах. Данные старой организации не используются.
