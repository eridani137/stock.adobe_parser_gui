import asyncio
import csv
import logging
import os
import random
import re
from typing import Tuple

from camoufox import AsyncCamoufox
from playwright.async_api import Page

import config
import utils
from configure_logger import configure

logger = logging.getLogger(__name__)
configure(logger)


async def goto_next_page(page: Page) -> Tuple[bool, bool]:
    max_retries = 7
    next_page_clicked = False
    is_complete = False
    selector = "xpath=//div[@id='pagination-element']/nav/span[last()]/button"

    for retry in range(max_retries):
        try:
            await asyncio.sleep(config.LONG_DELAY)
            next_page = await page.query_selector(selector)

            if next_page:
                if await next_page.is_disabled():
                    is_complete = True
                    break
                is_attached = await next_page.evaluate("el => el.isConnected")
                if not is_attached:
                    logger.warning(f"Элемент кнопки не прикреплен к DOM, повторная попытка {retry + 1}")
                    continue

                next_page_locator = page.locator(selector)

                await next_page_locator.click()

                next_page_clicked = True
                break
            else:
                logger.warning("Кнопка следующей страницы не найдена")
                is_complete = True  # Если кнопки нет, считаем, что это конец
                break

        except Exception as e:
            logger.warning(
                f"Ошибка при попытке перейти на следующую страницу (попытка {retry + 1}): {e}")
            if retry < max_retries - 1:
                await asyncio.sleep(2)
                continue
            else:
                logger.error("Не удалось перейти на следующую страницу после всех попыток")
                break

    return is_complete, next_page_clicked


class ImageParser:
    def __init__(self, archive_folder, batches_folder, log_callback=None):
        self.archive_folder = archive_folder
        self.batches_folder = batches_folder
        self.archive_names_file = "archive_name.csv"
        self.archive_links_file = "archive_links.csv"
        self.processed_links = set()
        self.existing_descriptions = set()
        self.log_callback = log_callback
        self.is_running = False

    def log(self, message, level="info"):
        if self.log_callback:
            self.log_callback(message, level)

        log_func = getattr(logger, level, logger.info)
        log_func(message)

    def ensure_folders(self):
        os.makedirs(self.archive_folder, exist_ok=True)
        os.makedirs(self.batches_folder, exist_ok=True)

    def load_processed_links(self):
        links_file = os.path.join(self.archive_folder, self.archive_links_file)
        self.processed_links.clear()
        if os.path.exists(links_file):
            try:
                with open(links_file, 'r', encoding='utf-8', newline='') as f:
                    reader = csv.reader(f)
                    next(reader, None)
                    for row in reader:
                        if row:
                            self.processed_links.add(row[0])
            except Exception as e:
                self.log(f"Ошибка загрузки архива ссылок: {e}")

    def load_existing_descriptions(self):
        names_file = os.path.join(self.archive_folder, self.archive_names_file)
        self.existing_descriptions.clear()
        if os.path.exists(names_file):
            try:
                with open(names_file, 'r', encoding='utf-8', newline='') as f:
                    reader = csv.reader(f)
                    next(reader, None)  # Пропустить заголовок
                    for row in reader:
                        # Убедимся, что в строке есть описание
                        if row and len(row) > 1:
                            self.existing_descriptions.add(row[1])
                self.log(f"Загружено {len(self.existing_descriptions)} уникальных описаний из архива.")
            except Exception as e:
                self.log(f"Ошибка загрузки архива описаний: {e}", "error")

    def filter_new_links(self, links):
        new_links = []
        for link in links:
            stripped_link = link.strip()
            if stripped_link and utils.is_valid_url(stripped_link) and stripped_link not in self.processed_links:
                new_links.append(stripped_link)
        return new_links

    def save_link_to_archive(self, link):
        links_file = os.path.join(self.archive_folder, self.archive_links_file)
        file_exists = os.path.exists(links_file)
        with open(links_file, 'a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            if not file_exists or os.path.getsize(links_file) == 0:
                writer.writerow(['Link'])
            writer.writerow([link])
        self.processed_links.add(link)

    def get_next_id(self):
        names_file = os.path.join(self.archive_folder, self.archive_names_file)
        max_id = 0
        if os.path.exists(names_file):
            try:
                with open(names_file, 'r', encoding='utf-8', newline='') as f:
                    reader = csv.reader(f)
                    next(reader, None)
                    for row in reader:
                        if row and len(row) > 0:
                            try:
                                current_id = int(row[0])
                                max_id = max(max_id, current_id)
                            except (ValueError, IndexError):
                                continue
            except Exception:
                pass
        return max_id + 1

    async def parse_single_url(self, url, depth=100):
        if not self.is_running:
            return
        self.log(f"Начинаю обработку: {url}")
        parsed_count = 0

        async with AsyncCamoufox(**config.BROWSER_OPTIONS) as browser_instance:
            page = await browser_instance.new_page()
            try:
                names_file_path = os.path.join(self.archive_folder, self.archive_names_file)
                file_exists = os.path.exists(names_file_path)

                with open(names_file_path, 'a', encoding='utf-8', newline='') as names_file:
                    names_writer = csv.writer(names_file, quoting=csv.QUOTE_ALL)
                    if not file_exists or os.path.getsize(names_file_path) == 0:
                        names_writer.writerow(['ID', 'Prompt'])

                    current_id = self.get_next_id()
                    await page.goto(url)

                    await asyncio.sleep(config.LONG_DELAY)

                    need_wait_selector = False

                    passed_pages = 0
                    while self.is_running and (depth == 0 or passed_pages < depth):
                        try:
                            await asyncio.sleep(3)

                            if need_wait_selector:
                                await asyncio.sleep(config.LONG_DELAY)

                            self.log(f"Обработка страницы #{passed_pages + 1}")

                            images = await page.query_selector_all("xpath=//div[@id='search-results']/div/div/a")
                            if not images:
                                self.log("На странице не найдено изображений.")
                                continue

                            for image in images:
                                if not self.is_running:
                                    break
                                try:
                                    image_href = await image.get_attribute("href")
                                    image_name_elem = await image.query_selector("xpath=/meta[@itemprop='name']")
                                    duration = await image.query_selector("xpath=/meta[@itemprop='duration']")
                                    if image_name_elem and image_href and not duration and not "/3d-assets/" in image_href and not "/templates/" in image_href:
                                        image_href += "?prev_url=detail"
                                        image_name_content = await image_name_elem.get_attribute("content")
                                        if image_name_content:
                                            name = image_name_content.replace('\n', ' ').strip()
                                            name = re.sub(r'\s+', ' ', name).strip()

                                            if name and name not in self.existing_descriptions:
                                                names_writer.writerow([current_id, name])
                                                names_file.flush()

                                                self.existing_descriptions.add(name)
                                                self.log(f"[{current_id}] {name}")

                                                parsed_count += 1
                                                current_id += 1
                                            else:
                                                pass
                                except Exception as e:
                                    self.log(f"Ошибка при обработке изображения: {e}")

                            passed_pages += 1

                            if 0 < depth <= passed_pages:
                                self.log(f"Достигнута заданная глубина обработки: {depth} страниц.")
                                break

                            is_complete, next_page_clicked = await goto_next_page(page)
                            need_wait_selector = True

                            if is_complete:
                                logger.info("Достигнута последняя доступная страница")
                                break

                            if not next_page_clicked:
                                logger.warning("Не удалось найти или нажать кнопку следующей страницы")
                                break

                        except Exception:
                            continue

                self.save_link_to_archive(url)
                self.log(f"Завершена обработка ссылки. Всего получено картинок: {parsed_count}")

            except Exception as e:
                self.log(f"Критическая ошибка при парсинге {url}: {e}")
            finally:
                await browser_instance.close()

    async def process_links(self, links, depth=100):
        self.ensure_folders()
        self.load_processed_links()
        self.load_existing_descriptions()

        new_links = self.filter_new_links(links)

        if not new_links:
            self.log("Все ссылки уже были обработаны ранее.")
            return

        self.log(f"К обработке: {len(new_links)} новых ссылок.")
        self.is_running = True
        for i, link in enumerate(new_links):
            if not self.is_running:
                break
            self.log(f"Обрабатываю ссылку {i + 1} из {len(new_links)}: {link}")
            await self.parse_single_url(link, depth)

        if self.is_running:
            self.log("Обработка всех ссылок завершена.")
        self.is_running = False

    def stop_processing(self):
        self.is_running = False
        self.log("Получен сигнал остановки.")

    def create_batches(self, num_batches, batch_size, remove_from_archive=False):
        names_file = os.path.join(self.archive_folder, self.archive_names_file)
        if not os.path.exists(names_file):
            self.log("Архив описаний не найден.")
            return 0

        all_descriptions = []
        try:
            with open(names_file, 'r', encoding='utf-8', newline='') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                for row in reader:
                    if row and len(row) > 1:
                        all_descriptions.append(row)
        except Exception as e:
            self.log(f"Ошибка чтения архива: {e}")
            return 0

        if remove_from_archive and len(all_descriptions) < num_batches * batch_size:
            self.log(f"В архиве недостаточно данных для создания {num_batches} партий по {batch_size} с удалением.")
            return 0
        if not remove_from_archive and len(all_descriptions) < batch_size:
            self.log(f"В архиве недостаточно данных для создания партий размером {batch_size}.")
            return 0

        self.ensure_folders()
        batches_created = 0
        available_data = list(all_descriptions)
        random.shuffle(available_data)

        for i in range(num_batches):
            if len(available_data) < batch_size:
                self.log(f"Недостаточно данных для создания партии {i + 1}.")
                break

            batch_data = available_data[:batch_size]

            if remove_from_archive:
                available_data = [item for item in available_data if item not in batch_data]

            batch_file = os.path.join(self.batches_folder, f"batch_{i + 1}.csv")
            try:
                with open(batch_file, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f, quoting=csv.QUOTE_ALL)
                    writer.writerow(['ID', 'Prompt'])
                    writer.writerows(batch_data)
                batches_created += 1
                self.log(f"Создана партия {i + 1}: {len(batch_data)} записей.")
            except Exception as e:
                self.log(f"Ошибка создания партии {i + 1}: {e}")

        if remove_from_archive:
            try:
                with open(names_file, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f, quoting=csv.QUOTE_ALL)
                    writer.writerow(header)
                    writer.writerows(available_data)
                self.log(f"Из архива удалено {len(all_descriptions) - len(available_data)} записей.")
            except Exception as e:
                self.log(f"Ошибка при обновлении файла архива: {e}")

        return batches_created
