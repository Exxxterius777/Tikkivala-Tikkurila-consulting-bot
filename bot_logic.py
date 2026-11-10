# -*- coding: utf-8 -*-
"""
Логика бота-консультанта Tikkivala (v0.3.1).
route_message() — единственная точка входа из Flask.
"""
import os
import re
import urllib.parse
from catalog import CATALOG
import texts


# ---------- СЛОВАРЬ СТЕМОВ ----------
PATTERNS = {
    'brand': ['tikkivala', 'tikkurila', 'тиккурила', 'тиккивала', 'тикурила',
              'тикивала', 'ppg'],
    'купить': ['куп', 'приобрест', 'закуп', 'докуп'],
    'подскажи': ['подскаж', 'расскаж', 'помог', 'объясн', 'укаж'],

    'адрес': ['адрес', 'магазин', 'точк', 'торгов'],
    'где_купить': ['где куп', 'где прода', 'где есть'],

    'стены': ['стен'],
    'потолок': ['потол'],
    'пол': ['полы', 'пола', 'полов', 'полом', 'пол'],
    'фасад': ['фасад'],
    'металл': ['металл', 'ржав', 'сталь', 'чугун'],
    'оцинковка': ['оцинков'],
    'дерево': ['дерев', 'древес', 'бревн', 'брус', 'вагонк', 'доск'],
    'мебель': ['мебел'],
    'декор': ['декор', 'рейк'],
    'мелкие изделия': ['игрушк', 'издели', 'полочк'],
    'терраса': ['террас'],
    'баня': ['баня', 'бани', 'баню', 'банях'],
    'сауна': ['саун'],
    'цоколь': ['цокол', 'фундамент'],
    'кафель': ['кафел'],
    'плитка': ['плитк'],
    'стекло': ['стекл'],
    'пластик': ['пластик', 'пвх'],
    'сложная поверхность': ['сложн'],
    'бетон': ['бетон'],
    'кирпич': ['кирпич'],
    'обои': ['обои', 'обоев'],
    'паркет': ['паркет'],
    'ванная': ['ванн', 'уборн', 'туалет', 'бойлер'],

    'влажное': ['влажн', 'ванн', 'кухн', 'душ', 'уборн', 'туалет', 'бойлер'],
    'внутри': ['внутри', 'внутренн', 'помещени', 'интерьер'],
    'снаружи': ['снаруж', 'наружн', 'улиц'],

    'краска': ['краск', 'покрас', 'окрас', 'водоэмульс'],
    'эмаль': ['эмал'],
    'лак': ['лак', 'лакир'],
    'пропитка': ['пропит'],
    'антисептик': ['антисепт', 'биозащ'],
    'морилка': ['морил'],
    'масло': ['масл'],
    'грунт': ['грунт', 'обеспыл'],
    'шпатлёвка': ['шпатл', 'шпакл'],
    'растворитель': ['раствор', 'уайт-спир', 'уайт спир'],
    'лазурь': ['лазур'],
    'кроющий состав': ['кроющ'],

    'матовая': ['матов'],
    'полуматовая': ['полумат'],
    'глянцевая': ['глянц'],
    'глубокоматовая': ['глубокомат'],
    'высокоглянцевая': ['высокоглянц'],

    'новое': ['ново', 'с нуля', 'впервые', 'первый раз', 'заново', 'по новой'],
    'обновить': ['обнов', 'перекрас', 'старо'],
    'лессирующая': ['лессир'],
    'кроющая': ['кроющ', 'укрыв'],
    'плёнка': ['плён', 'плен'],
    'бесплёночный': ['беспл', 'без плен', 'без плён'],
    'подготовлена': ['подготовл', 'зашпатл', 'прогрунт'],
    'не подготовлена': ['не подготовл', 'не зашпатл', 'не прогрунт'],
    'частично подготовлена': ['частично'],

    'attr_base': ['база', 'базу', 'баз'],
    'attr_gloss': ['блеск', 'глянц'],
    'attr_coverage': ['площад', 'расход', 'охват'],
    'attr_thinner': ['разбавител', 'разбавит', 'чем разбавить'],
    'attr_category': ['категори', 'тип продукта', 'что это за'],

    'more': ['ещё', 'еще', 'друг', 'следующ', 'дешевле', 'подешевле'],
}


def _extract_tags(text):
    text = text.lower()
    words = re.findall(r'[а-яёa-z]+', text)
    tags = set()
    all_stems = []
    for tag, roots in PATTERNS.items():
        for root in roots:
            all_stems.append((root, tag))
    all_stems.sort(key=lambda x: -len(x[0]))
    for w in words:
        for root, tag in all_stems:
            if w.startswith(root):
                tags.add(tag)
                break
    return tags


def _extract_number(text):
    m = re.search(r'\d+([.,]\d+)?', text)
    if m:
        try:
            return float(m.group().replace(',', '.'))
        except ValueError:
            return None
    return None


def _is_yes(msg):
    words = re.findall(r'[а-яёa-z]+', msg.lower())
    return any(w in ['да', 'будут', 'давай', 'конечно', 'ага', 'угу', 'yes'] for w in words)


def _is_no(msg):
    m = msg.lower()
    return any(t in m for t in ['нет', 'не будут', 'больше не', 'не надо', 'хватит', 'no'])


# ---------- ОПРЕДЕЛЕНИЕ НАМЕРЕНИЙ ----------
def _is_farewell(msg):
    return any(t in msg for t in ['пока', 'до свидан', 'до встреч', 'всего хорошего',
                                   'бывай', 'покеда', 'я пошёл', 'спасибо за помощь'])


def _is_greeting(msg):
    return any(t in msg for t in ['привет', 'здравств', 'хай', 'добр'])


def _is_calculator_start(msg):
    return any(t in msg for t in ['рассчита', 'калькулятор', 'посчита', 'площад'])


def _is_shops_request(msg):
    m = msg.lower()
    tags = _extract_tags(msg)

    # 1. Явные маркеры магазинов / адресов
    if any(t in m for t in ['магазин', 'точк', 'торгов', 'адрес']):
        return True
    if 'адрес' in tags:
        return True

    # 2. «Купить/приобрести/закупить» + контекст (где/куда/хочу/как/подскажи/дай или бренд)
    if 'купить' in tags:
        if 'brand' in tags:
            return True
        if any(w in m for w in ['где', 'куда', 'хочу', 'как', 'подскаж', 'дай', 'найти']):
            return True

    # 3. Прямые фразы
    if any(t in m for t in ['где куп', 'где прода', 'где найти', 'где взять',
                             'где есть', 'где можн', 'где я мог', 'где мне',
                             'куда идти', 'куда пойти', 'куда обрат']):
        return True

    return False


def _is_faq(msg):
    triggers = [
        'что такое', 'как расшифров', 'в чём разниц', 'чем отлича', 'чем лучше',
        'какой валик', 'какую кисть', 'кисть или валик', 'как не оставить',
        'что значит', 'биопораж', 'влага в дереве', 'почему по дереву',
        'зачем нужна кисть', 'зачем нужно сушить', 'как не полосить',
        'водно-дисперс', 'водоэмульс', 'малярный инструмент', 'какой ворс',
        'как правильно крас', 'колер', 'как хранить', 'как установить',
        'как крыть масл', 'неправильно заколер',
    ]
    if ('база' in msg.lower() or 'баз' in msg.lower()) and \
            ('разниц' in msg.lower() or ' a ' in msg.lower() or ' c ' in msg.lower()
             or 'прозрачн' in msg.lower() or 'бел' in msg.lower()):
        return True
    return any(t in msg for t in triggers)


def _is_consultation_request(msg):
    triggers = ['как ', 'чем ', 'правильно', 'инструкц', 'расскаж', 'подскаж как', 'каким образом']
    return any(t in msg for t in triggers)


def _is_more_request(msg):
    m = msg.lower().strip()
    return any(t in m for t in ['ещё', 'еще', 'друг', 'следующ', 'дешевле', 'подешевле'])


def _is_selection_request(msg):
    tags = _extract_tags(msg)
    lkm = {'краска', 'эмаль', 'лак', 'пропитка', 'антисептик', 'морилка', 'масло',
           'грунт', 'шпатлёвка', 'растворитель', 'лазурь', 'кроющий состав'}
    surfaces = {'стены', 'потолок', 'пол', 'фасад', 'металл', 'дерево', 'мебель',
                'терраса', 'баня', 'сауна', 'цоколь', 'кафель', 'стекло',
                'пластик', 'плитка'}
    return bool(tags & lkm) or bool(tags & surfaces)


# ---------- КОНКРЕТНАЯ ПОЗИЦИЯ ----------
def _detect_product_mention(msg):
    msg_l = msg.lower()
    msg_words = set(re.findall(r'[а-яёa-z0-9]+', msg_l))
    products_sorted = sorted(CATALOG, key=lambda p: -len(p['name']))
    for p in products_sorted:
        short = p['name'].replace('Tikkivala ', '').lower()
        if short in msg_l:
            return p
        short_words = re.findall(r'[а-яёa-z0-9]+', short)
        for w in short_words:
            if len(w) >= 4 and w in msg_words:
                return p
    return None


def _detect_attribute_request(msg):
    m = msg.lower()
    if 'разбавит' in m or 'чем разбав' in m:
        return 'thinner'
    if 'площад' in m or 'расход' in m or 'охват' in m:
        return 'coverage'
    if 'блеск' in m or 'глянц' in m:
        return 'gloss'
    if 'категор' in m or 'тип продукта' in m:
        return 'category'
    if 'база' in m or 'баз' in m or 'базу' in m:
        return 'base'
    return 'full'


def _handle_product_mention(product, msg):
    attr = _detect_attribute_request(msg)
    if attr == 'full':
        lines = [
            f"• {product['name']}",
            f"  Категория: {product['category']}",
            f"  Блеск: {product.get('gloss', '—')}",
            f"  База: {product.get('base', '—')}",
            f"  Площадь: {product.get('coverage', '—')}",
            f"  Разбавитель: {product.get('thinner', '—')}",
        ]
        return "\n".join(lines)
    if attr == 'base':
        return f"База у {product['name']}: {product.get('base', '—')}"
    if attr == 'gloss':
        return f"Степень блеска {product['name']}: {product.get('gloss', '—')}"
    if attr == 'coverage':
        return f"Окрашиваемая площадь {product['name']}: {product.get('coverage', '—')}"
    if attr == 'thinner':
        return f"Разбавитель {product['name']}: {product.get('thinner', '—')}"
    if attr == 'category':
        return f"Категория {product['name']}: {product['category']}"
    return None


# ---------- FAQ ----------
def _handle_faq(msg):
    m = msg.lower()

    # v0.3.1: сначала проверяем жалобы на цвет (важнее, чем процесс колеровки)
    if 'неправильно' in m and 'колер' in m:
        return texts.FAQ_COLOR_DIFF
    if 'цвет' in m and ('не тот' in m or 'отлича' in m or 'разниц' in m
                         or 'палитр' in m or 'каталог' in m):
        return texts.FAQ_COLOR_DIFF

    # Процесс колеровки
    if 'колер' in m:
        return texts.FAQ_TINTING

    # Остальные специфичные FAQ (порядок важен)
    if ('база' in m or 'баз' in m) and (' a ' in m or ' c ' in m or 'разниц' in m
                                         or 'прозрачн' in m or 'бел' in m):
        return texts.FAQ_BASE + "\n\n" + texts.FAQ_BASE_EXTRA
    if 'хран' in m and ('как' in m or 'правильно' in m) and 'срок' not in m:
        return texts.FAQ_STORAGE
    if ('срок хранения' in m or 'сколько хранится' in m or
            'испорчена' in m or 'как определить' in m or 'состояние крас' in m):
        return texts.FAQ_STORAGE_TERM
    if ('масл' in m and ('как работать' in m or 'наносить' in m or 'растирать' in m
                          or 'крыть' in m or 'тряпк' in m or 'губк' in m
                          or 'ветош' in m)):
        return texts.FAQ_OIL
    if ('мыть' in m or 'очищ' in m or 'очист' in m) and ('инструмент' in m or 'рук' in m):
        return texts.FAQ_TOOLS_WASH
    if ('разбав' in m) and ('крас' in m or 'лак' in m or 'пропит' in m or 'грунт' in m):
        return texts.FAQ_DILUTE
    if ('запах' in m) or ('водной основе' in m and 'алкидной' in m):
        return texts.FAQ_SMELL

    # Существующие FAQ из v0.2
    if ('лкм' in m or 'лакокрасоч' in m) and ('что такое' in m or 'расшифров' in m):
        return texts.FAQ_LKM
    if ('валик' in m or 'ворс' in m or 'шагрень' in m or 'полосить' in m):
        return texts.FAQ_ROLLER
    if ('инструмент' in m) or ('кисть' in m and 'валик' in m) or ('чем красить' in m):
        return texts.FAQ_TOOL
    if ('кист' in m and 'дерев' in m) or ('зачем нужна кисть' in m) or ('почему по дереву' in m):
        return texts.FAQ_BRUSH_WOOD
    if ('влажн' in m and 'сух' in m) or ('ванн' in m and 'помещен' in m) or ('влажн' in m and 'помещен' in m):
        return texts.FAQ_HUMID
    if ('влаг' in m and 'дерев' in m) or ('биопораж' in m) or ('сушить' in m and 'древесин' in m):
        return texts.FAQ_MOISTURE
    if ('краск' in m and 'эмал' in m) or ('водно-дисперс' in m) or ('водоэмульс' in m):
        return texts.FAQ_PAINT_VS_ENAMEL
    if ('лак' in m or 'пропит' in m or 'лазур' in m) and \
            ('разниц' in m or 'различ' in m or 'чем лучше' in m or 'чем отлича' in m):
        return texts.FAQ_LKM_TYPES
    return None


# ---------- МАГАЗИНЫ (v0.3.1) ----------
def _try_extract_city(msg):
    """Извлекает название города из запроса (устойчиво к регистру)."""
    # 1. «в/во/городе/из/около/под + <Заглавное>»
    m = re.search(r'\b(?:в|во|городе|город[аеу]?|из|около|под|возле)\s+([А-ЯЁA-Z][а-яёa-z\-]+)', msg)
    if m:
        return m.group(1)

    # 2. Любое «Заглавное» слово не в начале и не бренд
    words = re.findall(r'\b[А-ЯЁA-Z][а-яёa-z\-]+\b', msg)
    brands = {'тиккурила', 'тиккивала', 'тикурила', 'тикивала',
              'tikkivala', 'tikkurila', 'ppg'}
    for i, w in enumerate(words):
        if i == 0:
            continue
        if w.lower() not in brands:
            return w

    # 3. «в/во + <любое слово с маленькой>» — если это не служебное слово
    m = re.search(r'\b(?:в|во)\s+([а-яёa-z\-]{3,})', msg)
    if m:
        stop = {'моём', 'моем', 'вашем', 'городе', 'магазине', 'стране', 'краску',
                'краска', 'краски', 'лаке', 'лак', 'эмали', 'эмаль', 'грунте',
                'грунт', 'пропитке', 'пропитка', 'шпатлёвке', 'шпатлёвка',
                'москве', 'питере'}  # если город уже в списке — вернём ниже
        candidate = m.group(1).lower()
        if candidate not in stop or candidate in {'москве', 'питере'}:
            return m.group(1).capitalize()

    return None


def _handle_shops(msg, stage, context):
    if stage == 'shop_ask_city':
        city = _try_extract_city(msg) or msg.strip()
        if len(city) < 2:
            return ("Извините, не могу найти адреса в данный момент, "
                    "попробуйте позже.", 'start', {})
        return _generate_shop_response(city)

    city = _try_extract_city(msg)
    if city:
        return _generate_shop_response(city)

    return ("Подскажу, где можно приобрести продукцию Tikkivala в вашем городе.\n\n"
            "В каком городе вы находитесь?", 'shop_ask_city', {})


def _generate_shop_response(city):
    try:
        city_encoded = urllib.parse.quote(city)
        link = f"https://yandex.ru/maps/?text=магазины Tikkurila {city_encoded}"

        reply = (f"Вот магазины Tikkurila в городе {city}:\n\n"
                 "Нажмите на кнопку ниже — откроется Яндекс.Карты с полным списком "
                 "магазинов, их адресами, телефонами и режимом работы.\n\n"
                 "Если нужна консультация по процессу покраски или подбор "
                 "ассортимента — просто спросите.")

        ctx = {'link': link}

        api_key = os.environ.get('YANDEX_GEOCODER_KEY', '')
        if api_key:
            coords = _geocode_city(api_key, city)
            if coords:
                lon, lat = coords['lon'], coords['lat']
                ctx['map_url'] = (
                    f"https://yandex.ru/map-widget/v1/?ll={lon}%2C{lat}"
                    f"&z=11&text=магазины Tikkurila"
                )

        return reply, 'start', ctx
    except Exception:
        return ("Извините, не могу найти адреса в данный момент, попробуйте позже.",
                'start', {})


def _geocode_city(api_key, city):
    try:
        import requests
        url = "https://geocode-maps.yandex.ru/1.x/"
        params = {
            'apikey': api_key,
            'geocode': city,
            'format': 'json',
            'results': 1,
        }
        r = requests.get(url, params=params, timeout=5)
        r.raise_for_status()
        data = r.json()
        members = data['response']['GeoObjectCollection']['featureMember']
        if members:
            pos = members[0]['GeoObject']['Point']['pos']
            lon, lat = pos.split()
            return {'lon': lon, 'lat': lat}
    except Exception:
        return None
    return None


# ---------- КАЛЬКУЛЯТОР ----------
WINDOW_AREA = 1.6
DOOR_AREA = 1.9


def _calc_ask_type():
    return ("Я могу единовременно рассчитать среднее значение окрашиваемой "
            "площади.\n\nЧто будет окрашиваться?\n"
            "• внутреннее помещение\n• фасад здания\n• стена",
            'calc_ask_type', {'calc_total': 0, 'calc_remaining': 0})


def _handle_calculator(msg, stage, context):
    tags = _extract_tags(msg)
    num = _extract_number(msg)
    ctx = dict(context)

    if stage == 'calc_ask_type':
        if 'фасад' in tags:
            return ("Введите основные габариты здания, которое будет окрашиваться.\n\n"
                    "Сколько стен (сторон) у здания? (максимум 20)",
                    'calc_facade_count', {**ctx, 'calc_total': 0})
        if 'стены' in tags:
            return ("Введите основные габариты стены, которая будет окрашиваться.\n\n"
                    "Высота стены (м):", 'calc_wall_h', {})
        if 'внутри' in tags or 'пол' in tags or 'потолок' in tags or 'помещени' in msg.lower():
            return ("Введите основные габариты помещения, где предполагается окраска.\n\n"
                    "Длина помещения (м):", 'calc_interior_length', {})
        return ("Уточните, пожалуйста: внутреннее помещение, фасад здания или стена?",
                'calc_ask_type', ctx)

    if stage == 'calc_interior_length':
        if num is None:
            return "Пожалуйста, введите длину числом (например, 4 или 4.5).", stage, ctx
        ctx['length'] = num
        return "Ширина помещения (м):", 'calc_interior_width', ctx
    if stage == 'calc_interior_width':
        if num is None:
            return "Пожалуйста, введите ширину числом.", stage, ctx
        ctx['width'] = num
        return "Высота потолков (м):", 'calc_interior_height', ctx
    if stage == 'calc_interior_height':
        if num is None:
            return "Пожалуйста, введите высоту числом.", stage, ctx
        ctx['height'] = num
        return "Количество стандартных одностворчатых окон (1,6 м² каждое):", 'calc_interior_windows', ctx
    if stage == 'calc_interior_windows':
        if num is None:
            return "Пожалуйста, введите количество окон числом (0, если нет).", stage, ctx
        ctx['windows'] = int(num)
        return "Количество стандартных однодверных дверей (1,9 м² каждая):", 'calc_interior_doors', ctx
    if stage == 'calc_interior_doors':
        if num is None:
            return "Пожалуйста, введите количество дверей числом (0, если нет).", stage, ctx
        ctx['doors'] = int(num)
        area = 2 * (ctx['length'] + ctx['width']) * ctx['height'] \
               - ctx['windows'] * WINDOW_AREA - ctx['doors'] * DOOR_AREA
        return _calc_result(area, ctx)

    if stage == 'calc_facade_count':
        if num is None or num < 1:
            return "Пожалуйста, введите количество стен числом (1–20).", stage, ctx
        n = min(int(num), 20)
        ctx['calc_remaining'] = n
        ctx['calc_total'] = 0
        ctx['calc_wall_num'] = 1
        return (f"Стена №{ctx['calc_wall_num']}.\nВысота стены (м):", 'calc_facade_h', ctx)
    if stage == 'calc_facade_h':
        if num is None:
            return "Пожалуйста, введите высоту числом.", stage, ctx
        ctx['h'] = num
        return (f"Стена №{ctx['calc_wall_num']}.\nШирина стены (м):", 'calc_facade_w', ctx)
    if stage == 'calc_facade_w':
        if num is None:
            return "Пожалуйста, введите ширину числом.", stage, ctx
        ctx['w'] = num
        return (f"Стена №{ctx['calc_wall_num']}.\nКоличество окон на этой стене:",
                'calc_facade_win', ctx)
    if stage == 'calc_facade_win':
        if num is None:
            return "Пожалуйста, введите количество окон числом (0, если нет).", stage, ctx
        ctx['win'] = int(num)
        return (f"Стена №{ctx['calc_wall_num']}.\nКоличество дверей на этой стене:",
                'calc_facade_door', ctx)
    if stage == 'calc_facade_door':
        if num is None:
            return "Пожалуйста, введите количество дверей числом (0, если нет).", stage, ctx
        ctx['door'] = int(num)
        wall_area = ctx['h'] * ctx['w'] - ctx['win'] * WINDOW_AREA - ctx['door'] * DOOR_AREA
        ctx['calc_total'] += wall_area
        ctx['calc_remaining'] -= 1
        if ctx['calc_remaining'] > 0:
            ctx['calc_wall_num'] += 1
            return (f"Стена №{ctx['calc_wall_num']}.\nВысота стены (м):", 'calc_facade_h', ctx)
        return _calc_result(ctx['calc_total'], ctx)

    if stage == 'calc_wall_h':
        if num is None:
            return "Пожалуйста, введите высоту числом.", stage, ctx
        ctx['h'] = num
        return "Ширина стены (м):", 'calc_wall_w', ctx
    if stage == 'calc_wall_w':
        if num is None:
            return "Пожалуйста, введите ширину числом.", stage, ctx
        ctx['w'] = num
        return "Количество окон на стене:", 'calc_wall_win', ctx
    if stage == 'calc_wall_win':
        if num is None:
            return "Пожалуйста, введите количество окон числом (0, если нет).", stage, ctx
        ctx['win'] = int(num)
        return "Количество дверей на стене:", 'calc_wall_door', ctx
    if stage == 'calc_wall_door':
        if num is None:
            return "Пожалуйста, введите количество дверей числом (0, если нет).", stage, ctx
        ctx['door'] = int(num)
        area = ctx['h'] * ctx['w'] - ctx['win'] * WINDOW_AREA - ctx['door'] * DOOR_AREA
        return _calc_result(area, ctx)

    if stage == 'calc_ask_more':
        if _is_yes(msg):
            return ("Продолжим расчёт средней окрашиваемой площади.\n\n"
                    "Что будет окрашиваться?\n"
                    "• внутреннее помещение\n• фасад здания\n• стена",
                    'calc_ask_type', {'calc_total': 0, 'calc_remaining': 0})
        if _is_no(msg):
            return ("Чем ещё я могу Вам помочь?\n\nМогу подобрать ассортимент, "
                    "проконсультировать по процессу покраски или ответить на "
                    "типовые вопросы.", 'start', {})
        return ("Уточните, пожалуйста: будут ли ещё окрашиваемые поверхности? (да / нет)",
                'calc_ask_more', ctx)

    return ("Не понял, вернёмся к началу расчёта.", 'calc_ask_type', {})


def _calc_result(area, ctx):
    reply = (f"Вот примерная площадь, предстоящая к покраске: {round(area, 2)} м²\n\n"
             "Учитывайте, что это только приблизительная площадь, полученная из "
             "введённых вами данных. Есть вероятность погрешности.\n\n"
             "Будут ли ещё окрашиваемые поверхности?")
    return reply, 'calc_ask_more', {**ctx, 'calc_last_area': area}


# ---------- КОНСУЛЬТАЦИИ ----------
def _detect_consultation_topic(tags):
    if tags & {'кафель', 'стекло', 'пластик', 'плитка', 'сложная поверхность'}:
        return 'complex'
    if 'оцинковка' in tags:
        return 'galvanized'
    if 'металл' in tags:
        return 'metal'
    if 'терраса' in tags or ('пол' in tags and 'снаружи' in tags):
        return 'terrace'
    if 'фасад' in tags:
        return 'facade_wood'
    if tags & {'баня', 'сауна'}:
        return 'sauna'
    if 'ванная' in tags and (tags & {'стены', 'потолок'} or 'внутри' in tags):
        return 'bathroom'
    if 'дерево' in tags or 'паркет' in tags or 'мебель' in tags or 'декор' in tags:
        return 'wood_inside'
    if tags & {'стены', 'потолок'}:
        return 'walls_inside'
    if 'пол' in tags:
        return 'wood_inside'
    return None


def _clarify_new_or_update(topic):
    return ("Уточните, пожалуйста: вы обновляете старую покраску "
            "или красите заново?", f'consult_{topic}_ask_new', {})


def _start_consultation(topic, tags):
    if topic == 'complex':
        return (texts.COMPLEX, 'start', {})
    if topic == 'metal':
        return (texts.METAL, 'start', {})
    if topic == 'galvanized':
        return (texts.GALVANIZED, 'start', {})
    if topic == 'bathroom':
        return (texts.BATHROOM_TEXT, 'start', {})
    if topic == 'terrace':
        if 'обновить' in tags:
            return (texts.TERRACE_UPDATE + "\n\n" + texts.BLOCK_WALK_24H, 'start', {})
        if 'новое' in tags:
            return ("Хотите лессирующую поверхность (чтобы структуру дерева было "
                    "видно) или кроющую (чтобы всё было укрыто одним цветом)?",
                    'consult_terrace_ask_type', {})
        return ("Красите новое или обновляете?", 'consult_terrace_ask_new', {})
    if topic == 'facade_wood':
        if 'обновить' in tags:
            return (texts.FACADE_UPDATE, 'start', {})
        if 'новое' in tags:
            return (texts.FACADE_NEW, 'start', {})
        return ("Хотите красить заново или обновить окрашенное?", 'consult_facade_ask_new', {})
    if topic == 'walls_inside':
        if 'обновить' in tags:
            return (texts.WALLS_UPDATE, 'start', {})
        if 'новое' in tags:
            return ("Подготовлена ли поверхность к покраске (стены зашпатлёваны "
                    "и прогрунтованы, потолок чистый и ровный)?",
                    'consult_walls_ask_prepared', {})
        return ("Это будет обновление старой покраски, или красите заново?",
                'consult_walls_ask_new', {})
    if topic == 'wood_inside':
        if 'стены' in tags or 'потолок' in tags:
            if 'обновить' in tags:
                return (texts.WOOD_WALLS_UPDATE, 'start', {})
            if 'новое' in tags:
                return (texts.WOOD_WALLS_FIRST, 'start', {})
            return ("Будете обновлять старое или красите в первый раз?",
                    'consult_wood_walls_ask_new', {})
        if 'пол' in tags or 'паркет' in tags:
            if 'обновить' in tags:
                return (texts.WOOD_FLOOR_UPDATE, 'start', {})
            if 'новое' in tags:
                return (texts.WOOD_FLOOR_NEW, 'start', {})
            return ("Обновляете или красите по новой?", 'consult_wood_floor_ask_new', {})
        if 'декор' in tags:
            if 'обновить' in tags:
                return (texts.WOOD_DECOR_UPDATE, 'start', {})
            if 'новое' in tags:
                return (texts.WOOD_DECOR_NEW, 'start', {})
            return ("Обновляете или красите с нуля?", 'consult_wood_decor_ask_new', {})
        if 'мебель' in tags:
            if 'обновить' in tags:
                return (texts.WOOD_FURNITURE_UPDATE, 'start', {})
            if 'новое' in tags:
                return (texts.WOOD_FURNITURE_NEW, 'start', {})
            return ("Обновить или покрыть новое?", 'consult_wood_furniture_ask_new', {})
        if 'мелкие изделия' in tags:
            return (texts.WOOD_SMALL, 'start', {})
        return ("Это будут стены, потолок, пол, элементы декора (вроде реек), "
                "мебель или мелкие изделия?", 'consult_wood_ask_what', {})
    if topic == 'sauna':
        if 'обновить' in tags:
            return (texts.SAUNA_UPDATE, 'start', {})
        if 'новое' in tags:
            return (texts.SAUNA_NEW, 'start', {})
        return ("Вы обновляете или красите по новой?", 'consult_sauna_ask_new', {})
    return ("Уточните, пожалуйста, что именно красите.", 'start', {})


def _handle_consultation_reply(msg, stage, context, tags):
    if stage == 'consult_terrace_ask_new':
        if 'обновить' in tags:
            return (texts.TERRACE_UPDATE + "\n\n" + texts.BLOCK_WALK_24H, 'start', {})
        if 'новое' in tags:
            return ("Хотите лессирующую поверхность (чтобы структуру дерева было "
                    "видно) или кроющую (чтобы всё было укрыто одним цветом)?",
                    'consult_terrace_ask_type', {})
        return _clarify_new_or_update('terrace')
    if stage == 'consult_terrace_ask_type':
        if 'лессирующая' in tags:
            return (texts.TERRACE_LESS_INTRO + "\n\n"
                    "Хотите плёночный материал (лак — создаёт тонкую плёнку) "
                    "или бесплёночный (масло — впитывается без плёнки)?",
                    'consult_terrace_ask_film', {})
        if 'кроющая' in tags:
            return (texts.TERRACE_COVER + "\n\n" + texts.BLOCK_WALK_24H, 'start', {})
        return ("Уточните, пожалуйста: лессирующая (структуру дерева видно) "
                "или кроющая (всё укрыто одним цветом)?",
                'consult_terrace_ask_type', {})
    if stage == 'consult_terrace_ask_film':
        if 'плёнка' in tags:
            return (texts.TERRACE_LESS_FILM + "\n\n" + texts.BLOCK_WALK_24H, 'start', {})
        if 'бесплёночный' in tags:
            return (texts.TERRACE_LESS_NOFILM + "\n\n" + texts.BLOCK_WALK_24H, 'start', {})
        return ("Уточните: плёночный (лак) или бесплёночный (масло, пропитка)?",
                'consult_terrace_ask_film', {})
    if stage == 'consult_facade_ask_new':
        if 'обновить' in tags:
            return (texts.FACADE_UPDATE, 'start', {})
        if 'новое' in tags:
            return (texts.FACADE_NEW, 'start', {})
        return _clarify_new_or_update('facade')
    if stage == 'consult_walls_ask_new':
        if 'обновить' in tags:
            return (texts.WALLS_UPDATE, 'start', {})
        if 'новое' in tags:
            return ("Подготовлена ли поверхность к покраске (стены зашпатлёваны "
                    "и прогрунтованы, потолок чистый и ровный)?",
                    'consult_walls_ask_prepared', {})
        return _clarify_new_or_update('walls')
    if stage == 'consult_walls_ask_prepared':
        if 'не подготовлена' in tags:
            return (texts.WALLS_NEW_NOTPREPARED, 'start', {})
        if 'частично' in tags:
            return (texts.WALLS_NEW_PARTIAL, 'start', {})
        if 'подготовлена' in tags:
            return (texts.WALLS_NEW_PREPARED, 'start', {})
        return ("Уточните, пожалуйста: поверхность подготовлена, не подготовлена, "
                "или частично (зашпатлёвана, но не загрунтована)?",
                'consult_walls_ask_prepared', {})
    if stage == 'consult_wood_ask_what':
        if 'стены' in tags or 'потолок' in tags:
            return ("Будете обновлять старое или красите в первый раз?",
                    'consult_wood_walls_ask_new', {})
        if 'пол' in tags or 'паркет' in tags:
            return ("Обновляете или красите по новой?", 'consult_wood_floor_ask_new', {})
        if 'декор' in tags:
            return ("Обновляете или красите с нуля?", 'consult_wood_decor_ask_new', {})
        if 'мебель' in tags:
            return ("Обновить или покрыть новое?", 'consult_wood_furniture_ask_new', {})
        if 'мелкие изделия' in tags:
            return (texts.WOOD_SMALL, 'start', {})
        return ("Уточните: стены, потолок, пол, элементы декора, мебель "
                "или мелкие изделия?", 'consult_wood_ask_what', {})
    if stage == 'consult_wood_walls_ask_new':
        if 'обновить' in tags:
            return (texts.WOOD_WALLS_UPDATE, 'start', {})
        if 'новое' in tags:
            return (texts.WOOD_WALLS_FIRST, 'start', {})
        return _clarify_new_or_update('wood_walls')
    if stage == 'consult_wood_floor_ask_new':
        if 'обновить' in tags:
            return (texts.WOOD_FLOOR_UPDATE, 'start', {})
        if 'новое' in tags:
            return (texts.WOOD_FLOOR_NEW, 'start', {})
        return _clarify_new_or_update('wood_floor')
    if stage == 'consult_wood_decor_ask_new':
        if 'обновить' in tags:
            return (texts.WOOD_DECOR_UPDATE, 'start', {})
        if 'новое' in tags:
            return (texts.WOOD_DECOR_NEW, 'start', {})
        return _clarify_new_or_update('wood_decor')
    if stage == 'consult_wood_furniture_ask_new':
        if 'обновить' in tags:
            return (texts.WOOD_FURNITURE_UPDATE, 'start', {})
        if 'новое' in tags:
            return (texts.WOOD_FURNITURE_NEW, 'start', {})
        return _clarify_new_or_update('wood_furniture')
    if stage == 'consult_sauna_ask_new':
        if 'обновить' in tags:
            return (texts.SAUNA_UPDATE, 'start', {})
        if 'новое' in tags:
            return (texts.SAUNA_NEW, 'start', {})
        return _clarify_new_or_update('sauna')
    return ("Не совсем понял. Попробуйте сформулировать иначе.", 'start', {})


# ---------- ПОДБОР ----------
def _score_products(msg):
    tags = _extract_tags(msg)
    scored = []
    for p in CATALOG:
        if p.get('is_secondary'):
            continue
        matches = tags & set(p['keywords'])
        if len(matches) >= 2:
            scored.append((p['priority'], len(matches), p))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    return [p for _, _, p in scored], tags


def _is_specific_lkm_without_surface(msg):
    tags = _extract_tags(msg)
    surfaces = {'стены', 'потолок', 'пол', 'фасад', 'металл', 'дерево', 'мебель',
                'терраса', 'баня', 'сауна', 'цоколь', 'кафель', 'стекло',
                'пластик', 'плитка', 'ванная'}
    return 'краска' in tags and not (tags & surfaces)


def _handle_selection(msg, stage, context):
    candidates, tags = _score_products(msg)

    if not candidates:
        return (
            "Пока не нашёл подходящего продукта в каталоге.\n\n"
            "Уточните, пожалуйста:\n"
            "• какую поверхность красите (стены, потолок, пол, металл, дерево)?\n"
            "• какие условия (внутри или снаружи, сухое или влажное помещение)?",
            stage, {**context, 'last_query': msg, 'shown_names': []}
        )

    is_single_or_no_alt = (len(candidates) == 1) or (candidates[0]['priority'] == 4)
    primary = candidates[:2]
    secondary = _pick_secondary(tags) if 'новое' in tags else []
    if is_single_or_no_alt:
        primary = candidates[:1]

    reply = _format_selection_reply(primary, secondary, is_single_or_no_alt)
    new_ctx = {
        **context,
        'last_query': msg,
        'shown_names': [p['name'] for p in primary]
    }
    return reply, 'selection', new_ctx


def _handle_more_request(msg, context):
    last_query = context.get('last_query', '')
    shown_names = context.get('shown_names', [])

    if not last_query:
        return ("Не могу подобрать «ещё» — сначала опишите, что красите.", 'start', {})

    candidates, _ = _score_products(last_query)
    remaining = [p for p in candidates if p['name'] not in shown_names]

    if not remaining:
        return (
            "Я предложил все варианты какие имеются под ваш запрос. Может быть, "
            "хотите спросить что-то ещё? Или узнать поподробнее о конкретной позиции?",
            'selection', context
        )

    primary = remaining[:2]
    reply = _format_selection_reply(primary, [], False)
    new_shown = shown_names + [p['name'] for p in primary]
    return (reply, 'selection', {**context, 'shown_names': new_shown})


def _pick_secondary(tags):
    if 'металл' in tags:
        return [p for p in CATALOG if p['name'] == 'Tikkivala Metallista Primer']
    if 'дерево' in tags and 'снаружи' in tags:
        return [p for p in CATALOG if p['name'] == 'Tikkivala Valtti Expert Base']
    if 'стены' in tags or 'потолок' in tags:
        if 'снаружи' in tags:
            return [p for p in CATALOG if p['name'] == 'Tikkivala Facade Deep Primer']
        return [p for p in CATALOG if p['name'] == 'Tikkivala Euro Base']
    if 'пол' in tags:
        return [p for p in CATALOG if p['name'] == 'Tikkivala Euro Base']
    return []


def _format_selection_reply(primary, secondary, is_single=False):
    lines = []
    if is_single:
        lines.append("Единственное что мы можем предложить:")
    else:
        lines.append("Подойдут такие варианты:")
    for p in primary:
        lines.append("")
        lines.append(f"• {p['name']} — {p['category']}")
        lines.append(f"  Блеск: {p.get('gloss', '—')}, база: {p.get('base', '—')}")
        lines.append(f"  Площадь: {p.get('coverage', '—')}")
        lines.append(f"  Разбавитель: {p.get('thinner', '—')}")
    if secondary:
        lines.append("")
        lines.append("Дополнительно для новой покраски:")
        for p in secondary:
            lines.append(f"• {p['name']} — {p['category']}")
    lines.append("")
    lines.append("Если нужна консультация по процессу покраски — просто спросите.")
    return "\n".join(lines)


# ---------- ГЛАВНАЯ ФУНКЦИЯ ----------
def route_message(user_message: str, stage: str, context: dict):
    msg = user_message.lower().strip()
    tags = _extract_tags(msg)

    if _is_farewell(msg):
        return "Был рад общению, всего хорошего.", 'farewell', {}

    if stage.startswith('calc_'):
        return _handle_calculator(msg, stage, context)

    if stage.startswith('consult_'):
        return _handle_consultation_reply(msg, stage, context, tags)

    if stage == 'shop_ask_city':
        return _handle_shops(msg, stage, context)

    if _is_greeting(msg) and stage != 'start':
        return ("Здравствуйте! Что вас интересует — покраска, подбор ассортимента, "
                "адреса магазинов или расчёт площади?", stage, context)

    if stage == 'selection' and _is_more_request(msg):
        return _handle_more_request(msg, context)

    # Магазины — приоритет перед продуктом и FAQ
    if _is_shops_request(msg):
        return _handle_shops(msg, stage, context)

    mentioned = _detect_product_mention(msg)
    if mentioned:
        return (_handle_product_mention(mentioned, msg), 'start', {})

    if _is_faq(msg):
        answer = _handle_faq(msg)
        if answer:
            return (answer, 'start', {})

    if _is_calculator_start(msg):
        return _calc_ask_type()

    if _is_consultation_request(msg):
        topic = _detect_consultation_topic(tags)
        if topic:
            return _start_consultation(topic, tags)

    if _is_specific_lkm_without_surface(msg):
        return ("Вам нужна краска для стен или для потолка?", 'start', context)

    if _is_selection_request(msg):
        result = _handle_selection(msg, stage, context)
        if 'Пока не нашёл' in result[0]:
            topic = _detect_consultation_topic(tags)
            if topic:
                extra = ("\n\nМогу рассказать, как правильно красить — "
                         "просто напишите, что именно красите.")
                return (result[0] + extra, result[1], result[2])
        return result

    return ("Извините, я не понял. Пожалуйста, сформулируйте вопрос иначе. "
            "Или я могу подсказать по темам: покраска разных поверхностей, "
            "подбор ассортимента, калькулятор площади, типовые вопросы "
            "(про ЛКМ, выбор инструмента, разницу между красками и эмалями и т.п.).",
            'start', {})