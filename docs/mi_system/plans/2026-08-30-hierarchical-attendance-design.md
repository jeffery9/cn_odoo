# Specification: Hierarchical Attendance Policy Inheritance & Org Tree Mapping

## 1. Architectural Intent
To support large-scale enterprises with complex, multi-tiered organizational structures, the attendance system is upgraded from a flat, priority-sequence list to an **HR Organization Tree Inheritance Model**. 

By mapping attendance policies directly onto Odoo's native HR entities (`hr.employee` and `hr.department`), we achieve a seamless "Configure-Once, Inherit-Everywhere" user experience. HR managers can assign policies to high-level departments, and all sub-departments and nested employees automatically inherit them unless explicitly overridden.

---

## 2. Model Modifications

### 2.1. `cn.attendance.settings` (Simplified)
Scoping and manual ordering fields are deprecated on this model to keep it pure, highly reusable, and focused strictly on the attendance rules.
*   **Deprecate/Remove:** `applicability`, `sequence`, `department_ids`, `employee_ids`.
*   **Keep:** Core attendance parameters (`standard_check_in`, `standard_check_out`, `standard_daily_hours`, `grace_period_late`, `missing_checkout_fallback`).

### 2.2. Native Model Extensions (`hr.employee` & `hr.department`)
We inject a direct reference to the attendance policy group at each tier of the organizational structure.

#### `hr.employee` Extension
*   `attendance_settings_id` (`Many2one`, `cn.attendance.settings`, string="Personal Attendance Policy"): Custom personal override. If set, this completely overrides any department or company defaults.
*   `resolved_attendance_settings_id` (`Many2one`, `cn.attendance.settings`, compute="_compute_resolved_settings", string="Active Attendance Policy", readonly=True): Represents the active, evaluated policy for the employee.

#### `hr.department` Extension (Recursive Tree Nodes)
*   `attendance_settings_id` (`Many2one`, `cn.attendance.settings`, string="Department Attendance Policy"): Applied policy for this department. Inherits downward to all nested sub-departments and child employees recursively unless overridden.

---

## 3. Recursive Resolution Engine

To determine the active policy for an employee, the evaluation engine climbs the HR organizational tree recursively.

### 3.1. Evaluation Flow (ASCII Diagram)
```
  [ hr.employee (Zhang San) ]
             │
             ├──► Has `attendance_settings_id`?
             │         ├──► Yes: Use this personal policy
             │         └──► No: Climb to department
             ▼
  [ hr.department (Sales Team B) ]
             │
             ├──► Has `attendance_settings_id`?
             │         ├──► Yes: Use this department policy
             │         └──► No: Traverse up parent_id
             ▼
  [ hr.department (Sales Division) ] (Parent)
             │
             ├──► Has `attendance_settings_id`?
             │         ├──► Yes: Use this parent department policy
             │         └──► No: Fallback to Company
             ▼
  [ res.company Default Settings ]
```

### 3.2. Code Signature
```python
@api.model
def get_settings_for_employee(self, employee):
    """
    Climbs the HR tree to resolve the active attendance settings for the employee.
    Flow: Employee Override -> Department (Recursive climbing) -> Company Default.
    """
    if not employee:
        return self.browse()

    # 1. Check Employee-level specific override
    if employee.attendance_settings_id:
        return employee.attendance_settings_id

    # 2. Climb Department tree
    department = employee.department_id
    while department:
        if department.attendance_settings_id:
            return department.attendance_settings_id
        department = department.parent_id

    # 3. Fallback to Company Default (lowest sequence or standard default)
    company_default = self.search([('company_id', '=', employee.company_id.id)], limit=1)
    if company_default:
        return company_default

    # 4. Standard global settings browse fallback
    return self.search([], limit=1)
```

---

## 4. Tree-Aware Calendar Leaves Synchronization

Our `cn.attendance.holiday.rule` synchronization engine is upgraded to dynamically resolve which Odoo resource calendars (`resource.calendar`) need to receive synced global leave records by scanning the active HR Org tree.

### 4.1. Calendar Resolution Algorithm
When a holiday rule is created or modified on a policy, the target calendars are resolved using the following logic:
1.  **Resolve Scoped Employees:**
    *   Find all employees directly assigned to this settings record:
        `direct_employees = env['hr.employee'].search([('attendance_settings_id', '=', settings.id)])`
2.  **Resolve Scoped Departments:**
    *   Find all departments directly assigned to this settings record:
        `departments = env['hr.department'].search([('attendance_settings_id', '=', settings.id)])`
    *   Query all employees in these departments recursively (including child departments):
        `dept_employees = env['hr.employee'].search([('department_id', 'child_of', departments.ids)])`
3.  **Union & Extract Calendars:**
    *   Unique set of `resource_calendar_id` from both employee pools.
    *   `calendars = (direct_employees + dept_employees).mapped('resource_calendar_id')`
4.  **Sync Leaves:** Write/Remove native `resource.calendar.leaves` for this unified set of calendars.

---

## 5. View Integration & User Experience

We inject our new fields directly into native Odoo views, giving HR managers clean visibility of the active rules.

### 5.1. Department Form View Override
In `views/hr_department_views.xml`, we inject a dedicated card under a new group:
```xml
<record id="view_department_form_inherit_payroll" model="ir.ui.view">
    <field name="name">hr.department.form.inherit.payroll</field>
    <field name="model">hr.department</field>
    <field name="inherit_id" ref="hr.view_department_form"/>
    <field name="arch" type="xml">
        <xpath expr="//group[@name='left']" position="after">
            <group string="Attendance &amp; Payroll Settings" name="payroll_settings">
                <field name="attendance_settings_id" options="{'no_create': True}"/>
            </group>
        </xpath>
    </field>
</record>
```

### 5.2. Employee Form View Override
In `views/hr_employee_views.xml`, we inject the settings fields:
```xml
<record id="view_employee_form_inherit_payroll" model="ir.ui.view">
    <field name="name">hr.employee.form.inherit.payroll</field>
    <field name="model">hr.employee</field>
    <field name="inherit_id" ref="hr.view_employee_form"/>
    <field name="arch" type="xml">
        <xpath expr="//page[@name='public']" position="inside">
            <group string="Attendance &amp; Payroll Policies" name="payroll_policies">
                <field name="attendance_settings_id" options="{'no_create': True}"/>
                <field name="resolved_attendance_settings_id"/>
            </group>
        </xpath>
    </field>
</record>
```
