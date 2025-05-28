currency_choices = [
        ('UAH', 'UAH'),
        ('USD', 'USD'),
        ('EUR', 'EUR'),
        ('PLN', 'PLN'),
        ('GBP', 'GBP'),
        ('CAD', 'CAD'),
        ('NOK', 'NOK'),
        ('CHF', 'CHF'),
        ('SEK', 'SEK'),
]

currency_list = [currency[0] for currency in currency_choices]

access_type_choices = [
        ('subscribers', 'Subscribers'),
        ('everyone', 'Everyone'),
        ('only_me', 'Only me'),
        ('selected_users', 'Selected User')
]

valid_mime_types = ['.mp4', '.avi', '.mpeg', '.mov']

olx_currency = {
        'zł': 'PLN',
        '€': 'EUR'
}

image_size_choices = {
        ('1', '1x1'),
        ('0.75', '3x4'),
        ('1.3333', '4x3'),
        ('0.5625', '9x16'),
        ('1.7777', '16x9'),
}
