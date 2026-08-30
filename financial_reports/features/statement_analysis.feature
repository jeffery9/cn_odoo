# language: zh-CN
Feature: 动态自定义多维财务报表引擎

  Scenario: 生成基础财务报表与多期间同比环比比较
    Given 财务人员已录入 2024 年度 1 月和 2 月的会计凭证分录 (account.move.line)
    And 系统预装了“资产负债表”、“利润表”与“现金流量表”模板
    When 财务人员打开“资产负债表”查看器
    And 选择进行多账期对比：
      | 期间 ID | 起始日期 | 截止日期 |
      | 期间 1  | 2024-01-01 | 2024-01-31 |
      | 期间 2  | 2024-02-01 | 2024-02-28 |
    Then 系统应自动以列矩阵 (Columns Matrix) 的形式平行展示多期间的账户科目余额
    And 精准对齐渲染各行，并在 Excel 一键导出时保留级次缩进排版

  Scenario: 自定义新型财务管理报表零代码生成与下钻
    Given 集团管理会计需要制作一份名为“管理费用明细表”的特定管理报表
    And 管理会计在 Odoo 后端创建了一张全新的 account.report 记录
    And 在其下追加了一张行项目（account.report.line），名为“行政招待支出汇总”
    And 绑定表达式（account.report.expression）类型为“formula”，公式内容为“balance * 2.0”
    When 财务经理在财务报告查看器中刷新报表列表
    Then 下拉框中应动态出现并能够选择“管理费用明细表”
    And 系统能沙箱级执行并计算出正确的公式翻倍值
    And 双击该明细汇总行能够自动弹窗（act_window）打开对应的 Odoo 原始日记账凭证细单 (account.move.line) 列表
