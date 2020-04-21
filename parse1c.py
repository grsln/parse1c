# -*- coding: utf-8 -*-
from selenium import webdriver
from bs4 import BeautifulSoup as bs
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException, \
    ElementNotInteractableException, UnexpectedAlertPresentException, TimeoutException
from selenium.webdriver.common.by import By
import os
import re
import datetime
import time
from config import Config
import telebot
from models import User
from sqlalchemy.orm import sessionmaker
from models import engine
import logging
from logging.handlers import SMTPHandler, RotatingFileHandler
import smtplib
from email.message import EmailMessage
import email.utils
from selenium.webdriver.firefox.options import Options


class SSLSMTPHandler(SMTPHandler):
    def emit(self, record):
        """
        Emit a record.
        """
        try:
            port = self.mailport
            if not port:
                port = smtplib.SMTP_PORT
            smtp = smtplib.SMTP_SSL(self.mailhost, port)
            msg = EmailMessage()
            msg['From'] = self.fromaddr
            msg['To'] = ','.join(self.toaddrs)
            msg['Subject'] = self.getSubject(record)
            msg['Date'] = email.utils.localtime()
            msg.set_content(self.format(record))
            if self.username:
                smtp.login(self.username, self.password)
            smtp.send_message(msg, self.fromaddr, self.toaddrs)
            smtp.quit()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


def set_mail_logger():
    auth = None
    if Config.MAIL_USERNAME or Config.MAIL_PASSWORD:
        auth = (Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
    secure = None
    if Config.MAIL_USE_TLS:
        secure = ()
    mail_handler = SSLSMTPHandler(
        mailhost=(Config.MAIL_SERVER, Config.MAIL_PORT),
        fromaddr=Config.MAIL_USERNAME,
        toaddrs=Config.ADMINS, subject='Bot Failure',
        credentials=auth, secure=secure)
    mail_handler.setLevel(logging.ERROR)
    return mail_handler


def set_file_logger():
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/hhparse.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    file_handler.setLevel(logging.INFO)
    return file_handler


# logger = logging.getLogger(__name__)
logger = logging.getLogger('log')
if Config.MAIL_SERVER:
    logger.addHandler(set_mail_logger())
    # logger.propagate = False
logger.addHandler(set_file_logger())
logger.setLevel(logging.INFO)
logger.info('parse1c startup')

bot = telebot.TeleBot(Config.TG_TOKEN)

users_dict = {}
password_dict = {}
SessionDB = sessionmaker(bind=engine)
session_db = SessionDB()
url = 'http://1c-upp.bngf.ru/test_bngf/ru_RU/mainform.html?sysver=8.3.10.2667'


@bot.message_handler(commands=['start'])
def start_message(message):
    kb = telebot.types.ReplyKeyboardMarkup(True)
    kb.row('Заявки', 'Вход')
    msg = bot.send_message(message.chat.id, 'Введите логин:', reply_markup=kb)
    bot.register_next_step_handler(msg, ask_user)


def ask_user(message):
    chat_id = message.chat.id
    text = message.text
    users_dict[chat_id] = text
    msg = bot.send_message(chat_id, 'Введите пароль:')
    bot.register_next_step_handler(msg, ask_password)


def ask_password(message):
    chat_id = message.chat.id
    text = message.text
    password_dict[chat_id] = text
    bot.delete_message(
        chat_id=chat_id,
        message_id=message.message_id)
    ans(message)


# @bot.callback_query_handler(func=lambda c: True)
def ans(c):
    cid = c.chat.id
    if (cid in users_dict) and (cid in password_dict):
        bot.send_message(cid, "Подключение...")
        browser = setup_driver()
        logger.info('Запуск браузера')
        browser.get(url)
        authorization(browser, users_dict[cid], password_dict[cid])

        try:
            WebDriverWait(browser, 10).until(EC.element_to_be_clickable((By.ID, "FuncPanelButton")))
            login_title = browser.title
            if login_title.find('Производственный'):
                bot.send_message(cid, "Авторизация прошла успешно")
                result = session_db.query(User).filter_by(chat_id=cid).first()
                if result:
                    try:
                        result.login = users_dict[cid]
                        result.password = password_dict[cid]
                        session_db.commit()
                    except:
                        bot.send_message(cid, 'Ошибка обновления')
                        session_db.rollback()
                else:
                    try:
                        user_login = User(login=users_dict[cid],
                                          password=password_dict[cid],
                                          chat_id=cid,
                                          authorized=True)
                        session_db.add(user_login)
                        session_db.commit()
                    except:
                        bot.send_message(cid, 'Ошибка сохранения')
                        session_db.rollback()

        except UnexpectedAlertPresentException as e:
            bot.send_message(cid, "Авторизация не выполнена")
        browser.quit()
        session_db.close()

        del users_dict[cid]
        del password_dict[cid]


def setup_driver():
    # capabilities = {
    #     "browserName": "firefox",
    #     "version": "69.0",
    #     "enableVNC": True,
    #     "enableVideo": False,
    #     "sessionTimeout": "2m"
    # }
    # return webdriver.Remote(
    #     command_executor=f"http://{Config.SEL_SERVER}:4444/wd/hub",
    #     desired_capabilities=capabilities)
    options = Options()
    options.headless = True
    # return webdriver.Firefox(options=options,
    #                          executable_path=r'C:\Users\АУГР\PycharmProjects\hhparse\geckodriver.exe',
    #                          firefox_binary=r'C:\Program Files (x86)\Mozilla Firefox\firefox.exe')
    return webdriver.Firefox(options=options)


def authorization(browser, user, password):
    logger.info("ожидание отображения userName")
    WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.ID, "userName")))

    logger.info("ввод логина")
    while True:
        try:
            browser.find_element_by_id('userName').send_keys(user)
            break
        except (StaleElementReferenceException, NoSuchElementException, ElementNotInteractableException) as e:
            continue

    logger.info("ожидание userPassword")
    WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.ID, "userPassword")))

    logger.info("ввод пароля")
    browser.find_element_by_id('userPassword').send_keys(password)
    browser.find_element_by_id('okButton').click()


def waiting(browser, element, tv, tp, tc):
    try:
        if tv > 0:
            WebDriverWait(browser, tv).until(EC.visibility_of_element_located(element))
        if tp > 0:
            WebDriverWait(browser, tp).until(EC.presence_of_element_located(element))
        if tc > 0:
            WebDriverWait(browser, tc).until(EC.element_to_be_clickable(element))
    except TimeoutException as e:
        logger.info(e)


@bot.message_handler(content_types=['text'])
@bot.message_handler(commands=['q'])
def q_message(message):
    if (message.text.lower() == 'вход') or (message.text.lower() == '/start'):
        start_message(message)

    if (message.text.lower() == 'заявки') or (message.text.lower() == '/q'):
        result = session_db.query(User).filter_by(chat_id=message.chat.id).first()
        session_db.close()
        if result:
            # user = result.login
            # pswrd = result.password
            user = Config.USER_1C
            pswrd = Config.PSWRD
            t = os.path.getmtime('out2.html')
            delta = datetime.datetime.now() - datetime.datetime.fromtimestamp(t)
            if delta.seconds > 300:
                browser = setup_driver()
                logger.info('Запуск браузера')
                browser.get(url)

                authorization(browser, user, pswrd)

                logger.info("ожидание загрузки iframe")
                WebDriverWait(browser, 60).until(EC.visibility_of_element_located((By.ID, "form0_ФормаСформировать")))

                logger.info("нажатие сформировать")
                time.sleep(7)
                browser.find_element_by_id('form0_ФормаСформировать').click()
                time.sleep(7)

                logger.info("загрузка после нажатия сформировать")
                WebDriverWait(browser, 30).until(
                    EC.presence_of_element_located((By.ID, "form0_ФормаСформировать"))
                )
                WebDriverWait(browser, 60).until(
                    EC.element_to_be_clickable((By.ID, "form0_ФормаСформировать"))
                )
                f_c = len(browser.find_elements_by_css_selector('div#moxelform0_Результат.moxelDiv>iframe'))
                frame_ready = False
                for i_f in range(f_c):
                    ifr = browser.find_elements_by_css_selector('div#moxelform0_Результат.moxelDiv>iframe')[i_f]
                    # browser.switch_to.frame(ifr)
                    WebDriverWait(browser, 30).until(
                        EC.frame_to_be_available_and_switch_to_it(ifr)
                    )
                    required_html = browser.page_source
                    soup = bs(required_html, 'html.parser')
                    if soup.find_all('div', class_=re.compile("R\d+C\d+")):
                        frame_ready = True
                        break
                    browser.switch_to.default_content()

                browser.quit()
                if frame_ready:
                    f = open('out2.html', 'w', encoding='utf-8')
                    f.write(required_html)
                    f.close()
                else:
                    logger.info('Frame not ready')
            else:
                pass

            f = open('out2.html', 'r', encoding='utf-8')
            bot.send_document(message.chat.id, f)
            f.close()
        else:
            bot.send_message(message.chat.id, 'Вы не авторизованы. Выполните команду /start')


if __name__ == '__main__':
    bot.polling(none_stop=True, interval=0)
