# =============================================================================
# PowerShell Build Script - The Final Victorious Version
#
# Описание:
#   Включает ВСЕ найденные зависимости для camoufox.
# =============================================================================

# --- НАСТРОЙКИ СБОРКИ ---

$AppName = "AdobeStockParser"
# ВАЖНО: Укажите здесь ваше правильное имя главного файла!
$MainScript = "stock.adobe_parser_gui.py"
$IconFile = ""

# --- НАЧАЛО ПРОЦЕССА СБОРКИ ---

Clear-Host
Write-Host "🚀 Начинаю сборку для '$AppName' по ВАШЕЙ проверенной методике..." -ForegroundColor Cyan

# 0. Проверки
Write-Host "❗ ВАЖНО: Для этого скрипта требуется PyInstaller. Выполните 'pip install pyinstaller'." -ForegroundColor Yellow
Write-Host "❗ Не забудьте выполнить 'playwright install' для корректной работы .exe." -ForegroundColor Yellow

# 1. Автоопределение 'site-packages'
Write-Host "🔍 Автоматически определяю путь к 'site-packages'..."
try {
    # Заменяем одинарные бэкслэши на двойные для корректной вставки в .spec файл
    $sitePackagesPath = (python -c "from sysconfig import get_paths; print(get_paths()['purelib'])") -replace '\\', '\\'
    if (-not $sitePackagesPath -or -not (Test-Path $sitePackagesPath)) { throw "Путь не найден." }
    Write-Host "✅ Путь найден: $sitePackagesPath" -ForegroundColor Green
}
catch {
    Write-Host "❌ ОШИБКА: Не удалось найти 'site-packages'." -ForegroundColor Red
    exit 1
}

# 2. Очистка
Write-Host "🧹 Очищаю старые папки и файлы..."
Remove-Item -Path ".\dist", ".\build", ".\$($AppName).spec" -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "✅ Очистка завершена."

# --- ЭТАП 1: ГЕНЕРАЦИЯ .SPEC ФАЙЛА С НУЛЯ ---
Write-Host "⚙️  ЭТАП 1: Генерирую финальный .spec файл..."

# Списки зависимостей
$addData = @(
    "('ImageParser.py', '.'),",
    "('config.py', '.'),",
    "('utils.py', '.'),",
    "('configure_logger.py', '.'),",
    "('$($sitePackagesPath)\\browserforge\\fingerprints\\data', 'browserforge\\fingerprints\\data'),",
    "('$($sitePackagesPath)\\browserforge\\headers\\data', 'browserforge\\headers\\data'),",
    "('$($sitePackagesPath)\\camoufox\\browserforge.yml', 'camoufox'),",
    "('$($sitePackagesPath)\\camoufox\\warnings.yml', 'camoufox'),",
    # *** ПОСЛЕДНЕЕ ИСПРАВЛЕНИЕ ЗДЕСЬ ***
    "('$($sitePackagesPath)\\camoufox\\territoryInfo.xml', 'camoufox'),",
    "('$($sitePackagesPath)\\language_tags\\data', 'language_tags\\data')"
)

$hiddenImports = @(
    "'camoufox',",
    "'browserforge',",
    "'language_tags',",
    "'playwright',",
    "'patchright'"
)

# Создаем содержимое .spec файла
$specContent = @"
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['$MainScript'],
    pathex=[],
    binaries=[],
    datas=[
$($addData -join "`n")
    ],
    hiddenimports=[
$($hiddenImports -join "`n")
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['undetected_playwright'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='$AppName',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='$IconFile',
)
"@

$SpecFile = "$($AppName).spec"
$specContent | Set-Content -Path $SpecFile
Write-Host "✅ Финальный $SpecFile успешно создан." -ForegroundColor Green


# --- ЭТАП 2: СБОРКА ИЗ .SPEC ФАЙЛА ---
Write-Host "📦 ЭТАП 2: Запускаю PyInstaller для сборки из $SpecFile..."
& pyinstaller --noconfirm --clean $SpecFile

# Проверка результата
if ($LASTEXITCODE -eq 0) {
    Write-Host "🏆🏆🏆 СБОРКА УСПЕШНО ЗАВЕРШЕНА! 🏆🏆🏆" -ForegroundColor Green
    $ExePath = Join-Path -Path $PSScriptRoot -ChildPath "dist\$AppName.exe"
    Write-Host "Ваш файл готов: $ExePath"
    Invoke-Item (Join-Path -Path $PSScriptRoot -ChildPath "dist")
} else {
    Write-Host "❌ ОШИБКА СБОРКИ. Проверьте лог PyInstaller выше на наличие ошибок." -ForegroundColor Red
}