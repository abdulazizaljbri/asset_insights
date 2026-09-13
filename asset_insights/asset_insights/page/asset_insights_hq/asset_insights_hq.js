/* Asset Insights HQ — executive asset dashboard (clean rebuild v8).
 * ERPNext v15 — verified APIs only:
 *   frappe.db.get_list, frappe.utils.escape_html, frappe.desk.query_report.run,
 *   frappe.Chart (bundled), plain HTML controls (no page-head fields,
 *   plain HTML controls only (fragile alternatives avoided on 15.26.0 / RTL).
 * Drafts are ALWAYS included by default (sites running on unsubmitted docs).
 */

frappe.pages["asset-insights-hq"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Asset Insights HQ"),
		single_column: true,
	});

	page.set_primary_action(__("Refresh"), () => load());
	page.set_secondary_action(__("Workspace"), () =>
		frappe.set_route("app/asset-insights")
	);

	const kpis = () => [
		["kpi-assets", __("Total Assets"), "#2490ef"],
		["kpi-nbv", __("Net Book Value"), "#29cd42"],
		["kpi-dep", __("Depreciation (12m)"), "#813bff"],
		["kpi-overdue", __("Overdue Maintenance"), "#f59f00"],
		["kpi-repairs", __("Pending Repairs"), "#e42137"],
		["kpi-moves", __("Movements (30d)"), "#ec8d30"],
	];

	const chartCard = (id, title) => `
		<div class="ai-chart-card">
			<div class="ai-chart-title">${title}</div>
			<div id="${id}"></div>
		</div>`;

	const main = wrapper.querySelector(".layout-main-section");
	main.innerHTML = `
		<div class="ai-hq">
			<div class="ai-controls">
				<div class="ai-control">
					<div class="ai-control-label">${__("Company")}</div>
					<select id="ai-company" class="form-control"></select>
				</div>
				<label class="ai-control ai-switch">
					<input type="checkbox" id="ai-drafts" checked>
					<span>${__("Include Drafts")}</span>
				</label>
			</div>
			<div id="ai-hint" class="ai-hint" style="display:none"></div>
			<div class="ai-kpis">
				${kpis()
					.map(
						([id, label, color]) => `
					<div class="ai-kpi" style="--kc:${color}">
						<div class="ai-kpi-label">${label}</div>
						<div class="ai-kpi-value" id="${id}">…</div>
						<div class="ai-kpi-sub" id="${id}-sub"></div>
					</div>`
					)
					.join("")}
			</div>
			<div class="ai-charts">
				${chartCard("ai-c1", __("Net Book Value by Category"))}
				${chartCard("ai-c2", __("Depreciation (Monthly)"))}
				${chartCard("ai-c3", __("Repair Cost (Monthly)"))}
				${chartCard("ai-c4", __("Movements by Purpose"))}
			</div>
			<div class="ai-version">Asset Insights HQ • v8</div>
		</div>`;

	let currency = null;
	const company_select = document.getElementById("ai-company");
	const drafts_box = document.getElementById("ai-drafts");

	function fmt_money(value, precision = 0) {
		try {
			return format_currency(value || 0, currency || undefined, precision);
		} catch (e) {
			return (value || 0).toLocaleString();
		}
	}

	function set_kpi(id, value, sub) {
		const v = document.getElementById(id);
		if (v) v.innerHTML = value;
		const s = document.getElementById(id + "-sub");
		if (s) s.innerHTML = sub || "";
	}

	function empty_chart(id) {
		const el = document.getElementById(id);
		if (el)
			el.innerHTML = `<div class="ai-empty">${__(
				"No data for the selected filters"
			)}</div>`;
	}

	function draw(id, type, labels, datasets, colors, money) {
		const el = document.getElementById(id);
		if (!el) return;
		if (!labels || !labels.length) return empty_chart(id);
		el.innerHTML = "";
		new frappe.Chart(el, {
			type: type,
			colors: colors,
			height: 240,
			axisOptions: { xIsSeries: type === "line", shortenYAxisNumbers: 1 },
			data: { labels: labels, datasets: datasets },
			tooltipOptions: {
				formatTooltipY: (v) => (money ? fmt_money(v, 0) : String(v)),
			},
		});
	}

	function run(report_name, filters) {
		return frappe
			.call({
				method: "frappe.desk.query_report.run",
				args: {
					report_name: report_name,
					filters: Object.assign(
						{
							company: company_select.value || undefined,
							include_drafts: drafts_box.checked ? 1 : 0,
						},
						filters || {}
					),
				},
			})
			.then((r) => (r.message && r.message.result) || []);
	}

	function month_label(ym) {
		return frappe.datetime
			.str_to_obj(ym + "-15")
			.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
	}

	function by_month(rows, date_field, value_fields) {
		const out = {};
		rows.forEach((x) => {
			const d = x[date_field];
			if (!d) return;
			const k = String(d).slice(0, 7);
			const sum = value_fields.reduce((a, f) => a + (x[f] || 0), 0);
			out[k] = (out[k] || 0) + sum;
		});
		return out;
	}

	function load() {
		const today = frappe.datetime.get_today();
		const in_12m = frappe.datetime.add_months(today, 12);
		const month_ago = frappe.datetime.add_months(today, -1);
		kpis().forEach(([id]) => set_kpi(id, "…", ""));

		run("ai_asset_value_summary", { group_by: "Asset Category", as_of: today })
			.then((rows) => {
				const count = rows.reduce((a, x) => a + (x.asset_count || 0), 0);
				const gross = rows.reduce((a, x) => a + (x.gross || 0), 0);
				const nbv = rows.reduce((a, x) => a + (x.nbv || 0), 0);
				set_kpi("kpi-assets", String(count), `${fmt_money(gross)} ${__("gross")}`);
				set_kpi("kpi-nbv", fmt_money(nbv), `${rows.length} ${__("categories")}`);

				const hint = document.getElementById("ai-hint");
				if (hint) {
					hint.style.display = count === 0 ? "block" : "none";
					hint.innerHTML = count === 0
						? __("No assets found for these filters - run ai_seed_data() from the console or check the selected Company.")
						: "";
				}

				const top = rows.slice().sort((a, b) => (b.nbv || 0) - (a.nbv || 0)).slice(0, 10);
				draw("ai-c1", "bar", top.map((x) => x.group_value),
					[{ name: __("Net Book Value"), values: top.map((x) => Math.round(x.nbv || 0)) }],
					["#29cd42"], true);
			})
			.catch(() => empty_chart("ai-c1"));

		run("ai_depreciation_plan", { from_date: today, to_date: in_12m })
			.then((rows) => {
				const total = rows.reduce((a, x) => a + (x.depreciation_amount || 0), 0);
				set_kpi("kpi-dep", fmt_money(total), `${rows.length} ${__("scheduled bookings")}`);
				const m = by_month(rows, "schedule_date", ["depreciation_amount"]);
				const keys = Object.keys(m).sort();
				draw("ai-c2", "line", keys.map(month_label),
					[{ name: __("Depreciation Amount"), values: keys.map((k) => Math.round(m[k])) }],
					["#813bff"], true);
			})
			.catch(() => empty_chart("ai-c2"));

		run("ai_maintenance_schedule", { due_from: today, due_to: in_12m })
			.then((rows) => {
				const overdue = rows.filter((x) => (x.days_until_due || 0) < 0).length;
				set_kpi("kpi-overdue", String(overdue), `${rows.length} ${__("scheduled tasks")}`);
			})
			.catch(() => set_kpi("kpi-overdue", "—", ""));

		run("ai_repair_register", { from_date: month_ago, to_date: today })
			.then((rows) => {
				const pending = rows.filter((x) => x.repair_status === __("Pending")).length;
				const cost = rows.reduce((a, x) => a + (x.total_repair_cost || x.repair_cost || 0), 0);
				set_kpi("kpi-repairs", String(pending), `${fmt_money(cost)} ${__("this month")}`);
				const m = by_month(rows, "failure_date", ["total_repair_cost", "repair_cost"]);
				const keys = Object.keys(m).sort().slice(-12);
				draw("ai-c3", "bar", keys.map(month_label),
					[{ name: __("Total Repair Cost"), values: keys.map((k) => Math.round(m[k])) }],
					["#e42137"], true);
			})
			.catch(() => empty_chart("ai-c3"));

		run("ai_asset_movement_register", { from_date: month_ago, to_date: today })
			.then((rows) => {
				set_kpi("kpi-moves", String(rows.length), __("last 30 days"));
				const by_purpose = {};
				rows.forEach((x) => {
					const k = x.purpose || "—";
					by_purpose[k] = (by_purpose[k] || 0) + 1;
				});
				const items = Object.entries(by_purpose);
				draw("ai-c4", "donut", items.map((x) => x[0]),
					[{ name: __("Movement Lines"), values: items.map((x) => x[1]) }],
					["#2490ef", "#29cd42", "#f59f00", "#813bff"], false);
			})
			.catch(() => empty_chart("ai-c4"));
	}

	frappe.db
		.get_list("Company", {
			fields: ["name"],
			limit_page_length: 0,
			order_by: "name",
		})
		.then((rows) => {
			const def = frappe.defaults.get_user_default("Company");
			company_select.innerHTML =
				`<option value="">${__("All Companies")}</option>` +
				rows
					.map(
						(r) =>
							`<option value="${frappe.utils.escape_html(r.name)}"${
								r.name === def ? " selected" : ""
							}>${frappe.utils.escape_html(r.name)}</option>`
					)
					.join("");
		});

	company_select.addEventListener("change", () => load());
	drafts_box.addEventListener("change", () => load());

	frappe.call({
		method: "frappe.client.get_value",
		args: { doctype: "Global Defaults", fieldname: "default_currency" },
		callback(r) {
			currency = (r.message && r.message.default_currency) || null;
		},
	});

	load();
};

frappe.pages["asset-insights-hq"].on_page_show = function () {
	/* nothing extra */
};

