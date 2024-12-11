# 导入标准库
import json
import time
import random
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
import psutil

# 导入第三方库
import schedule
import requests
from DrissionPage.errors import *
from DrissionPage import Chromium
from DrissionPage import ChromiumOptions

# 导入自定义库
from cache import Cache
from mailSender import MailSender
from config import (CACHE_SIZE, TASK_TNTERVAL, 
                    MAX_TRY_TIMES, POST_URL, CACHE_LOCAL_PATH)

logger = logging.getLogger('my_logger')
handler = TimedRotatingFileHandler('my_app.log', when='midnight', interval=1, backupCount=30, encoding='utf-8')
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('[%(asctime)s %(levelname)s] %(message)s')
handler.setLevel(logging.DEBUG)
handler.setFormatter(formatter)
logger.addHandler(handler)


CACHE_LOCAL_PATH = './myCache.pkl'


def check_chrome_process():
    for proc in psutil.process_iter(['name']):
        if proc.info['name'].lower() == "chrome.exe" or proc.info['name'].lower() == "google-chrome":
            return True
    return False


def spilt_content(content):
    # 昵称全是特殊字符时可能会有问题
    if '\n' in content:
        index = content.find('\n')
        return content[:index], content[index + 1:]
    else:
        return content, ''


def send_login_mail(file_path, file_name, is_prd):
    if is_prd:
        mail_sender = MailSender(
            mail_host="smtp.bankcomm.com",
            mail_host_port=25,
            mail_user="oa_name@bankcomm.com",
            mail_pass="oa_password"
        )
        mail_sender.send_mail_with_attachment(
            receivers=['sender@bankcomm.com'],
            subject='网页版微信登录扫码请求',
            text='如收到请扫描附件中的二维码',
            attach_file_name=file_path + '/' + file_name
        )
    else:
        mail_sender = MailSender(
            mail_host="smtp.qq.com",
            mail_host_port=465,
            mail_user="1983270580@qq.com",
            mail_pass="ztwxmlqkxabqdeaj"
        )

        mail_sender.send_mail_with_attachment(
            receivers=['wangfengchen@bankcomm.com'],
            subject='票据辅助助手邮件发送功能测试',
            text='您好，本邮件为功能测试，收到可忽略',
            attach_file_name=file_name
        )


def init_chromium_browser_tab():
    # 启动或接管浏览器，并创建标签页对象（仅支持Chromium内核浏览器）
    if check_chrome_process():
        print('already exist chrome')
        return Chromium().latest_tab
    else:
        co = ChromiumOptions()
        co.set_argument('--start-maximized')
        co.add_extension(r'./wechat-need-web-main/dist/chrome')
        co.save_to_default()
        print('create new chrome')
        return Chromium(addr_or_opts=co).latest_tab


def save_as_json(items):
    path = "msg.json"
    with open(path, 'a', encoding="utf-8") as f:
        for item in items:
            data_json = json.dumps(item, ensure_ascii=False)
            f.write(data_json + "\n")


def _get_or_create_cache(max_cache_size):
    cache = Cache(max_cache_size)
    try:
        logger.info("加载本地缓存...")
        cache.load(CACHE_LOCAL_PATH)
    except:
        logger.warning("加载本地缓存失败，将不使用本地缓存")
    return cache


class MSGCrawler:
    """微信消息内容爬虫"""

    def __init__(self, max_cache_size, post_url):
        self._tab = init_chromium_browser_tab()  # 获取网页版微信标签页
        self._cache = _get_or_create_cache(max_cache_size)
        self.group_names = []  # 默认需抓取的群聊名列表
        self.post_url = post_url  # 抓取结果发送的url

    def post_to_server(self, item):
        """结果发到我们SLB，转发到edps_ack的nesAIQryCesDscntInfo处理"""
        jdata = {"REQ_MESSAGE": {"REQ_HEAD": {"TRANS_PROCESS": "", "TRANS_ID": ""}, "REQ_BODY": {"data": item}}}
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"  # 定义边界字符串
        body = ""
        for key, value in jdata.items():
            body += "--" + boundary + "\r\n"
            body += 'Content-Disposition: form-data; name="%s"\r\n\r\n' % key
            body += json.dumps(value) + "\r\n"
        body += "--" + boundary + "--\r\n"
        body = body.encode('utf-8')

        # 定义请求头，指定编码类型和内容长度
        headers = {
            "Content-Type": "multipart/form-data; boundary=%s" % boundary,
            "Content-Length": str(len(body))
        }

        response = requests.request("POST", self.post_url, headers=headers, data=body)
        if response.status_code == 200:
            logger.info("数据发送成功!!")
        else:
            info = "数据发送失败!! 响应状态码: %s" % response.status_code
            logger.warning(info)
            print("send failed!")

    def get_group_name(self):
        self._tab.ele('@title=通讯录').click(by_js=None)
        time.sleep(1)

        if not self._tab.ele('text=群组'):
            logger.warning("未发现当前账号保存的群聊！！！")
            self.group_names = []
        else:
            logger.info("开始获取所有群聊...")
            group_names = []
            is_group_items_end = False

            while not is_group_items_end:
                is_group_items_end, group_names, item_height = self.check_need_scroll_contact()
                if not is_group_items_end:
                    logger.info("继续向下滑动，获取更多群聊名")
                    self._tab.actions.scroll(delta_y=0.5 * item_height, on_ele=self._tab.ele('@class=scroll-bar'))
                    time.sleep(0.001 * random.randrange(200, 800))

            self.group_names = group_names
            logger.debug(f"获取到的群聊列表：{group_names}")

    def put_cache(self, group_name, plain_list, content_list):
        msg_item_list = []
        if plain_list is None or len(plain_list) == 0:
            logger.error("获取到的plain_list为空!!")
        else:
            pub_time = None
            for plain, content in zip(plain_list, content_list):
                logger.debug(f"plain:{plain},content:{content}")
                msg_item = {}
                if '\n' in plain:
                    if plain != content:  # 有时间
                        pub_time = plain.replace(content, '').replace('\n', '')
                    if not self._cache.is_in_cache(group_name, content):
                        self._cache.put(group_name, content) 
                        msg_item['publisher'], msg_item['content'] = spilt_content(content)
                        msg_item['pubDate'] = datetime.now().strftime("%Y-%m-%d")
                        msg_item['crawlTime'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        msg_item['groupName'] = group_name
                        if pub_time is not None:
                            hours, minutes = map(int, pub_time.split(":"))
                            msg_item['pubTime'] = datetime.now().replace(hour=int(hours), minute=int(minutes)).strftime("%H:%M:%S")
                        else:
                            msg_item['pubTime'] = datetime.now().strftime("%H:%M:%S")
                        msg_item_list.append(msg_item)
                else:  # 没有时间的非文字消息或其它情况
                    logger.debug(f"plain:{plain}")
        return msg_item_list

    def login(self):
        print("t1:", datetime.now().strftime("%H:%M:%S"))
        if self._tab.ele('@id=chatArea'):
            logger.info("已有账号登录")
        else:
            print("t2:", datetime.now().strftime("%H:%M:%S"))
            logger.info("需扫码登录")
            self._tab.get('https://wx.qq.com')
            print("t3:", datetime.now().strftime("%H:%M:%S"))
            # while not self._tab.ele('@id=chatArea'):
            #     print("waiting......")
            #     time.sleep(20)  # 等扫码完成加载
            # # 测试环境没开邮件网络权限，还是得手动扫码
            try_num = 0
            print(datetime.now().strftime("%H:%M:%S"))
            time.sleep(5)
            while try_num<=MAX_TRY_TIMES:
                try_num += 1
                try: 
                    name= f"qrcode_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    self._tab.get_screenshot(path='tmp', name=name, full_page=True)
                    logger.info("wait for login...")
                    send_login_mail('tmp', name, False)
                except Exception as e:
                    logger.error(f"send mail failed:{e}")
                finally:
                    time.sleep(30)
                    if self._tab.ele('@id=chatArea'):
                        logger.info("login finish")
                        break
            logger.debug(f"try_num={try_num}")

    def check_need_scroll(self, group_name, content_list):
        is_need_scroll = True
        cur_content_list = [ele.text for ele in self._tab.ele('@id=chatArea').eles('@class=content')]
        logger.debug("latest content:{}".format(cur_content_list[-1]))
        if content_list[-1] == cur_content_list[-1] and content_list[0] == cur_content_list[0]:
            logger.info("到顶了,不必再滑动")
            return False

        for content in cur_content_list:
            if self._cache.is_in_cache(group_name, content):
                is_need_scroll = False
                logger.info("已没有更多消息,不必再滑动")

        return is_need_scroll

    def check_need_scroll_contact(self):
        is_group_items_end = False
        group_names = []
        current_chat_items = self._tab.eles('@class=contact_item ')
        item_height = 0
        cnt = 0
        for current_chat_item in current_chat_items:
            try:
                cnt += 1
                item_height += current_chat_item.rect.size[1]
                if cnt > 1 and \
                        (current_chat_item.rect.location[1] - last_group_item_loc_height) > 5 + \
                        current_chat_item.rect.size[1]:
                    is_group_items_end = True
                last_group_item_loc_height = current_chat_item.rect.location[1]
                if not is_group_items_end:
                    if len(group_names) == 0 or current_chat_item.text not in group_names:
                        group_names.append(current_chat_item.text)
            except ElementNotFoundError as e:
                logger.error(f"获取群聊项时发生异常：{e}")

        return is_group_items_end, group_names, item_height

    def get_group_msgs(self, group_name):
        msg_item_list = {}
        plain_list, content_list = [], []
        # 向上滑动以获取未在缓存中的消息(仅文字)
        total_content_item_height = 0
        for content_ele in self._tab.ele('@id=chatArea').eles('@class=clearfix'):
            total_content_item_height += content_ele.rect.size[1]
            plain_list.append(content_ele.text)
            content_list.append(content_ele.ele('@class=content').text)

        scroll_flag = True
        while scroll_flag or self.check_need_scroll(group_name, content_list):
            scroll_flag = False
            msg_item_list = self.put_cache(group_name, plain_list, content_list)
            self._tab.actions.scroll(delta_y=-int(0.7 * total_content_item_height),
                                     on_ele=self._tab.ele('@id=chatArea').eles('@class=content')[-1])
            logger.debug("滑动一次，向上{}".format(0.7 * total_content_item_height))
        return msg_item_list

    def run(self):
        try:
            group_msgs = {}
            self.get_group_name()

            if self.group_names is not None and len(self.group_names) > 0:
                for group_name in self.group_names:
                    # 先清空搜索框再输入群名称
                    self._tab.ele('tag:input').clear()
                    self._tab.ele('tag:input').input(group_name)
                    time.sleep(1 + 0.001 * random.randrange(200, 800))
                    # 子元素中用class匹配，点击进入对应群聊会话
                    self._tab.ele('@id=search_bar').ele('@class=contact_item on').click()
                    time.sleep(1)
                    logger.info("开始抓取{}".format(group_name))
                    if self._tab.ele('@id=chatArea').eles('text=暂时没有新消息'):
                        logger.info("{}暂无新消息".format(group_name))
                    elif self._tab.ele('@id=chatArea').eles('@class=clearfix'):
                        logger.info("抓取{}中...".format(group_name))
                        group_msgs[group_name] = self.get_group_msgs(group_name)
                    else:
                        logger.error("未知错误")
                    logger.info("结束抓取{}".format(group_name))
                    time.sleep(1 + 0.001 * random.randrange(200, 300))
            else:
                logger.error("No Valid Group Name")

            if len(group_msgs) > 0:
                for k,v in group_msgs.items():
                    self.post_to_server(v)
                    logger.info(f"完成发送群聊{k}数据")
            else:
                logger.info("没有新数据，此次不发送数据")
            self._cache.save(CACHE_LOCAL_PATH)
            # 保存结果到本地
            save_as_json(group_msgs)
        except [ElementNotFoundError, ElementLostError, NoRectError] as e:
            logger.error(f"发生元素交互异常：{e}")
        # except [ContextLostError, CDPError, PageDisconnectedError] as e2:
        #     logger.error(f"环境异常：{e2}")



if __name__ == '__main__':
    crawler = MSGCrawler(max_cache_size=CACHE_SIZE, post_url=POST_URL)
    crawler.login()
    crawler.run()
    #  设置定时任务
    logger.info("启动定时任务..")
    # 群聊较多时根据实际情况调整定时间隔
    schedule.every(TASK_TNTERVAL).seconds.do(crawler.run)  

    while True:
        schedule.run_pending()
