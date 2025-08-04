您需要重新输出财务报告阅读器的需求规格和技术方案。

基于前面的对话和代码库分析，我将为您重新整理完整的需求规格和技术方案：

## 需求规格书

### 1. 系统概述

目标：为Odoo社区版开发一个动态、实时、多期间比较的财务报告阅读器，支持资产负债表、利润表和现金流量表的查看，并提供PDF和Excel导出功能。

技术架构：基于现有的account.report数据模型，开发前端JavaScript组件和后端API接口。

### 2. 功能需求

#### 2.1 核心报表支持

- 资产负债表（Balance Sheet）
- 利润表（Income Statement）
- 现金流量表（Cash Flow Statement）

#### 2.2 查看功能

- 动态报告查看器界面
- 层级树形结构显示
- 多期间数据对比
- 实时数据刷新
- 钻取功能（点击查看明细）

#### 2.3 导出功能

- PDF格式导出
- Excel格式导出
- 多语言文件名支持
- 批量导出功能

#### 2.4 交互功能

- 报告类型选择器
- 期间选择器（支持多期间比较）
- 公司/分析维度选择器
- 展开/折叠报告行
- 列排序和筛选

### 3. 技术需求

#### 3.1 数据模型

基于现有的会计报告架构： tax_report_data.xml:3-18

- account.report - 报告定义主表
- account.report.line - 报告行项目
- account.report.column - 报告列定义
- account.report.expression - 计算表达式

#### 3.2 表达式引擎

支持多种计算引擎： tax_report_data.xml:30-47

- aggregation - 聚合计算
- tax_tags - 基于标签计算
- external - 外部数据源
- 自定义公式计算

#### 3.3 PDF模板系统

参考现有的PDF报告模板： din5008_report.xml:5-18

支持多种PDF格式和布局配置。

## 技术方案

### 1. 系统架构

#### 1.1 数据层

- 扩展account.report模型
- 创建财务报表特定的表达式引擎
- 实现多期间数据聚合算法

#### 1.2 业务逻辑层

```
class FinancialReportController(http.Controller):  
      
    @http.route('/api/financial_reports/<string:report_type>',   
                type='json', auth='user')  
    def get_report_data(self, report_type, **kwargs):  
        # 报告数据获取逻辑  
        pass  
      
    @http.route('/financial_reports/pdf/<string:report_type>',   
                type='http', auth='user')  
    def export_pdf(self, report_type, **kwargs):  
        # PDF导出功能  
        pass  
          
    @http.route('/financial_reports/excel/<string:report_type>',   
                type='http', auth='user')  
    def export_excel(self, report_type, **kwargs):  
        # Excel导出功能  
        pass
```

#### 1.3 前端展示层

```
class FinancialReportViewer extends Component {  
    // 报告查看器主组件  
    async loadReportData() { /* 数据加载逻辑 */ }  
    async exportPDF() { /* PDF导出 */ }  
    async exportExcel() { /* Excel导出 */ }  
}  
  
class ReportLineComponent extends Component {  
    // 报告行组件（支持层级展开）  
}  
  
class PeriodComparisonComponent extends Component {  
    // 多期间比较组件  
}
```

### 2. 报表实现方案

#### 2.1 账户类型映射

```
FINANCIAL_STATEMENT_MAPPING = {  
    'balance_sheet': {  
        'assets': ['asset_receivable', 'asset_cash', 'asset_current', 'asset_non_current'],  
        'liabilities': ['liability_payable', 'liability_current', 'liability_non_current'],  
        'equity': ['equity', 'equity_unaffected']  
    },  
    'income_statement': {  
        'revenue': ['income', 'income_other'],  
        'expenses': ['expense', 'expense_depreciation', 'expense_direct_cost']  
    },  
    'cash_flow': {  
        'cash_accounts': ['asset_cash']  
    }  
}
```

#### 2.2 多期间比较实现

参考法国税务报告的聚合公式： tax_report_data.xml:1781-1787

```
class PeriodComparisonData:  
    def __init__(self):  
        self.periods = []  # 期间列表  
        self.data_matrix = {}  # 数据矩阵  
        self.variance_analysis = {}  # 差异分析
```

### 3. 导出功能实现

#### 3.1 PDF导出

利用现有的ir.actions.report系统： swissqr_report.xml:17-25

```
def export_pdf(self, report_type, **kwargs):  
    report_data = self._get_report_data(report_type, **kwargs)  
    pdf_content = self.env['ir.actions.report']._render(  
        'financial_report_viewer.financial_report_template',  
        report_data.ids,  
        data={'report_data': report_data}  
    )  
    return request.make_response(pdf_content[0], headers=[...])
```

#### 3.2 Excel导出

```
def export_excel(self, report_type, **kwargs):  
    report_data = self._get_report_data(report_type, **kwargs)  
    output = io.BytesIO()  
    workbook = xlsxwriter.Workbook(output)  
    worksheet = workbook.add_worksheet(report_type)  
    self._write_excel_data(worksheet, report_data)  
    workbook.close()  
    return request.make_response(output.getvalue(), headers=[...])
```

### 4. 模块结构

```
financial_report_viewer/  
├── __manifest__.py  
├── models/  
│   ├── financial_report.py  
│   ├── report_line.py  
│   └── report_expression.py  
├── controllers/  
│   └── main.py  
├── static/src/  
│   ├── js/  
│   │   ├── financial_report_viewer.js  
│   │   ├── report_components.js  
│   │   └── chart_integration.js  
│   ├── css/  
│   │   └── financial_reports.css  
│   └── xml/  
│       └── templates.xml  
├── views/  
│   ├── financial_report_views.xml  
│   └── menu_items.xml  
├── data/  
│   ├── balance_sheet_template.xml  
│   ├── income_statement_template.xml  
│   └── cash_flow_template.xml  
├── report/  
│   ├── financial_report_pdf.xml  
│   └── financial_report_templates.xml  
└── i18n/  
    ├── zh_CN.po  
    ├── en_US.po  
    └── fr_FR.po  

```

### 5. 性能优化

#### 5.1 数据库优化

```
-- 创建专用索引  
CREATE INDEX idx_account_move_line_report   
ON account_move_line (account_id, date, company_id);  
  
-- 创建物化视图（可选）  
CREATE MATERIALIZED VIEW mv_financial_summary AS  
SELECT account_id, date_trunc('month', date) as period,   
       SUM(debit - credit) as balance  
FROM account_move_line  
GROUP BY account_id, date_trunc('month', date);
```

#### 5.2 前端性能优化

- 虚拟滚动（大数据量报告）
- 懒加载（按需加载报告行）
- 数据分页（分批加载）
- 缓存机制

### 6. 安全和权限

#### 6.1 权限控制

```
class FinancialReportSecurity:  
    def check_report_access(self, user, report_type):  
        # 检查用户是否有报告查看权限  
        pass  
      
    def filter_company_data(self, user, data):  
        # 根据用户权限过滤公司数据  
        pass
```

#### 6.2 数据安全

- 使用Odoo ORM防止SQL注入
- 实现CSRF保护
- 数据传输HTTPS加密

## Notes

此方案充分利用了Odoo v17现有的会计报告架构，参考了法国税务报告和瑞士QR账单等模块的实现模式。方案采用模块化设计，支持完整的财务报表查看、多期间比较和PDF/Excel导出功能，确保与Odoo核心系统的兼容性。

