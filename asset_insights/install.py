# Copyright (c) 2026, Asset Insights Team
# License: MIT

"""Creates public Number Cards and Dashboard Charts after migrate.

The public "Asset Insights" Workspace ships as a STANDARD Workspace JSON —
exactly the way ERPNext core modules do it:
    asset_insights/asset_insights/workspace/asset_insights/asset_insights.json
Frappe's model syncer imports/updates it automatically on every
`bench migrate` and `bench install-app`, so the workspace needs no
programmatic creation here.

Every step below is defensive: a failure in one artifact never breaks
`bench migrate`.
"""

import json

import frappe


def after_migrate():
	make_number_cards()
	make_dashboard_charts()


def _insert_if_missing(doctype, name, fieldname, values):
	try:
		if not frappe.db.exists(doctype, values.get(fieldname)):
			doc = frappe.new_doc(doctype)
			doc.update(values)
			doc.insert(ignore_permissions=True)
			return doc
	except Exception:
		frappe.log_error(
			title="Asset Insights install",
			message=f"Could not create {doctype} '{name}':\n{frappe.get_traceback()}",
		)
	return None


def make_number_cards():
	cards = [
		{
			"label": "Total Assets",
			"document_type": "Asset",
			"filters_json": json.dumps(
				[["Asset", "docstatus", "=", 1],
				 ["Asset", "status", "not in", ["Sold", "Scrapped"]]]
			),
			"color": "#2490ef",
		},
		{
			"label": "Assets In Maintenance",
			"document_type": "Asset",
			"filters_json": json.dumps(
				[["Asset", "docstatus", "=", 1], ["Asset", "status", "=", "In Maintenance"]]
			),
			"color": "#f59f00",
		},
		{
			"label": "Assets Sold Or Scrapped",
			"document_type": "Asset",
			"filters_json": json.dumps(
				[["Asset", "docstatus", "=", 1],
				 ["Asset", "status", "in", ["Sold", "Scrapped"]]]
			),
			"color": "#e42137",
		},
		{
			"label": "Pending Repairs",
			"document_type": "Asset Repair",
			"filters_json": json.dumps(
				[["Asset Repair", "docstatus", "=", 1],
				 ["Asset Repair", "repair_status", "=", "Pending"]]
			),
			"color": "#813bff",
		},
		{
			"label": "Asset Movements (30d)",
			"document_type": "Asset Movement",
			"filters_json": json.dumps(
				[["Asset Movement", "docstatus", "=", 1]]
			),
			"color": "#29cd42",
		},
	]

	for card in cards:
		_insert_if_missing(
			"Number Card", card["label"], "label",
			{
				"label": card["label"],
				"type": "Document Type",
				"document_type": card["document_type"],
				"function": "Count",
				"aggregate_function": "count",
				"filters_json": card["filters_json"],
				"is_public": 1,
				"show_percentage_stats": 0,
				"color": card["color"],
			},
		)


def make_dashboard_charts():
	yearly = lambda values: {
		"chart_type": "Sum",
		"timeseries": 1,
		"time_interval": "Monthly",
		"timespan": "Last Year",
		"group_by_type": "Sum",
		"is_public": 1,
		**values,
	}

	charts = [
		yearly({
			"chart_name": "Asset Acquisitions (Monthly)",
			"document_type": "Asset",
			"based_on": "purchase_date",
			"aggregate_function": "sum",
			"value_based_on": "gross_purchase_amount",
			"color": "#2490ef",
			"filters_json": json.dumps([["Asset", "docstatus", "=", 1]]),
		}),
		yearly({
			"chart_name": "Asset Repair Cost (Monthly)",
			"document_type": "Asset Repair",
			"based_on": "failure_date",
			"aggregate_function": "sum",
			"value_based_on": "total_repair_cost",
			"color": "#e42137",
			"filters_json": json.dumps([["Asset Repair", "docstatus", "=", 1]]),
		}),
		{
			"chart_name": "Assets by Category",
			"chart_type": "Group By",
			"document_type": "Asset",
			"group_by_type": "Count",
			"group_by_based_on": "asset_category",
			"timeseries": 0,
			"is_public": 1,
			"color": "#813bff",
			"filters_json": json.dumps([["Asset", "docstatus", "=", 1]]),
		},
		{
			"chart_name": "Asset Movements by Purpose",
			"chart_type": "Group By",
			"document_type": "Asset Movement",
			"group_by_type": "Count",
			"group_by_based_on": "purpose",
			"timeseries": 0,
			"is_public": 1,
			"color": "#29cd42",
			"filters_json": json.dumps([["Asset Movement", "docstatus", "=", 1]]),
		},
	]

	for chart in charts:
		_insert_if_missing(
			"Dashboard Chart", chart["chart_name"], "chart_name", chart
		)
