# 99 full trace

```text
{
  "question": "Найди монитор 27 дюймов, 2K, 144 Гц, IPS, с хорошей цветопередачей и регулировкой по высоте, бюджет до 35000 рублей",
  "router": {
    "mode": "product_search",
    "response_style": "structured",
    "reason": "Запрос содержит конкретные критерии для нового поиска монитора (диагональ, разрешение, частота, тип матрицы, бюджет), что требует выполнения нового поиска по DNS."
  },
  "normalize": {
    "product_type": "monitor",
    "query": "монитор",
    "price_min": null,
    "price_max": 35000,
    "brand": "",
    "ranking_policy": "",
    "price_band_hint": "",
    "intent_signals": [
      {
        "key": "screen_size",
        "op": "==",
        "value": "27",
        "unit": "inch",
        "source_text": "27 дюймов",
        "weight": 1.0
      },
      {
        "key": "refresh_rate",
        "op": "==",
        "value": "144",
        "unit": "hz",
        "source_text": "144 Гц",
        "weight": 1.0
      },
      {
        "key": "matrix_type",
        "op": "==",
        "value": "ips",
        "unit": "",
        "source_text": "IPS",
        "weight": 1.0
      }
    ],
    "retrieval_tokens": [
      "27_inch",
      "144hz_display",
      "ips"
    ],
    "soft_wishes": [
      "good_color_accuracy",
      "height_adjustable"
    ],
    "source_signal_count": 3,
    "constraints": [
      {
        "key": "screen_size",
        "op": "==",
        "value": "27",
        "unit": "inch",
        "source_text": "27 дюймов",
        "weight": 1.0
      },
      {
        "key": "refresh_rate",
        "op": "==",
        "value": "144",
        "unit": "hz",
        "source_text": "144 Гц",
        "weight": 1.0
      },
      {
        "key": "matrix_type",
        "op": "==",
        "value": "ips",
        "unit": "",
        "source_text": "IPS",
        "weight": 1.0
      }
    ],
    "wishes": [
      "27_inch",
      "144hz_display",
      "ips"
    ],
    "source_hard_wishes_count": 3
  },
  "section_url": "https://www.dns-shop.ru/search/?q=%D0%BC%D0%BE%D0%BD%D0%B8%D1%82%D0%BE%D1%80&category=17a8943716404e77",
  "filters_map": {
    "filters_count": 81
  },
  "preselected_filters": [
    {
      "id": "f[2v]",
      "name": "Тип матрицы",
      "values": [
        {
          "id": "1uq",
          "name": "IPS"
        }
      ]
    },
    {
      "id": "f[2b]",
      "name": "Максимальная частота обновления экрана (Гц)",
      "values": [
        {
          "id": "sp",
          "name": "144 Гц"
        }
      ]
    },
    {
      "id": "fr[1q]",
      "name": "Диагональ экрана (дюйм)",
      "min": 27.0,
      "max": 27.0
    }
  ],
  "coverage": [
    {
      "constraint_key": "screen_size",
      "status": "covered",
      "confidence": 0.96,
      "selected_filter_ids": [
        "fr[1q]"
      ],
      "selected_values": [],
      "reason": ""
    },
    {
      "constraint_key": "refresh_rate",
      "status": "covered",
      "confidence": 0.96,
      "selected_filter_ids": [
        "f[2b]"
      ],
      "selected_values": [
        "144 Гц"
      ],
      "reason": ""
    },
    {
      "constraint_key": "matrix_type",
      "status": "covered",
      "confidence": 0.96,
      "selected_filter_ids": [
        "f[2v]"
      ],
      "selected_values": [
        "IPS"
      ],
      "reason": ""
    }
  ],
  "selected_filters": [
    {
      "id": "f[2v]",
      "name": "Тип матрицы",
      "values": [
        {
          "id": "1uq",
          "name": "IPS"
        }
      ]
    },
    {
      "id": "f[2b]",
      "name": "Максимальная частота обновления экрана (Гц)",
      "values": [
        {
          "id": "sp",
          "name": "144 Гц"
        }
      ]
    },
    {
      "id": "fr[1q]",
      "name": "Диагональ экрана (дюйм)",
      "min": 27.0,
      "max": 27.0
    }
  ],
  "built_url": "https://www.dns-shop.ru/search/?q=%D0%BC%D0%BE%D0%BD%D0%B8%D1%82%D0%BE%D1%80&category=17a8943716404e77&f%5B2v%5D=1uq&f%5B2b%5D=sp&fr%5B1q%5D=27-27",
  "parser": {
    "mode": "httpx",
    "requested_url": "https://www.dns-shop.ru/search/?q=%D0%BC%D0%BE%D0%BD%D0%B8%D1%82%D0%BE%D1%80&category=17a8943716404e77&f%5B2v%5D=1uq&f%5B2b%5D=sp&fr%5B1q%5D=27-27",
    "resolved_url": "https://www.dns-shop.ru/search/?q=%D0%BC%D0%BE%D0%BD%D0%B8%D1%82%D0%BE%D1%80&category=17a8943716404e77&f%5B2v%5D=1uq&f%5B2b%5D=sp&fr%5B1q%5D=27-27",
    "products_count": 28
  },
  "shortlist": {
    "selected_urls": [
      "https://www.dns-shop.ru/product/7329627da8cd0ab3/27-monitor-dexp-dq27n1-v3-cernyj/",
      "https://www.dns-shop.ru/product/505604cb758c1b80/27-monitor-gigabyte-g27q-cernyj/",
      "https://www.dns-shop.ru/product/226d8b65427ed582/27-monitor-asus-proart-pa278cgv-cernyj/",
      "https://www.dns-shop.ru/product/e9f9c6ba4f63ed20/27-monitor-lg-ultragear-27gn800-b-cernyj/",
      "https://www.dns-shop.ru/product/dcaf8f192805ed20/27-monitor-acer-nitro-xv275kpymipruzx-cernyj/"
    ],
    "shortlisted": [
      {
        "name": "27\" Монитор DEXP DQ27N1 V3 черный",
        "price": 11499,
        "url": "https://www.dns-shop.ru/product/7329627da8cd0ab3/27-monitor-dexp-dq27n1-v3-cernyj/",
        "code": "9306776"
      },
      {
        "name": "27\" Монитор LG UltraGear 27GN800-B черный",
        "price": 26199,
        "url": "https://www.dns-shop.ru/product/e9f9c6ba4f63ed20/27-monitor-lg-ultragear-27gn800-b-cernyj/",
        "code": "5079997"
      },
      {
        "name": "27\" Монитор GIGABYTE G27Q черный",
        "price": 28599,
        "url": "https://www.dns-shop.ru/product/505604cb758c1b80/27-monitor-gigabyte-g27q-cernyj/",
        "code": "1651848"
      },
      {
        "name": "27\" Монитор ASUS ProArt PA278CGV черный",
        "price": 31999,
        "url": "https://www.dns-shop.ru/product/226d8b65427ed582/27-monitor-asus-proart-pa278cgv-cernyj/",
        "code": "5473340"
      },
      {
        "name": "27\" Монитор Acer Nitro XV275KPymipruzx черный",
        "price": 33499,
        "url": "https://www.dns-shop.ru/product/dcaf8f192805ed20/27-monitor-acer-nitro-xv275kpymipruzx-cernyj/",
        "code": "5068605"
      }
    ]
  },
  "comparison_summary": {
    "top_pick": {
      "name": "27\" Монитор GIGABYTE G27Q черный",
      "url": "https://www.dns-shop.ru/product/505604cb758c1b80/27-monitor-gigabyte-g27q-cernyj/",
      "price": 28599,
      "score": 26,
      "fit_score": 26,
      "match_status": "partial",
      "matched_hard_wishes": [
        "27_inch",
        "ips"
      ],
      "contradicted_hard_wishes": [],
      "matched_soft_wishes": [
        "height_adjustable"
      ],
      "missing_hard_wishes": [
        "144hz_display"
      ],
      "missing_soft_wishes": [
        "good_color_accuracy"
      ],
      "brand_match": false,
      "query_match": true,
      "brand_mismatch": false,
      "details_confirmed_all_hard_wishes": false,
      "source_hard_wishes_count": 3,
      "normalized_hard_wishes_count": 3,
      "source_signal_count": 3,
      "normalized_signal_count": 3,
      "confirmed_signals": [
        "27 дюймов",
        "IPS"
      ],
      "unconfirmed_signals": [
        "144hz display"
      ],
      "contradicted_signals": [],
      "signal_evidence": [
        {
          "token": "27_inch",
          "label": "27 дюймов",
          "status": "confirmed",
          "signal_key": "screen_size",
          "source_text": "27 дюймов"
        },
        {
          "token": "144hz_display",
          "label": "144hz display",
          "status": "missing",
          "signal_key": "refresh_rate",
          "source_text": "144 Гц"
        },
        {
          "token": "ips",
          "label": "IPS",
          "status": "confirmed",
          "signal_key": "matrix_type",
          "source_text": "IPS"
        }
      ],
      "soft_wish_signal_scores": {
        "height_adjustable": 0
      }
    },
    "leader": {
      "name": "27\" Монитор GIGABYTE G27Q черный",
      "url": "https://www.dns-shop.ru/product/505604cb758c1b80/27-monitor-gigabyte-g27q-cernyj/",
      "price": 28599,
      "score": 26,
      "fit_score": 26,
      "match_status": "partial",
      "matched_hard_wishes": [
        "27_inch",
        "ips"
      ],
      "contradicted_hard_wishes": [],
      "matched_soft_wishes": [
        "height_adjustable"
      ],
      "missing_hard_wishes": [
        "144hz_display"
      ],
      "missing_soft_wishes": [
        "good_color_accuracy"
      ],
      "brand_match": false,
      "query_match": true,
      "brand_mismatch": false,
      "details_confirmed_all_hard_wishes": false,
      "source_hard_wishes_count": 3,
      "normalized_hard_wishes_count": 3,
      "source_signal_count": 3,
      "normalized_signal_count": 3,
      "confirmed_signals": [
        "27 дюймов",
        "IPS"
      ],
      "unconfirmed_signals": [
        "144hz display"
      ],
      "contradicted_signals": [],
      "signal_evidence": [
        {
          "token": "27_inch",
          "label": "27 дюймов",
          "status": "confirmed",
          "signal_key": "screen_size",
          "source_text": "27 дюймов"
        },
        {
          "token": "144hz_display",
          "label": "144hz display",
          "status": "missing",
          "signal_key": "refresh_rate",
          "source_text": "144 Гц"
        },
        {
          "token": "ips",
          "label": "IPS",
          "status": "confirmed",
          "signal_key": "matrix_type",
          "source_text": "IPS"
        }
      ],
      "soft_wish_signal_scores": {
        "height_adjustable": 0
      }
    },
    "price_pick": {
      "name": "27\" Монитор DEXP DQ27N1 V3 черный",
      "url": "https://www.dns-shop.ru/product/7329627da8cd0ab3/27-monitor-dexp-dq27n1-v3-cernyj/",
      "price": 11499,
      "score": 22,
      "fit_score": 22,
      "match_status": "partial",
      "matched_hard_wishes": [
        "27_inch",
        "ips"
      ],
      "contradicted_hard_wishes": [],
      "matched_soft_wishes": [],
      "missing_hard_wishes": [
        "144hz_display"
      ],
      "missing_soft_wishes": [
        "good_color_accuracy",
        "height_adjustable"
      ],
      "brand_match": false,
      "query_match": true,
      "brand_mismatch": false,
      "details_confirmed_all_hard_wishes": false,
      "source_hard_wishes_count": 3,
      "normalized_hard_wishes_count": 3,
      "source_signal_count": 3,
      "normalized_signal_count": 3,
      "confirmed_signals": [
        "27 дюймов",
        "IPS"
      ],
      "unconfirmed_signals": [
        "144hz display"
      ],
      "contradicted_signals": [],
      "signal_evidence": [
        {
          "token": "27_inch",
          "label": "27 дюймов",
          "status": "confirmed",
          "signal_key": "screen_size",
          "source_text": "27 дюймов"
        },
        {
          "token": "144hz_display",
          "label": "144hz display",
          "status": "missing",
          "signal_key": "refresh_rate",
          "source_text": "144 Гц"
        },
        {
          "token": "ips",
          "label": "IPS",
          "status": "confirmed",
          "signal_key": "matrix_type",
          "source_text": "IPS"
        }
      ],
      "soft_wish_signal_scores": {}
    },
    "price_leader": {
      "name": "27\" Монитор DEXP DQ27N1 V3 черный",
      "url": "https://www.dns-shop.ru/product/7329627da8cd0ab3/27-monitor-dexp-dq27n1-v3-cernyj/",
      "price": 11499,
      "score": 22,
      "fit_score": 22,
      "match_status": "partial",
      "matched_hard_wishes": [
        "27_inch",
        "ips"
      ],
      "contradicted_hard_wishes": [],
      "matched_soft_wishes": [],
      "missing_hard_wishes": [
        "144hz_display"
      ],
      "missing_soft_wishes": [
        "good_color_accuracy",
        "height_adjustable"
      ],
      "brand_match": false,
      "query_match": true,
      "brand_mismatch": false,
      "details_confirmed_all_hard_wishes": false,
      "source_hard_wishes_count": 3,
      "normalized_hard_wishes_count": 3,
      "source_signal_count": 3,
      "normalized_signal_count": 3,
      "confirmed_signals": [
        "27 дюймов",
        "IPS"
      ],
      "unconfirmed_signals": [
        "144hz display"
      ],
      "contradicted_signals": [],
      "signal_evidence": [
        {
          "token": "27_inch",
          "label": "27 дюймов",
          "status": "confirmed",
          "signal_key": "screen_size",
          "source_text": "27 дюймов"
        },
        {
          "token": "144hz_display",
          "label": "144hz display",
          "status": "missing",
          "signal_key": "refresh_rate",
          "source_text": "144 Гц"
        },
        {
          "token": "ips",
          "label": "IPS",
          "status": "confirmed",
          "signal_key": "matrix_type",
          "source_text": "IPS"
        }
      ],
      "soft_wish_signal_scores": {}
    },
    "segment_picks": {
      "price_leader": {
        "name": "27\" Монитор DEXP DQ27N1 V3 черный",
        "url": "https://www.dns-shop.ru/product/7329627da8cd0ab3/27-monitor-dexp-dq27n1-v3-cernyj/",
        "price": 11499,
        "score": 22,
        "fit_score": 22,
        "match_status": "partial",
        "matched_hard_wishes": [
          "27_inch",
          "ips"
        ],
        "contradicted_hard_wishes": [],
        "matched_soft_wishes": [],
        "missing_hard_wishes": [
          "144hz_display"
        ],
        "missing_soft_wishes": [
          "good_color_accuracy",
          "height_adjustable"
        ],
        "brand_match": false,
        "query_match": true,
        "brand_mismatch": false,
        "details_confirmed_all_hard_wishes": false,
        "source_hard_wishes_count": 3,
        "normalized_hard_wishes_count": 3,
        "source_signal_count": 3,
        "normalized_signal_count": 3,
        "confirmed_signals": [
          "27 дюймов",
          "IPS"
        ],
        "unconfirmed_signals": [
          "144hz display"
        ],
        "contradicted_signals": [],
        "signal_evidence": [
          {
            "token": "27_inch",
            "label": "27 дюймов",
            "status": "confirmed",
            "signal_key": "screen_size",
            "source_text": "27 дюймов"
          },
          {
            "token": "144hz_display",
            "label": "144hz display",
            "status": "missing",
            "signal_key": "refresh_rate",
            "source_text": "144 Гц"
          },
          {
            "token": "ips",
            "label": "IPS",
            "status": "confirmed",
            "signal_key": "matrix_type",
            "source_text": "IPS"
          }
        ],
        "soft_wish_signal_scores": {}
      },
      "value_leader": {
        "name": "27\" Монитор GIGABYTE G27Q черный",
        "url": "https://www.dns-shop.ru/product/505604cb758c1b80/27-monitor-gigabyte-g27q-cernyj/",
        "price": 28599,
        "score": 26,
        "fit_score": 26,
        "match_status": "partial",
        "matched_hard_wishes": [
          "27_inch",
          "ips"
        ],
        "contradicted_hard_wishes": [],
        "matched_soft_wishes": [
          "height_adjustable"
        ],
        "missing_hard_wishes": [
          "144hz_display"
        ],
        "missing_soft_wishes": [
          "good_color_accuracy"
        ],
        "brand_match": false,
        "query_match": true,
        "brand_mismatch": false,
        "details_confirmed_all_hard_wishes": false,
        "source_hard_wishes_count": 3,
        "normalized_hard_wishes_count": 3,
        "source_signal_count": 3,
        "normalized_signal_count": 3,
        "confirmed_signals": [
          "27 дюймов",
          "IPS"
        ],
        "unconfirmed_signals": [
          "144hz display"
        ],
        "contradicted_signals": [],
        "signal_evidence": [
          {
            "token": "27_inch",
            "label": "27 дюймов",
            "status": "confirmed",
            "signal_key": "screen_size",
            "source_text": "27 дюймов"
          },
          {
            "token": "144hz_display",
            "label": "144hz display",
            "status": "missing",
            "signal_key": "refresh_rate",
            "source_text": "144 Гц"
          },
          {
            "token": "ips",
            "label": "IPS",
            "status": "confirmed",
            "signal_key": "matrix_type",
            "source_text": "IPS"
          }
        ],
        "soft_wish_signal_scores": {
          "height_adjustable": 0
        }
      },
      "spec_leader": {
        "name": "27\" Монитор Acer Nitro XV275KPymipruzx черный",
        "url": "https://www.dns-shop.ru/product/dcaf8f192805ed20/27-monitor-acer-nitro-xv275kpymipruzx-cernyj/",
        "price": 33499,
        "score": 26,
        "fit_score": 26,
        "match_status": "partial",
        "matched_hard_wishes": [
          "27_inch",
          "ips"
        ],
        "contradicted_hard_wishes": [],
        "matched_soft_wishes": [
          "height_adjustable"
        ],
        "missing_hard_wishes": [
          "144hz_display"
        ],
        "missing_soft_wishes": [
          "good_color_accuracy"
        ],
        "brand_match": false,
        "query_match": true,
        "brand_mismatch": false,
        "details_confirmed_all_hard_wishes": false,
        "source_hard_wishes_count": 3,
        "normalized_hard_wishes_count": 3,
        "source_signal_count": 3,
        "normalized_signal_count": 3,
        "confirmed_signals": [
          "27 дюймов",
          "IPS"
        ],
        "unconfirmed_signals": [
          "144hz display"
        ],
        "contradicted_signals": [],
        "signal_evidence": [
          {
            "token": "27_inch",
            "label": "27 дюймов",
            "status": "confirmed",
            "signal_key": "screen_size",
            "source_text": "27 дюймов"
          },
          {
            "token": "144hz_display",
            "label": "144hz display",
            "status": "missing",
            "signal_key": "refresh_rate",
            "source_text": "144 Гц"
          },
          {
            "token": "ips",
            "label": "IPS",
            "status": "confirmed",
            "signal_key": "matrix_type",
            "source_text": "IPS"
          }
        ],
        "soft_wish_signal_scores": {
          "height_adjustable": 0
        }
      }
    },
    "segment_leaders": {
      "price_leader": {
        "name": "27\" Монитор DEXP DQ27N1 V3 черный",
        "url": "https://www.dns-shop.ru/product/7329627da8cd0ab3/27-monitor-dexp-dq27n1-v3-cernyj/",
        "price": 11499,
        "score": 22,
        "fit_score": 22,
        "match_status": "partial",
        "matched_hard_wishes": [
          "27_inch",
          "ips"
        ],
        "contradicted_hard_wishes": [],
        "matched_soft_wishes": [],
        "missing_hard_wishes": [
          "144hz_display"
        ],
        "missing_soft_wishes": [
          "good_color_accuracy",
          "height_adjustable"
        ],
        "brand_match": false,
        "query_match": true,
        "brand_mismatch": false,
        "details_confirmed_all_hard_wishes": false,
        "source_hard_wishes_count": 3,
        "normalized_hard_wishes_count": 3,
        "source_signal_count": 3,
        "normalized_signal_count": 3,
        "confirmed_signals": [
          "27 дюймов",
          "IPS"
        ],
        "unconfirmed_signals": [
          "144hz display"
        ],
        "contradicted_signals": [],
        "signal_evidence": [
          {
            "token": "27_inch",
            "label": "27 дюймов",
            "status": "confirmed",
            "signal_key": "screen_size",
            "source_text": "27 дюймов"
          },
          {
            "token": "144hz_display",
            "label": "144hz display",
            "status": "missing",
            "signal_key": "refresh_rate",
            "source_text": "144 Гц"
          },
          {
            "token": "ips",
            "label": "IPS",
            "status": "confirmed",
            "signal_key": "matrix_type",
            "source_text": "IPS"
          }
        ],
        "soft_wish_signal_scores": {}
      },
      "value_leader": {
        "name": "27\" Монитор GIGABYTE G27Q черный",
        "url": "https://www.dns-shop.ru/product/505604cb758c1b80/27-monitor-gigabyte-g27q-cernyj/",
        "price": 28599,
        "score": 26,
        "fit_score": 26,
        "match_status": "partial",
        "matched_hard_wishes": [
          "27_inch",
          "ips"
        ],
        "contradicted_hard_wishes": [],
        "matched_soft_wishes": [
          "height_adjustable"
        ],
        "missing_hard_wishes": [
          "144hz_display"
        ],
        "missing_soft_wishes": [
          "good_color_accuracy"
        ],
        "brand_match": false,
        "query_match": true,
        "brand_mismatch": false,
        "details_confirmed_all_hard_wishes": false,
        "source_hard_wishes_count": 3,
        "normalized_hard_wishes_count": 3,
        "source_signal_count": 3,
        "normalized_signal_count": 3,
        "confirmed_signals": [
          "27 дюймов",
          "IPS"
        ],
        "unconfirmed_signals": [
          "144hz display"
        ],
        "contradicted_signals": [],
        "signal_evidence": [
          {
            "token": "27_inch",
            "label": "27 дюймов",
            "status": "confirmed",
            "signal_key": "screen_size",
            "source_text": "27 дюймов"
          },
          {
            "token": "144hz_display",
            "label": "144hz display",
            "status": "missing",
            "signal_key": "refresh_rate",
            "source_text": "144 Гц"
          },
          {
            "token": "ips",
            "label": "IPS",
            "status": "confirmed",
            "signal_key": "matrix_type",
            "source_text": "IPS"
          }
        ],
        "soft_wish_signal_scores": {
          "height_adjustable": 0
        }
      },
      "spec_leader": {
        "name": "27\" Монитор Acer Nitro XV275KPymipruzx черный",
        "url": "https://www.dns-shop.ru/product/dcaf8f192805ed20/27-monitor-acer-nitro-xv275kpymipruzx-cernyj/",
        "price": 33499,
        "score": 26,
        "fit_score": 26,
        "match_status": "partial",
        "matched_hard_wishes": [
          "27_inch",
          "ips"
        ],
        "contradicted_hard_wishes": [],
        "matched_soft_wishes": [
          "height_adjustable"
        ],
        "missing_hard_wishes": [
          "144hz_display"
        ],
        "missing_soft_wishes": [
          "good_color_accuracy"
        ],
        "brand_match": false,
        "query_match": true,
        "brand_mismatch": false,
        "details_confirmed_all_hard_wishes": false,
        "source_hard_wishes_count": 3,
        "normalized_hard_wishes_count": 3,
        "source_signal_count": 3,
        "normalized_signal_count": 3,
        "confirmed_signals": [
          "27 дюймов",
          "IPS"
        ],
        "unconfirmed_signals": [
          "144hz display"
        ],
        "contradicted_signals": [],
        "signal_evidence": [
          {
            "token": "27_inch",
            "label": "27 дюймов",
            "status": "confirmed",
            "signal_key": "screen_size",
            "source_text": "27 дюймов"
          },
          {
            "token": "144hz_display",
            "label": "144hz display",
            "status": "missing",
            "signal_key": "refresh_rate",
            "source_text": "144 Гц"
          },
          {
            "token": "ips",
            "label": "IPS",
            "status": "confirmed",
            "signal_key": "matrix_type",
            "source_text": "IPS"
          }
        ],
        "soft_wish_signal_scores": {
          "height_adjustable": 0
        }
      }
    },
    "budget_defined": true,
    "use_segment_leaders": false,
    "request_has_hard_signals": true,
    "other_candidates": [
      {
        "name": "27\" Монитор ASUS ProArt PA278CGV черный",
        "url": "https://www.dns-shop.ru/product/226d8b65427ed582/27-monitor-asus-proart-pa278cgv-cernyj/",
        "price": 31999,
        "score": 26,
        "fit_score": 26,
        "match_status": "partial",
        "matched_hard_wishes": [
          "27_inch",
          "ips"
        ],
        "contradicted_hard_wishes": [],
        "matched_soft_wishes": [
          "height_adjustable"
        ],
        "missing_hard_wishes": [
          "144hz_display"
        ],
        "missing_soft_wishes": [
          "good_color_accuracy"
        ],
        "brand_match": false,
        "query_match": true,
        "brand_mismatch": false,
        "details_confirmed_all_hard_wishes": false,
        "source_hard_wishes_count": 3,
        "normalized_hard_wishes_count": 3,
        "source_signal_count": 3,
        "normalized_signal_count": 3,
        "confirmed_signals": [
          "27 дюймов",
          "IPS"
        ],
        "unconfirmed_signals": [
          "144hz display"
        ],
        "contradicted_signals": [],
        "signal_evidence": [
          {
            "token": "27_inch",
            "label": "27 дюймов",
            "status": "confirmed",
            "signal_key": "screen_size",
            "source_text": "27 дюймов"
          },
          {
            "token": "144hz_display",
            "label": "144hz display",
            "status": "missing",
            "signal_key": "refresh_rate",
            "source_text": "144 Гц"
          },
          {
            "token": "ips",
            "label": "IPS",
            "status": "confirmed",
            "signal_key": "matrix_type",
            "source_text": "IPS"
          }
        ],
        "soft_wish_signal_scores": {
          "height_adjustable": 0
        },
        "score_gap_to_leader": 0
      },
      {
        "name": "27\" Монитор Acer Nitro XV275KPymipruzx черный",
        "url": "https://www.dns-shop.ru/product/dcaf8f192805ed20/27-monitor-acer-nitro-xv275kpymipruzx-cernyj/",
        "price": 33499,
        "score": 26,
        "fit_score": 26,
        "match_status": "partial",
        "matched_hard_wishes": [
          "27_inch",
          "ips"
        ],
        "contradicted_hard_wishes": [],
        "matched_soft_wishes": [
          "height_adjustable"
        ],
        "missing_hard_wishes": [
          "144hz_display"
        ],
        "missing_soft_wishes": [
          "good_color_accuracy"
        ],
        "brand_match": false,
        "query_match": true,
        "brand_mismatch": false,
        "details_confirmed_all_hard_wishes": false,
        "source_hard_wishes_count": 3,
        "normalized_hard_wishes_count": 3,
        "source_signal_count": 3,
        "normalized_signal_count": 3,
        "confirmed_signals": [
          "27 дюймов",
          "IPS"
        ],
        "unconfirmed_signals": [
          "144hz display"
        ],
        "contradicted_signals": [],
        "signal_evidence": [
          {
            "token": "27_inch",
            "label": "27 дюймов",
            "status": "confirmed",
            "signal_key": "screen_size",
            "source_text": "27 дюймов"
          },
          {
            "token": "144hz_display",
            "label": "144hz display",
            "status": "missing",
            "signal_key": "refresh_rate",
            "source_text": "144 Гц"
          },
          {
            "token": "ips",
            "label": "IPS",
            "status": "confirmed",
            "signal_key": "matrix_type",
            "source_text": "IPS"
          }
        ],
        "soft_wish_signal_scores": {
          "height_adjustable": 0
        },
        "score_gap_to_leader": 0
      },
      {
        "name": "27\" Монитор DEXP DQ27N1 V3 черный",
        "url": "https://www.dns-shop.ru/product/7329627da8cd0ab3/27-monitor-dexp-dq27n1-v3-cernyj/",
        "price": 11499,
        "score": 22,
        "fit_score": 22,
        "match_status": "partial",
        "matched_hard_wishes": [
          "27_inch",
          "ips"
        ],
        "contradicted_hard_wishes": [],
        "matched_soft_wishes": [],
        "missing_hard_wishes": [
          "144hz_display"
        ],
        "missing_soft_wishes": [
          "good_color_accuracy",
          "height_adjustable"
        ],
        "brand_match": false,
        "query_match": true,
        "brand_mismatch": false,
        "details_confirmed_all_hard_wishes": false,
        "source_hard_wishes_count": 3,
        "normalized_hard_wishes_count": 3,
        "source_signal_count": 3,
        "normalized_signal_count": 3,
        "confirmed_signals": [
          "27 дюймов",
          "IPS"
        ],
        "unconfirmed_signals": [
          "144hz display"
        ],
        "contradicted_signals": [],
        "signal_evidence": [
          {
            "token": "27_inch",
            "label": "27 дюймов",
            "status": "confirmed",
            "signal_key": "screen_size",
            "source_text": "27 дюймов"
          },
          {
            "token": "144hz_display",
            "label": "144hz display",
            "status": "missing",
            "signal_key": "refresh_rate",
            "source_text": "144 Гц"
          },
          {
            "token": "ips",
            "label": "IPS",
            "status": "confirmed",
            "signal_key": "matrix_type",
            "source_text": "IPS"
          }
        ],
        "soft_wish_signal_scores": {},
        "score_gap_to_leader": 4
      },
      {
        "name": "27\" Монитор LG UltraGear 27GN800-B черный",
        "url": "https://www.dns-shop.ru/product/e9f9c6ba4f63ed20/27-monitor-lg-ultragear-27gn800-b-cernyj/",
        "price": 26199,
        "score": 22,
        "fit_score": 22,
        "match_status": "partial",
        "matched_hard_wishes": [
          "27_inch",
          "ips"
        ],
        "contradicted_hard_wishes": [],
        "matched_soft_wishes": [],
        "missing_hard_wishes": [
          "144hz_display"
        ],
        "missing_soft_wishes": [
          "good_color_accuracy",
          "height_adjustable"
        ],
        "brand_match": false,
        "query_match": true,
        "brand_mismatch": false,
        "details_confirmed_all_hard_wishes": false,
        "source_hard_wishes_count": 3,
        "normalized_hard_wishes_count": 3,
        "source_signal_count": 3,
        "normalized_signal_count": 3,
        "confirmed_signals": [
          "27 дюймов",
          "IPS"
        ],
        "unconfirmed_signals": [
          "144hz display"
        ],
        "contradicted_signals": [],
        "signal_evidence": [
          {
            "token": "27_inch",
            "label": "27 дюймов",
            "status": "confirmed",
            "signal_key": "screen_size",
            "source_text": "27 дюймов"
          },
          {
            "token": "144hz_display",
            "label": "144hz display",
            "status": "missing",
            "signal_key": "refresh_rate",
            "source_text": "144 Гц"
          },
          {
            "token": "ips",
            "label": "IPS",
            "status": "confirmed",
            "signal_key": "matrix_type",
            "source_text": "IPS"
          }
        ],
        "soft_wish_signal_scores": {},
        "score_gap_to_leader": 4
      }
    ],
    "competitors": [
      {
        "name": "27\" Монитор ASUS ProArt PA278CGV черный",
        "url": "https://www.dns-shop.ru/product/226d8b65427ed582/27-monitor-asus-proart-pa278cgv-cernyj/",
        "price": 31999,
        "score": 26,
        "fit_score": 26,
        "match_status": "partial",
        "matched_hard_wishes": [
          "27_inch",
          "ips"
        ],
        "contradicted_hard_wishes": [],
        "matched_soft_wishes": [
          "height_adjustable"
        ],
        "missing_hard_wishes": [
          "144hz_display"
        ],
        "missing_soft_wishes": [
          "good_color_accuracy"
        ],
        "brand_match": false,
        "query_match": true,
        "brand_mismatch": false,
        "details_confirmed_all_hard_wishes": false,
        "source_hard_wishes_count": 3,
        "normalized_hard_wishes_count": 3,
        "source_signal_count": 3,
        "normalized_signal_count": 3,
        "confirmed_signals": [
          "27 дюймов",
          "IPS"
        ],
        "unconfirmed_signals": [
          "144hz display"
        ],
        "contradicted_signals": [],
        "signal_evidence": [
          {
            "token": "27_inch",
            "label": "27 дюймов",
            "status": "confirmed",
            "signal_key": "screen_size",
            "source_text": "27 дюймов"
          },
          {
            "token": "144hz_display",
            "label": "144hz display",
            "status": "missing",
            "signal_key": "refresh_rate",
            "source_text": "144 Гц"
          },
          {
            "token": "ips",
            "label": "IPS",
            "status": "confirmed",
            "signal_key": "matrix_type",
            "source_text": "IPS"
          }
        ],
        "soft_wish_signal_scores": {
          "height_adjustable": 0
        },
        "score_gap_to_leader": 0
      },
      {
        "name": "27\" Монитор Acer Nitro XV275KPymipruzx черный",
        "url": "https://www.dns-shop.ru/product/dcaf8f192805ed20/27-monitor-acer-nitro-xv275kpymipruzx-cernyj/",
        "price": 33499,
        "score": 26,
        "fit_score": 26,
        "match_status": "partial",
        "matched_hard_wishes": [
          "27_inch",
          "ips"
        ],
        "contradicted_hard_wishes": [],
        "matched_soft_wishes": [
          "height_adjustable"
        ],
        "missing_hard_wishes": [
          "144hz_display"
        ],
        "missing_soft_wishes": [
          "good_color_accuracy"
        ],
        "brand_match": false,
        "query_match": true,
        "brand_mismatch": false,
        "details_confirmed_all_hard_wishes": false,
        "source_hard_wishes_count": 3,
        "normalized_hard_wishes_count": 3,
        "source_signal_count": 3,
        "normalized_signal_count": 3,
        "confirmed_signals": [
          "27 дюймов",
          "IPS"
        ],
        "unconfirmed_signals": [
          "144hz display"
        ],
        "contradicted_signals": [],
        "signal_evidence": [
          {
            "token": "27_inch",
            "label": "27 дюймов",
            "status": "confirmed",
            "signal_key": "screen_size",
            "source_text": "27 дюймов"
          },
          {
            "token": "144hz_display",
            "label": "144hz display",
            "status": "missing",
            "signal_key": "refresh_rate",
            "source_text": "144 Гц"
          },
          {
            "token": "ips",
            "label": "IPS",
            "status": "confirmed",
            "signal_key": "matrix_type",
            "source_text": "IPS"
          }
        ],
        "soft_wish_signal_scores": {
          "height_adjustable": 0
        },
        "score_gap_to_leader": 0
      },
      {
        "name": "27\" Монитор DEXP DQ27N1 V3 черный",
        "url": "https://www.dns-shop.ru/product/7329627da8cd0ab3/27-monitor-dexp-dq27n1-v3-cernyj/",
        "price": 11499,
        "score": 22,
        "fit_score": 22,
        "match_status": "partial",
        "matched_hard_wishes": [
          "27_inch",
          "ips"
        ],
        "contradicted_hard_wishes": [],
        "matched_soft_wishes": [],
        "missing_hard_wishes": [
          "144hz_display"
        ],
        "missing_soft_wishes": [
          "good_color_accuracy",
          "height_adjustable"
        ],
        "brand_match": false,
        "query_match": true,
        "brand_mismatch": false,
        "details_confirmed_all_hard_wishes": false,
        "source_hard_wishes_count": 3,
        "normalized_hard_wishes_count": 3,
        "source_signal_count": 3,
        "normalized_signal_count": 3,
        "confirmed_signals": [
          "27 дюймов",
          "IPS"
        ],
        "unconfirmed_signals": [
          "144hz display"
        ],
        "contradicted_signals": [],
        "signal_evidence": [
          {
            "token": "27_inch",
            "label": "27 дюймов",
            "status": "confirmed",
            "signal_key": "screen_size",
            "source_text": "27 дюймов"
          },
          {
            "token": "144hz_display",
            "label": "144hz display",
            "status": "missing",
            "signal_key": "refresh_rate",
            "source_text": "144 Гц"
          },
          {
            "token": "ips",
            "label": "IPS",
            "status": "confirmed",
            "signal_key": "matrix_type",
            "source_text": "IPS"
          }
        ],
        "soft_wish_signal_scores": {},
        "score_gap_to_leader": 4
      },
      {
        "name": "27\" Монитор LG UltraGear 27GN800-B черный",
        "url": "https://www.dns-shop.ru/product/e9f9c6ba4f63ed20/27-monitor-lg-ultragear-27gn800-b-cernyj/",
        "price": 26199,
        "score": 22,
        "fit_score": 22,
        "match_status": "partial",
        "matched_hard_wishes": [
          "27_inch",
          "ips"
        ],
        "contradicted_hard_wishes": [],
        "matched_soft_wishes": [],
        "missing_hard_wishes": [
          "144hz_display"
        ],
        "missing_soft_wishes": [
          "good_color_accuracy",
          "height_adjustable"
        ],
        "brand_match": false,
        "query_match": true,
        "brand_mismatch": false,
        "details_confirmed_all_hard_wishes": false,
        "source_hard_wishes_count": 3,
        "normalized_hard_wishes_count": 3,
        "source_signal_count": 3,
        "normalized_signal_count": 3,
        "confirmed_signals": [
          "27 дюймов",
          "IPS"
        ],
        "unconfirmed_signals": [
          "144hz display"
        ],
        "contradicted_signals": [],
        "signal_evidence": [
          {
            "token": "27_inch",
            "label": "27 дюймов",
            "status": "confirmed",
            "signal_key": "screen_size",
            "source_text": "27 дюймов"
          },
          {
            "token": "144hz_display",
            "label": "144hz display",
            "status": "missing",
            "signal_key": "refresh_rate",
            "source_text": "144 Гц"
          },
          {
            "token": "ips",
            "label": "IPS",
            "status": "confirmed",
            "signal_key": "matrix_type",
            "source_text": "IPS"
          }
        ],
        "soft_wish_signal_scores": {},
        "score_gap_to_leader": 4
      }
    ],
    "all_candidates_rejected": false,
    "retrieval_evidence": [],
    "evidence_ledger": [
      {
        "token": "27_inch",
        "label": "27 дюймов",
        "status": "confirmed",
        "signal_key": "screen_size",
        "source_text": "27 дюймов"
      },
      {
        "token": "144hz_display",
        "label": "144hz display",
        "status": "missing",
        "signal_key": "refresh_rate",
        "source_text": "144 Гц"
      },
      {
        "token": "ips",
        "label": "IPS",
        "status": "confirmed",
        "signal_key": "matrix_type",
        "source_text": "IPS"
      }
    ],
    "request_profile": {
      "ranking_policy": "",
      "price_band_hint": "",
      "soft_wishes": [
        "good_color_accuracy",
        "height_adjustable"
      ],
      "price_min": null,
      "price_max": 35000
    },
    "scoring": {
      "hard_wish_weight": 10,
      "soft_wish_weight": 4,
      "brand_weight": 3,
      "query_weight": 2
    }
  },
  "answer": "Лучший вариант\n27\" Монитор GIGABYTE G27Q черный, 28 599 руб. Точного совпадения нет.\n\nПочему он подходит\nТочного совпадения нет. Это лучший из найденных вариантов, но не точное совпадение под запрос. Совпадает по: 27 inch, ips. Не подтверждено: 144hz display. Часть условий противоречит карточке или не подтверждена полностью. Ключевые факты по карточке: диагональ 27\"; матрица IPS; частота 144 Гц.\n\nЧто сильнее у альтернатив\n27\" Монитор DEXP DQ27N1 V3 черный, 11 499 руб. Этот вариант интересен прежде всего более низкой ценой. Он дешевле лидера на 17 100 руб.. По карточке выделяются: диагональ 27\"; матрица IPS.\n\nКомпромиссы и проверки\nТочное совпадение по всем жёстким условиям не подтверждено."
}
```
