from decimal import Decimal


def calculate_gross_values(price, quantity, exchange_rate):
    gross_value = (price or Decimal("0")) * (quantity or Decimal("0"))
    gross_value_usd = gross_value if exchange_rate in (None, Decimal("0")) else gross_value / exchange_rate
    gross_value_brl = gross_value if exchange_rate in (None, Decimal("0")) else gross_value
    return gross_value_brl, gross_value_usd
