import os
import time
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

import selenium.common.exceptions as se
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# from selenium.webdriver.common.keys import Keys

from typing import Union, Optional, Callable


MAX_THREAD = os.cpu_count() + 4
THREAD_MSG = "[Thread #%03d] %s"

ROOT_DIR = os.path.dirname(__file__)
INPUT_PATH = os.path.join(ROOT_DIR, "input.csv")
OUTPUT_PATH = os.path.join(ROOT_DIR, "output.txt")

FACEBOOK_BASE_URL = "https://www.facebook.com"
FACEBOOK_PAGE_URL = FACEBOOK_BASE_URL + "/%s"
FACEBOOK_ADS_URL = FACEBOOK_PAGE_URL + "/about_profile_transparency"


class ProxyRequest:
    pass


class ChromeDriver:
    def config(self, **kwargs) -> Chrome:
        proxy = kwargs.get("proxy")
        options = Options()
        options.add_argument("--headless")
        driver = Chrome(options=options)
        return driver


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
        target = '//span[text()="See All"]'
        see_all_button = self.wait_for_element(By.XPATH, target)
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", see_all_button
        )
        self.click_button(By.XPATH, target)

    def close_modal(self):
        target = '//div[@aria-label="Close" and @role="button"]'
        self.click_button(By.XPATH, target)

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
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, mode="w") as f:
            data_str = "uid|page_name|email|ads_status|country"
            f.write(data_str + "\n")
    with open(path, mode="a", encoding="utf-8") as f:
        data_str = "|".join([str(v) for _, v in data.items()])
        f.write(data_str + "\n")


def scrape_one(uid, thread_number):
    print(THREAD_MSG % (thread_number, "starting scrape: %s" % uid))

    # ================================
    # Initialize the driver
    # ================================
    chrome_cli = ChromeDriver()
    driver = chrome_cli.config()
    facebook = FacebookManipulator(driver)

    # ================================
    # Get data in main page
    # ================================
    facebook.get(FACEBOOK_PAGE_URL % uid)
    facebook.close_modal()

    # ================================
    # Get data in extended page
    # ================================
    facebook.get(FACEBOOK_ADS_URL % uid)
    facebook.close_modal()
    facebook.click_see_all()
    managing_country = facebook.get_managing_country()
    print(THREAD_MSG % (thread_number, managing_country))

    # Save data to output.txt
    save_to_txt(OUTPUT_PATH, {"_": managing_country})

    # ================================
    # Quit the driver
    # ================================
    facebook.quit()


def scrape_all(uids: list[str], thread_count: int) -> None:
    with ThreadPoolExecutor(max_workers=thread_count) as executor:
        futures = {
            executor.submit(scrape_one, uid, i % thread_count): uid
            for i, uid in enumerate(uids)
        }

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Error occurred: {e}")


def main():
    uids = pd.read_csv(INPUT_PATH)["uid"].to_list()
    scrape_all(uids=uids, thread_count=MAX_THREAD)


if __name__ == "__main__":
    main()
