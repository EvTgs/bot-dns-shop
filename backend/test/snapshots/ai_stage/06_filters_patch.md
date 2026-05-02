# 06_filters_patch

```text
{
  "technical_prompt_and_input": "SKIPPED (preselected_hard_wishes_covered)",
  "output": {
    "skipped": true,
    "reason": "preselected_hard_wishes_covered",
    "preselected_filters": [
      {
        "id": "f[6jx]",
        "name": "Источник подсветки",
        "values": [
          {
            "id": "4m",
            "name": "LED"
          }
        ]
      },
      {
        "id": "f[9ns]",
        "name": "Регулировка скорости шитья без педали",
        "values": [
          {
            "id": "arlw",
            "name": "бесступенчатая"
          }
        ]
      },
      {
        "id": "fr[ux]",
        "name": "Количество швейных операций",
        "min": 30.0,
        "max": 478
      },
      {
        "id": "f[uy]",
        "name": "Выполнение петли",
        "values": [
          {
            "id": "5i5",
            "name": "автомат"
          },
          {
            "id": "5i6",
            "name": "полуавтомат"
          }
        ]
      },
      {
        "id": "f[uw]",
        "name": "Тип челнока",
        "values": [
          {
            "id": "5i1",
            "name": "горизонтальный"
          }
        ]
      },
      {
        "id": "price",
        "min": 0,
        "max": 25000
      }
    ],
    "coverage": [
      {
        "constraint_key": "shuttle_type",
        "status": "covered",
        "confidence": 0.96,
        "selected_filter_ids": [
          "f[uw]"
        ],
        "selected_values": [
          "горизонтальный"
        ],
        "reason": ""
      },
      {
        "constraint_key": "buttonhole",
        "status": "covered",
        "confidence": 0.96,
        "selected_filter_ids": [
          "f[uy]"
        ],
        "selected_values": [
          "автомат",
          "полуавтомат"
        ],
        "reason": ""
      },
      {
        "constraint_key": "sewing_operations",
        "status": "covered",
        "confidence": 0.96,
        "selected_filter_ids": [
          "fr[ux]"
        ],
        "selected_values": [],
        "reason": ""
      },
      {
        "constraint_key": "speed_control",
        "status": "covered",
        "confidence": 0.96,
        "selected_filter_ids": [
          "f[9ns]"
        ],
        "selected_values": [
          "бесступенчатая"
        ],
        "reason": ""
      },
      {
        "constraint_key": "work_area_light",
        "status": "covered",
        "confidence": 0.96,
        "selected_filter_ids": [
          "f[6jx]"
        ],
        "selected_values": [
          "LED"
        ],
        "reason": ""
      }
    ],
    "candidate_packets": []
  }
}
```
