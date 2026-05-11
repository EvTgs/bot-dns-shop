from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import statistics
from collections.abc import AsyncIterator, Callable
from dataclasses import replace
from pathlib import Path
from typing import Awaitable
from urllib.parse import urlparse

from .deepseek_client import DeepSeekClient
from .dns_search_parser import (
    DnsFilterSelectionError,
    Product,
    build_category_resolution_url,
    build_dns_url_from_section_filters,
    classify_query_params,
    collect_products_by_url,
    fetch_compare_characteristics_for_products,
    http_resolve_url,
    inspect_dns_section_filters,
    normalize_dns_url,
    postprocess_products,
    prewarm_dns_cookies,
    resolve_category_if_missing,
    browser_resolve_url,
)
from .orchestrator_contracts import BotAnalysisResult, IntentRoute, NormalizedConstraint, NormalizedSearchRequest
from .orchestrator_finalization import (
    build_teacher_corrected_analysis_answer,
    ensure_complete_analysis_answer,
    ensure_teacher_checked_analysis_answer,
    enforce_chat_answer_constraints,
    extract_chat_format_constraints,
    parse_analysis_sections,
)
from .orchestrator_json import parse_llm_json_payload, should_retry_router_response
from .orchestrator_prompts import (
    CHAT_TEACHER_SYSTEM_PROMPT,
    FILTER_SELECTION_SYSTEM_PROMPT,
    FINAL_ANALYSIS_SYSTEM_PROMPT,
    FOLLOWUP_DIRECT_SYSTEM_PROMPT,
    GENERAL_CHAT_SYSTEM_PROMPT,
    NORMALIZE_QUERY_SYSTEM_PROMPT,
    ROUTER_SYSTEM_PROMPT,
)
from .normalization.price import (
    CYRILLIC_RE,
    PRICE_BUCKET_TEXT_RE,
    PRICE_RANGE_RE,
    PRICE_SINGLE_RE,
    extract_price_hint,
    normalize_price_pair,
)


DEFAULT_PRODUCT_LIMIT = None
DEFAULT_ANALOG_SEARCH_TIMEOUT_SECONDS = 20.0
DETAILS_LIMIT = 8
SHORTLIST_LIMIT = 5
SHORTLIST_CANDIDATE_LIMIT = 20
logger = logging.getLogger("dns_bot.orchestrator")
COMPARE_CITY_ID = "128"
AI_CHAIN_REQUEST = "request"
AI_CHAIN_CATEGORY_FILTERS = "category_and_filters"
AI_CHAIN_FILTERS_AI = "filters_ai"
AI_CHAIN_BUILT_URL = "built_url"
AI_CHAIN_LIST = "list"
AI_CHAIN_SHORTLIST_AI = "shortlist_ai"
AI_CHAIN_DETAILS = "details"
AI_CHAIN_FINAL_AI = "final_ai"
AI_CHAIN_OUTPUT = "output"
SEARCH_INTENT_RE = re.compile(r"\b(найди|подбери|покажи|выбери|посоветуй|нужен|нужна|нужно|хочу)\b", re.IGNORECASE)
BOT_META_RE = re.compile(r"\b(бот|умеет|умеешь|можешь|возможност)\b", re.IGNORECASE)
FOLLOWUP_RE = re.compile(r"\b(какой|какая|какое|какие|лучше|хуже|почему|отличается|разница)\b", re.IGNORECASE)
BOT_PROCESS_META_RE = re.compile(
    r"(если\s+я\s+попрошу|что\s+ты\s+сделаешь|как\s+ты\s+будешь|по\s+шагам)",
    re.IGNORECASE,
)
FORMAT_FOLLOWUP_RE = re.compile(
    r"\b(ответь|перепиши|сократи|короче|кратко|без\s+списка|одним\s+абзацем|в\s+\d+\s+предложениях|суть)\b",
    re.IGNORECASE,
)
NUMERIC_VALUE_RE = re.compile(r"\d+(?:[.,]\d+)?")
PRODUCT_TYPE_QUERY_MAP = {
    "tablet": "планшет",
    "smartphone": "смартфон",
    "phone": "смартфон",
    "laptop": "ноутбук",
    "electricgrill": "гриль",
    "electric_grill": "гриль",
    "mfp": "мфу",
    "printer": "мфу",
    "exercisebike": "велотренажер",
    "exercise_bike": "велотренажер",
    "sewingmachine": "швейная машина",
    "sewing_machine": "швейная машина",
    "washingmachine": "стиральная машина",
    "robotvacuum": "робот-пылесос",
    "coffee_machine": "кофемашина",
    "coffeemachine": "кофемашина",
    "airconditioner": "кондиционер",
    "conditioning": "кондиционер",
    "gameconsole": "игровая приставка",
    "gamesconsole": "игровая приставка",
    "console": "игровая приставка",
    "refrigerator": "холодильник",
    "keyboard": "клавиатура",
    "mouse": "мышь",
    "monitor": "монитор",
    "tv": "телевизор",
    "ssd": "ssd",
    "hdd": "hdd",
    "router": "роутер",
    "graphicscard": "видеокарта",
    "graphics_card": "видеокарта",
    "videocard": "видеокарта",
    "processor": "процессор",
    "headphones": "наушники",
    "vacuumcleaner": "робот-пылесос",
    "dishwasher": "посудомоечная машина",
    "washing_machine": "стиральная машина",
    "air_conditioner": "кондиционер",
    "coffee_maker": "кофемашина",
    "gamingchair": "игровое кресло",
    "chair": "кресло",
}
STATIC_CATEGORY_ID_BY_PRODUCT_TYPE = {
    "keyboard": "17a8950d16404e77",
    "laptop": "17a892f816404e77",
    "monitor": "17a8943716404e77",
    "smartphone": "17a8a01d16404e77",
    "phone": "17a8a01d16404e77",
    "sewingmachine": "17a8cda216404e77",
    "sewing_machine": "17a8cda216404e77",
    "tv": "17a8ae4916404e77",
    "tablet": "17a8947216404e77",
    "refrigerator": "17a8ab8416404e77",
    "washingmachine": "17a8ad2a16404e77",
    "robotvacuum": "17a8d26216404e77",
    "airconditioner": "17a8a6af16404e77",
    "electricgrill": "17a8e0f216404e77",
    "mfp": "17a8c3a616404e77",
    "printer": "17a8c3a616404e77",
    "exercisebike": "17a8d9c316404e77",
}
STATIC_CATEGORY_STARTUP_PRODUCT_TYPES = ("monitor", "laptop", "smartphone", "keyboard", "tv")
PRODUCT_TYPE_QUERY_HINT_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("monitor", re.compile(r"\bмонитор\w*\b", re.IGNORECASE), "монитор"),
    ("laptop", re.compile(r"\b(?:ноутбук\w*|macbook)\b|\bмакбук\w*\b", re.IGNORECASE), "ноутбук"),
    ("tablet", re.compile(r"\bпланшет\w*\b", re.IGNORECASE), "планшет"),
    ("tv", re.compile(r"\b(?:телевизор\w*|tv)\b", re.IGNORECASE), "телевизор"),
    ("electricgrill", re.compile(r"\b(?:электро[-\s]*гриль\w*|электрогриль\w*)\b", re.IGNORECASE), "гриль"),
    ("mfp", re.compile(r"\b(?:мфу|лазерн\w*\s+мфу|принтер\w*|multifunction)\b", re.IGNORECASE), "мфу"),
    ("exercisebike", re.compile(r"\bвелотренажер\w*\b", re.IGNORECASE), "велотренажер"),
    ("graphicscard", re.compile(r"\b(?:видеокарт\w*|rtx\s*40\d0|geforce)\b", re.IGNORECASE), "видеокарта"),
    ("gamingchair", re.compile(r"\bигров\w*\s+кресл\w*\b", re.IGNORECASE), "игровое кресло"),
    ("chair", re.compile(r"\bкресл\w*\b", re.IGNORECASE), "кресло"),
    ("sewingmachine", re.compile(r"\bшвейн\w*\s+машин\w*\b|\bsewing\s+machine\b", re.IGNORECASE), "швейная машина"),
    ("washingmachine", re.compile(r"\bстиральн\w*\b", re.IGNORECASE), "стиральная машина"),
    ("robotvacuum", re.compile(r"\b(?:робот[-\s]*пылесос\w*|пылесос\w*)\b", re.IGNORECASE), "робот-пылесос"),
    ("hdd", re.compile(r"\b(?:жестк\w*\s+диск\w*|hdd)\b", re.IGNORECASE), "жесткий диск"),
    ("coffee_machine", re.compile(r"\bкофемашин\w*\b", re.IGNORECASE), "кофемашина"),
    ("airconditioner", re.compile(r"\b(?:кондиционер\w*|сплит[-\s]*систем\w*)\b", re.IGNORECASE), "кондиционер"),
    ("gameconsole", re.compile(r"\b(?:игров\w*[\s-]*приставк\w*|игровая\s+консоль|консоль)\b", re.IGNORECASE), "игровая приставка"),
    ("refrigerator", re.compile(r"\bхолодильник\w*\b", re.IGNORECASE), "холодильник"),
    ("smartphone", re.compile(r"\b(?:смартфон\w*|телефон\w*|iphone)\b|\bайфон\w*\b", re.IGNORECASE), "смартфон"),
)
BRAND_ALIASES = {
    "acer": ("асер",),
    "apple": ("эпл", "macbook", "макбук", "iphone", "айфон"),
    "bosch": ("бош",),
    "lenovo": ("леново",),
    "lg": ("лджи", "элджи", "lg"),
    "samsung": ("самсунг",),
    "xiaomi": ("сяоми", "ксяоми", "сиаоми", "redmi", "редми"),
}
WISH_ALIASES = {
    "oled": ("oled", "amoled", "super amoled", "dynamic amoled"),
    "amoled_display": ("amoled", "oled", "super amoled", "dynamic amoled"),
    "nfc": ("nfc",),
    "5g": ("5g",),
    "qualcom_processor": ("qualcomm", "snapdragon"),
    "good_camera": ("camera", "камера", "mp", "мп"),
    "good_battery": ("battery", "аккумулятор", "акб", "мач", "mah"),
    "bright_screen": ("яркий экран", "яркость", "brightness", "нит", "nits", "кд/м", "cd/m"),
    "1440p": ("2560x1440", "qhd", "1440p"),
    "27_inch": ("27", "27.0"),
    "ips": ("ips",),
    "height_adjustable": ("height", "высот"),
    "16gb_ram": ("16", "16gb", "16_gb", "озу", "ram"),
    "16_gb_ram": ("16", "16gb", "16_gb", "озу", "ram"),
    "12gb_ram": ("12", "12gb", "12_gb", "озу", "ram"),
    "storage_from_256_gb": ("256", "256gb", "256_gb", "память", "storage"),
    "ssd_from_512_gb": ("512", "512gb", "512_gb", "ssd"),
    "weight_up_to_1.5_kg": ("1.5", "1,5", "kg", "кг", "вес"),
    "32gb_ram": ("32", "32gb", "32_gb", "озу", "ram"),
    "240hz_screen": ("240", "240hz", "240_hz", "240_гц"),
    "240hz_display": ("240", "240hz", "240_hz", "240_гц"),
    "weight_up_to_2.5_kg": ("2.5", "2,5", "2.49", "kg", "кг", "вес"),
    "weight_up_to_2.5kg": ("2.5", "2,5", "2.49", "kg", "кг", "вес"),
    "weight_up_to_2.3_kg": ("2.3", "2,3", "kg", "кг", "вес"),
    "matte_screen": ("матовое", "матовый", "антибликовое", "anti_glare", "matte"),
    "rtx_4060": ("rtx_4060", "rtx4060", "geforce_rtx_4060"),
    "rtx_4070": ("rtx_4070", "rtx4070", "geforce_rtx_4070"),
    "rtx_4070_or_higher": ("rtx_4070", "rtx4070", "geforce_rtx_4070", "rtx_4080", "rtx4080", "geforce_rtx_4080", "rtx_4090", "rtx4090", "geforce_rtx_4090"),
    "rtx_4080": ("rtx_4080", "rtx4080", "geforce_rtx_4080"),
    "refresh_rate_from_165hz": ("165", "180", "240", "250", "300", "360", "hz", "гц"),
    "refresh_rate_from_120hz": ("120", "144", "165", "180", "240", "250", "300", "360", "hz", "гц"),
    "mechanical_keyboard": ("механическая", "mechanical"),
    "2024_year": ("2024",),
    "year_from_2024": ("2024", "2025", "2026"),
    "2024_model": ("2024",),
    "for_programmer": ("для программиста", "для программирования"),
    "for_gaming": ("игровой", "для игр", "гейминг", "gaming"),
    "mapping": ("карта", "построение карты", "mapping"),
    "matrix_type_amoled": ("amoled", "super amoled", "dynamic amoled", "amoled 2x", "амолед", "супер амолед"),
    "matrix_type_oled": ("oled", "олед"),
    "matrix_type_ips": ("ips",),
    "matrix_type_va": ("va", "va матрица", "ва матрица"),
    "matrix_type_qled": ("qled",),
    "network_5g": ("5g",),
    "fast_charge": ("быстрая зарядка", "fast charge"),
    "wireless_charge": ("беспроводная зарядка", "wireless charge"),
    "waterproof_ip67": ("ip67",),
    "waterproof_ip68": ("ip68",),
    "cooling_system_no_frost": ("no_frost", "no frost", "full no frost", "total no frost"),
    "freezer_position_bottom": ("морозильная камера снизу", "морозильной камерой снизу", "bottom freezer", "нижнее расположение морозильной камеры", "снизу"),
    "inverter_compressor": ("инверторный компрессор", "инвертор", "inverter compressor"),
    "sewing_operations_from_30": ("швейные операции", "операций", "операции", "sewing operations"),
    "shuttle_type_horizontal": ("горизонтальный челнок", "горизонтальным челноком", "horizontal shuttle"),
    "buttonhole_automatic": ("автоматическое выполнение петли", "автоматической петли", "автоматическая петля", "automatic buttonhole"),
    "speed_control": ("регулировка скорости", "скорость шитья", "speed control"),
    "work_area_light": ("подсветка рабочей зоны", "подсветкой рабочей зоны", "illumination", "led"),
    "width_up_to_60_cm": ("60", "см", "ширина"),
    "volume_from_300_l": ("300", "л", "объем", "объём"),
    "energy_class_not_lower_than_a": ("a", "a+", "a++", "a+++", "энергопотребления"),
}
WISH_CANONICAL_MAP = {
    "27inch": "27_inch",
    "27_inch": "27_inch",
    "1440p": "1440p",
    "ips": "ips",
    "heightadjustable": "height_adjustable",
    "height_adjustable": "height_adjustable",
    "16gb_ram": "16gb_ram",
    "16_gb_ram": "16gb_ram",
    "32gb_ram": "32gb_ram",
    "32_gb_ram": "32gb_ram",
    "12gb_ram": "12gb_ram",
    "12_gb_ram": "12gb_ram",
    "ssd_from_512_gb": "ssd_from_512_gb",
    "power_from_1800_w": "power_from_1800_w",
    "removable_panels": "removable_panels",
    "nonstick_coating": "nonstick_coating",
    "temperature_control": "temperature_control",
    "grease_tray": "grease_tray",
    "opens_180": "opens_180",
    "smartphone_control": "smartphone_control",
    "battery_capacity_from_4000_mah": "battery_capacity_from_4000_mah",
    "auto_return_to_base": "auto_return_to_base",
    "dustbin_easy_cleaning": "dustbin_easy_cleaning",
    "good_navigation": "good_navigation",
    "device_type_mfp": "device_type_mfp",
    "print_technology_laser": "print_technology_laser",
    "color_mode_monochrome": "color_mode_monochrome",
    "wifi": "wifi",
    "duplex_print": "duplex_print",
    "scanner": "scanner",
    "print_speed_from_20_ppm": "print_speed_from_20_ppm",
    "refill_easy": "refill_easy",
    "cheap_maintenance": "cheap_maintenance",
    "resistance_system_magnetic": "resistance_system_magnetic",
    "max_user_weight_from_120_kg": "max_user_weight_from_120_kg",
    "seat_adjustment": "seat_adjustment",
    "display": "display",
    "pulse_measurement": "pulse_measurement",
    "resistance_levels_from_8": "resistance_levels_from_8",
    "stable_construction": "stable_construction",
    "machine_type_automatic": "machine_type_automatic",
    "cappuccinator": "cappuccinator",
    "pressure_from_15_bar": "pressure_from_15_bar",
    "built_in_grinder": "built_in_grinder",
    "strength_adjustment": "strength_adjustment",
    "portion_volume_adjustment": "portion_volume_adjustment",
    "self_cleaning": "self_cleaning",
    "easy_maintenance": "easy_maintenance",
    "reliable": "reliable",
    "weight_up_to_1.5_kg": "weight_up_to_1.5_kg",
    "weight_up_to_2.5_kg": "weight_up_to_2.5_kg",
    "weight_up_to_2.3_kg": "weight_up_to_2.3_kg",
    "sewing_operations_from_30": "sewing_operations_from_30",
    "shuttle_type_horizontal": "shuttle_type_horizontal",
    "buttonhole_automatic": "buttonhole_automatic",
    "speed_control": "speed_control",
    "work_area_light": "work_area_light",
    "amoled_display": "amoled_display",
    "oled": "oled",
    "nfc": "nfc",
    "240hz_screen": "240hz_screen",
    "240_hz_screen": "240hz_screen",
    "240hz_display": "240hz_screen",
    "matte_screen": "matte_screen",
    "matte_display": "matte_screen",
    "rtx_4060": "rtx_4060",
    "rtx_4080": "rtx_4080",
    "2024_year": "2024_year",
    "2024_model": "2024_year",
    "weight_up_to_2.5kg": "weight_up_to_2.5_kg",
    "good_camera": "good_camera",
    "good_battery": "good_battery",
    "bright_screen": "bright_screen",
    "powerful": "good_performance",
    "good_performance": "good_performance",
    "thin_bezel": "thin_bezel",
    "spacious": "spacious",
    "quiet": "quiet",
    "reliable": "reliable",
    "lightweight": "lightweight",
    "for_drawing": "for_drawing",
    "back_support": "back_support",
    "quality_build": "quality_build",
    "for_programmer": "for_programmer",
    "for_gaming": "for_gaming",
    "144hz_display": "144hz_display",
    "256gb_storage": "256gb_storage",
    "storage_from_256_gb": "storage_from_256_gb",
    "55_inch": "55_inch",
    "4k": "4k",
    "side_by_side": "side_by_side",
    "wet_cleaning": "wet_cleaning",
    "lidar_navigation": "lidar_navigation",
    "mapping": "mapping",
    "dryer": "dryer",
    "rtx_4070": "rtx_4070",
    "rtx_4070_or_higher": "rtx_4070_or_higher",
    "rtx4070_or_higher": "rtx_4070_or_higher",
    "refresh_rate_from_165hz": "refresh_rate_from_165hz",
    "refresh_rate_from_120hz": "refresh_rate_from_120hz",
    "165hz_or_higher": "refresh_rate_from_165hz",
    "year_from_2024": "year_from_2024",
    "ssd": "ssd",
    "mechanical_keyboard": "mechanical_keyboard",
    "keyboard_type_magnetic": "keyboard_type_magnetic",
    "magnetic_keyboard": "keyboard_type_magnetic",
    "keyboard_format_75_80": "keyboard_format_75_80",
    "matrix_type": "matrix_type_amoled",
    "matrix_type_amoled": "matrix_type_amoled",
    "matrix_type_oled": "matrix_type_oled",
    "matrix_type_ips": "matrix_type_ips",
    "matrix_type_va": "matrix_type_va",
    "matrix_type_qled": "matrix_type_qled",
    "5g": "network_5g",
    "network_5g": "network_5g",
    "fast_charge": "fast_charge",
    "wireless_charge": "wireless_charge",
    "waterproof_ip67": "waterproof_ip67",
    "waterproof_ip68": "waterproof_ip68",
    "cooling_system_no_frost": "cooling_system_no_frost",
    "freezer_position_bottom": "freezer_position_bottom",
    "freezer_position": "freezer_position_bottom",
    "inverter_compressor": "inverter_compressor",
    "compressor_type": "inverter_compressor",
    "width_up_to_60_cm": "width_up_to_60_cm",
    "volume_from_300_l": "volume_from_300_l",
    "energy_class_not_lower_than_a": "energy_class_not_lower_than_a",
}
NON_FILTERABLE_WISHES = {
    "good_camera",
    "good_battery",
    "quiet",
    "reliable",
    "good_performance",
    "for_programmer",
    "for_gaming",
    "lightweight",
    "bright_screen",
}
STRICT_SPEC_WISHES = {
    "27_inch",
    "1440p",
    "ips",
    "height_adjustable",
    "16gb_ram",
    "32gb_ram",
    "12gb_ram",
    "storage_from_256_gb",
    "ssd_from_512_gb",
    "weight_up_to_1.5_kg",
    "weight_up_to_2.5_kg",
    "weight_up_to_2.3_kg",
    "sewing_operations_from_30",
    "shuttle_type_horizontal",
    "buttonhole_automatic",
    "speed_control",
    "work_area_light",
    "nfc",
    "amoled_display",
    "oled",
    "240hz_screen",
    "refresh_rate_from_165hz",
    "refresh_rate_from_120hz",
    "matte_screen",
    "rtx_4070_or_higher",
    "rtx_4080",
    "2024_year",
    "year_from_2024",
    "matrix_type_amoled",
    "matrix_type_oled",
    "matrix_type_ips",
    "matrix_type_va",
    "matrix_type_qled",
    "network_5g",
    "fast_charge",
    "wireless_charge",
    "waterproof_ip67",
    "waterproof_ip68",
    "cooling_system_no_frost",
    "freezer_position_bottom",
    "inverter_compressor",
    "width_up_to_60_cm",
    "volume_from_300_l",
    "energy_class_not_lower_than_a",
    "keyboard_type_magnetic",
    "keyboard_format_75_80",
}
WISH_DISPLAY_NAMES = {
    "27_inch": "27 дюймов",
    "1440p": "1440p",
    "ips": "IPS",
    "height_adjustable": "регулировка высоты",
    "16gb_ram": "16 ГБ ОЗУ",
    "32gb_ram": "32 ГБ ОЗУ",
    "12gb_ram": "12 ГБ ОЗУ",
    "storage_from_256_gb": "накопитель от 256 ГБ",
    "ssd_from_512_gb": "SSD от 512 ГБ",
    "weight_up_to_1.5_kg": "вес до 1.5 кг",
    "weight_up_to_2.5_kg": "вес до 2.5 кг",
    "weight_up_to_2.3_kg": "вес до 2.3 кг",
    "sewing_operations_from_30": "не меньше 30 швейных операций",
    "shuttle_type_horizontal": "горизонтальный челнок",
    "buttonhole_automatic": "автоматическое выполнение петли",
    "speed_control": "регулировка скорости шитья",
    "work_area_light": "подсветка рабочей зоны",
    "nfc": "NFC",
    "amoled_display": "AMOLED",
    "oled": "OLED",
    "240hz_screen": "экран 240 Гц",
    "refresh_rate_from_165hz": "экран от 165 Гц",
    "refresh_rate_from_120hz": "экран от 120 Гц",
    "matte_screen": "матовое покрытие",
    "rtx_4070": "RTX 4070",
    "rtx_4070_or_higher": "RTX 4070 или выше",
    "rtx_4080": "RTX 4080",
    "2024_year": "2024 год выпуска",
    "year_from_2024": "2024 год выпуска или новее",
    "price_max": "бюджет",
    "mapping": "построение карты",
    "matrix_type_amoled": "матрица AMOLED",
    "matrix_type_oled": "матрица OLED",
    "matrix_type_ips": "матрица IPS",
    "matrix_type_va": "матрица VA",
    "matrix_type_qled": "матрица QLED",
    "network_5g": "5G",
    "fast_charge": "быстрая зарядка",
    "wireless_charge": "беспроводная зарядка",
    "waterproof_ip67": "влагозащита IP67",
    "waterproof_ip68": "влагозащита IP68",
    "cooling_system_no_frost": "No Frost",
    "freezer_position_bottom": "морозильная камера снизу",
    "inverter_compressor": "инверторный компрессор",
    "width_up_to_60_cm": "ширина до 60 см",
    "volume_from_300_l": "объём от 300 л",
    "energy_class_not_lower_than_a": "класс энергопотребления не ниже A",
    "brand": "бренд",
    "power_from_1800_w": "мощностью от 1800 Вт",
    "removable_panels": "съёмными панелями",
    "nonstick_coating": "антипригарным покрытием",
    "temperature_control": "регулировкой температуры",
    "grease_tray": "поддоном для жира",
    "opens_180": "раскрытием на 180 градусов",
    "smartphone_control": "управлением со смартфона",
    "battery_capacity_from_4000_mah": "аккумулятором от 4000 мА·ч",
    "auto_return_to_base": "автоматическим возвращением на базу",
    "dustbin_easy_cleaning": "простой очисткой контейнера",
    "good_navigation": "хорошей навигацией",
    "device_type_mfp": "лазерным МФУ",
    "print_technology_laser": "лазерной печатью",
    "color_mode_monochrome": "черно-белой печатью",
    "wifi": "Wi-Fi",
    "duplex_print": "двусторонней печатью",
    "scanner": "сканером",
    "print_speed_from_20_ppm": "скоростью от 20 стр/мин",
    "refill_easy": "простой заправкой",
    "cheap_maintenance": "недорогим обслуживанием",
    "resistance_system_magnetic": "магнитной системой нагрузки",
    "max_user_weight_from_120_kg": "весом пользователя от 120 кг",
    "seat_adjustment": "регулировкой сиденья",
    "display": "дисплеем",
    "pulse_measurement": "измерением пульса",
    "resistance_levels_from_8": "не меньше 8 уровней нагрузки",
    "stable_construction": "устойчивой конструкцией",
    "keyboard_type_magnetic": "магнитная клавиатура",
    "keyboard_format_75_80": "формат 75-80%",
    "machine_type_automatic": "автоматической кофемашиной",
    "cappuccinator": "капучинатором",
    "pressure_from_15_bar": "давлением от 15 бар",
    "built_in_grinder": "встроенной кофемолкой",
    "strength_adjustment": "регулировкой крепости",
    "portion_volume_adjustment": "регулировкой объема порции",
    "self_cleaning": "самоочисткой",
    "easy_maintenance": "простым обслуживанием",
    "reliable": "надежной сборкой",
}
STRUCTURED_ONLY_WISHES = {
    "12gb_ram",
    "16gb_ram",
    "32gb_ram",
    "storage_from_256_gb",
    "ssd_from_512_gb",
    "refresh_rate_from_120hz",
    "refresh_rate_from_165hz",
    "matrix_type_amoled",
    "matrix_type_oled",
    "matrix_type_ips",
    "matrix_type_va",
    "matrix_type_qled",
    "network_5g",
    "fast_charge",
    "wireless_charge",
    "waterproof_ip67",
    "waterproof_ip68",
    "cooling_system_no_frost",
    "freezer_position_bottom",
    "inverter_compressor",
    "width_up_to_60_cm",
    "volume_from_300_l",
    "energy_class_not_lower_than_a",
}
CONSTRAINT_KEY_SYNONYMS: dict[str, tuple[str, ...]] = {
    "refresh_rate": ("частота обновления", "частота экрана", "герц", "гц", "refresh rate"),
    "storage": ("встроенная память", "память", "объем памяти", "объём памяти", "накопитель", "storage"),
    "ram": ("оперативная память", "озу", "ram"),
    "matrix_type": ("матрица", "тип экрана", "технология матрицы", "тип матрицы", "экран"),
    "network": ("стандарт связи", "мобильная связь", "сети", "связи", "network"),
    "nfc": ("nfc",),
    "protection": ("степень защиты", "класс защиты", "ip", "влагозащита", "пылевлагозащита"),
    "fast_charge": ("быстрая зарядка",),
    "wireless_charge": ("беспроводная зарядка",),
    "year": ("год релиза", "год выпуска", "релиз"),
    "resolution": ("разрешение", "максимальное разрешение", "resolution"),
    "screen_size": ("диагональ", "размер экрана", "screen size"),
    "brightness": ("яркость", "brightness", "светимость"),
    "height_adjustment": ("регулировка по высоте", "height adjustment"),
    "width": ("ширина",),
    "height": ("высота",),
    "depth": ("глубина",),
    "weight": ("вес",),
    "volume": ("объем", "объём", "полезный объем", "полезный объём"),
    "energy_class": ("класс энергопотребления", "энергопотребления", "энергоэффективности"),
    "cooling_system": ("no frost", "размораживание", "система охлаждения", "охлаждения"),
    "freezer_position": ("морозильная камера", "морозильной камеры", "расположение морозильной камеры", "морозилка"),
    "inverter_compressor": ("инверторный компрессор", "инвертор", "компрессор"),
    "sewing_operations": ("швейные операции", "операций", "операции", "стежк", "sewing operations"),
    "shuttle_type": ("челнок", "shuttle"),
    "buttonhole": ("петл", "buttonhole"),
    "speed_control": ("скорост", "скорость шитья", "регулировка скорости", "pedal"),
    "work_area_light": ("подсвет", "light", "illumination", "led"),
    "navigation": ("лидар", "lidar", "навигация"),
    "layout": ("тип", "форм фактор", "конструкция"),
    "dryer": ("сушка",),
    "wet_cleaning": ("влажная уборка",),
    "mapping": ("карта", "построение карты"),
    "gpu": ("видеокарта", "дискретная видеокарта", "gpu", "rtx", "geforce"),
    "screen_finish": ("покрытие экрана", "матовое покрытие", "антибликовое покрытие", "screen finish"),
    "power": ("мощность", "ватт", "w", "power"),
    "removable_panels": ("съемные панели", "съёмные панели", "панели", "removable panels"),
    "nonstick_coating": ("антипригарное покрытие", "nonstick", "non stick"),
    "temperature_control": ("регулировка температуры", "temperature control"),
    "grease_tray": ("поддон для жира", "tray for grease", "drip tray"),
    "opens_180": ("раскрытие на 180 градусов", "раскрывается на 180", "opens 180"),
    "smartphone_control": ("управление со смартфона", "управление со смартфоном", "app control", "смартфон"),
    "battery_capacity": ("аккумулятор", "емкость аккумулятора", "ёмкость аккумулятора", "battery capacity", "mah"),
    "auto_return_to_base": ("автоматическое возвращение на базу", "return to base", "автовозврат"),
    "dustbin_easy_cleaning": ("простая очистка контейнера", "очистка контейнера", "easy cleaning"),
    "good_navigation": ("хорошая навигация", "навигация", "navigation"),
    "device_type": ("мфу", "принтер", "device type"),
    "print_technology": ("лазерная печать", "laser", "печать"),
    "color_mode": ("черно-белая печать", "монохромная печать", "monochrome"),
    "wifi": ("wi-fi", "wifi", "wlan"),
    "duplex_print": ("двусторонняя печать", "duplex", "двусторонний"),
    "scanner": ("сканер", "scan"),
    "print_speed": ("скорость печати", "стр/мин", "ppm"),
    "refill_easy": ("простая заправка", "easy refill", "refill"),
    "cheap_maintenance": ("недорогое обслуживание", "cheap maintenance"),
    "resistance_system": ("система нагрузки", "магнитная система", "resistance system"),
    "max_user_weight": ("вес пользователя", "максимальный вес пользователя", "user weight"),
    "seat_adjustment": ("регулировка сиденья", "seat adjustment"),
    "display": ("дисплей", "display", "console"),
    "pulse_measurement": ("измерение пульса", "heart rate", "pulse"),
    "resistance_levels": ("уровни нагрузки", "уровень нагрузки", "levels"),
    "stable_construction": ("устойчивая конструкция", "stability", "stable"),
    "machine_type": ("автоматическая кофемашина", "кофемашина", "machine type"),
    "cappuccinator": ("капучинатор", "cappuccino"),
    "pressure": ("давление", "bar", "bars"),
    "built_in_grinder": ("встроенная кофемолка", "grinder", "кофемолка"),
    "strength_adjustment": ("регулировка крепости", "strength", "strength adjustment"),
    "portion_volume_adjustment": ("регулировка объема порции", "portion volume", "cup size"),
    "self_cleaning": ("самоочистка", "self cleaning"),
    "easy_maintenance": ("простое обслуживание", "maintenance", "easy maintenance"),
    "reliable": ("надежная сборка", "reliable", "reliability"),
    "keyboard_type": ("тип клавиатуры", "клавиатура", "переключатели", "switch"),
    "keyboard_format": ("формат клавиатуры", "форм фактор", "layout", "75%", "80%"),
}
CONSTRAINT_UNITS: dict[str, tuple[str, ...]] = {
    "refresh_rate": ("hz", "гц"),
    "storage": ("gb", "гб", "tb", "тб"),
    "ram": ("gb", "гб"),
    "screen_size": ("inch", "дюйм"),
    "brightness": ("nit", "nits", "нит", "кд/м²", "кд/м2", "cd/m2", "cd/m²"),
    "weight": ("kg", "кг", "g", "г"),
    "width": ("cm", "см", "mm", "мм"),
    "height": ("cm", "см", "mm", "мм"),
    "depth": ("cm", "см", "mm", "мм"),
    "volume": ("l", "л"),
    "year": ("year", "год"),
    "power": ("w", "ватт", "вт"),
    "battery_capacity": ("mah", "мач"),
    "print_speed": ("ppm", "стр/мин"),
    "pressure": ("bar",),
    "resistance_levels": ("levels", "уровн"),
    "max_user_weight": ("kg", "кг"),
}
ENUM_EQUIVALENTS: dict[str, dict[str, tuple[str, ...]]] = {
    "matrix_type": {
        "amoled": ("amoled", "super amoled", "dynamic amoled", "amoled/oled", "oled/amoled", "amoled 2x"),
        "oled": ("oled",),
        "ips": ("ips",),
        "va": ("va", "va матрица"),
        "qled": ("qled",),
    },
    "buttonhole": {
        "automatic": ("автомат", "автоматическое", "автоматическая", "automatic"),
        "semi_automatic": ("полуавтомат", "полуавтоматическая", "semi automatic", "semi_automatic"),
        "none": ("нет",),
    },
    "shuttle_type": {
        "horizontal": ("горизонтальный", "horizontal"),
        "vertical_rotary": ("вертикальный вращающийся", "rotary"),
        "vertical_oscillating": ("вертикальный качающийся", "oscillating"),
    },
    "network": {"5g": ("5g",)},
    "protection": {
        "ip67": ("ip67",),
        "ip68": ("ip68", "ip69", "ip68/ip69"),
    },
    "screen_finish": {
        "matte": ("матовое", "антибликовое", "matte", "anti glare", "anti-glare"),
    },
    "cooling_system": {
        "no_frost": ("no frost", "full no frost", "total no frost"),
    },
    "navigation": {
        "lidar": ("lidar", "лидар"),
    },
    "layout": {
        "side_by_side": ("side by side", "side-by-side"),
    },
    "navigation_type": {
        "lidar": ("lidar", "лидар"),
    },
    "resistance_system": {
        "magnetic": ("magnetic", "магнит", "магнитная"),
    },
    "color_mode": {
        "monochrome": ("monochrome", "черно-бел", "ч/б"),
    },
    "print_technology": {
        "laser": ("laser", "лазер"),
    },
    "machine_type": {
        "automatic": ("automatic", "автомат"),
    },
    "keyboard_type": {
        "magnetic": ("магнитная", "магнит", "magnetic", "hall effect", "he"),
    },
    "keyboard_format": {
        "75_80": ("75%", "tkl", "80%"),
    },
}
BOOLEAN_CONSTRAINT_KEYS = {"nfc", "fast_charge", "wireless_charge", "height_adjustment", "dryer", "wet_cleaning", "mapping", "inverter_compressor", "speed_control", "work_area_light", "removable_panels", "nonstick_coating", "temperature_control", "grease_tray", "opens_180", "smartphone_control", "auto_return_to_base", "wifi", "duplex_print", "scanner", "seat_adjustment", "display", "pulse_measurement", "cappuccinator", "built_in_grinder", "strength_adjustment", "portion_volume_adjustment", "self_cleaning"}
NUMERIC_CONSTRAINT_KEYS = {"ram", "storage", "refresh_rate", "year", "width", "height", "depth", "weight", "volume", "screen_size", "brightness", "sewing_operations", "power", "battery_capacity", "print_speed", "pressure", "resistance_levels", "max_user_weight"}
MODEL_FILTER_TOKENS = ("модель", "model")
BOOLEAN_FILTER_NAME_ALLOWLISTS: dict[str, tuple[str, ...]] = {
    "wifi": ("wi-fi", "wifi", "wlan", "беспровод"),
    "scanner": ("сканер", "scan"),
    "built_in_grinder": ("кофемолк", "grinder", "кофе_молк"),
    "cappuccinator": ("капучин",),
    "wet_cleaning": ("влажн", "моющ", "wash"),
    "auto_return_to_base": ("баз", "return", "возврат"),
    "dustbin_easy_cleaning": ("контейнер", "пылесборн", "dustbin"),
    "smartphone_control": ("смартфон", "app", "mobile"),
    "removable_panels": ("съёмн", "съемн", "removable"),
    "nonstick_coating": ("антипригар", "nonstick", "non_stick"),
    "temperature_control": ("температур", "temp"),
    "grease_tray": ("жир", "tray", "drip"),
    "opens_180": ("180", "180_град", "open"),
    "inverter_compressor": ("компрессор", "inverter"),
    "speed_control": ("скорост", "speed"),
    "work_area_light": ("подсвет", "light", "illumination"),
    "height_adjustment": ("регулиров", "высот", "height"),
    "seat_adjustment": ("сиден", "seat"),
    "display": ("диспле", "display", "console"),
    "pulse_measurement": ("пульс", "heart", "pulse"),
    "resistance_system": ("нагруз", "resistance", "system"),
    "stable_construction": ("конструкц", "stable", "stabil"),
    "pressure": ("давлен", "pressure", "bar"),
    "strength_adjustment": ("крепост", "strength", "grind"),
    "portion_volume_adjustment": ("порц", "volume", "cup"),
    "self_cleaning": ("самоочист", "self"),
    "waterproof_ip68": ("ip68",),
    "waterproof_ip67": ("ip67",),
    "mapping": ("карт", "map"),
    "good_navigation": ("навигац", "navigation"),
}
BOOLEAN_FILTER_NAME_DENYLISTS: dict[str, tuple[str, ...]] = {
    "wifi": ("отображ", "индикатор", "таймер"),
    "scanner": ("автоподач", "adf", "автоподат"),
    "built_in_grinder": ("регулировк", "помол"),
    "cappuccinator": ("энергосбереж", "режим"),
    "wet_cleaning": ("фильтр",),
    "auto_return_to_base": ("таймер",),
    "dustbin_easy_cleaning": ("таймер",),
    "smartphone_control": ("индикатор",),
    "removable_panels": ("комбинирован",),
    "nonstick_coating": ("таймер",),
    "temperature_control": ("таймер",),
    "grease_tray": ("таймер",),
    "opens_180": ("таймер",),
    "inverter_compressor": ("таймер",),
    "speed_control": ("таймер",),
    "work_area_light": ("энергосбереж", "таймер"),
    "seat_adjustment": ("таймер",),
    "display": ("таймер",),
    "pulse_measurement": ("таймер",),
    "resistance_system": ("таймер",),
    "stable_construction": ("таймер",),
    "pressure": ("таймер",),
    "strength_adjustment": ("таймер",),
    "portion_volume_adjustment": ("таймер",),
    "self_cleaning": ("таймер",),
}
NO_MATCH_RELAX_LABELS = {
    "refresh_rate": "частоту экрана",
    "storage": "объём памяти",
    "ram": "объём ОЗУ",
    "matrix_type": "тип экрана",
    "network": "5G",
    "nfc": "NFC",
    "sewing_operations": "количество швейных операций",
    "shuttle_type": "тип челнока",
    "buttonhole": "выполнение петли",
    "speed_control": "регулировку скорости шитья",
    "work_area_light": "подсветку рабочей зоны",
    "protection": "степень защиты",
    "fast_charge": "быструю зарядку",
    "wireless_charge": "беспроводную зарядку",
    "year": "год релиза",
    "width": "ширину",
    "height": "высоту",
    "depth": "глубину",
    "weight": "вес",
    "volume": "объём",
    "energy_class": "класс энергопотребления",
    "cooling_system": "систему охлаждения",
    "freezer_position": "расположение морозильной камеры",
    "inverter_compressor": "инверторный компрессор",
    "layout": "тип конструкции",
    "dryer": "сушку",
    "wet_cleaning": "влажную уборку",
    "mapping": "построение карты",
    "gpu": "видеокарту",
    "screen_finish": "покрытие экрана",
    "power": "мощность",
    "removable_panels": "съёмные панели",
    "nonstick_coating": "антипригарное покрытие",
    "temperature_control": "регулировку температуры",
    "grease_tray": "поддон для жира",
    "opens_180": "раскрытие на 180 градусов",
    "smartphone_control": "управление со смартфона",
    "battery_capacity": "ёмкость аккумулятора",
    "auto_return_to_base": "автовозврат на базу",
    "dustbin_easy_cleaning": "очистку контейнера",
    "good_navigation": "навигацию",
    "device_type": "тип устройства",
    "print_technology": "технологию печати",
    "color_mode": "режим печати",
    "wifi": "Wi-Fi",
    "duplex_print": "двустороннюю печать",
    "scanner": "сканер",
    "print_speed": "скорость печати",
    "refill_easy": "простую заправку",
    "cheap_maintenance": "недорогое обслуживание",
    "resistance_system": "систему нагрузки",
    "max_user_weight": "максимальный вес пользователя",
    "seat_adjustment": "регулировку сиденья",
    "display": "дисплей",
    "pulse_measurement": "измерение пульса",
    "resistance_levels": "уровни нагрузки",
    "stable_construction": "устойчивую конструкцию",
    "machine_type": "тип кофемашины",
    "cappuccinator": "капучинатор",
    "pressure": "давление",
    "built_in_grinder": "встроенную кофемолку",
    "strength_adjustment": "регулировку крепости",
    "portion_volume_adjustment": "регулировку объема порции",
    "self_cleaning": "самоочистку",
    "easy_maintenance": "простое обслуживание",
    "reliable": "надёжную сборку",
}
FULL_MATCH_CLAIM_RE = re.compile(
    r"(полност\w*\s+соответств|полное\s+соответств|все\s+требован\w*\s+выполн|выполняет\s+все\s+требован|единственн\w+\s+товар\w*[^.\n]{0,80}полност)",
    re.IGNORECASE,
)


def extract_dns_url(text: str) -> str:
    for raw_part in text.split():
        candidate = raw_part.strip(".,;()[]{}<>\"'")
        parsed = urlparse(candidate)
        if parsed.scheme in {"http", "https"} and parsed.netloc.endswith("dns-shop.ru"):
            return candidate
    return ""


class ProductDetailsSource(str):
    def __new__(cls, url: str, code: str) -> "ProductDetailsSource":
        instance = str.__new__(cls, url)
        instance.code = code  # type: ignore[attr-defined]
        return instance


class ProductAnalysisOrchestrator:
    def __init__(
        self,
        parser: Callable[[str, int | None], tuple[list[Product], str, str, str]] | None = None,
        stream_chat: Callable[[list[dict[str, str]]], AsyncIterator[str]] | None = None,
        chat: Callable[[list[dict[str, str]]], Awaitable[str]] | None = None,
        normalize_stream_chat: Callable[[list[dict[str, str]]], AsyncIterator[str]] | None = None,
        normalize_chat: Callable[[list[dict[str, str]]], Awaitable[str]] | None = None,
        characteristics_fetcher: Callable[[list[str]], list[dict[str, object]]] | None = None,
        section_filters_inspector: Callable[[str], dict[str, object]] | None = None,
        section_url_resolver: Callable[[str], str] | None = None,
        report_dir: Path | str | None = None,
        product_limit: int | None = DEFAULT_PRODUCT_LIMIT,
    ) -> None:
        self._default_client = None if stream_chat or chat else DeepSeekClient.from_env()
        self._router_client = None
        self._normalize_client = None
        self.parser = parser or self.default_parser
        self.stream_chat = stream_chat or (self._default_client.stream_chat if self._default_client is not None else self._stream_chat_via_chat)
        self.chat = chat or (self._default_client.chat if self._default_client is not None else None)
        self.normalize_stream_chat = normalize_stream_chat
        self.normalize_chat = normalize_chat
        self.characteristics_fetcher = characteristics_fetcher or self.default_characteristics_fetcher
        self.section_filters_inspector = section_filters_inspector or inspect_dns_section_filters
        self.section_url_resolver = section_url_resolver or self.default_section_url_resolver
        self.product_limit = product_limit
        self.analog_search_timeout_seconds = DEFAULT_ANALOG_SEARCH_TIMEOUT_SECONDS
        self._validated_static_category_ids: set[str] = set()
        self._last_shortlist_decision: dict[str, object] = {}
        self._last_filter_trace: dict[str, object] = {}

    async def _stream_chat_via_chat(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        if self.chat is None:
            return
        answer = await self.chat(messages)
        if answer:
            yield answer

    def prime_static_category_fast_path(self, product_types: tuple[str, ...] = STATIC_CATEGORY_STARTUP_PRODUCT_TYPES) -> None:
        for product_type in product_types:
            self.ensure_static_category_fast_path(normalize_token(product_type))

    def ensure_static_category_fast_path(self, product_type: str) -> bool:
        normalized_type = normalize_token(product_type)
        if normalized_type in self._validated_static_category_ids:
            return True
        category_id = STATIC_CATEGORY_ID_BY_PRODUCT_TYPE.get(normalized_type, "")
        query = PRODUCT_TYPE_QUERY_MAP.get(normalized_type, "")
        if not category_id or not query:
            return False
        section_url = normalize_dns_url(query, category=category_id)
        try:
            filters_map = self.section_filters_inspector(section_url)
        except Exception as exc:
            logger.warning("static_category_validation_failed product_type=%s error=%s", normalized_type, exc)
            return False
        filters = filters_map.get("filters", []) if isinstance(filters_map, dict) else []
        if isinstance(filters, list) and filters:
            self._validated_static_category_ids.add(normalized_type)
            return True
        return False

    def build_static_category_section_url(self, request: NormalizedSearchRequest) -> str:
        product_type = normalize_token(request.product_type)
        if product_type in STATIC_CATEGORY_STARTUP_PRODUCT_TYPES:
            if product_type not in self._validated_static_category_ids:
                return ""
        elif not self.ensure_static_category_fast_path(product_type):
            return ""
        category_id = STATIC_CATEGORY_ID_BY_PRODUCT_TYPE.get(product_type, "")
        return normalize_dns_url(
            request.query,
            category=category_id,
            price=normalize_price_pair(request.price_min, request.price_max),
        )

    async def _handle_general_chat_route(
        self,
        text: str,
        history: list[dict[str, str]],
        memory_context: dict[str, object] | None,
    ) -> BotAnalysisResult:
        answer = await self.collect_complete_answer(build_general_chat_messages(text, history))
        answer = await self.apply_chat_teacher_pack(text, answer, mode="general_chat")
        return BotAnalysisResult(
            answer.strip() or "Не удалось сформировать ответ.",
            [],
            0,
            str((memory_context or {}).get("resolved_url", "")),
            preserve_context_payload(memory_context),
        )

    def _build_followup_state(
        self,
        text: str,
        memory_context: dict[str, object] | None,
    ) -> tuple[list[Product], str, str, dict[str, object], dict[str, object], NormalizedSearchRequest]:
        context = memory_context or {}
        enriched = products_from_context(context)
        resolved_url = str(context.get("resolved_url", ""))
        section_url = str(context.get("section_url", ""))
        stats = dict(context.get("stats", {}) or {})
        normalized_request = build_normalized_search_request_from_fallback(text)
        logger.info("memory_context_reused products=%s resolved_url=%s", len(enriched), trim_log_value(resolved_url))
        return enriched, resolved_url, section_url, {"filters": []}, stats, normalized_request

    async def _handle_followup_direct_route(
        self,
        text: str,
        history: list[dict[str, str]],
        enriched: list[Product],
        resolved_url: str,
        stats: dict[str, object],
        memory_context: dict[str, object] | None,
    ) -> BotAnalysisResult:
        answer = await self.collect_complete_answer(
            build_followup_direct_messages(text, history, enriched, resolved_url, stats),
        )
        answer = await self.apply_chat_teacher_pack(text, answer, mode="followup_direct")
        return BotAnalysisResult(
            answer.strip() or "Недостаточно данных для ответа.",
            [],
            len(enriched),
            resolved_url,
            preserve_context_payload(memory_context),
        )

    async def _resolve_text_query_request(
        self,
        text: str,
        local_request_hint: NormalizedSearchRequest,
        requested_url_hint: str,
        stage_callback: Callable[[str], None],
    ) -> tuple[NormalizedSearchRequest, str]:
        static_section_url = self.build_static_category_section_url(local_request_hint)
        if static_section_url:
            normalized_request = await self.normalize_search_request(text)
            section_url = static_section_url
            log_ai_chain_step(AI_CHAIN_CATEGORY_FILTERS, section_url=section_url, source="category_static")
        else:
            normalized_request, section_url = await asyncio.gather(
                self.normalize_search_request(text),
                self.resolve_section_url(requested_url_hint, stage_callback),
            )
        search_query = choose_dns_search_query(normalized_request.query, local_request_hint.query)
        if search_query != normalized_request.query:
            normalized_request = replace(normalized_request, query=search_query)
        normalized_static_section_url = self.build_static_category_section_url(normalized_request)
        if normalized_static_section_url:
            section_url = normalized_static_section_url
        log_ai_chain_step(
            AI_CHAIN_REQUEST,
            source="text_query",
            input=text,
            normalized=normalized_request.query,
            price_min=normalized_request.price_min,
            price_max=normalized_request.price_max,
            brand=normalized_request.brand,
            wishes=",".join(normalized_request.wishes),
            soft_wishes=",".join(normalized_request.soft_wishes),
        )
        requested_url = normalize_dns_url(
            normalized_request.query,
            price=normalize_price_pair(normalized_request.price_min, normalized_request.price_max),
        )
        if normalized_request.query != local_request_hint.query and not normalized_static_section_url:
            section_url = await self.resolve_section_url(requested_url, stage_callback)
        return normalized_request, section_url

    async def _select_query_filters(
        self,
        text: str,
        history: list[dict[str, str]],
        section_url: str,
        normalized_request: NormalizedSearchRequest,
        stage_callback: Callable[[str], None],
    ) -> tuple[dict[str, object], str, list[dict[str, object]]]:
        filters_map = await self.load_section_filters(section_url, stage_callback)
        candidate_packets = build_constraint_candidate_packets(normalized_request, filters_map)
        preselected_filters, coverage = build_preselected_filters_and_coverage(normalized_request, filters_map)
        if not coverage_requires_patch(coverage):
            selected_filters = []
            logger.info("filters_ai_skipped reason=preselected_hard_wishes_covered")
            log_ai_chain_step(
                AI_CHAIN_FILTERS_AI,
                section_url=section_url,
                available_filters=len(filters_map.get("filters", [])),
                skipped="preselected_hard_wishes_covered",
            )
            stage_callback("filters_ai_skipped")
        else:
            selected_filters = await self.select_search_filters(
                text,
                history,
                section_url,
                normalized_request,
                preselected_filters,
                coverage,
                candidate_packets,
                stage_callback,
            )
        selected_filters = merge_selected_filters(preselected_filters, selected_filters)
        selected_filters = sanitize_selected_filters(selected_filters, normalized_request, preselected_filters)
        selected_filters = ensure_request_price_filter(selected_filters, normalized_request)
        try:
            stage_callback("create_link_start")
            query_input = build_dns_url_from_section_filters(
                section_url,
                selected_filters,
                filters_map.get("filters", []) if isinstance(filters_map.get("filters"), list) else [],
            )
        except DnsFilterSelectionError as exc:
            logger.error("built_url_failed details=%s", trim_log_value(json.dumps(exc.details, ensure_ascii=False)))
            raise ValueError("Не удалось собрать DNS URL: AI выбрал неизвестные фильтры или значения.") from exc
        logger.info("built_url_done url=%s", trim_log_value(query_input))
        log_ai_chain_step(AI_CHAIN_BUILT_URL, section_url=section_url, url=query_input)
        stage_callback("built_url_done")
        self._last_filter_trace = {
            "filters_map_count": len(filters_map.get("filters", [])) if isinstance(filters_map.get("filters"), list) else 0,
            "candidate_packets": candidate_packets,
            "preselected_filters": preselected_filters,
            "coverage": coverage,
            "selected_filters": selected_filters,
            "built_url": query_input,
        }
        return filters_map, query_input, coverage

    async def _prepare_search_request(
        self,
        text: str,
        history: list[dict[str, str]],
        url: str,
        stage_callback: Callable[[str], None],
    ) -> tuple[NormalizedSearchRequest, str, dict[str, object], str, list[dict[str, object]]]:
        if url:
            query_input = normalize_dns_url(url)
            log_ai_chain_step(AI_CHAIN_REQUEST, source="dns_url", input=text, normalized=query_input)
            section_url = await self.resolve_section_url(query_input, stage_callback)
            return build_normalized_search_request_from_fallback(text), section_url, {}, query_input, []
        local_request_hint = build_normalized_search_request_from_fallback(text)
        stage_callback("bot1_category_brand")
        stage_callback("bot2_price")
        stage_callback("bot4_wishes")
        stage_callback("wait_bot3_notimeout")
        stage_callback("json_build_start")
        requested_url_hint = normalize_dns_url(
            local_request_hint.query,
            price=normalize_price_pair(local_request_hint.price_min, local_request_hint.price_max),
        )
        normalized_request, section_url = await self._resolve_text_query_request(
            text,
            local_request_hint,
            requested_url_hint,
            stage_callback,
        )
        filters_map, query_input, coverage = await self._select_query_filters(
            text,
            history,
            section_url,
            normalized_request,
            stage_callback,
        )
        return normalized_request, section_url, filters_map, query_input, coverage

    async def _run_catalog_pipeline(
        self,
        text: str,
        history: list[dict[str, str]],
        normalized_request: NormalizedSearchRequest,
        query_input: str,
        section_url: str,
        url: str,
        coverage: list[dict[str, object]],
        stage_callback: Callable[[str], None],
    ) -> tuple[list[Product], str, dict[str, object]]:
        stage_callback("parser_start")
        logger.info("parser_start input=%s", trim_log_value(query_input))
        products, _mode, _requested_url, resolved_url = await asyncio.to_thread(
            self.parser,
            query_input,
            self.product_limit,
        )
        if not products and not url:
            stage_callback("relax_start")
            analog_request = build_normalized_search_request_from_fallback(text)
            analog_query_input = normalize_dns_url(
                analog_request.query,
                category=classify_query_params(section_url)["known"].get("category", ""),
                price=normalize_price_pair(analog_request.price_min, analog_request.price_max),
            )
            if analog_query_input != query_input:
                logger.info(
                    "analog_search_start exact_query=%s analog_query=%s",
                    trim_log_value(query_input),
                    trim_log_value(analog_query_input),
                )
                stage_callback("analog_search_start")
                stage_callback("relax_retry")
                try:
                    products, _mode, _requested_url, resolved_url = await asyncio.wait_for(
                        asyncio.to_thread(
                            self.parser,
                            analog_query_input,
                            self.product_limit,
                        ),
                        timeout=self.analog_search_timeout_seconds,
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        "analog_search_timeout exact_query=%s analog_query=%s timeout_s=%s",
                        trim_log_value(query_input),
                        trim_log_value(analog_query_input),
                        self.analog_search_timeout_seconds,
                    )
                    stage_callback("analog_search_timeout")
                    stage_callback("relax_limit")
                    products = []
                logger.info("analog_search_done total_products=%s resolved_url=%s", len(products), trim_log_value(resolved_url))
                stage_callback("analog_search_done")
            if not products:
                stage_callback("relax_limit")
        logger.info("parser_done total_products=%s resolved_url=%s", len(products), trim_log_value(resolved_url))
        log_ai_chain_step(AI_CHAIN_LIST, products=len(products), resolved_url=resolved_url)
        stage_callback("parser_done")
        query = classify_query_params(resolved_url)["known"].get("q", query_input)
        processed, stats = postprocess_products(products, query=query)
        stage_callback("shortlist_start")
        logger.info("shortlist_start candidates=%s", len(processed))
        shortlisted = await self.shortlist_products(text, history, processed, resolved_url, normalized_request)
        stage_callback("shortlist_done")
        stats = dict(stats)
        unresolved_signals = self._last_shortlist_decision.get("unresolved_signals", [])
        if isinstance(unresolved_signals, list) and unresolved_signals:
            stats["unresolved_signals"] = [str(item) for item in unresolved_signals if str(item).strip()]
        shortlist_no_match = bool(self._last_shortlist_decision.get("no_match"))
        if shortlist_no_match:
            reason = str(self._last_shortlist_decision.get("reason", "")).strip()
            stats["no_match"] = 1
            stats["no_match_reason"] = reason
            logger.info("shortlist_no_match reason=%s", trim_log_value(reason))
            return [], resolved_url, stats
        stage_callback("bot3_characteristics")
        stage_callback("details_start")
        enriched = await asyncio.to_thread(self.attach_characteristics, processed, shortlisted)
        logger.info("details_done products=%s with_specs=%s", len(enriched), count_products_with_specs(enriched))
        stage_callback("details_done")
        return enriched, resolved_url, stats

    async def _build_product_result(
        self,
        text: str,
        history: list[dict[str, str]],
        enriched: list[Product],
        resolved_url: str,
        stats: dict[str, object],
        normalized_request: NormalizedSearchRequest,
        section_url: str,
        filters_map: dict[str, object],
        coverage: list[dict[str, object]],
        on_text_chunk: Callable[[str], None],
        stage_callback: Callable[[str], None],
    ) -> BotAnalysisResult:
        if not enriched:
            answer = build_no_products_analysis_answer(normalized_request, resolved_url)
            log_ai_chain_step(AI_CHAIN_OUTPUT, images=0, products=0)
            stage_callback("analysis_done")
            stage_callback("render_done")
            return BotAnalysisResult(
                answer,
                [],
                0,
                resolved_url,
                build_context_payload(
                    [],
                    resolved_url,
                    stats,
                    section_url=section_url,
                    filters_map_summary=build_filters_map_summary(filters_map) if filters_map else {},
                    filters_llm=build_filters_llm(filters_map) if filters_map else {},
                    filter_trace=self._last_filter_trace,
                    normalized_request=normalized_request,
                    comparison_summary={"coverage": coverage},
                ),
            )
        comparison_summary = build_comparison_summary(enriched, normalized_request, coverage=coverage)
        messages = build_analysis_messages(text, history, enriched, resolved_url, stats, normalized_request, comparison_summary)
        stage_callback("analysis_start")
        logger.info("analysis_start products=%s", len(enriched))
        log_ai_chain_step(AI_CHAIN_FINAL_AI, products=len(enriched), resolved_url=resolved_url)
        answer_stream_callback = None if comparison_summary_requires_teacher_guard(comparison_summary) else on_text_chunk
        answer = await self.collect_text_answer(messages, answer_stream_callback)
        logger.info("analysis_done chars=%s", len(answer))
        stage_callback("analysis_done")
        log_ai_chain_step(AI_CHAIN_OUTPUT, images=0, products=len(enriched))
        stage_callback("compare_link_start")
        stage_callback("render_done")
        final_answer = ensure_teacher_checked_analysis_answer(answer.strip(), enriched, comparison_summary)
        return BotAnalysisResult(
            final_answer,
            [],
            len(enriched),
            resolved_url,
            build_context_payload(
                enriched,
                resolved_url,
                stats,
                section_url=section_url,
                filters_map_summary=build_filters_map_summary(filters_map) if filters_map else {},
                filters_llm=build_filters_llm(filters_map) if filters_map else {},
                filter_trace=self._last_filter_trace,
                normalized_request=normalized_request,
                comparison_summary=comparison_summary,
            ),
        )

    async def handle_message(
        self,
        text: str,
        history: list[dict[str, str]],
        on_text_chunk: Callable[[str], None],
        on_stage: Callable[[str], None] | None = None,
        memory_context: dict[str, object] | None = None,
    ) -> BotAnalysisResult:
        stage_callback = on_stage or (lambda _stage: None)
        stage_callback("remember_mode")
        stage_callback("find_x")
        stage_callback("cycle_code_1_start")
        url = extract_dns_url(text)
        route = await self.route_message_intent(text, history, memory_context, url)
        logger.info("intent_route mode=%s style=%s reason=%s", route.mode, route.response_style, trim_log_value(route.reason))
        coverage: list[dict[str, object]] = []
        if route.mode == "general_chat":
            return await self._handle_general_chat_route(text, history, memory_context)
        if route.mode == "product_followup":
            enriched, resolved_url, section_url, filters_map, stats, normalized_request = self._build_followup_state(text, memory_context)
            if route.response_style == "direct":
                return await self._handle_followup_direct_route(
                    text,
                    history,
                    enriched,
                    resolved_url,
                    stats,
                    memory_context,
                )
        else:
            normalized_request, section_url, filters_map, query_input, coverage = await self._prepare_search_request(
                text,
                history,
                url,
                stage_callback,
            )
            enriched, resolved_url, stats = await self._run_catalog_pipeline(
                text,
                history,
                normalized_request,
                query_input,
                section_url,
                url,
                coverage,
                stage_callback,
            )
            if not enriched and stats.get("no_match") == 1:
                reason = str(stats.get("no_match_reason", "")).strip()
                if normalized_request.brand:
                    answer = "Товаров по заданному бренду и условиям не найдено. Попробуйте расширить поиск или убрать один из фильтров."
                else:
                    answer = "Товаров по заданным фильтрам не найдено. Попробуйте расширить поиск или убрать один из фильтров."
                if reason:
                    answer = f"{answer}\nПричина: {reason}"
                return BotAnalysisResult(
                    answer=answer,
                    image_paths=[],
                    products_count=0,
                    resolved_url=resolved_url,
                    context_payload=build_context_payload(
                        [],
                        resolved_url,
                        stats,
                        section_url=section_url,
                        filters_map_summary=build_filters_map_summary(filters_map) if filters_map else {},
                        filters_llm=build_filters_llm(filters_map) if filters_map else {},
                        normalized_request=normalized_request,
                        comparison_summary={"coverage": coverage},
                    ),
                )
        return await self._build_product_result(
            text,
            history,
            enriched,
            resolved_url,
            stats,
            normalized_request,
            section_url,
            filters_map,
            coverage,
            on_text_chunk,
            stage_callback,
        )

    @staticmethod
    def default_parser(input_value: str, limit: int | None) -> tuple[list[Product], str, str, str]:
        return collect_products_by_url(input_value=input_value, limit=limit, allow_browser=True)

    @staticmethod
    def default_characteristics_fetcher(sources: list[object]) -> list[dict[str, object]]:
        return fetch_compare_characteristics_for_products(sources, allow_browser=True, city_id=COMPARE_CITY_ID)

    @staticmethod
    def default_section_url_resolver(requested_url: str) -> str:
        resolution_url = build_category_resolution_url(requested_url)
        cookies = prewarm_dns_cookies(reason="category_resolve")
        resolved_section_url = resolve_category_if_missing(
            resolution_url,
            browser_resolver=browser_resolve_url,
            http_resolver=lambda value: http_resolve_url(value, cookies=cookies),
        )
        resolved_category = classify_query_params(resolved_section_url)["known"].get("category", "")
        requested_query = normalize_token(classify_query_params(requested_url)["known"].get("q", ""))
        if not resolved_category and "велотренажер" in requested_query:
            fallback_url = normalize_dns_url("тренажер")
            fallback_resolution_url = build_category_resolution_url(fallback_url)
            resolved_section_url = resolve_category_if_missing(
                fallback_resolution_url,
                browser_resolver=browser_resolve_url,
                http_resolver=lambda value: http_resolve_url(value, cookies=cookies),
            )
            resolved_category = classify_query_params(resolved_section_url)["known"].get("category", "")
        return normalize_dns_url(requested_url, category=resolved_category) if resolved_category else requested_url

    async def normalize_search_request(self, text: str) -> NormalizedSearchRequest:
        messages = build_normalize_query_messages(text)
        selected_chat = self.normalize_chat
        selected_stream = self.normalize_stream_chat
        if selected_chat is None and selected_stream is None and self._default_client is not None:
            self._normalize_client = self._normalize_client or build_normalize_client()
            selected_chat = self._normalize_client.chat
        answer = await self.collect_complete_answer(
            messages,
            chat=selected_chat,
            stream_chat=selected_stream,
        )
        planned = normalized_search_request_from_text(answer, fallback=text)
        logger.info(
            "normalize_query_done source=%s planned=%s price_min=%s price_max=%s brand=%s retrieval_tokens=%s",
            trim_log_value(text),
            trim_log_value(planned.product_type),
            planned.price_min,
            planned.price_max,
            trim_log_value(planned.brand),
            ",".join(request_retrieval_tokens(planned)),
        )
        logger.info("normalize_query_search_url url=%s", trim_log_value(build_normalized_request_search_url(planned)))
        return planned

    async def route_message_intent(
        self,
        text: str,
        history: list[dict[str, str]],
        memory_context: dict[str, object] | None,
        url: str,
    ) -> IntentRoute:
        if url:
            return IntentRoute(mode="product_search", response_style="structured", reason="dns_url")
        if is_obvious_bot_meta_question(text):
            return IntentRoute(mode="general_chat", response_style="direct", reason="local_general_chat")
        if is_format_followup_for_chat(text, history, memory_context):
            return IntentRoute(mode="general_chat", response_style="direct", reason="local_chat_followup")
        if products_from_context(memory_context) and is_obvious_followup_question(text) and not is_obvious_product_search_signal(text):
            return IntentRoute(mode="product_followup", response_style="direct", reason="local_followup")
        if is_obvious_product_search_signal(text):
            return IntentRoute(mode="product_search", response_style="structured", reason="local_search")
        messages = build_router_messages(text, history, memory_context)
        if self._default_client is not None:
            self._router_client = self._router_client or build_router_client()
            raw_answer = await self.collect_complete_answer(messages, chat=self._router_client.chat)
        else:
            raw_answer = await self.collect_text_answer(messages, stream_chat=self.stream_chat)
        if should_retry_router_response(raw_answer):
            logger.error("router_response_noise_detected chars=%s", len(raw_answer))
            if self._default_client is not None:
                raw_answer = await self.collect_complete_answer(messages, chat=self._router_client.chat)
            else:
                raw_answer = await self.collect_text_answer(messages, stream_chat=self.stream_chat)
        return parse_intent_route(raw_answer, has_products=bool(products_from_context(memory_context)))

    async def collect_text_answer(
        self,
        messages: list[dict[str, str]],
        on_text_chunk: Callable[[str], None] | None = None,
        stream_chat: Callable[[list[dict[str, str]]], AsyncIterator[str]] | None = None,
    ) -> str:
        parts: list[str] = []
        selected_stream = stream_chat or self.stream_chat
        async for chunk in selected_stream(messages):
            parts.append(chunk)
            if on_text_chunk is not None:
                on_text_chunk(chunk)
        return "".join(parts)

    async def collect_complete_answer(
        self,
        messages: list[dict[str, str]],
        chat: Callable[[list[dict[str, str]]], Awaitable[str]] | None = None,
        stream_chat: Callable[[list[dict[str, str]]], AsyncIterator[str]] | None = None,
    ) -> str:
        selected_chat = chat or self.chat
        if selected_chat is not None:
            return await selected_chat(messages)
        return await self.collect_text_answer(messages, stream_chat=stream_chat)

    async def apply_chat_teacher_pack(self, question: str, answer: str, mode: str) -> str:
        normalized = enforce_chat_answer_constraints(answer, extract_chat_format_constraints(question))
        teacher_messages = build_chat_teacher_messages(question, normalized, mode)
        revised = await self.collect_complete_answer(teacher_messages)
        revised = enforce_chat_answer_constraints(revised or normalized, extract_chat_format_constraints(question))
        return revised.strip() or normalized.strip() or answer.strip()

    async def resolve_section_url(self, requested_url: str, on_stage: Callable[[str], None]) -> str:
        on_stage("category_resolve_start")
        logger.info("category_resolve_start input=%s", trim_log_value(requested_url))
        resolved_section_url = await asyncio.to_thread(self.section_url_resolver, requested_url)
        logger.info("category_resolve_done section_url=%s", trim_log_value(resolved_section_url))
        log_ai_chain_step(AI_CHAIN_CATEGORY_FILTERS, section_url=resolved_section_url, source="category_resolve")
        on_stage("category_resolve_done")
        return resolved_section_url

    async def load_section_filters(self, section_url: str, on_stage: Callable[[str], None]) -> dict[str, object]:
        on_stage("filters_map_start")
        logger.info("filters_map_start section_url=%s", trim_log_value(section_url))
        filters_map = await asyncio.to_thread(self.section_filters_inspector, section_url)
        logger.info("filters_map_done count=%s", len(filters_map.get("filters", [])))
        log_ai_chain_step(AI_CHAIN_CATEGORY_FILTERS, section_url=section_url, filters=len(filters_map.get("filters", [])), source="filters_map")
        on_stage("filters_map_done")
        return filters_map

    async def select_search_filters(
        self,
        question: str,
        history: list[dict[str, str]],
        section_url: str,
        normalized_request: NormalizedSearchRequest,
        preselected_filters: list[dict[str, object]],
        coverage: list[dict[str, object]],
        candidate_packets: list[dict[str, object]],
        on_stage: Callable[[str], None],
    ) -> list[dict[str, object]]:
        on_stage("filters_ai_start")
        logger.info("filters_ai_start constraints=%s problematic=%s", len(normalized_request.constraints), len(problematic_constraint_packets(candidate_packets, coverage)))
        log_ai_chain_step(AI_CHAIN_FILTERS_AI, section_url=section_url, constraints=len(normalized_request.constraints))
        answer = await self.collect_complete_answer(
            build_filter_selection_messages(question, history, section_url, normalized_request, preselected_filters, coverage, candidate_packets),
            chat=self.chat,
        )
        selected_filters = filter_selection_to_filters(answer)
        logger.info("filters_ai_done selected=%s", len(selected_filters))
        on_stage("filters_ai_done")
        return selected_filters

    async def shortlist_products(
        self,
        question: str,
        history: list[dict[str, str]],
        products: list[Product],
        resolved_url: str,
        normalized_request: NormalizedSearchRequest,
    ) -> list[Product]:
        if not products:
            return []
        ranked_products = rank_products_for_request(products, normalized_request)
        log_ai_chain_step(AI_CHAIN_SHORTLIST_AI, candidates=len(ranked_products), resolved_url=resolved_url)
        messages = build_shortlist_messages(question, history, ranked_products, resolved_url, normalized_request)
        answer = await self.collect_complete_answer(messages, chat=self.chat)
        shortlist_decision = parse_shortlist_decision(answer, ranked_products)
        self._last_shortlist_decision = shortlist_decision
        selected_urls = shortlist_decision["selected_urls"]
        shortlisted = [product for product in ranked_products if product.url in selected_urls][:SHORTLIST_LIMIT]
        no_hard_signals = request_source_signal_count(normalized_request) == 0 and not request_intent_signals(normalized_request)
        if not shortlisted and (not shortlist_decision.get("no_match") or no_hard_signals):
            shortlisted = ranked_products[:SHORTLIST_LIMIT]
            self._last_shortlist_decision = {
                **shortlist_decision,
                "no_match": False,
                "reason": "",
                "selected_urls": [product.url for product in shortlisted],
                "selected_codes": [product.code for product in shortlisted if product.code],
            }
        logger.info("shortlist_done input=%s selected=%s", len(products), len(shortlisted))
        return shortlisted

    def attach_characteristics(self, products: list[Product], selected_products: list[Product]) -> list[Product]:
        if not selected_products:
            return selected_products
        if all(product_has_detailed_specs(product) for product in selected_products[:DETAILS_LIMIT]):
            logger.info("details_reused_from_shortlist products=%s", len(selected_products[:DETAILS_LIMIT]))
            return selected_products[:DETAILS_LIMIT]
        sources = [
            ProductDetailsSource(product.url, product.code)
            for product in selected_products[:DETAILS_LIMIT]
            if product.code
        ]
        logger.info("details_start urls=%s", len(sources))
        log_ai_chain_step(AI_CHAIN_DETAILS, urls=len(sources))
        items = self.characteristics_fetcher(sources)
        specs_by_url = {
            str(item.get("url", "")): item.get("specs", [])
            for item in items
            if isinstance(item, dict)
        }
        enriched: list[Product] = []
        for product in selected_products:
            specs = specs_by_url.get(product.url, product.specs or None)
            enriched.append(
                Product(
                    name=product.name,
                    price=product.price,
                    url=product.url,
                    code=product.code,
                    specs=specs,
                )
            )
        return enriched

    async def aclose(self) -> None:
        if self._default_client is not None:
            await self._default_client.aclose()
        if self._router_client is not None:
            await self._router_client.aclose()
        if self._normalize_client is not None:
            await self._normalize_client.aclose()

def build_analysis_messages(
    question: str,
    history: list[dict[str, str]],
    products: list[Product],
    resolved_url: str,
    stats: dict[str, int],
    normalized_request: NormalizedSearchRequest,
    comparison_summary: dict[str, object] | None = None,
) -> list[dict[str, str]]:
    payload = build_analysis_payload(question, resolved_url, stats, normalized_request, products, comparison_summary)
    messages = [
        {
            "role": "system",
            "content": (
                FINAL_ANALYSIS_SYSTEM_PROMPT
                + " normalized_request.soft_wishes are ranking hints only, not DNS filters. "
                + "Пользовательский payload приходит как JSON во входных данных: секции QUESTION, URL, STATS, REQUEST, PRODUCTS, COMPARISON. "
                + "Ответ не должен повторять этот JSON и всегда должен быть обычным текстом."
            ),
        }
    ]
    messages.extend(turn for turn in history[-8:] if turn.get("role") in {"user", "assistant"})
    messages.append({"role": "user", "content": payload})
    return messages


def build_router_messages(
    text: str,
    history: list[dict[str, str]],
    memory_context: dict[str, object] | None,
) -> list[dict[str, str]]:
    payload = {
        "task": "intent_route",
        "question": text,
        "history": history[-4:],
        "has_memory_context": bool(products_from_context(memory_context)),
        "memory_summary": summarize_context_products(memory_context),
    }
    return [
        {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def build_general_chat_messages(text: str, history: list[dict[str, str]]) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": GENERAL_CHAT_SYSTEM_PROMPT}]
    messages.extend(turn for turn in history[-8:] if turn.get("role") in {"user", "assistant"})
    messages.append({"role": "user", "content": text})
    return messages


def build_followup_direct_messages(
    question: str,
    history: list[dict[str, str]],
    products: list[Product],
    resolved_url: str,
    stats: dict[str, int],
) -> list[dict[str, str]]:
    payload = {
        "question": question,
        "resolved_url": resolved_url,
        "stats": stats,
        "products": [product_payload(product) for product in products],
    }
    messages = [{"role": "system", "content": FOLLOWUP_DIRECT_SYSTEM_PROMPT}]
    messages.extend(turn for turn in history[-8:] if turn.get("role") in {"user", "assistant"})
    messages.append({"role": "user", "content": json.dumps(payload, ensure_ascii=False)})
    return messages


def build_chat_teacher_messages(question: str, draft_answer: str, mode: str) -> list[dict[str, str]]:
    payload = {
        "user_request": question,
        "mode": mode,
        "draft_answer": draft_answer,
    }
    return [
        {"role": "system", "content": CHAT_TEACHER_SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def build_normalize_query_messages(text: str) -> list[dict[str, str]]:
    payload = {"task": "normalize_query", "question": text}
    return [
        {"role": "system", "content": NORMALIZE_QUERY_SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def build_filter_selection_messages(
    question: str,
    history: list[dict[str, str]],
    section_url: str,
    normalized_request: NormalizedSearchRequest,
    preselected_filters: list[dict[str, object]],
    coverage: list[dict[str, object]],
    candidate_packets: list[dict[str, object]],
) -> list[dict[str, str]]:
    payload = build_filters_payload(
        question=question,
        history=history[-4:],
        section_url=section_url,
        normalized_request=normalized_request,
        preselected_filters=preselected_filters,
        coverage=coverage,
        candidate_packets=candidate_packets,
    )
    return [
        {
            "role": "system",
            "content": (
                FILTER_SELECTION_SYSTEM_PROMPT
                + " Soft wishes are ranking hints only and must never be converted into DNS filters. "
                + "Фильтр 'Модель' запрещён для технических свойств без явного model/line запроса. "
                + "Вход приходит в JSON format: секции QUESTION, URL, REQUEST, PRESELECTED, COVERAGE, CANDIDATES."
            ),
        },
        {"role": "user", "content": payload},
    ]


def parse_intent_route(raw_value: str, has_products: bool) -> IntentRoute:
    payload = parse_llm_json_payload(raw_value)
    if payload is None:
        if has_products:
            return IntentRoute(mode="product_followup", response_style="direct", reason="router_fallback_with_context")
        return IntentRoute(mode="product_search", response_style="structured", reason="router_fallback_search")
    mode = str(payload.get("mode", "")).strip()
    response_style = str(payload.get("response_style", "")).strip()
    reason = str(payload.get("reason", "")).strip()
    if mode not in {"general_chat", "product_followup", "product_search"}:
        mode = "product_followup" if has_products else "product_search"
    if response_style not in {"direct", "structured"}:
        response_style = "direct" if mode == "product_followup" else "structured"
    if mode == "product_followup" and not has_products:
        mode = "product_search"
        response_style = "structured"
    return IntentRoute(mode=mode, response_style=response_style, reason=reason)


def build_shortlist_messages(
    question: str,
    history: list[dict[str, str]],
    products: list[Product],
    resolved_url: str,
    normalized_request: NormalizedSearchRequest,
) -> list[dict[str, str]]:
    system = (
        "Ты выбираешь лучшие товары из списка DNS для дальнейшего детального разбора. "
        "Верни только JSON: selected_codes, reasons, no_match, reason, unresolved_signals. "
        "selected_codes должен содержать до 5 DNS code из переданного списка. "
        "Если в запросе нет hard-сигналов, не ставь no_match=true: выбери лучшие товары по общему смыслу и цене/качеству. "
        "Если по обязательному бренду не найдено ни одного товара, верни no_match=true и пустой selected_codes. "
        "Если важный intent_signal нельзя проверить по данным категории, верни его в unresolved_signals. "
        "normalized_request.soft_wishes — это мягкие сигналы для ранжирования, не фильтры. "
        "Вход приходит в JSON format, где товары идут в массиве PRODUCTS."
    )
    if normalized_request.price_max is None and normalized_request.price_min is None:
        system += " Если бюджет не задан, не выбирай только самые дешёвые варианты: покрой бюджетный, средний и флагманский сегменты, если они есть."
    deduplicated_products = deduplicate_products_by_model(products)
    shortlist_candidates = select_shortlist_candidates(deduplicated_products, normalized_request, SHORTLIST_CANDIDATE_LIMIT)
    logger.info(
        "shortlist_payload candidates=%s deduplicated=%s shortlisted=%s",
        min(len(products), SHORTLIST_CANDIDATE_LIMIT),
        len(deduplicated_products),
        len(shortlist_candidates),
    )
    payload = build_shortlist_payload(
        question,
        resolved_url,
        normalized_request,
        shortlist_candidates,
        history[-4:],
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": payload},
    ]


def build_filters_payload(
    question: str,
    history: list[dict[str, str]],
    section_url: str,
    normalized_request: NormalizedSearchRequest,
    preselected_filters: list[dict[str, object]],
    coverage: list[dict[str, object]],
    candidate_packets: list[dict[str, object]],
) -> str:
    problematic_keys = {
        str(item.get("constraint_key", ""))
        for item in coverage
        if isinstance(item, dict) and str(item.get("status", "")) not in {"covered"}
    }
    payload = {
        "task": "filters_patch",
        "question": question,
        "url": section_url,
        "request": normalized_request_payload(normalized_request),
        "history": history,
        "preselected_filters": preselected_filters,
        "coverage": coverage,
        "candidate_packets": [
            packet
            for packet in candidate_packets
            if isinstance(packet, dict)
            and (
                (
                    isinstance(packet.get("intent_signal"), dict)
                    and str(packet["intent_signal"].get("key", "")) in problematic_keys
                )
                or (
                    isinstance(packet.get("constraint"), dict)
                    and str(packet["constraint"].get("key", "")) in problematic_keys
                )
            )
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def build_analysis_payload(
    question: str,
    resolved_url: str,
    stats: dict[str, object],
    normalized_request: NormalizedSearchRequest,
    products: list[Product],
    comparison_summary: dict[str, object] | None = None,
) -> str:
    payload = {
        "task": "analysis",
        "question": question,
        "url": resolved_url,
        "stats": stats,
        "request": normalized_request_payload(normalized_request),
        "products": [analysis_product_payload(product, normalized_request) for product in products[:20]],
    }
    if isinstance(comparison_summary, dict) and comparison_summary:
        payload["comparison"] = comparison_summary
    return json.dumps(payload, ensure_ascii=False)


def build_shortlist_payload(
    question: str,
    resolved_url: str,
    normalized_request: NormalizedSearchRequest,
    products: list[Product],
    history: list[dict[str, str]],
) -> str:
    payload = {
        "task": "shortlist",
        "question": question,
        "url": resolved_url,
        "request": normalized_request_payload(normalized_request),
        "history": history,
        "products": [device_llm_payload(product, normalized_request) for product in products],
    }
    return json.dumps(payload, ensure_ascii=False)


def request_intent_signals(request: NormalizedSearchRequest) -> tuple[NormalizedConstraint, ...]:
    return request.intent_signals or request.constraints or constraints_from_legacy_wishes(request.wishes)


def request_retrieval_tokens(request: NormalizedSearchRequest) -> tuple[str, ...]:
    if request.retrieval_tokens:
        return request.retrieval_tokens
    if request.wishes:
        return request.wishes
    return constraints_to_wishes(request_intent_signals(request))


def request_source_signal_count(request: NormalizedSearchRequest) -> int:
    if request.source_signal_count:
        return request.source_signal_count
    if request.source_hard_wishes_count:
        return request.source_hard_wishes_count
    signals = request_intent_signals(request)
    return len(signals)


def harmonize_normalized_request(request: NormalizedSearchRequest) -> NormalizedSearchRequest:
    intent_signals = request_intent_signals(request)
    retrieval_tokens = request_retrieval_tokens(request)
    source_signal_count = request_source_signal_count(request)
    ranking_policy = normalize_ranking_policy_for_request(request)
    price_band_hint = normalize_price_band_hint_for_request(request)
    return replace(
        request,
        intent_signals=intent_signals,
        retrieval_tokens=retrieval_tokens,
        source_signal_count=source_signal_count,
        constraints=intent_signals,
        wishes=retrieval_tokens,
        source_hard_wishes_count=source_signal_count,
        ranking_policy=ranking_policy,
        price_band_hint=price_band_hint,
    )


def request_has_display_priority(request: NormalizedSearchRequest) -> bool:
    display_constraint_keys = {"screen_size", "brightness", "matrix_type", "resolution", "refresh_rate", "screen_finish"}
    if any(normalize_token(item.key) in display_constraint_keys for item in request.constraints):
        return True
    display_soft_wishes = {"bright_screen", "good_image_quality"}
    return any(canonicalize_wish(item) in display_soft_wishes for item in request.soft_wishes)


def request_has_performance_priority(request: NormalizedSearchRequest) -> bool:
    if any(normalize_token(item.key) in {"gpu", "ram"} for item in request.constraints):
        return True
    return any(canonicalize_wish(item) == "good_performance" for item in request.soft_wishes)


def normalize_ranking_policy_for_request(request: NormalizedSearchRequest) -> str:
    policy = normalize_token(request.ranking_policy)
    if policy == "performance" and request_has_display_priority(request) and not request_has_performance_priority(request):
        return "display"
    return policy


def normalize_price_band_hint_for_request(request: NormalizedSearchRequest) -> str:
    return normalize_token(request.price_band_hint)


def infer_context_constraints_from_text(text: str, product_type: str) -> tuple[NormalizedConstraint, ...]:
    normalized = text.casefold()
    constraints: list[NormalizedConstraint] = []
    if product_type == "laptop" and re.search(r"(сам\w*\s+больш\w*.*экран|больш\w*.*экран|больш\w*\s+диагонал)", normalized, re.IGNORECASE):
        constraints.append(build_constraint("screen_size", ">=", "17", "inch", "большой экран"))
    if re.search(r"(?:яркост\w*\s+от|brightness\s+from)\s*(\d[\d\s.,]*)\s*(?:нит|nits|кд/м²|кд/м2|cd/m2|cd/m²)", normalized, re.IGNORECASE):
        match = re.search(r"(?:яркост\w*\s+от|brightness\s+from)\s*(\d[\d\s.,]*)", normalized, re.IGNORECASE)
        if match is not None:
            constraints.append(build_constraint("brightness", ">=", match.group(1), "nit", "яркость"))
    return deduplicate_constraints_tuples(tuple(constraints))


def infer_ranking_policy_from_text(text: str, request: NormalizedSearchRequest) -> str:
    normalized = text.casefold()
    if re.search(r"(цена\s*/\s*качество|цена\s+качество|по\s+цен[еы]\s+и\s+качеств|соотношени\w*\s+цен\w*\s+и\s+качеств)", normalized, re.IGNORECASE):
        return "value"
    if request_has_display_priority(request):
        return "display"
    if re.search(r"(сам\w*\s+мощ\w*|сам\w*\s+мощь\w*|максимальн\w*\s+производитель|топов\w*\s+производитель)", normalized, re.IGNORECASE):
        return "performance"
    return ""


def infer_price_band_hint_from_text(text: str) -> str:
    normalized = text.casefold()
    if re.search(r"(от\s+средн\w*\s+до|средн\w*\s+сегмент\w*\s+и\s+выше|mid\s+to\s+max)", normalized, re.IGNORECASE):
        return "mid_to_max"
    if re.search(r"(верхн\w*\s+сегмент|флагман\w*|топов\w*\s+сегмент)", normalized, re.IGNORECASE):
        return "top"
    return ""


def normalized_search_request_from_text(raw_value: str, fallback: str) -> NormalizedSearchRequest:
    fallback_request = build_normalized_search_request_from_fallback(fallback)
    parsed = parse_normalized_search_request(raw_value)
    if parsed is not None:
        strict_structured_json = parse_llm_json_payload(raw_value) is not None
        parsed_product_type = normalize_token(parsed.product_type)
        use_fallback_defaults = parsed_product_type not in PRODUCT_TYPE_QUERY_MAP
        resolved_product_type = parsed_product_type
        if use_fallback_defaults:
            resolved_product_type = normalize_token(fallback_request.product_type)
        cleaned_query = choose_dns_search_query(parsed.query, fallback_request.query or fallback, resolved_product_type)
        price_hint = extract_price_hint(fallback, product_type=resolved_product_type)
        if strict_structured_json:
            recovered_constraints = fallback_request.constraints
            constraints = normalize_constraints_for_product_type(
                fallback,
                resolved_product_type,
                deduplicate_constraints_tuples(merge_constraints_tuples(parsed.constraints, recovered_constraints)),
            )
            hard_wishes = normalize_merged_wishes(constraints_to_wishes(constraints))
            soft_wishes_seed = parsed.soft_wishes or (fallback_request.soft_wishes if use_fallback_defaults else ())
            soft_wishes = normalize_supported_soft_wishes(soft_wishes_seed, fallback)
            resolved_price_min = parsed.price_min
            resolved_price_max = parsed.price_max
            if resolved_price_min is None and resolved_price_max is None:
                if price_hint is not None:
                    resolved_price_min, resolved_price_max = price_hint
                else:
                    resolved_price_min = fallback_request.price_min
                    resolved_price_max = fallback_request.price_max
            source_hard_wishes_count = len(constraints)
        else:
            recovered_constraints = extract_constraints_from_text(fallback)
            constraints = normalize_constraints_for_product_type(
                fallback,
                resolved_product_type,
                deduplicate_constraints_tuples(merge_constraints_tuples(parsed.constraints, recovered_constraints)),
            )
            hard_wishes = normalize_merged_wishes(merge_wish_tuples(parsed.wishes, constraints_to_wishes(constraints)))
            soft_wishes = normalize_supported_soft_wishes(
                merge_wish_tuples(parsed.soft_wishes, extract_soft_wishes_from_text(fallback)),
                fallback,
            )
            resolved_price_min = price_hint[0] if price_hint is not None else parsed.price_min
            resolved_price_max = price_hint[1] if price_hint is not None else parsed.price_max
            source_hard_wishes_count = len(extract_hard_wishes_from_text(fallback))
        parsed = normalize_year_semantics_from_text(
            fallback,
            harmonize_normalized_request(replace(
                parsed,
                product_type=resolved_product_type or fallback_request.product_type,
                query=cleaned_query,
                price_min=resolved_price_min,
                price_max=resolved_price_max,
                brand=parsed.brand or (fallback_request.brand if use_fallback_defaults else ""),
                ranking_policy=parsed.ranking_policy or (fallback_request.ranking_policy if use_fallback_defaults else ""),
                price_band_hint=parsed.price_band_hint or (fallback_request.price_band_hint if use_fallback_defaults else ""),
                intent_signals=constraints,
                retrieval_tokens=hard_wishes,
                source_signal_count=source_hard_wishes_count,
                constraints=constraints,
                wishes=hard_wishes,
                soft_wishes=soft_wishes,
                source_hard_wishes_count=source_hard_wishes_count,
            )),
        )
        return parsed
    return harmonize_normalized_request(build_normalized_search_request_from_fallback(fallback))


def filter_selection_to_filters(raw_value: str) -> list[dict[str, object]]:
    payload = parse_llm_json_payload(raw_value)
    if payload is None:
        return []
    filters = payload.get("filters", [])
    return filters if isinstance(filters, list) else []


def shortlist_to_urls(raw_plan: str, products: list[Product]) -> list[str]:
    decision = parse_shortlist_decision(raw_plan, products)
    return decision["selected_urls"]


def parse_shortlist_decision(raw_plan: str, products: list[Product] | None = None) -> dict[str, object]:
    known_urls = {product.url for product in (products or [])}
    known_codes = {product.code: product.url for product in (products or []) if product.code}
    payload = parse_llm_json_payload(raw_plan)
    result: dict[str, object] = {
        "selected_urls": [],
        "selected_codes": [],
        "no_match": False,
        "reason": "",
        "unresolved_signals": [],
    }
    if payload is None:
        return result
    no_match = bool(payload.get("no_match"))
    reason = str(payload.get("reason", "")).strip()
    unresolved_signals = payload.get("unresolved_signals", payload.get("hard_wish_unverifiable", []))
    if not isinstance(unresolved_signals, list):
        unresolved_signals = []
    selected = payload.get("selected_codes", payload.get("selected_urls", []))
    if not isinstance(selected, list):
        selected = []
    selected_urls: list[str] = []
    selected_codes: list[str] = []
    for item in selected:
        if not isinstance(item, str):
            continue
        if item in known_codes:
            resolved_url = known_codes[item]
            if item in selected_codes or resolved_url in selected_urls:
                continue
            selected_codes.append(item)
            selected_urls.append(resolved_url)
        elif known_urls and item in known_urls:
            if item in selected_urls:
                continue
            selected_urls.append(item)
        else:
            continue
        if len(selected_urls) >= SHORTLIST_LIMIT:
            break
    result["selected_urls"] = selected_urls
    result["selected_codes"] = selected_codes
    result["no_match"] = no_match
    result["reason"] = reason
    result["unresolved_signals"] = [str(item) for item in unresolved_signals if str(item).strip()]
    return result


MODEL_COLOR_TOKENS = {
    "black",
    "white",
    "silver",
    "gray",
    "grey",
    "green",
    "blue",
    "red",
    "pink",
    "gold",
    "yellow",
    "purple",
    "черный",
    "чёрный",
    "белый",
    "серый",
    "серебристый",
    "зеленый",
    "зелёный",
    "синий",
    "красный",
    "розовый",
    "золотистый",
    "фиолетовый",
}
COMPACT_LISTING_SPEC_NAMES = {
    "дополнительно",
    "основные_характеристики",
    "кратко_о_товаре",
    "характеристики",
    "additional",
}


def build_router_client() -> DeepSeekClient:
    return DeepSeekClient.from_env(
        temperature=0.0,
        max_tokens=128,
        top_p=1.0,
    )


def build_normalize_client() -> DeepSeekClient:
    return DeepSeekClient.from_env(
        temperature=0.0,
        max_tokens=256,
        top_p=1.0,
    )


def parse_normalized_search_request(raw_value: str) -> NormalizedSearchRequest | None:
    json_object_parsed = parse_json_object_normalized_search_request(raw_value)
    if json_object_parsed is not None:
        return json_object_parsed
    json_array_parsed = parse_json_array_normalized_search_request(raw_value)
    if json_array_parsed is not None:
        return json_array_parsed
    parts = split_compact_normalize_sections(raw_value)
    if parts is None or len(parts) != 5:
        return None
    query_value = unwrap_compact_field(parts[0])
    price_min, price_max = parse_compact_price_field(parts[1])
    price_min, price_max = normalize_missing_price_pair(price_min, price_max)
    brand = normalize_token(unwrap_compact_field(parts[2]).strip("\"'"))
    hard_wishes = parse_compact_hard_wishes_field(parts[3])
    soft_wishes = parse_compact_subjective_wishes_field(parts[4])
    product_type, product_query = infer_product_type_and_query(query_value)
    return harmonize_normalized_request(NormalizedSearchRequest(
        product_type=product_type or "unknown",
        query=product_query or normalize_search_query_value(query_value),
        price_min=price_min,
        price_max=price_max,
        brand=brand,
        intent_signals=constraints_from_legacy_wishes(hard_wishes),
        retrieval_tokens=hard_wishes,
        constraints=constraints_from_legacy_wishes(hard_wishes),
        wishes=hard_wishes,
        soft_wishes=soft_wishes,
    ))


def parse_json_object_normalized_search_request(raw_value: str) -> NormalizedSearchRequest | None:
    payload = parse_llm_json_payload(raw_value)
    if payload is None:
        return None
    query_value = extract_normalize_query_value(payload.get("query") or payload.get("query_rus") or payload)
    if not query_value:
        return None
    product_type = normalize_token(str(payload.get("product_type", "")).strip())
    inferred_type, product_query = infer_product_type_and_query(query_value)
    constraints = extract_normalize_constraints(payload.get("intent_signals") or payload.get("constraints"))
    soft_wishes = extract_normalize_soft_wishes(payload.get("soft_wishes"))
    ranking_policy = extract_normalize_ranking_policy(payload.get("ranking_policy"))
    price_band_hint = extract_normalize_price_band_hint(payload.get("price_band_hint"))
    brand = normalize_token(extract_normalize_brand_value(payload.get("brand") or payload.get("brand_en")))
    price_min = parse_optional_int_string(str(payload.get("price_min", "")).strip())
    price_max = parse_optional_int_string(str(payload.get("price_max", "")).strip())
    if price_min is None and price_max is None:
        price_min, price_max = extract_normalize_price_pair(payload.get("price"))
    price_min, price_max = normalize_missing_price_pair(price_min, price_max)
    retrieval_tokens = tuple(str(item) for item in payload.get("retrieval_tokens", []) if isinstance(item, str)) or constraints_to_wishes(constraints)
    source_signal_count = int(payload.get("source_signal_count", 0) or 0)
    return harmonize_normalized_request(NormalizedSearchRequest(
        product_type=inferred_type or product_type or "unknown",
        query=choose_dns_search_query(product_query or query_value, query_value, inferred_type or product_type),
        price_min=price_min,
        price_max=price_max,
        brand=brand,
        ranking_policy=ranking_policy,
        price_band_hint=price_band_hint,
        intent_signals=constraints,
        retrieval_tokens=retrieval_tokens,
        source_signal_count=source_signal_count,
        constraints=constraints,
        wishes=retrieval_tokens,
        soft_wishes=soft_wishes,
    ))


def parse_json_array_normalized_search_request(raw_value: str) -> NormalizedSearchRequest | None:
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, list) or len(payload) != 5:
        return None
    query_value = extract_normalize_query_value(payload[0])
    if not query_value:
        return None
    price_min, price_max = extract_normalize_price_pair(payload[1])
    price_min, price_max = normalize_missing_price_pair(price_min, price_max)
    brand = normalize_token(extract_normalize_brand_value(payload[2]))
    hard_wishes = extract_normalize_hard_wishes(payload[3])
    constraints = extract_normalize_constraints(payload[3])
    soft_wishes = extract_normalize_soft_wishes(payload[4])
    inferred_type, product_query = infer_product_type_and_query(query_value)
    return harmonize_normalized_request(NormalizedSearchRequest(
        product_type=inferred_type or "unknown",
        query=choose_dns_search_query(product_query or query_value, query_value, inferred_type),
        price_min=price_min,
        price_max=price_max,
        brand=brand,
        intent_signals=constraints or constraints_from_legacy_wishes(hard_wishes),
        retrieval_tokens=normalize_merged_wishes(hard_wishes),
        constraints=constraints or constraints_from_legacy_wishes(hard_wishes),
        wishes=normalize_merged_wishes(hard_wishes),
        soft_wishes=soft_wishes,
    ))


def extract_normalize_query_value(value: object) -> str:
    if isinstance(value, str):
        return unwrap_compact_field(value)
    if isinstance(value, dict):
        for key in ("query_rus", "query", "search_query"):
            item = value.get(key)
            if isinstance(item, str) and item.strip():
                return item.strip()
    return ""


def extract_normalize_price_pair(value: object) -> tuple[int | None, int | None]:
    if isinstance(value, dict):
        minimum = parse_optional_int_string(str(value.get("min", "")).strip())
        maximum = parse_optional_int_string(str(value.get("max", "")).strip())
        return minimum, maximum
    if isinstance(value, str):
        return parse_compact_price_field(value)
    return None, None


def normalize_missing_price_pair(price_min: int | None, price_max: int | None) -> tuple[int | None, int | None]:
    if price_min == 0 and price_max == 0:
        return None, None
    return price_min, price_max


def extract_normalize_brand_value(value: object) -> str:
    if isinstance(value, str):
        return unwrap_compact_field(value).strip("\"'")
    if isinstance(value, dict):
        for key in ("brand_en", "brand"):
            item = value.get(key)
            if isinstance(item, str) and item.strip():
                return item.strip().strip("\"'")
    return ""


def extract_normalize_hard_wishes(value: object) -> tuple[str, ...]:
    if isinstance(value, dict):
        return hard_wishes_from_payload(value)
    if isinstance(value, str):
        return parse_compact_hard_wishes_field(value)
    return ()


def extract_normalize_constraints(value: object) -> tuple[NormalizedConstraint, ...]:
    if isinstance(value, list):
        constraints: list[NormalizedConstraint] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            key = normalize_token(str(item.get("key", "")).strip())
            op = str(item.get("op", "")).strip()
            raw_value = item.get("value", "")
            unit = normalize_token(str(item.get("unit", "")).strip())
            source_text = str(item.get("source_text", "")).strip()
            if not key or not op or raw_value in {"", None}:
                continue
            constraints.append(
                NormalizedConstraint(
                    key=key,
                    op=op,
                    value=str(raw_value).strip(),
                    unit=unit,
                    source_text=source_text,
                )
            )
        return merge_constraints_tuples(tuple(constraints))
    if isinstance(value, dict):
        return constraints_from_payload(value)
    return ()


def extract_normalize_soft_wishes(value: object) -> tuple[str, ...]:
    if isinstance(value, list):
        wishes = [canonicalize_wish(normalize_token(str(item))) for item in value if str(item).strip()]
        return merge_wish_tuples(tuple(wish for wish in wishes if wish))
    if isinstance(value, dict):
        wishes = [canonicalize_wish(normalize_token(key)) for key, raw in value.items() if raw]
        return merge_wish_tuples(tuple(wish for wish in wishes if wish))
    if isinstance(value, str):
        return parse_compact_subjective_wishes_field(value)
    return ()


def extract_normalize_ranking_policy(value: object) -> str:
    normalized = normalize_token(str(value).strip())
    if normalized in {"", "balanced", "value", "performance", "display"}:
        return normalized
    if normalized == "value_performance":
        return "value"
    return ""


def extract_normalize_price_band_hint(value: object) -> str:
    normalized = normalize_token(str(value).strip())
    if normalized in {"", "budget", "mid", "mid_to_max", "top", "any"}:
        return normalized
    return ""


def split_compact_normalize_sections(raw_value: str) -> list[str] | None:
    stripped = raw_value.strip()
    if not stripped.startswith("[") or not stripped.endswith("]"):
        return None
    body = stripped[1:-1].strip()
    if not body:
        return []
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    in_string = False
    escaped = False
    for char in body:
        current.append(char)
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char in "[{":
            depth += 1
            continue
        if char in "]}":
            depth -= 1
            continue
        if char == "," and depth == 0:
            current.pop()
            parts.append("".join(current).strip())
            current = []
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def unwrap_compact_field(value: str) -> str:
    stripped = value.strip()
    if stripped == "{}":
        return ""
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped[1:-1].strip()
    return stripped


def parse_compact_price_field(value: str) -> tuple[int | None, int | None]:
    stripped = unwrap_compact_field(value)
    if not stripped:
        return None, None
    if ":" not in stripped:
        return None, None
    left, right = (part.strip() for part in stripped.split(":", 1))
    if not left or not right:
        return None, None
    try:
        return int(left), int(right)
    except ValueError:
        return None, None


def parse_compact_subjective_wishes_field(value: str) -> tuple[str, ...]:
    stripped = unwrap_compact_field(value)
    if not stripped:
        return ()
    wishes = []
    for item in stripped.split(","):
        cleaned_item = item.strip().strip("{}\"' ")
        if ":" in cleaned_item:
            cleaned_item = cleaned_item.split(":", 1)[0].strip().strip("\"' ")
        canonical = canonicalize_wish(normalize_token(cleaned_item))
        if canonical:
            wishes.append(canonical)
    return merge_wish_tuples(tuple(wishes))


def parse_compact_hard_wishes_field(value: str) -> tuple[str, ...]:
    stripped = value.strip()
    if stripped == "{}":
        return ()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return ()
    if not isinstance(payload, dict):
        return ()
    return normalize_merged_wishes(hard_wishes_from_payload(payload))


def hard_wishes_from_payload(payload: dict[str, object]) -> tuple[str, ...]:
    wishes: list[str] = []
    storage_value = ""
    storage_type_value = ""
    for raw_key, raw_value in payload.items():
        key = normalize_token(str(raw_key))
        value = normalize_token(str(raw_value))
        if key in {"ram", "ram_min"}:
            if value == "12_gb":
                wishes.append("12gb_ram")
            elif value == "16_gb":
                wishes.append("16gb_ram")
            elif value == "32_gb":
                wishes.append("32gb_ram")
        elif key in {"storage", "memory", "storage_min"}:
            storage_value = value
            if value == "256_gb":
                wishes.append("storage_from_256_gb" if key == "storage_min" else "256gb_storage")
        elif key == "storage_type":
            storage_type_value = value
            if value == "ssd":
                wishes.append("ssd")
        elif key in {"gpu", "gpu_min"}:
            if "4060" in value:
                wishes.append("rtx_4060")
            if "4070" in value:
                wishes.append("rtx_4070_or_higher" if key == "gpu_min" else "rtx_4070")
            if "4080" in value:
                wishes.append("rtx_4080")
        elif key in {"refresh_rate", "screen_refresh", "display_refresh", "refresh_rate_min"}:
            if key == "refresh_rate_min":
                numeric_refresh = parse_first_number(value)
                if numeric_refresh is not None and numeric_refresh >= 165:
                    wishes.append("refresh_rate_from_165hz")
                elif numeric_refresh is not None and numeric_refresh >= 120:
                    wishes.append("refresh_rate_from_120hz")
            elif "165" in value:
                wishes.append("refresh_rate_from_165hz")
            elif "120" in value:
                wishes.append("refresh_rate_from_120hz")
            elif "240" in value:
                wishes.append("240hz_screen")
            elif "144" in value:
                wishes.append("144hz_display")
        elif key in {"panel", "screen_type"}:
            if "ips" in value:
                wishes.append("ips")
            elif "amoled" in value:
                wishes.append("amoled_display")
            elif "oled" in value:
                wishes.append("oled")
        elif key == "matrix_type":
            if "super_amoled" in value or "dynamic_amoled" in value or "amoled" in value:
                wishes.append("matrix_type_amoled")
            elif "oled" in value:
                wishes.append("matrix_type_oled")
            elif "ips" in value:
                wishes.append("matrix_type_ips")
            elif "qled" in value:
                wishes.append("matrix_type_qled")
            elif value == "va" or "va_" in value or "_va" in value:
                wishes.append("matrix_type_va")
        elif key in {"resolution", "display_resolution"}:
            if "1440" in value or "qhd" in value:
                wishes.append("1440p")
            elif "4k" in value or "3840x2160" in value:
                wishes.append("4k")
        elif key in {"size", "screen_size"}:
            if value.startswith("27"):
                wishes.append("27_inch")
            elif value.startswith("55"):
                wishes.append("55_inch")
        elif key in {"height_adjustment", "height_adjustable"} and value in {"yes", "true", "есть"}:
            wishes.append("height_adjustable")
        elif key == "nfc":
            if value in {"true", "yes", "есть", "1"}:
                wishes.append("nfc")
        elif key in {"network", "connectivity"}:
            if value in {"wifi", "wi-fi", "wlan"}:
                wishes.append("wifi")
            elif "5g" in value:
                wishes.append("network_5g")
        elif key == "fast_charge":
            if value in {"true", "yes", "есть", "1"}:
                wishes.append("fast_charge")
        elif key == "wireless_charge":
            if value in {"true", "yes", "есть", "1"}:
                wishes.append("wireless_charge")
        elif key == "protection":
            if "ip68" in value:
                wishes.append("waterproof_ip68")
            elif "ip67" in value:
                wishes.append("waterproof_ip67")
        elif key in {"screen_finish", "finish", "coating"} and ("matte" in value or "матов" in value):
            wishes.append("matte_screen")
        elif key in {"weight_max", "weight"}:
            if "1_5" in value:
                wishes.append("weight_up_to_1.5_kg")
            elif "2_3" in value:
                wishes.append("weight_up_to_2.3_kg")
            elif "2_5" in value:
                wishes.append("weight_up_to_2.5_kg")
        elif key in {"year", "year_min"} and "2024" in value:
            wishes.append("year_from_2024" if key == "year_min" else "2024_year")
        elif key == "nfc" and value in {"yes", "true", "есть"}:
            wishes.append("nfc")
        elif key == "keyboard_type" and "mechanical" in value:
            wishes.append("mechanical_keyboard")
        elif key == "layout" and "side" in value:
            wishes.append("side_by_side")
        elif key == "dryer" and value in {"yes", "true", "есть"}:
            wishes.append("dryer")
        elif key in {"wet_cleaning", "cleaning_mode"} and value in {"yes", "true", "есть", "wet", "влажная_уборка"}:
            wishes.append("wet_cleaning")
        elif key == "mapping" and value in {"true", "yes", "есть"}:
            wishes.append("mapping")
        elif key in {"navigation", "mapping"} and "lidar" in value:
            wishes.append("lidar_navigation")
    if storage_type_value == "ssd" and "512" in storage_value:
        wishes.append("ssd_from_512_gb")
    return normalize_merged_wishes(tuple(wishes))


def constraints_from_payload(payload: dict[str, object]) -> tuple[NormalizedConstraint, ...]:
    constraints: list[NormalizedConstraint] = []
    for raw_key, raw_value in payload.items():
        key = normalize_token(str(raw_key))
        value = normalize_token(str(raw_value))
        if raw_value in {"", None, False}:
            continue
        if key == "ram_min":
            constraints.append(build_constraint("ram", ">=", raw_value, "gb", str(raw_key)))
        elif key == "ram":
            constraints.append(build_constraint("ram", "==", raw_value, "gb", str(raw_key)))
        elif key == "storage_min":
            constraints.append(build_constraint("storage", ">=", raw_value, infer_storage_unit(value), str(raw_key)))
        elif key in {"storage", "memory"}:
            constraints.append(build_constraint("storage", "==", raw_value, infer_storage_unit(value), str(raw_key)))
        elif key == "storage_type":
            constraints.append(build_constraint("storage_type", "==", raw_value, "", str(raw_key)))
        elif key == "refresh_rate_min":
            constraints.append(build_constraint("refresh_rate", ">=", raw_value, "hz", str(raw_key)))
        elif key in {"refresh_rate", "screen_refresh", "display_refresh"}:
            constraints.append(build_constraint("refresh_rate", "==", raw_value, "hz", str(raw_key)))
        elif key == "gpu_min":
            constraints.append(build_constraint("gpu", ">=", raw_value, "", str(raw_key)))
        elif key == "gpu":
            constraints.append(build_constraint("gpu", "==", raw_value, "", str(raw_key)))
        elif key == "matrix_type":
            constraints.append(build_constraint("matrix_type", "==", raw_value, "", str(raw_key)))
        elif key in {"panel", "screen_type"}:
            constraints.append(build_constraint("matrix_type", "==", raw_value, "", str(raw_key)))
        elif key in {"sewing_operations", "sewing_operations_min"}:
            constraints.append(build_constraint("sewing_operations", ">=" if key.endswith("_min") else "==", raw_value, "", str(raw_key)))
        elif key == "shuttle_type":
            constraints.append(build_constraint("shuttle_type", "==", raw_value, "", str(raw_key)))
        elif key == "buttonhole":
            constraints.append(build_constraint("buttonhole", "==", raw_value, "", str(raw_key)))
        elif key in {"speed_control", "speed_regulation"} and value in {"true", "yes", "есть", "1"}:
            constraints.append(build_constraint("speed_control", "==", "true", "", str(raw_key)))
        elif key in {"work_area_light", "work_area_illumination"} and value in {"true", "yes", "есть", "1"}:
            constraints.append(build_constraint("work_area_light", "==", "true", "", str(raw_key)))
        elif key in {"size", "screen_size"}:
            constraints.append(build_constraint("screen_size", "==", raw_value, "inch", str(raw_key)))
        elif key == "brightness":
            constraints.append(build_constraint("brightness", ">=", raw_value, "nit", str(raw_key)))
        elif key in {"resolution", "display_resolution"}:
            constraints.append(build_constraint("resolution", "==", raw_value, "", str(raw_key)))
        elif key in {"height_adjustment", "height_adjustable"} and value in {"yes", "true", "есть", "1"}:
            constraints.append(build_constraint("height_adjustment", "==", "true", "", str(raw_key)))
        elif key in {"nfc", "fast_charge", "wireless_charge"} and value in {"true", "yes", "есть", "1"}:
            constraints.append(build_constraint(key, "==", "true", "", str(raw_key)))
        elif key == "power":
            constraints.append(build_constraint("power", ">=", raw_value, "w", str(raw_key)))
        elif key in {"removable_panels", "nonstick_coating", "temperature_control", "grease_tray", "opens_180"} and value in {"true", "yes", "есть", "1"}:
            constraints.append(build_constraint(key, "==", "true", "", str(raw_key)))
        elif key == "smartphone_control" and value in {"true", "yes", "есть", "1"}:
            constraints.append(build_constraint("smartphone_control", "==", "true", "", str(raw_key)))
        elif key == "battery_capacity":
            constraints.append(build_constraint("battery_capacity", ">=", raw_value, "mah", str(raw_key)))
        elif key == "auto_return_to_base" and value in {"true", "yes", "есть", "1"}:
            constraints.append(build_constraint("auto_return_to_base", "==", "true", "", str(raw_key)))
        elif key == "dustbin_easy_cleaning" and value in {"true", "yes", "есть", "1"}:
            constraints.append(build_constraint("dustbin_easy_cleaning", "==", "true", "", str(raw_key)))
        elif key == "good_navigation" and value in {"true", "yes", "есть", "1"}:
            constraints.append(build_constraint("good_navigation", "==", "true", "", str(raw_key)))
        elif key in {"device_type", "device_kind"}:
            constraints.append(build_constraint("device_type", "==", raw_value, "", str(raw_key)))
        elif key == "print_technology":
            constraints.append(build_constraint("print_technology", "==", raw_value, "", str(raw_key)))
        elif key == "color_mode":
            constraints.append(build_constraint("color_mode", "==", raw_value, "", str(raw_key)))
        elif key == "wifi" and value in {"true", "yes", "есть", "1"}:
            constraints.append(build_constraint("wifi", "==", "true", "", str(raw_key)))
        elif key == "duplex_print" and value in {"true", "yes", "есть", "1"}:
            constraints.append(build_constraint("duplex_print", "==", "true", "", str(raw_key)))
        elif key == "scanner" and value in {"true", "yes", "есть", "1"}:
            constraints.append(build_constraint("scanner", "==", "true", "", str(raw_key)))
        elif key == "print_speed":
            constraints.append(build_constraint("print_speed", ">=", raw_value, "ppm", str(raw_key)))
        elif key == "refill_easy" and value in {"true", "yes", "есть", "1"}:
            constraints.append(build_constraint("refill_easy", "==", "true", "", str(raw_key)))
        elif key == "cheap_maintenance" and value in {"true", "yes", "есть", "1"}:
            constraints.append(build_constraint("cheap_maintenance", "==", "true", "", str(raw_key)))
        elif key == "resistance_system":
            constraints.append(build_constraint("resistance_system", "==", raw_value, "", str(raw_key)))
        elif key == "max_user_weight":
            constraints.append(build_constraint("max_user_weight", ">=", raw_value, "kg", str(raw_key)))
        elif key == "seat_adjustment" and value in {"true", "yes", "есть", "1"}:
            constraints.append(build_constraint("seat_adjustment", "==", "true", "", str(raw_key)))
        elif key == "display" and value in {"true", "yes", "есть", "1"}:
            constraints.append(build_constraint("display", "==", "true", "", str(raw_key)))
        elif key == "pulse_measurement" and value in {"true", "yes", "есть", "1"}:
            constraints.append(build_constraint("pulse_measurement", "==", "true", "", str(raw_key)))
        elif key == "resistance_levels":
            constraints.append(build_constraint("resistance_levels", ">=", raw_value, "", str(raw_key)))
        elif key == "stable_construction" and value in {"true", "yes", "есть", "1"}:
            constraints.append(build_constraint("stable_construction", "==", "true", "", str(raw_key)))
        elif key == "machine_type":
            constraints.append(build_constraint("machine_type", "==", raw_value, "", str(raw_key)))
        elif key == "cappuccinator" and value in {"true", "yes", "есть", "1"}:
            constraints.append(build_constraint("cappuccinator", "==", "true", "", str(raw_key)))
        elif key == "pressure":
            constraints.append(build_constraint("pressure", ">=", raw_value, "bar", str(raw_key)))
        elif key == "built_in_grinder" and value in {"true", "yes", "есть", "1"}:
            constraints.append(build_constraint("built_in_grinder", "==", "true", "", str(raw_key)))
        elif key == "strength_adjustment" and value in {"true", "yes", "есть", "1"}:
            constraints.append(build_constraint("strength_adjustment", "==", "true", "", str(raw_key)))
        elif key == "portion_volume_adjustment" and value in {"true", "yes", "есть", "1"}:
            constraints.append(build_constraint("portion_volume_adjustment", "==", "true", "", str(raw_key)))
        elif key == "self_cleaning" and value in {"true", "yes", "есть", "1"}:
            constraints.append(build_constraint("self_cleaning", "==", "true", "", str(raw_key)))
        elif key in {"network", "connectivity"}:
            if value in {"wifi", "wi-fi", "wlan"}:
                constraints.append(build_constraint("wifi", "==", "true", "", str(raw_key)))
            else:
                constraints.append(build_constraint("network", "==", raw_value, "", str(raw_key)))
        elif key == "protection":
            constraints.append(build_constraint("protection", ">=", raw_value, "", str(raw_key)))
        elif key in {"screen_finish", "finish", "coating"}:
            constraints.append(build_constraint("screen_finish", "==", raw_value, "", str(raw_key)))
        elif key in {"weight_max", "weight"}:
            constraints.append(build_constraint("weight", "<=" if key == "weight_max" else "==", raw_value, "kg", str(raw_key)))
        elif key == "year_min":
            constraints.append(build_constraint("year", ">=", raw_value, "", str(raw_key)))
        elif key == "year":
            constraints.append(build_constraint("year", "==", raw_value, "", str(raw_key)))
        elif key in {"width", "width_max"}:
            constraints.append(build_constraint("width", "<=" if key.endswith("_max") else "==", raw_value, "cm", str(raw_key)))
        elif key in {"height", "height_max"}:
            constraints.append(build_constraint("height", "<=" if key.endswith("_max") else "==", raw_value, "cm", str(raw_key)))
        elif key in {"depth", "depth_max"}:
            constraints.append(build_constraint("depth", "<=" if key.endswith("_max") else "==", raw_value, "cm", str(raw_key)))
        elif key in {"volume", "volume_min"}:
            constraints.append(build_constraint("volume", ">=" if key.endswith("_min") else "==", raw_value, "l", str(raw_key)))
        elif key in {"energy_class", "energy_class_min"}:
            constraints.append(build_constraint("energy_class", ">=" if key.endswith("_min") else "==", raw_value, "", str(raw_key)))
        elif key in {"cooling_system", "defrost_system"}:
            constraints.append(build_constraint("cooling_system", "==", raw_value, "", str(raw_key)))
        elif key in {"freezer_position", "freezer_position_bottom"}:
            constraints.append(build_constraint("freezer_position", "==", raw_value, "", str(raw_key)))
        elif key in {"compressor_type", "inverter_compressor"}:
            compressor_value = "true" if value in {"true", "yes", "есть", "1", "inverter"} else raw_value
            constraints.append(build_constraint("inverter_compressor", "==", compressor_value, "", str(raw_key)))
        elif key == "navigation":
            constraints.append(build_constraint("navigation", "==", raw_value, "", str(raw_key)))
        elif key in {"keyboard_type", "keyboard_switch_type"}:
            constraints.append(build_constraint("keyboard_type", "==", raw_value, "", str(raw_key)))
        elif key in {"keyboard_format", "keyboard_layout", "form_factor"}:
            constraints.append(build_constraint("keyboard_format", "==", raw_value, "", str(raw_key)))
        elif key == "layout":
            constraints.append(build_constraint("layout", "==", raw_value, "", str(raw_key)))
        elif key == "dryer" and value in {"yes", "true", "есть", "1"}:
            constraints.append(build_constraint("dryer", "==", "true", "", str(raw_key)))
        elif key in {"wet_cleaning", "cleaning_mode"} and value in {"yes", "true", "есть", "wet", "влажная_уборка"}:
            constraints.append(build_constraint("wet_cleaning", "==", "true", "", str(raw_key)))
        elif key == "mapping" and value in {"yes", "true", "есть", "1"}:
            constraints.append(build_constraint("mapping", "==", "true", "", str(raw_key)))
    return merge_constraints_tuples(tuple(constraints))


def build_constraint(key: str, op: str, raw_value: object, unit: str, source_text: str) -> NormalizedConstraint:
    return NormalizedConstraint(
        key=normalize_token(key),
        op=op.strip(),
        value=str(raw_value).strip().replace('"', ""),
        unit=normalize_token(unit),
        source_text=source_text.strip(),
    )


def infer_storage_unit(value: str) -> str:
    if "tb" in value or "тб" in value:
        return "tb"
    return "gb"


def merge_constraints_tuples(*constraint_sets: tuple[NormalizedConstraint, ...]) -> tuple[NormalizedConstraint, ...]:
    merged: list[NormalizedConstraint] = []
    seen: set[tuple[str, str, str, str]] = set()
    for constraint_set in constraint_sets:
        for constraint in constraint_set:
            signature = (
                normalize_token(constraint.key),
                constraint.op.strip(),
                normalize_token(str(constraint.value)),
                normalize_token(constraint.unit),
            )
            if signature in seen:
                continue
            seen.add(signature)
            merged.append(constraint)
    return tuple(merged)


def deduplicate_constraints_tuples(constraints: tuple[NormalizedConstraint, ...]) -> tuple[NormalizedConstraint, ...]:
    return merge_constraints_tuples(constraints)


def constraints_to_wishes(constraints: tuple[NormalizedConstraint, ...]) -> tuple[str, ...]:
    wishes: list[str] = []
    storage_floor: float | None = None
    storage_type_ssd = False
    for constraint in constraints:
        key = normalize_token(constraint.key)
        value = normalize_token(str(constraint.value))
        op = constraint.op
        numeric = parse_first_number(value)
        if key == "ram":
            if op == ">=" and numeric is not None and numeric >= 32:
                wishes.append("32gb_ram")
            elif op == ">=" and numeric is not None and numeric >= 12:
                wishes.append("12gb_ram")
            elif op == "==" and numeric == 16:
                wishes.append("16gb_ram")
            elif op == "==" and numeric == 32:
                wishes.append("32gb_ram")
        elif key == "storage":
            if numeric is not None:
                storage_floor = max(storage_floor or 0.0, numeric)
            if op == ">=" and numeric is not None and numeric >= 256:
                wishes.append("storage_from_256_gb")
            elif op == "==" and numeric == 256:
                wishes.append("256gb_storage")
        elif key == "storage_type" and value == "ssd":
            storage_type_ssd = True
            wishes.append("ssd")
        elif key == "screen_size" and value.startswith("27"):
            wishes.append("27_inch")
        elif key == "screen_size" and value.startswith("55"):
            wishes.append("55_inch")
        elif key == "resolution" and ("1440" in value or "2560x1440" in value):
            wishes.append("1440p")
        elif key == "resolution" and ("3840x2160" in value or "4k" in value):
            wishes.append("4k")
        elif key == "height_adjustment" and value == "true":
            wishes.append("height_adjustable")
        elif key == "refresh_rate":
            numeric = parse_first_number(value)
            if op == ">=" and numeric is not None and numeric >= 165:
                wishes.append("refresh_rate_from_165hz")
            elif op == ">=" and numeric is not None and numeric >= 120:
                wishes.append("refresh_rate_from_120hz")
            elif op == "==" and numeric == 240:
                wishes.append("240hz_screen")
            elif op == "==" and numeric == 144:
                wishes.append("144hz_display")
        elif key == "gpu":
            if op == ">=" and "4070" in value:
                wishes.append("rtx_4070_or_higher")
            elif op == "==" and "4070" in value:
                wishes.append("rtx_4070")
            elif "4080" in value:
                wishes.append("rtx_4080")
            elif "4070" in value:
                wishes.append("rtx_4070")
        elif key == "matrix_type":
            if "amoled" in value:
                wishes.append("matrix_type_amoled")
            elif "oled" in value:
                wishes.append("matrix_type_oled")
            elif "ips" in value:
                wishes.append("ips")
            elif value == "va":
                wishes.append("matrix_type_va")
            elif "qled" in value:
                wishes.append("matrix_type_qled")
        elif key == "sewing_operations":
            if op == ">=" and numeric is not None and numeric >= 30:
                wishes.append("sewing_operations_from_30")
            elif op == "==" and numeric is not None and numeric >= 30:
                wishes.append("sewing_operations_from_30")
        elif key == "shuttle_type" and "horizontal" in value:
            wishes.append("shuttle_type_horizontal")
        elif key == "buttonhole" and "automatic" in value:
            wishes.append("buttonhole_automatic")
        elif key == "speed_control" and value == "true":
            wishes.append("speed_control")
        elif key == "work_area_light" and value == "true":
            wishes.append("work_area_light")
        elif key == "power" and op == ">=" and numeric is not None and numeric >= 1800:
            wishes.append("power_from_1800_w")
        elif key == "removable_panels" and value == "true":
            wishes.append("removable_panels")
        elif key == "nonstick_coating" and value == "true":
            wishes.append("nonstick_coating")
        elif key == "temperature_control" and value == "true":
            wishes.append("temperature_control")
        elif key == "grease_tray" and value == "true":
            wishes.append("grease_tray")
        elif key == "opens_180" and value == "true":
            wishes.append("opens_180")
        elif key == "smartphone_control" and value == "true":
            wishes.append("smartphone_control")
        elif key == "battery_capacity" and op == ">=" and numeric is not None and numeric >= 4000:
            wishes.append("battery_capacity_from_4000_mah")
        elif key == "auto_return_to_base" and value == "true":
            wishes.append("auto_return_to_base")
        elif key == "dustbin_easy_cleaning" and value == "true":
            wishes.append("dustbin_easy_cleaning")
        elif key == "good_navigation" and value == "true":
            wishes.append("good_navigation")
        elif key == "device_type" and "mfp" in value:
            wishes.append("device_type_mfp")
        elif key == "print_technology" and "laser" in value:
            wishes.append("print_technology_laser")
        elif key == "color_mode" and ("mono" in value or "black_white" in value or "blackwhite" in value):
            wishes.append("color_mode_monochrome")
        elif key == "wifi" and value == "true":
            wishes.append("wifi")
        elif key == "duplex_print" and value == "true":
            wishes.append("duplex_print")
        elif key == "scanner" and value == "true":
            wishes.append("scanner")
        elif key == "print_speed" and op == ">=" and numeric is not None and numeric >= 20:
            wishes.append("print_speed_from_20_ppm")
        elif key == "refill_easy" and value == "true":
            wishes.append("refill_easy")
        elif key == "cheap_maintenance" and value == "true":
            wishes.append("cheap_maintenance")
        elif key == "resistance_system" and "magnetic" in value:
            wishes.append("resistance_system_magnetic")
        elif key == "keyboard_type" and ("magnetic" in value or "магнит" in value):
            wishes.append("keyboard_type_magnetic")
        elif key == "keyboard_format" and ("75" in value or "80" in value or "tkl" in value):
            wishes.append("keyboard_format_75_80")
        elif key == "max_user_weight" and op == ">=" and numeric is not None and numeric >= 120:
            wishes.append("max_user_weight_from_120_kg")
        elif key == "seat_adjustment" and value == "true":
            wishes.append("seat_adjustment")
        elif key == "display" and value == "true":
            wishes.append("display")
        elif key == "pulse_measurement" and value == "true":
            wishes.append("pulse_measurement")
        elif key == "resistance_levels" and op == ">=" and numeric is not None and numeric >= 8:
            wishes.append("resistance_levels_from_8")
        elif key == "stable_construction" and value == "true":
            wishes.append("stable_construction")
        elif key == "machine_type" and "automatic" in value:
            wishes.append("machine_type_automatic")
        elif key == "cappuccinator" and value == "true":
            wishes.append("cappuccinator")
        elif key == "pressure" and op == ">=" and numeric is not None and numeric >= 15:
            wishes.append("pressure_from_15_bar")
        elif key == "built_in_grinder" and value == "true":
            wishes.append("built_in_grinder")
        elif key == "strength_adjustment" and value == "true":
            wishes.append("strength_adjustment")
        elif key == "portion_volume_adjustment" and value == "true":
            wishes.append("portion_volume_adjustment")
        elif key == "self_cleaning" and value == "true":
            wishes.append("self_cleaning")
        elif key == "network" and "5g" in value:
            wishes.append("network_5g")
        elif key == "navigation" and "lidar" in value:
            wishes.append("lidar_navigation")
        elif key == "nfc" and value == "true":
            wishes.append("nfc")
        elif key == "fast_charge" and value == "true":
            wishes.append("fast_charge")
        elif key == "wireless_charge" and value == "true":
            wishes.append("wireless_charge")
        elif key == "protection":
            if "ip68" in value:
                wishes.append("waterproof_ip68")
            elif "ip67" in value:
                wishes.append("waterproof_ip67")
        elif key == "screen_finish" and ("matte" in value or "матов" in value):
            wishes.append("matte_screen")
        elif key == "weight":
            if op == "<=" and numeric is not None and numeric <= 2.3:
                wishes.append("weight_up_to_2.3_kg")
            elif op == "<=" and numeric is not None and numeric <= 2.5:
                wishes.append("weight_up_to_2.5_kg")
        elif key == "year":
            if op == ">=" and numeric is not None and numeric >= 2024:
                wishes.append("year_from_2024")
            elif op == "==" and numeric == 2024:
                wishes.append("2024_year")
        elif key == "cooling_system" and "no_frost" in value.replace("-", "_"):
            wishes.append("cooling_system_no_frost")
        elif key == "freezer_position" and value in {"bottom", "снизу"}:
            wishes.append("freezer_position_bottom")
        elif key == "inverter_compressor" and value in {"true", "inverter", "yes", "есть", "1"}:
            wishes.append("inverter_compressor")
        elif key == "layout" and "side" in value:
            wishes.append("side_by_side")
        elif key == "dryer" and value == "true":
            wishes.append("dryer")
        elif key == "wet_cleaning" and value == "true":
            wishes.append("wet_cleaning")
        elif key == "mapping" and value == "true":
            wishes.append("mapping")
        elif key == "width":
            if op == "<=" and numeric is not None and numeric <= 60:
                wishes.append("width_up_to_60_cm")
        elif key == "volume":
            if op == ">=" and numeric is not None and numeric >= 300:
                wishes.append("volume_from_300_l")
        elif key == "energy_class" and normalize_energy_class(value) in {"a", "a+", "a++", "a+++"} and op in {">=", "=="}:
            wishes.append("energy_class_not_lower_than_a")
    if storage_type_ssd and storage_floor is not None and storage_floor >= 512:
        wishes.append("ssd_from_512_gb")
    return normalize_merged_wishes(tuple(wishes))


def constraints_from_legacy_wishes(wishes: tuple[str, ...]) -> tuple[NormalizedConstraint, ...]:
    constraints: list[NormalizedConstraint] = []
    for wish in normalize_merged_wishes(wishes):
        if wish == "12gb_ram":
            constraints.append(build_constraint("ram", ">=", "12", "gb", wish))
        elif wish == "16gb_ram":
            constraints.append(build_constraint("ram", "==", "16", "gb", wish))
        elif wish == "32gb_ram":
            constraints.append(build_constraint("ram", "==", "32", "gb", wish))
        elif wish == "storage_from_256_gb":
            constraints.append(build_constraint("storage", ">=", "256", "gb", wish))
        elif wish == "256gb_storage":
            constraints.append(build_constraint("storage", "==", "256", "gb", wish))
        elif wish == "ssd_from_512_gb":
            constraints.append(build_constraint("storage", ">=", "512", "gb", wish))
            constraints.append(build_constraint("storage_type", "==", "ssd", "", wish))
        elif wish == "27_inch":
            constraints.append(build_constraint("screen_size", "==", "27", "inch", wish))
        elif wish == "1440p":
            constraints.append(build_constraint("resolution", "==", "2560x1440", "", wish))
        elif wish == "ips" or wish == "matrix_type_ips":
            constraints.append(build_constraint("matrix_type", "==", "ips", "", wish))
        elif wish == "amoled_display" or wish == "matrix_type_amoled":
            constraints.append(build_constraint("matrix_type", "==", "amoled", "", wish))
        elif wish == "oled" or wish == "matrix_type_oled":
            constraints.append(build_constraint("matrix_type", "==", "oled", "", wish))
        elif wish == "height_adjustable":
            constraints.append(build_constraint("height_adjustment", "==", "true", "", wish))
        elif wish == "refresh_rate_from_120hz":
            constraints.append(build_constraint("refresh_rate", ">=", "120", "hz", wish))
        elif wish == "refresh_rate_from_165hz":
            constraints.append(build_constraint("refresh_rate", ">=", "165", "hz", wish))
        elif wish == "144hz_display":
            constraints.append(build_constraint("refresh_rate", "==", "144", "hz", wish))
        elif wish == "240hz_screen":
            constraints.append(build_constraint("refresh_rate", "==", "240", "hz", wish))
        elif wish == "55_inch":
            constraints.append(build_constraint("screen_size", "==", "55", "inch", wish))
        elif wish == "4k":
            constraints.append(build_constraint("resolution", "==", "3840x2160", "", wish))
        elif wish == "lidar_navigation":
            constraints.append(build_constraint("navigation", "==", "lidar", "", wish))
        elif wish == "rtx_4070":
            constraints.append(build_constraint("gpu", "==", "rtx 4070", "", wish))
        elif wish == "rtx_4070_or_higher":
            constraints.append(build_constraint("gpu", ">=", "rtx 4070", "", wish))
        elif wish == "rtx_4080":
            constraints.append(build_constraint("gpu", "==", "rtx 4080", "", wish))
        elif wish == "matrix_type_amoled":
            constraints.append(build_constraint("matrix_type", "==", "amoled", "", wish))
        elif wish == "matrix_type_oled":
            constraints.append(build_constraint("matrix_type", "==", "oled", "", wish))
        elif wish == "matrix_type_ips":
            constraints.append(build_constraint("matrix_type", "==", "ips", "", wish))
        elif wish == "sewing_operations_from_30":
            constraints.append(build_constraint("sewing_operations", ">=", "30", "", wish))
        elif wish == "shuttle_type_horizontal":
            constraints.append(build_constraint("shuttle_type", "==", "horizontal", "", wish))
        elif wish == "buttonhole_automatic":
            constraints.append(build_constraint("buttonhole", "==", "automatic", "", wish))
        elif wish == "speed_control":
            constraints.append(build_constraint("speed_control", "==", "true", "", wish))
        elif wish == "work_area_light":
            constraints.append(build_constraint("work_area_light", "==", "true", "", wish))
        elif wish == "power_from_1800_w":
            constraints.append(build_constraint("power", ">=", "1800", "w", wish))
        elif wish == "removable_panels":
            constraints.append(build_constraint("removable_panels", "==", "true", "", wish))
        elif wish == "nonstick_coating":
            constraints.append(build_constraint("nonstick_coating", "==", "true", "", wish))
        elif wish == "temperature_control":
            constraints.append(build_constraint("temperature_control", "==", "true", "", wish))
        elif wish == "grease_tray":
            constraints.append(build_constraint("grease_tray", "==", "true", "", wish))
        elif wish == "opens_180":
            constraints.append(build_constraint("opens_180", "==", "true", "", wish))
        elif wish == "smartphone_control":
            constraints.append(build_constraint("smartphone_control", "==", "true", "", wish))
        elif wish == "battery_capacity_from_4000_mah":
            constraints.append(build_constraint("battery_capacity", ">=", "4000", "mah", wish))
        elif wish == "auto_return_to_base":
            constraints.append(build_constraint("auto_return_to_base", "==", "true", "", wish))
        elif wish == "dustbin_easy_cleaning":
            constraints.append(build_constraint("dustbin_easy_cleaning", "==", "true", "", wish))
        elif wish == "good_navigation":
            constraints.append(build_constraint("good_navigation", "==", "true", "", wish))
        elif wish == "device_type_mfp":
            constraints.append(build_constraint("device_type", "==", "mfp", "", wish))
        elif wish == "print_technology_laser":
            constraints.append(build_constraint("print_technology", "==", "laser", "", wish))
        elif wish == "color_mode_monochrome":
            constraints.append(build_constraint("color_mode", "==", "monochrome", "", wish))
        elif wish == "wifi":
            constraints.append(build_constraint("wifi", "==", "true", "", wish))
        elif wish == "duplex_print":
            constraints.append(build_constraint("duplex_print", "==", "true", "", wish))
        elif wish == "scanner":
            constraints.append(build_constraint("scanner", "==", "true", "", wish))
        elif wish == "print_speed_from_20_ppm":
            constraints.append(build_constraint("print_speed", ">=", "20", "ppm", wish))
        elif wish == "refill_easy":
            constraints.append(build_constraint("refill_easy", "==", "true", "", wish))
        elif wish == "cheap_maintenance":
            constraints.append(build_constraint("cheap_maintenance", "==", "true", "", wish))
        elif wish == "resistance_system_magnetic":
            constraints.append(build_constraint("resistance_system", "==", "magnetic", "", wish))
        elif wish == "keyboard_type_magnetic":
            constraints.append(build_constraint("keyboard_type", "==", "magnetic", "", wish))
        elif wish == "keyboard_format_75_80":
            constraints.append(build_constraint("keyboard_format", "==", "75_80", "", wish))
        elif wish == "max_user_weight_from_120_kg":
            constraints.append(build_constraint("max_user_weight", ">=", "120", "kg", wish))
        elif wish == "seat_adjustment":
            constraints.append(build_constraint("seat_adjustment", "==", "true", "", wish))
        elif wish == "display":
            constraints.append(build_constraint("display", "==", "true", "", wish))
        elif wish == "pulse_measurement":
            constraints.append(build_constraint("pulse_measurement", "==", "true", "", wish))
        elif wish == "resistance_levels_from_8":
            constraints.append(build_constraint("resistance_levels", ">=", "8", "", wish))
        elif wish == "stable_construction":
            constraints.append(build_constraint("stable_construction", "==", "true", "", wish))
        elif wish == "machine_type_automatic":
            constraints.append(build_constraint("machine_type", "==", "automatic", "", wish))
        elif wish == "cappuccinator":
            constraints.append(build_constraint("cappuccinator", "==", "true", "", wish))
        elif wish == "pressure_from_15_bar":
            constraints.append(build_constraint("pressure", ">=", "15", "bar", wish))
        elif wish == "built_in_grinder":
            constraints.append(build_constraint("built_in_grinder", "==", "true", "", wish))
        elif wish == "strength_adjustment":
            constraints.append(build_constraint("strength_adjustment", "==", "true", "", wish))
        elif wish == "portion_volume_adjustment":
            constraints.append(build_constraint("portion_volume_adjustment", "==", "true", "", wish))
        elif wish == "self_cleaning":
            constraints.append(build_constraint("self_cleaning", "==", "true", "", wish))
        elif wish == "network_5g":
            constraints.append(build_constraint("network", "==", "5g", "", wish))
        elif wish == "nfc":
            constraints.append(build_constraint("nfc", "==", "true", "", wish))
        elif wish == "fast_charge":
            constraints.append(build_constraint("fast_charge", "==", "true", "", wish))
        elif wish == "waterproof_ip68":
            constraints.append(build_constraint("protection", ">=", "ip68", "", wish))
        elif wish == "2024_year":
            constraints.append(build_constraint("year", "==", "2024", "", wish))
        elif wish == "year_from_2024":
            constraints.append(build_constraint("year", ">=", "2024", "", wish))
        elif wish == "weight_up_to_2.3_kg":
            constraints.append(build_constraint("weight", "<=", "2.3", "kg", wish))
        elif wish == "weight_up_to_2.5_kg":
            constraints.append(build_constraint("weight", "<=", "2.5", "kg", wish))
        elif wish == "matte_screen":
            constraints.append(build_constraint("screen_finish", "==", "matte", "", wish))
        elif wish == "cooling_system_no_frost":
            constraints.append(build_constraint("cooling_system", "==", "no_frost", "", wish))
        elif wish == "freezer_position_bottom":
            constraints.append(build_constraint("freezer_position", "==", "bottom", "", wish))
        elif wish == "inverter_compressor":
            constraints.append(build_constraint("inverter_compressor", "==", "true", "", wish))
        elif wish == "width_up_to_60_cm":
            constraints.append(build_constraint("width", "<=", "60", "cm", wish))
        elif wish == "volume_from_300_l":
            constraints.append(build_constraint("volume", ">=", "300", "l", wish))
        elif wish == "energy_class_not_lower_than_a":
            constraints.append(build_constraint("energy_class", ">=", "a", "", wish))
        elif wish == "side_by_side":
            constraints.append(build_constraint("layout", "==", "side_by_side", "", wish))
        elif wish == "dryer":
            constraints.append(build_constraint("dryer", "==", "true", "", wish))
        elif wish == "wet_cleaning":
            constraints.append(build_constraint("wet_cleaning", "==", "true", "", wish))
        elif wish == "mapping":
            constraints.append(build_constraint("mapping", "==", "true", "", wish))
    return merge_constraints_tuples(tuple(constraints))


def infer_product_type_and_query(value: str) -> tuple[str, str]:
    normalized = normalize_token(value)
    plain_text = normalize_search_query_value(value)
    for product_type, pattern, query in PRODUCT_TYPE_QUERY_HINT_PATTERNS:
        if pattern.search(plain_text):
            return product_type, query
    for product_type, query in PRODUCT_TYPE_QUERY_MAP.items():
        query_token = normalize_token(query)
        if tokens_match_query_hint(normalized, product_type) or tokens_match_query_hint(normalized, query_token):
            return product_type, query
        if query_token in normalized:
            return product_type, query
    return normalized or "unknown", normalize_search_query_value(value)


def parse_optional_int_string(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_numeric_metric_value(value: str) -> int | None:
    cleaned = normalize_token(value).replace("_", "").replace(" ", "").replace(",", ".")
    match = re.search(r"(\d+(?:\.\d+)?)", cleaned)
    if not match:
        return None
    number = float(match.group(1))
    return int(number) if number.is_integer() else int(number)


def normalize_token(value: str) -> str:
    return value.strip().casefold().replace(" ", "_")


def normalize_merged_wishes(wishes: tuple[str, ...]) -> tuple[str, ...]:
    merged = merge_wish_tuples(wishes)
    filtered = [wish for wish in merged]
    if "matrix_type_amoled" in filtered and "amoled_display" in filtered:
        filtered = [wish for wish in filtered if wish != "amoled_display"]
    if "matrix_type_oled" in filtered and "oled" in filtered:
        filtered = [wish for wish in filtered if wish != "oled"]
    if "matrix_type_ips" in filtered and "ips" in filtered:
        filtered = [wish for wish in filtered if wish != "ips"]
    if "storage_from_256_gb" in filtered and "256gb_storage" in filtered:
        filtered = [wish for wish in filtered if wish != "256gb_storage"]
    if "ssd_from_512_gb" in filtered:
        filtered = [wish for wish in filtered if wish not in {"ssd", "storage_from_256_gb", "256gb_storage"}]
    return tuple(filtered)


def tokens_match_query_hint(source: str, target: str) -> bool:
    if source == target:
        return True
    source_parts = [part for part in source.split("_") if part]
    target_parts = [part for part in target.split("_") if part]
    source_compact = "".join(source_parts)
    target_compact = "".join(target_parts)
    if source_compact and source_compact == target_compact:
        return True
    if source_parts and target_parts:
        if all(part in source_parts for part in target_parts):
            return True
        if all(part in target_parts for part in source_parts):
            return True
    if source_compact and target_compact:
        common_prefix_length = len(os.path.commonprefix([source_compact, target_compact]))
        if common_prefix_length >= 6 and min(len(source_compact), len(target_compact)) - common_prefix_length <= 2:
            return True
    return False


def detect_brand(text: str) -> str:
    lowered = text.casefold()
    found: list[str] = []
    for brand, aliases in BRAND_ALIASES.items():
        variants = (brand, *aliases)
        if any(re.search(rf"(?<!\w){re.escape(variant)}(?!\w)", lowered, re.IGNORECASE) for variant in variants):
            found.append(brand)
    unique = list(dict.fromkeys(found))
    if len(unique) != 1:
        return ""
    return unique[0]


def build_normalized_request_search_url(request: NormalizedSearchRequest) -> str:
    return normalize_dns_url(request.query, price=normalize_price_pair(request.price_min, request.price_max))


def build_preselected_filters(
    normalized_request: NormalizedSearchRequest,
    filters_map: dict[str, object],
) -> list[dict[str, object]]:
    return build_preselected_filters_and_coverage(normalized_request, filters_map)[0]


def build_preselected_filters_and_coverage(
    normalized_request: NormalizedSearchRequest,
    filters_map: dict[str, object],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    available_filters = filters_map.get("filters", [])
    if not isinstance(available_filters, list):
        return [], []
    selections: list[dict[str, object]] = []
    coverage: list[dict[str, object]] = []
    if normalized_request.price_min is not None or normalized_request.price_max is not None:
        if any(str(item.get("id", "")) == "price" for item in available_filters if isinstance(item, dict)):
            selections.append({"id": "price", "min": normalized_request.price_min or 0, "max": normalized_request.price_max})
    if normalized_request.brand:
        brand_selection = match_brand_filter(available_filters, normalized_request.brand)
        if brand_selection is not None:
            selections.append(brand_selection)
    candidate_packets = build_constraint_candidate_packets(normalized_request, filters_map)
    for packet in candidate_packets:
        audit_item, selected_filters = preselect_constraint_packet(packet)
        coverage.append(audit_item)
        if selected_filters is not None:
            selections = merge_selected_filters(selections, selected_filters)
    return deduplicate_filter_list(selections), coverage


def build_constraint_candidate_packets(
    normalized_request: NormalizedSearchRequest,
    filters_map: dict[str, object],
) -> list[dict[str, object]]:
    available_filters = filters_map.get("filters", [])
    if not isinstance(available_filters, list):
        return []
    packets: list[dict[str, object]] = []
    effective_constraints = request_intent_signals(normalized_request)
    for constraint in effective_constraints:
        scored_candidates: list[tuple[int, dict[str, object]]] = []
        for filter_block in available_filters:
            if not isinstance(filter_block, dict):
                continue
            if is_disallowed_model_filter(filter_block, constraint):
                continue
            score = score_filter_candidate(constraint, filter_block)
            if score <= 0:
                continue
            scored_candidates.append((score, compact_filter_candidate(constraint, filter_block)))
        scored_candidates.sort(key=lambda item: (-item[0], str(item[1].get("id", ""))))
        packets.append(
            {
                "intent_signal": constraint_payload(constraint),
                "constraint": constraint_payload(constraint),
                "candidate_filters": [item[1] for item in scored_candidates[:5]],
            }
        )
    return packets


def coverage_requires_patch(coverage: list[dict[str, object]]) -> bool:
    if not coverage:
        return True
    for item in coverage:
        if not isinstance(item, dict):
            return True
        if str(item.get("status", "")) != "covered":
            return True
        if float(item.get("confidence", 0.0) or 0.0) < 0.9:
            return True
    return False


def problematic_constraint_packets(
    candidate_packets: list[dict[str, object]],
    coverage: list[dict[str, object]],
) -> list[dict[str, object]]:
    problematic_keys = {
        str(item.get("constraint_key", ""))
        for item in coverage
        if isinstance(item, dict) and str(item.get("status", "")) != "covered"
    }
    return [
        packet
        for packet in candidate_packets
        if isinstance(packet, dict)
        and (
            (
                isinstance(packet.get("intent_signal"), dict)
                and str(packet["intent_signal"].get("key", "")) in problematic_keys
            )
            or (
                isinstance(packet.get("constraint"), dict)
                and str(packet["constraint"].get("key", "")) in problematic_keys
            )
        )
    ]


def constraint_payload(constraint: NormalizedConstraint) -> dict[str, object]:
    return {
        "key": constraint.key,
        "op": constraint.op,
        "value": constraint.value,
        "unit": constraint.unit,
        "source_text": constraint.source_text,
        "weight": getattr(constraint, "weight", 1.0),
    }


def constraint_allows_model_filter(constraint: NormalizedConstraint) -> bool:
    return normalize_token(constraint.key) in {"model", "line"}


def is_model_filter_name(value: str) -> bool:
    return normalize_token(value) in MODEL_FILTER_TOKENS


def is_disallowed_model_filter(filter_block: dict[str, object], constraint: NormalizedConstraint) -> bool:
    if constraint_allows_model_filter(constraint):
        return False
    return is_model_filter_name(str(filter_block.get("name", "")))


def filter_semantic_gate_score(constraint: NormalizedConstraint, filter_block: dict[str, object]) -> int:
    key = normalize_token(constraint.key)
    tokens = tuple(
        token
        for token in (normalize_token(item) for item in CONSTRAINT_KEY_SYNONYMS.get(key, ()))
        if token
    )
    if not tokens:
        return 0
    name = normalize_token(str(filter_block.get("name", "")))
    group = normalize_token(str(filter_block.get("group", "")))
    values = filter_block.get("values", [])
    value_names = [
        normalize_token(str(item.get("name", "")))
        for item in values
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    ]
    score = 0
    if any(token in name for token in tokens):
        score += 4
    if any(token in group for token in tokens):
        score += 3
    if any(any(token in value_name for token in tokens) for value_name in value_names):
        score += 2
    return score


def boolean_filter_matches_constraint(constraint: NormalizedConstraint, filter_block: dict[str, object]) -> bool:
    key = normalize_token(constraint.key)
    if key not in BOOLEAN_CONSTRAINT_KEYS:
        return False
    name = normalize_token(str(filter_block.get("name", "")))
    group = normalize_token(str(filter_block.get("group", "")))
    values = filter_block.get("values", [])
    value_names = [
        normalize_token(str(item.get("name", "")))
        for item in values
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    ]
    deny_tokens = BOOLEAN_FILTER_NAME_DENYLISTS.get(key, ())
    if any(token in name or token in group or any(token in value_name for value_name in value_names) for token in deny_tokens):
        return False
    allow_tokens = BOOLEAN_FILTER_NAME_ALLOWLISTS.get(key, CONSTRAINT_KEY_SYNONYMS.get(key, ()))
    if not allow_tokens:
        return False
    return any(token in name or token in group or any(token in value_name for value_name in value_names) for token in allow_tokens)


def score_filter_candidate(constraint: NormalizedConstraint, filter_block: dict[str, object]) -> int:
    key = normalize_token(constraint.key)
    name = normalize_token(str(filter_block.get("name", "")))
    group = normalize_token(str(filter_block.get("group", "")))
    score = 0
    semantic_score = 0
    values = filter_block.get("values", [])
    value_names = [
        normalize_token(str(item.get("name", "")))
        for item in values
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    ]
    if key == "ram":
        if any(token in name for token in ("оператив", "озу")):
            score += 18
            semantic_score += 18
        if any(token in name for token in ("встроен", "слот", "карты_памяти", "максимальный_объем_карты")):
            score -= 14
    if key == "ram" and any(token in name for token in ("виртуаль", "расширен")):
        score -= 20
    if key == "storage":
        if any(token in name for token in ("встроен", "накопител", "постоян")):
            score += 18
            semantic_score += 18
        if any(token in name for token in ("оператив", "озу")):
            score -= 14
    if key in BOOLEAN_CONSTRAINT_KEYS and not boolean_filter_matches_constraint(constraint, filter_block):
        return 0
    for synonym in CONSTRAINT_KEY_SYNONYMS.get(key, (key,)):
        token = normalize_token(synonym)
        if token and token in name:
            score += 12
            semantic_score += 12
        elif token and token in group:
            score += 6
            semantic_score += 6
    if key == "refresh_rate":
        if any(token in name or token in group for token in ("дискретизац", "сенсор", "ярк", "цвет", "камер", "оптик", "объектив")) and not any(
            token in name or token in group for token in ("частот", "герц", "гц", "hz", "экран", "дисплей", "матриц", "панел")
        ):
            score -= 40
        if any(token in name or token in group for token in ("процессор", "cpu", "ядро", "чип")):
            score -= 24
        if any(token in name or token in group for token in ("экран", "дисплей", "матриц", "панел")):
            score += 8
    if key == "matrix_type":
        if any(token in name or token in group for token in ("камер", "оптик", "объектив", "передач", "связ", "ярк", "цвет", "разрешен", "частот")) and not any(
            token in name or token in group for token in ("матриц", "матрица", "тип экрана", "технолог", "панел", "panel", "amoled", "oled", "ips", "va", "qled")
        ):
            score -= 40
        if any(token in name or token in group for token in ("разрешен", "частот", "ярк", "цвет", "гц", "hz", "ppi", "dpi")):
            score -= 22
        if any(token in name or token in group for token in ("матриц", "матрица", "технолог", "панел", "panel")):
            score += 20
            semantic_score += 20
    if constraint.unit:
        for unit_token in CONSTRAINT_UNITS.get(key, (constraint.unit,)):
            normalized_unit = normalize_token(unit_token)
            if normalized_unit and (normalized_unit in name or normalized_unit in group):
                score += 4
                break
    unit_compatible = filter_matches_constraint_unit(constraint, filter_block)
    if isinstance(values, list) and values:
        if key in BOOLEAN_CONSTRAINT_KEYS and any(is_positive_filter_value_name(str(item.get("name", ""))) for item in values if isinstance(item, dict)):
            score += 8
        if key == "matrix_type":
            enum_tokens = enum_candidate_tokens(constraint)
            if any(any(token in value_name for token in enum_tokens) for value_name in value_names):
                score += 12
            if any(value_name in {"amoled", "oled", "ips", "va", "qled"} for value_name in value_names):
                score += 6
            if "подробно" in name and not any(value_name in {"amoled", "oled", "ips", "va", "qled"} for value_name in value_names):
                score -= 4
        elif key == "gpu":
            if any(
                gpu_value_matches_constraint(constraint, normalize_token(str(item.get("name", ""))).replace("-", "_"))
                for item in values
                if isinstance(item, dict)
            ):
                score += 18
        elif key == "network":
            if any("5g" in normalize_token(str(item.get("name", ""))) for item in values if isinstance(item, dict)):
                score += 10
        elif key == "protection":
            expected = normalize_token(str(constraint.value))
            if any(expected in normalize_token(str(item.get("name", ""))) for item in values if isinstance(item, dict)):
                score += 10
        elif key == "cooling_system":
            if any("no_frost" in normalize_token(str(item.get("name", ""))).replace("-", "_") for item in values if isinstance(item, dict)):
                score += 10
        elif key == "energy_class":
            if any(normalize_energy_class(str(item.get("name", ""))) for item in values if isinstance(item, dict)):
                score += 8
        elif key in NUMERIC_CONSTRAINT_KEYS:
            numeric_values = [parse_first_number(str(item.get("name", ""))) for item in values if isinstance(item, dict)]
            numeric_values = [item for item in numeric_values if item is not None]
            if numeric_values and constraint_numeric_value(constraint) is not None and unit_compatible and semantic_score > 0:
                score += 8
                if constraint.op == ">=" and any(item >= constraint_numeric_value(constraint) for item in numeric_values):
                    score += 8
                if constraint.op == "<=" and any(item <= constraint_numeric_value(constraint) for item in numeric_values):
                    score += 8
                if constraint.op == "==" and any(abs(item - constraint_numeric_value(constraint)) < 0.001 for item in numeric_values):
                    score += 8
    range_info = filter_block.get("range", {})
    if key in NUMERIC_CONSTRAINT_KEYS and isinstance(range_info, dict) and range_info and constraint_numeric_value(constraint) is not None and unit_compatible and semantic_score > 0:
        score += 6
    return score


def filter_matches_constraint_unit(constraint: NormalizedConstraint, filter_block: dict[str, object]) -> bool:
    key = normalize_token(constraint.key)
    if not constraint.unit or key == "year":
        return True
    expected_units = {
        normalize_token(item)
        for item in CONSTRAINT_UNITS.get(key, (constraint.unit,))
        if normalize_token(item)
    }
    if not expected_units:
        return True
    probes = [
        str(filter_block.get("name", "")),
        str(filter_block.get("group", "")),
    ]
    values = filter_block.get("values", [])
    if isinstance(values, list):
        probes.extend(str(item.get("name", "")) for item in values[:5] if isinstance(item, dict))
    candidate_units = {detect_unit_from_text(item) for item in probes if detect_unit_from_text(item)}
    if not candidate_units:
        return False
    return bool(candidate_units & expected_units)


def compact_filter_candidate(constraint: NormalizedConstraint, filter_block: dict[str, object]) -> dict[str, object]:
    values = filter_block.get("values", [])
    compact_values = compact_constraint_values(constraint, values if isinstance(values, list) else [])
    candidate = {
        "id": str(filter_block.get("id", "")),
        "name": str(filter_block.get("name", "")),
        "group": str(filter_block.get("group", "")),
        "type": str(filter_block.get("type", "")),
        "values": compact_values,
    }
    if isinstance(values, list):
        candidate["total_values_count"] = len(values)
    if isinstance(filter_block.get("range"), dict):
        candidate["range"] = dict(filter_block.get("range", {}))
    return candidate


def compact_constraint_values(constraint: NormalizedConstraint, values: list[object]) -> list[dict[str, object]]:
    if not values:
        return []
    key = normalize_token(constraint.key)
    if key in BOOLEAN_CONSTRAINT_KEYS:
        return [
            compact_value_entry(value, include_numeric=False, include_unit=False)
            for value in values
            if isinstance(value, dict) and is_positive_filter_value_name(str(value.get("name", "")))
        ][:3]
    if key in {"matrix_type", "network", "protection", "cooling_system", "screen_finish", "layout", "keyboard_type", "keyboard_format", "resolution", "navigation", "buttonhole", "shuttle_type"}:
        selected_values = select_enum_values_for_constraint(constraint, values)
        selected_ids = {str(item.get("id", "")) for item in selected_values if isinstance(item, dict)}
        matched = [
            compact_value_entry(value, include_numeric=False, include_unit=False)
            for value in values
            if isinstance(value, dict) and str(value.get("id", "")) in selected_ids
        ]
        if key == "matrix_type" and normalize_token(str(constraint.value)) == "amoled":
            return matched
        return matched[:5]
    target = constraint_numeric_value(constraint)
    if target is None:
        return [compact_value_entry(value, include_numeric=False, include_unit=False) for value in values if isinstance(value, dict)][:5]
    matched: list[tuple[float, dict[str, object]]] = []
    below: list[tuple[float, dict[str, object]]] = []
    above: list[tuple[float, dict[str, object]]] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        numeric = parse_first_number(str(value.get("name", "")))
        if numeric is None:
            continue
        entry = compact_value_entry(value)
        distance = abs(numeric - target)
        if constraint.op == ">=":
            if numeric >= target:
                matched.append((numeric, entry))
            else:
                below.append((distance, entry))
        elif constraint.op == "<=":
            if numeric <= target:
                matched.append((numeric, entry))
            else:
                above.append((distance, entry))
        elif abs(numeric - target) < 0.001:
            matched.append((numeric, entry))
        elif numeric < target:
            below.append((distance, entry))
        else:
            above.append((distance, entry))
    if constraint.op == ">=" and matched:
        matched.sort(key=lambda item: item[0])
        below.sort(key=lambda item: item[0])
        return [item[1] for item in matched] + [item[1] for item in below[:2]]
    if constraint.op == "<=" and matched:
        matched.sort(key=lambda item: item[0])
        above.sort(key=lambda item: item[0])
        return [item[1] for item in matched] + [item[1] for item in above[:2]]
    if matched:
        matched.sort(key=lambda item: item[0])
        return [item[1] for item in matched]
    decorated = below + above
    decorated.sort(key=lambda item: item[0])
    return [item[1] for item in decorated[:7]]


def compact_value_entry(
    value: dict[str, object],
    *,
    include_numeric: bool = True,
    include_unit: bool = True,
) -> dict[str, object]:
    name = str(value.get("name", ""))
    entry: dict[str, object] = {
        "id": str(value.get("id", "")),
        "name": name,
    }
    if include_numeric:
        entry["numeric"] = parse_first_number(name)
    if include_unit:
        entry["unit"] = detect_unit_from_text(name)
    return entry


def enum_candidate_tokens(constraint: NormalizedConstraint) -> tuple[str, ...]:
    key = normalize_token(constraint.key)
    value = normalize_token(str(constraint.value)).replace("-", "_")
    return tuple(normalize_token(item).replace("-", "_") for item in ENUM_EQUIVALENTS.get(key, {}).get(value, (value,)))


def constraint_numeric_value(constraint: NormalizedConstraint) -> float | None:
    return parse_first_number(str(constraint.value))


def preselect_constraint_packet(packet: dict[str, object]) -> tuple[dict[str, object], list[dict[str, object]] | None]:
    constraint_dict = packet.get("constraint", {})
    if not isinstance(constraint_dict, dict):
        return {"constraint_key": "", "status": "unverifiable", "confidence": 0.0, "reason": "invalid constraint payload"}, None
    constraint = NormalizedConstraint(
        key=normalize_token(str(constraint_dict.get("key", ""))),
        op=str(constraint_dict.get("op", "")),
        value=str(constraint_dict.get("value", "")),
        unit=normalize_token(str(constraint_dict.get("unit", ""))),
        source_text=str(constraint_dict.get("source_text", "")),
    )
    candidates = packet.get("candidate_filters", [])
    if not isinstance(candidates, list) or not candidates:
        return {
            "constraint_key": constraint.key,
            "status": "unverifiable",
            "confidence": 0.0,
            "reason": "No technical DNS filter found.",
        }, None
    selected_filters = select_filters_for_constraint(constraint, candidates)
    if not selected_filters:
        return {
            "constraint_key": constraint.key,
            "status": "uncovered",
            "confidence": 0.0,
            "reason": "Candidate filters found, but deterministic preselect could not map values.",
        }, None
    status = "covered"
    confidence = 0.96
    reason = ""
    if any(is_model_filter_name(str(selected.get("name", ""))) for selected in selected_filters):
        status = "weak_covered"
        confidence = 0.2
        reason = "Model filter is not allowed for technical constraints."
    elif constraint.key == "matrix_type" and normalize_token(str(constraint.value)) == "amoled":
        selected_values = [
            normalize_token(str(item.get("name", "")))
            for selected in selected_filters
            for item in selected.get("values", [])
            if isinstance(item, dict) and str(item.get("name", "")).strip()
        ]
        amoled_family = [value for value in selected_values if "amoled" in value or "oled" in value]
        broad_markers = {"amoled", "amoled/oled", "oled/amoled", "oled"}
        if len(amoled_family) == 1 and amoled_family[0] not in broad_markers:
            status = "over_narrowed"
            confidence = 0.55
            reason = "Selected only a narrow AMOLED subtype."
        elif amoled_family:
            reason = "Selected broad AMOLED subtype set."
    if any(selection_wrong_for_constraint(constraint, selected) for selected in selected_filters):
        status = "wrong"
        confidence = 0.0
        reason = "Selected filter contradicts constraint."
    return {
        "constraint_key": constraint.key,
        "status": status,
        "confidence": confidence,
        "selected_filter_ids": [str(selected.get("id", "")) for selected in selected_filters],
        "selected_values": [
            str(item.get("name", ""))
            for selected in selected_filters
            for item in selected.get("values", [])
            if isinstance(item, dict)
        ],
        "reason": reason,
    }, selected_filters


def select_filters_for_constraint(constraint: NormalizedConstraint, candidates: list[object]) -> list[dict[str, object]]:
    if normalize_token(constraint.key) == "cooling_system" and normalize_token(str(constraint.value)) == "no_frost":
        selected: list[dict[str, object]] = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            matched = deterministic_filter_selection(constraint, candidate)
            if matched is None:
                continue
            if isinstance(matched, list):
                selected.extend(matched)
            else:
                selected.append(matched)
        return deduplicate_filter_list(selected)
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        selected = deterministic_filter_selection(constraint, candidate)
        if selected is None:
            continue
        if isinstance(selected, list):
            return selected
        return [selected]
    return []


def deterministic_filter_selection(constraint: NormalizedConstraint, filter_block: dict[str, object]) -> dict[str, object] | list[dict[str, object]] | None:
    block_id = str(filter_block.get("id", ""))
    block_name = str(filter_block.get("name", ""))
    block_type = str(filter_block.get("type", ""))
    range_info = filter_block.get("range", {})
    if (
        normalize_token(constraint.key) in NUMERIC_CONSTRAINT_KEYS
        and isinstance(range_info, dict)
        and range_info
        and constraint_numeric_value(constraint) is not None
        and constraint.op in {">=", "<=", "=="}
    ):
        if constraint.op == ">=":
            return {"id": block_id, "name": block_name, "min": constraint_numeric_value(constraint), "max": range_info.get("max")}
        if constraint.op == "<=":
            minimum = range_info.get("min")
            if minimum in {"", None}:
                minimum = 0
            return {"id": block_id, "name": block_name, "min": minimum, "max": constraint_numeric_value(constraint)}
        return {"id": block_id, "name": block_name, "min": constraint_numeric_value(constraint), "max": constraint_numeric_value(constraint)}
    values = filter_block.get("values", [])
    if not isinstance(values, list) or not values:
        if block_type == "toggle" and constraint.key in BOOLEAN_CONSTRAINT_KEYS and normalize_token(str(constraint.value)) == "true":
            if not boolean_filter_matches_constraint(constraint, filter_block):
                return None
            return {"id": block_id, "name": block_name, "enabled": True}
        return None
    if constraint.key in BOOLEAN_CONSTRAINT_KEYS:
        if not boolean_filter_matches_constraint(constraint, filter_block):
            return None
        matched = [value_pick(value) for value in values if isinstance(value, dict) and is_positive_filter_value_name(str(value.get("name", "")))]
        return {"id": block_id, "name": block_name, "values": matched[:1]} if matched else None
    if constraint.key in {"matrix_type", "network", "protection", "cooling_system", "screen_finish", "energy_class", "gpu", "layout", "keyboard_type", "keyboard_format", "resolution", "navigation", "freezer_position", "inverter_compressor", "buttonhole", "shuttle_type"}:
        matched = select_enum_values_for_constraint(constraint, values)
        return {"id": block_id, "name": block_name, "values": matched} if matched else None
    numeric_target = constraint_numeric_value(constraint)
    if numeric_target is None:
        return None
    matched_values: list[dict[str, str]] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        lower_bound, upper_bound = filter_value_bounds(str(value.get("name", "")))
        if lower_bound is None and upper_bound is None:
            continue
        if constraint.op == ">=" and lower_bound is not None and lower_bound >= numeric_target:
            matched_values.append(value_pick(value))
        elif constraint.op == "<=" and upper_bound is not None and upper_bound <= numeric_target:
            matched_values.append(value_pick(value))
        elif constraint.op == "==" and lower_bound is not None and upper_bound is not None and lower_bound <= numeric_target <= upper_bound:
            matched_values.append(value_pick(value))
    if matched_values:
        return {"id": block_id, "name": block_name, "values": matched_values}
    return None


def value_pick(value: dict[str, object]) -> dict[str, str]:
    return {"id": str(value.get("id", "")), "name": str(value.get("name", ""))}


def select_enum_values_for_constraint(constraint: NormalizedConstraint, values: list[object]) -> list[dict[str, str]]:
    key = normalize_token(constraint.key)
    expected_tokens = enum_candidate_tokens(constraint)
    matched: list[dict[str, str]] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        value_name = normalize_token(str(value.get("name", ""))).replace("-", "_")
        if key == "energy_class":
            if energy_class_matches_constraint(constraint, value_name):
                matched.append(value_pick(value))
            continue
        if key == "gpu":
            if gpu_value_matches_constraint(constraint, value_name):
                matched.append(value_pick(value))
            continue
        if key == "freezer_position":
            if any(token in value_name for token in ("снизу", "bottom")):
                matched.append(value_pick(value))
            continue
        if any(token in value_name for token in expected_tokens):
            matched.append(value_pick(value))
    if key == "screen_finish" and normalize_token(str(constraint.value)) == "matte":
        exact_matte = [item for item in matched if "матов" in normalize_token(item["name"]) or "matte" in normalize_token(item["name"])]
        if exact_matte:
            return exact_matte
    if key == "matrix_type" and normalize_token(str(constraint.value)) == "amoled":
        amoled_family = [item for item in matched if "amoled" in normalize_token(item["name"])]
        if amoled_family:
            return amoled_family
    return matched


def selection_wrong_for_constraint(constraint: NormalizedConstraint, selected_filter: dict[str, object]) -> bool:
    if normalize_token(constraint.key) in {"resolution", "keyboard_format", "keyboard_type"}:
        return False
    values = selected_filter.get("values", [])
    if not isinstance(values, list) or not values:
        return False
    numeric_target = constraint_numeric_value(constraint)
    if numeric_target is None:
        return False
    bounds = [filter_value_bounds(str(item.get("name", ""))) for item in values if isinstance(item, dict)]
    if not any(lower is not None or upper is not None for lower, upper in bounds):
        return False
    if constraint.op == ">=":
        return any(lower is not None and lower < numeric_target for lower, _upper in bounds)
    if constraint.op == "<=":
        return any(upper is not None and upper > numeric_target for _lower, upper in bounds)
    if constraint.op == "==":
        return any(not (lower is not None and upper is not None and lower <= numeric_target <= upper) for lower, upper in bounds)
    return False


def is_positive_filter_value_name(value_name: str) -> bool:
    normalized = normalize_token(value_name)
    return normalized in {"есть", "да", "true", "1", "поддерживается"} or any(
        token in normalized for token in ("5g", "nfc", "fast", "wireless", "amoled", "oled", "no_frost", "led", "светодиод", "бесступенчат", "ступенчат")
    )


def detect_unit_from_text(value_name: str) -> str:
    normalized = normalize_token(value_name)
    for unit in ("гц", "hz", "гб", "gb", "тб", "tb", "кг", "kg", "см", "cm", "мм", "mm", "л", "l", "мах", "mah", "ватт", "w", "вт", "bar", "ppm", "ops"):
        if unit in normalized:
            return unit
    return ""


def filter_value_bounds(value_name: str) -> tuple[float | None, float | None]:
    normalized = normalize_token(value_name).replace('"', "")
    if "и_более" in normalized:
        lower = parse_first_number(normalized)
        return lower, None
    if "менее" in normalized:
        upper = parse_first_number(normalized)
        return None, max(0.0, upper - 0.001) if upper is not None else None
    numbers = NUMERIC_VALUE_RE.findall(normalized)
    if not numbers:
        return None, None
    if len(numbers) == 1:
        value = parse_first_number(normalized)
        return value, value
    try:
        return float(numbers[0].replace(",", ".")), float(numbers[1].replace(",", "."))
    except ValueError:
        return None, None


def normalize_energy_class(value: str) -> str:
    normalized = normalize_token(value).replace("_", "")
    match = re.search(r"a\+{0,3}", normalized)
    return match.group(0) if match is not None else ""


def energy_class_matches_constraint(constraint: NormalizedConstraint, value_name: str) -> bool:
    expected = normalize_energy_class(str(constraint.value))
    actual = normalize_energy_class(value_name)
    if not expected or not actual:
        return False
    ordering = {"a": 1, "a+": 2, "a++": 3, "a+++": 4}
    if constraint.op == ">=":
        return ordering.get(actual, 0) >= ordering.get(expected, 0)
    return actual == expected


def gpu_value_matches_constraint(constraint: NormalizedConstraint, value_name: str) -> bool:
    if normalize_token(str(constraint.value)).startswith("rtx_4070") and constraint.op == ">=":
        return rtx_4070_or_higher_value_matches(value_name)
    expected = normalize_token(str(constraint.value))
    return expected in value_name


def match_brand_filter(available_filters: list[dict[str, object]], brand: str) -> dict[str, object] | None:
    aliases = {brand, *BRAND_ALIASES.get(brand, ())}
    for filter_block in available_filters:
        if not isinstance(filter_block, dict):
            continue
        block_id = str(filter_block.get("id", "")).casefold()
        block_name = str(filter_block.get("name", "")).casefold()
        if block_id != "brand" and "бренд" not in block_name:
            continue
        for value in filter_block.get("values", []):
            if not isinstance(value, dict):
                continue
            value_id = normalize_token(str(value.get("id", "")))
            value_name = normalize_token(str(value.get("name", "")))
            if value_id in aliases or value_name in aliases:
                return {"id": str(filter_block.get("id", "")), "name": str(filter_block.get("name", "")), "values": [{"id": str(value.get("id", "")), "name": str(value.get("name", ""))}]}
    return None


def match_wish_filter(available_filters: list[dict[str, object]], wish: str) -> dict[str, object] | None:
    canonical_wish = canonicalize_wish(wish)
    structured_selection = match_structured_wish_filter(available_filters, canonical_wish)
    if structured_selection is not None:
        return structured_selection
    if canonical_wish in STRUCTURED_ONLY_WISHES:
        return None
    phrases = WISH_ALIASES.get(canonical_wish, (canonical_wish.replace("_", " "),))
    for filter_block in available_filters:
        if not isinstance(filter_block, dict):
            continue
        values = filter_block.get("values", [])
        if not isinstance(values, list):
            continue
        matched_values: list[dict[str, str]] = []
        block_name = normalize_token(str(filter_block.get("name", "")))
        for value in values:
            if not isinstance(value, dict):
                continue
            value_name = normalize_token(str(value.get("name", "")))
            value_id = str(value.get("id", ""))
            if any(alias_matches_filter_text(value_name, normalize_token(phrase)) for phrase in phrases):
                matched_values.append({"id": value_id, "name": str(value.get("name", ""))})
        if not matched_values and any(alias_matches_filter_text(block_name, normalize_token(phrase)) for phrase in phrases):
            positive_value = first_positive_filter_value(values)
            if positive_value is not None:
                matched_values.append(positive_value)
        if matched_values:
            return {"id": str(filter_block.get("id", "")), "name": str(filter_block.get("name", "")), "values": matched_values}
    return None


def match_structured_wish_filter(available_filters: list[dict[str, object]], wish: str) -> dict[str, object] | None:
    if wish == "27_inch":
        return match_range_bucket_filter(available_filters, "диагональ_экрана", 27.0)
    if wish == "1440p":
        return match_named_filter_value(available_filters, "максимальное_разрешение", ("2560x1440",))
    if wish == "ips":
        return match_named_filter_value(available_filters, "тип_матрицы", ("ips",))
    if wish == "matrix_type_ips":
        return match_named_filter_value(available_filters, "тип_матрицы", ("ips",))
    if wish == "matrix_type_amoled":
        return match_named_filter_value(available_filters, "тип_матрицы", ("super_amoled", "dynamic_amoled", "amoled"))
    if wish == "matrix_type_oled":
        return match_named_filter_value(available_filters, "тип_матрицы", ("oled",))
    if wish == "matrix_type_va":
        return match_named_filter_value(available_filters, "тип_матрицы", ("va",))
    if wish == "matrix_type_qled":
        return match_named_filter_value(available_filters, "тип_матрицы", ("qled",))
    if wish == "height_adjustable":
        return match_named_filter_value(available_filters, "регулировка_по_высоте", ("есть", "да"))
    if wish == "12gb_ram":
        return match_min_numeric_filter_values(available_filters, "объем_оперативной_памяти", 12)
    if wish == "32gb_ram":
        return match_named_filter_value(available_filters, "объем_оперативной_памяти", ("32_гб", "32gb"))
    if wish == "storage_from_256_gb":
        return match_min_numeric_filter_values(available_filters, "объем_встроенной_памяти", 256)
    if wish == "240hz_screen":
        return match_named_filter_value(available_filters, "частота_обновления_экрана", ("240_гц", "240hz"))
    if wish == "refresh_rate_from_120hz":
        return match_min_numeric_filter_values(available_filters, "частота_обновления_экрана", 120)
    if wish == "refresh_rate_from_165hz":
        return match_min_numeric_filter_values(available_filters, "частота_обновления_экрана", 165)
    if wish == "weight_up_to_2.3_kg":
        return match_max_numeric_range_filter(available_filters, "вес", 2.3)
    if wish == "weight_up_to_2.5_kg":
        return match_max_numeric_range_filter(available_filters, "вес", 2.5)
    if wish == "matte_screen":
        return match_named_filter_value(available_filters, "покрытие_экрана", ("матовое", "антибликовое", "matte"))
    if wish == "rtx_4080":
        return match_named_filter_value(available_filters, "дискретной_видеокарты", ("rtx_4080", "geforce_rtx_4080"))
    if wish == "rtx_4070":
        return match_named_filter_value(available_filters, "дискретной_видеокарты", ("rtx_4070", "geforce_rtx_4070"))
    if wish == "rtx_4070_or_higher":
        return match_rtx_4070_or_higher_filter_values(available_filters)
    if wish == "2024_year":
        return match_named_filter_value(available_filters, "год_релиза", ("2024",))
    if wish == "year_from_2024":
        return match_min_numeric_filter_values(available_filters, "год_релиза", 2024)
    if wish == "network_5g":
        return match_named_filter_value(available_filters, "стандарт_связи", ("5g",))
    if wish == "fast_charge":
        return match_named_filter_value(available_filters, "быстрая_зарядка", ("есть", "да"))
    if wish == "wireless_charge":
        return match_named_filter_value(available_filters, "беспроводная_зарядка", ("есть", "да"))
    if wish == "waterproof_ip68":
        return match_named_filter_value(available_filters, "степень_защиты", ("ip68",))
    if wish == "waterproof_ip67":
        return match_named_filter_value(available_filters, "степень_защиты", ("ip67",))
    if wish == "cooling_system_no_frost":
        return match_all_named_filter_values(available_filters, "разморажив", ("no frost", "full no frost", "total no frost"))
    if wish == "freezer_position_bottom":
        return match_named_filter_value(available_filters, "морозильной_камеры", ("снизу", "bottom"))
    if wish == "inverter_compressor":
        return match_named_filter_value(available_filters, "инверторный_компрессор", ("есть", "да", "true", "инвертор"))
    return None


def match_min_numeric_filter_values(
    available_filters: list[dict[str, object]],
    filter_name_token: str,
    min_value: float,
) -> dict[str, object] | None:
    for filter_block in available_filters:
        if not isinstance(filter_block, dict):
            continue
        block_name = normalize_token(str(filter_block.get("name", "")))
        if filter_name_token not in block_name:
            continue
        values = filter_block.get("values", [])
        if not isinstance(values, list):
            continue
        matched_values: list[dict[str, str]] = []
        for value in values:
            if not isinstance(value, dict):
                continue
            value_name = normalize_token(str(value.get("name", "")))
            if filter_name_token == "дискретной_видеокарты" and "rtx" not in value_name:
                continue
            numeric_value = parse_first_number(value_name)
            if numeric_value is None or numeric_value < min_value:
                continue
            matched_values.append({"id": str(value.get("id", "")), "name": str(value.get("name", ""))})
        if matched_values:
            return {
                "id": str(filter_block.get("id", "")),
                "name": str(filter_block.get("name", "")),
                "values": matched_values,
            }
    return None


def match_rtx_4070_or_higher_filter_values(
    available_filters: list[dict[str, object]],
) -> dict[str, object] | None:
    for filter_block in available_filters:
        if not isinstance(filter_block, dict):
            continue
        block_name = normalize_token(str(filter_block.get("name", "")))
        if "дискретной_видеокарты" not in block_name:
            continue
        values = filter_block.get("values", [])
        if not isinstance(values, list):
            continue
        matched_values: list[dict[str, str]] = []
        for value in values:
            if not isinstance(value, dict):
                continue
            value_name = str(value.get("name", ""))
            if not rtx_4070_or_higher_value_matches(value_name):
                continue
            matched_values.append({"id": str(value.get("id", "")), "name": value_name})
        if matched_values:
            return {
                "id": str(filter_block.get("id", "")),
                "name": str(filter_block.get("name", "")),
                "values": matched_values,
            }
    return None


def match_named_filter_value(
    available_filters: list[dict[str, object]],
    filter_name_token: str,
    value_tokens: tuple[str, ...],
) -> dict[str, object] | None:
    for filter_block in available_filters:
        if not isinstance(filter_block, dict):
            continue
        block_name = normalize_token(str(filter_block.get("name", "")))
        if filter_name_token not in block_name:
            continue
        values = filter_block.get("values", [])
        if not isinstance(values, list):
            continue
        best_match: tuple[int, int, dict[str, object]] | None = None
        for value in values:
            if not isinstance(value, dict):
                continue
            value_name = normalize_token(str(value.get("name", "")))
            for token_index, token in enumerate(value_tokens):
                if token not in value_name:
                    continue
                exactness_rank = 0 if value_name == token else 1
                selection = {
                    "id": str(filter_block.get("id", "")),
                    "name": str(filter_block.get("name", "")),
                    "values": [{"id": str(value.get("id", "")), "name": str(value.get("name", ""))}],
                }
                candidate = (token_index, exactness_rank, selection)
                if best_match is None or candidate[:2] < best_match[:2]:
                    best_match = candidate
                break
        if best_match is not None:
            return best_match[2]
    return None


def match_all_named_filter_values(
    available_filters: list[dict[str, object]],
    filter_name_token: str,
    value_tokens: tuple[str, ...],
) -> list[dict[str, object]] | None:
    matches: list[dict[str, object]] = []
    for filter_block in available_filters:
        if not isinstance(filter_block, dict):
            continue
        block_name = normalize_token(str(filter_block.get("name", "")))
        if filter_name_token not in block_name:
            continue
        values = filter_block.get("values", [])
        if not isinstance(values, list):
            continue
        matched_values: list[dict[str, str]] = []
        for value in values:
            if not isinstance(value, dict):
                continue
            value_name = normalize_token(str(value.get("name", "")))
            if any(token in value_name for token in value_tokens):
                matched_values.append({"id": str(value.get("id", "")), "name": str(value.get("name", ""))})
        if matched_values:
            matches.append({"id": str(filter_block.get("id", "")), "name": str(filter_block.get("name", "")), "values": matched_values})
    return matches or None


def match_range_bucket_filter(
    available_filters: list[dict[str, object]],
    filter_name_token: str,
    target_value: float,
) -> dict[str, object] | None:
    for filter_block in available_filters:
        if not isinstance(filter_block, dict):
            continue
        block_name = normalize_token(str(filter_block.get("name", "")))
        if filter_name_token not in block_name:
            continue
        values = filter_block.get("values", [])
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, dict):
                continue
            if not range_bucket_contains_target(str(value.get("name", "")), target_value):
                continue
            return {
                "id": str(filter_block.get("id", "")),
                "name": str(filter_block.get("name", "")),
                "values": [{"id": str(value.get("id", "")), "name": str(value.get("name", ""))}],
            }
    return None


def match_max_numeric_range_filter(
    available_filters: list[dict[str, object]],
    filter_name_token: str,
    max_value: float,
) -> dict[str, object] | None:
    for filter_block in available_filters:
        if not isinstance(filter_block, dict):
            continue
        block_name = normalize_token(str(filter_block.get("name", "")))
        if filter_name_token not in block_name:
            continue
        range_info = filter_block.get("range", {})
        if not isinstance(range_info, dict):
            continue
        minimum = range_info.get("min")
        if minimum in {None, ""}:
            minimum = 0
        return {
            "id": str(filter_block.get("id", "")),
            "name": str(filter_block.get("name", "")),
            "min": minimum,
            "max": max_value,
        }
    return None


def match_max_range_bucket_filters(
    available_filters: list[dict[str, object]],
    filter_name_token: str,
    max_value: float,
) -> dict[str, object] | None:
    for filter_block in available_filters:
        if not isinstance(filter_block, dict):
            continue
        block_name = normalize_token(str(filter_block.get("name", "")))
        if filter_name_token not in block_name:
            continue
        values = filter_block.get("values", [])
        if not isinstance(values, list):
            continue
        matched_values: list[dict[str, str]] = []
        for value in values:
            if not isinstance(value, dict):
                continue
            bucket_upper = range_bucket_upper_bound(str(value.get("name", "")))
            if bucket_upper is None or bucket_upper > max_value:
                continue
            matched_values.append({"id": str(value.get("id", "")), "name": str(value.get("name", ""))})
        if matched_values:
            return {
                "id": str(filter_block.get("id", "")),
                "name": str(filter_block.get("name", "")),
                "values": matched_values,
            }
    return None


def range_bucket_contains_target(label: str, target_value: float) -> bool:
    normalized_label = normalize_token(label).replace('"', "")
    if "и_более" in normalized_label:
        lower_bound = parse_first_number(normalized_label)
        return lower_bound is not None and target_value >= lower_bound
    if "менее" in normalized_label:
        upper_bound = parse_first_number(normalized_label)
        return upper_bound is not None and target_value < upper_bound
    numbers = NUMERIC_VALUE_RE.findall(normalized_label)
    if len(numbers) < 2:
        return False
    lower_bound = float(numbers[0].replace(",", "."))
    upper_bound = float(numbers[1].replace(",", "."))
    return lower_bound <= target_value <= upper_bound


def range_bucket_upper_bound(label: str) -> float | None:
    normalized_label = normalize_token(label).replace('"', "")
    if "менее" in normalized_label:
        upper_bound = parse_first_number(normalized_label)
        if upper_bound is None:
            return None
        return max(0.0, upper_bound - 0.001)
    if "и_более" in normalized_label:
        return None
    numbers = NUMERIC_VALUE_RE.findall(normalized_label)
    if len(numbers) < 2:
        return None
    try:
        return float(numbers[1].replace(",", "."))
    except ValueError:
        return None


def first_positive_filter_value(values: list[object]) -> dict[str, str] | None:
    positive_tokens = ("есть", "да", "поддерживается", "5g", "nfc", "oled", "amoled")
    for value in values:
        if not isinstance(value, dict):
            continue
        value_name = str(value.get("name", "")).casefold()
        if any(token in value_name for token in positive_tokens):
            return {"id": str(value.get("id", "")), "name": str(value.get("name", ""))}
    return None


def merge_selected_filters(primary: list[dict[str, object]], secondary: list[dict[str, object]]) -> list[dict[str, object]]:
    merged: dict[str, dict[str, object]] = {}
    order: list[str] = []
    for collection in (secondary, primary):
        for item in collection:
            if not isinstance(item, dict):
                continue
            filter_id = str(item.get("id", "") or item.get("name", "")).strip()
            if not filter_id:
                continue
            if filter_id not in order:
                order.append(filter_id)
            merged[filter_id] = item
    return [merged[item_id] for item_id in order if item_id in merged]


def sanitize_selected_filters(
    selected_filters: list[dict[str, object]],
    normalized_request: NormalizedSearchRequest,
    preselected_filters: list[dict[str, object]],
) -> list[dict[str, object]]:
    preselected_ids = {
        str(item.get("id", "")).casefold()
        for item in preselected_filters
        if isinstance(item, dict) and str(item.get("id", "")).strip()
    }
    unresolved_wishes = unresolved_request_wishes(normalized_request, preselected_filters)
    result: list[dict[str, object]] = []
    for item in selected_filters:
        filter_id = str(item.get("id", "")).casefold()
        filter_name = str(item.get("name", "")).casefold()
        if filter_id in preselected_ids:
            result.append(item)
            continue
        if not normalized_request.brand and (filter_id == "brand" or "бренд" in filter_name):
            continue
        if filter_id == "price":
            if normalized_request.price_min is not None or normalized_request.price_max is not None:
                result.append(item)
            continue
        if normalized_request.brand and (filter_id == "brand" or "бренд" in filter_name):
            result.append(item)
            continue
        if any(selected_filter_matches_wish(item, wish) for wish in unresolved_wishes):
            result.append(item)
            continue
    return deduplicate_filter_list(result)


def ensure_request_price_filter(
    selected_filters: list[dict[str, object]],
    normalized_request: NormalizedSearchRequest,
) -> list[dict[str, object]]:
    """Keep explicit budget as a hard DNS URL constraint even when DNS map omits price."""

    if normalized_request.price_min is None and normalized_request.price_max is None:
        return selected_filters
    price_filter = {
        "id": "price",
        "min": normalized_request.price_min if normalized_request.price_min is not None else 0,
        "max": normalized_request.price_max,
    }
    without_price = [item for item in selected_filters if str(item.get("id", "")).casefold() != "price"]
    return [*without_price, price_filter]


def unresolved_request_wishes(
    normalized_request: NormalizedSearchRequest,
    preselected_filters: list[dict[str, object]],
) -> tuple[str, ...]:
    unresolved: list[str] = []
    for wish in normalized_request.wishes:
        if wish in NON_FILTERABLE_WISHES:
            continue
        if any(selected_filter_matches_wish(item, wish) for item in preselected_filters if isinstance(item, dict)):
            continue
        unresolved.append(wish)
    return tuple(unresolved)


def selected_filter_matches_wish(selected_filter: dict[str, object], wish: str) -> bool:
    canonical_wish = canonicalize_wish(wish)
    if canonical_wish in {"weight_up_to_2.3_kg", "weight_up_to_2.5_kg"}:
        filter_name = normalize_token(str(selected_filter.get("name", "")))
        filter_id = normalize_token(str(selected_filter.get("id", "")))
        max_value = selected_filter.get("max")
        if "вес" in filter_name or filter_id.startswith("fr_8o") or filter_id.startswith("fr[8o]"):
            numeric_max = parse_first_number(str(max_value))
            if canonical_wish == "weight_up_to_2.3_kg":
                return numeric_max is not None and numeric_max <= 2.3
            return numeric_max is not None and numeric_max <= 2.5
    if canonical_wish in {"12gb_ram", "storage_from_256_gb", "refresh_rate_from_120hz", "refresh_rate_from_165hz"}:
        values = selected_filter.get("values", [])
        if isinstance(values, list) and values:
            numeric_values = [
                parse_first_number(str(value.get("name", "")))
                for value in values
                if isinstance(value, dict)
            ]
            numeric_values = [value for value in numeric_values if value is not None]
            if numeric_values:
                if canonical_wish == "12gb_ram":
                    return min(numeric_values) >= 12
                if canonical_wish == "storage_from_256_gb":
                    return min(numeric_values) >= 256
                if canonical_wish == "refresh_rate_from_120hz":
                    return min(numeric_values) >= 120
                if canonical_wish == "refresh_rate_from_165hz":
                    return min(numeric_values) >= 165
    aliases = wish_alias_tokens(wish)
    haystacks = [normalize_token(str(selected_filter.get("id", ""))), normalize_token(str(selected_filter.get("name", "")))]
    values = selected_filter.get("values", [])
    if isinstance(values, list):
        for value in values:
            if not isinstance(value, dict):
                continue
            haystacks.append(normalize_token(str(value.get("id", ""))))
            haystacks.append(normalize_token(str(value.get("name", ""))))
    return any(filter_text_matches_alias(haystack, aliases) for haystack in haystacks if haystack)


def wish_alias_tokens(wish: str) -> tuple[str, ...]:
    canonical_wish = canonicalize_wish(wish)
    raw_tokens = WISH_ALIASES.get(canonical_wish, (canonical_wish.replace("_", " "),))
    return tuple(normalize_token(token) for token in raw_tokens if token)


def canonicalize_wish(wish: str) -> str:
    normalized = normalize_token(wish)
    return WISH_CANONICAL_MAP.get(normalized, normalized)


def filter_id_matches_alias(filter_id: str, aliases: tuple[str, ...]) -> bool:
    return filter_text_matches_alias(filter_id, aliases)


def filter_text_matches_alias(haystack: str, aliases: tuple[str, ...]) -> bool:
    return any(alias_matches_filter_text(haystack, alias) for alias in aliases if alias)


def alias_matches_filter_text(haystack: str, alias: str) -> bool:
    if not haystack or not alias:
        return False
    if haystack == alias:
        return True
    haystack_tokens = [token for token in haystack.split("_") if token]
    alias_tokens = [token for token in alias.split("_") if token]
    if len(alias_tokens) > 1:
        return alias in haystack
    alias_token = alias_tokens[0] if alias_tokens else alias
    return any(token == alias_token or token.startswith(alias_token) for token in haystack_tokens)


def product_has_detailed_specs(product: Product) -> bool:
    specs = product.specs or []
    if len(specs) < 12:
        return False
    detailed_names = {normalize_token(str(spec.get("name", ""))) for spec in specs if isinstance(spec, dict)}
    return any(
        name in detailed_names
        for name in (
            "гарантия_продавца_/_производителя",
            "модель",
            "диагональ_экрана_(дюйм)",
            "регулировка_по_высоте",
        )
    )


def deduplicate_filter_list(selected_filters: list[dict[str, object]]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for item in selected_filters:
        filter_id = str(item.get("id", "")).casefold()
        if not filter_id or filter_id in seen_ids:
            continue
        seen_ids.add(filter_id)
        result.append(item)
    return result


def build_normalized_search_request_from_fallback(text: str) -> NormalizedSearchRequest:
    query = normalize_search_query_value(text)
    product_type, base_query = infer_product_type_and_query(query or text.strip())
    price_hint = extract_price_hint(text, product_type=product_type)
    brand = detect_brand(text)
    inferred_context_constraints = infer_context_constraints_from_text(text, product_type)
    constraints = normalize_constraints_for_product_type(
        text,
        product_type,
        deduplicate_constraints_tuples(merge_constraints_tuples(extract_constraints_from_text(text), inferred_context_constraints)),
    )
    retrieval_tokens = recover_contextual_hard_wishes(text, product_type, constraints_to_wishes(constraints))
    soft_wishes = normalize_supported_soft_wishes(extract_soft_wishes_from_text(text), text)
    draft_request = NormalizedSearchRequest(
        product_type=product_type,
        query=choose_dns_search_query(base_query, text, product_type),
        price_min=price_hint[0] if price_hint is not None else None,
        price_max=price_hint[1] if price_hint is not None else None,
        brand=brand,
        ranking_policy="",
        price_band_hint="",
        intent_signals=constraints,
        retrieval_tokens=retrieval_tokens,
        source_signal_count=len(extract_hard_wishes_from_text(text)),
        constraints=constraints,
        wishes=retrieval_tokens,
        soft_wishes=soft_wishes,
        source_hard_wishes_count=len(extract_hard_wishes_from_text(text)),
    )
    request = harmonize_normalized_request(replace(
        draft_request,
        ranking_policy=infer_ranking_policy_from_text(text, draft_request),
        price_band_hint=infer_price_band_hint_from_text(text),
    ))
    return normalize_year_semantics_from_text(text, request)


def normalize_year_semantics_from_text(text: str, request: NormalizedSearchRequest) -> NormalizedSearchRequest:
    normalized = text.casefold()
    exact_year = bool(re.search(r"\b2024(?:\s*год|\s*года|\s*г\.)?\b", normalized, re.IGNORECASE))
    range_year = bool(
        re.search(r"(?:не\s+старше|(?:от|с)\s*2024|начиная\s+с\s*2024|2024.{0,24}(?:или\s+новее|и\s+новее|не\s+старше))", normalized, re.IGNORECASE)
    )
    if not exact_year and not range_year:
        return request
    if exact_year and not range_year:
        constraints = merge_constraints_tuples(
            tuple(
                replace(constraint, op="==")
                if normalize_token(constraint.key) == "year"
                and constraint.op in {">=", "=="}
                and normalize_token(str(constraint.value)) == "2024"
                else constraint
                for constraint in request.constraints
            )
        )
        wishes = normalize_merged_wishes(
            merge_wish_tuples(tuple("2024_year" if wish == "year_from_2024" else wish for wish in request.wishes))
        )
        return harmonize_normalized_request(replace(request, intent_signals=constraints, retrieval_tokens=wishes, constraints=constraints, wishes=wishes))
    constraints = merge_constraints_tuples(
        tuple(
            replace(constraint, op=">=")
            if normalize_token(constraint.key) == "year"
            and constraint.op == "=="
            and normalize_token(str(constraint.value)) == "2024"
            else constraint
            for constraint in request.constraints
        )
    )
    wishes = merge_wish_tuples(
        tuple("year_from_2024" if wish == "2024_year" else wish for wish in request.wishes),
    )
    return harmonize_normalized_request(replace(request, intent_signals=constraints, retrieval_tokens=wishes, constraints=constraints, wishes=wishes))


def normalize_constraints_for_product_type(
    text: str,
    product_type: str,
    constraints: tuple[NormalizedConstraint, ...],
) -> tuple[NormalizedConstraint, ...]:
    normalized_product_type = normalize_token(product_type)
    normalized_constraints: list[NormalizedConstraint] = []
    for constraint in constraints:
        key = normalize_token(constraint.key)
        value = normalize_token(str(constraint.value))
        if normalized_product_type == "exercisebike":
            if key == "weight":
                normalized_constraints.append(
                    replace(
                        constraint,
                        key="max_user_weight",
                        unit="kg",
                    )
                )
                continue
            if key == "sewing_operations":
                continue
        if normalized_product_type in {"mfp", "printer"}:
            if key == "network" and ("wifi" in value or "wi-fi" in value or "wlan" in value):
                normalized_constraints.append(
                    replace(
                        constraint,
                        key="wifi",
                        op="==",
                        value="true",
                        unit="",
                    )
                )
                continue
        normalized_constraints.append(constraint)
    return deduplicate_constraints_tuples(tuple(normalized_constraints))


def recover_contextual_hard_wishes(text: str, product_type: str, hard_wishes: tuple[str, ...]) -> tuple[str, ...]:
    normalized = text.casefold()
    recovered = list(hard_wishes)
    if product_type == "laptop":
        if "16gb_ram" not in recovered and re.search(r"\b16\s*гб\b|\b16\s*gb\b", normalized, re.IGNORECASE):
            recovered.append("16gb_ram")
    return merge_wish_tuples(tuple(recovered))


def split_request_wishes(wishes: tuple[str, ...]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    hard_wishes: list[str] = []
    soft_wishes: list[str] = []
    for wish in wishes:
        canonical_wish = canonicalize_wish(wish)
        if canonical_wish in NON_FILTERABLE_WISHES:
            soft_wishes.append(canonical_wish)
            continue
        hard_wishes.append(canonical_wish)
    return tuple(hard_wishes), tuple(soft_wishes)


def merge_wish_tuples(*wish_sets: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    seen: set[str] = set()
    for wish_set in wish_sets:
        for wish in wish_set:
            wish = canonicalize_wish(wish)
            if wish in seen:
                continue
            seen.add(wish)
            merged.append(wish)
    return tuple(collapse_range_wish_overlaps(merged))


def collapse_range_wish_overlaps(wishes: list[str]) -> list[str]:
    wish_set = set(wishes)
    collapsed: list[str] = []
    for wish in wishes:
        if wish == "rtx_4070" and "rtx_4070_or_higher" in wish_set:
            continue
        if wish == "2024_year" and "year_from_2024" in wish_set:
            continue
        collapsed.append(wish)
    return collapsed


def extract_soft_wishes_from_text(text: str) -> tuple[str, ...]:
    normalized = text.casefold()
    soft_wishes: list[str] = []
    if re.search(r"(для\s+программист|для\s+программирован)", normalized, re.IGNORECASE):
        soft_wishes.append("for_programmer")
    if re.search(r"(игров\w*\s+монитор|для\s+игр|гейминг|gaming)", normalized, re.IGNORECASE):
        soft_wishes.append("for_gaming")
    camera_hit = bool(re.search(r"\b(?:камер\w*|camera|(?:\d+\s*)?мп\b|mp\b)", normalized, re.IGNORECASE))
    camera_fallback_context = bool(re.search(r"(холодил\w*|морозил\w*)", normalized, re.IGNORECASE))
    if camera_hit and not (camera_fallback_context and not re.search(r"(фото|селфи|снимк|объектив|линз|камера\s+съём|мп\b|mp\b)", normalized, re.IGNORECASE)):
        soft_wishes.append("good_camera")
    if re.search(r"(хорош\w*\s+батаре|долг\w*\s+автоном|хорош\w*\s+автоном|автономн\w*|battery)", normalized, re.IGNORECASE):
        soft_wishes.append("good_battery")
    if re.search(r"(не\s+тормоз|шуст\w*|быстр\w*|мощн\w*|мощьн\w*|производительн\w*)", normalized, re.IGNORECASE):
        soft_wishes.append("good_performance")
    if re.search(r"(ярк\w*\s+экран|ярк\w*\s+диспле|высок\w*\s+яркост|bright\s+screen)", normalized, re.IGNORECASE):
        soft_wishes.append("bright_screen")
    if re.search(r"(хорош\w*\s+навигац|lidar|лидар|mapping)", normalized, re.IGNORECASE):
        soft_wishes.append("good_navigation")
    if re.search(r"(тонк\w*\s+рамк)", normalized, re.IGNORECASE):
        soft_wishes.append("thin_bezel")
    if re.search(r"(вместительн\w*)", normalized, re.IGNORECASE):
        soft_wishes.append("spacious")
    if re.search(r"\bтих\w*\b", normalized, re.IGNORECASE):
        soft_wishes.append("quiet")
    if re.search(r"\bнадеж\w*\b", normalized, re.IGNORECASE):
        soft_wishes.append("reliable")
    if re.search(r"((?:легк|лёгк)\w*|не\s+слишком\s+тяжел\w*)", normalized, re.IGNORECASE):
        soft_wishes.append("lightweight")
    if re.search(r"(для\s+рисован|рисоват)", normalized, re.IGNORECASE):
        soft_wishes.append("for_drawing")
    if re.search(r"(поддержк\w*\s+спин|эргоном)", normalized, re.IGNORECASE):
        soft_wishes.append("back_support")
    if re.search(r"(не\s+хлам|качеств\w*\s+сборк)", normalized, re.IGNORECASE):
        soft_wishes.append("quality_build")
    if re.search(r"(прост\w*\s+обслуживан|easy\s+maintenance)", normalized, re.IGNORECASE):
        soft_wishes.append("easy_maintenance")
    if re.search(r"(картинк\w*\s+был\w*\s+хорош|хорош\w*\s+картинк)", normalized, re.IGNORECASE):
        soft_wishes.append("good_image_quality")
    return tuple(soft_wishes)


def normalize_supported_soft_wishes(soft_wishes: tuple[str, ...], text: str) -> tuple[str, ...]:
    supported: list[str] = []
    for wish in soft_wishes:
        canonical = canonicalize_wish(wish)
        if not canonical:
            continue
        if canonical == "good_performance" and not soft_wish_supported_by_text(canonical, text):
            continue
        supported.append(canonical)
    return merge_wish_tuples(tuple(supported))


def soft_wish_supported_by_text(wish: str, text: str) -> bool:
    normalized = text.casefold()
    if wish == "for_programmer":
        return bool(re.search(r"(для\s+программист|для\s+программирован)", normalized, re.IGNORECASE))
    if wish == "for_gaming":
        return bool(re.search(r"(игров\w*\s+монитор|для\s+игр|гейминг|gaming)", normalized, re.IGNORECASE))
    if wish == "good_camera":
        return bool(re.search(r"\b(?:камер\w*|camera|(?:\d+\s*)?мп\b|mp\b)", normalized, re.IGNORECASE))
    if wish == "good_battery":
        return bool(re.search(r"(хорош\w*\s+батаре|долг\w*\s+автоном|battery|автономн)", normalized, re.IGNORECASE))
    if wish == "good_performance":
        return bool(re.search(r"(не\s+тормоз|шуст\w*|производител|мощн\w*|мощьн\w*)", normalized, re.IGNORECASE))
    if wish == "bright_screen":
        return bool(re.search(r"(ярк\w*\s+экран|ярк\w*\s+диспле|высок\w*\s+яркост|bright\s+screen)", normalized, re.IGNORECASE))
    if wish == "thin_bezel":
        return bool(re.search(r"(тонк\w*\s+рамк)", normalized, re.IGNORECASE))
    if wish == "spacious":
        return bool(re.search(r"(вместительн\w*)", normalized, re.IGNORECASE))
    if wish == "quiet":
        return bool(re.search(r"\bтих\w*\b", normalized, re.IGNORECASE))
    if wish == "reliable":
        return bool(re.search(r"\bнадеж\w*\b", normalized, re.IGNORECASE))
    if wish == "good_navigation":
        return bool(re.search(r"(лидар|lidar|навигац|mapping)", normalized, re.IGNORECASE))
    if wish == "easy_maintenance":
        return bool(re.search(r"(прост\w*\s+обслуживан|easy\s+maintenance)", normalized, re.IGNORECASE))
    if wish == "lightweight":
        return bool(re.search(r"((?:легк|лёгк)\w*|не\s+слишком\s+тяжел\w*)", normalized, re.IGNORECASE))
    if wish == "for_drawing":
        return bool(re.search(r"(для\s+рисован|рисоват)", normalized, re.IGNORECASE))
    if wish == "back_support":
        return bool(re.search(r"(поддержк\w*\s+спин|эргоном)", normalized, re.IGNORECASE))
    if wish == "quality_build":
        return bool(re.search(r"(не\s+хлам|качеств\w*\s+сборк)", normalized, re.IGNORECASE))
    if wish == "good_image_quality":
        return bool(re.search(r"(картинк\w*\s+был\w*\s+хорош|хорош\w*\s+картинк)", normalized, re.IGNORECASE))
    return True


def extract_constraints_from_text(text: str) -> tuple[NormalizedConstraint, ...]:
    return constraints_from_legacy_wishes(extract_hard_wishes_from_text(text))


def extract_hard_wishes_from_text(text: str) -> tuple[str, ...]:
    normalized = text.casefold()
    wishes: list[str] = []
    rtx_4070_range = bool(re.search(r"(?:от\s*)?\brtx\s*4070\b(?:\s*(?:или|и)?\s*выше)?", normalized, re.IGNORECASE)) and bool(
        re.search(r"\brtx\s*4070\b.{0,24}(?:или\s+выше|и\s+выше|выше)|от\s*rtx\s*4070", normalized, re.IGNORECASE)
    )
    if rtx_4070_range:
        wishes.append("rtx_4070_or_higher")
    elif re.search(r"\brtx\s*4070\b", normalized, re.IGNORECASE):
        wishes.append("rtx_4070")
    if re.search(r"\brtx\s*4080\b", normalized, re.IGNORECASE):
        wishes.append("rtx_4080")
    if re.search(r"\b32\s*гб\b|\b32\s*gb\b", normalized, re.IGNORECASE) and (
        re.search(r"\bозу\b|\bram\b|оператив", normalized, re.IGNORECASE)
    ):
        wishes.append("32gb_ram")
    if re.search(r"\b12\s*гб\b|\b12\s*gb\b", normalized, re.IGNORECASE) and (
        re.search(r"\bозу\b|\bram\b|оператив", normalized, re.IGNORECASE)
    ):
        wishes.append("12gb_ram")
    if re.search(r"\b16\s*гб\b|\b16\s*gb\b", normalized, re.IGNORECASE) and (
        re.search(r"\bозу\b|\bram\b|оператив", normalized, re.IGNORECASE)
    ):
        wishes.append("16gb_ram")
    if re.search(r"(?:от\s*)?\b120\s*(?:гц|hz)\b.{0,24}(?:или\s+выше|и\s+выше|выше)|от\s*120\s*(?:гц|hz)", normalized, re.IGNORECASE):
        wishes.append("refresh_rate_from_120hz")
    if re.search(r"(?:от\s*)?\b165\s*(?:гц|hz)\b.{0,24}(?:или\s+выше|и\s+выше|выше)|от\s*165\s*(?:гц|hz)", normalized, re.IGNORECASE):
        wishes.append("refresh_rate_from_165hz")
    elif re.search(r"\b240\s*гц\b|\b240\s*hz\b", normalized, re.IGNORECASE):
        wishes.append("240hz_screen")
    if re.search(r"\b144\s*гц\b|\b144\s*hz\b", normalized, re.IGNORECASE):
        wishes.append("144hz_display")
    if re.search(r"\b1440p\b|\bqhd\b|\b2560\s*[xх]\s*1440\b", normalized, re.IGNORECASE):
        wishes.append("1440p")
    if re.search(r"\b(?:монитор|monitor|экран|display)\b", normalized, re.IGNORECASE) and re.search(
        r"\b(?:2\s*[кk]|2k)\b",
        normalized,
        re.IGNORECASE,
    ):
        wishes.append("1440p")
    if re.search(r"\b4k\b|\b3840\s*[xх]\s*2160\b", normalized, re.IGNORECASE):
        wishes.append("4k")
    if re.search(r"\bips\b", normalized, re.IGNORECASE):
        wishes.append("ips")
    if re.search(r"\bnfc\b", normalized, re.IGNORECASE):
        wishes.append("nfc")
    if re.search(r"\bamoled\b|\boled\b", normalized, re.IGNORECASE):
        wishes.append("amoled_display" if "amoled" in normalized else "oled")
    if re.search(r"\b27\s*(?:дюйм(?:а|ов)?|\"|''|inch)\b|\b27inch\b", normalized, re.IGNORECASE):
        wishes.append("27_inch")
    if re.search(r"\b55\s*(?:дюйм(?:а|ов)?|\"|''|inch)\b|\b55inch\b", normalized, re.IGNORECASE):
        wishes.append("55_inch")
    if re.search(r"регулировк\w*\s+высот|height\s*adjust", normalized, re.IGNORECASE):
        wishes.append("height_adjustable")
    if re.search(r"\b512\s*гб\b|\b512\s*gb\b", normalized, re.IGNORECASE) and re.search(r"\bssd\b", normalized, re.IGNORECASE):
        wishes.append("ssd_from_512_gb")
    if re.search(r"\b256\s*гб\b|\b256\s*gb\b", normalized, re.IGNORECASE) and re.search(r"(памят|storage|ssd)", normalized, re.IGNORECASE):
        if re.search(r"(?:от|не\s+менее)\s*256\s*(?:гб|gb)\b", normalized, re.IGNORECASE):
            wishes.append("storage_from_256_gb")
        else:
            wishes.append("256gb_storage")
    if re.search(r"(?:не\s+меньше|от|минимум)\s*30\s*(?:швейн\w*\s+операц\w*|операц\w*.*швейн\w*)", normalized, re.IGNORECASE):
        wishes.append("sewing_operations_from_30")
    elif re.search(r"\b30\s*(?:швейн\w*\s+операц\w*|операц\w*.*швейн\w*)\b", normalized, re.IGNORECASE):
        wishes.append("sewing_operations_from_30")
    if re.search(r"(горизонтал\w*\s+челнок|horizontal\s+shuttle)", normalized, re.IGNORECASE):
        wishes.append("shuttle_type_horizontal")
    if re.search(r"(автоматическ\w*\s+выполнени\w*\s+петл|автоматическ\w*\s+петл|automatic\s+buttonhole)", normalized, re.IGNORECASE):
        wishes.append("buttonhole_automatic")
    if re.search(r"(регулировк\w*\s+скорост\w*|скорость\s+шить|speed\s+control)", normalized, re.IGNORECASE):
        wishes.append("speed_control")
    if re.search(r"(подсветк\w*\s+рабоч\w*\s+зон|illumination|led\s+подсветк\w*|подсветк\w*)", normalized, re.IGNORECASE):
        wishes.append("work_area_light")
    if re.search(r"(съёмн\w*\s+панел|съемн\w*\s+панел|removable\s+panel)", normalized, re.IGNORECASE):
        wishes.append("removable_panels")
    if re.search(r"(антипригарн\w*\s+покрыт|non[-\s]*stick|nonstick)", normalized, re.IGNORECASE):
        wishes.append("nonstick_coating")
    if re.search(r"(регулировк\w*\s+температур|temperature\s+control)", normalized, re.IGNORECASE):
        wishes.append("temperature_control")
    if re.search(r"(поддон\w*\s+для\s+жир|drip\s+tray|grease\s+tray)", normalized, re.IGNORECASE):
        wishes.append("grease_tray")
    if re.search(r"(раскрыт\w*\s+на\s+180|180\s*градус|opens\s+180)", normalized, re.IGNORECASE):
        wishes.append("opens_180")
    if re.search(r"(управлен\w*\s+со\s+смартфон|app\s+control|smartphone\s+control)", normalized, re.IGNORECASE):
        wishes.append("smartphone_control")
    if re.search(r"(?:от\s*)?\b4000\s*(?:м?а·?ч|mah)\b|\bаккумулятор\w*\s+от\s*4000", normalized, re.IGNORECASE):
        wishes.append("battery_capacity_from_4000_mah")
    if re.search(r"(автоматическ\w*\s+возвращен\w*\s+на\s+баз|return\s+to\s+base|автовозврат)", normalized, re.IGNORECASE):
        wishes.append("auto_return_to_base")
    if re.search(r"(прост\w*\s+очистк\w*\s+контейнер|easy\s+cleaning)", normalized, re.IGNORECASE):
        wishes.append("dustbin_easy_cleaning")
    if re.search(r"(хорош\w*\s+навигац|good\s+navigation)", normalized, re.IGNORECASE):
        wishes.append("good_navigation")
    if re.search(r"\bwi[-\s]?fi\b|\bwifi\b", normalized, re.IGNORECASE):
        wishes.append("wifi")
    if re.search(r"(двусторонн\w*\s+печать|duplex)", normalized, re.IGNORECASE):
        wishes.append("duplex_print")
    if re.search(r"\bсканер\w*\b|\bscanner\b", normalized, re.IGNORECASE):
        wishes.append("scanner")
    if re.search(r"(?:от\s*)?\b20\s*(?:стр/мин|ppm)\b|\bскорост\w*\s+от\s*20", normalized, re.IGNORECASE):
        wishes.append("print_speed_from_20_ppm")
    if re.search(r"(простой\s+заправк|easy\s+refill|прост\w*\s+обслуживан)", normalized, re.IGNORECASE):
        wishes.append("refill_easy")
    if re.search(r"(недорог\w*\s+обслуживан|cheap\s+maintenance)", normalized, re.IGNORECASE):
        wishes.append("cheap_maintenance")
    if re.search(r"(магнитн\w*\s+систем\w*\s+нагруз|magnetic\s+system|resistance\s+system)", normalized, re.IGNORECASE):
        wishes.append("resistance_system_magnetic")
    if re.search(r"(магнитн\w*\s+клавиатур|клавиатур\w*.{0,40}магнитн|magnetic\s+keyboard|hall\s+effect)", normalized, re.IGNORECASE):
        wishes.append("keyboard_type_magnetic")
    if re.search(r"(?:75\s*[-–—]\s*80|75\s*/\s*80|75\s*(?:%|процент)|80\s*(?:%|процент)|tkl)", normalized, re.IGNORECASE) and re.search(r"(клавиатур|keyboard|раскладк|формат|форм[-\s]*фактор|процент)", normalized, re.IGNORECASE):
        wishes.append("keyboard_format_75_80")
    if re.search(r"(?:не\s+меньше|не\s+ниже|от)\s*120\s*(?:кг|kg)\b", normalized, re.IGNORECASE):
        wishes.append("max_user_weight_from_120_kg")
    if re.search(r"(регулировк\w*\s+сидень|seat\s+adjustment)", normalized, re.IGNORECASE):
        wishes.append("seat_adjustment")
    if re.search(r"(диспле\w*|console|display)", normalized, re.IGNORECASE):
        wishes.append("display")
    if re.search(r"(измерен\w*\s+пульс|heart\s+rate|pulse)", normalized, re.IGNORECASE):
        wishes.append("pulse_measurement")
    if re.search(r"(?:не\s+меньше|не\s+ниже|от)\s*8\s*(?:уровн\w*\s+нагруз|levels?)", normalized, re.IGNORECASE):
        wishes.append("resistance_levels_from_8")
    if re.search(r"(устойчив\w*\s+конструкц|stable\s+construction)", normalized, re.IGNORECASE):
        wishes.append("stable_construction")
    if re.search(r"(автоматическ\w*\s+кофемашин|автоматическ\w*\s+машин\w*.*коф|automatic\s+coffee\s+machine)", normalized, re.IGNORECASE):
        wishes.append("machine_type_automatic")
    if re.search(r"(капучинатор|cappuccino)", normalized, re.IGNORECASE):
        wishes.append("cappuccinator")
    if re.search(r"(?:от\s*)?\b15\s*(?:бар|bar)\b", normalized, re.IGNORECASE):
        wishes.append("pressure_from_15_bar")
    if re.search(r"(встроенн\w*\s+кофемолк|built[-\s]*in\s+grinder|grinder)", normalized, re.IGNORECASE):
        wishes.append("built_in_grinder")
    if re.search(r"(регулировк\w*\s+крепост|strength\s+adjustment)", normalized, re.IGNORECASE):
        wishes.append("strength_adjustment")
    if re.search(r"(регулировк\w*\s+объем\w*\s+порц|portion\s+volume|cup\s+size)", normalized, re.IGNORECASE):
        wishes.append("portion_volume_adjustment")
    if re.search(r"(самоочистк|self\s+cleaning)", normalized, re.IGNORECASE):
        wishes.append("self_cleaning")
    if re.search(r"(?:до|<=?)\s*1[.,]5\s*кг", normalized, re.IGNORECASE):
        wishes.append("weight_up_to_1.5_kg")
    if re.search(r"(?:до|<=?)\s*2[.,]3\s*кг", normalized, re.IGNORECASE):
        wishes.append("weight_up_to_2.3_kg")
    if re.search(r"(?:до|<=?)\s*2[.,]5\s*кг", normalized, re.IGNORECASE):
        wishes.append("weight_up_to_2.5_kg")
    if re.search(r"матов\w*|антиблик\w*|anti[-\s_]*glare|matte", normalized, re.IGNORECASE):
        wishes.append("matte_screen")
    if re.search(r"(не\s+старше|(?:от|с)\s*2024|начиная\s+с\s*2024|2024.{0,24}(?:или\s+новее|и\s+новее|не\s+старше))", normalized, re.IGNORECASE):
        wishes.append("year_from_2024")
    elif re.search(r"\b2024(?:\s*год|\s*года|\s*г\.)?\b", normalized, re.IGNORECASE):
        wishes.append("2024_year")
    if re.search(r"side[-\s]*by[-\s]*side", normalized, re.IGNORECASE):
        wishes.append("side_by_side")
    if re.search(r"\bno\s*frost\b|\bноу\s*фрост\b", normalized, re.IGNORECASE):
        wishes.append("cooling_system_no_frost")
    if re.search(r"(морозильн\w*\s+камер\w*\s+снизу|морозилка\s+снизу|нижн\w*\s+расположен\w*\s+морозильн\w*\s+камер\w*|bottom\s+freezer)", normalized, re.IGNORECASE):
        wishes.append("freezer_position_bottom")
    if re.search(r"(инверторн\w*\s+компрессор|инвертор\s+компрессор|inverter\s+compressor)", normalized, re.IGNORECASE):
        wishes.append("inverter_compressor")
    if re.search(r"(?:до|не\s+больше|не\s+шире)\s*60\s*см", normalized, re.IGNORECASE):
        wishes.append("width_up_to_60_cm")
    if re.search(r"(?:от|не\s+меньше|не\s+ниже)\s*300\s*л", normalized, re.IGNORECASE):
        wishes.append("volume_from_300_l")
    if re.search(r"(?:класс\w*\s+энергопотребления|энергоэффективности).{0,20}(?:не\s+ниже\s*a|\ba\+{0,3}\b)", normalized, re.IGNORECASE):
        wishes.append("energy_class_not_lower_than_a")
    if re.search(r"\bсушк\w*\b", normalized, re.IGNORECASE):
        wishes.append("dryer")
    if re.search(r"(влажн\w*\s+уборк|влажной\s+уборкой)", normalized, re.IGNORECASE):
        wishes.append("wet_cleaning")
    if re.search(r"(построени\w*\s+карт|навигац\w*\s+по\s+карт|mapping)", normalized, re.IGNORECASE):
        wishes.append("mapping")
    if re.search(r"\bлидар\w*\b|lidar", normalized, re.IGNORECASE):
        wishes.append("lidar_navigation")
    return normalize_merged_wishes(tuple(wishes))


def rank_products_for_request(
    products: list[Product],
    normalized_request: NormalizedSearchRequest,
) -> list[Product]:
    if not products:
        return []
    numeric_prices = [product.price for product in products if isinstance(product.price, int)]
    median_price = statistics.median(numeric_prices) if numeric_prices and normalized_request.price_max is None else None
    price_floor = preferred_price_floor(normalized_request, products)
    price_target = preferred_price_target(normalized_request)
    ranked = sorted(
        enumerate(products),
        key=lambda item: (
            -score_product_for_request(item[1], normalized_request),
            0
            if median_price is None
            and not product_exceeds_price_max(item[1], normalized_request)
            and (price_floor is None or not isinstance(item[1].price, int) or item[1].price >= price_floor)
            else 1,
            price_distance_for_ranking(item[1], median_price, price_target),
            item[0],
        ),
    )
    return deduplicate_products_by_model([product for _, product in ranked], max_per_model=2)


def select_shortlist_candidates(
    products: list[Product],
    normalized_request: NormalizedSearchRequest,
    limit: int = SHORTLIST_CANDIDATE_LIMIT,
) -> list[Product]:
    ranked = deduplicate_products_by_model(products, max_per_model=2)
    if len(ranked) <= limit:
        return ranked
    if normalized_request.price_max is not None:
        return ranked[:limit]
    priced = [item for item in enumerate(ranked) if isinstance(item[1].price, int)]
    if len(priced) < 3:
        return ranked[:limit]
    priced_sorted = sorted(
        priced,
        key=lambda item: (
            item[1].price if isinstance(item[1].price, int) else 999999999,
            -score_product_for_request(item[1], normalized_request),
            item[0],
        ),
    )
    chunk = max(1, len(priced_sorted) // 3)
    tiers = [priced_sorted[:chunk], priced_sorted[chunk : 2 * chunk], priced_sorted[2 * chunk :]]
    selected: list[Product] = []
    seen_urls: set[str] = set()
    per_tier = max(1, limit // 3)
    for tier in tiers:
        tier_ranked = sorted(
            tier,
            key=lambda item: (
                -score_product_for_request(item[1], normalized_request),
                item[1].price if isinstance(item[1].price, int) else 999999999,
                item[0],
            ),
        )
        for _, product in tier_ranked[:per_tier]:
            if product.url in seen_urls:
                continue
            selected.append(product)
            seen_urls.add(product.url)
            if len(selected) >= limit:
                return selected[:limit]
    for product in ranked:
        if product.url in seen_urls:
            continue
        selected.append(product)
        seen_urls.add(product.url)
        if len(selected) >= limit:
            break
    return selected[:limit]


def extract_model_key(name: str) -> str:
    parts = [part for part in normalize_token(name).split("_") if part]
    while parts and parts[-1] in MODEL_COLOR_TOKENS:
        parts.pop()
    if not parts:
        return normalize_token(name)
    return "_".join(parts[-8:])


def deduplicate_products_by_model(products: list[Product], max_per_model: int = 1) -> list[Product]:
    if max_per_model <= 0:
        return []
    seen: dict[str, int] = {}
    result: list[Product] = []
    for product in products:
        key = extract_model_key(product.name)
        current = seen.get(key, 0)
        if current >= max_per_model:
            continue
        seen[key] = current + 1
        result.append(product)
    return result


def extract_product_metric(text: str, metric_name: str) -> int:
    match = re.search(rf"{metric_name}[^\d]{{0,24}}(\d[\d\s.,]*)", text, re.IGNORECASE)
    if not match:
        return 0
    return parse_numeric_metric_value(match.group(1)) or 0


def preferred_price_floor(
    normalized_request: NormalizedSearchRequest,
    products: list[Product],
) -> int | None:
    hint = normalize_token(normalized_request.price_band_hint)
    prices = sorted(product.price for product in products if isinstance(product.price, int))
    if not prices:
        return None
    if hint == "mid_to_max":
        return int(statistics.median(prices))
    if hint == "top":
        return int(prices[max(0, len(prices) - max(1, len(prices) // 3))])
    return None


def preferred_price_target(normalized_request: NormalizedSearchRequest) -> int | None:
    """Return target price for quality-oriented ranking inside a fixed budget."""

    if not isinstance(normalized_request.price_max, int):
        return None
    if normalize_token(normalized_request.price_band_hint) == "budget":
        return None
    return max(1, int(normalized_request.price_max * 0.7))


def price_distance_for_ranking(
    product: Product,
    median_price: float | int | None,
    price_target: int | None,
) -> int:
    """Prefer relevant products near the intended budget segment, not the cheapest item."""

    if not isinstance(product.price, int):
        return 999999999
    if price_target is not None:
        return abs(product.price - price_target)
    if median_price is not None:
        return abs(product.price - int(median_price))
    return product.price


def ranking_policy_bonus(
    product: Product,
    normalized_request: NormalizedSearchRequest,
    product_text: str,
) -> int:
    policy = normalize_token(normalized_request.ranking_policy)
    band_hint = normalize_token(normalized_request.price_band_hint)
    if not policy:
        return 0
    price = product.price if isinstance(product.price, int) else None
    if price is None:
        return 0
    bonus = 0
    if band_hint == "mid_to_max" and isinstance(normalized_request.price_max, int):
        band_floor = max(1, int(normalized_request.price_max * 0.35))
        if price < band_floor:
            bonus -= 5000
    elif band_hint == "top" and isinstance(normalized_request.price_max, int):
        band_floor = max(1, int(normalized_request.price_max * 0.7))
        if price < band_floor:
            bonus -= 5000
    antutu_score = extract_product_metric(product_text, r"(?:antutu|антуту)")
    brightness_score = extract_product_metric(product_text, r"(?:яркость|brightness)")
    screen_size_score = extract_product_metric(product_text, r"(?:диагональ(?:_экрана)?|размер_экрана|screen_size)")
    if policy == "performance":
        bonus += antutu_score // 50000
    elif policy == "display":
        bonus += brightness_score // 25
        bonus += screen_size_score * 8
    elif policy == "value" and antutu_score > 0:
        bonus += int((antutu_score / max(price, 1)) * 100)
    return bonus


def brand_matches_product(brand: str, product: Product, searchable_text: str) -> bool:
    normalized_brand = normalize_token(brand)
    if not normalized_brand:
        return False
    if normalized_brand in searchable_text:
        return True
    aliases = BRAND_ALIASES.get(normalized_brand, ())
    for alias in aliases:
        normalized_alias = normalize_token(alias)
        if normalized_alias and normalized_alias in searchable_text:
            return True
    detected = detect_brand(searchable_text.replace("_", " "))
    return bool(detected and normalize_token(detected) == normalized_brand)


def score_product_for_request(product: Product, normalized_request: NormalizedSearchRequest) -> int:
    text = normalize_token(product.name)
    if product.specs:
        for spec in product.specs:
            if not isinstance(spec, dict):
                continue
            text += " " + normalize_token(str(spec.get("name", "")))
            text += " " + normalize_token(str(spec.get("value", "")))
    score = 0
    retrieval_tokens = request_retrieval_tokens(normalized_request)
    for token in retrieval_tokens:
        if product_matches_wish(product, token, text=text):
            score += 10
        elif product_contradicts_wish(product, token, text=text):
            score -= 8
    if product_exceeds_price_max(product, normalized_request):
        score -= 25
    for wish in normalized_request.soft_wishes:
        score += 4 if product_matches_wish(product, wish, text=text) else 0
    if brand_matches_product(normalized_request.brand, product, text):
        score += 3
    if normalized_request.query and normalized_request.query in text:
        score += 2
    score += ranking_policy_bonus(product, normalized_request, text)
    return score


def product_text_matches_wish(text: str, wish: str) -> bool:
    aliases = wish_alias_tokens(wish)
    if not aliases:
        return False
    return any(alias_matches_filter_text(text, alias) for alias in aliases)


def product_matches_wish(product: Product, wish: str, text: str | None = None) -> bool:
    canonical_wish = canonicalize_wish(wish)
    specs_match = product_matches_wish_by_specs(product, canonical_wish)
    if specs_match:
        return True
    if canonical_wish in STRICT_SPEC_WISHES and product.specs and not product_has_compact_listing_specs(product):
        return False
    haystack = text
    if haystack is None:
        haystack = normalize_token(product.name)
        if product.specs:
            for spec in product.specs:
                if not isinstance(spec, dict):
                    continue
                haystack += " " + normalize_token(str(spec.get("name", "")))
                haystack += " " + normalize_token(str(spec.get("value", "")))
    return product_text_matches_wish(haystack, canonical_wish)


def product_matches_wish_by_specs(product: Product, wish: str) -> bool:
    specs = product.specs or []
    if not specs:
        return False
    spec_pairs = [
        (
            normalize_token(str(spec.get("name", ""))),
            normalize_token(str(spec.get("value", ""))),
        )
        for spec in specs
        if isinstance(spec, dict)
    ]
    if wish == "27_inch":
        return any("диагональ" in name and "27" in value for name, value in spec_pairs)
    if wish == "1440p":
        return any(("разреш" in name or "максимальное_разрешение" in name) and ("2560x1440" in value or "1440" in value) for name, value in spec_pairs)
    if wish == "ips":
        return any(("матриц" in name or "экран" in name) and "ips" in value for name, value in spec_pairs)
    if wish == "height_adjustable":
        return any("регулировка" in name and "высот" in name and is_positive_spec_value(value) for name, value in spec_pairs)
    if wish == "16gb_ram":
        return any(("оператив" in name or "озу" in name) and parse_first_number(value) == 16 for name, value in spec_pairs)
    if wish == "12gb_ram":
        return any(("оператив" in name or "озу" in name) and parse_first_number(value) is not None and parse_first_number(value) >= 12 for name, value in spec_pairs)
    if wish == "32gb_ram":
        return any(("оператив" in name or "озу" in name) and parse_first_number(value) == 32 for name, value in spec_pairs)
    if wish == "storage_from_256_gb":
        return any(
            ("встроен" in name or "накопител" in name or ("памят" in name and "оператив" not in name and "озу" not in name))
            and parse_first_number(value) is not None
            and parse_first_number(value) >= 256
            for name, value in spec_pairs
        )
    if wish == "ssd_from_512_gb":
        return any(("ssd" in name or "твердотель" in name) and (parse_first_number(value) or 0) >= 512 for name, value in spec_pairs)
    if wish == "weight_up_to_1.5_kg":
        return any("вес" in name and parse_first_number(value) is not None and parse_first_number(value) <= 1.5 for name, value in spec_pairs)
    if wish == "weight_up_to_2.5_kg":
        return any("вес" in name and parse_first_number(value) is not None and parse_first_number(value) <= 2.5 for name, value in spec_pairs)
    if wish == "weight_up_to_2.3_kg":
        return any("вес" in name and parse_first_number(value) is not None and parse_first_number(value) <= 2.3 for name, value in spec_pairs)
    if wish == "nfc":
        return any(name == "nfc" and is_positive_spec_value(value) for name, value in spec_pairs)
    if wish == "amoled_display":
        return any(("матриц" in name or "экран" in name) and ("amoled" in value or "dynamic amoled" in value or "super amoled" in value) for name, value in spec_pairs)
    if wish == "matrix_type_amoled":
        return any(("матриц" in name or "экран" in name) and ("amoled" in value or "dynamic amoled" in value or "super amoled" in value) for name, value in spec_pairs)
    if wish == "matrix_type_oled":
        return any(("матриц" in name or "экран" in name) and "oled" in value for name, value in spec_pairs)
    if wish == "matrix_type_ips":
        return any(("матриц" in name or "экран" in name) and "ips" in value for name, value in spec_pairs)
    if wish == "matrix_type_va":
        return any(("матриц" in name or "экран" in name) and "va" in value for name, value in spec_pairs)
    if wish == "matrix_type_qled":
        return any(("матриц" in name or "экран" in name) and "qled" in value for name, value in spec_pairs)
    if wish == "oled":
        return any(("матриц" in name or "экран" in name) and "oled" in value for name, value in spec_pairs)
    if wish == "240hz_screen":
        return any(("частота" in name and "экран" in name) and parse_first_number(value) == 240 for name, value in spec_pairs)
    if wish == "refresh_rate_from_120hz":
        return any(("частота" in name and "экран" in name) and parse_first_number(value) is not None and parse_first_number(value) >= 120 for name, value in spec_pairs)
    if wish == "refresh_rate_from_165hz":
        return any(("частота" in name and "экран" in name) and parse_first_number(value) is not None and parse_first_number(value) >= 165 for name, value in spec_pairs)
    if wish == "matte_screen":
        return any(("покрытие" in name or "экран" in name) and ("матов" in value or "антиблик" in value) for name, value in spec_pairs)
    if wish == "bright_screen":
        return any(("яркост" in name or "brightness" in name) and parse_first_number(value) is not None for name, value in spec_pairs)
    if wish == "rtx_4080":
        return any(("видеокарт" in name or "gpu" in name) and ("rtx_4080" in value or "geforce_rtx_4080" in value) for name, value in spec_pairs)
    if wish == "rtx_4070":
        return any(("видеокарт" in name or "gpu" in name) and ("rtx_4070" in value or "geforce_rtx_4070" in value) for name, value in spec_pairs)
    if wish == "rtx_4070_or_higher":
        return any(("видеокарт" in name or "gpu" in name) and rtx_4070_or_higher_value_matches(value) for name, value in spec_pairs)
    if wish == "2024_year":
        return any(("год" in name or "релиз" in name) and "2024" in value for name, value in spec_pairs)
    if wish == "year_from_2024":
        return any(("год" in name or "релиз" in name) and parse_first_number(value) is not None and parse_first_number(value) >= 2024 for name, value in spec_pairs)
    if wish == "network_5g":
        return any(("связ" in name or "стандарт" in name) and "5g" in value for name, value in spec_pairs)
    if wish == "wifi":
        return any(("wi_fi" in name or "wi-fi" in name or "wifi" in name or "wlan" in name) and is_positive_spec_value(value) for name, value in spec_pairs)
    if wish == "fast_charge":
        return any(("быстрая" in name and "заряд" in name) and is_positive_spec_value(value) for name, value in spec_pairs)
    if wish == "wireless_charge":
        return any(("беспровод" in name and "заряд" in name) and is_positive_spec_value(value) for name, value in spec_pairs)
    if wish == "waterproof_ip68":
        return any(("защит" in name or "ip" in name) and "ip68" in value for name, value in spec_pairs)
    if wish == "waterproof_ip67":
        return any(("защит" in name or "ip" in name) and "ip67" in value for name, value in spec_pairs)
    if wish == "cooling_system_no_frost":
        freezer_no_frost = any(
            "морозиль" in name and ("no_frost" in value or "nofrost" in value)
            for name, value in spec_pairs
        )
        fridge_no_frost = any(
            "холодильн" in name and ("no_frost" in value or "nofrost" in value)
            for name, value in spec_pairs
        )
        return freezer_no_frost and fridge_no_frost
    if wish == "freezer_position_bottom":
        return any(("морозиль" in name or "располож" in name) and ("снизу" in value or "bottom" in value) for name, value in spec_pairs)
    if wish == "inverter_compressor":
        return any("компрессор" in name and ("инвертор" in value or is_positive_spec_value(value)) for name, value in spec_pairs)
    if wish == "scanner":
        return any(("сканер" in name or "scanner" in name or "сканир" in name) and is_positive_spec_value(value) for name, value in spec_pairs)
    if wish in {"sewing_operations_from_30", "sewing_operations"}:
        return any(
            ("швейн" in name or "операц" in name)
            and parse_first_number(value) is not None
            and parse_first_number(value) >= 30
            for name, value in spec_pairs
        )
    if wish == "shuttle_type_horizontal":
        return any(("челнок" in name or "шаттл" in name) and ("горизонт" in value or "horizontal" in value) for name, value in spec_pairs)
    if wish == "buttonhole_automatic":
        return any(("петл" in name or "buttonhole" in name) and "автомат" in value for name, value in spec_pairs)
    if wish == "speed_control":
        return any(
            ("скорост" in name or "регулиров" in name)
            and (is_positive_spec_value(value) or "бесступенчат" in value or "ступенчат" in value)
            for name, value in spec_pairs
        )
    if wish == "built_in_grinder":
        return any(("кофемолк" in name or "grinder" in name) and is_positive_spec_value(value) for name, value in spec_pairs)
    if wish == "work_area_light":
        return any(
            ("подсвет" in name or "light" in name or "illumination" in name)
            and (is_positive_spec_value(value) or "led" in value or "светодиод" in value)
            for name, value in spec_pairs
        )
    if wish == "keyboard_type_magnetic":
        return any(
            ("тип_клавиатуры" in name or "переключател" in name or "switch" in name)
            and ("магнит" in value or "magnetic" in value or "hall" in value)
            for name, value in spec_pairs
        )
    if wish == "keyboard_format_75_80":
        return any(
            ("формат" in name or "раскладк" in name or "количество_клавиш" in name)
            and ("75" in value or "80" in value or "tkl" in value)
            for name, value in spec_pairs
        )
    return False


def product_contradicts_wish(product: Product, wish: str, text: str | None = None) -> bool:
    canonical_wish = canonicalize_wish(wish)
    specs = product.specs or []
    spec_pairs = [
        (
            normalize_token(str(spec.get("name", ""))),
            normalize_token(str(spec.get("value", ""))),
        )
        for spec in specs
        if isinstance(spec, dict)
    ]
    if canonical_wish == "27_inch":
        diagonal = find_monitor_diagonal_value(spec_pairs, text or product.name)
        return diagonal is not None and abs(diagonal - 27.0) > 0.4
    if canonical_wish == "1440p":
        return any(("разреш" in name or "максимальное_разрешение" in name) and "2560x1440" not in value and "1440" not in value for name, value in spec_pairs)
    if canonical_wish == "ips":
        return any(("матриц" in name or "экран" in name) and value and "ips" not in value for name, value in spec_pairs)
    if canonical_wish == "height_adjustable":
        return any("регулировка" in name and "высот" in name and is_negative_spec_value(value) for name, value in spec_pairs)
    if canonical_wish == "32gb_ram":
        return any(("оператив" in name or "озу" in name) and parse_first_number(value) is not None and parse_first_number(value) != 32 for name, value in spec_pairs)
    if canonical_wish == "12gb_ram":
        return any(("оператив" in name or "озу" in name) and parse_first_number(value) is not None and parse_first_number(value) < 12 for name, value in spec_pairs)
    if canonical_wish == "storage_from_256_gb":
        return any(
            ("встроен" in name or "накопител" in name or ("памят" in name and "оператив" not in name and "озу" not in name))
            and parse_first_number(value) is not None
            and parse_first_number(value) < 256
            for name, value in spec_pairs
        )
    if canonical_wish == "240hz_screen":
        return any(("частота" in name and "экран" in name) and parse_first_number(value) is not None and parse_first_number(value) < 240 for name, value in spec_pairs)
    if canonical_wish == "refresh_rate_from_120hz":
        return any(("частота" in name and "экран" in name) and parse_first_number(value) is not None and parse_first_number(value) < 120 for name, value in spec_pairs)
    if canonical_wish == "refresh_rate_from_165hz":
        return any(("частота" in name and "экран" in name) and parse_first_number(value) is not None and parse_first_number(value) < 165 for name, value in spec_pairs)
    if canonical_wish == "weight_up_to_2.5_kg":
        return any("вес" in name and parse_first_number(value) is not None and parse_first_number(value) > 2.5 for name, value in spec_pairs)
    if canonical_wish == "weight_up_to_2.3_kg":
        return any("вес" in name and parse_first_number(value) is not None and parse_first_number(value) > 2.3 for name, value in spec_pairs)
    if canonical_wish == "matte_screen":
        return any(("покрытие" in name or "экран" in name) and value and "матов" not in value and "антиблик" not in value for name, value in spec_pairs)
    if canonical_wish in {"amoled_display", "matrix_type_amoled"}:
        return any(("матриц" in name or "экран" in name) and value and "amoled" not in value for name, value in spec_pairs)
    if canonical_wish == "matrix_type_oled":
        return any(("матриц" in name or "экран" in name) and value and "oled" not in value for name, value in spec_pairs)
    if canonical_wish == "matrix_type_ips":
        return any(("матриц" in name or "экран" in name) and value and "ips" not in value for name, value in spec_pairs)
    if canonical_wish == "matrix_type_va":
        return any(("матриц" in name or "экран" in name) and value and "va" not in value for name, value in spec_pairs)
    if canonical_wish == "matrix_type_qled":
        return any(("матриц" in name or "экран" in name) and value and "qled" not in value for name, value in spec_pairs)
    if canonical_wish == "network_5g":
        return any(("связ" in name or "стандарт" in name) and value and "5g" not in value for name, value in spec_pairs)
    if canonical_wish == "fast_charge":
        return any(("быстрая" in name and "заряд" in name) and is_negative_spec_value(value) for name, value in spec_pairs)
    if canonical_wish == "wireless_charge":
        return any(("беспровод" in name and "заряд" in name) and is_negative_spec_value(value) for name, value in spec_pairs)
    if canonical_wish == "waterproof_ip68":
        return any(("защит" in name or "ip" in name) and value and "ip68" not in value for name, value in spec_pairs)
    if canonical_wish == "waterproof_ip67":
        return any(("защит" in name or "ip" in name) and value and ("ip67" not in value and "ip68" not in value) for name, value in spec_pairs)
    if canonical_wish == "cooling_system_no_frost":
        freezer_specs = [value for name, value in spec_pairs if "морозиль" in name and "разморажив" in name]
        fridge_specs = [value for name, value in spec_pairs if "холодильн" in name and "разморажив" in name]
        return bool(freezer_specs and any("no_frost" not in value and "nofrost" not in value for value in freezer_specs)) or bool(
            fridge_specs and any("no_frost" not in value and "nofrost" not in value for value in fridge_specs)
        )
    if canonical_wish == "freezer_position_bottom":
        return any(("морозиль" in name or "располож" in name) and value and "снизу" not in value and "bottom" not in value for name, value in spec_pairs)
    if canonical_wish == "inverter_compressor":
        return any(("инвертор" in name or "инверторный" in name) and value and "инвертор" not in value and not is_positive_spec_value(value) for name, value in spec_pairs)
    if canonical_wish in {"sewing_operations_from_30", "sewing_operations"}:
        return any(
            ("швейн" in name or "операц" in name)
            and parse_first_number(value) is not None
            and parse_first_number(value) < 30
            for name, value in spec_pairs
        )
    if canonical_wish == "shuttle_type_horizontal":
        return any(("челнок" in name or "шаттл" in name) and ("вертик" in value or "oscillating" in value or "rotary" in value) for name, value in spec_pairs)
    if canonical_wish == "buttonhole_automatic":
        return any(("петл" in name or "buttonhole" in name) and "нет" in value for name, value in spec_pairs)
    if canonical_wish == "speed_control":
        return any(("скорост" in name or "регулиров" in name) and is_negative_spec_value(value) for name, value in spec_pairs)
    if canonical_wish == "work_area_light":
        return any(("подсвет" in name or "light" in name or "illumination" in name) and is_negative_spec_value(value) for name, value in spec_pairs)
    if canonical_wish == "keyboard_type_magnetic":
        return any(("тип_клавиатуры" in name or "переключател" in name or "switch" in name) and value and "магнит" not in value and "magnetic" not in value and "hall" not in value for name, value in spec_pairs)
    if canonical_wish == "keyboard_format_75_80":
        return any(("формат" in name or "раскладк" in name) and value and "75" not in value and "80" not in value and "tkl" not in value for name, value in spec_pairs)
    if canonical_wish == "rtx_4080":
        return any(("видеокарт" in name or "gpu" in name) and value and "rtx_4080" not in value and "geforce_rtx_4080" not in value for name, value in spec_pairs)
    if canonical_wish == "rtx_4070":
        return any(("видеокарт" in name or "gpu" in name) and value and "rtx_4070" not in value and "geforce_rtx_4070" not in value for name, value in spec_pairs)
    if canonical_wish == "rtx_4070_or_higher":
        return any(
            ("видеокарт" in name or "gpu" in name)
            and extract_rtx_mobile_class(value) is not None
            and not rtx_4070_or_higher_value_matches(value)
            for name, value in spec_pairs
        )
    if canonical_wish == "2024_year":
        return any(("год" in name or "релиз" in name) and value and "2024" not in value for name, value in spec_pairs)
    if canonical_wish == "year_from_2024":
        return any(("год" in name or "релиз" in name) and parse_first_number(value) is not None and parse_first_number(value) < 2024 for name, value in spec_pairs)
    return False


def find_monitor_diagonal_value(spec_pairs: list[tuple[str, str]], fallback_text: str) -> float | None:
    for name, value in spec_pairs:
        if "диагональ" in name:
            parsed = parse_first_number(value)
            if parsed is not None:
                return parsed
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:\"|дюйм)", fallback_text.casefold())
    if match is None:
        return None


def product_has_compact_listing_specs(product: Product) -> bool:
    specs = product.specs or []
    if not specs:
        return False
    names = [
        normalize_token(str(spec.get("name", "")))
        for spec in specs
        if isinstance(spec, dict)
    ]
    names = [name for name in names if name]
    if not names:
        return False
    # Листинговый формат DNS обычно отдаёт 1-3 агрегированных поля типа "Дополнительно".
    return len(names) <= 3 and all(name in COMPACT_LISTING_SPEC_NAMES for name in names)
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def is_positive_spec_value(value: str) -> bool:
    normalized = normalize_token(value)
    return normalized in {"есть", "да", "true", "поддерживается", "led", "светодиоды", "светодиод", "бесступенчатая", "ступенчатая"}


def is_negative_spec_value(value: str) -> bool:
    return value in {"нет", "false", "не_поддерживается", "отсутствует"}


def parse_first_number(value: str) -> float | None:
    match = NUMERIC_VALUE_RE.search(value.replace(" ", ""))
    if match is None:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def extract_rtx_mobile_class(value: str) -> int | None:
    normalized = normalize_token(value)
    match = re.search(r"rtx[_\s-]*(\d{4})", normalized)
    if match is None:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def rtx_4070_or_higher_value_matches(value: str) -> bool:
    gpu_class = extract_rtx_mobile_class(value)
    if gpu_class is None:
        return False
    generation = gpu_class // 100
    tier = gpu_class % 100
    return generation == 40 and tier >= 70


def build_comparison_summary(
    products: list[Product],
    normalized_request: NormalizedSearchRequest,
    coverage: list[dict[str, object]] | None = None,
    limit: int = 5,
) -> dict[str, object]:
    ranked = rank_products_for_request(products, normalized_request)
    if not ranked:
        return {}
    all_entries = [build_product_score_entry(product, normalized_request) for product in ranked]
    entries = all_entries[: max(1, limit)]
    price_leader = min(entries, key=comparison_price_sort_key)
    budget_defined = normalized_request.price_min is not None or normalized_request.price_max is not None
    segment_leaders = build_no_budget_segment_leaders(all_entries)
    leader = entries[0]
    has_hard_signals = bool(request_intent_signals(normalized_request))
    use_segment_leaders = not has_hard_signals
    if not has_hard_signals:
        value_leader = segment_leaders.get("value_leader") if isinstance(segment_leaders, dict) else None
        if isinstance(value_leader, dict):
            leader = value_leader
    elif budget_defined and str(leader.get("match_status", "")) != "exact":
        value_leader = segment_leaders.get("value_leader") if isinstance(segment_leaders, dict) else None
        if isinstance(value_leader, dict):
            leader = value_leader
    competitors = [
        {**entry, "score_gap_to_leader": leader["score"] - entry["score"]}
        for entry in entries
        if entry.get("url") != leader.get("url") or entry.get("name") != leader.get("name")
    ]
    all_candidates_rejected = all(str(entry.get("match_status", "")) == "rejected" for entry in entries)
    return {
        "top_pick": leader,
        "leader": leader,
        "price_pick": price_leader,
        "price_leader": price_leader,
        "segment_picks": segment_leaders,
        "segment_leaders": segment_leaders,
        "budget_defined": budget_defined,
        "use_segment_leaders": use_segment_leaders,
        "request_has_hard_signals": has_hard_signals,
        "other_candidates": competitors,
        "competitors": competitors,
        "all_candidates_rejected": all_candidates_rejected,
        "retrieval_evidence": coverage if isinstance(coverage, list) else [],
        "evidence_ledger": leader.get("signal_evidence", []),
        "request_profile": {
            "ranking_policy": normalized_request.ranking_policy,
            "price_band_hint": normalized_request.price_band_hint,
            "soft_wishes": list(normalized_request.soft_wishes),
            "price_min": normalized_request.price_min,
            "price_max": normalized_request.price_max,
        },
        "scoring": {
            "hard_wish_weight": 10,
            "soft_wish_weight": 4,
            "brand_weight": 3,
            "query_weight": 2,
        },
    }


def build_product_score_entry(product: Product, normalized_request: NormalizedSearchRequest) -> dict[str, object]:
    text = normalize_token(product.name)
    signal_text_parts = [product.name]
    if product.specs:
        for spec in product.specs:
            if not isinstance(spec, dict):
                continue
            text += " " + normalize_token(str(spec.get("name", "")))
            text += " " + normalize_token(str(spec.get("value", "")))
            signal_text_parts.append(str(spec.get("name", "")))
            signal_text_parts.append(str(spec.get("value", "")))
    signal_text = " ".join(part for part in signal_text_parts if str(part).strip())
    retrieval_tokens = request_retrieval_tokens(normalized_request)
    hard_matches = [wish for wish in retrieval_tokens if product_matches_wish(product, wish, text=text)]
    soft_matches = [wish for wish in normalized_request.soft_wishes if product_matches_wish(product, wish, text=text)]
    contradicted_hard = [
        wish
        for wish in retrieval_tokens
        if wish not in hard_matches and product_contradicts_wish(product, wish, text=text)
    ]
    missing_hard = [
        wish
        for wish in retrieval_tokens
        if wish not in hard_matches and wish not in contradicted_hard
    ]
    missing_soft = [wish for wish in normalized_request.soft_wishes if wish not in soft_matches]
    price_number = product.price if isinstance(product.price, int) else None
    brand_match = brand_matches_product(normalized_request.brand, product, text)
    effective_brand_match = brand_match if normalized_request.brand else True
    if normalized_request.brand and not brand_match:
        missing_hard = [*missing_hard, "brand"]
    if product_exceeds_price_max(product, normalized_request):
        contradicted_hard = [*contradicted_hard, "price_max"]
    details_confirmed_all_hard_wishes = bool(
        product_has_detailed_specs(product) and not missing_hard and not contradicted_hard
    )
    source_hard_wishes_count = request_source_signal_count(normalized_request)
    signal_evidence = build_signal_evidence(
        normalized_request,
        hard_matches,
        missing_hard,
        contradicted_hard,
    )
    return {
        "name": product.name,
        "url": product.url,
        "price": price_number,
        "score": score_product_for_request(product, normalized_request),
        "fit_score": score_product_for_request(product, normalized_request),
        "match_status": resolve_match_status(
            hard_matches,
            missing_hard,
            contradicted_hard,
            retrieval_tokens,
            effective_brand_match,
            source_hard_wishes_count,
        ),
        "matched_hard_wishes": hard_matches,
        "contradicted_hard_wishes": contradicted_hard,
        "matched_soft_wishes": soft_matches,
        "missing_hard_wishes": missing_hard,
        "missing_soft_wishes": missing_soft,
        "brand_match": brand_match,
        "query_match": bool(normalized_request.query and normalized_request.query in text),
        "brand_mismatch": bool(normalized_request.brand and not brand_match),
        "details_confirmed_all_hard_wishes": details_confirmed_all_hard_wishes,
        "source_hard_wishes_count": source_hard_wishes_count,
        "normalized_hard_wishes_count": len(retrieval_tokens),
        "source_signal_count": source_hard_wishes_count,
        "normalized_signal_count": len(request_intent_signals(normalized_request)),
        "confirmed_signals": display_wishes(hard_matches),
        "unconfirmed_signals": display_wishes(missing_hard),
        "contradicted_signals": display_wishes(contradicted_hard),
        "signal_evidence": signal_evidence,
        "soft_wish_signal_scores": {
            wish: soft_wish_signal_score(signal_text, wish)
            for wish in normalized_request.soft_wishes
            if wish in soft_matches
        },
    }


def build_signal_evidence(
    normalized_request: NormalizedSearchRequest,
    matched_tokens: list[str],
    missing_tokens: list[str],
    contradicted_tokens: list[str],
) -> list[dict[str, object]]:
    token_to_signal: dict[str, NormalizedConstraint] = {
        token: signal
        for token, signal in zip(request_retrieval_tokens(normalized_request), request_intent_signals(normalized_request))
    }
    evidence: list[dict[str, object]] = []
    for token in request_retrieval_tokens(normalized_request):
        status = "missing"
        if token in contradicted_tokens:
            status = "contradicted"
        elif token in matched_tokens:
            status = "confirmed"
        signal = token_to_signal.get(token)
        evidence.append(
            {
                "token": token,
                "label": display_wish(token),
                "status": status,
                "signal_key": signal.key if signal is not None else token,
                "source_text": signal.source_text if signal is not None else token,
            }
        )
    return evidence


def resolve_match_status(
    matched_hard: list[str],
    missing_hard: list[str],
    contradicted_hard: list[str],
    requested_hard: tuple[str, ...],
    brand_match: bool,
    source_hard_wishes_count: int = 0,
) -> str:
    if not brand_match:
        return "partial"
    if source_hard_wishes_count > len(requested_hard):
        return "partial"
    if not requested_hard:
        return "exact"
    if contradicted_hard:
        return "rejected"
    if missing_hard:
        return "partial"
    if matched_hard:
        return "exact"
    return "partial"


def display_wishes(wishes: object) -> list[str]:
    if not isinstance(wishes, (list, tuple)):
        return []
    return [display_wish(str(wish)) for wish in wishes if str(wish).strip()]


def display_wish(wish: str) -> str:
    canonical = canonicalize_wish(wish)
    return WISH_DISPLAY_NAMES.get(canonical, canonical.replace("_", " "))


def normalize_search_query_value(value: str) -> str:
    normalized = value.strip()
    normalized = PRICE_RANGE_RE.sub(" ", normalized)
    normalized = PRICE_SINGLE_RE.sub(" ", normalized)
    normalized = PRICE_BUCKET_TEXT_RE.sub(" ", normalized)
    normalized = re.sub(r"\b(?:найди|подбери|покажи|лучшую|лучший|лучшее|лучшие|за|с|и|или)\b", " ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s+", " ", normalized).strip(" ,.-")
    return normalized


def product_exceeds_price_max(product: Product, normalized_request: NormalizedSearchRequest) -> bool:
    return (
        isinstance(product.price, int)
        and isinstance(normalized_request.price_max, int)
        and product.price > normalized_request.price_max
    )


def choose_dns_search_query(primary_query: str, fallback_query: str, product_type_hint: str = "") -> str:
    for candidate in (product_type_hint, primary_query, fallback_query):
        normalized = normalize_search_query_value(candidate)
        if not normalized:
            continue
        inferred_type, inferred_query = infer_product_type_and_query(normalized)
        if inferred_type and inferred_type != "unknown":
            return inferred_query or normalized
        if CYRILLIC_RE.search(normalized) and len(normalized.split()) <= 3:
            return normalized
    primary = normalize_search_query_value(primary_query)
    fallback = normalize_search_query_value(fallback_query)
    if CYRILLIC_RE.search(primary):
        return primary
    if CYRILLIC_RE.search(fallback):
        return fallback
    return primary or fallback


def is_obvious_product_search_signal(text: str) -> bool:
    return SEARCH_INTENT_RE.search(text) is not None or extract_price_hint(text) is not None


def is_obvious_bot_meta_question(text: str) -> bool:
    if BOT_PROCESS_META_RE.search(text) is not None:
        return True
    return BOT_META_RE.search(text) is not None and not is_obvious_product_search_signal(text)


def is_obvious_followup_question(text: str) -> bool:
    return FOLLOWUP_RE.search(text) is not None


def is_format_followup_for_chat(
    text: str,
    history: list[dict[str, str]],
    memory_context: dict[str, object] | None,
) -> bool:
    if products_from_context(memory_context):
        return False
    if FORMAT_FOLLOWUP_RE.search(text) is None:
        return False
    if not history:
        return False
    last_assistant = ""
    for turn in reversed(history):
        if turn.get("role") == "assistant":
            last_assistant = str(turn.get("content", "")).strip()
            break
    if not last_assistant:
        return False
    if "Лидер анализа" in last_assistant:
        return False
    return True


def parse_optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def product_payload(product: Product) -> dict[str, object]:
    return {
        "name": product.name,
        "price": product.price,
        "url": product.url,
        "code": product.code,
        "specs": product.specs or [],
    }


def extract_raw_additional(product: Product) -> str:
    specs = product.specs or []
    compact_values: list[str] = []
    for spec in specs:
        if not isinstance(spec, dict):
            continue
        spec_name = normalize_token(str(spec.get("name", "")))
        spec_value = str(spec.get("value", "")).strip()
        if not spec_value:
            continue
        if spec_name in COMPACT_LISTING_SPEC_NAMES:
            compact_values.append(spec_value)
    if compact_values:
        return " | ".join(compact_values)
    fallback_values = [
        str(spec.get("value", "")).strip()
        for spec in specs
        if isinstance(spec, dict) and str(spec.get("value", "")).strip()
    ]
    return " | ".join(fallback_values[:3])


def device_llm_payload(product: Product, normalized_request: NormalizedSearchRequest | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": product.name,
        "price": product.price,
        "code": product.code,
        "raw_additional": extract_raw_additional(product),
    }
    facts = build_verified_facts(product)
    if facts:
        payload["normalized_fields"] = facts
    if normalized_request is not None:
        payload["fit_score"] = score_product_for_request(product, normalized_request)
    return payload


def analysis_product_payload(product: Product, normalized_request: NormalizedSearchRequest) -> dict[str, object]:
    payload = device_llm_payload(product, normalized_request)
    key_specs = pick_key_specs_for_request(product, normalized_request)
    payload["highlights"] = build_product_highlights(product, normalized_request, key_specs)
    payload["verified_facts"] = build_verified_facts(product)
    return payload


def build_verified_facts(product: Product) -> dict[str, object]:
    specs = product.specs or []
    spec_pairs = [
        (
            normalize_token(str(spec.get("name", ""))),
            str(spec.get("value", "")).strip(),
            normalize_token(str(spec.get("value", ""))),
        )
        for spec in specs
        if isinstance(spec, dict)
    ]
    facts: dict[str, object] = {}
    diagonal = find_monitor_diagonal_value([(name, normalized_value) for name, _raw, normalized_value in spec_pairs], product.name)
    if diagonal is not None:
        facts["diagonal_inches"] = diagonal
    for name, raw_value, normalized_value in spec_pairs:
        if name in {"максимальное_разрешение", "разрешение"}:
            facts["resolution"] = raw_value
        elif name in {"тип_матрицы", "тип_экрана"}:
            facts["matrix_type"] = raw_value
        elif name in {"частота_при_максимальном_разрешении", "максимальная_частота_обновления_экрана", "частота_обновления"}:
            refresh = parse_first_number(normalized_value)
            if refresh is not None:
                facts["refresh_rate_hz"] = int(refresh)
        elif name in {"регулировка_по_высоте", "регулировка_высоты"}:
            facts["height_adjustable"] = is_positive_spec_value(normalized_value)
        elif name == "usb-концентратор":
            facts["usb_hub"] = is_positive_spec_value(normalized_value)
        elif name == "поддержка_usb_power_delivery":
            facts["usb_power_delivery"] = is_positive_spec_value(normalized_value)
        elif name == "мощность_зарядки_usb_power_delivery":
            watts = parse_first_number(normalized_value)
            if watts is not None:
                facts["usb_power_delivery_watts"] = int(watts)
        elif name in {"видеоразъемы", "тип,_версия_и_количество_видеоразъемов"}:
            if "usb_type-c" in normalized_value or "usb_type_c" in normalized_value:
                facts["usb_type_c"] = True
    return facts


def pick_key_specs_for_request(product: Product, normalized_request: NormalizedSearchRequest) -> list[dict[str, str]]:
    if not product.specs:
        return []
    priority_spec_names = {
        "цена",
        "год релиза",
        "операционная система",
        "версия ос",
        "оболочка ос",
        "модель процессора",
        "процессор",
        "ядра процессора",
        "объем оперативной памяти",
        "оперативная память",
        "объем встроенной памяти",
        "встроенная память",
        "разрешение",
        "частота обновления",
        "тип матрицы",
        "тип экрана",
        "диагональ",
    }
    priority_terms = tuple(
        filter(
            None,
            (
                normalized_request.query,
                normalized_request.brand,
                *normalized_request.wishes,
                *normalized_request.soft_wishes,
            ),
        )
    )
    ranked: list[tuple[int, dict[str, str]]] = []
    for index, spec in enumerate(product.specs):
        if not isinstance(spec, dict):
            continue
        name = str(spec.get("name", "")).strip()
        value = str(spec.get("value", "")).strip()
        if not name or not value:
            continue
        spec_text = f"{name} {value}".casefold()
        relevance = 0
        for term in priority_terms:
            normalized_term = normalize_token(term)
            if normalized_term and normalized_term in normalize_token(spec_text):
                relevance += 5
        if name.casefold() in priority_spec_names:
            relevance += 2
        ranked.append((-(relevance), {"name": name, "value": value, "_index": str(index)}))
    ranked.sort(key=lambda item: (item[0], int(item[1]["_index"])))
    return [{"name": item[1]["name"], "value": item[1]["value"]} for item in ranked[:5]]


def build_product_highlights(
    product: Product,
    normalized_request: NormalizedSearchRequest,
    key_specs: list[dict[str, str]],
) -> list[str]:
    highlights: list[str] = []
    if normalized_request.brand and normalized_request.brand.casefold() in normalize_token(product.name):
        highlights.append("бренд совпадает с запросом")
    if normalized_request.query and normalized_request.query.casefold() in normalize_token(product.name):
        highlights.append("категория совпадает с запросом")
    if key_specs:
        for spec in key_specs[:3]:
            spec_name = normalize_token(spec["name"])
            spec_value = spec["value"].strip()
            normalized_value = normalize_token(spec_value)
            if is_negative_spec_value(normalized_value):
                continue
            if normalized_value == normalize_token(normalized_request.query):
                continue
            if spec_name in {"диагональ", "размер_экрана", "диагональ_экрана", "диагональ_экрана_(дюйм)"}:
                highlights.append(f"подходит по размеру: {spec_value}")
            elif spec_name in {"разрешение", "четкость", "максимальное_разрешение"}:
                highlights.append(f"подходит по разрешению: {spec_value}")
            elif spec_name in {"матрица", "тип_матрицы", "тип_экрана"}:
                highlights.append(f"подходит по матрице: {spec_value}")
            elif spec_name in {"частота_обновления", "герцовка", "максимальная_частота_обновления_экрана_(гц)"}:
                highlights.append(f"подходит по частоте: {spec_value}")
            elif spec_name in {"регулировка_высоты", "регулировка_по_высоте", "подставка"}:
                highlights.append("есть регулировка высоты")
            else:
                highlights.append(f"важный признак: {spec_value}")
    if not highlights:
        highlights.append("подходит по базовой категории и бюджету")
    return highlights[:4]


def count_products_with_specs(products: list[Product]) -> int:
    return sum(1 for product in products if product.specs)


def trim_log_value(value: str, limit: int = 200) -> str:
    return value if len(value) <= limit else value[: limit - 3] + "..."


def log_ai_chain_step(step: str, **details: object) -> None:
    if details:
        serialized = " ".join(
            f"{key}={trim_log_value(str(value))}"
            for key, value in details.items()
            if value not in ("", None)
        )
        logger.info("ai_chain_step step=%s %s", step, serialized)
        return
    logger.info("ai_chain_step step=%s", step)


def build_context_payload(
    products: list[Product],
    resolved_url: str,
    stats: dict[str, int],
    section_url: str = "",
    filters_map_summary: dict[str, object] | None = None,
    filters_llm: dict[str, object] | None = None,
    filter_trace: dict[str, object] | None = None,
    normalized_request: NormalizedSearchRequest | None = None,
    comparison_summary: dict[str, object] | None = None,
) -> dict[str, object]:
    payload = {
        "resolved_url": resolved_url,
        "stats": stats,
        "products": [product_payload(product) for product in products],
    }
    if section_url:
        payload["section_url"] = section_url
    if isinstance(filters_map_summary, dict) and filters_map_summary:
        payload["filters_map_summary"] = filters_map_summary
    if isinstance(filters_llm, dict) and filters_llm:
        payload["filters_llm"] = filters_llm
    if isinstance(filter_trace, dict) and filter_trace:
        payload["filter_trace"] = filter_trace
    if normalized_request is not None:
        payload["normalized_request"] = normalized_request_payload(normalized_request)
    if isinstance(comparison_summary, dict) and comparison_summary:
        payload["comparison_summary"] = comparison_summary
    return payload


def normalized_request_payload(request: NormalizedSearchRequest) -> dict[str, object]:
    intent_signals = request_intent_signals(request)
    retrieval_tokens = request_retrieval_tokens(request)
    return {
        "product_type": request.product_type,
        "query": request.query,
        "price_min": request.price_min,
        "price_max": request.price_max,
        "brand": request.brand,
        "ranking_policy": request.ranking_policy,
        "price_band_hint": request.price_band_hint,
        "source_signal_count": request_source_signal_count(request),
        "intent_signals": [constraint_payload(item) for item in intent_signals],
        "retrieval_tokens": list(retrieval_tokens),
        "soft_wishes": list(request.soft_wishes),
    }


def products_from_context(memory_context: dict[str, object] | None) -> list[Product]:
    if not memory_context:
        return []
    raw_products = memory_context.get("products", [])
    if not isinstance(raw_products, list):
        return []
    products: list[Product] = []
    for item in raw_products:
        if not isinstance(item, dict):
            continue
        products.append(
            Product(
                name=str(item.get("name", "")),
                price=item.get("price") if isinstance(item.get("price"), int) else None,
                url=str(item.get("url", "")),
                code=str(item.get("code", "")),
                specs=item.get("specs") if isinstance(item.get("specs"), list) else None,
            )
        )
    return products


def summarize_context_products(memory_context: dict[str, object] | None) -> list[dict[str, object]]:
    return [product_payload(product) for product in products_from_context(memory_context)[:SHORTLIST_LIMIT]]


def preserve_context_payload(memory_context: dict[str, object] | None) -> dict[str, object]:
    if not isinstance(memory_context, dict):
        return {}
    resolved_url = memory_context.get("resolved_url", "")
    section_url = memory_context.get("section_url", "")
    stats = memory_context.get("stats", {})
    products = memory_context.get("products", [])
    filters_map_summary = memory_context.get("filters_map_summary", {})
    normalized_request = memory_context.get("normalized_request", {})
    return {
        "resolved_url": resolved_url if isinstance(resolved_url, str) else "",
        "section_url": section_url if isinstance(section_url, str) else "",
        "stats": stats if isinstance(stats, dict) else {},
        "products": products if isinstance(products, list) else [],
        "filters_map_summary": filters_map_summary if isinstance(filters_map_summary, dict) else {},
        "normalized_request": normalized_request if isinstance(normalized_request, dict) else {},
    }


def build_filters_map_summary(filters_map: dict[str, object]) -> dict[str, object]:
    filters = filters_map.get("filters", [])
    if not isinstance(filters, list):
        return {}
    return {
        "count": len(filters),
        "filters": [
            {
                "id": str(item.get("id", "")),
                "name": str(item.get("name", "")),
                "type": str(item.get("type", "")),
                "values_count": len(item.get("values", [])) if isinstance(item.get("values", []), list) else 0,
            }
            for item in filters
            if isinstance(item, dict)
        ],
    }


def classify_filter_kind(filter_block: dict[str, object]) -> tuple[str, str, str]:
    raw_type = normalize_token(str(filter_block.get("type", "")))
    name = normalize_token(str(filter_block.get("name", "")))
    values = filter_block.get("values", [])
    value_names = [
        normalize_token(str(item.get("name", "")))
        for item in values
        if isinstance(item, dict)
    ] if isinstance(values, list) else []
    if raw_type == "toggle":
        return "boolean", "toggle", "service" if name in {"наличие", "рейтинг_4_и_выше", "хит_продаж"} else "product_spec"
    if raw_type == "shops":
        return "service", "shops", "service"
    if raw_type == "range-radio":
        return "range", "free_range", "product_spec"
    if raw_type == "range-checkbox":
        return "range" if str(filter_block.get("id", "")).startswith("fr[") else "range_enum", "free_range" if str(filter_block.get("id", "")).startswith("fr[") else "discrete_values", "product_spec"
    if raw_type == "checkbox":
        bool_like = value_names and all(value in {"есть", "нет", "да", "true", "false"} for value in value_names[: min(len(value_names), 4)])
        return ("boolean", "discrete_values", "product_spec") if bool_like else ("enum", "discrete_values", "service" if name in {"магазины", "наличие"} else "product_spec")
    return "unknown", "unknown", "product_spec"


def build_filters_llm(filters_map: dict[str, object]) -> dict[str, object]:
    filters = filters_map.get("filters", [])
    if not isinstance(filters, list):
        return {}
    groups: dict[str, list[dict[str, object]]] = {}
    for item in filters:
        if not isinstance(item, dict):
            continue
        group = str(item.get("group", "")).strip() or "Без группы"
        kind, input_mode, role = classify_filter_kind(item)
        entry: dict[str, object] = {
            "id": str(item.get("id", "")),
            "name": str(item.get("name", "")),
            "kind": kind,
            "role": role,
        }
        if input_mode != "unknown":
            entry["input_mode"] = input_mode
        values = item.get("values", [])
        if isinstance(values, list) and values:
            sample_values = [str(value.get("name", "")) for value in values if isinstance(value, dict) and str(value.get("name", "")).strip()][:6]
            if sample_values and kind in {"enum", "range_enum"}:
                entry["value_examples"] = sample_values
            if kind == "range_enum":
                entry["value_count"] = len(values)
        groups.setdefault(group, []).append(entry)
    return {
        "groups": [{"name": name, "filters": entries} for name, entries in groups.items()],
        "filters_count": len(filters),
    }


def comparison_summary_requires_teacher_guard(comparison_summary: dict[str, object]) -> bool:
    return False


def comparison_price_sort_key(entry: dict[str, object]) -> tuple[int, int, str]:
    price = entry.get("price")
    score = entry.get("score")
    return (
        price if isinstance(price, int) else 999999999,
        -(score if isinstance(score, int) else 0),
        str(entry.get("name", "")),
    )


def comparison_value_sort_key(entry: dict[str, object]) -> tuple[int, int, str]:
    price = entry.get("price")
    score = entry.get("score")
    return (
        -(score if isinstance(score, int) else 0),
        price if isinstance(price, int) else 999999999,
        str(entry.get("name", "")),
    )


def comparison_spec_sort_key(entry: dict[str, object]) -> tuple[int, int, str]:
    price = entry.get("price")
    score = entry.get("score")
    return (
        -(score if isinstance(score, int) else 0),
        -(price if isinstance(price, int) else 0),
        str(entry.get("name", "")),
    )


def build_no_budget_segment_leaders(entries: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    priced_entries = [entry for entry in entries if isinstance(entry.get("price"), int)]
    if not priced_entries:
        return {}
    ordered = sorted(priced_entries, key=comparison_price_sort_key)
    if len(ordered) == 1:
        only = ordered[0]
        return {"price_leader": only, "value_leader": only, "spec_leader": only}
    budget_cutoff = max(1, len(ordered) // 3)
    spec_start = max(budget_cutoff + 1, (2 * len(ordered)) // 3)
    budget_pool = ordered[:budget_cutoff]
    value_pool = ordered[budget_cutoff:spec_start] or ordered
    spec_pool = ordered[spec_start:] or ordered[-max(1, len(ordered) // 3):]
    value_leader = sorted(value_pool, key=comparison_value_sort_key)[0]
    strongest_soft_signal = min(priced_entries, key=soft_signal_value_sort_key)
    current_soft_signal = aggregate_soft_signal_score(value_leader)
    strongest_soft_score = aggregate_soft_signal_score(strongest_soft_signal)
    if strongest_soft_score > 0 and (current_soft_signal == 0 or strongest_soft_score >= int(current_soft_signal * 1.2)):
        value_leader = strongest_soft_signal
    return {
        "price_leader": budget_pool[0],
        "value_leader": value_leader,
        "spec_leader": sorted(spec_pool, key=comparison_spec_sort_key)[0],
    }


def aggregate_soft_signal_score(entry: dict[str, object]) -> int:
    raw_scores = entry.get("soft_wish_signal_scores", {})
    if not isinstance(raw_scores, dict):
        return 0
    total = 0
    for value in raw_scores.values():
        if isinstance(value, (int, float)):
            total += int(value)
    return total


def soft_signal_value_sort_key(entry: dict[str, object]) -> tuple[int, int, int, str]:
    price = entry.get("price")
    score = entry.get("score")
    return (
        -aggregate_soft_signal_score(entry),
        -(score if isinstance(score, int) else 0),
        price if isinstance(price, int) else 999999999,
        str(entry.get("name", "")),
    )


def soft_wish_signal_score(text: str, wish: str) -> int:
    normalized = text.casefold()
    if wish == "good_battery":
        values = [
            parsed
            for value in re.findall(r"(\d[\d\s.,]*)\s*(?:м?а·?ч|мач|mah|wh)\b", normalized, re.IGNORECASE)
            if (parsed := parse_numeric_metric_value(value)) is not None
        ]
        return max(values, default=0)
    if wish == "good_camera":
        values = [
            parsed
            for value in re.findall(r"(\d[\d\s.,]*)\s*(?:мп|mp)\b", normalized, re.IGNORECASE)
            if (parsed := parse_numeric_metric_value(value)) is not None
        ]
        if not values:
            return 0
        return max(values) + min(len(values), 5) * 10
    if wish == "good_performance":
        antutu_values = [
            parsed
            for value in re.findall(r"(?:antutu|антуту)[^\d]{0,24}(\d[\d\s.,]*)", normalized, re.IGNORECASE)
            if (parsed := parse_numeric_metric_value(value)) is not None
        ]
        if antutu_values:
            return max(antutu_values)
        return 0
    if wish == "bright_screen":
        values = [
            parsed
            for value in re.findall(r"(\d[\d\s.,]*)\s*(?:нит|nits|кд/м²|кд/м2|cd/m2|cd/m²)\b", normalized, re.IGNORECASE)
            if (parsed := parse_numeric_metric_value(value)) is not None
        ]
        return max(values, default=0)
    if wish == "good_navigation":
        return 100 if re.search(r"(лидар|lidar|навигац|mapping)", normalized, re.IGNORECASE) else 0
    return 0


def build_no_products_analysis_answer(
    normalized_request: NormalizedSearchRequest,
    _resolved_url: str,
) -> str:
    constraints = build_no_products_constraints_summary(normalized_request)
    relaxations = build_no_products_relaxation_suggestions(normalized_request)
    if constraints:
        return (
            "По заданным фильтрам товаров не найдено.\n"
            f"Точного совпадения нет: одновременно не нашлось модели с {constraints}.\n"
            f"Рекомендуется ослабить одно из условий: {relaxations}."
        )
    return (
        "По заданным фильтрам товаров не найдено.\n"
        "Точного совпадения нет.\n"
        f"Рекомендуется ослабить одно из условий: {relaxations}."
    )


def humanize_constraint(constraint: NormalizedConstraint) -> str:
    key = normalize_token(constraint.key)
    value = str(constraint.value).strip()
    numeric = constraint_numeric_value(constraint)
    if key == "storage" and numeric is not None and constraint.op == ">=":
        return f"накопителем от {int(numeric)} ГБ"
    if key == "storage" and numeric is not None and constraint.op == "==":
        return f"накопителем {int(numeric)} ГБ"
    if key == "ram" and numeric is not None and constraint.op == ">=":
        return f"ОЗУ от {int(numeric)} ГБ"
    if key == "ram" and numeric is not None and constraint.op == "==":
        return f"ОЗУ {int(numeric)} ГБ"
    if key == "refresh_rate" and numeric is not None and constraint.op == ">=":
        return f"экраном {int(numeric)}+ Гц"
    if key == "brightness" and numeric is not None and constraint.op == ">=":
        return f"яркостью экрана от {int(numeric)} нит"
    if key == "matrix_type":
        if "amoled" in normalize_token(value):
            return "AMOLED/OLED-экраном"
        return f"экраном {value.upper()}"
    if key == "network" and "5g" in normalize_token(value):
        return "5G"
    if key == "nfc":
        return "NFC"
    if key == "protection":
        return f"защитой {value.upper()}"
    if key == "fast_charge":
        return "быстрой зарядкой"
    if key == "wireless_charge":
        return "беспроводной зарядкой"
    if key == "year" and numeric is not None and constraint.op == ">=":
        return f"годом релиза {int(numeric)}+"
    if key == "weight" and numeric is not None and constraint.op == "<=":
        return f"весом до {numeric:g} кг"
    if key == "gpu" and constraint.op == ">=":
        return f"видеокартой {value.upper()} или выше"
    if key == "screen_finish" and "matte" in normalize_token(value):
        return "матовым экраном"
    if key == "cooling_system" and "no_frost" in normalize_token(value).replace("-", "_"):
        return "No Frost"
    if key == "freezer_position" and ("bottom" in normalize_token(value) or "снизу" in normalize_token(value)):
        return "морозильной камерой снизу"
    if key == "inverter_compressor" and normalize_token(value) in {"true", "inverter", "yes", "есть", "1"}:
        return "инверторным компрессором"
    if key == "sewing_operations" and numeric is not None and constraint.op == ">=":
        return f"не меньше {int(numeric)} швейных операций"
    if key == "sewing_operations" and numeric is not None and constraint.op == "==":
        return f"{int(numeric)} швейных операций"
    if key == "shuttle_type" and "horizontal" in normalize_token(value):
        return "горизонтальным челноком"
    if key == "buttonhole" and "automatic" in normalize_token(value):
        return "автоматическим выполнением петли"
    if key == "speed_control" and normalize_token(value) in {"true", "yes", "есть", "1"}:
        return "регулировкой скорости шитья"
    if key == "work_area_light" and normalize_token(value) in {"true", "yes", "есть", "1"}:
        return "подсветкой рабочей зоны"
    if key == "power" and numeric is not None and constraint.op == ">=":
        return f"мощностью от {int(numeric)} Вт"
    if key == "removable_panels" and normalize_token(value) in {"true", "yes", "есть", "1"}:
        return "съёмными панелями"
    if key == "nonstick_coating" and normalize_token(value) in {"true", "yes", "есть", "1"}:
        return "антипригарным покрытием"
    if key == "temperature_control" and normalize_token(value) in {"true", "yes", "есть", "1"}:
        return "регулировкой температуры"
    if key == "grease_tray" and normalize_token(value) in {"true", "yes", "есть", "1"}:
        return "поддоном для жира"
    if key == "opens_180" and normalize_token(value) in {"true", "yes", "есть", "1"}:
        return "раскрытием на 180 градусов"
    if key == "smartphone_control" and normalize_token(value) in {"true", "yes", "есть", "1"}:
        return "управлением со смартфона"
    if key == "battery_capacity" and numeric is not None and constraint.op == ">=":
        return f"аккумулятором от {int(numeric)} мА·ч"
    if key == "auto_return_to_base" and normalize_token(value) in {"true", "yes", "есть", "1"}:
        return "автоматическим возвращением на базу"
    if key == "dustbin_easy_cleaning" and normalize_token(value) in {"true", "yes", "есть", "1"}:
        return "простой очисткой контейнера"
    if key == "good_navigation" and normalize_token(value) in {"true", "yes", "есть", "1"}:
        return "хорошей навигацией"
    if key == "noise_canceling" and normalize_token(value) in {"true", "yes", "есть", "1"}:
        return "шумоподавлением"
    if key == "device_type" and "mfp" in normalize_token(value):
        return "лазерным МФУ"
    if key == "print_technology" and "laser" in normalize_token(value):
        return "лазерной печатью"
    if key == "color_mode" and "mono" in normalize_token(value):
        return "черно-белой печатью"
    if key == "wifi" and normalize_token(value) in {"true", "yes", "есть", "1"}:
        return "Wi-Fi"
    if key == "duplex_print" and normalize_token(value) in {"true", "yes", "есть", "1"}:
        return "двусторонней печатью"
    if key == "scanner" and normalize_token(value) in {"true", "yes", "есть", "1"}:
        return "сканером"
    if key == "print_speed" and numeric is not None and constraint.op == ">=":
        return f"скоростью от {int(numeric)} стр/мин"
    if key == "refill_easy" and normalize_token(value) in {"true", "yes", "есть", "1"}:
        return "простой заправкой"
    if key == "cheap_maintenance" and normalize_token(value) in {"true", "yes", "есть", "1"}:
        return "недорогим обслуживанием"
    if key == "resistance_system" and "magnetic" in normalize_token(value):
        return "магнитной системой нагрузки"
    if key == "max_user_weight" and numeric is not None and constraint.op == ">=":
        return f"весом пользователя от {int(numeric)} кг"
    if key == "seat_adjustment" and normalize_token(value) in {"true", "yes", "есть", "1"}:
        return "регулировкой сиденья"
    if key == "display" and normalize_token(value) in {"true", "yes", "есть", "1"}:
        return "дисплеем"
    if key == "pulse_measurement" and normalize_token(value) in {"true", "yes", "есть", "1"}:
        return "измерением пульса"
    if key == "resistance_levels" and numeric is not None and constraint.op == ">=":
        return f"не меньше {int(numeric)} уровней нагрузки"
    if key == "stable_construction" and normalize_token(value) in {"true", "yes", "есть", "1"}:
        return "устойчивой конструкцией"
    if key == "machine_type" and "automatic" in normalize_token(value):
        return "автоматической кофемашиной"
    if key == "cappuccinator" and normalize_token(value) in {"true", "yes", "есть", "1"}:
        return "капучинатором"
    if key == "pressure" and numeric is not None and constraint.op == ">=":
        return f"давлением от {int(numeric)} бар"
    if key == "built_in_grinder" and normalize_token(value) in {"true", "yes", "есть", "1"}:
        return "встроенной кофемолкой"
    if key == "strength_adjustment" and normalize_token(value) in {"true", "yes", "есть", "1"}:
        return "регулировкой крепости"
    if key == "portion_volume_adjustment" and normalize_token(value) in {"true", "yes", "есть", "1"}:
        return "регулировкой объема порции"
    if key == "self_cleaning" and normalize_token(value) in {"true", "yes", "есть", "1"}:
        return "самоочисткой"
    if key == "easy_maintenance" and normalize_token(value) in {"true", "yes", "есть", "1"}:
        return "простым обслуживанием"
    if key == "reliable" and normalize_token(value) in {"true", "yes", "есть", "1"}:
        return "надежной сборкой"
    if key == "width" and numeric is not None and constraint.op == "<=":
        return f"шириной до {numeric:g} см"
    if key == "volume" and numeric is not None and constraint.op == ">=":
        return f"объёмом от {numeric:g} л"
    if key == "energy_class":
        return f"классом энергопотребления не ниже {value.upper()}"
    return ""


def build_no_products_constraints_summary(normalized_request: NormalizedSearchRequest) -> str:
    parts: list[str] = []
    if normalized_request.brand:
        parts.append(f"брендом {normalized_request.brand.upper()}")
    parts.extend(
        deduplicate_display_wishes(
            [humanize_constraint(constraint) for constraint in normalized_request.constraints if humanize_constraint(constraint)]
            or display_wishes(normalized_request.wishes)
        )
    )
    price_text = build_no_products_budget_text(normalized_request)
    if price_text:
        parts.append(price_text)
    return ", ".join(parts)


def build_no_products_relaxation_suggestions(normalized_request: NormalizedSearchRequest) -> str:
    suggestions: list[str] = []
    effective_constraints = normalized_request.constraints or constraints_from_legacy_wishes(normalized_request.wishes)
    for constraint in effective_constraints:
        label = NO_MATCH_RELAX_LABELS.get(normalize_token(constraint.key), "")
        if label:
            suggestions.append(label)
    if normalized_request.price_max is not None:
        suggestions.append("бюджет")
    if not suggestions:
        suggestions = ["бюджет", "один из жёстких критериев"]
    return ", ".join(list(dict.fromkeys(suggestions[:3])))


def build_no_products_budget_text(normalized_request: NormalizedSearchRequest) -> str:
    price_min = normalized_request.price_min
    price_max = normalized_request.price_max
    if isinstance(price_min, int) and isinstance(price_max, int):
        if price_min <= 0:
            return f"бюджетом до {format_price_value(price_max).replace(' руб.', ' ₽')}"
        return (
            "бюджетом от "
            f"{format_price_value(price_min).replace(' руб.', ' ₽')} "
            f"до {format_price_value(price_max).replace(' руб.', ' ₽')}"
        )
    if isinstance(price_max, int):
        return f"бюджетом до {format_price_value(price_max).replace(' руб.', ' ₽')}"
    if isinstance(price_min, int):
        return f"бюджетом от {format_price_value(price_min).replace(' руб.', ' ₽')}"
    return ""


def deduplicate_display_wishes(wishes: list[str]) -> list[str]:
    return list(dict.fromkeys(wishes))


def format_price_value(price: int | None) -> str:
    if price is None:
        return "цена не указана"
    return f"{price:,} руб.".replace(",", " ")
