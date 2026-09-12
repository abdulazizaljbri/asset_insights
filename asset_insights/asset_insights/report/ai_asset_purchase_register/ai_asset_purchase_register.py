# Copyright (c) 2026, Asset Insights Team
# License: MIT
# Asset Purchase Register — سجل شراء الأصول  (v15.23.1-verified fields)
# Two complementary sources, deduplicated so every purchase appears once:
#   1) Purchase Invoice lines with is_fixed_asset = 1 (posted always;
#      draft invoices only when Include Drafts is ticked);
#   2) Assets NOT linked to a purchase invoice (direct purchases created
#      as Asset documents - e.g. draft assets entered by hand). Draft
#      assets appear only when Include Drafts is ticked.

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
		{"label": _("Voucher Type"), "fieldname": "voucher_type", "fieldtype": "Data", "width": 130},
		{"label": _("Voucher No"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 160},
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


def get_invoice_rows(filters):
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

	return frappe.db.sql(
		f"""
		select pi.posting_date as posting_date,
		       'Purchase Invoice' as voucher_type,
		       pi.name as voucher_no,
		       pi.supplier as supplier,
		       pi.supplier_name as supplier_name,
		       pii.item_code as item_code, pii.item_name as item_name,
		       pii.asset_category as asset_category,
		       pii.asset_location as asset_location,
		       pii.qty as qty, pii.rate as rate, pii.amount as amount,
		       pi.docstatus as docstatus
		from `tabPurchase Invoice` pi
		join `tabPurchase Invoice Item` pii on pii.parent = pi.name
		WHERE pii.is_fixed_asset = 1 AND {" AND ".join(conditions)}
		""",
		values,
		as_dict=1,
	)


def get_direct_asset_rows(filters):
	conditions, values = [], []
	conditions.append(drafts_clause(filters, alias="a"))
	# dedupe: invoice-backed assets are already shown via their invoice line
	conditions.append("(a.purchase_invoice is null or a.purchase_invoice = '')")
	if filters.get("company"):
		conditions.append("a.company = %s")
		values.append(filters.company)
	if filters.get("supplier"):
		conditions.append("a.supplier = %s")
		values.append(filters.supplier)
	if filters.get("asset_category"):
		conditions.append("a.asset_category = %s")
		values.append(filters.asset_category)
	if filters.get("item_code"):
		conditions.append("a.item_code = %s")
		values.append(filters.item_code)
	conditions.append("coalesce(a.purchase_date, date(a.creation)) BETWEEN %s AND %s")
	values += [filters.from_date, filters.to_date]

	return frappe.db.sql(
		f"""
		select coalesce(a.purchase_date, date(a.creation)) as posting_date,
		       'Asset' as voucher_type,
		       a.name as voucher_no,
		       a.supplier as supplier,
		       sup.supplier_name as supplier_name,
		       a.item_code as item_code,
		       a.asset_name as item_name,
		       a.asset_category as asset_category,
		       a.location as asset_location,
		       coalesce(a.asset_quantity, 1) as qty,
		       a.gross_purchase_amount as rate,
		       a.gross_purchase_amount as amount,
		       a.docstatus as docstatus
		from `tabAsset` a
		left join `tabSupplier` sup on sup.name = a.supplier
		WHERE {" AND ".join(conditions)}
		""",
		values,
		as_dict=1,
	)


def get_data(filters):
	rows = list(get_invoice_rows(filters)) + list(get_direct_asset_rows(filters))
	rows.sort(key=lambda r: (getdate(r.posting_date or "1970-01-01"), str(r.voucher_no)))

	currency = get_company_currency(filters.get("company"))
	data = []
	by_month = frappe._dict()
	total_amount = 0.0

	for r in rows:
		amount = flt(r.amount)
		status = _("Draft") if r.docstatus == 0 else _("Submitted")
		data.append(frappe._dict(
			posting_date=r.posting_date,
			voucher_type=r.voucher_type,
			voucher_no=r.voucher_no,
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

	message = "{t}: <b>{tc}</b> — {a}: <b>{av}</b> — {d}: <b>{dc}</b>".format(
		t=_("Asset Purchase Lines"), tc=len(data),
		a=_("Amount"), av=currency_fmt(total_amount, currency),
		d=_("Draft"), dc=sum(1 for x in data if x.status == _("Draft")),
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
