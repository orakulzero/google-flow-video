# Гайд и пресеты Google Flow: Сериал «Тиран в оборонительной игре» в стиле *Arcane (Fortiche)*

## 1. Инструменты Google Flow для создания полноценного сериала

На базе официальной документации **Google Flow (`flow.google.com`)**, гайдов по AI-кинематографу (`Ingredients to Video`, `SceneBuilder`) и возможностей `gflow-cli v0.92.1` производственный конвейер сериала строится на **5 нативных механизмах Flow**:

| Механизм Google Flow | Команда / Режим | Как работает в сериале | Расход кредитов |
| :--- | :--- | :--- | :--- |
| **1. Character Sheets (`Nano Banana Pro`)** | `gflow image t2i --model nano-pro` | Генерация 3-ракурсных концепт-листов (`Portrait + 3/4 + Turnaround`) в живописном стиле **Fortiche (*Arcane*)** (`1376x768`). | **0 кредитов (Бесплатно)** |
| **2. Режим Персонажей (`Flow Characters`)** | `gflow character create` / `@Name` | Создаёт в проекте сущность `CHARACTER`: `Slot 0` (портрет лица) → автоматически привязывается как seed в `Slot 1` (триптих тела Спереди/Сбоку/Сзади) + привязка голоса (`--voice`) и характера (`--personality`). | **0 кредитов (Бесплатно)** |
| **3. Пресеты проекта (`Agent Brief Cards`)** | `gflow instructions add / apply` | Постоянные карточки инструкций проекта (`Project Brief`). Карточка **«Arcane Fortiche Visual Style»** автоматически вшивается агентом Flow в каждый промпт сцены. | **0 кредитов (Бесплатно)** |
| **4. Ингредиенты (`Ingredients / R2V` и `I2V`)** | `gflow video r2v --ref` / `video i2v -i` | **Ingredients (`r2v`)**: подача до 3 референсов (`veo-fast`/`veo-lite`) или до 7 (`omni-flash`) — лицо героя + локация + предмет. **First-Frame (`i2v`)**: генерация идеального кадра в `Nano Banana Pro` с последующей анимацией в `Veo 3.1 - Quality`. | **По тарифу видео** |
| **5. Оркестратор фильма (`movie.toml` + `SceneBuilder`)** | `gflow movie run movie.toml` | Единый манифест эпизода с глобальным `[style]`, списком `[[characters]]`, диалогами (`speaker`, `line`) и авто-склейкой сцен (`runVideoFxConcatenation`). | **Только за новые сцены** |

---

## 2. Готовый пресет стиля *Arcane (Fortiche Production)* для Flow

### А. Шаблон карточки стиля (`Project Brief Card`)
```toml
[[instructions.card]]
title = "Arcane Fortiche Visual Bible"
text = "Hand-painted 2.5D/3D hybrid animation in the signature style of Fortiche Production (Arcane: League of Legends). Visible oil and gouache brushstrokes on skin, armor, and stone walls; rich impasto texture; bold expressive ink contours; dramatic high-contrast chiaroscuro rim lighting (warm amber torchlight vs cold hextech cyan and crimson moonlight); cinematic 24fps camera movement with expressive facial micro-acting."
enabled = true
```

### Б. Шаблон промпта для генерации концепт-листа персонажа (`Nano Banana Pro`)
> `Character concept turnaround sheet in the hand-painted brushwork style of Fortiche Production Arcane: visible dynamic oil and gouache brushstrokes on skin and fabric, heavy impasto texture, bold expressive ink outlines blended with 3D volumetric chiaroscuro rim lighting, neutral parchment concept art background, showing close-up face portrait, 3/4 expression view, and full-body front/side turnaround. No text, no labels, no typography. Subject: [Описание героя по канону новеллы]`

---

## 3. Кастинг, канон внешности из новеллы и многоголосая озвучка ролей

| Персонаж (Роль в сериале) | Внешность по канону новеллы *«Тиран в оборонительной игре»* | Голос в Flow (`gflow character voices`) | Русский дубляж и характер речи |
| :--- | :--- | :--- | :--- |
| **1. Эш «Борнхейтер» Эверблэк** *(Главный герой, 3-й принц, Командир Перекрёстка)* | Угольно-чёрные растрёпанные волосы, бледная кожа, тёмные круги от бессонницы, золотисто-янтарные глаза (позже вертикальный драконий зрачок), ожоговые шрамы на шее и руках после пролога, чёрно-золотой имперский офицерский сюртук. | `Alnilam` *(Male, firm, mid-low)* | Холодный, расчётливый, усталый баритон командира, срывающийся на жёсткий командный рык в бою. |
| **2. Лукас Макгрегор** *(SSR-рыцарь авангарда, телохранитель Эша)* | «Золотые волосы, золотое сердце» — высокий широкоплечий молодой рыцарь со светлыми золотистыми волосами, благородными чертами лица, шрамом на щеке, в стальном латном доспехе с лазурным плащом, башенным щитом и клеймором. | `Orus` *(Male, firm, mid-low)* | Тёплый, преданный героический баритон в диалогах с Эшем и стальной непреклонный голос на передовой. |
| **3. Дэмиен** *(N-жрец → EX-ранговый Магический Снайпер «Всевидящее Око»)* | Худощавый юноша с каштановыми волосами, стимпанк-моноклем/очками стрелка; при активации «Всевидящего Ока» радужки светятся белым, из глаза течёт кровавая слеза; вооружён длинноствольным магическим мушкетом «Чёрная Королева». | `Fenrir` *(Male, younger, excitable)* | Мягкий, неуверенный юношеский тенор в обычной жизни, переходящий в ледяной шёпот во время прицеливания. |
| **4. Евангелина Кросс** *(SSR-рыцарь-танк, юная наследница маркграфа Кросса)* | Миниатюрная, но свирепая девушка-рыцарь с ярко-малиновыми/розовыми волосами (два хвоста или распущенные), рубиновыми глазами и дерзкой ухмылкой, в массивном серебряно-алом латном доспехе дома Кросс с огромным копьём-ленсом и щитом. | `Leda` *(Female, youthful, mid-high)* | Звонкое, дерзкое, задиристое сопрано аристократки, переходящее в яростный боевой клич при таране строя монстров. |
| **5. Юпитер «Удар Молнии»** *(SR-ветеран, одноглазый маг молний)* | Харизматичная 55-летняя наёмница-ветеран (в духе Севики/Амбессы из *Arcane*), взъерошенные пепельно-седые волосы, чёрная повязка на левом глазу, боевые шрамы, сигара в углу рта, прожжённый плащ с дугами синих молний. | `Gacrux` *(Female, mature, mid)* | Низкий, прокуренный, саркастичный женский контральто опытного ветерана. |
| **6. Лили** *(R-маг огня и главный алхимик-инженер)* | Огненно-рыжие волосы в небрежном пучке, вечно невыспавшиеся зелёные глаза под круглыми латунными очками, кожаный фартук поверх мантии мага-инженера, ядро огненной маны и чертежи баллист. | `Aoede` *(Female, breezy, mid)* | Ироничное, вечно сонное меццо-сопрано инженера, мечтающего об отставке. |
| **7. Система / Рассказчик** *(Интерфейс «Оборонительной Игры»)* | Голографические золотые и багровые рунические уведомления о начале волны и потерях отряда. | `Sulafat` / `voice_y0joebp3bwta` | Бесстрастный, кристально чистый голос Системы с лёгким металлическим ревербератором. |

---

## 4. Сгенерированные в Google Flow (`Nano Banana Pro`) варианты главных героев в стиле *Arcane*

Все 10 концепт-листов (`1376x768`, 3 ракурса: крупный портрет лица, 3/4 и полный рост спереди/сбоку/сзади) сгенерированы напрямую через **Google Flow (`GEM_PIX_2 / Nano Banana Pro`)** в проекте `7d9a2a67-9cd2-4a79-932e-717d2e29257f`:

![Сводный контакт-лист 10 вариантов главных героев в стиле Arcane (Fortiche)](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/arcane_cast_contact_sheet.png)

### Интерактивная карусель всех 10 вариантов (листайте слайды)

````carousel
![01. Эш Эверблэк — Вариант 1: Классический мундир 3-го принца, тёмные круги бессонницы, ожоговые шрамы](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/ash_arcane_v1.jpg)
<!-- slide -->
![02. Эш Эверблэк — Вариант 2: Боевой Тиран на стене Перекрёстка, золотой драконий взгляд, плащ с мехом и подзорная труба](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/ash_arcane_v2.jpg)
<!-- slide -->
![03. Лукас Макгрегор — Вариант 1: Золотой SSR-рыцарь авангарда, полированный латный доспех, башенный щит и лазурный плащ](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/lucas_arcane_v1.jpg)
<!-- slide -->
![04. Лукас Макгрегор — Вариант 2: Ветеран первой линии в помятой воронёной броне после ночного штурма](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/lucas_arcane_v2.jpg)
<!-- slide -->
![05. Дэмиен — Вариант 1: Магический снайпер со «Всевидящим Оком» (белые светящиеся радужки, латунный монокль, мушкет «Чёрная Королева»)](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/damien_arcane_v1.jpg)
<!-- slide -->
![06. Дэмиен — Вариант 2: Стрелок дозорной башни в тёмно-зелёном плаще с капюшоном и патронташем синих мана-патронов](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/damien_arcane_v2.jpg)
<!-- slide -->
![07. Евангелина Кросс — Вариант 1: Алый Бастион Дома Кросс (два хвоста, массивный серебряно-багровый латный доспех танка, гигантское копьё-ленс)](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/evangeline_arcane_v1.jpg)
<!-- slide -->
![08. Евангелина Кросс — Вариант 2: Штурмовая Валькирия с распущенными розово-алыми волосами и меховой накидкой маркграфства Кросс](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/evangeline_arcane_v2.jpg)
<!-- slide -->
![09. Юпитер «Удар Молнии» — Одноглазая наёмница-ветеран (55 лет, пепельно-седые волосы, повязка на левом глазу, сигара, дуги молний)](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/jupiter_arcane_v1.jpg)
<!-- slide -->
![10. Лили — Главный алхимик-инженер и маг огня (огненно-рыжий пучок, круглые латунные очки, кожаный фартук, ядро огненной маны и чертежи)](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/lily_arcane_v1.jpg)
````

---

## 5. Концепт-листы *Arcane* на базе оригинальных фреймов из манхвы (`Google Flow Ingredients i2i`)

В проект Google Flow (`7d9a2a67-9cd2-4a79-932e-717d2e29257f`) через меню **«Добавить ингредиенты в окно запроса» (`button.add-menu-trigger` → `Загрузить` → `Добавить в запрос`)** были загружены **оригинальные фреймы из вебтуна/манхвы «Тиран в оборонительной игре»**, и по каждому фрейму в `Nano Banana Pro` (`1376×768`) сгенерирован 3-ракурсный концепт-лист в стиле **Arcane (Fortiche)** с сохранением оригинальной причёски, черт лица, брони и оружия из манхвы:

![Сравнение: Оригинальный фрейм из манхвы (слева) -> Сгенерированный в Google Flow Arcane-лист (справа)](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/manhwa_vs_arcane_contact_sheet.png)

### Попарная карусель: `[Оригинальный фрейм манхвы]` → `[Arcane-лист из Google Flow]`

````carousel
![01. Эш Эверблэк — Arcane-лист из фрейма манхвы (ash_manhwa_cover.jpg -> ash_from_manhwa.jpg)](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/ash_from_manhwa.jpg)
<!-- slide -->
![02. Лукас Макгрегор — Arcane-лист из фрейма манхвы (lucas_manhwa_intro.jpg -> lucas_from_manhwa.jpg)](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/lucas_from_manhwa.jpg)
<!-- slide -->
![03. Дэмиен (Снайпер в бою) — Arcane-лист из фрейма манхвы (damien_manhwa_action.jpg -> damien_from_manhwa.jpg)](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/damien_from_manhwa.jpg)
<!-- slide -->
![04. Эйдер (Директор и казначей Эша) — Arcane-лист из фрейма манхвы (eider_manhwa.jpg -> damien_eye_from_manhwa.jpg)](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/damien_eye_from_manhwa.jpg)
<!-- slide -->
![05. Евангелина Кросс (SSR Рыцарь-щитоносец Дома Кросс) — Arcane-лист из фрейма манхвы (evangeline_manhwa_young.jpg -> evangeline_from_manhwa.jpg)](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/evangeline_from_manhwa.jpg)
<!-- slide -->
![06. Юпитер (Маг молний с сигарой и повязкой) — Arcane-лист из фрейма манхвы (jupiter_manhwa.jpg -> jupiter_from_manhwa.jpg)](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/jupiter_from_manhwa.jpg)
<!-- slide -->
![07. Лили (Алхимик-инженер Перекрёстка) — Arcane-лист из фрейма манхвы (lily_manhwa_1.jpg -> lily_from_manhwa.jpg)](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/lily_from_manhwa.jpg)
<!-- slide -->
![08. Босс 1-й волны: Чёрная Паучья Королева — Arcane-лист из фрейма манхвы (black_spider_queen_manhwa.jpg -> spider_queen_from_manhwa.jpg)](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/spider_queen_from_manhwa.jpg)
<!-- slide -->
![Сводная сетка 12 оригинальных фреймов из манхвы (исходники)](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/manhwa_original_frames_grid.jpg)
````


---

## 6. Каноничный пакет 1-го Эпизода (напрямую из 492 фреймов Глав 1–3 манхвы: Оборона Передового Форта)

Поскольку рисовка и образы персонажей меняются по ходу манхвы, с официального **LINE Webtoon (`title_no=10765`, Главы 1–3)** были выгружены и нарезаны по межфреймовым границам все **492 оригинальных фрейма первого эпизода (`ep01`: 217 кадров, `ep02`: 159 кадров, `ep03`: 116 кадров)**.

В **1-м эпизоде (Пролог + Учебный этап / Оборона Передового Форта против Легиона Чёрных Пауков)** герои выглядят совсем иначе, чем в поздних главах:
- **Эш (Пролог, `ep01/frame_003.jpg`):** стример «Ретро-Геймер» в голубом худи и наушниках за монитором ПК до переноса в мир игры.
- **Эш Эверблэк (`ep01/frame_094.jpg`):** очнувшийся под кислотным обстрелом на горящей стене 3-й принц в чёрно-красно-золотом мундире с эполетами, аксельбантом и ссадинами на щеке.
- **Лукас Макгрегор (`ep01/frame_193.jpg`):** рыцарь-телохранитель в многослойном серебряно-вороненом латном доспехе и бело-синем плаще.
- **Дэмиен (`ep02/frame_129.jpg`):** в 1-м эпизоде он ещё **травмированный жрец N-ранга в круглых очках и чёрно-золотой сутане**, которого Эш прямо перед боем переводит в снайперы.
- **Лили (`ep02/frame_119.jpg`):** в 1-м эпизоде носит **боковую косу, белую тунику с коричневым корсетным жилетом и красный плащ с капюшоном**, а Эш ударом кинжала пробуждает её скрытый талант *«Огненная кожа»* (танк уклонения).
- **Кен (`ep02/frame_106.jpg`):** четвёртый член стартового отряда Эша в 1-м эпизоде — короткостриженый щитоносец со шрамом на щеке, которого Эш переводит в диверсанты (*«Выживание мелкого вора»*).
- **Древняя Мана-Пушка и артиллерийский расчёт (`ep03/frame_110.jpg`):** бело-золотое орудие на стене Передового Форта и расчёт в красных туниках и стальных кирасах.
- **Легион Чёрных Пауков и Королева (`ep01/frame_166.jpg`):** гигантские пауки-штурмовики с горящими красными глазами и **ярко-зелёным токсичным ядом**.

### А. Сравнение `8 из 8`: `[Фрейм из Глав 1–3 манхвы]` → `[Arcane-лист из Google Flow]`

![Сравнение каноничных фреймов Глав 1–3 манхвы (слева) и Arcane-листов из Google Flow (справа)](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/ep01_manhwa_vs_arcane_sheet.png)

````carousel
![01. Эш в Прологе (Гл.1, ep01/frame_003.jpg) — Геймер в голубом худи за стримерским ПК до переноса](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/ep01_ash_gamer_arcane.jpg)
<!-- slide -->
![02. Принц Эш Эверблэк (Гл.1, ep01/frame_094.jpg) — Пробуждение на горящей стене в чёрно-золотом мундире](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/ep01_ash_commander_arcane.jpg)
<!-- slide -->
![03. Лукас Макгрегор (Гл.1, ep01/frame_193.jpg) — Серебряный латный доспех и бело-синий плащ 1-го эпизода](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/ep01_lucas_knight_arcane.jpg)
<!-- slide -->
![04. Дэмиен (Гл.2, ep02/frame_129.jpg) — Дебютный облик в 1-м эпизоде: круглые очки и чёрно-золотая ряса жреца](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/ep01_demian_priest_arcane.jpg)
<!-- slide -->
![05. Лили (Гл.2, ep02/frame_119.jpg) — Дебютный облик в 1-м эпизоде: коса, белая туника, корсетный жилет и красный плащ](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/ep01_lily_flameskin_arcane.jpg)
<!-- slide -->
![06. Кен (Гл.2, ep02/frame_106.jpg) — Четвёртый боец отряда 1-го эпизода: шрам на щеке, тёмный латный доспех и щит](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/ep01_ken_infiltrator_arcane.jpg)
<!-- slide -->
![07. Древняя Мана-Пушка и расчёт Передового Форта (Гл.3, ep03/frame_110.jpg)](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/ep01_mana_cannon_arcane.jpg)
<!-- slide -->
![08. Легион Чёрных Пауков с изумрудным ядом (Гл.1, ep01/frame_166.jpg)](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/ep01_black_spider_arcane.jpg)
````

### Б. Последовательная раскадровка 1-го Эпизода (12 ключевых фреймов напрямую из Глав 1–3)

![12 последовательных сюжетных фреймов 1-го эпизода напрямую из Глав 1–3 манхвы](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/ep01_storyboard_12scenes_grid.jpg)


---

## 7. Пилотный выпуск 1-го Эпизода в `Omni 1.1 Flash` + Аудит отловленных ошибок перед `Veo 3.1 Quality`

### А. Готовый мастер-выпуск Эпизода 1 (`Omni 1.1 Flash` + 5 голосов `Gemini 3.8 Studio` + BGM)

- **Видеофайл (`1280×720`, `24 fps`, `95.3 сек`, `40.3 МБ`):** [`ttd_episode_01_omni_flash_ru.mp4`](file:///C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/ttd_episode_01_omni_flash_ru.mp4) (и копия в [`output/ttd_ep01_omni_flash/ttd_episode_01_omni_flash_ru.mp4`](file:///e:/ANTIGRAVITY/flow_video_testbench/output/ttd_ep01_omni_flash/ttd_episode_01_omni_flash_ru.mp4))
- **Субтитры по ролям:** [`ttd_episode_01_omni_flash_ru.vtt`](file:///e:/ANTIGRAVITY/flow_video_testbench/output/ttd_ep01_omni_flash/ttd_episode_01_omni_flash_ru.vtt) и [`ttd_episode_01_omni_flash_ru.srt`](file:///e:/ANTIGRAVITY/flow_video_testbench/output/ttd_ep01_omni_flash/ttd_episode_01_omni_flash_ru.srt)

![Эпизод 1 (Omni 1.1 Flash Edition) — Тиран в оборонительной игре (Русский многоголосый дубляж)](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/ttd_episode_01_omni_flash_ru.mp4)

### Б. Сводный лист проверки всех 8 отрендеренных видеосцен (`8 из 8 Verified`)

![Покадровый аудит всех 8 сцен Эпизода 1, отрендеренных в Google Flow (Omni 1.1 Flash)](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/ep01_omni_flash_frames_sheet.png)

````carousel
![Сцена 01 (Omni 1.1 Flash): Эш в голубом худи проходит «Защити Империю» и затягивается в портал монитора](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/scene_01_mid.jpg)
<!-- slide -->
![Сцена 02 (Omni 1.1 Flash): Пробуждение в теле принца Эша Эверблэка на горящей стене под кислотным обстрелом](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/scene_02_mid.jpg)
<!-- slide -->
![Сцена 03 (Omni 1.1 Flash): Прорыв гигантского Чёрного Паука с горящими красными глазами и изумрудным ядом](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/scene_03_mid.jpg)
<!-- slide -->
![Сцена 04 (Omni 1.1 Flash — после фикса референса): Лукас Макгрегор в серебряном доспехе защищает Эша](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/scene_04_mid.jpg)
<!-- slide -->
![Сцена 05 (Omni 1.1 Flash): Лили в красном плаще и корсете уклоняется от кинжала Эша («Огненная кожа»)](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/scene_05_mid.jpg)
<!-- slide -->
![Сцена 06 (Omni 1.1 Flash): Дэмиен в круглых очках и рясе жреца рядом со щитоносцем Кеном со шрамом на щеке](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/scene_06_mid.jpg)
<!-- slide -->
![Сцена 07 (Omni 1.1 Flash — после фикса): Перегрузка Древней Мана-Пушки на рассвете 1 марта](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/scene_07_mid.jpg)
<!-- slide -->
![Сцена 08 (Omni 1.1 Flash): Залп перегруженной Древней Мана-Пушки по гнезду Чёрной Паучьей Королевы](C:/Users/Orakul%20Grey/.gemini/antigravity/brain/94dd6a04-54e7-4e8c-9551-224cace4f85f/scene_08_mid.jpg)
````

### В. Какие грубые ошибки выявил прогон `Omni 1.1 Flash` (и как они устранены)

| Сцена / Проблема | Что произошло на первом прогоне `Omni 1.1 Flash` | Причина | Применённое исправление (в `Omni 1.1 Flash` и для `Veo 3.1 Quality`) |
| :--- | :--- | :--- | :--- |
| **1. Сцена 04 (Спасение Лукасом)** | Вместо появления Лукаса модель отредактировала видео паука из Сцены 03, добавив поверх него золотую вспышку удара без самого рыцаря. | В исходном фрейме `ep01/frame_179.jpg` 90% кадра занимала туша паука, а Лукас был крошечным силуэтом снизу. | Второй референс заменён на `ep01/frame_180.jpg` (крупный план Лукаса в доспехе перед рассечённым пауком) — Лукас отрисован крупным планом точно по `ep01_lucas_knight_arcane.jpg`. |
| **2. Сцена 07 (Приказ у Мана-Пушки)** | На первом прогоне у командира рядом с Мана-Пушкой были короткие каштановые волосы вместо причёски и черт Эша из Сцены 02. | В пару к `ep01_mana_cannon_arcane.jpg` был подан общий план стены `ep03/frame_094.jpg` без портретного листа Эша. | В качестве пары ингредиентов поданы `ep01_ash_commander_arcane.jpg` + `ep01_mana_cannon_arcane.jpg`. |
| **3. Баблы и рамки манхвы (Все 8 сцен)** | **0 артефактов** (ни одного речевого пузыря или вертикальной рамки манхвы). | Явный запрет `NO comic panel borders, NO split screens, NO speech bubbles` в `STYLE_DIRECTIVE`. | Сохранить этот же `STYLE_DIRECTIVE` при генерации в `Veo 3.1 - Quality`. |
