import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import UrlError
from requests import RequestException

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s',
    level=logging.DEBUG, handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
}


def check_tokens() -> bool:
    """Проверяет доступность переменных окружения."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def send_message(bot: telegram.Bot, message: str) -> None:
    """Отправляет сообщение в Telegram чаткружения."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
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
            params=payload,
        )
        if response.status_code != HTTPStatus.OK:
            message = ('Запрос перенапрален или отсутсвует доступ '
                       f'к сайту {response.status_code}')
            raise UrlError(message)
        return response.json()
    except UrlError as e:
        logging.error(f'{e}')
        raise RequestException('Ошибка в запросе к API')
    except RequestException as e:
        logging.error(f'{e}')


def check_response(response: dict) -> str:
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Словарь имеет некорректный тип')
    if not isinstance(response.get('homeworks'), list):
        raise TypeError('Формат ответа не соответствует')
    if 'current_date' not in response:
        raise TypeError('Осутствует ожидаемый ключ')
    logging.debug(response.get('homeworks'))
    return response.get('homeworks')


def parse_status(homework: dict) -> str:
    """Статус информации о конкретной домашней работе."""
    homework_name = homework.get('homework_name')
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует имя домашней работы.')
    homework_status = homework.get('status')
    if 'status' not in homework:
        raise KeyError('Отсутствует статус проверки.')
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(
            f'Неожиданный статус работы: "{homework_status}"'
        )
    logging.debug(f'Cтатус работы "{homework_name}". {verdict}')
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
        'name': '',
        'message': '',
    }
    prev_report = {
        'name': '',
        'message': '',
    }
    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response.get('current_date')
            homework = check_response(response)
            if homework:
                homework = homework[0]
                current_report['name'] = homework.get('homework_name')
                current_report['message'] = parse_status(homework)
            else:
                current_report['message'] = ('Отсутсвует новый статус домашней'
                                             ' работы.')
        except (TypeError, KeyError, ValueError, Exception) as e:
            logging.error(f'{e}')
        if current_report != prev_report:
            send_message(bot, current_report.get('message'))
            prev_report = current_report.copy()
        logging.debug(current_report.get('message'))
        logging.debug('Итерация завершена')
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
