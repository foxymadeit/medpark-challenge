# Foundation (scan)

**Источник:** своя ДС, файл `QYy8I55YDJRojTI6UCZENa`
**Дата сканирования:** 2026-11-04
**Коллекции:** Primitives 69, Color 71 (мод Light), Spacing 10, Radius 5, Motion 3. Всего 158 переменных.

## Слой 1: примитивные токены

### Палитра
- gray: 0 #ffffff, 50 #f7f6f3, 100 #efede8, 200 #eae6df, 300 #ddd8cf, 400 #d9d6d1, 500 #c9c6c0, 600 #6f685f, 700 #5b544b, 800 #2b2b2b, 900 #101010
- brand/500 #007aff (не используется: бренд, Upload и кнопки на одном синем blue/600)
- blue: 50 #eaf1fd, 100 #ddebff, 200 #a9c8f5, 400 #4f86f0, 500 #2f6feb, 600 #1f5fd1, 700 #1a50b3
- red: 50 #fdf1f0, 100 #ffe1de, 200 #f1c6c2, 300 #f5b5ae, 400 #e5635a, 500 #d9463d, 600 #b3261e, 700 #9a1f18
- green: 50 #e3f3ea, 700 #1e7f4f
- speaker: magenta #b73f74, amber #c27544, teal #0093a5, violet #6450a1
- tone/<rose|peach|amber|green|teal|blue|violet|stone|ink>/<bg|fg|dot|solid>: 36 значений, совпадают с `src/lib/colors.ts`

### Отступы
space/0-5 = 2, 1 = 4, 2 = 8, 3 = 12, 4 = 16, 5 = 20, 6 = 24, 8 = 32, 10 = 40, 12 = 48

### Радиусы
radius/xs = 4, sm = 8, md = 12, lg = 16, full = 999

### Кольцо аватарок
Снаружи, color/bg/panel: S 1, M 1.5, L 2. В коде `--sm-avatar-ring-s`, `-m`, `-l`.

### Движение
duration/fast = 120, base = 200, slow = 280

### Шрифты
Onest (заголовки, плашки, аватарки), Golos Text (текст, кнопки, данные)

## Слой 2: смысловые токены

- color/text: primary → gray/900, secondary → gray/700, tertiary → gray/600, disabled → gray/500, on-solid → gray/0
- color/bg: ground → gray/50, panel → gray/0, track → gray/100, keyword-hover → gray/300
- color/border: hairline → gray/200, dashed → gray/400
- color/control: default → gray/900, hover → gray/800
- color/brand/default → brand/500
- color/action: default → blue/600, hover → blue/700, tint → blue/50
- color/upload: ink → blue/500, line → blue/400, tint → blue/100, tint-line → blue/200
- color/record: ink → red/500, line → red/400, tint → red/100, tint-line → red/300
- color/danger: default → red/600, hover → red/700, tint → red/50, line → red/200
- color/success: default → green/700, tint → green/50
- color/speaker/01–04 → speaker/*
- color/person/<tone>/<bg|fg|dot|solid> → tone/*

## Текстовые стили (19)

| Стиль | Шрифт | Размер / строка |
|---|---|---|
| Display | Onest SemiBold | 40 / 48 |
| Heading/H1 | Onest SemiBold | 28 / 36 |
| Heading/H2 | Onest SemiBold | 20 / 28 |
| Heading/H3 | Onest SemiBold | 16 / 24 |
| Label/Plate | Onest Medium | 12 / 16 |
| Body/LG | Golos Regular | 17 / 24 |
| Body/MD | Golos Regular | 15 / 24 |
| Body/SM | Golos Regular | 13 / 20 |
| Body/Strong | Golos SemiBold | 15 / 24 |
| Label/Button | Golos Medium | 15 / 20 |
| Data/MD | Golos Medium | 15 / 20 |
| Data/SM | Golos Regular | 13 / 20 |
| Timer | Golos Medium | 72 / 80 |
| Label/Field | Golos Medium | 13 / 20 |
| Label/Tag | Golos SemiBold | 13 / 20 |
| Label/Column | Golos Medium | 12 / 16 |
| Avatar/S, M, L | Onest Medium | 10 / 12, 12 / 16, 18 / 24 |

## Стили эффектов (6)

Elevation/Button, Raised, Card, Popover, Modal и Focus ring. Значения совпадают с `--sm-elevation-*`.

## Замечания после сканирования
- [x] Привязки Semantic → Primitive: сделаны, все 71 смысловой цвет идёт через примитивы
- [x] Кириллица: Onest и Golos Text её поддерживают (знание о шрифтах, отдельно по глифам не проверяла)
- [ ] Дубликаты имён: не найдено
- [ ] Описания: нет у всех 69 примитивов и у 35 смысловых цветов
- [ ] Тёмной темы нет: у Color один мод Light
