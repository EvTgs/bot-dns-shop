# 99 full trace

```text
{
  "question": "Найди холодильник с No Frost, шириной до 60 см, общим объемом от 300 л, морозильной камерой снизу, классом энергопотребления не ниже A, инверторным компрессором, тихой работой и надежной сборкой, бюджет до 70 000 рублей",
  "router": {
    "mode": "product_search",
    "response_style": "structured",
    "reason": "Запрос содержит детальные критерии для нового поиска холодильника, включая технические характеристики и бюджет, что требует структурированного ответа с подбором товаров."
  },
  "normalize": {
    "product_type": "холодильник",
    "query": "холодильник",
    "price_min": 0,
    "price_max": 70000,
    "brand": "",
    "constraints": [
      {
        "key": "cooling_system",
        "op": "==",
        "value": "no_frost",
        "unit": "",
        "source_text": "No Frost"
      },
      {
        "key": "width",
        "op": "<=",
        "value": "60",
        "unit": "cm",
        "source_text": "шириной до 60 см"
      },
      {
        "key": "volume",
        "op": ">=",
        "value": "300",
        "unit": "l",
        "source_text": "общим объемом от 300 л"
      },
      {
        "key": "energy_class",
        "op": ">=",
        "value": "a",
        "unit": "",
        "source_text": "классом энергопотребления не ниже A"
      }
    ],
    "wishes": [
      "cooling_system_no_frost",
      "width_up_to_60_cm",
      "volume_from_300_l",
      "energy_class_not_lower_than_a"
    ],
    "soft_wishes": [
      "quiet",
      "reliable"
    ]
  },
  "section_url": "https://www.dns-shop.ru/search/?q=%D1%85%D0%BE%D0%BB%D0%BE%D0%B4%D0%B8%D0%BB%D1%8C%D0%BD%D0%B8%D0%BA&price=0-70000&category=4e2a7cdb390b7fd7",
  "filters_map": {
    "filters_count": 75
  },
  "preselected_filters": [
    {
      "id": "f[5q2]",
      "name": "Класс энергоэффективности",
      "values": [
        {
          "id": "5dc",
          "name": "A++"
        },
        {
          "id": "5db",
          "name": "A+"
        },
        {
          "id": "54c",
          "name": "A"
        }
      ]
    },
    {
      "id": "fr[tk]",
      "name": "Общий полезный объем (л)",
      "min": 300.0,
      "max": 750
    },
    {
      "id": "fr[8g]",
      "name": "Ширина (см)",
      "min": 20.8,
      "max": 60.0
    },
    {
      "id": "f[2v8]",
      "name": "Размораживание морозильной камеры / НТО",
      "values": [
        {
          "id": "5e1",
          "name": "No Frost"
        }
      ]
    },
    {
      "id": "price",
      "min": 0,
      "max": 70000
    }
  ],
  "coverage": [
    {
      "constraint_key": "cooling_system",
      "status": "covered",
      "confidence": 0.96,
      "selected_filter_ids": [
        "f[2v8]"
      ],
      "selected_values": [
        "No Frost"
      ],
      "reason": ""
    },
    {
      "constraint_key": "width",
      "status": "covered",
      "confidence": 0.96,
      "selected_filter_ids": [
        "fr[8g]"
      ],
      "selected_values": [],
      "reason": ""
    },
    {
      "constraint_key": "volume",
      "status": "covered",
      "confidence": 0.96,
      "selected_filter_ids": [
        "fr[tk]"
      ],
      "selected_values": [],
      "reason": ""
    },
    {
      "constraint_key": "energy_class",
      "status": "covered",
      "confidence": 0.96,
      "selected_filter_ids": [
        "f[5q2]"
      ],
      "selected_values": [
        "A++",
        "A+",
        "A"
      ],
      "reason": ""
    }
  ],
  "selected_filters": [
    {
      "id": "f[5q2]",
      "name": "Класс энергоэффективности",
      "values": [
        {
          "id": "5dc",
          "name": "A++"
        },
        {
          "id": "5db",
          "name": "A+"
        },
        {
          "id": "54c",
          "name": "A"
        }
      ]
    },
    {
      "id": "fr[tk]",
      "name": "Общий полезный объем (л)",
      "min": 300.0,
      "max": 750
    },
    {
      "id": "fr[8g]",
      "name": "Ширина (см)",
      "min": 20.8,
      "max": 60.0
    },
    {
      "id": "f[2v8]",
      "name": "Размораживание морозильной камеры / НТО",
      "values": [
        {
          "id": "5e1",
          "name": "No Frost"
        }
      ]
    },
    {
      "id": "price",
      "min": 0,
      "max": 70000
    }
  ],
  "built_url": "https://www.dns-shop.ru/search/?q=%D1%85%D0%BE%D0%BB%D0%BE%D0%B4%D0%B8%D0%BB%D1%8C%D0%BD%D0%B8%D0%BA&category=4e2a7cdb390b7fd7&price=0-70000&f%5B5q2%5D=5dc-5db-54c&fr%5Btk%5D=300-750&fr%5B8g%5D=20.8-60&f%5B2v8%5D=5e1",
  "parser": {
    "mode": "httpx",
    "requested_url": "https://www.dns-shop.ru/search/?q=%D1%85%D0%BE%D0%BB%D0%BE%D0%B4%D0%B8%D0%BB%D1%8C%D0%BD%D0%B8%D0%BA&category=4e2a7cdb390b7fd7&price=0-70000&f%5B5q2%5D=5dc-5db-54c&fr%5Btk%5D=300-750&fr%5B8g%5D=20.8-60&f%5B2v8%5D=5e1",
    "resolved_url": "https://www.dns-shop.ru/search/?q=%D1%85%D0%BE%D0%BB%D0%BE%D0%B4%D0%B8%D0%BB%D1%8C%D0%BD%D0%B8%D0%BA&category=4e2a7cdb390b7fd7&price=0-70000&f%5B5q2%5D=5dc-5db-54c&fr%5Btk%5D=300-750&fr%5B8g%5D=20.8-60&f%5B2v8%5D=5e1",
    "products_count": 100
  },
  "shortlist": {
    "selected_urls": [
      "https://www.dns-shop.ru/product/48385233a05b6c5c/holodilnik-s-morozilnikom-dexp-b4-35ama-belyj/",
      "https://www.dns-shop.ru/product/f91e98cce236ed20/holodilnik-s-morozilnikom-dexp-b4-0340aka-seryj/",
      "https://www.dns-shop.ru/product/587c5222eb2ae586/holodilnik-s-morozilnikom-dexp-b4-33ama-belyj/",
      "https://www.dns-shop.ru/product/42d91fbdb5651e21/holodilnik-s-morozilnikom-dexp-b4-34aka-belyj/",
      "https://www.dns-shop.ru/product/c41c10a81f7f8363/holodilnik-s-morozilnikom-dexp-b4-34ama-belyj/"
    ],
    "shortlisted": [
      {
        "name": "Холодильник с морозильником DEXP B4-35AMA белый",
        "price": 25999,
        "url": "https://www.dns-shop.ru/product/48385233a05b6c5c/holodilnik-s-morozilnikom-dexp-b4-35ama-belyj/",
        "code": "9261632"
      },
      {
        "name": "Холодильник с морозильником DEXP B4-0340AKA серый",
        "price": 27699,
        "url": "https://www.dns-shop.ru/product/f91e98cce236ed20/holodilnik-s-morozilnikom-dexp-b4-0340aka-seryj/",
        "code": "5043991"
      },
      {
        "name": "Холодильник с морозильником DEXP B4-33AMA белый",
        "price": 28999,
        "url": "https://www.dns-shop.ru/product/587c5222eb2ae586/holodilnik-s-morozilnikom-dexp-b4-33ama-belyj/",
        "code": "9330373"
      },
      {
        "name": "Холодильник с морозильником DEXP B4-34AKA белый",
        "price": 29999,
        "url": "https://www.dns-shop.ru/product/42d91fbdb5651e21/holodilnik-s-morozilnikom-dexp-b4-34aka-belyj/",
        "code": "9124966"
      },
      {
        "name": "Холодильник с морозильником DEXP B4-34AMA белый",
        "price": 29999,
        "url": "https://www.dns-shop.ru/product/c41c10a81f7f8363/holodilnik-s-morozilnikom-dexp-b4-34ama-belyj/",
        "code": "9263056"
      }
    ]
  },
  "comparison_summary": {
    "leader": {
      "name": "Холодильник с морозильником DEXP B4-35AMA белый",
      "url": "https://www.dns-shop.ru/product/48385233a05b6c5c/holodilnik-s-morozilnikom-dexp-b4-35ama-belyj/",
      "price": 25999,
      "score": 2,
      "match_status": "partial",
      "matched_hard_wishes": [],
      "contradicted_hard_wishes": [],
      "matched_soft_wishes": [],
      "missing_hard_wishes": [
        "cooling_system_no_frost",
        "width_up_to_60_cm",
        "volume_from_300_l",
        "energy_class_not_lower_than_a"
      ],
      "missing_soft_wishes": [
        "quiet",
        "reliable"
      ],
      "brand_match": false,
      "query_match": true,
      "brand_mismatch": false,
      "details_confirmed_all_hard_wishes": false,
      "soft_wish_signal_scores": {}
    },
    "price_leader": {
      "name": "Холодильник с морозильником DEXP B4-35AMA белый",
      "url": "https://www.dns-shop.ru/product/48385233a05b6c5c/holodilnik-s-morozilnikom-dexp-b4-35ama-belyj/",
      "price": 25999,
      "score": 2,
      "match_status": "partial",
      "matched_hard_wishes": [],
      "contradicted_hard_wishes": [],
      "matched_soft_wishes": [],
      "missing_hard_wishes": [
        "cooling_system_no_frost",
        "width_up_to_60_cm",
        "volume_from_300_l",
        "energy_class_not_lower_than_a"
      ],
      "missing_soft_wishes": [
        "quiet",
        "reliable"
      ],
      "brand_match": false,
      "query_match": true,
      "brand_mismatch": false,
      "details_confirmed_all_hard_wishes": false,
      "soft_wish_signal_scores": {}
    },
    "soft_wish_leaders": {},
    "competitors": [
      {
        "name": "Холодильник с морозильником DEXP B4-0340AKA серый",
        "url": "https://www.dns-shop.ru/product/f91e98cce236ed20/holodilnik-s-morozilnikom-dexp-b4-0340aka-seryj/",
        "price": 27699,
        "score": 2,
        "match_status": "partial",
        "matched_hard_wishes": [],
        "contradicted_hard_wishes": [],
        "matched_soft_wishes": [],
        "missing_hard_wishes": [
          "cooling_system_no_frost",
          "width_up_to_60_cm",
          "volume_from_300_l",
          "energy_class_not_lower_than_a"
        ],
        "missing_soft_wishes": [
          "quiet",
          "reliable"
        ],
        "brand_match": false,
        "query_match": true,
        "brand_mismatch": false,
        "details_confirmed_all_hard_wishes": false,
        "soft_wish_signal_scores": {},
        "score_gap_to_leader": 0
      },
      {
        "name": "Холодильник с морозильником DEXP B4-33AMA белый",
        "url": "https://www.dns-shop.ru/product/587c5222eb2ae586/holodilnik-s-morozilnikom-dexp-b4-33ama-belyj/",
        "price": 28999,
        "score": 2,
        "match_status": "partial",
        "matched_hard_wishes": [],
        "contradicted_hard_wishes": [],
        "matched_soft_wishes": [],
        "missing_hard_wishes": [
          "cooling_system_no_frost",
          "width_up_to_60_cm",
          "volume_from_300_l",
          "energy_class_not_lower_than_a"
        ],
        "missing_soft_wishes": [
          "quiet",
          "reliable"
        ],
        "brand_match": false,
        "query_match": true,
        "brand_mismatch": false,
        "details_confirmed_all_hard_wishes": false,
        "soft_wish_signal_scores": {},
        "score_gap_to_leader": 0
      },
      {
        "name": "Холодильник с морозильником DEXP B4-34AKA белый",
        "url": "https://www.dns-shop.ru/product/42d91fbdb5651e21/holodilnik-s-morozilnikom-dexp-b4-34aka-belyj/",
        "price": 29999,
        "score": 2,
        "match_status": "partial",
        "matched_hard_wishes": [],
        "contradicted_hard_wishes": [],
        "matched_soft_wishes": [],
        "missing_hard_wishes": [
          "cooling_system_no_frost",
          "width_up_to_60_cm",
          "volume_from_300_l",
          "energy_class_not_lower_than_a"
        ],
        "missing_soft_wishes": [
          "quiet",
          "reliable"
        ],
        "brand_match": false,
        "query_match": true,
        "brand_mismatch": false,
        "details_confirmed_all_hard_wishes": false,
        "soft_wish_signal_scores": {},
        "score_gap_to_leader": 0
      },
      {
        "name": "Холодильник с морозильником DEXP B4-34AMA белый",
        "url": "https://www.dns-shop.ru/product/c41c10a81f7f8363/holodilnik-s-morozilnikom-dexp-b4-34ama-belyj/",
        "price": 29999,
        "score": 2,
        "match_status": "partial",
        "matched_hard_wishes": [],
        "contradicted_hard_wishes": [],
        "matched_soft_wishes": [],
        "missing_hard_wishes": [
          "cooling_system_no_frost",
          "width_up_to_60_cm",
          "volume_from_300_l",
          "energy_class_not_lower_than_a"
        ],
        "missing_soft_wishes": [
          "quiet",
          "reliable"
        ],
        "brand_match": false,
        "query_match": true,
        "brand_mismatch": false,
        "details_confirmed_all_hard_wishes": false,
        "soft_wish_signal_scores": {},
        "score_gap_to_leader": 0
      }
    ],
    "all_candidates_rejected": false,
    "teacher_contract": {
      "leader_match_status": "partial",
      "all_candidates_rejected": false,
      "details_confirmed_all_hard_wishes": false,
      "full_match_allowed": false,
      "forbid_full_match_claim": true,
      "missing_hard_wishes": [
        "No Frost",
        "ширина до 60 см",
        "объём от 300 л",
        "класс энергопотребления не ниже A"
      ],
      "contradicted_hard_wishes": [],
      "required_caveats": [
        "не подтверждено: No Frost, ширина до 60 см, объём от 300 л, класс энергопотребления не ниже A"
      ]
    },
    "scoring": {
      "hard_wish_weight": 10,
      "soft_wish_weight": 4,
      "brand_weight": 3,
      "query_weight": 2
    }
  },
  "answer": "Ближайшие аналоги\n— Холодильник с морозильником DEXP B4-35AMA белый, 25 999 руб.. Лучший из найденных вариантов, но не точное совпадение. Совпадает по: части критериев. Не подтверждено: No Frost, ширина до 60 см, объём от 300 л, класс энергопотребления не ниже A. Сравнительный score: 2.\n\nАльтернатива\nХолодильник с морозильником DEXP B4-0340AKA серый, 27 699 руб.. Альтернативный вариант, но не подтверждено: No Frost, ширина до 60 см, объём от 300 л, класс энергопотребления не ниже A.\n\nКритическое резюме\nТочное совпадение не подтверждено по: No Frost, ширина до 60 см, объём от 300 л, класс энергопотребления не ниже A."
}
```
