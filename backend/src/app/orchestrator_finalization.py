from __future__ import annotations

import re

from .dns_search_parser import Product


def ensure_complete_analysis_answer(answer: str, products: list[Product]) -> str:
    if answer.strip():
        cleaned_answer = answer.strip()
        if (
            cleaned_answer.startswith("Лучший вариант")
            and "\nПочему он подходит" in cleaned_answer
            and "\nЧто сильнее у альтернатив" in cleaned_answer
            and "\nКомпромиссы и проверки" in cleaned_answer
        ):
            return cleaned_answer
        sections = parse_analysis_sections(answer)
        leader = sections.get("Лучший вариант", "").strip() or sections.get("Лидер анализа", "").strip() or sections.get("Ближайшие аналоги", "").strip()
        reasons = sections.get("Почему он подходит", "").strip()
        alternative = sections.get("Что сильнее у альтернатив", "").strip() or sections.get("Альтернатива", "").strip()
        critical = sections.get("Компромиссы и проверки", "").strip() or sections.get("Критическое резюме", "").strip()
        if not reasons and leader:
            reasons = "Исходный ответ не разделял мотивацию отдельным блоком; сохранены только уже присутствующие факты."
        if leader and reasons and alternative and critical:
            return (
                f"Лучший вариант\n{leader}\n\n"
                f"Почему он подходит\n{reasons}\n\n"
                f"Что сильнее у альтернатив\n{alternative}\n\n"
                f"Компромиссы и проверки\n{critical}"
            ).strip()
        return answer.strip()
    sections = parse_analysis_sections(answer)
    leader = sections.get("Лучший вариант", "").strip() or build_leader_block(products)
    reasons = sections.get("Почему он подходит", "").strip() or "Выбор сделан по текущему ранжированию и подтверждённым фактам карточки."
    alternative = sections.get("Что сильнее у альтернатив", "").strip() or build_alternative_block(products)
    critical = sections.get("Компромиссы и проверки", "").strip() or build_critical_block(products)
    return (
        f"Лучший вариант\n{leader}\n\n"
        f"Почему он подходит\n{reasons}\n\n"
        f"Что сильнее у альтернатив\n{alternative}\n\n"
        f"Компромиссы и проверки\n{critical}"
    ).strip()


def extract_chat_format_constraints(question: str) -> dict[str, object]:
    lowered = question.casefold()
    normalized = normalize_token(question)
    max_sentences = 0
    sentence_match = re.search(r"\b([12])\s+предлож", lowered)
    if sentence_match is not None:
        max_sentences = int(sentence_match.group(1))
    elif "два_предлож" in normalized:
        max_sentences = 2
    elif "одно_предлож" in normalized:
        max_sentences = 1
    return {
        "no_list": "без_списка" in normalized,
        "one_paragraph": "одним_абзацем" in normalized,
        "max_sentences": max_sentences,
    }


def enforce_chat_answer_constraints(answer: str, constraints: dict[str, object]) -> str:
    if constraints.get("no_list"):
        lines = []
        for raw_line in answer.replace("\r", "\n").splitlines():
            stripped = raw_line.strip()
            stripped = re.sub(r"^(?:[-•*]\s+|\d+[.)]\s+)", "", stripped)
            if stripped:
                lines.append(stripped)
        result = " ".join(lines)
    else:
        result = sanitize_chat_teacher_text(answer)
    if constraints.get("one_paragraph"):
        result = " ".join(part.strip() for part in result.splitlines() if part.strip())
    max_sentences = int(constraints.get("max_sentences", 0) or 0)
    if max_sentences > 0:
        sentences = split_sentences(result)
        if len(sentences) > max_sentences:
            result = " ".join(sentences[:max_sentences]).strip()
    return sanitize_chat_teacher_text(result)


def sanitize_chat_teacher_text(value: str) -> str:
    cleaned = " ".join(part.strip() for part in value.replace("\r", "\n").splitlines() if part.strip())
    return re.sub(r"\s+", " ", cleaned).strip()


def split_sentences(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", value.strip()) if part.strip()]


def ensure_teacher_checked_analysis_answer(
    answer: str,
    products: list[Product],
    comparison_summary: dict[str, object],
) -> str:
    if looks_like_raw_structured_analysis_answer(answer):
        answer = ""
    completed = ensure_complete_analysis_answer(answer, products)
    if not products and completed:
        if completed.startswith("Лучший вариант"):
            return sanitize_analysis_answer_format(completed)
        sections = parse_analysis_sections(completed)
        leader = sections.get("Лучший вариант", "").strip() or sections.get("Лидер анализа", "").strip() or completed.strip()
        alternative = sections.get("Что сильнее у альтернатив", "").strip() or sections.get("Альтернатива", "").strip() or "Отдельная альтернатива не была сформулирована."
        critical = sections.get("Компромиссы и проверки", "").strip() or sections.get("Критическое резюме", "").strip() or "Спорные параметры стоит перепроверить вручную."
        rebuilt = (
            f"Лучший вариант\n{leader}\n\n"
            f"Почему он подходит\nИсходный ответ не разделял мотивацию по новой схеме, поэтому сохранён только уже присутствующий смысл без новых фактов.\n\n"
            f"Что сильнее у альтернатив\n{alternative}\n\n"
            f"Компромиссы и проверки\n{critical}"
        )
        return sanitize_analysis_answer_format(rebuilt)
    corrected = build_teacher_corrected_analysis_answer(products, comparison_summary)
    return sanitize_analysis_answer_format(corrected or completed)


def answer_violates_teacher_contract(answer: str, comparison_summary: dict[str, object]) -> bool:
    lowered = answer.casefold()
    leaked_markers = (
        "лидер анализа",
        "ближайшие аналоги",
        "альтернатива",
        "критическое резюме",
        "spec_leader",
        "value_leader",
        "price_leader",
        "fit_score",
        "shortlist",
        "ranking_policy",
        "coverage",
        "ledger",
    )
    if any(marker in lowered for marker in leaked_markers):
        return True
    leader = comparison_summary.get("leader", {})
    if not isinstance(leader, dict):
        return False
    match_status = str(leader.get("match_status", "")).casefold()
    details_confirmed = bool(leader.get("details_confirmed_all_hard_wishes"))
    if match_status in {"partial", "rejected"} and "точного совпадения нет" not in lowered:
        return True
    return "полностью соответствует" in lowered and (match_status != "exact" or not details_confirmed)


def build_teacher_corrected_analysis_answer(
    products: list[Product],
    comparison_summary: dict[str, object],
) -> str:
    leader = comparison_summary.get("leader", {})
    competitors = comparison_summary.get("competitors", [])
    segment_leaders = comparison_summary.get("segment_leaders", {})
    request_profile = comparison_summary.get("request_profile", {})
    if not isinstance(leader, dict):
        return ensure_complete_analysis_answer("", products)
    if isinstance(segment_leaders, dict) and segment_leaders:
        derived_competitors: list[dict[str, object]] = []
        leader_name = str(leader.get("name", "")).strip()
        for key in ("value_leader", "price_leader", "spec_leader"):
            candidate = segment_leaders.get(key)
            if isinstance(candidate, dict) and str(candidate.get("name", "")).strip() and str(candidate.get("name", "")).strip() != leader_name:
                derived_competitors.append(candidate)
        if derived_competitors:
            competitors = derived_competitors
    leader_name = str(leader.get("name", "Лидер не определён")).strip() or "Лидер не определён"
    leader_price = format_price_value(leader.get("price") if isinstance(leader.get("price"), int) else None)
    match_status = str(leader.get("match_status", "")).casefold()
    leader_matched = display_wishes(leader.get("matched_hard_wishes", []))
    leader_missing = display_wishes(leader.get("missing_hard_wishes", []))
    leader_contradicted = display_wishes(leader.get("contradicted_hard_wishes", []))
    if match_status in {"partial", "rejected"} or bool(comparison_summary.get("all_candidates_rejected")):
        leader_intro = "Точного совпадения нет."
        reasons_parts = ["Точного совпадения нет. Это лучший из найденных вариантов, но не точное совпадение под запрос."]
        if leader_matched:
            reasons_parts.append("Совпадает по: " + ", ".join(leader_matched) + ".")
        if leader_missing:
            reasons_parts.append("Не подтверждено: " + ", ".join(leader_missing) + ".")
        if leader_contradicted:
            reasons_parts.append("противоречит карточке по: " + ", ".join(leader_contradicted) + ".")
        else:
            reasons_parts.append("Часть условий противоречит карточке или не подтверждена полностью.")
    else:
        leader_intro = build_leader_intro(leader, request_profile)
        reasons_parts = ["По карточке подтверждены основные сигналы запроса."]
    leader_facts = extract_request_facts_for_entry(leader, products, request_profile)
    if leader_facts:
        reasons_parts.append("Ключевые факты по карточке: " + "; ".join(leader_facts) + ".")
    if "good_camera" in [normalize_token(str(item)) for item in request_profile.get("soft_wishes", [])] if isinstance(request_profile, dict) and isinstance(request_profile.get("soft_wishes", []), list) else []:
        reasons_parts.append("Если важна хорошая камера, этот вариант выглядит сильнее по карточке и не уходит в слабый бюджетный сегмент.")
    leader_block = f"{leader_name}, {leader_price} {leader_intro}".strip()
    alternative_block = "В рамках текущей выборки более сильной альтернативы под тот же приоритет не найдено."
    if isinstance(competitors, list):
        for competitor in competitors:
            if isinstance(competitor, dict) and str(competitor.get("name", "")).strip():
                alternative_block = build_alternative_block_from_entry(leader, competitor, products, request_profile)
                break
    critical_block = build_request_risk_note(request_profile, leader)
    if not critical_block and match_status in {"partial", "rejected"}:
        critical_parts: list[str] = []
        if leader_missing:
            critical_parts.append("Точное совпадение не подтверждено по: " + ", ".join(leader_missing) + ".")
        if leader_contradicted:
            critical_parts.append("Лидер противоречит карточке по: " + ", ".join(leader_contradicted) + ".")
        if not leader_contradicted:
            critical_parts.append("Лидер противоречит карточке по части требований или не подтверждает их полностью.")
        critical_block = " ".join(critical_parts) if critical_parts else "Точного совпадения нет."
    if not critical_block:
        critical_block = "Сильных расхождений по текущей карточке не видно, но спорные параметры стоит отдельно перепроверить перед покупкой."
    return (
        f"Лучший вариант\n{leader_block}\n\n"
        f"Почему он подходит\n{' '.join(part.strip() for part in reasons_parts if part.strip())}\n\n"
        f"Что сильнее у альтернатив\n{alternative_block}\n\n"
        f"Компромиссы и проверки\n{critical_block}"
    ).strip()


def build_leader_intro(leader: dict[str, object], request_profile: object) -> str:
    profile = request_profile if isinstance(request_profile, dict) else {}
    ranking_policy = normalize_token(str(profile.get("ranking_policy", "")).strip())
    price_band_hint = normalize_token(str(profile.get("price_band_hint", "")).strip())
    if ranking_policy == "value" and price_band_hint == "mid_to_max":
        return "Это основной кандидат под запрос на баланс цены и оснащения в среднем сегменте и выше."
    if ranking_policy == "value":
        return "Это основной кандидат под запрос на лучшее соотношение цены и характеристик."
    if ranking_policy == "display":
        return "Это основной кандидат под запрос на максимально сильный экран в текущей выборке."
    if ranking_policy == "performance":
        return "Это основной кандидат под запрос на максимальную производительность в заданном бюджете."
    return "Это самый ровный вариант по ключевым характеристикам в текущей выборке."


def extract_request_facts_for_entry(
    entry: dict[str, object],
    products: list[Product],
    request_profile: object,
    limit: int = 3,
) -> list[str]:
    product = find_product_for_entry(entry, products)
    if product is None or not product.specs:
        return []
    profile = request_profile if isinstance(request_profile, dict) else {}
    ranking_policy = normalize_token(str(profile.get("ranking_policy", "")).strip())
    soft_wishes = [normalize_token(str(item)) for item in profile.get("soft_wishes", [])] if isinstance(profile.get("soft_wishes", []), list) else []
    ranked_specs: list[tuple[int, str]] = []
    for spec in product.specs:
        if not isinstance(spec, dict):
            continue
        fact = humanize_product_spec_fact(str(spec.get("name", "")), str(spec.get("value", "")))
        if not fact:
            continue
        score = score_spec_for_request(str(spec.get("name", "")), soft_wishes, ranking_policy)
        if score <= 0:
            continue
        ranked_specs.append((score, fact))
    ranked_specs.sort(key=lambda item: (-item[0], item[1]))
    facts: list[str] = []
    for _, fact in ranked_specs:
        if fact not in facts:
            facts.append(fact)
        if len(facts) >= limit:
            break
    return facts


def score_spec_for_request(name: str, soft_wishes: list[str], ranking_policy: str) -> int:
    normalized = normalize_token(name)
    score = 0
    if ("bright_screen" in soft_wishes or ranking_policy == "display") and re.search(r"(яркост|brightness)", normalized, re.IGNORECASE):
        score += 10
    if ranking_policy == "display" and re.search(
        r"(диагонал|размер_экрана|разрешение_экрана|тип_матрицы|покрытие_экрана|частота_обновления_экрана|экран|матриц|oled|amoled|refresh)",
        normalized,
        re.IGNORECASE,
    ):
        score += 8
    if "good_camera" in soft_wishes:
        if re.search(r"(мегапиксел.*основн.*камер|основн.*камер.*мегапиксел)", normalized, re.IGNORECASE):
            score += 18
        elif re.search(r"(мегапиксел.*фронтальн.*камер|фронтальн.*камер.*мегапиксел|селфи.*мегапиксел)", normalized, re.IGNORECASE):
            score += 16
        elif re.search(r"(сенсор.*основн.*камер|модель_сенсор.*основн.*камер|сенсор.*фронтальн.*камер)", normalized, re.IGNORECASE):
            score += 17
        elif re.search(r"(оптическ.*стабилиз|ois|зум|telephoto|перископ|видеосъемк|4k|8k)", normalized, re.IGNORECASE):
            score += 14
        elif re.search(r"(камер|camera|фронтальн|селфи)", normalized, re.IGNORECASE):
            score += 8
        if re.search(r"(количеств.*камер|апертур|угол_обзор|угол_зрения|f/)", normalized, re.IGNORECASE):
            score -= 7
    if ("good_performance" in soft_wishes or ranking_policy == "performance") and re.search(r"(процесс|chip|чип|soc|cpu|оператив|озу|ram)", normalized, re.IGNORECASE):
        score += 6
    elif ranking_policy == "value" and re.search(r"(процесс|chip|чип|soc|cpu|оператив|озу|ram)", normalized, re.IGNORECASE):
        score += 2
    if ranking_policy == "value" and re.search(r"(памят|накопител|storage|rom)", normalized, re.IGNORECASE):
        score += 5
    elif re.search(r"(памят|накопител|storage|rom)", normalized, re.IGNORECASE):
        score += 3
    if ranking_policy != "display" and re.search(
        r"(диагонал|размер_экрана|разрешение_экрана|тип_матрицы|покрытие_экрана|частота_обновления_экрана|экран|матриц|oled|amoled|refresh)",
        normalized,
        re.IGNORECASE,
    ):
        score += 4 if ranking_policy == "value" else 3
    if re.search(r"(аккумулятор|батар|мач|mah|заряд)", normalized, re.IGNORECASE):
        score += 5 if ranking_policy == "value" else 3
    return score


def humanize_product_spec_fact(name: str, value: str) -> str:
    clean_name = str(name).strip()
    clean_value = str(value).strip()
    if not clean_name or not clean_value or clean_value in {"-", "—", "нет", "none", "null"}:
        return ""
    normalized = normalize_token(clean_name)
    if any(token in normalized for token in ("яркост", "brightness")):
        return f"яркость {clean_value}"
    if any(token in normalized for token in ("диагонал", "размер_экрана")):
        return f"диагональ {clean_value}"
    if any(token in normalized for token in ("разреш", "resolution")):
        return f"разрешение {clean_value}"
    if any(token in normalized for token in ("тип_матрицы", "матриц", "panel")):
        return f"матрица {clean_value}"
    if any(token in normalized for token in ("частота", "refresh")):
        return f"частота {clean_value}"
    if any(token in normalized for token in ("памят", "storage", "rom", "накопител")) and "оператив" not in normalized and "озу" not in normalized and "ram" not in normalized:
        return f"память {clean_value}"
    if any(token in normalized for token in ("оператив", "озу", "ram")):
        return f"ОЗУ {clean_value}"
    if any(token in normalized for token in ("процесс", "chip", "чип", "soc", "cpu")):
        return f"процессор {clean_value}"
    if re.search(r"(мегапиксел.*основн.*камер|основн.*камер.*мегапиксел|основная_камера)", normalized, re.IGNORECASE):
        return f"основная камера {clean_value}"
    if re.search(r"(мегапиксел.*фронтальн.*камер|фронтальн.*камер.*мегапиксел|селфи|фронтальная_камера)", normalized, re.IGNORECASE):
        return f"фронтальная камера {clean_value}"
    if re.search(r"(сенсор.*основн.*камер|модель_сенсор.*основн.*камер)", normalized, re.IGNORECASE):
        return f"сенсор основной камеры {clean_value}"
    if re.search(r"(сенсор.*фронтальн.*камер|модель_сенсор.*фронтальн.*камер)", normalized, re.IGNORECASE):
        return f"сенсор фронтальной камеры {clean_value}"
    if re.search(r"(количеств.*камер|апертур|угол_обзор|угол_зрения)", normalized, re.IGNORECASE):
        return ""
    if any(token in normalized for token in ("камер", "camera")):
        return f"камера {clean_value}"
    if any(token in normalized for token in ("аккумулятор", "батар", "mah", "мач")):
        return f"аккумулятор {clean_value}"
    if any(token in normalized for token in ("частот", "гц", "refresh", "диагонал", "экран")):
        return f"экран {clean_value}"
    return f"{clean_name}: {clean_value}"


def find_product_for_entry(entry: dict[str, object], products: list[Product]) -> Product | None:
    entry_url = str(entry.get("url", "")).strip()
    entry_name = str(entry.get("name", "")).strip()
    entry_code = str(entry.get("code", "")).strip()
    for product in products:
        if entry_url and product.url == entry_url:
            return product
        if entry_code and product.code == entry_code:
            return product
        if entry_name and product.name == entry_name:
            return product
    return None


def build_alternative_block_from_entry(
    leader: dict[str, object],
    competitor: dict[str, object],
    products: list[Product],
    request_profile: object,
) -> str:
    competitor_name = str(competitor.get("name", "Альтернатива")).strip() or "Альтернатива"
    competitor_price_value = competitor.get("price") if isinstance(competitor.get("price"), int) else None
    competitor_price = format_price_value(competitor_price_value)
    price_delta = price_difference_text(leader.get("price"), competitor_price_value)
    competitor_facts = extract_request_facts_for_entry(competitor, products, request_profile, limit=2)
    advantage = infer_competitor_advantage(leader, competitor, request_profile)
    sentence_parts = [advantage]
    if price_delta:
        sentence_parts.append(price_delta)
    body = ". ".join(part.strip() for part in sentence_parts if part.strip()) + "."
    facts_text = ""
    if competitor_facts:
        facts_text = " По карточке выделяются: " + "; ".join(competitor_facts) + "."
    return f"{competitor_name}, {competitor_price} {body}{facts_text}".strip()


def infer_competitor_advantage(
    leader: dict[str, object],
    competitor: dict[str, object],
    request_profile: object,
) -> str:
    profile = request_profile if isinstance(request_profile, dict) else {}
    ranking_policy = normalize_token(str(profile.get("ranking_policy", "")).strip())
    leader_price = leader.get("price") if isinstance(leader.get("price"), int) else None
    competitor_price = competitor.get("price") if isinstance(competitor.get("price"), int) else None
    if competitor_price is not None and leader_price is not None and competitor_price < leader_price:
        return "Этот вариант интересен прежде всего более низкой ценой"
    if ranking_policy == "display":
        return "Этот вариант стоит смотреть, если важнее более яркий экран или другой экранный профиль"
    if ranking_policy == "value":
        if competitor_price is not None and leader_price is not None and competitor_price == leader_price:
            return "Этот вариант стоит смотреть, если при той же цене важнее другой набор сильных характеристик"
        if competitor_price is not None and leader_price is not None and competitor_price < leader_price:
            return "Этот вариант стоит смотреть, если важен близкий уровень характеристик при более низкой цене"
        return "Этот вариант стоит смотреть, если важен максимум характеристик и можно немного переплатить"
    if ranking_policy == "performance":
        return "Этот вариант интересен, если нужен более мягкий компромисс по цене"
    return "Этот вариант может быть полезен при смещении приоритета на другую сильную сторону"


def price_difference_text(leader_price: object, competitor_price: int | None) -> str:
    if not isinstance(leader_price, int) or competitor_price is None:
        return ""
    delta = competitor_price - leader_price
    if delta == 0:
        return "Цена сопоставима с основным лидером"
    if delta > 0:
        return f"Он дороже лидера на {format_price_value(delta)}"
    return f"Он дешевле лидера на {format_price_value(abs(delta))}"


def build_request_risk_note(request_profile: object, leader: dict[str, object]) -> str:
    profile = request_profile if isinstance(request_profile, dict) else {}
    ranking_policy = normalize_token(str(profile.get("ranking_policy", "")).strip())
    soft_wishes = [normalize_token(str(item)) for item in profile.get("soft_wishes", [])] if isinstance(profile.get("soft_wishes", []), list) else []
    notes: list[str] = []
    if "good_camera" in soft_wishes:
        notes.append("По карточке камера выглядит сильной, но реальное качество съёмки стоит сверить по обзорам.")
    if "bright_screen" in soft_wishes or ranking_policy == "display":
        notes.append("Яркость и субъективное качество экрана оценены по карточке, поэтому комфорт в реальном использовании стоит сверить вручную.")
    if "good_performance" in soft_wishes or ranking_policy == "performance":
        notes.append("Если важен максимум скорости в играх и тяжёлых задачах, стоит отдельно проверить реальный чип и тесты производительности.")
    if bool(leader.get("brand_mismatch")):
        notes.append("Бренд лидера не совпадает с исходным пожеланием, поэтому это компромисс в пользу общей выгоды.")
    match_status = str(leader.get("match_status", "")).casefold()
    if match_status in {"partial", "rejected"}:
        notes.append("Точное совпадение по всем жёстким условиям не подтверждено.")
    return " ".join(notes).strip()


def looks_like_raw_structured_analysis_answer(answer: str) -> bool:
    stripped = answer.strip()
    if not stripped:
        return False
    if stripped.startswith("{") or stripped.startswith("["):
        return True
    structured_markers = (
        '"normalized_request"',
        '"comparison_summary"',
        '"selected_codes"',
        '"filters_llm"',
        '"evidence_ledger"',
        '"fit_policy"',
    )
    return any(marker in stripped for marker in structured_markers)


def sanitize_analysis_answer_format(answer: str) -> str:
    cleaned_lines: list[str] = []
    for raw_line in answer.replace("\r", "\n").splitlines():
        line = raw_line.replace("**", "").strip()
        line = re.sub(r"^\d+[.)]\s+", "", line)
        if line:
            cleaned_lines.append(line)
        elif cleaned_lines and cleaned_lines[-1] != "":
            cleaned_lines.append("")
    return "\n".join(cleaned_lines).strip()


def parse_analysis_sections(answer: str) -> dict[str, str]:
    headings = {
        "лучший вариант": "Лучший вариант",
        "почему он подходит": "Почему он подходит",
        "что сильнее у альтернатив": "Что сильнее у альтернатив",
        "компромиссы и проверки": "Компромиссы и проверки",
        "лидер анализа": "Лучший вариант",
        "ближайшие аналоги": "Лучший вариант",
        "альтернатива": "Что сильнее у альтернатив",
        "критическое резюме": "Компромиссы и проверки",
    }
    sections: dict[str, str] = {
        "Лучший вариант": "",
        "Почему он подходит": "",
        "Что сильнее у альтернатив": "",
        "Компромиссы и проверки": "",
        "Лидер анализа": "",
        "Ближайшие аналоги": "",
        "Альтернатива": "",
        "Критическое резюме": "",
    }
    current_heading = ""
    buffer: list[str] = []
    for raw_line in answer.replace("\r", "\n").splitlines():
        cleaned = raw_line.replace("*", "").strip()
        match = re.match(
            r"^(лучший вариант|почему он подходит|что сильнее у альтернатив|компромиссы и проверки|лидер анализа|ближайшие аналоги|альтернатива|критическое резюме)\s*[:：]?\s*(.*)$",
            cleaned,
            re.IGNORECASE,
        )
        mapped_heading = headings.get(match.group(1).casefold()) if match else None
        if mapped_heading:
            if current_heading and buffer:
                sections[current_heading] = " ".join(line.strip() for line in buffer if line.strip()).strip()
            current_heading = mapped_heading
            buffer = []
            tail = match.group(2).strip() if match else ""
            if tail:
                buffer.append(tail)
            continue
        if current_heading:
            buffer.append(raw_line.strip())
    if current_heading and buffer:
        sections[current_heading] = " ".join(line.strip() for line in buffer if line.strip()).strip()
    if sections["Лучший вариант"] and not sections["Лидер анализа"]:
        sections["Лидер анализа"] = sections["Лучший вариант"]
    if sections["Что сильнее у альтернатив"] and not sections["Альтернатива"]:
        sections["Альтернатива"] = sections["Что сильнее у альтернатив"]
    if sections["Компромиссы и проверки"] and not sections["Критическое резюме"]:
        sections["Критическое резюме"] = sections["Компромиссы и проверки"]
    return sections


def build_leader_block(products: list[Product]) -> str:
    if not products:
        return "Точного лидера определить не удалось."
    leader = products[0]
    return f"{leader.name}, {format_price_value(leader.price)}. Это самый сильный кандидат в текущем shortlist."


def build_alternative_block(products: list[Product]) -> str:
    if len(products) < 2:
        return "Отдельная альтернатива не сформировалась."
    competitor = products[1]
    return f"{competitor.name}, {format_price_value(competitor.price)}. Имеет смысл как ближайшая альтернатива с другим набором сильных сторон."


def build_critical_block(products: list[Product]) -> str:
    if not products:
        return "Точных совпадений в текущей выборке нет."
    return "Перед покупкой стоит отдельно перепроверить спорные характеристики по карточке и обзорам."


def summarize_specs(product: Product, limit: int) -> str:
    items: list[str] = []
    for spec in product.specs[:limit]:
        if not isinstance(spec, dict):
            continue
        name = str(spec.get("name", "")).strip()
        value = str(spec.get("value", "")).strip()
        if not name or not value:
            continue
        items.append(f"{name}: {value}")
    return "; ".join(items)


def display_wishes(wishes: object) -> list[str]:
    if not isinstance(wishes, list):
        return []
    return [display_wish(str(wish)) for wish in wishes if str(wish).strip()]


def display_wish(wish: str) -> str:
    aliases = {
        "weight_up_to_2.5_kg": "вес до 2.5 кг",
        "weight_up_to_2.3_kg": "вес до 2.3 кг",
        "weight_up_to_1.5_kg": "вес до 1.5 кг",
        "240hz_screen": "экран 240 Гц",
        "32gb_ram": "32 ГБ ОЗУ",
        "2024_year": "2024 год выпуска",
        "matte_screen": "матовое покрытие",
        "rtx_4080": "RTX 4080",
    }
    return aliases.get(wish, wish.replace("_", " "))


def normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9а-я]+", "_", value.casefold()).strip("_")


def format_price_value(price: int | None) -> str:
    if price is None:
        return "цена не указана"
    return f"{price:,} руб.".replace(",", " ")
