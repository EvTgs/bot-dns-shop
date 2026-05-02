# 04_candidate_packets

```text
{
  "technical_prompt_and_input": {
    "section_url": "https://www.dns-shop.ru/search/?q=%D1%88%D0%B2%D0%B5%D0%B9%D0%BD%D0%B0%D1%8F%20%D0%BC%D0%B0%D1%88%D0%B8%D0%BD%D0%B0&category=17a8cda216404e77&price=0-25000"
  },
  "output": {
    "filters_count": 61,
    "candidate_packets": [
      {
        "constraint": {
          "key": "shuttle_type",
          "op": "==",
          "value": "horizontal",
          "unit": "",
          "source_text": "горизонтальным челноком"
        },
        "candidate_filters": [
          {
            "id": "f[uw]",
            "name": "Тип челнока",
            "group": "Основные характеристики",
            "type": "checkbox",
            "values": [
              {
                "id": "5i1",
                "name": "горизонтальный"
              }
            ],
            "total_values_count": 3
          }
        ]
      },
      {
        "constraint": {
          "key": "buttonhole",
          "op": "==",
          "value": "automatic",
          "unit": "",
          "source_text": "автоматическим выполнением петли"
        },
        "candidate_filters": [
          {
            "id": "f[8v4]",
            "name": "Лапка для выметывания петли",
            "group": "Лапки",
            "type": "checkbox",
            "values": [],
            "total_values_count": 2
          },
          {
            "id": "f[uy]",
            "name": "Выполнение петли",
            "group": "Швейные операции",
            "type": "checkbox",
            "values": [
              {
                "id": "5i5",
                "name": "автомат"
              },
              {
                "id": "5i6",
                "name": "полуавтомат"
              }
            ],
            "total_values_count": 3
          }
        ]
      },
      {
        "constraint": {
          "key": "sewing_operations",
          "op": ">=",
          "value": "30",
          "unit": "",
          "source_text": "не меньше 30 швейных операций"
        },
        "candidate_filters": [
          {
            "id": "fr[ux]",
            "name": "Количество швейных операций",
            "group": "Швейные операции",
            "type": "range-radio",
            "values": [
              {
                "id": "f28fe9502296830c3f3b44f8441c1468",
                "name": "50 - 99",
                "numeric": 50.0,
                "unit": ""
              },
              {
                "id": "e12201c91f1a3bce04ae4ad0821925e5",
                "name": "100 - 199",
                "numeric": 100.0,
                "unit": ""
              },
              {
                "id": "498ff46ce5995ce07e4fb986f6dc4a79",
                "name": "200 и более",
                "numeric": 200.0,
                "unit": "л"
              },
              {
                "id": "9aab925910e3c218165dcc7f9cb87c4d",
                "name": "25 - 49",
                "numeric": 25.0,
                "unit": ""
              },
              {
                "id": "3fc93cd8ef3040c6fe61b9177f500623",
                "name": "15 - 24",
                "numeric": 15.0,
                "unit": ""
              }
            ],
            "total_values_count": 6,
            "range": {
              "min": 1,
              "max": 478,
              "min_selected": null,
              "max_selected": null
            }
          },
          {
            "id": "f[uz]",
            "name": "Количество петель",
            "group": "Швейные операции",
            "type": "checkbox",
            "values": [
              {
                "id": "1p3",
                "name": "13",
                "numeric": 13.0,
                "unit": ""
              },
              {
                "id": "1ox",
                "name": "10",
                "numeric": 10.0,
                "unit": ""
              },
              {
                "id": "bq",
                "name": "8",
                "numeric": 8.0,
                "unit": ""
              },
              {
                "id": "1p2",
                "name": "7",
                "numeric": 7.0,
                "unit": ""
              },
              {
                "id": "bo",
                "name": "6",
                "numeric": 6.0,
                "unit": ""
              },
              {
                "id": "1oy",
                "name": "5",
                "numeric": 5.0,
                "unit": ""
              },
              {
                "id": "bn",
                "name": "4",
                "numeric": 4.0,
                "unit": ""
              }
            ],
            "total_values_count": 11
          },
          {
            "id": "f[v0]",
            "name": "Максимальная длина стежка (мм)",
            "group": "Основные характеристики",
            "type": "checkbox",
            "values": [
              {
                "id": "5i9",
                "name": "7 мм",
                "numeric": 7.0,
                "unit": "мм"
              },
              {
                "id": "5ic",
                "name": "6 мм",
                "numeric": 6.0,
                "unit": "мм"
              },
              {
                "id": "5i8",
                "name": "5 мм",
                "numeric": 5.0,
                "unit": "мм"
              },
              {
                "id": "5ia",
                "name": "4.5 мм",
                "numeric": 4.5,
                "unit": "мм"
              },
              {
                "id": "13lo",
                "name": "4.1 мм",
                "numeric": 4.1,
                "unit": "мм"
              },
              {
                "id": "5i7",
                "name": "4 мм",
                "numeric": 4.0,
                "unit": "мм"
              },
              {
                "id": "112f",
                "name": "3.6 мм",
                "numeric": 3.6,
                "unit": "мм"
              }
            ],
            "total_values_count": 10
          },
          {
            "id": "f[8v2]",
            "name": "Декоративные строчки",
            "group": "Швейные операции",
            "type": "checkbox",
            "values": [],
            "total_values_count": 2
          },
          {
            "id": "f[95d]",
            "name": "Регулировка длины стежка в мм",
            "group": "Функционал",
            "type": "checkbox",
            "values": [],
            "total_values_count": 2
          }
        ]
      },
      {
        "constraint": {
          "key": "speed_control",
          "op": "==",
          "value": "True",
          "unit": "",
          "source_text": "регулировкой скорости"
        },
        "candidate_filters": [
          {
            "id": "f[9ns]",
            "name": "Регулировка скорости шитья без педали",
            "group": "Функционал",
            "type": "checkbox",
            "values": [
              {
                "id": "arlw",
                "name": "бесступенчатая"
              },
              {
                "id": "62e",
                "name": "ступенчатая"
              }
            ],
            "total_values_count": 3
          },
          {
            "id": "f[1w0]",
            "name": "Максимальная скорость шитья (ст/мин)",
            "group": "Основные характеристики",
            "type": "checkbox",
            "values": [],
            "total_values_count": 22
          },
          {
            "id": "f[v8]",
            "name": "Регулировка макс. скорости шитья с педалью",
            "group": "Функционал",
            "type": "checkbox",
            "values": [
              {
                "id": "21",
                "name": "есть"
              }
            ],
            "total_values_count": 2
          },
          {
            "id": "f[24t]",
            "name": "Ручка для переноски",
            "group": "Элементы корпуса",
            "type": "checkbox",
            "values": [
              {
                "id": "21",
                "name": "есть"
              }
            ],
            "total_values_count": 2
          },
          {
            "id": "f[6jx]",
            "name": "Источник подсветки",
            "group": "Элементы корпуса",
            "type": "checkbox",
            "values": [
              {
                "id": "4m",
                "name": "LED"
              },
              {
                "id": "h5x",
                "name": "светодиоды"
              }
            ],
            "total_values_count": 4
          }
        ]
      },
      {
        "constraint": {
          "key": "work_area_light",
          "op": "==",
          "value": "True",
          "unit": "",
          "source_text": "подсветкой рабочей зоны"
        },
        "candidate_filters": [
          {
            "id": "f[6jx]",
            "name": "Источник подсветки",
            "group": "Элементы корпуса",
            "type": "checkbox",
            "values": [
              {
                "id": "4m",
                "name": "LED"
              },
              {
                "id": "h5x",
                "name": "светодиоды"
              }
            ],
            "total_values_count": 4
          },
          {
            "id": "f[24t]",
            "name": "Ручка для переноски",
            "group": "Элементы корпуса",
            "type": "checkbox",
            "values": [
              {
                "id": "21",
                "name": "есть"
              }
            ],
            "total_values_count": 2
          },
          {
            "id": "f[8v2]",
            "name": "Декоративные строчки",
            "group": "Швейные операции",
            "type": "checkbox",
            "values": [
              {
                "id": "21",
                "name": "есть"
              }
            ],
            "total_values_count": 2
          },
          {
            "id": "f[8v3]",
            "name": "Лапка универсальная для зиг-зага",
            "group": "Лапки",
            "type": "checkbox",
            "values": [
              {
                "id": "21",
                "name": "есть"
              }
            ],
            "total_values_count": 2
          },
          {
            "id": "f[8v4]",
            "name": "Лапка для выметывания петли",
            "group": "Лапки",
            "type": "checkbox",
            "values": [
              {
                "id": "21",
                "name": "есть"
              }
            ],
            "total_values_count": 2
          }
        ]
      }
    ]
  }
}
```
