# l10n_cn_tax/features/china_vat_compliance.feature
Feature: 中国增值税合规与数电发票金税集成 (PRC VAT Compliance & Golden Tax Digital Integration)
  As a Chinese tax accountant,
  I want Odoo to automatically match State Tax Catalog commodity codes, track certified input VAT, and compute VAT Super Deductions (加计抵减),
  So that our tax declaration matches the Golden Tax System (金税系统 / 数电发票) and complies with the State Taxation Administration (国家税务总局).

  Scenario Outline: 金税系统数电发票增值税率与免税商品分类匹配
    Given 销售开票员为中国客户创建了一张应收销售发票 (account.move)
    And 该发票明细包含品类为 "<product_category>" 的商品
    When 会计确认该销售发票，并触发表单过账
    Then 发票明细行的税收分类编码 (tax_catalog_code) 必须自动解析为国家标准分类码 "<tax_catalog_code>"
    And 销项增值税计算公式必须严格匹配法定税率 "<vat_rate>"%
    And 导出的金税数电发票 XML/JSON 报文中的开票类型和税率完全一致

    Examples:
      | product_category | tax_catalog_code | vat_rate |
      | 工业机械设备     | 1090243000000000 | 13       |
      | 房屋建设工程     | 3010101000000000 | 9        |
      | 软件研发技术服务 | 1060301010000000 | 6        |
      | 农业自产初级产品 | 1010115000000000 | 0        |

  Scenario Outline: 进项税额勾选确认与抵扣链条审计
    Given 采购文员登记了一笔金额为 100,000.00 元的供应商进项增值税发票
    And 初始状态下，税款计入待认证会计科目 "<pending_account_code>" (待认证进项税额)
    When 财务会计在国家税务总局发票平台执行勾选认证
    And 在 Odoo 中标记该发票为 "<certification_status>" (已勾选抵扣)
    Then 凭证的税款必须自动通过过账结转到抵扣科目 "<deducted_account_code>" (应交增值税-进项税额)
    And 结转日记账分录必须借贷相抵，记录审计日志以备税务机关穿透式稽查

    Examples:
      | pending_account_code | certification_status | deducted_account_code |
      | 22210101             | certified            | 22210102              |

  Scenario: 增值税加计抵减计算与会计分录自动生成
    Given 某现代服务业企业符合国家 5% 增值税加计抵减政策 (Super Deduction)
    And 该企业在本月共认证并勾选可抵扣进项税额共计 100,000.00 元
    And 计提的销项税额共计 150,000.00 元
    When 财务会计运行“增值税期末结转与申报向导”
    Then 系统必须精确计算出加计抵减额为 5,000.00 元 (100,000.00 * 5%)
    And 计算出本月实际应纳增值税额为 45,000.00 元 (150,000.00 - 100,000.00 - 5,000.00)
    And 自动生成期末结转凭证：
      | 科目名称                         | 借方金额  | 贷方金额  |
      | 应交税费-应交增值税-转出未交增值税 | 45,000.00 | 0.00      |
      | 其他收益-加计抵减                | 0.00      | 5,000.00  |
      | 应交税费-未交增值税               | 0.00      | 40,000.00 |
