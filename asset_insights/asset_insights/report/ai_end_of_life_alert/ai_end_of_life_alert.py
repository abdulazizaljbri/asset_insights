# Copyright (c) 2026, Asset Insights Team
# License: MIT
# End Of Life Alert — أصول قرب نهاية العمر الإنتاجي
# Estimates remaining useful life from the real v15 finance books child
# (`tabAsset Finance Book`): total_number_of_depreciations,
# total_number_of_booked_depreciations (+ asset.opening_number_of_booked_
# depreciations) and frequency_of_depreciation (months per booking).
# Drafts only when Include Drafts is ticked.

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate, add_months

from asset_insights.asset_insights.utils import (
	build_asset_conditions,
	currency_fmt,
	drafts_clause,
	get_company_currency,
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.within_months = cint(filters.get("within_months") or 12)
	filters.as_of = filters.get("as_of") or nowdate()

	columns = get_columns()
	data, message, chart = get_data(filters)
	return columns, data, message, chart


def get_columns():
	return [
		{"label": _("Asset ID"), "fieldname": "name", "fieldtype": "Link", "options": "Asset", "width": 150},
		{"label": _("Asset Name"), "fieldname": "asset_name", "fieldtype": "Data", "width": 180},
		{"label": _("Asset Category"), "fieldname": "asset_category", "fieldtype": "Link", "options": "Asset Category", "width": 140},
		{"label": _("Location"), "fieldname": "location", "fieldtype": "Link", "options": "Location", "width": 130},
		{"label": _("Custodian"), "fieldname": "custodian", "fieldtype": "Link", "options": "Employee", "width": 130},
		{"label": _("Depreciation Method"), "fieldname": "depreciation_method", "fieldtype": "Data", "width": 160},
		{"label": _("Total Depreciations"), "fieldname": "total_depreciations", "fieldtype": "Int", "width": 130},
		{"label": _("Booked Depreciations"), "fieldname": "booked", "fieldtype": "Int", "width": 130},
		{"label": _("Remaining (bookings)"), "fieldname": "remaining", "fieldtype": "Int", "width": 130},
		{"label": _("Frequency (months)"), "fieldname": "frequency", "fieldtype": "Int", "width": 130},
		{"label": _("Estimated End Date"), "fieldname": "est_end_date", "fieldtype": "Date", "width": 140},
		{"label": _("Months Left"), "fieldname": "months_left", "fieldtype": "Int", "width": 110},
		{"label": _("Net Book Value"), "fieldname": "nbv", "fieldtype": "Currency", "width": 150},
	]


def get_data(filters):
	conditions, values = build_asset_conditions(filters)
	conditions.append(drafts_clause(filters))
	conditions.append("a.calculate_depreciation = 1")
	conditions.append("a.status not in ('Sold', 'Scrapped', 'Cancelled')")
	conditions.append("(a.purchase_date is null or a.purchase_date <= %s)")
	values.append(filters.as_of)

	rows = frappe.db.sql(
		f"""
		select a.name, a.asset_name, a.asset_category, a.location,
		       a.custodian, a.value_after_depreciation, a.docstatus,
		       a.opening_number_of_booked_depreciations,
		       fb.depreciation_method, fb.total_number_of_depreciations,
		       fb.total_number_of_booked_depreciations,
		       fb.frequency_of_depreciation, fb.depreciation_start_date
		from `tabAsset` a
		join `tabAsset Finance Book` fb on fb.parent = a.name
		WHERE {" AND ".join(conditions)}
		ORDER BY a.name ASC
		""",
		values,
		as_dict=1,
	)

	currency = get_company_currency(filters.get("company"))
	today = getdate(filters.as_of)
	data = []
	total_nbv = 0.0
	by_quarter = frappe._dict()

	for r in rows:
		total_dep = cint(r.total_number_of_depreciations)
		booked = cint(r.opening_number_of_booked_depreciations) + cint(r.total_number_of_booked_depreciations)
		frequency = cint(r.frequency_of_depreciation) or 12
		remaining = max(total_dep - booked, 0)
		months_left = remaining * frequency

		est_end = None
		if r.depreciation_start_date:
			est_end = add_months(getdate(r.depreciation_start_date), total_dep * frequency)
		elif est_end is None:
			est_end = add_months(today, months_left)

		# keep only assets ending within the requested window
		if months_left > filters.within_months:
			continue

		data.append(frappe._dict(
			name=r.name,
			asset_name=r.asset_name,
			asset_category=r.asset_category,
			location=r.location,
			custodian=r.custodian,
			depreciation_method=r.depreciation_method or "",
			total_depreciations=total_dep,
			booked=booked,
			remaining=remaining,
			frequency=frequency,
			est_end_date=est_end,
			months_left=months_left,
			nbv=flt(r.value_after_depreciation),
		))
		total_nbv += flt(r.value_after_depreciation)
		if est_end:
			delta_months = (est_end.year - today.year) * 12 + (est_end.month - today.month)
			q = max(int(delta_months // 3), 0)
			label = _("This quarter") if q == 0 else _("+{0} quarters").format(q)
			by_quarter[label] = by_quarter.get(label, 0) + 1

	data.sort(key=lambda d: (d.months_left, d.name))

	message = "{t}: <b>{tc}</b> — {n}: <b>{nv}</b> — {w}: {wm}".format(
		t=_("Assets Nearing End Of Life"), tc=len(data),
		n=_("Net Book Value"), nv=currency_fmt(total_nbv, currency),
		w=_("Within"), wm=_("{0} months").format(filters.within_months),
	)

	chart = get_chart(by_quarter)
	return data, message, chart


def get_chart(by_quarter):
	if not by_quarter:
		return {}
	items = sorted(by_quarter.items())
	return {
		"data": {
			"labels": [k for k, _cnt in items],
			"datasets": [{"name": _("Assets"), "values": [v for _k, v in items]}],
		},
		"type": "bar",
	}
