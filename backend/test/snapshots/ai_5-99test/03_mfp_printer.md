# 99 full trace

```text
{
  "question": "Найди лазерное МФУ для дома и учебы с Wi-Fi, двусторонней печатью, сканером, черно-белой печатью, скоростью от 20 стр/мин, недорогим обслуживанием и простой заправкой, бюджет до 25 000 рублей",
  "router": {
    "mode": "product_search",
    "response_style": "structured",
    "reason": "Пользователь запрашивает новый подбор товара с конкретными характеристиками и бюджетом, что требует нового поиска и структурированного ответа."
  },
  "normalize": {
    "product_type": "mfp",
    "query": "мфу",
    "price_min": 0,
    "price_max": 25000,
    "brand": "",
    "constraints": [
      {
        "key": "wifi",
        "op": "==",
        "value": "true",
        "unit": "",
        "source_text": "с Wi-Fi"
      },
      {
        "key": "duplex_print",
        "op": "==",
        "value": "true",
        "unit": "",
        "source_text": "duplex_print"
      },
      {
        "key": "scanner",
        "op": "==",
        "value": "true",
        "unit": "",
        "source_text": "scanner"
      },
      {
        "key": "print_speed",
        "op": ">=",
        "value": "20",
        "unit": "ppm",
        "source_text": "print_speed_from_20_ppm"
      },
      {
        "key": "refill_easy",
        "op": "==",
        "value": "true",
        "unit": "",
        "source_text": "refill_easy"
      },
      {
        "key": "cheap_maintenance",
        "op": "==",
        "value": "true",
        "unit": "",
        "source_text": "cheap_maintenance"
      }
    ],
    "wishes": [
      "wifi",
      "duplex_print",
      "scanner",
      "print_speed_from_20_ppm",
      "refill_easy",
      "cheap_maintenance"
    ],
    "soft_wishes": [],
    "source_hard_wishes_count": 6
  },
  "section_url": "https://www.dns-shop.ru/search/?q=%D0%BC%D1%84%D1%83&price=0-25000&category=17a8df6816404e77",
  "filters_map": {
    "filters_count": 52
  },
  "preselected_filters": [
    {
      "id": "fr[2hy]",
      "name": "Скорость черно-белой печати (стр/мин)",
      "min": 20.0,
      "max": 65
    },
    {
      "id": "price",
      "min": 0,
      "max": 25000
    }
  ],
  "coverage": [
    {
      "constraint_key": "wifi",
      "status": "uncovered",
      "confidence": 0.0,
      "reason": "Candidate filters found, but deterministic preselect could not map values."
    },
    {
      "constraint_key": "duplex_print",
      "status": "unverifiable",
      "confidence": 0.0,
      "reason": "No technical DNS filter found."
    },
    {
      "constraint_key": "scanner",
      "status": "uncovered",
      "confidence": 0.0,
      "reason": "Candidate filters found, but deterministic preselect could not map values."
    },
    {
      "constraint_key": "print_speed",
      "status": "covered",
      "confidence": 0.96,
      "selected_filter_ids": [
        "fr[2hy]"
      ],
      "selected_values": [],
      "reason": ""
    },
    {
      "constraint_key": "refill_easy",
      "status": "unverifiable",
      "confidence": 0.0,
      "reason": "No technical DNS filter found."
    },
    {
      "constraint_key": "cheap_maintenance",
      "status": "unverifiable",
      "confidence": 0.0,
      "reason": "No technical DNS filter found."
    }
  ],
  "selected_filters": [
    {
      "id": "fr[2hy]",
      "name": "Скорость черно-белой печати (стр/мин)",
      "min": 20.0,
      "max": 65
    },
    {
      "id": "price",
      "min": 0,
      "max": 25000
    }
  ],
  "built_url": "https://www.dns-shop.ru/search/?q=%D0%BC%D1%84%D1%83&category=17a8df6816404e77&price=0-25000&fr%5B2hy%5D=20-65",
  "parser": {
    "mode": "httpx",
    "requested_url": "https://www.dns-shop.ru/search/?q=%D0%BC%D1%84%D1%83&category=17a8df6816404e77&price=0-25000&fr%5B2hy%5D=20-65",
    "resolved_url": "https://www.dns-shop.ru/search/?q=%D0%BC%D1%84%D1%83&category=17a8df6816404e77&price=0-25000&fr%5B2hy%5D=20-65",
    "products_count": 36
  },
  "shortlist": {
    "selected_urls": [
      "https://www.dns-shop.ru/product/e3b1fab2c357d582/mfu-lazernoe-pantum-bm2302w/",
      "https://www.dns-shop.ru/product/e0d1dfccdaa4ed20/mfu-lazernoe-pantum-bm2300w/",
      "https://www.dns-shop.ru/product/862b4d5965d43332/mfu-lazernoe-pantum-m6502w/",
      "https://www.dns-shop.ru/product/3874cebcdaa6ed20/mfu-lazernoe-pantum-bm2300aw/",
      "https://www.dns-shop.ru/product/156da825d0e31b80/mfu-lazernoe-pantum-m6507w/"
    ],
    "shortlisted": [
      {
        "name": "МФУ лазерное Pantum BM2302W",
        "price": 12999,
        "url": "https://www.dns-shop.ru/product/e3b1fab2c357d582/mfu-lazernoe-pantum-bm2302w/",
        "code": "5611917"
      },
      {
        "name": "МФУ лазерное Pantum BM2300W",
        "price": 13199,
        "url": "https://www.dns-shop.ru/product/e0d1dfccdaa4ed20/mfu-lazernoe-pantum-bm2300w/",
        "code": "5450799"
      },
      {
        "name": "МФУ лазерное Pantum M6502W",
        "price": 13299,
        "url": "https://www.dns-shop.ru/product/862b4d5965d43332/mfu-lazernoe-pantum-m6502w/",
        "code": "4758967"
      },
      {
        "name": "МФУ лазерное Pantum BM2300AW",
        "price": 14499,
        "url": "https://www.dns-shop.ru/product/3874cebcdaa6ed20/mfu-lazernoe-pantum-bm2300aw/",
        "code": "5450806"
      },
      {
        "name": "МФУ лазерное Pantum M6507W",
        "price": 14799,
        "url": "https://www.dns-shop.ru/product/156da825d0e31b80/mfu-lazernoe-pantum-m6507w/",
        "code": "1298844"
      }
    ]
  },
  "comparison_summary": {
    "leader": {
      "name": "МФУ лазерное Pantum BM2302W",
      "url": "https://www.dns-shop.ru/product/e3b1fab2c357d582/mfu-lazernoe-pantum-bm2302w/",
      "price": 12999,
      "score": 2,
      "match_status": "partial",
      "matched_hard_wishes": [],
      "contradicted_hard_wishes": [],
      "matched_soft_wishes": [],
      "missing_hard_wishes": [
        "wifi",
        "duplex_print",
        "scanner",
        "print_speed_from_20_ppm",
        "refill_easy",
        "cheap_maintenance"
      ],
      "missing_soft_wishes": [],
      "brand_match": false,
      "query_match": true,
      "brand_mismatch": false,
      "details_confirmed_all_hard_wishes": false,
      "source_hard_wishes_count": 6,
      "normalized_hard_wishes_count": 6,
      "soft_wish_signal_scores": {}
    },
    "price_leader": {
      "name": "МФУ лазерное Pantum BM2302W",
      "url": "https://www.dns-shop.ru/product/e3b1fab2c357d582/mfu-lazernoe-pantum-bm2302w/",
      "price": 12999,
      "score": 2,
      "match_status": "partial",
      "matched_hard_wishes": [],
      "contradicted_hard_wishes": [],
      "matched_soft_wishes": [],
      "missing_hard_wishes": [
        "wifi",
        "duplex_print",
        "scanner",
        "print_speed_from_20_ppm",
        "refill_easy",
        "cheap_maintenance"
      ],
      "missing_soft_wishes": [],
      "brand_match": false,
      "query_match": true,
      "brand_mismatch": false,
      "details_confirmed_all_hard_wishes": false,
      "source_hard_wishes_count": 6,
      "normalized_hard_wishes_count": 6,
      "soft_wish_signal_scores": {}
    },
    "soft_wish_leaders": {},
    "segment_leaders": {},
    "budget_defined": true,
    "competitors": [
      {
        "name": "МФУ лазерное Pantum BM2300W",
        "url": "https://www.dns-shop.ru/product/e0d1dfccdaa4ed20/mfu-lazernoe-pantum-bm2300w/",
        "price": 13199,
        "score": 2,
        "match_status": "partial",
        "matched_hard_wishes": [],
        "contradicted_hard_wishes": [],
        "matched_soft_wishes": [],
        "missing_hard_wishes": [
          "wifi",
          "duplex_print",
          "scanner",
          "print_speed_from_20_ppm",
          "refill_easy",
          "cheap_maintenance"
        ],
        "missing_soft_wishes": [],
        "brand_match": false,
        "query_match": true,
        "brand_mismatch": false,
        "details_confirmed_all_hard_wishes": false,
        "source_hard_wishes_count": 6,
        "normalized_hard_wishes_count": 6,
        "soft_wish_signal_scores": {},
        "score_gap_to_leader": 0
      },
      {
        "name": "МФУ лазерное Pantum M6502W",
        "url": "https://www.dns-shop.ru/product/862b4d5965d43332/mfu-lazernoe-pantum-m6502w/",
        "price": 13299,
        "score": 2,
        "match_status": "partial",
        "matched_hard_wishes": [],
        "contradicted_hard_wishes": [],
        "matched_soft_wishes": [],
        "missing_hard_wishes": [
          "wifi",
          "duplex_print",
          "scanner",
          "print_speed_from_20_ppm",
          "refill_easy",
          "cheap_maintenance"
        ],
        "missing_soft_wishes": [],
        "brand_match": false,
        "query_match": true,
        "brand_mismatch": false,
        "details_confirmed_all_hard_wishes": false,
        "source_hard_wishes_count": 6,
        "normalized_hard_wishes_count": 6,
        "soft_wish_signal_scores": {},
        "score_gap_to_leader": 0
      },
      {
        "name": "МФУ лазерное Pantum BM2300AW",
        "url": "https://www.dns-shop.ru/product/3874cebcdaa6ed20/mfu-lazernoe-pantum-bm2300aw/",
        "price": 14499,
        "score": 2,
        "match_status": "partial",
        "matched_hard_wishes": [],
        "contradicted_hard_wishes": [],
        "matched_soft_wishes": [],
        "missing_hard_wishes": [
          "wifi",
          "duplex_print",
          "scanner",
          "print_speed_from_20_ppm",
          "refill_easy",
          "cheap_maintenance"
        ],
        "missing_soft_wishes": [],
        "brand_match": false,
        "query_match": true,
        "brand_mismatch": false,
        "details_confirmed_all_hard_wishes": false,
        "source_hard_wishes_count": 6,
        "normalized_hard_wishes_count": 6,
        "soft_wish_signal_scores": {},
        "score_gap_to_leader": 0
      },
      {
        "name": "МФУ лазерное Pantum M6507W",
        "url": "https://www.dns-shop.ru/product/156da825d0e31b80/mfu-lazernoe-pantum-m6507w/",
        "price": 14799,
        "score": 2,
        "match_status": "partial",
        "matched_hard_wishes": [],
        "contradicted_hard_wishes": [],
        "matched_soft_wishes": [],
        "missing_hard_wishes": [
          "wifi",
          "duplex_print",
          "scanner",
          "print_speed_from_20_ppm",
          "refill_easy",
          "cheap_maintenance"
        ],
        "missing_soft_wishes": [],
        "brand_match": false,
        "query_match": true,
        "brand_mismatch": false,
        "details_confirmed_all_hard_wishes": false,
        "source_hard_wishes_count": 6,
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
        "Wi-Fi",
        "двусторонней печатью",
        "сканером",
        "скоростью от 20 стр/мин",
        "простой заправкой",
        "недорогим обслуживанием"
      ],
      "contradicted_hard_wishes": [],
      "required_caveats": [
        "не подтверждено: Wi-Fi, двусторонней печатью, сканером, скоростью от 20 стр/мин, простой заправкой, недорогим обслуживанием"
      ]
    },
    "scoring": {
      "hard_wish_weight": 10,
      "soft_wish_weight": 4,
      "brand_weight": 3,
      "query_weight": 2
    }
  },
  "answer": "Ближайшие аналоги\n— МФУ лазерное Pantum BM2302W, 12 999 руб.. Лучший из найденных вариантов, но не точное совпадение. Совпадает по: части критериев. Не подтверждено: Wi-Fi, двусторонней печатью, сканером, скоростью от 20 стр/мин, простой заправкой, недорогим обслуживанием. Сравнительный score: 2.\n\nАльтернатива\nМФУ лазерное Pantum BM2300W, 13 199 руб.. Альтернативный вариант, но не подтверждено: Wi-Fi, двусторонней печатью, сканером, скоростью от 20 стр/мин, простой заправкой, недорогим обслуживанием.\n\nКритическое резюме\nТочное совпадение не подтверждено по: Wi-Fi, двусторонней печатью, сканером, скоростью от 20 стр/мин, простой заправкой, недорогим обслуживанием."
}
```
