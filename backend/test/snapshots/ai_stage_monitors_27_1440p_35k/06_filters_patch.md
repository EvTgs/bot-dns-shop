# 06_filters_patch

```text
{
  "technical_prompt_and_input": "SKIPPED (preselected_hard_wishes_covered)",
  "output": {
    "skipped": true,
    "reason": "preselected_hard_wishes_covered",
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
    "candidate_packets": []
  }
}
```
