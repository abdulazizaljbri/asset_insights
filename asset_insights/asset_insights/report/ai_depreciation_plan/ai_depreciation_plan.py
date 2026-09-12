# Copyright (c) 2026, Asset Insights Team
# License: MIT
# Depreciation Plan — جدول الإهلاك
# Real v15 tables: `tabAsset Depreciation Schedule` (ads) joined to its
# `tabDepreciation Schedule` child rows (ds) and `tabAsset` (a).
# Booking status from ds.journal_entry; draft schedules only when
# Include Drafts is ticked.

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
	# default window: the next 12 months of the plan
	filters.from_date = filters.get("from_date") or getdate(nowdate())
	filters.to_date = filters.get("to_date") or add_months(getdate(nowdate()), 12)

	columns = get_columns()
	data, message, chart = get_data(filters)
	return columns, data, message, chart


def get_columns():
	return [
		{"label": _("Asset ID"), "fieldname": "asset", "fieldtype": "Link", "options": "Asset", "width": 150},
		{"label": _("Asset Name"), "fieldname": "asset_name", "fieldtype": "Data", "width": 190},
		{"label": _("Asset Category"), "fieldname": "asset_category", "fieldtype": "Link", "options": "Asset Category", "width": 140},
		{"label": _("Schedule Date"), "fieldname": "schedule_date", "fieldtype": "Date", "width": 110},
		{"label": _("Depreciation Amount"), "fieldname": "depreciation_amount", "fieldtype": "Currency", "width": 160},
		{"label": _("Accumulated Depreciation"), "fieldname": "accumulated", "fieldtype": "Currency", "width": 170},
		{"label": _("Finance Book"), "fieldname": "finance_book", "fieldtype": "Link", "options": "Finance Book", "width": 130},
		{"label": _("Journal Entry"), "fieldname": "journal_entry", "fieldtype": "Link", "options": "Journal Entry", "width": 150},
		{"label": _("Booking Status"), "fieldname": "booking_status", "fieldtype": "Data", "width": 110},
	]


def get_data(filters):
	conditions, values = [], []
	conditions.append(drafts_clause(filters, alias="ads"))
	if filters.get("company"):
		conditions.append("ads.company = %s")
		values.append(filters.company)
	if filters.get("asset_category"):
		conditions.append("a.asset_category = %s")
		values.append(filters.asset_category)
	if filters.get("asset"):
		conditions.append("ads.asset = %s")
		values.append(filters.asset)
	if filters.get("booking_status") == "Pending":
		conditions.append("ds.journal_entry is null")
	elif filters.get("booking_status") == "Booked":
		conditions.append("ds.journal_entry is not null")
	conditions.append("ds.schedule_date BETWEEN %s AND %s")
	values += [filters.from_date, filters.to_date]

	rows = frappe.db.sql(
		f"""
		select ads.asset, a.asset_name, a.asset_category,
		       ads.finance_book, ads.docstatus as ads_docstatus,
		       ds.schedule_date, ds.depreciation_amount,
		       ds.accumulated_depreciation_amount, ds.journal_entry
		from `tabAsset Depreciation Schedule` ads
		join `tabDepreciation Schedule` ds on ds.parent = ads.name
		join `tabAsset` a on a.name = ads.asset
		WHERE {" AND ".join(conditions)}
		ORDER BY ds.schedule_date ASC, ads.asset ASC
		""",
		values,
		as_dict=1,
	)

	currency = get_company_currency(filters.get("company"))
	data = []
	total_amount = 0.0
	by_month = frappe._dict()

	for r in rows:
		if r.ads_docstatus == 0:
			status = _("Draft")
		elif r.journal_entry:
			status = _("Booked")
		else:
			status = _("Pending")

		data.append(frappe._dict(
			asset=r.asset,
			asset_name=r.asset_name,
			asset_category=r.asset_category,
			schedule_date=r.schedule_date,
			depreciation_amount=flt(r.depreciation_amount),
			accumulated=flt(r.accumulated_depreciation_amount),
			finance_book=r.finance_book,
			journal_entry=r.journal_entry or "",
			booking_status=status,
		))
		total_amount += flt(r.depreciation_amount)
		by_month[month_key(r.schedule_date)] = by_month.get(
			month_key(r.schedule_date), 0.0) + flt(r.depreciation_amount)

	booked = sum(1 for d in data if d.booking_status == _("Booked"))
	message = "{t}: <b>{tv}</b> — {b}: <b>{bc}</b> / {n}".format(
		t=_("Total Depreciation"), tv=currency_fmt(total_amount, currency),
		b=_("Booked"), bc=booked, n=len(data),
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
			"datasets": [{"name": _("Depreciation Amount"), "values": vals}],
		},
		"type": "bar",
	}
