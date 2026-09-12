# Copyright (c) 2026, Asset Insights Team
# License: MIT
# Disposal Register — سجل الاستبعاد والبيع
# Assets disposed as Sold or Scrapped (real v15 fields: status,
# disposal_date, journal_entry_for_scrap, value_after_depreciation).
# Drafts only when Include Drafts is ticked.

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate, add_months

from asset_insights.asset_insights.utils import (
	build_asset_conditions,
	currency_fmt,
	drafts_clause,
	get_company_currency,
	ASSET_DISPOSAL_STATUSES,
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
		{"label": _("Disposal Date"), "fieldname": "disposal_date", "fieldtype": "Date", "width": 120},
		{"label": _("Asset ID"), "fieldname": "name", "fieldtype": "Link", "options": "Asset", "width": 150},
		{"label": _("Asset Name"), "fieldname": "asset_name", "fieldtype": "Data", "width": 180},
		{"label": _("Asset Category"), "fieldname": "asset_category", "fieldtype": "Link", "options": "Asset Category", "width": 140},
		{"label": _("Custodian"), "fieldname": "custodian", "fieldtype": "Link", "options": "Employee", "width": 130},
		{"label": _("Purchase Date"), "fieldname": "purchase_date", "fieldtype": "Date", "width": 110},
		{"label": _("Gross Purchase Amount"), "fieldname": "gross", "fieldtype": "Currency", "width": 150},
		{"label": _("Accumulated Depreciation"), "fieldname": "accum_dep", "fieldtype": "Currency", "width": 160},
		{"label": _("Net Book Value"), "fieldname": "nbv", "fieldtype": "Currency", "width": 150},
		{"label": _("Disposal Method"), "fieldname": "disposal_method", "fieldtype": "Data", "width": 120},
		{"label": _("Scrap Journal Entry"), "fieldname": "journal_entry_for_scrap", "fieldtype": "Link", "options": "Journal Entry", "width": 160},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
	]


def get_data(filters):
	conditions, values = build_asset_conditions(filters)
	conditions.append(drafts_clause(filters))
	conditions.append("a.status in ('Sold', 'Scrapped')")
	conditions.append("(a.disposal_date is null or a.disposal_date BETWEEN %s AND %s)")
	values += [filters.from_date, filters.to_date]

	rows = frappe.db.sql(
		f"""
		select a.name, a.asset_name, a.asset_category, a.custodian,
		       a.purchase_date, a.disposal_date, a.gross_purchase_amount,
		       a.value_after_depreciation, a.status,
		       a.journal_entry_for_scrap, a.docstatus
		from `tabAsset` a
		WHERE {" AND ".join(conditions)}
		ORDER BY a.disposal_date ASC, a.name ASC
		""",
		values,
		as_dict=1,
	)

	currency = get_company_currency(filters.get("company"))
	data = []
	by_method = frappe._dict()
	by_month = frappe._dict()
	total_nbv = 0.0

	for r in rows:
		gross = flt(r.gross_purchase_amount)
		nbv = flt(r.value_after_depreciation) if flt(r.value_after_depreciation) else gross
		accum = max(gross - nbv, 0.0)
		status = _("Draft") if r.docstatus == 0 else _(r.status)

		data.append(frappe._dict(
			name=r.name,
			disposal_date=r.disposal_date,
			asset_name=r.asset_name,
			asset_category=r.asset_category,
			custodian=r.custodian,
			purchase_date=r.purchase_date,
			gross=gross,
			accum_dep=accum,
			nbv=nbv,
			disposal_method=_(r.status) if r.status in ASSET_DISPOSAL_STATUSES else r.status,
			journal_entry_for_scrap=r.journal_entry_for_scrap or "",
			status=status,
		))
		total_nbv += nbv
		by_method[r.status or "-"] = by_method.get(r.status or "-", 0) + 1
		if r.disposal_date:
			k = month_key(r.disposal_date)
			by_month[k] = by_month.get(k, 0.0) + nbv

	message = "{t}: <b>{tc}</b> — {n}: <b>{nv}</b>".format(
		t=_("Disposals"), tc=len(data),
		n=_("Net Book Value"), nv=currency_fmt(total_nbv, currency),
	)

	chart = get_chart(by_method, by_month)
	return data, message, chart


def get_chart(by_method, by_month):
	labels, vals = [], []
	for k in sorted(by_month):
		labels.append(month_label(f"{k}-15"))
		vals.append(flt(by_month[k]))
	if not labels:
		if not by_method:
			return {}
		items = sorted(by_method.items())
		return {
			"data": {
				"labels": [_(k) if k != "-" else _("Not Specified") for k, _cnt in items],
				"datasets": [{"name": _("Disposals"), "values": [v for _k, v in items]}],
			},
			"type": "donut",
		}
	return {
		"data": {
			"labels": labels,
			"datasets": [{"name": _("Net Book Value"), "values": vals}],
		},
		"type": "bar",
	}
