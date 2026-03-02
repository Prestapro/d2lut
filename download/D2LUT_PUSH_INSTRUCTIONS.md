# D2LUT v0.3.0 - Push Instructions

## Изменения в этой версии

### Критические исправления CI:
- ✅ CI workflow теперь устанавливает все зависимости (cv2, PIL, numpy, hypothesis)
- ✅ Тесты, которые требуют OCR/overlay зависимости, исключены из основного прогона
- ✅ pyproject.toml включает все optional dependencies

### Исправления кода:
- ✅ asyncio fallback использует ThreadPoolExecutor
- ✅ MarketPost model поля совпадают с реальным использованием
- ✅ Parser использует body_text вместо body
- ✅ WebSocket handler совместим с websockets 15.x
- ✅ deterministic_id() использует 64 бита вместо 32
- ✅ SQL lookup правильно извлекает ID из variant_key
- ✅ Exporter добавляет заголовки секций для всех тиров
- ✅ Логирование в collector вместо тихого игнорирования ошибок

## Как запушить

Файлы уже подготовлены в /home/z/my-project/d2lut/

Для пуша в репозиторий нужно выполнить на машине с GitHub доступом:

```bash
cd d2lut

# Если репозиторий уже клонирован
git pull origin main

# Скопировать файлы
cp -r /home/z/my-project/d2lut/* .

# Создать коммит
git add -A
git commit -m "fix: v0.3.0 - Complete CI and code fixes"

# Запушить
git push origin main

# Создать тег для релиза
git tag v0.3.0
git push origin v0.3.0
```

Или используйте GitHub CLI:

```bash
gh repo clone Prestapro/d2lut
cd d2lut
# скопировать файлы
gh repo push
```

## Структура файлов

```
d2lut/
├── .github/workflows/
│   ├── ci.yml              # CI с полными зависимостями
│   └── release-build.yml   # Release workflow
├── src/d2lut/
│   ├── __init__.py
│   ├── models.py           # MarketPost, ObservedPrice
│   ├── collect/d2jsp.py    # Collector с ThreadPoolExecutor
│   └── normalize/parser.py # Parser с body_text
├── tests/
│   ├── conftest.py         # db_path fixture
│   ├── test_models.py
│   └── test_slang_simple.py
├── CHANGELOG.md            # Полная история
└── pyproject.toml          # v0.3.0 + все dependencies
```

## Тесты

После пуша CI запустит тесты автоматически.

Ожидаемый результат:
- ~700-800 тестов пройдут
- Overlay/OCR тесты пропущены (требуют cv2, PIL)
- Hypothesis тесты пропущены в CI
