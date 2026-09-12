# Copyright (c) 2026, Asset Insights Team
# License: MIT
# Asset Value Adjustment Register — سجل تعديل قيم الأصول
# Real ERPNext v15.23.1 fields on `tabAsset Value Adjustment`: date,
# current_asset_value, new_asset_value, difference_amount, journal_entry.
# (difference_account does not exist in 15.23.1 - added in later versions.)
# Drafts only when Include Drafts is ticked.

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
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 110},
		{"label": _("Adjustment ID"), "fieldname": "name", "fieldtype": "Link", "options": "Asset Value Adjustment", "width": 160},
		{"label": _("Asset ID"), "fieldname": "asset", "fieldtype": "Link", "options": "Asset", "width": 150},
		{"label": _("Asset Name"), "fieldname": "asset_display", "fieldtype": "Data", "width": 170},
		{"label": _("Asset Category"), "fieldname": "asset_category", "fieldtype": "Link", "options": "Asset Category", "width": 140},
		{"label": _("Current Asset Value"), "fieldname": "current_asset_value", "fieldtype": "Currency", "width": 160},
		{"label": _("New Asset Value"), "fieldname": "new_asset_value", "fieldtype": "Currency", "width": 150},
		{"label": _("Difference Amount"), "fieldname": "difference_amount", "fieldtype": "Currency", "width": 150},
		{"label": _("Journal Entry"), "fieldname": "journal_entry", "fieldtype": "Link", "options": "Journal Entry", "width": 150},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
	]


def get_data(filters):
	conditions, values = [], []
	conditions.append(drafts_clause(filters, alias="va"))
	if filters.get("company"):
		conditions.append("va.company = %s")
		values.append(filters.company)
	if filters.get("asset"):
		conditions.append("va.asset = %s")
		values.append(filters.asset)
	conditions.append("va.date BETWEEN %s AND %s")
	values += [filters.from_date, filters.to_date]

	rows = frappe.db.sql(
		f"""
		select va.name, va.asset, va.asset_category, va.date,
		       va.current_asset_value, va.new_asset_value,
		       va.difference_amount,
		       va.journal_entry, va.docstatus,
		       a.asset_name as asset_display
		from `tabAsset Value Adjustment` va
		left join `tabAsset` a on a.name = va.asset
		WHERE {" AND ".join(conditions)}
		ORDER BY va.date ASC, va.name ASC
		""",
		values,
		as_dict=1,
	)

	currency = get_company_currency(filters.get("company"))
	data = []
	by_month = frappe._dict()
	net_diff = 0.0

	for r in rows:
		diff = flt(r.difference_amount)
		net_diff += diff
		status = _("Draft") if r.docstatus == 0 else _("Submitted")
		data.append(frappe._dict(
			name=r.name,
			date=r.date,
			asset=r.asset,
			asset_display=r.asset_display or "",
			asset_category=r.asset_category or "",
			current_asset_value=flt(r.current_asset_value),
			new_asset_value=flt(r.new_asset_value),
			difference_amount=diff,
			journal_entry=r.journal_entry or "",
			status=status,
		))
		if r.date:
			k = month_key(r.date)
			by_month[k] = by_month.get(k, 0.0) + diff

	message = "{t}: <b>{tc}</b> — {n}: <b>{nv}</b>".format(
		t=_("Adjustments"), tc=len(data),
		n=_("Net Difference"), nv=currency_fmt(net_diff, currency),
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
			"datasets": [{"name": _("Difference Amount"), "values": vals}],
		},
		"type": "bar",
	}
