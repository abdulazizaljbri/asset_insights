# Copyright (c) 2026, Asset Insights Team
# License: MIT
# Asset Register — سجل الأصول التفصيلي
# Detailed / Summary views, live statuses, drafts only when
# Include Drafts is ticked. Real v15 fields: tabAsset + tabEmployee.

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate, add_months

from asset_insights.asset_insights.utils import (
	build_asset_conditions,
	currency_fmt,
	drafts_clause,
	get_company_currency,
	ASSET_LIVE_STATUSES,
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	# sane defaults so the report always renders
	filters.from_date = filters.get("from_date") or add_months(getdate(nowdate()), -36)
	filters.to_date = filters.get("to_date") or nowdate()

	columns = get_columns(filters.get("view_type") or "Detailed")
	data, message, chart = get_data(filters)
	return columns, data, message, chart


def get_columns(view_type):
	if view_type == "Summary":
		return [
			{"label": _("Asset Category"), "fieldname": "asset_category",
			 "fieldtype": "Link", "options": "Asset Category", "width": 200},
			{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 130},
			{"label": _("Count"), "fieldname": "asset_count", "fieldtype": "Int", "width": 80},
			{"label": _("Gross Purchase Amount"), "fieldname": "gross", "fieldtype": "Currency", "width": 150},
			{"label": _("Accumulated Depreciation"), "fieldname": "accum_dep", "fieldtype": "Currency", "width": 160},
			{"label": _("Net Book Value"), "fieldname": "nbv", "fieldtype": "Currency", "width": 150},
		]

	return [
		{"label": _("Asset ID"), "fieldname": "name", "fieldtype": "Link", "options": "Asset", "width": 150},
		{"label": _("Asset Name"), "fieldname": "asset_name", "fieldtype": "Data", "width": 200},
		{"label": _("Asset Category"), "fieldname": "asset_category", "fieldtype": "Link", "options": "Asset Category", "width": 140},
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 120},
		{"label": _("Location"), "fieldname": "location", "fieldtype": "Link", "options": "Location", "width": 140},
		{"label": _("Custodian"), "fieldname": "custodian", "fieldtype": "Link", "options": "Employee", "width": 130},
		{"label": _("Custodian Name"), "fieldname": "custodian_name", "fieldtype": "Data", "width": 150},
		{"label": _("Purchase Date"), "fieldname": "purchase_date", "fieldtype": "Date", "width": 110},
		{"label": _("Available For Use Date"), "fieldname": "available_for_use_date", "fieldtype": "Date", "width": 130},
		{"label": _("Gross Purchase Amount"), "fieldname": "gross", "fieldtype": "Currency", "width": 150},
		{"label": _("Accumulated Depreciation"), "fieldname": "accum_dep", "fieldtype": "Currency", "width": 160},
		{"label": _("Net Book Value"), "fieldname": "nbv", "fieldtype": "Currency", "width": 150},
		{"label": _("Age (Years)"), "fieldname": "age_years", "fieldtype": "Float", "width": 100},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 130},
	]


def get_data(filters):
	conditions, values = build_asset_conditions(filters)
	conditions.append(drafts_clause(filters))
	conditions.append("a.purchase_date BETWEEN %s AND %s")
	values += [filters.from_date, filters.to_date]
	if not filters.get("status"):
		conditions.append("a.status != 'Cancelled'")

	rows = frappe.db.sql(
		f"""
		select a.name, a.asset_name, a.asset_category, a.item_code,
		       a.location, a.custodian, a.purchase_date,
		       a.available_for_use_date, a.gross_purchase_amount,
		       a.value_after_depreciation, a.status, a.docstatus,
		       e.employee_name
		from `tabAsset` a
		left join `tabEmployee` e on e.name = a.custodian
		WHERE {" AND ".join(conditions)}
		ORDER BY a.purchase_date ASC, a.name ASC
		""",
		values,
		as_dict=1,
	)

	currency = get_company_currency(filters.get("company"))
	data = []
	totals = frappe._dict(count=0, gross=0.0, accum=0.0, nbv=0.0)
	by_cat = frappe._dict()

	for r in rows:
		gross = flt(r.gross_purchase_amount)
		nbv = flt(r.value_after_depreciation) if flt(r.value_after_depreciation) else gross
		accum = max(gross - nbv, 0.0)
		age_years = 0.0
		if r.purchase_date:
			age_years = round((getdate(filters.to_date) - getdate(r.purchase_date)).days / 365.0, 1)

		status = _(r.status) if r.docstatus == 1 else _("Draft")
		data.append(frappe._dict(
			name=r.name,
			asset_name=r.asset_name,
			asset_category=r.asset_category,
			item_code=r.item_code,
			location=r.location,
			custodian=r.custodian,
			custodian_name=r.employee_name or "",
			purchase_date=r.purchase_date,
			available_for_use_date=r.available_for_use_date,
			gross=gross,
			accum_dep=accum,
			nbv=nbv,
			age_years=age_years,
			status=status,
		))

		totals.count += 1
		totals.gross += gross
		totals.accum += accum
		totals.nbv += nbv
		cat = frappe._dict(asset_count=0, gross=0.0, accum_dep=0.0, nbv=0.0)
		cat = by_cat.setdefault((r.asset_category, status), cat)
		cat.asset_count += 1
		cat.gross += gross
		cat.accum_dep += accum
		cat.nbv += nbv

	if (filters.get("view_type") or "Detailed") == "Summary":
		data = [
			frappe._dict(
				asset_category=key[0], status=key[1],
				asset_count=v.asset_count, gross=v.gross,
				accum_dep=v.accum_dep, nbv=v.nbv,
			)
			for key, v in sorted(by_cat.items())
		]

	message = "{c}: <b>{cnt}</b> — {g}: <b>{gv}</b> — {n}: <b>{nv}</b>".format(
		c=_("Assets"), cnt=totals.count,
		g=_("Gross Purchase Amount"), gv=currency_fmt(totals.gross, currency),
		n=_("Net Book Value"), nv=currency_fmt(totals.nbv, currency),
	)

	chart = get_chart(by_cat if (filters.get("view_type") or "Detailed") == "Summary" else _regroup(rows, data))

	return data, message, chart


def _regroup(rows, data):
	out = frappe._dict()
	for r, d in zip(rows, data):
		cat = frappe._dict(asset_count=0, gross=0.0, accum_dep=0.0, nbv=0.0)
		cat = out.setdefault(r.asset_category or _("Not Categorized"), cat)
		cat.asset_count += 1
		cat.gross += d.gross
		cat.nbv += d.nbv
	return out


def get_chart(by_cat):
	if not by_cat:
		return {}
	cats = sorted(by_cat.items(), key=lambda x: x[1].nbv, reverse=True)[:8]
	return {
		"data": {
			"labels": [str(k) for k, _v in cats],
			"datasets": [
				{"name": _("Net Book Value"), "values": [flt(_v.nbv) for _k, _v in cats]},
			],
		},
		"type": "bar",
	}
