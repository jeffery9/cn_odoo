/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { ReportLineComponent } from "./report_components";

class FinancialReportViewer extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ 
            title: "",
            lines: [],
            columns: [], // New: for multi-period columns
            reports: [], 
            selected_report_id: null, 
            periods: [
                { id: 1, date_from: new Date(new Date().getFullYear(), 0, 1).toISOString().split('T')[0], date_to: new Date().toISOString().split('T')[0] } // Default to current year
            ],
            nextPeriodId: 2,
            showSankey: false,
        });

        onWillStart(async () => {
            if (this.props.action.context && this.props.action.context.default_report_id) {
                this.state.selected_report_id = this.props.action.context.default_report_id;
            } else {
                this.state.reports = await this.orm.searchRead(
                    'account.report',
                    [],
                    ['id', 'name']
                );
                if (this.state.reports.length > 0) {
                    this.state.selected_report_id = this.state.reports[0].id;
                }
            }
            await this.loadReportData();
        });
    }

    async loadReportData() {
        if (!this.state.selected_report_id) {
            return; // No report selected yet
        }
        const data = await this.orm.call(
            '', 
            `/api/financial_reports/${this.state.selected_report_id}`,
            {},
            { 
                periods: this.state.periods,
                context: this.props.context 
            }
        );
        this.state.title = data.title;
        this.state.lines = data.lines;
        this.state.columns = data.columns;
    }

    async onDateChange(ev) {
        const period = this.state.periods.find(p => p.id === 1); // Assuming single period for now
        if (period) {
            period[ev.target.id] = ev.target.value;
            await this.loadReportData();
        }
    }

    async onLineClick(action_id) {
        if (action_id) {
            this.action.doAction(action_id);
        }
    }

    addPeriod() {
        this.state.periods.push({ 
            id: this.state.nextPeriodId,
            date_from: new Date(new Date().getFullYear(), 0, 1).toISOString().split('T')[0],
            date_to: new Date().toISOString().split('T')[0]
        });
        this.state.nextPeriodId++;
        this.loadReportData();
    }

    removePeriod(periodId) {
        this.state.periods = this.state.periods.filter(p => p.id !== periodId);
        this.loadReportData();
    }

    onPeriodDateChange(periodId, field, value) {
        const period = this.state.periods.find(p => p.id === periodId);
        if (period) {
            period[field] = value;
            this.loadReportData();
        }
    }

    toggleSankey() {
        this.state.showSankey = !this.state.showSankey;
    }

    getSankeyData() {
        // Flatten values
        const vals = {};
        const traverse = (node) => {
            const name = node.name || "";
            vals[name] = node.balances[0] || 0.0;
            if (node.children) {
                node.children.forEach(traverse);
            }
        };
        this.state.lines.forEach(traverse);

        // Resolve standard nodes
        const findVal = (keywords, defaultVal) => {
            for (let k in vals) {
                for (let kw of keywords) {
                    if (k.includes(kw)) return vals[k];
                }
            }
            return defaultVal;
        };

        const revenue = findVal(["营业收入", "收入", "Revenue", "Income"], 0.0);
        const cogs = Math.abs(findVal(["营业成本", "主营业务成本", "COGS", "Cost"], 0.0));
        const selling = Math.abs(findVal(["销售费用", "Selling"], 0.0));
        const admin = Math.abs(findVal(["管理费用", "Admin"], 0.0));
        const rnd = Math.abs(findVal(["研发费用", "R&D", "RD"], 0.0));
        const tax = Math.abs(findVal(["所得税", "Tax"], 0.0));
        const netProfit = findVal(["净利润", "Net Profit"], revenue - cogs - selling - admin - rnd - tax);

        const grossProfit = Math.max(0, revenue - cogs);
        
        const hasData = revenue > 0.0 || cogs > 0.0 || selling > 0.0 || admin > 0.0 || rnd > 0.0 || tax > 0.0;
        if (!hasData) {
            return { nodes: [], links: [], hasData: false };
        }

        // Dimensions
        const W = 900;
        const H = 450;
        const padX = 80;
        const padY = 50;
        const dX = (W - padX * 2) / 2; // ~370px
        const maxColH = H - padY * 2; // ~350px

        // Node definitions
        const col0 = [
            { id: 'rev', label: '营业收入', value: revenue, color: '#1F4E79' }
        ];
        const col1 = [
            { id: 'gp', label: '毛利润', value: grossProfit, color: '#2E75B6' },
            { id: 'cogs', label: '营业成本', value: cogs, color: '#C65911' }
        ];
        const col2 = [
            { id: 'np', label: '净利润', value: netProfit, color: '#385723' },
            { id: 'sell', label: '销售费用', value: selling, color: '#7030A0' },
            { id: 'admin', label: '管理费用', value: admin, color: '#8FAADC' },
            { id: 'rnd', label: '研发费用', value: rnd, color: '#A5A5A5' },
            { id: 'tax', label: '所得税', value: tax, color: '#FFC000' }
        ];

        const scale = maxColH / revenue; // Scale based on input revenue

        // Layout Columns Y
        const layoutColumn = (cols, x) => {
            let currentY = padY;
            const gap = 20;
            return cols.map(node => {
                const h = Math.max(15, node.value * scale);
                const item = {
                    ...node,
                    x: x,
                    y: currentY,
                    w: 25,
                    h: h,
                    outOffset: 0,
                    inOffset: 0
                };
                currentY += h + gap;
                return item;
            });
        };

        const nodes0 = layoutColumn(col0, padX);
        const nodes1 = layoutColumn(col1, padX + dX);
        const nodes2 = layoutColumn(col2, padX + dX * 2);

        const allNodesMap = {};
        [...nodes0, ...nodes1, ...nodes2].forEach(n => {
            allNodesMap[n.id] = n;
        });

        // Link definitions
        const linkDefs = [
            { src: 'rev', tgt: 'gp', val: grossProfit, color: 'rgba(46, 117, 182, 0.25)' },
            { src: 'rev', tgt: 'cogs', val: cogs, color: 'rgba(198, 89, 17, 0.25)' },
            { src: 'gp', tgt: 'np', val: netProfit, color: 'rgba(56, 87, 35, 0.25)' },
            { src: 'gp', tgt: 'sell', val: selling, color: 'rgba(112, 48, 160, 0.25)' },
            { src: 'gp', tgt: 'admin', val: admin, color: 'rgba(143, 170, 220, 0.25)' },
            { src: 'gp', tgt: 'rnd', val: rnd, color: 'rgba(165, 165, 165, 0.25)' },
            { src: 'gp', tgt: 'tax', val: tax, color: 'rgba(255, 192, 0, 0.25)' }
        ];

        const links = linkDefs.map(link => {
            const s = allNodesMap[link.src];
            const t = allNodesMap[link.tgt];
            if (!s || !t) return null;

            const h = Math.max(2, link.val * scale);

            const x0 = s.x + s.w;
            const y0 = s.y + s.outOffset;
            const x1 = t.x;
            const y1 = t.y + t.inOffset;

            s.outOffset += h;
            t.inOffset += h;

            // Curved ribbon path
            const path = `M ${x0} ${y0}
                          C ${(x0 + x1) / 2} ${y0}, ${(x0 + x1) / 2} ${y1}, ${x1} ${y1}
                          L ${x1} ${y1 + h}
                          C ${(x0 + x1) / 2} ${y1 + h}, ${(x0 + x1) / 2} ${y0 + h}, ${x0} ${y0 + h}
                          Z`;

            return {
                path,
                color: link.color,
                value: link.val.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
                label: `${s.label} ──► ${t.label}`
            };
        }).filter(Boolean);

        const nodes = [...nodes0, ...nodes1, ...nodes2].map(n => ({
            ...n,
            formattedValue: n.value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
        }));

        return { nodes, links, hasData: true };
    }

    exportPDF() {
        const url = `/financial_reports/pdf/${this.state.selected_report_id}?periods=${JSON.stringify(this.state.periods)}`;
        window.open(url, '_blank');
    }

    exportExcel() {
        const url = `/financial_reports/excel/${this.state.selected_report_id}?periods=${JSON.stringify(this.state.periods)}`;
        window.open(url, '_blank');
    }
}

FinancialReportViewer.components = { ReportLineComponent };
FinancialReportViewer.template = "financial_report_viewer.FinancialReportViewer";

registry.category("actions").add("financial_report_viewer_action", FinancialReportViewer);