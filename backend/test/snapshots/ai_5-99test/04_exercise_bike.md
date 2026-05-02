# 99 full trace

```text
{
  "question": "Найди велотренажер для дома с магнитной системой нагрузки, весом пользователя от 120 кг, регулировкой сиденья, дисплеем, измерением пульса, не меньше 8 уровней нагрузки, тихой работой и устойчивой конструкцией, бюджет до 30 000 рублей",
  "router": {
    "mode": "product_search",
    "response_style": "structured",
    "reason": "Запрос содержит детальные критерии для нового поиска велотренажера, не связанные с предыдущим shortlist."
  },
  "normalize": {
    "product_type": "exercisebike",
    "query": "велотренажер",
    "price_min": 0,
    "price_max": 30000,
    "brand": "",
    "constraints": [
      {
        "key": "max_user_weight",
        "op": ">=",
        "value": "120",
        "unit": "kg",
        "source_text": "весом пользователя от 120 кг"
      },
      {
        "key": "resistance_system",
        "op": "==",
        "value": "magnetic",
        "unit": "",
        "source_text": "resistance_system_magnetic"
      },
      {
        "key": "seat_adjustment",
        "op": "==",
        "value": "true",
        "unit": "",
        "source_text": "seat_adjustment"
      },
      {
        "key": "display",
        "op": "==",
        "value": "true",
        "unit": "",
        "source_text": "display"
      },
      {
        "key": "pulse_measurement",
        "op": "==",
        "value": "true",
        "unit": "",
        "source_text": "pulse_measurement"
      },
      {
        "key": "resistance_levels",
        "op": ">=",
        "value": "8",
        "unit": "",
        "source_text": "resistance_levels_from_8"
      },
      {
        "key": "stable_construction",
        "op": "==",
        "value": "true",
        "unit": "",
        "source_text": "stable_construction"
      }
    ],
    "wishes": [
      "max_user_weight_from_120_kg",
      "resistance_system_magnetic",
      "seat_adjustment",
      "display",
      "pulse_measurement",
      "resistance_levels_from_8",
      "stable_construction"
    ],
    "soft_wishes": [
      "quiet"
    ],
    "source_hard_wishes_count": 7
  },
  "section_url": "https://www.dns-shop.ru/search/?q=%D0%B2%D0%B5%D0%BB%D0%BE%D1%82%D1%80%D0%B5%D0%BD%D0%B0%D0%B6%D0%B5%D1%80&price=0-30000&category=17a8cf4816404e77",
  "filters_map": {
    "filters_count": 0
  },
  "preselected_filters": [],
  "coverage": [
    {
      "constraint_key": "max_user_weight",
      "status": "unverifiable",
      "confidence": 0.0,
      "reason": "No technical DNS filter found."
    },
    {
      "constraint_key": "resistance_system",
      "status": "unverifiable",
      "confidence": 0.0,
      "reason": "No technical DNS filter found."
    },
    {
      "constraint_key": "seat_adjustment",
      "status": "unverifiable",
      "confidence": 0.0,
      "reason": "No technical DNS filter found."
    },
    {
      "constraint_key": "display",
      "status": "unverifiable",
      "confidence": 0.0,
      "reason": "No technical DNS filter found."
    },
    {
      "constraint_key": "pulse_measurement",
      "status": "unverifiable",
      "confidence": 0.0,
      "reason": "No technical DNS filter found."
    },
    {
      "constraint_key": "resistance_levels",
      "status": "unverifiable",
      "confidence": 0.0,
      "reason": "No technical DNS filter found."
    },
    {
      "constraint_key": "stable_construction",
      "status": "unverifiable",
      "confidence": 0.0,
      "reason": "No technical DNS filter found."
    }
  ],
  "selected_filters": [],
  "built_url": "https://www.dns-shop.ru/search/?q=%D0%B2%D0%B5%D0%BB%D0%BE%D1%82%D1%80%D0%B5%D0%BD%D0%B0%D0%B6%D0%B5%D1%80&category=17a8cf4816404e77",
  "parser": {
    "mode": "httpx",
    "requested_url": "https://www.dns-shop.ru/search/?q=%D0%B2%D0%B5%D0%BB%D0%BE%D1%82%D1%80%D0%B5%D0%BD%D0%B0%D0%B6%D0%B5%D1%80&category=17a8cf4816404e77",
    "resolved_url": "https://www.dns-shop.ru/search/?q=%D0%B2%D0%B5%D0%BB%D0%BE%D1%82%D1%80%D0%B5%D0%BD%D0%B0%D0%B6%D0%B5%D1%80&category=17a8cf4816404e77",
    "products_count": 0
  },
  "answer": "По заданным фильтрам товаров не найдено.\nТочного совпадения нет: одновременно не нашлось модели с весом пользователя от 120 кг, магнитной системой нагрузки, регулировкой сиденья, дисплеем, измерением пульса, не меньше 8 уровней нагрузки, устойчивой конструкцией, бюджетом до 30 000 ₽.\nРекомендуется ослабить одно из условий: максимальный вес пользователя, систему нагрузки, регулировку сиденья."
}
```
