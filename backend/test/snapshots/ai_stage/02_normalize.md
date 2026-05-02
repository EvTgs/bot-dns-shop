# 02_normalize

```text
{
  "technical_prompt_and_input": [
    {
      "role": "system",
      "content": "Нормализуй товарный запрос в JSON-объект. Верни только JSON без markdown и пояснений.\nФормат:\n{\n  \"product_type\": \"...\",\n  \"query\": \"...\",\n  \"price_min\": 0,\n  \"price_max\": 0,\n  \"brand\": \"\",\n  \"constraints\": [\n    {\"key\": \"...\", \"op\": \">=\", \"value\": 120, \"unit\": \"hz\", \"source_text\": \"...\"}\n  ],\n  \"soft_wishes\": [\"good_camera\", \"good_battery\"]\n}\n\nПравила:\n- query — короткая русская поисковая фраза без бренда.\n- brand — только если бренд указан явно или однозначен.\n- constraints — только проверяемые параметры DNS.\n- soft_wishes — только субъективные пожелания, они не должны превращаться в DNS-фильтры.\n\nОператоры:\n- от / не меньше / не ниже / или выше -> \">=\"\n- до / не больше / не выше -> \"<=\"\n- точное значение -> \"==\"\n\nПоддерживаемые keys:\n- ram\n- storage\n- storage_type\n- refresh_rate\n- gpu\n- matrix_type\n- sewing_operations\n- shuttle_type\n- buttonhole\n- speed_control\n- work_area_light\n- network\n- nfc\n- protection\n- fast_charge\n- wireless_charge\n- year\n- width\n- height\n- depth\n- weight\n- volume\n- energy_class\n- cooling_system\n- freezer_position\n- inverter_compressor\n- screen_finish\n\nПримеры:\n- \"от 12 ГБ ОЗУ\" -> {\"key\":\"ram\",\"op\":\">=\",\"value\":12,\"unit\":\"gb\"}\n- \"памятью от 256 ГБ\" -> {\"key\":\"storage\",\"op\":\">=\",\"value\":256,\"unit\":\"gb\"}\n- \"экраном от 120 Гц\" -> {\"key\":\"refresh_rate\",\"op\":\">=\",\"value\":120,\"unit\":\"hz\"}\n- \"RTX 4070 или выше\" -> {\"key\":\"gpu\",\"op\":\">=\",\"value\":\"rtx 4070\",\"unit\":\"\"}\n- \"AMOLED-экраном\" -> {\"key\":\"matrix_type\",\"op\":\"==\",\"value\":\"amoled\",\"unit\":\"\"}\n- \"горизонтальным челноком\" -> {\"key\":\"shuttle_type\",\"op\":\"==\",\"value\":\"horizontal\",\"unit\":\"\"}\n- \"автоматическим выполнением петли\" -> {\"key\":\"buttonhole\",\"op\":\"==\",\"value\":\"automatic\",\"unit\":\"\"}\n- \"не меньше 30 швейных операций\" -> {\"key\":\"sewing_operations\",\"op\":\">=\",\"value\":30,\"unit\":\"\"}\n- \"регулировкой скорости\" -> {\"key\":\"speed_control\",\"op\":\"==\",\"value\":true,\"unit\":\"\"}\n- \"подсветкой рабочей зоны\" -> {\"key\":\"work_area_light\",\"op\":\"==\",\"value\":true,\"unit\":\"\"}\n- \"поддержкой 5G\" -> {\"key\":\"network\",\"op\":\"==\",\"value\":\"5g\",\"unit\":\"\"}\n- \"NFC\" -> {\"key\":\"nfc\",\"op\":\"==\",\"value\":true,\"unit\":\"\"}\n- \"защитой не ниже IP68\" -> {\"key\":\"protection\",\"op\":\">=\",\"value\":\"ip68\",\"unit\":\"\"}\n- \"быстрой зарядкой\" -> {\"key\":\"fast_charge\",\"op\":\"==\",\"value\":true,\"unit\":\"\"}\n- \"не старше 2024 года\" -> {\"key\":\"year\",\"op\":\">=\",\"value\":2024,\"unit\":\"\"}\n- \"шириной до 60 см\" -> {\"key\":\"width\",\"op\":\"<=\",\"value\":60,\"unit\":\"cm\"}\n- \"объемом от 300 л\" -> {\"key\":\"volume\",\"op\":\">=\",\"value\":300,\"unit\":\"l\"}\n- \"классом энергопотребления не ниже A\" -> {\"key\":\"energy_class\",\"op\":\">=\",\"value\":\"a\",\"unit\":\"\"}\n- \"No Frost\" -> {\"key\":\"cooling_system\",\"op\":\"==\",\"value\":\"no_frost\",\"unit\":\"\"}\n- \"морозильной камерой снизу\" -> {\"key\":\"freezer_position\",\"op\":\"==\",\"value\":\"bottom\",\"unit\":\"\"}\n- \"инверторным компрессором\" -> {\"key\":\"inverter_compressor\",\"op\":\"==\",\"value\":true,\"unit\":\"\"}\n- \"матовым покрытием\" -> {\"key\":\"screen_finish\",\"op\":\"==\",\"value\":\"matte\",\"unit\":\"\"}\n\nsoft_wishes:\n- good_camera\n- good_battery\n- quiet\n- reliable\n- powerful\n- for_programmer\n- for_gaming\n- lightweight\n\nНе выдумывай constraints, которых нет в запросе."
    },
    {
      "role": "user",
      "content": "{\"task\": \"normalize_query\", \"question\": \"Найди швейную машину для дома с горизонтальным челноком, автоматическим выполнением петли, не меньше 30 швейных операций, регулировкой скорости, подсветкой рабочей зоны, возможностью шить плотные ткани, надежной сборкой и простым управлением, бюджет до 25 000 рублей\"}"
    }
  ],
  "output": {
    "raw": "{\n  \"product_type\": \"sewing_machine\",\n  \"query\": \"швейная машина для дома\",\n  \"price_min\": 0,\n  \"price_max\": 25000,\n  \"brand\": \"\",\n  \"constraints\": [\n    {\"key\": \"shuttle_type\", \"op\": \"==\", \"value\": \"horizontal\", \"unit\": \"\", \"source_text\": \"горизонтальным челноком\"},\n    {\"key\": \"buttonhole\", \"op\": \"==\", \"value\": \"automatic\", \"unit\": \"\", \"source_text\": \"автоматическим выполнением петли\"},\n    {\"key\": \"sewing_operations\", \"op\": \">=\", \"value\": 30, \"unit\": \"\", \"source_text\": \"не меньше 30 швейных операций\"},\n    {\"key\": \"speed_control\", \"op\": \"==\", \"value\": true, \"unit\": \"\", \"source_text\": \"регулировкой скорости\"},\n    {\"key\": \"work_area_light\", \"op\": \"==\", \"value\": true, \"unit\": \"\", \"source_text\": \"подсветкой рабочей зоны\"}\n  ],\n  \"soft_wishes\": [\"powerful\", \"reliable\"]\n}",
    "parsed": {
      "product_type": "sewingmachine",
      "query": "швейная машина",
      "price_min": 0,
      "price_max": 25000,
      "brand": "",
      "constraints": [
        {
          "key": "shuttle_type",
          "op": "==",
          "value": "horizontal",
          "unit": "",
          "source_text": "горизонтальным челноком"
        },
        {
          "key": "buttonhole",
          "op": "==",
          "value": "automatic",
          "unit": "",
          "source_text": "автоматическим выполнением петли"
        },
        {
          "key": "sewing_operations",
          "op": ">=",
          "value": "30",
          "unit": "",
          "source_text": "не меньше 30 швейных операций"
        },
        {
          "key": "speed_control",
          "op": "==",
          "value": "True",
          "unit": "",
          "source_text": "регулировкой скорости"
        },
        {
          "key": "work_area_light",
          "op": "==",
          "value": "True",
          "unit": "",
          "source_text": "подсветкой рабочей зоны"
        }
      ],
      "wishes": [
        "shuttle_type_horizontal",
        "buttonhole_automatic",
        "sewing_operations_from_30",
        "speed_control",
        "work_area_light"
      ],
      "soft_wishes": [
        "reliable"
      ]
    }
  }
}
```
