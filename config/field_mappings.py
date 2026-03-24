"""
Словарь полей 1С для AI-распознавания структуры файлов.
Содержит синонимы названий колонок для различных конфигураций 1С.
"""

FIELD_MAPPINGS = {
    # === ФИНАНСОВЫЕ ПОЛЯ ===
    "revenue": {
        "synonyms": [
            "Выручка", "СуммаПродажи", "Оборот", "Продажи", "СуммаДокумента",
            "СуммаРеализации", "ВыручкаОтПродаж", "ОборотПродаж", "Доход",
            "Revenue", "SalesAmount", "Turnover"
        ],
        "data_type": "float",
        "aggregation": "sum",
        "unit": "RUB",
        "category": "financial"
    },
    "cost": {
        "synonyms": [
            "Себестоимость", "СуммаПокупки", "ЗакупочнаяЦена", "Затраты",
            "CostPrice", "PurchaseAmount", "CostOfGoods", "ЗатратыНаЗакупку",
            "СебестоимостьПродаж", "Cost"
        ],
        "data_type": "float",
        "aggregation": "sum",
        "unit": "RUB",
        "category": "financial"
    },
    "profit": {
        "synonyms": [
            "Прибыль", "ВаловаяПрибыль", "Маржа", "Profit", "GrossProfit",
            "МаржинальнаяПрибыль", "ФинансовыйРезультат"
        ],
        "data_type": "float",
        "aggregation": "sum",
        "unit": "RUB",
        "category": "financial"
    },
    "margin_percent": {
        "synonyms": [
            "Маржинальность", "ПроцентМаржи", "MarginPercent", "ВаловаяМаржа",
            "УровеньМаржинальности", "Margin%"
        ],
        "data_type": "float",
        "aggregation": "avg",
        "unit": "percent",
        "category": "financial"
    },
    
    # === ДАТА И ВРЕМЯ ===
    "date": {
        "synonyms": [
            "Дата", "ДатаДокумента", "Период", "ДатаС", "ДатаПо",
            "Date", "DocumentDate", "Period", "OrderDate", "TransactionDate",
            "ДатаОперации", "ДатаЗаказа"
        ],
        "data_type": "datetime",
        "formats": [
            "%d.%m.%Y", "%Y-%m-%d", "%d.%m.%Y %H:%M", "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y", "%m/%d/%Y"
        ],
        "category": "temporal"
    },
    
    # === ТОВАРЫ И НОМЕНКЛАТУРА ===
    "product": {
        "synonyms": [
            "Товар", "Номенклатура", "Наименование", "Product", "Item",
            "ProductName", "Товары", "Артикул", "SKU", "Материал",
            "Услуга", "Работа"
        ],
        "data_type": "string",
        "aggregation": "count",
        "category": "product"
    },
    "category": {
        "synonyms": [
            "Категория", "Группа", "Раздел", "Category", "Group", "Department",
            "ГруппаНоменклатуры", "КатегорияТовара", "Подкатегория",
            "Family", "Class"
        ],
        "data_type": "string",
        "aggregation": "count_distinct",
        "category": "product"
    },
    "quantity": {
        "synonyms": [
            "Количество", "Колво", "Qty", "Quantity", "Объём", "Вес",
            "Штуки", "Единицы", "Pieces", "Units", "Weight_kg"
        ],
        "data_type": "float",
        "aggregation": "sum",
        "category": "product"
    },
    "price": {
        "synonyms": [
            "Цена", "ЦенаЕдиницы", "UnitPrice", "Price", "РозничнаяЦена",
            "ЗакупочнаяЦена", "ЦенаПродажи", "PricePerUnit"
        ],
        "data_type": "float",
        "aggregation": "avg",
        "unit": "RUB",
        "category": "financial"
    },
    
    # === КЛИЕНТЫ И КОНТРАГЕНТЫ ===
    "customer": {
        "synonyms": [
            "Клиент", "Покупатель", "Контрагент", "Customer", "Client",
            "Buyer", "Партнёр", "Partner", "Заказчик", "Дебитор",
            "ОрганизацияПокупатель", "ФИОКлиента"
        ],
        "data_type": "string",
        "aggregation": "count_distinct",
        "category": "customer"
    },
    "customer_segment": {
        "synonyms": [
            "СегментКлиентов", "ТипКлиента", "CustomerSegment", "КатегорияКлиента",
            "ГруппаКлиентов", "CustomerType", "ClientCategory"
        ],
        "data_type": "string",
        "aggregation": "count_distinct",
        "category": "customer"
    },
    "manager": {
        "synonyms": [
            "Менеджер", "Ответственный", "Manager", "SalesManager",
            "МенеджерПоПродажам", "Сотрудник", "Employee", "Представитель",
            "Agent", "Консультант"
        ],
        "data_type": "string",
        "aggregation": "count_distinct",
        "category": "employee"
    },
    
    # === ГЕОГРАФИЯ ===
    "region": {
        "synonyms": [
            "Регион", "Область", "Край", "Region", "Area", "FederalDistrict",
            "ФедеральныйОкруг", "Город", "Country", "Страна"
        ],
        "data_type": "string",
        "aggregation": "count_distinct",
        "category": "geo"
    },
    "city": {
        "synonyms": [
            "Город", "НаселенныйПункт", "City", "Town", "Settlement",
            "Муниципалитет", "District"
        ],
        "data_type": "string",
        "aggregation": "count_distinct",
        "category": "geo"
    },
    "address": {
        "synonyms": [
            "Адрес", "АдресДоставки", "Address", "DeliveryAddress",
            "ЮридическийАдрес", "ФактическийАдрес", "Location"
        ],
        "data_type": "string",
        "aggregation": "count_distinct",
        "category": "geo"
    },
    
    # === ДОКУМЕНТЫ ===
    "document_number": {
        "synonyms": [
            "НомерДокумента", "Номер", "DocumentNumber", "DocNum",
            "НомерЗаказа", "НомерСчета", "InvoiceNumber", "OrderNumber"
        ],
        "data_type": "string",
        "aggregation": "count",
        "category": "document"
    },
    "document_type": {
        "synonyms": [
            "ТипДокумента", "ВидДокумента", "DocumentType", "DocType",
            "ВидОперации", "OperationType", "TransactionType"
        ],
        "data_type": "string",
        "aggregation": "count_distinct",
        "category": "document"
    },
    
    # === СКЛАД И ЗАПАСЫ ===
    "warehouse": {
        "synonyms": [
            "Склад", "Warehouse", "Storage", "СкладскоеПомещение",
            "ТочкаХранения", "DistributionCenter", "DC"
        ],
        "data_type": "string",
        "aggregation": "count_distinct",
        "category": "warehouse"
    },
    "stock_balance": {
        "synonyms": [
            "Остаток", "ОстаткиНаСкладе", "StockBalance", "InventoryBalance",
            "ТекущийОстаток", "КоличествоОстаток", "OnHand"
        ],
        "data_type": "float",
        "aggregation": "sum",
        "category": "warehouse"
    },
}

# Профили конфигураций 1С
CONFIG_PROFILES = {
    "UT": {
        "name": "1С:Управление торговлей",
        "typical_fields": ["revenue", "cost", "product", "customer", "manager", "warehouse"],
        "priority_rules": ["gross_margin_percent", "abc_analysis", "revenue_by_category"]
    },
    "KA": {
        "name": "1С:Комплексная автоматизация",
        "typical_fields": ["revenue", "cost", "profit", "customer", "employee", "production"],
        "priority_rules": ["gross_margin_percent", "active_customer_base", "labor_productivity"]
    },
    "BP": {
        "name": "1С:Бухгалтерия предприятия",
        "typical_fields": ["revenue", "cost", "profit", "document_number", "counterparty"],
        "priority_rules": ["gross_margin_percent", "revenue_growth_yoy", "expense_structure"]
    },
    "UNF": {
        "name": "1С:Управление нашей фирмой",
        "typical_fields": ["revenue", "customer", "product", "manager", "project"],
        "priority_rules": ["active_customer_base", "revenue_by_manager", "project_profitability"]
    },
}
