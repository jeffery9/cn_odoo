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