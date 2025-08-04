/** @odoo-module **/

import { Component, useState } from "@odoo/owl";

export class ReportLineComponent extends Component {
    setup() {
        this.state = useState({ 
            isFolded: true,
        });
    }

    toggleFold() {
        this.state.isFolded = !this.state.isFolded;
    }
}

ReportLineComponent.template = "financial_report_viewer.ReportLineComponent";
ReportLineComponent.props = {
    line: Object,
    onLineClick: Function,
};