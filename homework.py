import logging
import logging.config
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
DAYS_IN_MONTH = 30
HOURS_IN_DAY = 24
MIN_IN_HOUR = 60
SEC_IN_MIN = 60

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.config.fileConfig('logging.conf')
main_logger = logging.getLogger('main')
stream_logger = logging.getLogger('stream')


def send_message(bot, message):
    """Отправка сообщение в Telegram о статусе работы."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        stream_logger.info(
            f'Сообщение отправлено в чат {TELEGRAM_CHAT_ID}: {message}'
        )
    except Exception:
        raise Exception('Ошибка отправки сообщения в телеграм')


def get_api_answer(current_timestamp):
    """Запрос к единственному эндпоинту API сервиса."""
    timestamp = current_timestamp or int(time.time())
    headers = {
        'url':
        'https://practicum.yandex.ru/api/user_api/homework_statuses/',
        'headers': {'Authorization': f'OAuth {PRACTICUM_TOKEN}'},
        'params': {'from_date': timestamp}
    }
    try:
        homework_statuses = requests.get(**headers)
    except Exception as error:
        raise Exception(f'Ошибка при запросе к основному API: {error}')
    if homework_statuses.status_code != HTTPStatus.OK:
        status_code = homework_statuses.status_code
        main_logger.error(
            f'Ошибочный статус ответа по API: {homework_statuses.status_code}'
        )
        raise Exception(f'Ошибка {status_code}')
    try:
        return homework_statuses.json()
    except ValueError:
        raise ValueError('Ошибка парсинга ответа из формата json')


def check_response(response):
    """Проверка ответа API на корректность."""
    if type(response) is not dict:
        raise TypeError('Ответ отличен от словаря')
    try:
        list_works = response['homeworks']
    except KeyError:
        raise KeyError('Ошибка словаря по ключу homeworks')
    if type(list_works) is not list:
        raise TypeError('Ответ отличен от списка')
    try:
        homework = list_works[0]
    except IndexError:
        raise IndexError('Список домашних работ пуст')
    return homework


def parse_status(homework):
    """Информации о статусе конкретной домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if 'status' not in homework:
        raise Exception('Отсутствует ключ "status" в ответе API')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности переменных окружения."""
    if PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID is not None:
        return True
    else:
        return False


def main():
    """Основная логика работы бота."""
    current_timestamp = int(
        time.time() - DAYS_IN_MONTH
        * HOURS_IN_DAY * MIN_IN_HOUR * SEC_IN_MIN
    )
    STATUS = ''
    ERROR_CACHE_MESSAGE = ''
    if not check_tokens():
        stream_logger.critical(
            'Недоступна одна или несколько переменных окружения'
        )
        raise sys.exit(1)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_date')
            message = parse_status(check_response(response))
            if message != STATUS:
                send_message(bot, message)
                STATUS = message
        except Exception as error:
            stream_logger.error(error)
            message_t = str(error)
            if message_t != ERROR_CACHE_MESSAGE:
                send_message(bot, message_t)
                ERROR_CACHE_MESSAGE = message_t
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
