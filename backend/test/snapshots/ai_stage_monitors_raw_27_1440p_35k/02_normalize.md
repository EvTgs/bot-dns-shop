# 02_normalize

```text
{
  "technical_prompt_and_input": [
    {
      "role": "system",
      "content": "Нормализуй товарный запрос в один JSON-объект. Верни только JSON без markdown, комментариев и пояснений.\nФормат:\n{\n  \"product_type\": \"...\",\n  \"query\": \"...\",\n  \"price_min\": null,\n  \"price_max\": null,\n  \"brand\": \"\",\n  \"ranking_policy\": \"\",\n  \"price_band_hint\": \"\",\n  \"constraints\": [\n    {\"key\": \"...\", \"op\": \">=\", \"value\": 120, \"unit\": \"hz\", \"source_text\": \"...\"}\n  ],\n  \"soft_wishes\": [\"good_camera\", \"good_battery\"]\n}\n\nПравила:\n- query — короткая русская поисковая фраза без бренда.\n- brand — только если бренд указан явно или однозначен.\n- ranking_policy — стратегия ранжирования, а не DNS-фильтр. Допустимые значения: \"\", \"balanced\", \"value\", \"performance\", \"display\".\n- price_band_hint — ценовой сегмент для ранжирования, а не жёсткий фильтр. Допустимые значения: \"\", \"budget\", \"mid\", \"mid_to_max\", \"top\", \"any\".\n- constraints — только проверяемые и осмысленные hard-ограничения. Это не итоговая истина, а вход для retrieval и scoring.\n- soft_wishes — только субъективные пожелания, они не должны превращаться в DNS-фильтры.\n- Не используй legacy-поля intent_signals, retrieval_tokens, wishes, hard_wishes, subjective_wishes.\n- Если нижняя цена не названа числом, оставь price_min = null. Нельзя ставить 0 просто по умолчанию.\n- Если фраза описывает большую диагональ или большой экран в категории, где размер экрана фильтруется, выражай это через constraint с key = \"screen_size\".\n- Если пользователь просит яркий экран без числа, не выдумывай numeric constraint. В таком случае ставь soft_wishes: [\"bright_screen\"] и используй ranking_policy = \"display\", если запрос в целом про экран.\n\nОператоры:\n- от / не меньше / не ниже / или выше -> \">=\"\n- до / не больше / не выше -> \"<=\"\n- точное значение -> \"==\"\n\nПоддерживаемые keys:\n- ram\n- storage\n- storage_type\n- refresh_rate\n- gpu\n- screen_size\n- brightness\n- matrix_type\n- sewing_operations\n- shuttle_type\n- buttonhole\n- speed_control\n- work_area_light\n- network\n- nfc\n- protection\n- fast_charge\n- wireless_charge\n- year\n- width\n- height\n- depth\n- weight\n- volume\n- energy_class\n- cooling_system\n- freezer_position\n- inverter_compressor\n- screen_finish\n\nПримеры:\n- \"от 12 ГБ ОЗУ\" -> {\"key\":\"ram\",\"op\":\">=\",\"value\":12,\"unit\":\"gb\"}\n- \"памятью от 256 ГБ\" -> {\"key\":\"storage\",\"op\":\">=\",\"value\":256,\"unit\":\"gb\"}\n- \"экраном от 120 Гц\" -> {\"key\":\"refresh_rate\",\"op\":\">=\",\"value\":120,\"unit\":\"hz\"}\n- \"RTX 4070 или выше\" -> {\"key\":\"gpu\",\"op\":\">=\",\"value\":\"rtx 4070\",\"unit\":\"\"}\n- \"большой экран\" для ноутбука -> {\"key\":\"screen_size\",\"op\":\">=\",\"value\":16,\"unit\":\"inch\",\"source_text\":\"большой экран\"}\n- \"AMOLED-экраном\" -> {\"key\":\"matrix_type\",\"op\":\"==\",\"value\":\"amoled\",\"unit\":\"\"}\n- \"горизонтальным челноком\" -> {\"key\":\"shuttle_type\",\"op\":\"==\",\"value\":\"horizontal\",\"unit\":\"\"}\n- \"автоматическим выполнением петли\" -> {\"key\":\"buttonhole\",\"op\":\"==\",\"value\":\"automatic\",\"unit\":\"\"}\n- \"не меньше 30 швейных операций\" -> {\"key\":\"sewing_operations\",\"op\":\">=\",\"value\":30,\"unit\":\"\"}\n- \"регулировкой скорости\" -> {\"key\":\"speed_control\",\"op\":\"==\",\"value\":true,\"unit\":\"\"}\n- \"подсветкой рабочей зоны\" -> {\"key\":\"work_area_light\",\"op\":\"==\",\"value\":true,\"unit\":\"\"}\n- \"поддержкой 5G\" -> {\"key\":\"network\",\"op\":\"==\",\"value\":\"5g\",\"unit\":\"\"}\n- \"NFC\" -> {\"key\":\"nfc\",\"op\":\"==\",\"value\":true,\"unit\":\"\"}\n- \"защитой не ниже IP68\" -> {\"key\":\"protection\",\"op\":\">=\",\"value\":\"ip68\",\"unit\":\"\"}\n- \"быстрой зарядкой\" -> {\"key\":\"fast_charge\",\"op\":\"==\",\"value\":true,\"unit\":\"\"}\n- \"не старше 2024 года\" -> {\"key\":\"year\",\"op\":\">=\",\"value\":2024,\"unit\":\"\"}\n- \"шириной до 60 см\" -> {\"key\":\"width\",\"op\":\"<=\",\"value\":60,\"unit\":\"cm\"}\n- \"объемом от 300 л\" -> {\"key\":\"volume\",\"op\":\">=\",\"value\":300,\"unit\":\"l\"}\n- \"классом энергопотребления не ниже A\" -> {\"key\":\"energy_class\",\"op\":\">=\",\"value\":\"a\",\"unit\":\"\"}\n- \"No Frost\" -> {\"key\":\"cooling_system\",\"op\":\"==\",\"value\":\"no_frost\",\"unit\":\"\"}\n- \"морозильной камерой снизу\" -> {\"key\":\"freezer_position\",\"op\":\"==\",\"value\":\"bottom\",\"unit\":\"\"}\n- \"инверторным компрессором\" -> {\"key\":\"inverter_compressor\",\"op\":\"==\",\"value\":true,\"unit\":\"\"}\n- \"матовым покрытием\" -> {\"key\":\"screen_finish\",\"op\":\"==\",\"value\":\"matte\",\"unit\":\"\"}\n- \"цена/качество\" -> \"ranking_policy\": \"value\"\n- \"самый мощный\" -> \"ranking_policy\": \"performance\" если запрос только про максимум мощности; если в той же фразе есть \"цена/качество\", оставь \"ranking_policy\": \"value\", а мощность учти через soft_wishes\n- \"ноутбук с самым большим и ярким экраном\" -> \"ranking_policy\": \"display\", constraint по screen_size и soft_wishes: [\"bright_screen\"]\n- \"яркость от 500 нит\" -> {\"key\":\"brightness\",\"op\":\">=\",\"value\":500,\"unit\":\"nit\",\"source_text\":\"яркость от 500 нит\"}\n- \"от средней до 100к\" -> \"price_band_hint\": \"mid_to_max\", \"price_max\": 100000\n- \"верхний сегмент\" -> \"price_band_hint\": \"top\"\n\nsoft_wishes:\n- good_camera\n- good_battery\n- good_performance\n- bright_screen\n- quiet\n- reliable\n- for_programmer\n- for_gaming\n- lightweight\n\nНе добавляй retrieval_tokens, wishes, intent_signals или иные legacy-поля.\nНе выдумывай constraints, которых нет в запросе."
    },
    {
      "role": "user",
      "content": "{\"task\": \"normalize_query\", \"question\": \"Найди монитор 27 дюймов, 2K, 144 Гц, IPS, с хорошей цветопередачей и регулировкой по высоте, бюджет до 35000 рублей\"}"
    }
  ],
  "output": {
    "raw": "{\n  \"product_type\": \"monitor\",\n  \"query\": \"монитор 27 дюймов 2K 144 Гц IPS\",\n  \"price_min\": null,\n  \"price_max\": 35000,\n  \"brand\": \"\",\n  \"ranking_policy\": \"\",\n  \"price_band_hint\": \"\",\n  \"constraints\": [\n    {\"key\": \"screen_size\", \"op\": \"==\", \"value\": 27, \"unit\": \"inch\", \"source_text\": \"27 дюймов\"},\n    {\"key\": \"refresh_rate\", \"op\": \"==\", \"value\": 144, \"unit\": \"hz\", \"source_text\": \"144 Гц\"},\n    {\"key\": \"matrix_type\", \"op\": \"==\", \"value\": \"ips\", \"unit\": \"\", \"source_text\": \"IPS\"}\n  ],\n  \"soft_wishes\": [\"good_color_accuracy\", \"height_adjustable\"]\n}",
    "parsed": {
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
    }
  }
}
```
