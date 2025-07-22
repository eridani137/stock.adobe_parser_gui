import asyncio
import logging
from datetime import datetime

import flet as ft

import config
from ImageParser import ImageParser
from configure_logger import configure

logger = logging.getLogger(__name__)
configure(logger)


async def main(page: ft.Page):
    page.title = "stock.adobe"
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
            if e.control.data == "archive":
                archive_path.value = e.path
            elif e.control.data == "batches":
                batches_path.value = e.path
            page.update()

    file_picker = ft.FilePicker(on_result=on_dialog_result)
    page.overlay.append(file_picker)

    def add_log(message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_list.controls.append(
            ft.Text(f"[{timestamp}] {message}", size=12, color=ft.Colors.WHITE)
        )
        if len(log_list.controls) > 100:
            log_list.controls = log_list.controls[-100:]
        log_list.update()

    async def start_processing(e):
        nonlocal parser, processing_task
        if processing_task and not processing_task.done():
            add_log("Обработка уже запущена.")
            return

        if not links_input.value.strip():
            add_log("Ошибка: Введите хотя бы одну ссылку.")
            return
        try:
            depth = int(depth_input.value)
            if not 1 <= depth <= 100:
                add_log("Ошибка: Глубина обработки должна быть от 1 до 100.")
                return
        except ValueError:
            add_log("Ошибка: Глубина обработки должна быть числом.")
            return

        links = [line.strip() for line in links_input.value.split('\n') if line.strip()]
        if not links:
            add_log("Ошибка: Не найдено валидных ссылок для обработки.")
            return

        parser = ImageParser(
            archive_folder=archive_path.value,
            batches_folder=batches_path.value,
            log_callback=add_log
        )

        start_btn.visible = False
        stop_btn.visible = True
        create_batches_btn.disabled = True
        page.update()

        add_log("Начинаю обработку ссылок...")
        processing_task = asyncio.create_task(parser.process_links(links, depth))
        try:
            await processing_task
        except asyncio.CancelledError:
            add_log("Обработка остановлена пользователем.")
        except Exception as ex:
            add_log(f"Произошла ошибка во время обработки: {ex}")
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
        add_log("Отправлен сигнал остановки...")

    def create_batches_click(e):
        try:
            num_batches = int(num_batches_input.value)
            batch_size = int(batch_size_input.value)
            if not 1 <= num_batches <= 1000:
                add_log("Ошибка: Количество партий должно быть от 1 до 1000.")
                return
            if not 1 <= batch_size <= 10000:
                add_log("Ошибка: Количество строк в партии должно быть от 1 до 10 000.")
                return
        except ValueError:
            add_log("Ошибка: Параметры партий должны быть числами.")
            return

        temp_parser = ImageParser(
            archive_folder=archive_path.value,
            batches_folder=batches_path.value,
            log_callback=add_log
        )
        add_log("Начинаю создание партий...")
        created_count = temp_parser.create_batches(
            num_batches=num_batches,
            batch_size=batch_size,
            remove_from_archive=remove_from_archive_cb.value
        )
        if created_count > 0:
            add_log(f"Успешно создано {created_count} партий.")
        else:
            add_log("Не удалось создать партии. Проверьте лог на наличие ошибок.")

    links_input = ft.TextField(label="Ссылки (по одной на строку)", multiline=True, min_lines=6, max_lines=8,
                               border_color=config.BORDER_COLOR)
    depth_input = ft.TextField(label="Глубина (страниц)", value="100", width=150, keyboard_type=ft.KeyboardType.NUMBER,
                               border_color=config.BORDER_COLOR)
    archive_path = ft.TextField(label="Папка для архива", value="./archive/", expand=True, read_only=True,
                                border_color=config.BORDER_COLOR)
    archive_browse_btn = ft.IconButton(icon=ft.Icons.FOLDER_OPEN, on_click=lambda _: file_picker.get_directory_path(
        dialog_title="Выберите папку для архива"), data="archive", tooltip="Выбрать папку")
    num_batches_input = ft.TextField(label="Количество партий", value="100", width=200,
                                     keyboard_type=ft.KeyboardType.NUMBER, border_color=config.BORDER_COLOR)
    batch_size_input = ft.TextField(label="Строк в партии", value="1000", width=200,
                                    keyboard_type=ft.KeyboardType.NUMBER, border_color=config.BORDER_COLOR)
    remove_from_archive_cb = ft.Checkbox(label="Удалять строки из архива", value=False)
    batches_path = ft.TextField(label="Папка для сохранения партий", value="./batches/", expand=True, read_only=True,
                                border_color=config.BORDER_COLOR)
    batches_browse_btn = ft.IconButton(icon=ft.Icons.FOLDER_OPEN, on_click=lambda _: file_picker.get_directory_path(
        dialog_title="Выберите папку для партий"), data="batches", tooltip="Выбрать папку")
    log_list = ft.ListView(
        expand=True,
        spacing=2,
        padding=ft.padding.all(10),
        auto_scroll=True
    )

    start_btn = ft.ElevatedButton("Запуск", on_click=start_processing, width=100, icon=ft.Icons.PLAY_ARROW,
                                  bgcolor=ft.Colors.PRIMARY, color=ft.Colors.WHITE)
    stop_btn = ft.ElevatedButton("Остановить", on_click=stop_processing, width=150, icon=ft.Icons.STOP,
                                 bgcolor=ft.Colors.RED,
                                 color=ft.Colors.WHITE, visible=False)
    create_batches_btn = ft.ElevatedButton("Сформировать", on_click=create_batches_click,
                                           icon=ft.Icons.CREATE_NEW_FOLDER, bgcolor=ft.Colors.PRIMARY,
                                           color=ft.Colors.WHITE)

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
                                padding=15
                            )
                        ),
                        ft.Row([start_btn, stop_btn], alignment=ft.MainAxisAlignment.CENTER, spacing=20)
                    ],
                    spacing=15
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
                                    ft.Row([num_batches_input, batch_size_input], spacing=10),
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
                    spacing=15
                )
            ),
        ],
        expand=False,
    )

    page.add(
        ft.Column(
            controls=[
                tabs,
                ft.Text("Лог выполнения", weight=ft.FontWeight.BOLD),
                ft.Container(
                    content=log_list,
                    height=200,
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=8
                )
            ],
            expand=True,
            spacing=10
        )
    )

    add_log("Приложение запущено и готово к работе")

    # page.add(
    #     ft.Column(
    #         controls=[
    #             tabs,
    #             ft.Divider(height=5, color="transparent"),
    #             ft.Text("Лог выполнения", weight=ft.FontWeight.BOLD),
    #             ft.Container(
    #                 content=log_output
    #             )
    #         ],
    #         expand=True,
    #         spacing=5
    #     )
    # )


if __name__ == "__main__":
    ft.app(target=main)
