import frappe
from frappe.utils import flt

# Tizimda yoqilgan 3 ta valyuta (Currency doctype, enabled=1) — Kassa shu
# valyutalarda ishlaydi, shuning uchun bu report ham har uchalasini alohida
# ustunlarda ko'rsatishi kerak (avval faqat UZS/USD bo'lgani uchun CNY
# kontragentlar — masalan Xitoy zavod — balansi ko'rinmas edi).
CURRENCIES = ["UZS", "USD", "CNY"]


def execute(filters=None):
    if not filters:
        return [], []

    columns = get_columns(filters)
    data = get_data(filters)

    return columns, data


def get_columns(filters):
    currency = filters.get("currency", "")
    currencies_to_show = [currency] if currency else CURRENCIES

    # Base columns
    columns = [
        {"label": "Контрагент тури", "fieldname": "party_type", "fieldtype": "Data", "width": 130},
        {"label": "Контрагент", "fieldname": "party", "fieldtype": "Dynamic Link", "options": "party_type", "width": 200},
        {"label": "Валюта", "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "width": 80},
        {"label": "Акт Сверка", "fieldname": "akt_sverka_link", "fieldtype": "Data", "width": 120},
    ]

    # Bitta valyuta filtri tanlansa, ustun nomlarida valyuta kodi ko'rsatilmaydi
    # (barchasi bir xil bo'lgani uchun) — barcha valyutalar ko'rsatilsa, har
    # ustun o'z valyuta kodi bilan farqlanadi.
    label_prefix = (lambda cur: "") if currency else (lambda cur: f" {cur}")

    for cur in currencies_to_show:
        suffix = cur.lower()
        columns.extend([
            {"label": f"Кредит{label_prefix(cur)} (дан олдин)", "fieldname": f"opening_credit_{suffix}", "fieldtype": "Currency", "width": 150},
            {"label": f"Дебет{label_prefix(cur)} (дан олдин)", "fieldname": f"opening_debit_{suffix}", "fieldtype": "Currency", "width": 150},
        ])
    for cur in currencies_to_show:
        suffix = cur.lower()
        columns.extend([
            {"label": f"Кредит{label_prefix(cur)} (давр)", "fieldname": f"period_credit_{suffix}", "fieldtype": "Currency", "width": 150},
            {"label": f"Дебет{label_prefix(cur)} (давр)", "fieldname": f"period_debit_{suffix}", "fieldtype": "Currency", "width": 150},
        ])
    for cur in currencies_to_show:
        suffix = cur.lower()
        columns.extend([
            {"label": f"Сўнгги Кредит{label_prefix(cur)}", "fieldname": f"final_credit_{suffix}", "fieldtype": "Currency", "width": 150},
            {"label": f"Сўнгги Дебет{label_prefix(cur)}", "fieldname": f"final_debit_{suffix}", "fieldtype": "Currency", "width": 150},
        ])

    return columns


def get_data(filters):
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    party_type = filters.get("party_type")
    party = filters.get("party")
    currency_filter = filters.get("currency")

    # Get list of parties (without currency filter in query)
    parties = get_parties(party_type, party)

    data = []

    # Initialize totals
    totals = {}
    for cur in CURRENCIES:
        suffix = cur.lower()
        for prefix in ("opening", "period", "final"):
            for kind in ("credit", "debit"):
                totals[f"{prefix}_{kind}_{suffix}"] = 0

    for party_info in parties:
        row = calculate_party_balances(party_info, from_date, to_date)
        if row:
            # Filter by party's default currency if currency filter is set
            if currency_filter and row.get("currency") != currency_filter:
                continue

            data.append(row)

            # Add to totals
            for key in totals:
                totals[key] += row.get(key, 0)

    # Add total row at the top if there's data
    if data:
        total_row = {
            "party_type": "",
            "party": "ЖАМИ",
            "currency": "",
            "akt_sverka_link": "",
            "is_total_row": True
        }
        total_row.update(totals)
        data.insert(0, total_row)

    return data


def get_parties(party_type=None, party=None):
    """Get list of parties based on filters"""
    conditions = ["party IS NOT NULL", "party != ''", "party_type IS NOT NULL", "party_type != ''"]
    values = []

    if party:
        # Specific party
        conditions.append("party = %s")
        values.append(party)

    if party_type:
        conditions.append("party_type = %s")
        values.append(party_type)

    where_clause = "WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT DISTINCT party_type, party
        FROM `tabGL Entry`
        {where_clause}
        ORDER BY party_type, party
    """

    result = frappe.db.sql(query, tuple(values), as_dict=True)
    return result


def calculate_party_balances(party_info, from_date, to_date):
    """Calculate all balances for a party, for every currency in CURRENCIES."""
    party_type = party_info.get("party_type")
    party = party_info.get("party")

    # Get party currency from Party Financial Defaults
    currency = get_party_currency(party_type, party)

    row = {
        "party_type": party_type,
        "party": party,
        "currency": currency,
        "akt_sverka_link": "Акт Сверка",  # Will be formatted as link in JS
    }

    for cur in CURRENCIES:
        suffix = cur.lower()
        opening = calculate_opening_balance(party_type, party, from_date, cur)
        period = calculate_period_balance(party_type, party, from_date, to_date, cur)

        final_net = (opening['credit'] - opening['debit']) + (period['credit'] - period['debit'])

        row[f"opening_credit_{suffix}"] = opening['credit'] if opening['credit'] > 0 else 0
        row[f"opening_debit_{suffix}"] = opening['debit'] if opening['debit'] > 0 else 0
        row[f"period_credit_{suffix}"] = period['credit']
        row[f"period_debit_{suffix}"] = period['debit']
        row[f"final_credit_{suffix}"] = final_net if final_net > 0 else 0
        row[f"final_debit_{suffix}"] = abs(final_net) if final_net < 0 else 0

    return row


def get_party_currency(party_type, party):
    """Get party currency with safe fallback when custom doctype is unavailable."""
    currency = None

    if frappe.db.exists("DocType", "Party Financial Defaults"):
        currency = frappe.db.get_value(
            "Party Financial Defaults",
            {"party_type": party_type, "party": party},
            "currency"
        )

    if not currency:
        currency = frappe.db.get_value(
            "GL Entry",
            {"party_type": party_type, "party": party, "is_cancelled": 0},
            "account_currency",
            order_by="posting_date desc, creation desc"
        )

    return currency or "UZS"


def calculate_opening_balance(party_type, party, from_date, currency):
    """
    Calculate opening balance before from_date for a specific currency

    Credit calculation:
    + Journal Entry (Opening Entry) Credit
    + Purchase Invoice
    + Payment Entry Receive
    + Journal Entry (Journal Entry) Credit
    + Salary Slip (only for UZS)

    Debit calculation:
    + Journal Entry (Opening Entry) Debit
    + Sales Invoice
    + Payment Entry Pay
    + Journal Entry (Journal Entry) Debit
    """

    # Journal Entry Opening Entry Credit
    je_opening_credit = frappe.db.sql("""
        SELECT IFNULL(SUM(credit_in_account_currency), 0)
        FROM `tabGL Entry`
        WHERE posting_date < %s
          AND party_type = %s
          AND party = %s
          AND voucher_type = 'Journal Entry'
          AND account_currency = %s
          AND is_cancelled = 0
          AND voucher_no IN (
              SELECT name FROM `tabJournal Entry`
              WHERE voucher_type = 'Opening Entry'
          )
    """, (from_date, party_type, party, currency))[0][0] or 0

    # Journal Entry Journal Entry Credit
    je_journal_credit = frappe.db.sql("""
        SELECT IFNULL(SUM(credit_in_account_currency), 0)
        FROM `tabGL Entry`
        WHERE posting_date < %s
          AND party_type = %s
          AND party = %s
          AND voucher_type = 'Journal Entry'
          AND account_currency = %s
          AND is_cancelled = 0
          AND voucher_no IN (
              SELECT name FROM `tabJournal Entry`
              WHERE voucher_type = 'Journal Entry'
          )
    """, (from_date, party_type, party, currency))[0][0] or 0

    # Purchase Invoice
    pi_credit = frappe.db.sql("""
        SELECT IFNULL(SUM(credit_in_account_currency), 0)
        FROM `tabGL Entry`
        WHERE posting_date < %s
          AND party_type = %s
          AND party = %s
          AND voucher_type = 'Purchase Invoice'
          AND account_currency = %s
          AND is_cancelled = 0
    """, (from_date, party_type, party, currency))[0][0] or 0

    # Payment Entry Receive
    pe_receive_credit = frappe.db.sql("""
        SELECT IFNULL(SUM(ge.credit_in_account_currency), 0)
        FROM `tabGL Entry` ge
        INNER JOIN `tabPayment Entry` pe ON ge.voucher_no = pe.name
        WHERE ge.posting_date < %s
          AND ge.party_type = %s
          AND ge.party = %s
          AND ge.voucher_type = 'Payment Entry'
          AND pe.payment_type = 'Receive'
          AND ge.account_currency = %s
          AND ge.is_cancelled = 0
    """, (from_date, party_type, party, currency))[0][0] or 0

    # Salary Slip (only for UZS)
    salary_credit = 0
    if currency == "UZS":
        salary_credit = frappe.db.sql("""
            SELECT IFNULL(SUM(credit_in_account_currency), 0)
            FROM `tabGL Entry`
            WHERE posting_date < %s
              AND party_type = %s
              AND party = %s
              AND voucher_type = 'Salary Slip'
              AND account_currency = 'UZS'
              AND is_cancelled = 0
        """, (from_date, party_type, party))[0][0] or 0

    total_credit = je_opening_credit + je_journal_credit + pi_credit + pe_receive_credit + salary_credit

    # Debit calculations
    # Journal Entry Opening Entry Debit
    je_opening_debit = frappe.db.sql("""
        SELECT IFNULL(SUM(debit_in_account_currency), 0)
        FROM `tabGL Entry`
        WHERE posting_date < %s
          AND party_type = %s
          AND party = %s
          AND voucher_type = 'Journal Entry'
          AND account_currency = %s
          AND is_cancelled = 0
          AND voucher_no IN (
              SELECT name FROM `tabJournal Entry`
              WHERE voucher_type = 'Opening Entry'
          )
    """, (from_date, party_type, party, currency))[0][0] or 0

    # Journal Entry Journal Entry Debit
    je_journal_debit = frappe.db.sql("""
        SELECT IFNULL(SUM(debit_in_account_currency), 0)
        FROM `tabGL Entry`
        WHERE posting_date < %s
          AND party_type = %s
          AND party = %s
          AND voucher_type = 'Journal Entry'
          AND account_currency = %s
          AND is_cancelled = 0
          AND voucher_no IN (
              SELECT name FROM `tabJournal Entry`
              WHERE voucher_type = 'Journal Entry'
          )
    """, (from_date, party_type, party, currency))[0][0] or 0

    # Sales Invoice
    si_debit = frappe.db.sql("""
        SELECT IFNULL(SUM(debit_in_account_currency), 0)
        FROM `tabGL Entry`
        WHERE posting_date < %s
          AND party_type = %s
          AND party = %s
          AND voucher_type = 'Sales Invoice'
          AND account_currency = %s
          AND is_cancelled = 0
    """, (from_date, party_type, party, currency))[0][0] or 0

    # Payment Entry Pay
    pe_pay_debit = frappe.db.sql("""
        SELECT IFNULL(SUM(ge.debit_in_account_currency), 0)
        FROM `tabGL Entry` ge
        INNER JOIN `tabPayment Entry` pe ON ge.voucher_no = pe.name
        WHERE ge.posting_date < %s
          AND ge.party_type = %s
          AND ge.party = %s
          AND ge.voucher_type = 'Payment Entry'
          AND pe.payment_type = 'Pay'
          AND ge.account_currency = %s
          AND ge.is_cancelled = 0
    """, (from_date, party_type, party, currency))[0][0] or 0

    total_debit = je_opening_debit + je_journal_debit + si_debit + pe_pay_debit

    # Calculate net and determine credit/debit
    net = total_credit - total_debit

    if net > 0:
        return {"credit": net, "debit": 0}
    else:
        return {"credit": 0, "debit": abs(net)}


def calculate_period_balance(party_type, party, from_date, to_date, currency):
    """
    Calculate period balance from from_date to to_date for a specific currency

    Credit calculation:
    + Opening Entry Credit
    + Journal Entry Credit
    + Purchase Invoice
    + Payment Entry Receive
    + Salary Slip (only for UZS)

    Debit calculation:
    + Opening Entry Debit
    + Journal Entry Debit
    + Payment Entry Pay
    + Sales Invoice
    """

    # Opening Entry Credit
    opening_credit = frappe.db.sql("""
        SELECT IFNULL(SUM(credit_in_account_currency), 0)
        FROM `tabGL Entry`
        WHERE posting_date >= %s
          AND posting_date <= %s
          AND party_type = %s
          AND party = %s
          AND voucher_type = 'Journal Entry'
          AND account_currency = %s
          AND is_cancelled = 0
          AND voucher_no IN (
              SELECT name FROM `tabJournal Entry`
              WHERE voucher_type = 'Opening Entry'
          )
    """, (from_date, to_date, party_type, party, currency))[0][0] or 0

    # Journal Entry Credit
    je_credit = frappe.db.sql("""
        SELECT IFNULL(SUM(credit_in_account_currency), 0)
        FROM `tabGL Entry`
        WHERE posting_date >= %s
          AND posting_date <= %s
          AND party_type = %s
          AND party = %s
          AND voucher_type = 'Journal Entry'
          AND account_currency = %s
          AND is_cancelled = 0
          AND voucher_no IN (
              SELECT name FROM `tabJournal Entry`
              WHERE voucher_type = 'Journal Entry'
          )
    """, (from_date, to_date, party_type, party, currency))[0][0] or 0

    # Purchase Invoice Credit
    pi_credit = frappe.db.sql("""
        SELECT IFNULL(SUM(credit_in_account_currency), 0)
        FROM `tabGL Entry`
        WHERE posting_date >= %s
          AND posting_date <= %s
          AND party_type = %s
          AND party = %s
          AND voucher_type = 'Purchase Invoice'
          AND account_currency = %s
          AND is_cancelled = 0
    """, (from_date, to_date, party_type, party, currency))[0][0] or 0

    # Payment Entry Receive Credit
    pe_receive_credit = frappe.db.sql("""
        SELECT IFNULL(SUM(ge.credit_in_account_currency), 0)
        FROM `tabGL Entry` ge
        INNER JOIN `tabPayment Entry` pe ON ge.voucher_no = pe.name
        WHERE ge.posting_date >= %s
          AND ge.posting_date <= %s
          AND ge.party_type = %s
          AND ge.party = %s
          AND ge.voucher_type = 'Payment Entry'
          AND pe.payment_type = 'Receive'
          AND ge.account_currency = %s
          AND ge.is_cancelled = 0
    """, (from_date, to_date, party_type, party, currency))[0][0] or 0

    # Salary Slip (only for UZS)
    salary_credit = 0
    if currency == "UZS":
        salary_credit = frappe.db.sql("""
            SELECT IFNULL(SUM(credit_in_account_currency), 0)
            FROM `tabGL Entry`
            WHERE posting_date >= %s
              AND posting_date <= %s
              AND party_type = %s
              AND party = %s
              AND voucher_type = 'Salary Slip'
              AND account_currency = 'UZS'
              AND is_cancelled = 0
        """, (from_date, to_date, party_type, party))[0][0] or 0

    total_credit = opening_credit + je_credit + pi_credit + pe_receive_credit + salary_credit

    # Debit calculations
    # Opening Entry Debit
    opening_debit = frappe.db.sql("""
        SELECT IFNULL(SUM(debit_in_account_currency), 0)
        FROM `tabGL Entry`
        WHERE posting_date >= %s
          AND posting_date <= %s
          AND party_type = %s
          AND party = %s
          AND voucher_type = 'Journal Entry'
          AND account_currency = %s
          AND is_cancelled = 0
          AND voucher_no IN (
              SELECT name FROM `tabJournal Entry`
              WHERE voucher_type = 'Opening Entry'
          )
    """, (from_date, to_date, party_type, party, currency))[0][0] or 0

    # Journal Entry Debit
    je_debit = frappe.db.sql("""
        SELECT IFNULL(SUM(debit_in_account_currency), 0)
        FROM `tabGL Entry`
        WHERE posting_date >= %s
          AND posting_date <= %s
          AND party_type = %s
          AND party = %s
          AND voucher_type = 'Journal Entry'
          AND account_currency = %s
          AND is_cancelled = 0
          AND voucher_no IN (
              SELECT name FROM `tabJournal Entry`
              WHERE voucher_type = 'Journal Entry'
          )
    """, (from_date, to_date, party_type, party, currency))[0][0] or 0

    # Payment Entry Pay Debit
    pe_pay_debit = frappe.db.sql("""
        SELECT IFNULL(SUM(ge.debit_in_account_currency), 0)
        FROM `tabGL Entry` ge
        INNER JOIN `tabPayment Entry` pe ON ge.voucher_no = pe.name
        WHERE ge.posting_date >= %s
          AND ge.posting_date <= %s
          AND ge.party_type = %s
          AND ge.party = %s
          AND ge.voucher_type = 'Payment Entry'
          AND pe.payment_type = 'Pay'
          AND ge.account_currency = %s
          AND ge.is_cancelled = 0
    """, (from_date, to_date, party_type, party, currency))[0][0] or 0

    # Sales Invoice Debit
    si_debit = frappe.db.sql("""
        SELECT IFNULL(SUM(debit_in_account_currency), 0)
        FROM `tabGL Entry`
        WHERE posting_date >= %s
          AND posting_date <= %s
          AND party_type = %s
          AND party = %s
          AND voucher_type = 'Sales Invoice'
          AND account_currency = %s
          AND is_cancelled = 0
    """, (from_date, to_date, party_type, party, currency))[0][0] or 0

    total_debit = opening_debit + je_debit + pe_pay_debit + si_debit

    return {"credit": total_credit, "debit": total_debit}
