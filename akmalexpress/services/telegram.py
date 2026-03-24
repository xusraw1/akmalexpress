"""Telegram notification helpers for public contact requests."""

import json
import logging
from html import escape
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

TELEGRAM_TIMEOUT_SECONDS = 7
TELEGRAM_SEND_MESSAGE_URL = 'https://api.telegram.org/bot{token}/sendMessage'


def _contact_message(name: str, phone: str, email: str, message: str, page_url: str = '') -> str:
    """Build escaped HTML text for Telegram notification."""
    submitted_at = timezone.localtime().strftime('%d.%m.%Y %H:%M')
    lines = [
        '<b>Новый запрос с сайта AkmalExpress</b>',
        '',
        f'<b>Имя:</b> {escape(name or "-")}',
        f'<b>Телефон:</b> {escape(phone or "-")}',
        f'<b>Email:</b> {escape(email or "-")}',
        f'<b>Дата:</b> {escape(submitted_at)}',
        '',
        f'<b>Текст:</b>\n{escape(message or "-")}',
    ]
    if page_url:
        lines.extend(['', f'<b>Страница:</b> {escape(page_url)}'])
    return '\n'.join(lines)


def send_contact_request_notification(*, name: str, phone: str, email: str, message: str, page_url: str = '') -> bool:
    """Send contact form payload to configured Telegram chats.

    Returns:
        bool: True when at least one chat accepted the message.
    """
    if not getattr(settings, 'TELEGRAM_CONTACT_NOTIFICATIONS_ENABLED', True):
        return False

    token = (getattr(settings, 'TELEGRAM_BOT_TOKEN', '') or '').strip()
    chat_ids = list(getattr(settings, 'TELEGRAM_CONTACT_CHAT_IDS', []) or [])
    thread_id = getattr(settings, 'TELEGRAM_CONTACT_THREAD_ID', None)
    if not token or not chat_ids:
        logger.warning('Telegram contact notifications are not configured.')
        return False

    endpoint = TELEGRAM_SEND_MESSAGE_URL.format(token=token)
    text = _contact_message(name=name, phone=phone, email=email, message=message, page_url=page_url)
    sent_count = 0

    for chat_id in chat_ids:
        payload = {
            'chat_id': str(chat_id),
            'text': text,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True,
        }
        if thread_id:
            payload['message_thread_id'] = thread_id

        request = Request(
            endpoint,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'AkmalExpress/1.0',
            },
            method='POST',
        )

        try:
            with urlopen(request, timeout=TELEGRAM_TIMEOUT_SECONDS) as response:
                raw_response = response.read().decode('utf-8', errors='ignore')
            response_data = json.loads(raw_response)
            if isinstance(response_data, dict) and response_data.get('ok') is True:
                sent_count += 1
            else:
                logger.warning('Telegram API returned non-ok response for chat_id=%s', chat_id)
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError) as exc:
            logger.warning('Failed to send Telegram contact request notification: %s', exc)

    return sent_count > 0
