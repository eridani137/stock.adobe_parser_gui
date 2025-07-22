import asyncio
import logging
import os
from datetime import datetime

import flet as ft

import config
from ImageParser import ImageParser
from configure_logger import configure

logger = logging.getLogger(__name__)
configure(logger)


async def main(page: ft.Page):
    page.title = "stock.adobe"
    page.window.height = 895
    page.window.center()

    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(
        color_scheme=ft.ColorScheme(
            primary=ft.Colors.DEEP_PURPLE_200,
            on_surface=ft.Colors.WHITE,
            on_background=ft.Colors.WHITE
        )
    )
    page.update()

    parser = None
    processing_task = None

    def on_dialog_result(e: ft.FilePickerResultEvent):
        if e.path:
            abs_path = os.path.abspath(e.path)
            if e.control.data == "archive":
                archive_path.value = abs_path
            elif e.control.data == "batches":
                batches_path.value = abs_path
            page.update()

    file_picker = ft.FilePicker(on_result=on_dialog_result)
    page.overlay.append(file_picker)

    def add_log(message, level="info"):
        log_level_str = level.lower()
        if log_level_str == "error":
            logger.error(message)
        elif log_level_str == "warning":
            logger.warning(message)
        elif log_level_str == "debug":
            logger.debug(message)
        else:
            logger.info(message)

        level_colors = {
            "debug": ft.Colors.GREY,
            "info": ft.Colors.GREEN,
            "warning": ft.Colors.YELLOW,
            "error": ft.Colors.RED,
        }
        timestamp = datetime.now().strftime("%H:%M:%S")

        color = level_colors.get(level.lower(), ft.Colors.WHITE)
        log_list.controls.append(
            ft.Text(f"[{timestamp}] {message}", size=15, color=color)
        )

        if len(log_list.controls) > 100:
            log_list.controls = log_list.controls[-100:]
        log_list.update()

    interactive_controls = []

    def set_controls_enabled(enabled: bool):
        for ctrl in interactive_controls:
            ctrl.disabled = not enabled
        tabs.disabled = not enabled
        page.update()

    async def start_processing(e):
        nonlocal parser, processing_task
        if processing_task and not processing_task.done():
            add_log("Обработка уже запущена.", "warning")
            return

        if not links_input.value.strip():
            add_log("Ошибка: Введите хотя бы одну ссылку.", "error")
            return
        try:
            depth = int(depth_input.value)
            if not 1 <= depth <= 100:
                add_log("Ошибка: Глубина обработки должна быть от 1 до 100.", "error")
                return
        except ValueError:
            add_log("Ошибка: Глубина обработки должна быть числом.", "error")
            return

        links = [line.strip() for line in links_input.value.split('\n') if line.strip()]
        if not links:
            add_log("Ошибка: Не найдено валидных ссылок для обработки.", "error")
            return

        for folder in [archive_path.value, batches_path.value]:
            try:
                os.makedirs(folder, exist_ok=True)
                add_log(f"Папка создана/существует: {folder}", "debug")
            except Exception as ex:
                add_log(f"Ошибка при создании папки {folder}: {ex}", "error")
                return

        parser = ImageParser(
            archive_folder=archive_path.value,
            batches_folder=batches_path.value,
            log_callback=add_log
        )

        set_controls_enabled(False)
        start_btn.visible = False
        stop_btn.visible = True
        create_batches_btn.disabled = True
        page.update()

        add_log("Начинаю обработку ссылок...", "info")
        processing_task = asyncio.create_task(parser.process_links(links, depth))
        try:
            await processing_task
        except asyncio.CancelledError:
            add_log("Обработка остановлена пользователем.", "warning")
        except Exception as ex:
            add_log(f"Произошла ошибка во время обработки: {ex}", "error")
        finally:
            start_btn.visible = True
            stop_btn.visible = False
            create_batches_btn.disabled = False
            page.update()

    async def stop_processing(e):
        nonlocal parser, processing_task
        if parser:
            parser.stop_processing()
        if processing_task and not processing_task.done():
            processing_task.cancel()
        add_log("Отправлен сигнал остановки...", "warning")
        set_controls_enabled(True)
        stop_btn.visible = False
        start_btn.visible = True
        page.update()

    def create_batches_click(e):
        try:
            num_batches = int(num_batches_input.value)
            batch_size = int(batch_size_input.value)
            if not 1 <= num_batches <= 1000:
                add_log("Ошибка: Количество партий должно быть от 1 до 1000.", "error")
                return
            if not 1 <= batch_size <= 10000:
                add_log("Ошибка: Количество строк в партии должно быть от 1 до 10 000.", "error")
                return
        except ValueError:
            add_log("Ошибка: Параметры партий должны быть числами.", "error")
            return

        temp_parser = ImageParser(
            archive_folder=archive_path.value,
            batches_folder=batches_path.value,
            log_callback=add_log
        )
        add_log("Начинаю создание партий...", "info")
        created_count = temp_parser.create_batches(
            num_batches=num_batches,
            batch_size=batch_size,
            remove_from_archive=remove_from_archive_cb.value
        )
        if created_count > 0:
            add_log(f"Успешно создано {created_count} партий.", "info")
        else:
            add_log("Не удалось создать партии. Проверьте лог на наличие ошибок.", "error")

    links_input = ft.TextField(label="Ссылки (по одной на строку)", multiline=True, min_lines=6, max_lines=8,
                               border_color=config.BORDER_COLOR)
    depth_input = ft.TextField(label="Глубина (страниц)", value="100", width=150, keyboard_type=ft.KeyboardType.NUMBER,
                               border_color=config.BORDER_COLOR)
    archive_path = ft.TextField(label="Папка для архива", value=os.path.abspath("./archive/"), expand=True,
                                read_only=True,
                                border_color=config.BORDER_COLOR)
    archive_browse_btn = ft.IconButton(icon=ft.Icons.FOLDER_OPEN, on_click=lambda _: file_picker.get_directory_path(
        dialog_title="Выберите папку для архива"), data="archive", tooltip="Выбрать папку")
    num_batches_input = ft.TextField(label="Количество партий", value="100", width=200,
                                     keyboard_type=ft.KeyboardType.NUMBER, border_color=config.BORDER_COLOR)
    batch_size_input = ft.TextField(label="Строк в партии", value="1000", width=200,
                                    keyboard_type=ft.KeyboardType.NUMBER, border_color=config.BORDER_COLOR)
    remove_from_archive_cb = ft.Checkbox(label="Удалять строки из архива", value=False)
    batches_path = ft.TextField(label="Папка для сохранения партий", value=os.path.abspath("./batches/"), expand=True,
                                read_only=True,
                                border_color=config.BORDER_COLOR)
    batches_browse_btn = ft.IconButton(icon=ft.Icons.FOLDER_OPEN, on_click=lambda _: file_picker.get_directory_path(
        dialog_title="Выберите папку для партий"), data="batches", tooltip="Выбрать папку")
    log_list = ft.ListView(
        expand=True,
        spacing=2,
        padding=ft.padding.all(5),
        auto_scroll=True,
    )

    start_btn = ft.ElevatedButton("Запуск",
                                  on_click=start_processing,
                                  width=120,
                                  icon=ft.Icons.PLAY_ARROW,
                                  bgcolor=ft.Colors.PRIMARY,
                                  color=ft.Colors.BLACK,
                                  style=ft.ButtonStyle(
                                      shape=ft.RoundedRectangleBorder(radius=10),
                                      padding=ft.padding.all(15)
                                  ))
    stop_btn = ft.ElevatedButton("Остановить",
                                 on_click=stop_processing,
                                 width=150,
                                 icon=ft.Icons.STOP,
                                 bgcolor=ft.Colors.RED,
                                 color=ft.Colors.WHITE,
                                 visible=False,
                                 style=ft.ButtonStyle(
                                     shape=ft.RoundedRectangleBorder(radius=10),
                                     padding=ft.padding.all(15)
                                 ))
    create_batches_btn = ft.ElevatedButton("Сформировать",
                                           on_click=create_batches_click,
                                           icon=ft.Icons.CREATE_NEW_FOLDER,
                                           bgcolor=ft.Colors.PRIMARY,
                                           color=ft.Colors.BLACK,
                                           style=ft.ButtonStyle(
                                               shape=ft.RoundedRectangleBorder(radius=10),
                                               padding=ft.padding.all(15)
                                           ))

    tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=[
            ft.Tab(
                text="Парсинг",
                icon=ft.Icons.DOWNLOAD,
                content=ft.Column(
                    controls=[
                        ft.Card(
                            margin=ft.margin.only(top=10),
                            content=ft.Container(
                                content=ft.Column([
                                    ft.Text("1. Введите ссылки и глубину обработки", weight=ft.FontWeight.BOLD),
                                    links_input,
                                    depth_input,
                                ]),
                                padding=15,
                            )
                        ),
                        ft.Card(
                            content=ft.Container(
                                content=ft.Column([
                                    ft.Text("2. Укажите, куда сохранять архив", weight=ft.FontWeight.BOLD),
                                    ft.Row([archive_path, archive_browse_btn])
                                ]),
                                padding=7
                            )
                        ),
                        ft.Row([start_btn, stop_btn], alignment=ft.MainAxisAlignment.CENTER, spacing=7)
                    ],
                    spacing=7
                )
            ),
            ft.Tab(
                text="Работа с партиями",
                icon=ft.Icons.FOLDER_COPY,
                content=ft.Column(
                    controls=[
                        ft.Card(
                            margin=ft.margin.only(top=10),
                            content=ft.Container(
                                content=ft.Column([
                                    ft.Text("1. Настройте параметры партий", weight=ft.FontWeight.BOLD),
                                    ft.Row([num_batches_input, batch_size_input], spacing=7),
                                    remove_from_archive_cb
                                ]),
                                padding=15
                            )
                        ),
                        ft.Card(
                            content=ft.Container(
                                content=ft.Column([
                                    ft.Text("2. Укажите, куда сохранять партии", weight=ft.FontWeight.BOLD),
                                    ft.Row([batches_path, batches_browse_btn])
                                ]),
                                padding=15
                            )
                        ),
                        ft.Row([create_batches_btn], alignment=ft.MainAxisAlignment.CENTER)
                    ],
                    spacing=7
                )
            ),
        ]
    )

    interactive_controls.extend([
        links_input,
        depth_input,
        archive_browse_btn,
        num_batches_input,
        batch_size_input,
        remove_from_archive_cb,
        batches_browse_btn,
        create_batches_btn,
        tabs
    ])

    page.add(
        ft.Column(
            expand=True,
            spacing=7,
            controls=[
                ft.Container(
                    content=tabs,
                    expand=True,
                ),
                ft.Container(
                    content=log_list,
                    height=300,
                    border=ft.border.all(1, ft.Colors.PRIMARY),
                    border_radius=8,
                )
            ]
        )
    )


if __name__ == "__main__":
    ft.app(target=main)
