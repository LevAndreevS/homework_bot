import logging
import os
import sys
import time
import telegram
import requests

from dotenv import load_dotenv
from telegram.ext import Updater

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    filemode='w',
    format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s'
)
logger = logging.getLogger()
streamHandler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
TIMESTAMP = 1673873421


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    for i in (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID):
        if i is not None:
            return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram чаткружения."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logging.debug('Сообщение отправлено')
    except Exception as error:
        logging.error(f'Ошибка отправки сообщения в телеграм: {error}')


class UrlError(Exception):
    """Ошибка Url."""

    pass


def get_api_answer(timestamp):
    """Запрашивает к единственному эндпоинту API-сервиса."""
    try:
        payload = {'from_date': timestamp}
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=payload
        )
    except Exception as error:
        logging.error(f'Сбой в работе сайта: {error}')
    if response.status_code != 200:
        raise UrlError(response)
    logging.debug('Вернулся json файл')
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if 'homeworks' and 'current_date' not in response:
        raise TypeError('Осутствуют ожидаемые ключи.')
    if not isinstance(response, dict):
        raise TypeError('Имеет некорректный тип.')
    if not isinstance(response.get('homeworks'), list):
        raise TypeError('Формат ответа не соответствует.')
    if not response:
        raise TypeError('Содержит пустой словарь.')
    try:
        response = response.get('homeworks')[0]
    except Exception as error:
        logging.error(f'Осутствуют ожидаемые ключи: {error}')
    logging.debug('Последняя домашняя работа')
    return response


def parse_status(homework):
    """Статус информации о конкретной домашней работе."""
    try:
        homework_name = homework.get('homework_name')
        homework_status = homework.get('status')
        verdict = HOMEWORK_VERDICTS.get(homework_status)
    except Exception as error:
        logging.error(
            'Неожиданный статус домашней работы, '
            f'обнаруженный в ответе API: {error}'
        )
    if homework_name is None:
        raise KeyError('Отсутствует имя домашней работы.')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError('Отсутствует статус проверки.')
    logging.debug('Проверяем статус домашней')
    if homework_status is None:
        logging.debug('Отсутствует статус новой домашней работы')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    logging.info('Бот начал работу')
    if check_tokens() is not True:
        logging.critical(
            'Отсутствуют обязательные переменные окружения.'
        )
        exit('Программа принудительно остановлена.')
    updater = Updater(token=TELEGRAM_TOKEN)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)

    while True:
        try:
            response = get_api_answer(TIMESTAMP)
            message = parse_status(check_response(response))
        except Exception as error:
            logging.error(f'Сбой в работе программы: {error}')
            message = str(error)
        finally:
            send_message(bot, message)

        time.sleep(RETRY_PERIOD)
        updater.start_polling()
        updater.idle()


if __name__ == '__main__':
    main()
