# 02_normalize

```text
{
  "technical_prompt_and_input": [
    {
      "role": "system",
      "content": "Нормализуй товарный запрос в JSON-объект. Верни только JSON без markdown и пояснений.\nФормат:\n{\n  \"product_type\": \"...\",\n  \"query\": \"...\",\n  \"price_min\": 0,\n  \"price_max\": 0,\n  \"brand\": \"\",\n  \"constraints\": [\n    {\"key\": \"...\", \"op\": \">=\", \"value\": 120, \"unit\": \"hz\", \"source_text\": \"...\"}\n  ],\n  \"soft_wishes\": [\"good_camera\", \"good_battery\"]\n}\n\nПравила:\n- query — короткая русская поисковая фраза без бренда.\n- brand — только если бренд указан явно или однозначен.\n- constraints — только проверяемые параметры DNS.\n- soft_wishes — только субъективные пожелания, они не должны превращаться в DNS-фильтры.\n\nОператоры:\n- от / не меньше / не ниже / или выше -> \">=\"\n- до / не больше / не выше -> \"<=\"\n- точное значение -> \"==\"\n\nПоддерживаемые keys:\n- ram\n- storage\n- storage_type\n- refresh_rate\n- gpu\n- matrix_type\n- network\n- nfc\n- protection\n- fast_charge\n- wireless_charge\n- year\n- width\n- height\n- depth\n- weight\n- volume\n- energy_class\n- cooling_system\n- screen_finish\n\nПримеры:\n- \"от 12 ГБ ОЗУ\" -> {\"key\":\"ram\",\"op\":\">=\",\"value\":12,\"unit\":\"gb\"}\n- \"памятью от 256 ГБ\" -> {\"key\":\"storage\",\"op\":\">=\",\"value\":256,\"unit\":\"gb\"}\n- \"экраном от 120 Гц\" -> {\"key\":\"refresh_rate\",\"op\":\">=\",\"value\":120,\"unit\":\"hz\"}\n- \"RTX 4070 или выше\" -> {\"key\":\"gpu\",\"op\":\">=\",\"value\":\"rtx 4070\",\"unit\":\"\"}\n- \"AMOLED-экраном\" -> {\"key\":\"matrix_type\",\"op\":\"==\",\"value\":\"amoled\",\"unit\":\"\"}\n- \"поддержкой 5G\" -> {\"key\":\"network\",\"op\":\"==\",\"value\":\"5g\",\"unit\":\"\"}\n- \"NFC\" -> {\"key\":\"nfc\",\"op\":\"==\",\"value\":true,\"unit\":\"\"}\n- \"защитой не ниже IP68\" -> {\"key\":\"protection\",\"op\":\">=\",\"value\":\"ip68\",\"unit\":\"\"}\n- \"быстрой зарядкой\" -> {\"key\":\"fast_charge\",\"op\":\"==\",\"value\":true,\"unit\":\"\"}\n- \"не старше 2024 года\" -> {\"key\":\"year\",\"op\":\">=\",\"value\":2024,\"unit\":\"\"}\n- \"шириной до 60 см\" -> {\"key\":\"width\",\"op\":\"<=\",\"value\":60,\"unit\":\"cm\"}\n- \"объемом от 300 л\" -> {\"key\":\"volume\",\"op\":\">=\",\"value\":300,\"unit\":\"l\"}\n- \"классом энергопотребления не ниже A\" -> {\"key\":\"energy_class\",\"op\":\">=\",\"value\":\"a\",\"unit\":\"\"}\n- \"No Frost\" -> {\"key\":\"cooling_system\",\"op\":\"==\",\"value\":\"no_frost\",\"unit\":\"\"}\n- \"матовым покрытием\" -> {\"key\":\"screen_finish\",\"op\":\"==\",\"value\":\"matte\",\"unit\":\"\"}\n\nsoft_wishes:\n- good_camera\n- good_battery\n- quiet\n- reliable\n- powerful\n- for_programmer\n- for_gaming\n- lightweight\n\nНе выдумывай constraints, которых нет в запросе."
    },
    {
      "role": "user",
      "content": "{\"task\": \"normalize_query\", \"question\": \"Найди холодильник с No Frost, шириной до 60 см, общим объемом от 300 л, морозильной камерой снизу, классом энергопотребления не ниже A, инверторным компрессором, тихой работой и надежной сборкой, бюджет до 70 000 рублей\"}"
    }
  ],
  "output": {
    "raw": "{\n  \"product_type\": \"холодильник\",\n  \"query\": \"холодильник с морозильной камерой снизу инверторным компрессором\",\n  \"price_min\": 0,\n  \"price_max\": 70000,\n  \"brand\": \"\",\n  \"constraints\": [\n    {\"key\": \"cooling_system\", \"op\": \"==\", \"value\": \"no_frost\", \"unit\": \"\", \"source_text\": \"No Frost\"},\n    {\"key\": \"width\", \"op\": \"<=\", \"value\": 60, \"unit\": \"cm\", \"source_text\": \"шириной до 60 см\"},\n    {\"key\": \"volume\", \"op\": \">=\", \"value\": 300, \"unit\": \"l\", \"source_text\": \"общим объемом от 300 л\"},\n    {\"key\": \"energy_class\", \"op\": \">=\", \"value\": \"a\", \"unit\": \"\", \"source_text\": \"классом энергопотребления не ниже A\"}\n  ],\n  \"soft_wishes\": [\"quiet\", \"reliable\"]\n}",
    "parsed": {
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
  }
}
```
