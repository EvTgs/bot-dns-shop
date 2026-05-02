# 99 full trace

```text
{
  "question": "Найди электрогриль для дома со съемными панелями, антипригарным покрытием, регулировкой температуры, мощностью от 1800 Вт, поддоном для жира, возможностью раскрытия на 180 градусов, простой очисткой и надежной сборкой, бюджет до 15 000 рублей",
  "router": {
    "mode": "product_search",
    "response_style": "structured",
    "reason": "Запрос содержит детальные критерии для нового поиска электрогриля (мощность, функции, бюджет), что требует нового подбора товаров."
  },
  "normalize": {
    "product_type": "electricgrill",
    "query": "гриль",
    "price_min": 0,
    "price_max": 15000,
    "brand": "",
    "constraints": [
      {
        "key": "power",
        "op": ">=",
        "value": "1800",
        "unit": "w",
        "source_text": "мощностью от 1800 Вт"
      },
      {
        "key": "removable_panels",
        "op": "==",
        "value": "true",
        "unit": "",
        "source_text": "removable_panels"
      },
      {
        "key": "nonstick_coating",
        "op": "==",
        "value": "true",
        "unit": "",
        "source_text": "nonstick_coating"
      },
      {
        "key": "temperature_control",
        "op": "==",
        "value": "true",
        "unit": "",
        "source_text": "temperature_control"
      },
      {
        "key": "grease_tray",
        "op": "==",
        "value": "true",
        "unit": "",
        "source_text": "grease_tray"
      },
      {
        "key": "opens_180",
        "op": "==",
        "value": "true",
        "unit": "",
        "source_text": "opens_180"
      }
    ],
    "wishes": [
      "power_from_1800_w",
      "removable_panels",
      "nonstick_coating",
      "temperature_control",
      "grease_tray",
      "opens_180"
    ],
    "soft_wishes": [
      "reliable"
    ],
    "source_hard_wishes_count": 5
  },
  "section_url": "https://www.dns-shop.ru/search/?q=%D0%B3%D1%80%D0%B8%D0%BB%D1%8C&price=0-15000&category=17a9a71416404e77",
  "filters_map": {
    "filters_count": 52
  },
  "preselected_filters": [
    {
      "id": "f[65p]",
      "name": "Открытие на 180°/положение барбекю",
      "values": [
        {
          "id": "21",
          "name": "есть"
        }
      ]
    },
    {
      "id": "f[r6]",
      "name": "Лоток для жира и сока",
      "values": [
        {
          "id": "21",
          "name": "есть"
        }
      ]
    },
    {
      "id": "f[96n]",
      "name": "Независимая регулировка температуры пластин",
      "values": [
        {
          "id": "21",
          "name": "есть"
        }
      ]
    },
    {
      "id": "f[1wj]",
      "name": "Антипригарное покрытие",
      "values": [
        {
          "id": "21",
          "name": "есть"
        }
      ]
    },
    {
      "id": "f[54e]",
      "name": "Съемные пластины",
      "values": [
        {
          "id": "21",
          "name": "есть"
        }
      ]
    },
    {
      "id": "fr[8e]",
      "name": "Мощность (Вт)",
      "min": 1800.0,
      "max": 7500
    },
    {
      "id": "price",
      "min": 0,
      "max": 15000
    }
  ],
  "coverage": [
    {
      "constraint_key": "power",
      "status": "covered",
      "confidence": 0.96,
      "selected_filter_ids": [
        "fr[8e]"
      ],
      "selected_values": [],
      "reason": ""
    },
    {
      "constraint_key": "removable_panels",
      "status": "covered",
      "confidence": 0.96,
      "selected_filter_ids": [
        "f[54e]"
      ],
      "selected_values": [
        "есть"
      ],
      "reason": ""
    },
    {
      "constraint_key": "nonstick_coating",
      "status": "covered",
      "confidence": 0.96,
      "selected_filter_ids": [
        "f[1wj]"
      ],
      "selected_values": [
        "есть"
      ],
      "reason": ""
    },
    {
      "constraint_key": "temperature_control",
      "status": "covered",
      "confidence": 0.96,
      "selected_filter_ids": [
        "f[96n]"
      ],
      "selected_values": [
        "есть"
      ],
      "reason": ""
    },
    {
      "constraint_key": "grease_tray",
      "status": "covered",
      "confidence": 0.96,
      "selected_filter_ids": [
        "f[r6]"
      ],
      "selected_values": [
        "есть"
      ],
      "reason": ""
    },
    {
      "constraint_key": "opens_180",
      "status": "covered",
      "confidence": 0.96,
      "selected_filter_ids": [
        "f[65p]"
      ],
      "selected_values": [
        "есть"
      ],
      "reason": ""
    }
  ],
  "selected_filters": [
    {
      "id": "f[65p]",
      "name": "Открытие на 180°/положение барбекю",
      "values": [
        {
          "id": "21",
          "name": "есть"
        }
      ]
    },
    {
      "id": "f[r6]",
      "name": "Лоток для жира и сока",
      "values": [
        {
          "id": "21",
          "name": "есть"
        }
      ]
    },
    {
      "id": "f[96n]",
      "name": "Независимая регулировка температуры пластин",
      "values": [
        {
          "id": "21",
          "name": "есть"
        }
      ]
    },
    {
      "id": "f[1wj]",
      "name": "Антипригарное покрытие",
      "values": [
        {
          "id": "21",
          "name": "есть"
        }
      ]
    },
    {
      "id": "f[54e]",
      "name": "Съемные пластины",
      "values": [
        {
          "id": "21",
          "name": "есть"
        }
      ]
    },
    {
      "id": "fr[8e]",
      "name": "Мощность (Вт)",
      "min": 1800.0,
      "max": 7500
    },
    {
      "id": "price",
      "min": 0,
      "max": 15000
    }
  ],
  "built_url": "https://www.dns-shop.ru/search/?q=%D0%B3%D1%80%D0%B8%D0%BB%D1%8C&category=17a9a71416404e77&price=0-15000&f%5B65p%5D=21&f%5Br6%5D=21&f%5B96n%5D=21&f%5B1wj%5D=21&f%5B54e%5D=21&fr%5B8e%5D=1800-7500",
  "parser": {
    "mode": "httpx",
    "requested_url": "https://www.dns-shop.ru/search/?q=%D0%B3%D1%80%D0%B8%D0%BB%D1%8C&category=17a9a71416404e77&price=0-15000&f%5B65p%5D=21&f%5Br6%5D=21&f%5B96n%5D=21&f%5B1wj%5D=21&f%5B54e%5D=21&fr%5B8e%5D=1800-7500",
    "resolved_url": "https://www.dns-shop.ru/search/?q=%D0%B3%D1%80%D0%B8%D0%BB%D1%8C&category=17a9a71416404e77&price=0-15000&f%5B65p%5D=21&f%5Br6%5D=21&f%5B96n%5D=21&f%5B1wj%5D=21&f%5B54e%5D=21&fr%5B8e%5D=1800-7500",
    "products_count": 47
  },
  "shortlist": {
    "selected_urls": [
      "https://www.dns-shop.ru/product/c08859bdd773b5c6/gril-kitfort-kt-3615-cernyj/",
      "https://www.dns-shop.ru/product/2a47247ccf06ed20/gril-reoka-rkg-d201-cernyj/",
      "https://www.dns-shop.ru/product/551f0c02b8af3330/gril-gfgril-gf-165-serebristyj/",
      "https://www.dns-shop.ru/product/090541d1695dd1a5/gril-jvc-jk-gr320-cernyj/",
      "https://www.dns-shop.ru/product/506ea079d33a5682/gril-oasis-gr-sr-serebristyj/"
    ],
    "shortlisted": [
      {
        "name": "Гриль Kitfort КТ-3615 черный",
        "price": 3499,
        "url": "https://www.dns-shop.ru/product/c08859bdd773b5c6/gril-kitfort-kt-3615-cernyj/",
        "code": "9129631"
      },
      {
        "name": "Гриль Reoka RKG-D201 черный",
        "price": 3599,
        "url": "https://www.dns-shop.ru/product/2a47247ccf06ed20/gril-reoka-rkg-d201-cernyj/",
        "code": "5408665"
      },
      {
        "name": "Гриль GFgril GF-165 серебристый",
        "price": 3599,
        "url": "https://www.dns-shop.ru/product/551f0c02b8af3330/gril-gfgril-gf-165-serebristyj/",
        "code": "8147905"
      },
      {
        "name": "Гриль JVC JK-GR320 черный",
        "price": 3999,
        "url": "https://www.dns-shop.ru/product/090541d1695dd1a5/gril-jvc-jk-gr320-cernyj/",
        "code": "9057655"
      },
      {
        "name": "Гриль Oasis GR-SR серебристый",
        "price": 3999,
        "url": "https://www.dns-shop.ru/product/506ea079d33a5682/gril-oasis-gr-sr-serebristyj/",
        "code": "9146013"
      }
    ]
  },
  "comparison_summary": {
    "leader": {
      "name": "Гриль Kitfort КТ-3615 черный",
      "url": "https://www.dns-shop.ru/product/c08859bdd773b5c6/gril-kitfort-kt-3615-cernyj/",
      "price": 3499,
      "score": 2,
      "match_status": "partial",
      "matched_hard_wishes": [],
      "contradicted_hard_wishes": [],
      "matched_soft_wishes": [],
      "missing_hard_wishes": [
        "power_from_1800_w",
        "removable_panels",
        "nonstick_coating",
        "temperature_control",
        "grease_tray",
        "opens_180"
      ],
      "missing_soft_wishes": [
        "reliable"
      ],
      "brand_match": false,
      "query_match": true,
      "brand_mismatch": false,
      "details_confirmed_all_hard_wishes": false,
      "source_hard_wishes_count": 5,
      "normalized_hard_wishes_count": 6,
      "soft_wish_signal_scores": {}
    },
    "price_leader": {
      "name": "Гриль Kitfort КТ-3615 черный",
      "url": "https://www.dns-shop.ru/product/c08859bdd773b5c6/gril-kitfort-kt-3615-cernyj/",
      "price": 3499,
      "score": 2,
      "match_status": "partial",
      "matched_hard_wishes": [],
      "contradicted_hard_wishes": [],
      "matched_soft_wishes": [],
      "missing_hard_wishes": [
        "power_from_1800_w",
        "removable_panels",
        "nonstick_coating",
        "temperature_control",
        "grease_tray",
        "opens_180"
      ],
      "missing_soft_wishes": [
        "reliable"
      ],
      "brand_match": false,
      "query_match": true,
      "brand_mismatch": false,
      "details_confirmed_all_hard_wishes": false,
      "source_hard_wishes_count": 5,
      "normalized_hard_wishes_count": 6,
      "soft_wish_signal_scores": {}
    },
    "soft_wish_leaders": {},
    "segment_leaders": {},
    "budget_defined": true,
    "competitors": [
      {
        "name": "Гриль Reoka RKG-D201 черный",
        "url": "https://www.dns-shop.ru/product/2a47247ccf06ed20/gril-reoka-rkg-d201-cernyj/",
        "price": 3599,
        "score": 2,
        "match_status": "partial",
        "matched_hard_wishes": [],
        "contradicted_hard_wishes": [],
        "matched_soft_wishes": [],
        "missing_hard_wishes": [
          "power_from_1800_w",
          "removable_panels",
          "nonstick_coating",
          "temperature_control",
          "grease_tray",
          "opens_180"
        ],
        "missing_soft_wishes": [
          "reliable"
        ],
        "brand_match": false,
        "query_match": true,
        "brand_mismatch": false,
        "details_confirmed_all_hard_wishes": false,
        "source_hard_wishes_count": 5,
        "normalized_hard_wishes_count": 6,
        "soft_wish_signal_scores": {},
        "score_gap_to_leader": 0
      },
      {
        "name": "Гриль GFgril GF-165 серебристый",
        "url": "https://www.dns-shop.ru/product/551f0c02b8af3330/gril-gfgril-gf-165-serebristyj/",
        "price": 3599,
        "score": 2,
        "match_status": "partial",
        "matched_hard_wishes": [],
        "contradicted_hard_wishes": [],
        "matched_soft_wishes": [],
        "missing_hard_wishes": [
          "power_from_1800_w",
          "removable_panels",
          "nonstick_coating",
          "temperature_control",
          "grease_tray",
          "opens_180"
        ],
        "missing_soft_wishes": [
          "reliable"
        ],
        "brand_match": false,
        "query_match": true,
        "brand_mismatch": false,
        "details_confirmed_all_hard_wishes": false,
        "source_hard_wishes_count": 5,
        "normalized_hard_wishes_count": 6,
        "soft_wish_signal_scores": {},
        "score_gap_to_leader": 0
      },
      {
        "name": "Гриль JVC JK-GR320 черный",
        "url": "https://www.dns-shop.ru/product/090541d1695dd1a5/gril-jvc-jk-gr320-cernyj/",
        "price": 3999,
        "score": 2,
        "match_status": "partial",
        "matched_hard_wishes": [],
        "contradicted_hard_wishes": [],
        "matched_soft_wishes": [],
        "missing_hard_wishes": [
          "power_from_1800_w",
          "removable_panels",
          "nonstick_coating",
          "temperature_control",
          "grease_tray",
          "opens_180"
        ],
        "missing_soft_wishes": [
          "reliable"
        ],
        "brand_match": false,
        "query_match": true,
        "brand_mismatch": false,
        "details_confirmed_all_hard_wishes": false,
        "source_hard_wishes_count": 5,
        "normalized_hard_wishes_count": 6,
        "soft_wish_signal_scores": {},
        "score_gap_to_leader": 0
      },
      {
        "name": "Гриль Oasis GR-SR серебристый",
        "url": "https://www.dns-shop.ru/product/506ea079d33a5682/gril-oasis-gr-sr-serebristyj/",
        "price": 3999,
        "score": 2,
        "match_status": "partial",
        "matched_hard_wishes": [],
        "contradicted_hard_wishes": [],
        "matched_soft_wishes": [],
        "missing_hard_wishes": [
          "power_from_1800_w",
          "removable_panels",
          "nonstick_coating",
          "temperature_control",
          "grease_tray",
          "opens_180"
        ],
        "missing_soft_wishes": [
          "reliable"
        ],
        "brand_match": false,
        "query_match": true,
        "brand_mismatch": false,
        "details_confirmed_all_hard_wishes": false,
        "source_hard_wishes_count": 5,
        "normalized_hard_wishes_count": 6,
        "soft_wish_signal_scores": {},
        "score_gap_to_leader": 0
      }
    ],
    "all_candidates_rejected": false,
    "coverage": [],
    "coverage_has_gap": false,
    "teacher_contract": {
      "leader_match_status": "partial",
      "all_candidates_rejected": false,
      "details_confirmed_all_hard_wishes": false,
      "full_match_allowed": false,
      "forbid_full_match_claim": true,
      "missing_hard_wishes": [
        "мощностью от 1800 Вт",
        "съёмными панелями",
        "антипригарным покрытием",
        "регулировкой температуры",
        "поддоном для жира",
        "раскрытием на 180 градусов"
      ],
      "contradicted_hard_wishes": [],
      "required_caveats": [
        "не подтверждено: мощностью от 1800 Вт, съёмными панелями, антипригарным покрытием, регулировкой температуры, поддоном для жира, раскрытием на 180 градусов"
      ]
    },
    "scoring": {
      "hard_wish_weight": 10,
      "soft_wish_weight": 4,
      "brand_weight": 3,
      "query_weight": 2
    }
  },
  "answer": "Ближайшие аналоги\n— Гриль Kitfort КТ-3615 черный, 3 499 руб.. Лучший из найденных вариантов, но не точное совпадение. Совпадает по: части критериев. Не подтверждено: мощностью от 1800 Вт, съёмными панелями, антипригарным покрытием, регулировкой температуры, поддоном для жира, раскрытием на 180 градусов. Сравнительный score: 2.\n\nАльтернатива\nГриль Reoka RKG-D201 черный, 3 599 руб.. Альтернативный вариант, но не подтверждено: мощностью от 1800 Вт, съёмными панелями, антипригарным покрытием, регулировкой температуры, поддоном для жира, раскрытием на 180 градусов.\n\nКритическое резюме\nТочное совпадение не подтверждено по: мощностью от 1800 Вт, съёмными панелями, антипригарным покрытием, регулировкой температуры, поддоном для жира, раскрытием на 180 градусов."
}
```
