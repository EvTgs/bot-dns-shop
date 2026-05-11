# 04_candidate_packets

```text
{
  "technical_prompt_and_input": {
    "section_url": "https://www.dns-shop.ru/search/?q=%D0%BC%D0%BE%D0%BD%D0%B8%D1%82%D0%BE%D1%80&category=17a8943716404e77"
  },
  "output": {
    "filters_count": 81,
    "candidate_packets": [
      {
        "intent_signal": {
          "key": "screen_size",
          "op": "==",
          "value": "27",
          "unit": "inch",
          "source_text": "27 дюймов",
          "weight": 1.0
        },
        "constraint": {
          "key": "screen_size",
          "op": "==",
          "value": "27",
          "unit": "inch",
          "source_text": "27 дюймов",
          "weight": 1.0
        },
        "candidate_filters": [
          {
            "id": "fr[1q]",
            "name": "Диагональ экрана (дюйм)",
            "group": "Экран",
            "type": "range-radio",
            "values": [
              {
                "id": "07b55b2fbb4be2eba152cc163aa6aea6",
                "name": "26 - 29.99",
                "numeric": 26.0,
                "unit": ""
              },
              {
                "id": "b82cd4212a2f15dece1141dede954f91",
                "name": "30 - 37.99",
                "numeric": 30.0,
                "unit": ""
              },
              {
                "id": "a4ca97a920208ea23600732ec45334da",
                "name": "23 - 25.99",
                "numeric": 23.0,
                "unit": ""
              },
              {
                "id": "4d62fafc61e94a1b91aa7c51bf047d97",
                "name": "20 - 22.99",
                "numeric": 20.0,
                "unit": ""
              },
              {
                "id": "2584283adea05b6d16e192d47b18480d",
                "name": "Менее 19.99",
                "numeric": 19.99,
                "unit": ""
              },
              {
                "id": "f3875a36163b64bb9c9c4acc01e0a815",
                "name": "38 и более",
                "numeric": 38.0,
                "unit": "л"
              }
            ],
            "total_values_count": 6,
            "range": {
              "min": 13.3,
              "max": 70,
              "min_selected": null,
              "max_selected": null
            }
          }
        ]
      },
      {
        "intent_signal": {
          "key": "refresh_rate",
          "op": "==",
          "value": "144",
          "unit": "hz",
          "source_text": "144 Гц",
          "weight": 1.0
        },
        "constraint": {
          "key": "refresh_rate",
          "op": "==",
          "value": "144",
          "unit": "hz",
          "source_text": "144 Гц",
          "weight": 1.0
        },
        "candidate_filters": [
          {
            "id": "f[2b]",
            "name": "Максимальная частота обновления экрана (Гц)",
            "group": "Технические характеристики экрана",
            "type": "checkbox",
            "values": [
              {
                "id": "sp",
                "name": "144 Гц",
                "numeric": 144.0,
                "unit": "гц"
              }
            ],
            "total_values_count": 43
          },
          {
            "id": "fr[520]",
            "name": "Частота при максимальном разрешении (Гц)",
            "group": "Технические характеристики экрана",
            "type": "range-radio",
            "values": [
              {
                "id": "ce79e9c3ebc30de1b12452fd10716131",
                "name": "121 - 200",
                "numeric": 121.0,
                "unit": ""
              },
              {
                "id": "578f78455ffaa49a74c809daa6f62820",
                "name": "Менее 120",
                "numeric": 120.0,
                "unit": ""
              },
              {
                "id": "c5ae3f63d04dc854b3f6d898aee741ba",
                "name": "201 - 300",
                "numeric": 201.0,
                "unit": ""
              },
              {
                "id": "330b847fe93ab0a830f5ee6657bb79fe",
                "name": "301 - 400",
                "numeric": 301.0,
                "unit": ""
              },
              {
                "id": "59f9429013daedf6678f5af03f687ab8",
                "name": "401 и более",
                "numeric": 401.0,
                "unit": "л"
              }
            ],
            "total_values_count": 5,
            "range": {
              "min": 60,
              "max": 610,
              "min_selected": null,
              "max_selected": null
            }
          },
          {
            "id": "f[1s]",
            "name": "Угол обзора по горизонтали (градус)",
            "group": "Экран",
            "type": "checkbox",
            "values": [
              {
                "id": "fd",
                "name": "160°",
                "numeric": 160.0,
                "unit": ""
              },
              {
                "id": "fj",
                "name": "120°",
                "numeric": 120.0,
                "unit": ""
              },
              {
                "id": "fc",
                "name": "170°",
                "numeric": 170.0,
                "unit": ""
              },
              {
                "id": "fg",
                "name": "176°",
                "numeric": 176.0,
                "unit": ""
              },
              {
                "id": "fe",
                "name": "178°",
                "numeric": 178.0,
                "unit": ""
              },
              {
                "id": "ff",
                "name": "90°",
                "numeric": 90.0,
                "unit": ""
              },
              {
                "id": "6yz2",
                "name": "89°",
                "numeric": 89.0,
                "unit": ""
              }
            ],
            "total_values_count": 7
          },
          {
            "id": "f[1t]",
            "name": "Угол обзора по вертикали (градус)",
            "group": "Экран",
            "type": "checkbox",
            "values": [
              {
                "id": "fd",
                "name": "160°",
                "numeric": 160.0,
                "unit": ""
              },
              {
                "id": "fj",
                "name": "120°",
                "numeric": 120.0,
                "unit": ""
              },
              {
                "id": "fc",
                "name": "170°",
                "numeric": 170.0,
                "unit": ""
              },
              {
                "id": "fg",
                "name": "176°",
                "numeric": 176.0,
                "unit": ""
              },
              {
                "id": "fe",
                "name": "178°",
                "numeric": 178.0,
                "unit": ""
              },
              {
                "id": "6yz2",
                "name": "89°",
                "numeric": 89.0,
                "unit": ""
              },
              {
                "id": "fh",
                "name": "65°",
                "numeric": 65.0,
                "unit": ""
              }
            ],
            "total_values_count": 7
          },
          {
            "id": "f[1u]",
            "name": "Максимальное количество цветов",
            "group": "Технические характеристики экрана",
            "type": "checkbox",
            "values": [
              {
                "id": "fm",
                "name": "16.7 млн.",
                "numeric": 16.7,
                "unit": "л"
              },
              {
                "id": "fn",
                "name": "более 1 млрд.",
                "numeric": 1.0,
                "unit": "л"
              },
              {
                "id": "gv8k",
                "name": "0.26 млн.",
                "numeric": 0.26,
                "unit": "л"
              }
            ],
            "total_values_count": 3
          }
        ]
      },
      {
        "intent_signal": {
          "key": "matrix_type",
          "op": "==",
          "value": "ips",
          "unit": "",
          "source_text": "IPS",
          "weight": 1.0
        },
        "constraint": {
          "key": "matrix_type",
          "op": "==",
          "value": "ips",
          "unit": "",
          "source_text": "IPS",
          "weight": 1.0
        },
        "candidate_filters": [
          {
            "id": "f[2v]",
            "name": "Тип матрицы",
            "group": "Экран",
            "type": "checkbox",
            "values": [
              {
                "id": "1uq",
                "name": "IPS"
              }
            ],
            "total_values_count": 4
          },
          {
            "id": "f[25s]",
            "name": "Тип матрицы (подробно)",
            "group": "Экран",
            "type": "checkbox",
            "values": [
              {
                "id": "gt6j",
                "name": "Fast IPS"
              },
              {
                "id": "gt7v",
                "name": "Rapid IPS"
              },
              {
                "id": "gqx6",
                "name": "A-Si IPS"
              },
              {
                "id": "gs71",
                "name": "AAS IPS"
              },
              {
                "id": "110d",
                "name": "AH-IPS"
              }
            ],
            "total_values_count": 26
          },
          {
            "id": "f[4sg]",
            "name": "Технология динамического обновления экрана",
            "group": "Технические характеристики экрана",
            "type": "checkbox",
            "values": [],
            "total_values_count": 10
          },
          {
            "id": "f[5px]",
            "name": "Технология защиты зрения",
            "group": "Функции",
            "type": "checkbox",
            "values": [],
            "total_values_count": 4
          },
          {
            "id": "f[51i]",
            "name": "Тип подсветки экрана",
            "group": "Экран",
            "type": "checkbox",
            "values": [],
            "total_values_count": 6
          }
        ]
      }
    ]
  }
}
```
