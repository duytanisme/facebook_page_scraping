import os
import time
import re
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

import selenium.common.exceptions as se
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# from selenium.webdriver.common.keys import Keys

from typing import Union, Optional, Callable
from fake_useragent import UserAgent

os.system("cls")

load_dotenv()

API_KEY = os.getenv("API_KEY")


MAX_THREAD = os.cpu_count() + 4
THREAD_MSG = "[Thread #%03d] - %s: %s"

ROOT_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(ROOT_DIR, "data")
INPUT_PATH = os.path.join(DATA_DIR, "input.csv")
OUTPUT_PATH = os.path.join(DATA_DIR, "output.txt")

FACEBOOK_BASE_URL = "https://www.facebook.com"
FACEBOOK_PAGE_URL = FACEBOOK_BASE_URL + "/%s"
FACEBOOK_ADS_URL = FACEBOOK_PAGE_URL + "/about_profile_transparency"
ERROR_MSG = "This content isn't available at the moment"
ADS_STATUS = {
    "YES": "Có chạy",
    "NO": "Không chạy",
}

PROXY_BASE_URL = "http://proxy.shoplike.vn/Api"
GET_NEW_ENDPOINT = PROXY_BASE_URL + "/getNewProxy"
GET_CURRENT_ENDPOINT = PROXY_BASE_URL + "/getCurrentProxy"
RESPONSE_STATUS = {
    "ERROR": "error",
    "SUCCESS": "success",
}


class ProxyRequest:
    def __init__(self, api_key: str) -> None:
        self.__api_key = api_key

    def get_api_key(self) -> str:
        return self.__api_key

    def request(self, url: str) -> dict:
        params = {
            "access_token": self.get_api_key(),
            "location": "",
            "provider": "",
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_new_proxy(self) -> str:
        data = self.request(GET_NEW_ENDPOINT)
        if data is None:
            return
        if data["status"] == RESPONSE_STATUS["ERROR"]:
            return
        return data["data"]["proxy"]

    def get_current_proxy(self) -> str:
        data = self.request(GET_CURRENT_ENDPOINT)
        if data is None:
            return
        return data["data"]["proxy"]


proxy_cli = ProxyRequest(API_KEY)


class ChromeDriver:
    def config(self, **kwargs) -> Chrome:
        proxy = kwargs.get("proxy")
        options = Options()
        ua = UserAgent()
        random_user_agent = ua.random
        # options.add_argument("--headless")
        # options.add_argument(f"user-agent={random_user_agent}")
        options.add_argument(f"--proxy-server={proxy}")
        options.add_argument("--log-level=3")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--enable-unsafe-webgpu")
        options.add_argument("--enable-unsafe-swiftshader")
        options.add_argument("--window-size=1920x1080")
        # options.add_argument("--disable-web-security")
        # options.add_argument("--disable-site-isolation-trials")
        # options.add_argument("--disable-application-cache")
        # options.add_argument(
        #     "--disable-blink-features=AutomationControlled"
        # )
        options.add_experimental_option(
            "excludeSwitches",
            ["enable-automation", "enable-logging"],
        )
        # options.add_experimental_option("useAutomationExtension", False)
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--log-level=3")
        # options.add_argument("--disable-popup-blocking")
        options.add_argument("--ignore-certificate-errors")
        driver = Chrome(options=options)
        return driver


class ChromePosition:

    @staticmethod
    def config(
        driver: Chrome,
        thread_id: int,
        thread_count: int,
        width: int = 510,
        height: int = 300,
    ) -> None:
        x_position = (thread_id - 1) % thread_count * width
        y_position = (thread_id - 1) // thread_count * height
        # driver.set_window_size(width, height)
        driver.set_window_position(x_position, y_position)


class DriverManipulator:
    def __init__(self, driver: Chrome) -> None:
        self.driver = driver

    def get(self, url: str) -> None:
        self.driver.get(url)

    def quit(self) -> None:
        self.driver.quit()

    def error_handler(self, func, *args, **kwargs):
        try:
            return func(*args)
        except se.ElementNotInteractableException:
            pass
        except se.ElementNotSelectableException:
            pass
        except se.ElementNotVisibleException:
            pass
        except se.TimeoutException:
            pass
        except se.WebDriverException:
            pass
        except:
            pass

    def wait(self, timeout: int = 10) -> WebDriverWait:
        return WebDriverWait(self.driver, timeout=timeout)

    def send_keys(
        self,
        strategy: str,
        target: str,
        keys_to_send: str,
        condition: Callable = EC.presence_of_element_located,
        timeout: int = 10,
    ) -> None:
        def foo():
            element = self.wait(timeout).until(condition((strategy, target)))
            try:
                element.clear()
            except:
                pass
            element.send_keys(keys_to_send)

        return self.error_handler(foo, target=target)

    def click_button(
        self,
        strategy: str,
        target: str,
        condition: Callable = EC.element_to_be_clickable,
        timeout: int = 10,
    ) -> None:
        def foo():
            element = self.wait(timeout).until(condition((strategy, target)))
            element.click()

        return self.error_handler(foo, target=target)

    def wait_for_element(
        self,
        strategy: str,
        target: str,
        condition: Callable = EC.presence_of_element_located,
        timeout: int = 10,
    ):
        def foo():
            element = self.wait(timeout).until(condition((strategy, target)))
            return element

        return self.error_handler(foo, target=target)

    def wait_for_elements(
        self,
        strategy: str,
        target: str,
        condition: Callable = EC.presence_of_all_elements_located,
        timeout: int = 10,
    ):
        def foo():
            element = self.wait(timeout).until(condition((strategy, target)))
            return element

        return self.error_handler(foo, target=target)


class FacebookManipulator(DriverManipulator):
    def __init__(self, driver):
        super().__init__(driver)

    def click_see_all(self):
        def foo():
            target = '//span[text()="See All"]'
            see_all_button = self.wait_for_element(By.XPATH, target, timeout=30)
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});",
                see_all_button,
            )
            self.click_button(By.XPATH, target)

        self.error_handler(foo)

    def close_modal(self):
        def foo():
            target = '//div[@aria-label="Close" and @role="button"]'
            self.click_button(By.XPATH, target)

        self.error_handler(foo)

    def get_page_name(self) -> Optional[str]:
        return self.wait_for_element(By.XPATH, "//h1").text.strip()

    def get_email(self) -> Optional[str]:
        path = '//a[starts-with(@href, "mailto:")]'
        mail_elements = self.wait_for_element(By.XPATH, path, timeout=5)
        if mail_elements:
            return mail_elements[0].get_attribute("href").replace("mailto:", "")
        else:
            regex = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
            found_emails = re.findall(regex, self.driver.page_source)
            if found_emails:
                return found_emails[0]

    def get_running_ads_status(self) -> Optional[str]:
        texts = [
            "Trang này đang chạy quảng cáo",
            "This Page is currently running ads",
        ]
        if any(x in self.driver.page_source for x in texts):
            return ADS_STATUS["YES"]
        else:
            return ADS_STATUS["NO"]

    def get_managing_country(self) -> Optional[str]:
        def foo():
            target = "div .x1516sgx.x13fuv20.x18ccme9"
            element = self.wait_for_elements(By.CSS_SELECTOR, target)[1]
            c_target = "div .x1gzmo1b"
            country_elm = element.find_element(By.CSS_SELECTOR, c_target)
            country = country_elm.text.strip()
            return country

        return self.error_handler(foo)


def save_to_txt(path: str = OUTPUT_PATH, data: dict[str, str] = None) -> None:
    if data is None:
        return

    # Kiểm tra xem file output có tồn tại không.
    # Nếu không, tạo một file text mới tại đường dẫn đã cho và thêm vào headers.
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, mode="w") as f:
            data_str = "uid|page_name|email|ads_status|country"
            f.write(data_str + "\n")

    # Thêm dữ liệu mới vào cuối file.
    # Trong mỗi dòng, dữ liệu của các cột được ngăn cách bởi dấu "|".
    with open(path, mode="a", encoding="utf-8") as f:
        data_str = "|".join([str(v) for _, v in data.items()])
        data_str.replace("\n", ",")
        f.write(data_str + "\n")


def scrape_one(uid: str, thread_id: int, thread_count: int):
    print(THREAD_MSG % (thread_id, uid, "Đang lấy thông tin..."))
    data = {
        "uid": uid,
        "page_name": None,
        "email": None,
        "ads_status": None,
        "country": None,
    }

    # ================================
    # Initialize the driver
    # ================================
    proxy = proxy_cli.get_new_proxy()
    if not proxy:
        print(THREAD_MSG % (thread_id, uid, "Không lấy được proxy mới"))
        proxy = proxy_cli.get_current_proxy()
    else:
        print(THREAD_MSG % (thread_id, uid, "Đã lấy được proxy mới"))
    print(THREAD_MSG % (thread_id, uid, f"Proxy: {proxy}"))
    chrome_cli = ChromeDriver()
    driver = chrome_cli.config(proxy=proxy)
    ChromePosition.config(driver, thread_id, thread_count)
    facebook = FacebookManipulator(driver)

    # ================================
    # Get data in main page
    # ================================
    facebook.get(FACEBOOK_PAGE_URL % uid)
    if ERROR_MSG in facebook.driver.page_source:
        print(THREAD_MSG % (thread_id, uid, "Không truy cập được page"))
        save_to_txt(OUTPUT_PATH, data)
        facebook.quit()
        return
    facebook.close_modal()
    data["page_name"] = facebook.get_page_name()
    data["email"] = facebook.get_email()

    # ================================
    # Get data in extended page
    # ================================
    facebook.get(FACEBOOK_ADS_URL % uid)
    if ERROR_MSG in facebook.driver.page_source:
        print(THREAD_MSG % (thread_id, uid, "Không truy cập được page mở rộng"))
        save_to_txt(OUTPUT_PATH, data)
        facebook.quit()
        return
    facebook.close_modal()
    data["ads_status"] = facebook.get_running_ads_status()
    facebook.click_see_all()
    data["country"] = facebook.get_managing_country()
    print(THREAD_MSG % (thread_id, uid, "Lấy thông tin thành công"))

    # Save data to output.txt
    save_to_txt(OUTPUT_PATH, data)

    # ================================
    # Quit the driver
    # ================================
    facebook.quit()


def scrape_all(uids: list[str], thread_count: int) -> None:
    with ThreadPoolExecutor(max_workers=thread_count) as executor:
        futures = {
            executor.submit(
                scrape_one, uid, i % thread_count, thread_count
            ): uid
            for i, uid in enumerate(uids)
        }

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Error occurred: {e}")


def main():
    try:
        uids = pd.read_csv(INPUT_PATH)["uid"].to_list()
        scrape_all(uids=uids, thread_count=MAX_THREAD)
    except FileNotFoundError:
        print("File %s không tồn tại" % INPUT_PATH)
    except KeyError:
        print("File %s không chứa cột 'uid'" % INPUT_PATH)
    except PermissionError:
        print("Check file %s" % OUTPUT_PATH)
    except:
        pass


if __name__ == "__main__":
    main()
