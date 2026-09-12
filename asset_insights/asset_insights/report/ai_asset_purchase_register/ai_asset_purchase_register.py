# Copyright (c) 2026, Asset Insights Team
# License: MIT
# Asset Purchase Register — سجل شراء الأصول
# Purchases of fixed assets through Purchase Invoices (real v15 fields:
# Purchase Invoice Item .is_fixed_asset / .asset_category / .asset_location).
# Draft invoices only when Include Drafts is ticked.

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate, add_months

from asset_insights.asset_insights.utils import (
	currency_fmt,
	drafts_clause,
	get_company_currency,
	month_key,
	month_label,
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.from_date = filters.get("from_date") or add_months(getdate(nowdate()), -12)
	filters.to_date = filters.get("to_date") or nowdate()

	columns = get_columns()
	data, message, chart = get_data(filters)
	return columns, data, message, chart


def get_columns():
	return [
		{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 110},
		{"label": _("Purchase Invoice"), "fieldname": "name", "fieldtype": "Link", "options": "Purchase Invoice", "width": 160},
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 150},
		{"label": _("Supplier Name"), "fieldname": "supplier_name", "fieldtype": "Data", "width": 160},
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 130},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 170},
		{"label": _("Asset Category"), "fieldname": "asset_category", "fieldtype": "Link", "options": "Asset Category", "width": 140},
		{"label": _("Asset Location"), "fieldname": "asset_location", "fieldtype": "Link", "options": "Location", "width": 140},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 70},
		{"label": _("Rate"), "fieldname": "rate", "fieldtype": "Currency", "width": 120},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 140},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
	]


def get_data(filters):
	conditions, values = [], []
	conditions.append(drafts_clause(filters, alias="pi"))
	if filters.get("company"):
		conditions.append("pi.company = %s")
		values.append(filters.company)
	if filters.get("supplier"):
		conditions.append("pi.supplier = %s")
		values.append(filters.supplier)
	if filters.get("asset_category"):
		conditions.append("pii.asset_category = %s")
		values.append(filters.asset_category)
	if filters.get("item_code"):
		conditions.append("pii.item_code = %s")
		values.append(filters.item_code)
	conditions.append("pi.posting_date BETWEEN %s AND %s")
	values += [filters.from_date, filters.to_date]

	rows = frappe.db.sql(
		f"""
		select pi.name, pi.posting_date, pi.supplier, pi.supplier_name,
		       pi.docstatus,
		       pii.item_code, pii.item_name, pii.asset_category,
		       pii.asset_location, pii.qty, pii.rate, pii.amount
		from `tabPurchase Invoice` pi
		join `tabPurchase Invoice Item` pii on pii.parent = pi.name
		WHERE pii.is_fixed_asset = 1 AND {" AND ".join(conditions)}
		ORDER BY pi.posting_date ASC, pi.name ASC
		""",
		values,
		as_dict=1,
	)

	currency = get_company_currency(filters.get("company"))
	data = []
	by_month = frappe._dict()
	total_amount = 0.0

	for r in rows:
		amount = flt(r.amount)
		status = _("Draft") if r.docstatus == 0 else _("Submitted")
		data.append(frappe._dict(
			name=r.name,
			posting_date=r.posting_date,
			supplier=r.supplier,
			supplier_name=r.supplier_name or "",
			item_code=r.item_code,
			item_name=r.item_name or "",
			asset_category=r.asset_category or "",
			asset_location=r.asset_location or "",
			qty=flt(r.qty),
			rate=flt(r.rate),
			amount=amount,
			status=status,
		))
		total_amount += amount
		if r.posting_date:
			k = month_key(r.posting_date)
			by_month[k] = by_month.get(k, 0.0) + amount

	message = "{t}: <b>{tc}</b> — {a}: <b>{av}</b>".format(
		t=_("Asset Purchase Lines"), tc=len(data),
		a=_("Amount"), av=currency_fmt(total_amount, currency),
	)

	chart = get_chart(by_month)
	return data, message, chart


def get_chart(by_month):
	if not by_month:
		return {}
	labels, vals = [], []
	for k in sorted(by_month):
		labels.append(month_label(f"{k}-15"))
		vals.append(flt(by_month[k]))
	return {
		"data": {
			"labels": labels,
			"datasets": [{"name": _("Amount"), "values": vals}],
		},
		"type": "bar",
	}
