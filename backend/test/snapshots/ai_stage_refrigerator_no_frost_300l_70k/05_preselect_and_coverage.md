# 05_preselect_and_coverage

```text
{
  "technical_prompt_and_input": {
    "section_url": "https://www.dns-shop.ru/search/?q=%D1%85%D0%BE%D0%BB%D0%BE%D0%B4%D0%B8%D0%BB%D1%8C%D0%BD%D0%B8%D0%BA&price=0-70000&category=4e2a7cdb390b7fd7",
    "normalized": {
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
    }
  },
  "output": {
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
    "coverage_requires_patch": false,
    "candidate_packets": [
      {
        "constraint": {
          "key": "cooling_system",
          "op": "==",
          "value": "no_frost",
          "unit": "",
          "source_text": "No Frost"
        },
        "candidate_filters": [
          {
            "id": "f[2v8]",
            "name": "Размораживание морозильной камеры / НТО",
            "group": "Основные характеристики",
            "type": "checkbox",
            "values": [
              {
                "id": "5e1",
                "name": "No Frost"
              }
            ],
            "total_values_count": 3
          },
          {
            "id": "f[tq]",
            "name": "Размораживание холодильной камеры",
            "group": "Основные характеристики",
            "type": "checkbox",
            "values": [
              {
                "id": "5e1",
                "name": "No Frost"
              }
            ],
            "total_values_count": 2
          }
        ]
      },
      {
        "constraint": {
          "key": "width",
          "op": "<=",
          "value": "60",
          "unit": "cm",
          "source_text": "шириной до 60 см"
        },
        "candidate_filters": [
          {
            "id": "fr[8g]",
            "name": "Ширина (см)",
            "group": "Габариты и вес",
            "type": "range-radio",
            "values": [
              {
                "id": "38ed65a2b334f28deed1dd4f792250b5",
                "name": "Менее 49.9",
                "numeric": 49.9,
                "unit": ""
              },
              {
                "id": "ca6daf411d37f374c77392a93a175507",
                "name": "50 - 54.9",
                "numeric": 50.0,
                "unit": ""
              },
              {
                "id": "24fcceb386946af1dd2b302f0e3af96b",
                "name": "55 - 59.9",
                "numeric": 55.0,
                "unit": ""
              },
              {
                "id": "4e068a1e2215a72c0fa9e665096be33d",
                "name": "60 - 69.9",
                "numeric": 60.0,
                "unit": ""
              },
              {
                "id": "29ae944e12bc285125084fdb01ee930a",
                "name": "70 - 89.9",
                "numeric": 70.0,
                "unit": ""
              },
              {
                "id": "5fcf1f160825ef34da3cf2a8ede551b4",
                "name": "90 и более",
                "numeric": 90.0,
                "unit": "л"
              }
            ],
            "total_values_count": 6,
            "range": {
              "min": 20.8,
              "max": 105.4,
              "min_selected": null,
              "max_selected": null
            }
          },
          {
            "id": "f[4tk]",
            "name": "Управление со смартфона",
            "group": "Индикация и управление",
            "type": "checkbox",
            "values": [],
            "total_values_count": 3
          },
          {
            "id": "f[8yg]",
            "name": "Возможность смены фронтальной панели",
            "group": "Конструкция и комплектация",
            "type": "checkbox",
            "values": [],
            "total_values_count": 3
          },
          {
            "id": "fr[6cn]",
            "name": "Глубина с открытой дверцей (см)",
            "group": "Габариты и вес",
            "type": "range-radio",
            "values": [
              {
                "id": "d4d8ace7f53a4854404a9daa8c1c6ec5",
                "name": "Менее 99.99",
                "numeric": 99.99,
                "unit": ""
              },
              {
                "id": "9c0f8a9bb74b1a39328ec4d5d0980e23",
                "name": "100 - 119.99",
                "numeric": 100.0,
                "unit": ""
              },
              {
                "id": "16bc3dee69b6f12ae1295ea9a02a7824",
                "name": "120 - 139.99",
                "numeric": 120.0,
                "unit": ""
              },
              {
                "id": "6c63cd5da71eacb8c04c9feaa5575bc4",
                "name": "140 и более",
                "numeric": 140.0,
                "unit": "л"
              }
            ],
            "total_values_count": 4,
            "range": {
              "min": 68,
              "max": 161,
              "min_selected": null,
              "max_selected": null
            }
          },
          {
            "id": "fr[8i]",
            "name": "Высота (см)",
            "group": "Габариты и вес",
            "type": "range-radio",
            "values": [
              {
                "id": "7fff641213940c60663d1c97ccc6f76f",
                "name": "Менее 84.99",
                "numeric": 84.99,
                "unit": ""
              },
              {
                "id": "c7f5d4ac8e8a85029853db6a41e1b4c7",
                "name": "85 - 154.99",
                "numeric": 85.0,
                "unit": ""
              },
              {
                "id": "570fed2714952aabed0788c2d0d2076f",
                "name": "155 - 174.99",
                "numeric": 155.0,
                "unit": ""
              },
              {
                "id": "00f74014b6b6251468c56c90f5662816",
                "name": "175 - 184.99",
                "numeric": 175.0,
                "unit": ""
              },
              {
                "id": "a8bc34424b201a5d6607649045dc3b17",
                "name": "185 - 199.99",
                "numeric": 185.0,
                "unit": ""
              },
              {
                "id": "498ff46ce5995ce07e4fb986f6dc4a79",
                "name": "200 и более",
                "numeric": 200.0,
                "unit": "л"
              }
            ],
            "total_values_count": 6,
            "range": {
              "min": 26.5,
              "max": 219.5,
              "min_selected": null,
              "max_selected": null
            }
          }
        ]
      },
      {
        "constraint": {
          "key": "volume",
          "op": ">=",
          "value": "300",
          "unit": "l",
          "source_text": "общим объемом от 300 л"
        },
        "candidate_filters": [
          {
            "id": "fr[tk]",
            "name": "Общий полезный объем (л)",
            "group": "Объем",
            "type": "range-radio",
            "values": [
              {
                "id": "61a8d780c5d3a295ba5db24ac62aef52",
                "name": "350 - 449.9",
                "numeric": 350.0,
                "unit": ""
              },
              {
                "id": "6b9b88fcd80b06318ce4bca8f34db25b",
                "name": "450 - 549.9",
                "numeric": 450.0,
                "unit": ""
              },
              {
                "id": "bb1763f821beb3dd07f8a89ea0882eaf",
                "name": "550 и более",
                "numeric": 550.0,
                "unit": "л"
              },
              {
                "id": "a79e9c840ee5145aa857783d691cbdff",
                "name": "250 - 349.9",
                "numeric": 250.0,
                "unit": ""
              },
              {
                "id": "4930ffb2f68eb76be4f98e821c12f1f6",
                "name": "150 - 249.9",
                "numeric": 150.0,
                "unit": ""
              }
            ],
            "total_values_count": 6,
            "range": {
              "min": 4,
              "max": 750,
              "min_selected": null,
              "max_selected": null
            }
          },
          {
            "id": "fr[tl]",
            "name": "Полезный объем холодильной камеры (л)",
            "group": "Объем",
            "type": "range-radio",
            "values": [
              {
                "id": "8009ad5b3daa550b27a5e30493cc7aa5",
                "name": "300 - 399.9",
                "numeric": 300.0,
                "unit": ""
              },
              {
                "id": "c14e63daf5ddcbbbe91a92893213a98b",
                "name": "400 - 499.9",
                "numeric": 400.0,
                "unit": ""
              },
              {
                "id": "ef33b23d314d9987b6f72171802a85de",
                "name": "500 и более",
                "numeric": 500.0,
                "unit": "л"
              },
              {
                "id": "f88de80a2f9fdd3d53974fe5ff9cb445",
                "name": "200 - 299.9",
                "numeric": 200.0,
                "unit": ""
              },
              {
                "id": "4f7cdaf962fbba4d3896c1b714ecbb1b",
                "name": "100 - 199.9",
                "numeric": 100.0,
                "unit": ""
              }
            ],
            "total_values_count": 6,
            "range": {
              "min": 4,
              "max": 619,
              "min_selected": null,
              "max_selected": null
            }
          },
          {
            "id": "fr[2va]",
            "name": "Полезный объем морозильной камеры / НТО (л)",
            "group": "Объем",
            "type": "range-radio",
            "values": [
              {
                "id": "6fb80dca136889f1d2adb6e54d3360ec",
                "name": "199.91 и более",
                "numeric": 199.91,
                "unit": "л"
              },
              {
                "id": "115c2ad0dfab341404a3bfed64636eac",
                "name": "129.91 - 199.9",
                "numeric": 129.91,
                "unit": ""
              },
              {
                "id": "6c8f7e0afd21e6edeb76f6d2dece92a1",
                "name": "79.91 - 129.9",
                "numeric": 79.91,
                "unit": ""
              },
              {
                "id": "624aac67e7653949095af4031738539e",
                "name": "39.91 - 79.9",
                "numeric": 39.91,
                "unit": ""
              },
              {
                "id": "1088704dfcb6e3b47410b3e4a483c297",
                "name": "9.91 - 39.9",
                "numeric": 9.91,
                "unit": ""
              },
              {
                "id": "f45b5947ab3bbc4bf7e9333f207c4a80",
                "name": "Менее 9.9",
                "numeric": 9.9,
                "unit": ""
              }
            ],
            "total_values_count": 6,
            "range": {
              "min": 0,
              "max": 350,
              "min_selected": null,
              "max_selected": null
            }
          },
          {
            "id": "action",
            "name": "Предложения брендов",
            "group": "Основные",
            "type": "checkbox",
            "values": [],
            "total_values_count": 2
          },
          {
            "id": "f[10r]",
            "name": "Дополнительный цвет",
            "group": "Общие параметры",
            "type": "checkbox",
            "values": [],
            "total_values_count": 11
          }
        ]
      },
      {
        "constraint": {
          "key": "energy_class",
          "op": ">=",
          "value": "a",
          "unit": "",
          "source_text": "классом энергопотребления не ниже A"
        },
        "candidate_filters": [
          {
            "id": "f[5q2]",
            "name": "Класс энергоэффективности",
            "group": "Классы",
            "type": "checkbox",
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
              },
              {
                "id": "54d",
                "name": "B"
              },
              {
                "id": "29",
                "name": "C"
              }
            ],
            "total_values_count": 8
          },
          {
            "id": "brand",
            "name": "Бренд",
            "group": "Основные",
            "type": "checkbox",
            "values": [
              {
                "id": "aceline",
                "name": "Aceline"
              },
              {
                "id": "aeg",
                "name": "AEG"
              },
              {
                "id": "ardo",
                "name": "ARDO"
              },
              {
                "id": "ascoli",
                "name": "Ascoli"
              },
              {
                "id": "atlant",
                "name": "ATLANT"
              }
            ],
            "total_values_count": 71
          },
          {
            "id": "f[296]",
            "name": "Цвет, заявленный производителем",
            "group": "Общие параметры",
            "type": "checkbox",
            "values": [
              {
                "id": "4hrw",
                "name": "black"
              },
              {
                "id": "9y3j",
                "name": "gray"
              },
              {
                "id": "nqao",
                "name": "gray inox"
              },
              {
                "id": "1xa8",
                "name": "grey"
              },
              {
                "id": "4nrp",
                "name": "inox"
              }
            ],
            "total_values_count": 140
          },
          {
            "id": "f[5xj]",
            "name": "Приложение для управления",
            "group": "Умный дом",
            "type": "checkbox",
            "values": [
              {
                "id": "g6g",
                "name": "AEG"
              },
              {
                "id": "fcl6",
                "name": "ConnectLife"
              },
              {
                "id": "6ok6",
                "name": "Home Connect"
              },
              {
                "id": "7qdn",
                "name": "HomeWhiz"
              },
              {
                "id": "i5es",
                "name": "Houself"
              }
            ],
            "total_values_count": 10
          },
          {
            "id": "f[8ax]",
            "name": "Экосистема умного дома",
            "group": "Умный дом",
            "type": "checkbox",
            "values": [
              {
                "id": "g6g",
                "name": "AEG"
              },
              {
                "id": "fcl6",
                "name": "ConnectLife"
              },
              {
                "id": "5tyq",
                "name": "EVO"
              },
              {
                "id": "6ok6",
                "name": "Home Connect"
              },
              {
                "id": "pe6i",
                "name": "HomeWhiz Smart Home"
              }
            ],
            "total_values_count": 10
          }
        ]
      }
    ]
  }
}
```
