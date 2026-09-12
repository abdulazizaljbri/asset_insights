# Copyright (c) 2026, Asset Insights Team
# License: MIT

"""Shared helpers for the Asset Insights script reports.

Conventions (mirroring the Warehouse Insights app):
- every report defaults its date filters so it ALWAYS renders;
- drafts are surfaced ONLY when the Include Drafts checkbox is ticked,
  via a `docstatus in (0, 1)` clause (never leaked when unchecked);
- labels go through `_()` so translations/ar.csv applies (bilingual AR/EN).
"""

import frappe
from frappe import _
from frappe.utils import cint, getdate


# Real v15 `Asset.status` options (asset.json):
# Draft / Submitted / Cancelled / Partially Depreciated / Fully Depreciated /
# Sold / Scrapped / In Maintenance / Out of Order / Issue / Receipt /
# Capitalized / Work In Progress
ASSET_LIVE_STATUSES = [
	"Partially Depreciated",
	"Fully Depreciated",
	"Sold",
	"Scrapped",
	"In Maintenance",
	"Out of Order",
	"Issue",
	"Receipt",
	"Capitalized",
	"Work In Progress",
]

ASSET_DISPOSAL_STATUSES = ["Sold", "Scrapped"]

ASSET_MOVEMENT_PURPOSES = ["Issue", "Receipt", "Transfer", "Transfer and Issue"]

REPAIR_STATUSES = ["Pending", "Completed", "Cancelled"]

MAINTENANCE_TASK_STATUSES = ["Planned", "Overdue", "Cancelled"]

MAINTENANCE_LOG_STATUSES = ["Planned", "Completed", "Cancelled", "Overdue"]

DEPRECIATION_METHODS = [
	"Straight Line",
	"Double Declining Balance",
	"Written Down Value",
	"Manual",
]


def get_company_currency(company=None):
	if company:
		currency = frappe.db.get_value("Company", company, "default_currency")
		if currency:
			return currency
	return frappe.db.get_single_value("Global Defaults", "default_currency")


def drafts_clause(filters, alias="a"):
	"""`docstatus in (0, 1)` only when Include Drafts is ticked, else strict."""
	if cint(filters.get("include_drafts")):
		return f"{alias}.docstatus in (0, 1)"
	return f"{alias}.docstatus = 1"


def build_asset_conditions(filters, alias="a"):
	"""Common WHERE fragments for tabAsset `a` queries.

	Handles: company, asset_category, location, custodian, status, item_code.
	Returns (conditions, values).
	"""
	conditions, values = [], []

	if filters.get("company"):
		conditions.append(f"{alias}.company = %s")
		values.append(filters.get("company"))

	if filters.get("asset_category"):
		conditions.append(f"{alias}.asset_category = %s")
		values.append(filters.get("asset_category"))

	if filters.get("location"):
		conditions.append(f"{alias}.location = %s")
		values.append(filters.get("location"))

	if filters.get("custodian"):
		conditions.append(f"{alias}.custodian = %s")
		values.append(filters.get("custodian"))

	if filters.get("item_code"):
		conditions.append(f"{alias}.item_code = %s")
		values.append(filters.get("item_code"))

	if filters.get("status") and filters.get("status") in ASSET_LIVE_STATUSES:
		conditions.append(f"{alias}.status = %s")
		values.append(filters.get("status"))

	return conditions, values


def currency_fmt(value, currency):
	return frappe.utils.fmt_money(value or 0, currency=currency)


def month_key(d):
	"""`YYYY-MM` bucket key for chart grouping."""
	d = getdate(d)
	return f"{d.year}-{d.month:02d}"


def month_label(d):
	"""Human `Mon YYYY` label for chart buckets (locale-agnostic)."""
	d = getdate(d)
	return d.strftime("%b %Y")
