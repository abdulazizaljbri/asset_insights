/* Asset Finance HQ — depreciation & value dashboard for ERPNext v15.
   Live from the Asset Insights script reports. */

frappe.pages["asset-finance-hq"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Asset Finance HQ"),
		single_column: true,
	});


	page.set_primary_action(__("Refresh"), () => load());
	page.set_secondary_action(__("Workspace"), () =>
		frappe.set_route("app/asset-insights")
	);

	wrapper.querySelector(".layout-main-section-wrapper").classList.add("ai-hq-wrapper");
	const main = wrapper.querySelector(".layout-main-section");

	const KPI_SLOTS = [
		["kpi-gross", __("Gross Value"), "#2490ef"],
		["kpi-accum", __("Accumulated Depreciation"), "#f59f00"],
		["kpi-nbv", __("Net Book Value"), "#29cd42"],
		["kpi-age", __("Average Age"), "#813bff"],
		["kpi-eol", __("Nearing End Of Life"), "#e42137"],
		["kpi-disposed", __("Disposals (12m)"), "#ec8d30"],
	];

	const VERSION_MARKER = "Asset Finance HQ • v6";

	main.innerHTML = `
		<div class="ai-hq">
			<div class="ai-controls">
				<div class="ai-control">
					<div class="ai-control-label">${__("Company")}</div>
					<div id="ai-company-wrap"></div>
				</div>
				<label class="ai-control ai-switch">
					<input type="checkbox" id="ai-drafts" checked>
					<span>${__("Include Drafts")}</span>
				</label>
			</div>
			<div id="ai-fhint" class="ai-hint" style="display:none"></div>
			<div class="ai-kpis">
				${KPI_SLOTS.map(
					([id, label, color]) => `
					<div class="ai-kpi" style="--kc:${color}">
						<div class="ai-kpi-label">${label}</div>
						<div class="ai-kpi-value" id="${id}">…</div>
						<div class="ai-kpi-sub" id="${id}-sub"></div>
					</div>`
				).join("")}
			</div>
			<div class="ai-charts">
				<div class="ai-chart-card">
					<div class="ai-chart-title">${__("Net Book Value by Location")}</div>
					<div id="ai-f1"></div>
				</div>
				<div class="ai-chart-card">
					<div class="ai-chart-title">${__("Asset Ageing")}</div>
					<div id="ai-f2"></div>
				</div>
				<div class="ai-chart-card">
					<div class="ai-chart-title">${__("Disposal NBV (Monthly)")}</div>
					<div id="ai-f3"></div>
				</div>
				<div class="ai-chart-card">
					<div class="ai-chart-title">${__("Assets Nearing End Of Life")}</div>
					<div id="ai-f4"></div>
				</div>
			</div>
			<div class="ai-version">${VERSION_MARKER}</div>
		</div>`;

	// in-body filter bar (always visible - page-head fields are hidden
	// on some v15 builds, especially under RTL)
	const company_control = new frappe.ui.form.ControlLink({
		parent: wrapper.querySelector("#ai-company-wrap"),
		df: {
			fieldtype: "Link",
			options: "Company",
			fieldname: "company",
		},
	});
	company_control.set_value(frappe.defaults.get_user_default("Company"));
	company_control.$input.on("change", () => load());
	wrapper.querySelector("#ai-drafts").addEventListener("change", () => load());

	let currency = null;

	function set_kpi(id, value, sub) {
		const el = document.getElementById(id);
		if (el) el.innerHTML = value;
		const sub_el = document.getElementById(id + "-sub");
		if (sub_el) sub_el.innerHTML = sub || "";
	}

	function fmt_money(value, precision = 0) {
		try {
			return format_currency(value || 0, currency || undefined, precision);
		} catch (e) {
			return (value || 0).toLocaleString();
		}
	}

	function empty(id) {
		const el = document.getElementById(id);
		if (el) el.innerHTML = `<div class="ai-empty">${__("No data for the selected filters")}</div>`;
	}

	function render_chart(id, type, labels, datasets, colors, y_currency) {
		const el = document.getElementById(id);
		if (!el) return;
		if (!labels || !labels.length) return empty(id);
		el.innerHTML = "";
		new frappe.Chart(el, {
			type: type,
			colors: colors,
			height: 240,
			axisOptions: { xIsSeries: type === "line", shortenYAxisNumbers: 1 },
			data: { labels: labels, datasets: datasets },
			tooltipOptions: {
				formatTooltipY: (v) => (y_currency ? fmt_money(v, 0) : String(v)),
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
							company: company_control.get_value() || undefined,
							include_drafts: document.getElementById("ai-drafts").checked ? 1 : 0,
						},
						filters || {}
					),
				},
			})
			.then((r) => (r.message && r.message.result) || []);
	}

	function month_label(k) {
		return frappe.datetime.str_to_obj(k + "-15").toLocaleDateString(undefined, {
			month: "short",
			year: "2-digit",
		});
	}

	function load() {
		const today = frappe.datetime.get_today();
		const year_ago = frappe.datetime.add_months(today, -12);

		KPI_SLOTS.forEach(([id]) => set_kpi(id, "…", ""));

		run("ai_asset_value_summary", { group_by: "Company", as_of: today })
			.then((rows) => {
				const gross = rows.reduce((a, x) => a + (x.gross || 0), 0);
				const accum = rows.reduce((a, x) => a + (x.accum_dep || 0), 0);
				const nbv = rows.reduce((a, x) => a + (x.nbv || 0), 0);
				set_kpi("kpi-gross", fmt_money(gross));
				set_kpi("kpi-accum", fmt_money(accum),
					`${gross ? ((accum / gross) * 100).toFixed(1) : "0"}% ${__("of gross")}`);
				set_kpi("kpi-nbv", fmt_money(nbv));
				const total_count = rows.reduce((a, x) => a + (x.asset_count || 0), 0);
				const hint = document.getElementById("ai-fhint");
				if (hint) {
					hint.style.display = total_count === 0 ? "block" : "none";
					hint.innerHTML = total_count === 0
						? __("No assets found for these filters - run ai_seed_data() from the console or check the selected Company.")
						: "";
				}
			})
			.catch(() => {
				set_kpi("kpi-gross", "—", "");
				set_kpi("kpi-accum", "—", "");
				set_kpi("kpi-nbv", "—", "");
			});

		run("ai_asset_value_summary", { group_by: "Location", as_of: today })
			.then((rows) => {
				const loc = rows.slice().sort((a, b) => (b.nbv || 0) - (a.nbv || 0)).slice(0, 10);
				render_chart("ai-f1", "bar", loc.map((x) => x.group_value),
					[{ name: __("Net Book Value"), values: loc.map((x) => Math.round(x.nbv || 0)) }],
					["#2490ef"], true);
			})
			.catch(() => empty("ai-f1"));

		run("ai_asset_ageing", { as_of: today })
			.then((rows) => {
				const count = rows.reduce((a, x) => a + (x.asset_count || 0), 0);
				const ages = rows.reduce((a, x) => a + (x.avg_age || 0) * (x.asset_count || 0), 0);
				set_kpi("kpi-age", ages && count ? (ages / count).toFixed(1) + " " + __("yrs") : "—",
					`${count} ${__("assets")}`);
				render_chart("ai-f2", "bar", rows.map((x) => x.bucket),
					[{ name: __("Net Book Value"), values: rows.map((x) => Math.round(x.nbv || 0)) }],
					["#813bff"], true);
			})
			.catch(() => empty("ai-f2"));

		run("ai_disposal_register", { from_date: year_ago, to_date: today })
			.then((rows) => {
				const nbv = rows.reduce((a, x) => a + (x.nbv || 0), 0);
				set_kpi("kpi-disposed", String(rows.length), fmt_money(nbv));
				const by_month = {};
				rows.forEach((x) => {
					if (!x.disposal_date) return;
					const k = x.disposal_date.slice(0, 7);
					by_month[k] = (by_month[k] || 0) + (x.nbv || 0);
				});
				const keys = Object.keys(by_month).sort();
				render_chart("ai-f3", "bar", keys.map(month_label),
					[{ name: __("Net Book Value"), values: keys.map((k) => Math.round(by_month[k])) }],
					["#ec8d30"], true);
			})
			.catch(() => empty("ai-f3"));

		run("ai_end_of_life_alert", { as_of: today, within_months: 12 })
			.then((rows) => {
				set_kpi("kpi-eol", String(rows.length), __("within 12 months"));
				const by_bucket = {};
				rows.forEach((x) => {
					const m = x.months_left || 0;
					const b = m <= 3 ? "0-3" : m <= 6 ? "4-6" : m <= 9 ? "7-9" : "10-12";
					by_bucket[b] = (by_bucket[b] || 0) + 1;
				});
				const items = Object.entries(by_bucket).sort();
				render_chart("ai-f4", "bar", items.map((x) => x[0] + " " + __("months")),
					[{ name: __("Assets"), values: items.map((x) => x[1]) }],
					["#e42137"], false);
			})
			.catch(() => empty("ai-f4"));
	}

	frappe.call({
		method: "frappe.client.get_value",
		args: { doctype: "Global Defaults", fieldname: "default_currency" },
		callback(r) {
			currency = (r.message && r.message.default_currency) || null;
		},
	});

	load();
};
