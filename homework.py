import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import StatusError, UrlError

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s',
    level=logging.DEBUG, handlers=[logging.StreamHandler(sys.stdout)]
)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens() -> bool:
    """Проверяет доступность переменных окружения."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def send_message(bot: telegram.Bot, message: str) -> None:
    """Отправляет сообщение в Telegram чаткружения."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logging.debug('Сообщение отправлено')
    except telegram.error.TelegramError as e:
        logging.error(f'Сообщение не отправлено: {e}')


def get_api_answer(timestamp: int) -> dict:
    """Запрашивает к единственному эндпоинту API-сервиса."""
    current_timestamp = timestamp or int(time.time())
    payload = {'from_date': current_timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=payload
        )
        if response.status_code != HTTPStatus.OK:
            raise UrlError(
                'Запрос перенапрален или отсутсвует доступ к сайту'
            )
    except UrlError(Exception) as e:
        logging.error(f'Сбой в работе сайта: {e}')
        raise
    return response.json()


def check_response(response: dict) -> str:
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Словарь имеет некорректный тип')
    if 'homeworks' not in response:
        raise TypeError('Осутствуют ожидаемые ключи')
    if 'current_date' not in response:
        raise TypeError('Осутствуют ожидаемые ключи')
    if not isinstance(response.get('homeworks'), list):
        raise TypeError('Формат ответа не соответствует')
    return response.get('homeworks')


def parse_status(homework: dict) -> str:
    """Статус информации о конкретной домашней работе."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует имя домашней работы.')
    if 'status' not in homework:
        raise KeyError('Отсутствует статус проверки.')
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(
            f'Неожиданный статус работы: "{homework_status}"'
        )
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main() -> None:
    """Основная логика работы бота."""
    logging.info('Бот начал работу')
    if not check_tokens():
        logging.critical(
            'Отсутствуют обязательные переменные окружения.'
        )
        sys.exit('Программа принудительно остановлена.')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    current_report = {
        'message': '',
        'name': ''
    }
    prev_report = {
        'message': '',
        'name': ''
    }
    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response.get('current_date')
            homework = check_response(response)
            if homework:
                homework = homework[0]
                current_report['name'] = homework.get('homework_name')
                message = parse_status(homework)
                current_report['message'] = message
            else:
                message = 'Отсутсвует новый статус домашней работы.'
                current_report['message'] = message
                raise StatusError(message)
        except StatusError as e:
            logging.error(f'Новый статус отсутсвует: {e}')
        if current_report != prev_report:
            send_message(bot, message)
            prev_report = current_report.copy()
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
