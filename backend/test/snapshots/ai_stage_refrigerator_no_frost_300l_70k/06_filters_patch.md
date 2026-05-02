# 06_filters_patch

```text
{
  "technical_prompt_and_input": "SKIPPED (preselected_hard_wishes_covered)",
  "output": {
    "skipped": true,
    "reason": "preselected_hard_wishes_covered",
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
    "candidate_packets": []
  }
}
```
