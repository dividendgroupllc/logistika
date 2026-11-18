# ERPNext o'rnatilishida yaratilishi kerak bo'lgan Address/Contact custom field'lari
# (masalan Contact.is_billing_contact) production saytida yo'q edi — Purchase Invoice
# yaratishda "Unknown column 'tabContact.is_billing_contact'" xatosi chiqardi.
# create_custom_fields idempotent: bor maydonlarga tegmaydi.

from erpnext.setup.install import create_address_and_contact_custom_fields


def execute():
	create_address_and_contact_custom_fields()
