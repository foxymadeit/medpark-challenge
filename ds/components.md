# Components (scan)

**Источник:** страницы COMPONENTS (`1:10`) и PATTERNS (`1:12`), файл `QYy8I55YDJRojTI6UCZENa`
**Кол-во компонентов и наборов:** 25 на COMPONENTS, 30 на PATTERNS
**Used in:** «нет на экранах» значит 0 инстансов на странице Screens на 2026-11-04

## Действия

### Button
- **Назначение:** основная кнопка. S 40, M 44, L 48
- **Варианты:** Size: S | M | L; Style: Primary | Ink | Secondary | Ghost | Danger | Danger text; State: Default | Hover | Disabled
- **Node ID:** `11:82`

### Icon button
- **Назначение:** квадратная кнопка с иконкой, всегда с aria-label
- **Варианты:** Size: 32 | 40; Style: Default | Solid | Confirm; State: Default | Hover | Disabled
- **Node ID:** `11:141`

### Chip
- **Назначение:** выбираемая плашка
- **Варианты:** Size: Md | Sm; State: Default | Hover | Selected; Icon (опционально), Icon swap
- **Node ID:** `12:84`
- **Used in:** 01c Your meetings

### Review actions
- **Назначение:** кнопки футера Review, Preview и Send
- **Варианты:** State: Pending | Ready
- **Node ID:** `39:177`
- **Used in:** футеры 04–07, 04b

## Ввод

### Input
- **Назначение:** однострочное поле
- **Варианты:** Size: Default | Inline; State: Placeholder | Filled | Focus | Error
- **Node ID:** `12:56`

### Field
- **Назначение:** поле с подписью и подсказкой
- **Варианты:** State: Default | Error
- **Node ID:** `16:32`

### Selection control
- **Назначение:** чекбокс и радио, чёрные в выбранном состоянии
- **Варианты:** Type: Checkbox | Radio; State: Off | On | Indeterminate | Disabled (последние два только у Checkbox)
- **Node ID:** `12:67`

### Search
- **Назначение:** поле поиска
- **Варианты:** State: Default | Focus
- **Node ID:** `16:45`

### Dropdown
- **Назначение:** селект. Compact 36, Field 40
- **Варианты:** Size: Compact | Field; State: Default | Open
- **Node ID:** `16:78`

### Dropdown option
- **Назначение:** строка меню
- **Варианты:** State: Default | Active | Selected
- **Node ID:** `16:79`
- **Used in:** нет на экранах

### Emails field
- **Назначение:** поле участников с чипами
- **Варианты:** State: Default | Focus
- **Node ID:** `17:88`
- **Used in:** 01 Start, ширина 1152

### Email chip
- **Назначение:** участник внутри поля, с крестиком
- **Варианты:** одиночный
- **Node ID:** `17:55`

### Owner picker
- **Назначение:** ответственный в строке задачи
- **Варианты:** Mode: Edit | Read; State: Default | Hover
- **Node ID:** `17:109`
- **Used in:** нет на экранах. Панель на 05 собрана из `Person`

### Date chip, Date picker, Date picker day
- **Назначение:** выбор даты
- **Варианты:** Date chip State: Default | Hover; день State: Default | Hover | Selected | Muted
- **Node ID:** `16:115`, `23:120`, `23:119`

### Segmented item, Segmented control
- **Назначение:** переключатель
- **Варианты:** Size: M | L; State: Default | Selected
- **Node ID:** `13:43`, `13:44`

### Dropzone, File row, Start tile
- **Назначение:** запуск записи и загрузка файла
- **Варианты:** File row State: Uploaded | Uploading; Start tile Type: Record | Upload, State: Default | Drag-over | Hover
- **Node ID:** `292:806`, `292:797`, `25:82`

## Навигация

### Topbar
- **Назначение:** шапка. App в приложении, Access на экранах входа (без логотипа и аккаунта)
- **Варианты:** Type: App | Access
- **Node ID:** `327:597`

### Sidenav, Nav item
- **Назначение:** меню слева, 240, порядок пунктов задан в компоненте
- **Варианты:** Nav item State: Default | Hover | Active
- **Node ID:** `22:28`, `17:46`

### Page header
- **Назначение:** заголовок страницы
- **Варианты:** Type: Section | New meeting
- **Node ID:** `22:87`

## Данные

### Tag, Status tag
- **Назначение:** метка «me» и статус в History
- **Варианты:** Status: Needs review | Processing | Sent
- **Node ID:** `14:150`, `14:165`

### Avatar
- **Назначение:** инициалы. S 24, M 32, L 56. Белое кольцо снаружи: 1, 1.5, 2
- **Варианты:** Size: S | M | L; Tone: rose | peach | amber | green | teal | blue | violet | stone | ink
- **Node ID:** `15:100`

### Person
- **Назначение:** человек в таблице и в панели получателей (там с отступами 8 сверху и снизу)
- **Варианты:** Email: No | Yes
- **Node ID:** `108:168`

### Progress bar
- **Назначение:** прогресс, процент задан вариантом
- **Варианты:** Value: 5 | 30 (Tone=Success, Processing); 33 | 67 | 100 (Tone=Action, Onboarding)
- **Node ID:** `292:2405`

### Participant row, Participants header
- **Назначение:** таблица участников, 1152, колонки 640 / 256 / 208 / 48
- **Варианты:** State: Default | Hover | Me | Me read-only
- **Node ID:** `41:230`, `54:399`

### History row, History header
- **Назначение:** таблица History, 1152
- **Варианты:** State: Default | Hover | Needs review | Processing
- **Node ID:** `47:448`, `270:1966`

### Action item row — Edit
- **Назначение:** строка задачи в Review
- **Варианты:** Mode: Edit | Read
- **Node ID:** `231:932`

### Summary
- **Назначение:** блок Summary в карточке Review
- **Варианты:** одиночный
- **Node ID:** `36:95`

### Transcript line
- **Назначение:** реплика в расшифровке
- **Варианты:** Content: Plain | Keyword
- **Node ID:** `40:180`
- **Used in:** 04c Transcript

### Template card
- **Назначение:** шаблон встречи, 564
- **Варианты:** одиночный, свойства Title, Meta, Icon, People
- **Node ID:** `43:190`

### Recorder, Live details, Live details / Voice, Live details / Language, Waveform
- **Назначение:** экран записи
- **Варианты:** Recorder State: Recording | Paused; Voice State: Speaking | Heard | Not matched | Not heard; Language State: Active | Default
- **Node ID:** `84:717`, `84:718`, `84:523`, `84:485`, `84:408`

### People panel, People panel / Add participant
- **Назначение:** панель получателей на Review
- **Варианты:** Add participant State: Default | Hover | Adding
- **Node ID:** `38:112`, `38:111`

### Settings section
- **Назначение:** секция настроек
- **Варианты:** одиночный
- **Node ID:** `59:391`
- **Used in:** 12 Settings, ширина 1104

## Фидбэк

### Form alert
- **Назначение:** красный блок ошибки в форме
- **Варианты:** одиночный
- **Node ID:** `17:47`
- **Used in:** 01e Log in error, 03a Processing failed

### Empty state
- **Назначение:** пустое состояние
- **Варианты:** одиночный
- **Node ID:** `17:110`
- **Used in:** 10d Only you

## Модалки

### Modal / Confirm
- **Назначение:** диалог подтверждения 560: заголовок, текст, необязательная заметка, Cancel и кнопка действия
- **Варианты:** Tone: Danger | Primary; Title, Lead, Note, Has note
- **Node ID:** `345:673`
- **Used in:** 10b, 10c, 11c

### Modal / Replace person
- **Назначение:** замена человека в шаблоне, список от края до края
- **Варианты:** одиночный
- **Node ID:** `345:674`
- **Used in:** 11b

### Template person
- **Назначение:** строка людей в редакторе шаблона, 576×48
- **Варианты:** State: In template | Suggested; Name, Role, Me
- **Node ID:** `345:776`
- **Used in:** Modal / New template

### Modal / Preview MoM, New participant, New template, Profile
- **Назначение:** модалки. Preview 1152, New template 640, остальные 560
- **Варианты:** одиночные
- **Node ID:** `267:1909`, `52:370`, `50:334`, `125:710`
- **Used in:** Profile нет на экранах

## Замечания после сканирования
- [ ] Подозрительные имена: `Action item row — Edit` (в наборе Edit и Read)
