# 07_built_url

```text
{
  "technical_prompt_and_input": {
    "section_url": "https://www.dns-shop.ru/search/?q=%D1%85%D0%BE%D0%BB%D0%BE%D0%B4%D0%B8%D0%BB%D1%8C%D0%BD%D0%B8%D0%BA&price=0-70000&category=4e2a7cdb390b7fd7",
    "merged_filters": [
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
    ]
  },
  "output": {
    "built_url": "https://www.dns-shop.ru/search/?q=%D1%85%D0%BE%D0%BB%D0%BE%D0%B4%D0%B8%D0%BB%D1%8C%D0%BD%D0%B8%D0%BA&category=4e2a7cdb390b7fd7&price=0-70000&f%5B5q2%5D=5dc-5db-54c&fr%5Btk%5D=300-750&fr%5B8g%5D=20.8-60&f%5B2v8%5D=5e1"
  }
}
```
