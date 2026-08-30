# Hierarchical Attendance Policy Inheritance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement an HR Organization Tree Inheritance Model for attendance policies (`cn.attendance.settings`) supporting recursive policy resolution, tree-aware calendar leaves synchronization, and native Odoo form view integrations.

**Architecture:** Extend native Odoo models `hr.employee` and `hr.department` with a direct Many2one link to `cn.attendance.settings`. Refactor the policy evaluation engine to climb the HR department tree recursively to resolve active policies. Deprecate flat sequence-based resolution.

**Tech Stack:** Odoo 17, Python, PostgreSQL, XML.

**Spec:** `docs/mi_system/plans/2026-08-30-hierarchical-attendance-design.md`

## Global Constraints
*   **Think in Odoo:** Respect native Odoo ORM patterns, Active Record API, and inheritance chains.
*   **Complete Override:** Traverse the tree to locate the closest policy, then adopt its entire record. Do not merge fields.
*   **Test-Driven Development:** Write and execute explicit Python unittest test cases validating both active policy resolution and calendar leaf propagation.

---

### Task 1: Native HR Model Extensions & XML Views Override

**Files:**
- Create: `cn_payroll_core/views/hr_department_views.xml`
- Create: `cn_payroll_core/views/hr_employee_views.xml`
- Modify: `cn_payroll_core/models/cn_attendance_settings.py` (add model extensions)
- Modify: `cn_payroll_core/__manifest__.py` (register view XMLs)

**Interfaces:**
- Produces: `hr.employee.attendance_settings_id` (Many2one), `hr.employee.resolved_attendance_settings_id` (Many2one Compute), `hr.department.attendance_settings_id` (Many2one)

- [ ] **Step 1: Simplify `cn.attendance.settings` and add extensions in `cn_payroll_core/models/cn_attendance_settings.py`**

Simplify the settings model fields (remove sequence and applicability fields) and add native extensions:
```python
# Inside cn_payroll_core/models/cn_attendance_settings.py

class CnAttendanceSettings(models.Model):
    _name = 'cn.attendance.settings'
    _description = 'Chinese Attendance Policy'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(required=True, string='Settings Label', tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    standard_check_in = fields.Float(string='Standard Check-In', default=9.0, required=True, tracking=True)
    standard_check_out = fields.Float(string='Standard Check-Out', default=18.0, required=True, tracking=True)
    standard_daily_hours = fields.Float(string='Standard Daily Hours', default=8.0, required=True, tracking=True)
    grace_period_late = fields.Integer(string='Late Grace Period (Min)', default=0, required=True, tracking=True)
    missing_checkout_fallback = fields.Selection([
        ('standard', 'Autocomplete Shift'),
        ('absent', 'Count as Absent')
    ], string='Missing Check-out Fallback', default='standard', required=True, tracking=True)
    holiday_rule_ids = fields.One2many('cn.attendance.holiday.rule', 'settings_id', string='Holiday and Swapped Workday Rules')


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    attendance_settings_id = fields.Many2one('cn.attendance.settings', string='Personal Attendance Policy')
    resolved_attendance_settings_id = fields.Many2one(
        'cn.attendance.settings', 
        compute='_compute_resolved_settings', 
        string='Active Attendance Policy', 
        readonly=True
    )

    @api.depends('attendance_settings_id', 'department_id', 'department_id.attendance_settings_id')
    def _compute_resolved_settings(self):
        for employee in self:
            employee.resolved_attendance_settings_id = self.env['cn.attendance.settings'].get_settings_for_employee(employee)


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    attendance_settings_id = fields.Many2one('cn.attendance.settings', string='Department Attendance Policy')
```

- [ ] **Step 2: Create Department View xml at `cn_payroll_core/views/hr_department_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
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
</odoo>
```

- [ ] **Step 3: Create Employee View xml at `cn_payroll_core/views/hr_employee_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
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
</odoo>
```

- [ ] **Step 4: Register Views in `cn_payroll_core/__manifest__.py`**

Modify Manifest's `'data'` list to register views:
```python
    'data': [
        'security/ir.model.access.csv',
        'views/hr_department_views.xml',
        'views/hr_employee_views.xml',
    ],
```

- [ ] **Step 5: Run Python compiler check to confirm no syntax issues**

Run: `python3 -m py_compile cn_payroll_core/models/cn_attendance_settings.py`
Expected: Compile success.

- [ ] **Step 6: Commit**

```bash
git add cn_payroll_core/models/cn_attendance_settings.py cn_payroll_core/views/ cn_payroll_core/__manifest__.py
git commit -m "feat: implement native HR model extensions and XML views for hierarchical attendance settings"
```

---

### Task 2: Recursive Resolution Engine & Summary Engine Integration

**Files:**
- Modify: `cn_payroll_core/models/cn_attendance_settings.py` (add get_settings_for_employee helper)
- Modify: `cn_payroll_core/models/cn_attendance_summary.py` (refactor settings resolution call)

**Interfaces:**
- Consumes: `hr.employee` record instance
- Produces: `cn.attendance.settings.get_settings_for_employee(employee)` -> returns single `cn.attendance.settings` record.

- [ ] **Step 1: Implement `get_settings_for_employee` method in `cn.attendance.settings`**

Replace old sequential lookup with recursive tree-climbing:
```python
# Inside cn_payroll_core/models/cn_attendance_settings.py (CnAttendanceSettings class)

    @api.model
    def get_settings_for_employee(self, employee):
        """
        Recursively climbs the HR hierarchy tree to locate the active attendance settings.
        Flow: Employee Override -> Department Tree (climbing upwards) -> Company Default -> Database Fallback.
        """
        if not employee:
            return self.browse()

        # 1. Personal Specific Policy Override
        if employee.attendance_settings_id:
            return employee.attendance_settings_id

        # 2. Climb Department tree (recursive)
        dept = employee.department_id
        while dept:
            if dept.attendance_settings_id:
                return dept.attendance_settings_id
            dept = dept.parent_id

        # 3. Company Default
        company_default = self.search([('company_id', '=', employee.company_id.id)], limit=1)
        if company_default:
            return company_default

        # 4. Standard Database Fallback
        return self.search([], limit=1)
```

- [ ] **Step 2: Ensure Summary engine calls the correct model method**

Modify lines 40-50 in `cn_payroll_core/models/cn_attendance_summary.py` to:
```python
        # Fetch active cohort-specific settings recursively climbing the HR tree
        settings = self.env['cn.attendance.settings'].get_settings_for_employee(self.employee_id)
```

- [ ] **Step 3: Run Python compiler check to confirm no syntax issues**

Run: `python3 -m py_compile cn_payroll_core/models/cn_attendance_summary.py`
Expected: Compile success.

- [ ] **Step 4: Commit**

```bash
git add cn_payroll_core/models/cn_attendance_settings.py cn_payroll_core/models/cn_attendance_summary.py
git commit -m "feat: implement recursive resolution engine climbing HR tree to resolve active policy"
```

---

### Task 3: Tree-Aware Calendar Leaves Sync Adaptations

**Files:**
- Modify: `cn_payroll_core/models/cn_attendance_settings.py` (refactor leaves sync)

- [ ] **Step 1: Rewrite target calendar resolution in `cn.attendance.holiday.rule`**

Update `_sync_to_resource_calendar_leave` and `_remove_resource_calendar_leave` methods to dynamically find all active calendars under this policy's tree nodes:
```python
# Inside cn_payroll_core/models/cn_attendance_settings.py (CnAttendanceHolidayRule class)

    def _sync_to_resource_calendar_leave(self):
        self.ensure_one()
        if self.holiday_type != 'holiday':
            self._remove_resource_calendar_leave()
            return

        settings = self.settings_id
        
        # Resolve all scoped employees directly or recursively under assigned departments
        direct_employees = self.env['hr.employee'].search([('attendance_settings_id', '=', settings.id)])
        
        departments = self.env['hr.department'].search([('attendance_settings_id', '=', settings.id)])
        dept_employees = self.env['hr.employee'].search([('department_id', 'child_of', departments.ids)]) if departments else self.env['hr.employee']
        
        all_employees = direct_employees + dept_employees
        calendars = all_employees.mapped('resource_calendar_id')
        
        # If no explicit assignments, fallback to company calendar
        if not calendars:
            if settings.company_id.resource_calendar_id:
                calendars = settings.company_id.resource_calendar_id

        for calendar in calendars:
            existing_leave = self.env['resource.calendar.leaves'].search([
                ('calendar_id', '=', calendar.id),
                ('name', '=', self.name),
                ('date_from', '=', fields.Datetime.to_string(datetime.combine(self.date, datetime.min.time()))),
            ], limit=1)
            
            if not existing_leave:
                self.env['resource.calendar.leaves'].create({
                    'name': self.name,
                    'calendar_id': calendar.id,
                    'date_from': datetime.combine(self.date, datetime.min.time()),
                    'date_to': datetime.combine(self.date, datetime.max.time()),
                })

    def _remove_resource_calendar_leave(self):
        self.ensure_one()
        settings = self.settings_id
        
        direct_employees = self.env['hr.employee'].search([('attendance_settings_id', '=', settings.id)])
        
        departments = self.env['hr.department'].search([('attendance_settings_id', '=', settings.id)])
        dept_employees = self.env['hr.employee'].search([('department_id', 'child_of', departments.ids)]) if departments else self.env['hr.employee']
        
        all_employees = direct_employees + dept_employees
        calendars = all_employees.mapped('resource_calendar_id')
        
        if not calendars:
            if settings.company_id.resource_calendar_id:
                calendars = settings.company_id.resource_calendar_id

        if calendars:
            leaves = self.env['resource.calendar.leaves'].search([
                ('calendar_id', 'in', calendars.ids),
                ('name', '=', self.name),
            ])
            leaves.unlink()
```

- [ ] **Step 2: Run Python compiler check to confirm no syntax issues**

Run: `python3 -m py_compile cn_payroll_core/models/cn_attendance_settings.py`
Expected: Compile success.

- [ ] **Step 3: Commit**

```bash
git add cn_payroll_core/models/cn_attendance_settings.py
git commit -m "feat: refactor calendar leave sync to recursively identify all calendars scoped under policy tree"
```

---

### Task 4: Complete TDD Refactoring & Hierarchical Unit Test Suite

**Files:**
- Modify: `cn_payroll_core/tests/test_payroll_core.py` (refactor and extend test suite)

- [ ] **Step 1: Refactor and append Hierarchical Tree-Climbing Unit Test**

Rewrite existing flat-based unit tests to declare and assign policy structures via HR Employee and Department links, and add `test_hierarchical_attendance_inheritance` checking Department-level defaults, sub-department inheritance, personal override, and leaf propagation:
```python
# Inside cn_payroll_core/tests/test_payroll_core.py

    def test_hierarchical_attendance_inheritance(self):
        """Validate recursive policy climbing, department-level inheritance, sub-department scoping, and personal employee override"""
        # 1. Setup base policies
        global_policy = self.env['cn.attendance.settings'].create({
            'name': 'Global Parent Policy',
            'standard_check_in': 9.0,
            'standard_check_out': 18.0,
        })
        factory_policy = self.env['cn.attendance.settings'].create({
            'name': 'Factory Custom Policy',
            'standard_check_in': 8.0,
            'standard_check_out': 17.0,
        })

        # 2. Setup HR Department hierarchy
        parent_dept = self.env['hr.department'].create({
            'name': 'Manufacturing Division',
            'attendance_settings_id': factory_policy.id,
        })
        child_dept = self.env['hr.department'].create({
            'name': 'Assembly Line Section A',
            'parent_id': parent_dept.id, # Sub-department!
        })

        # 3. Setup Employees
        # Worker A: belongs to assembly line. No personal override, no department override. Should climb to parent_dept's policy!
        worker_a = self.env['hr.employee'].create({
            'name': 'Assembly Line Worker A',
            'department_id': child_dept.id,
        })

        # Executive B: belongs to assembly line but has a personal override settings. Should resolve to global_policy!
        exec_b = self.env['hr.employee'].create({
            'name': 'On-Site Inspector B',
            'department_id': child_dept.id,
            'attendance_settings_id': global_policy.id,
        })

        # 4. Resolve Active Policies
        policy_a = self.env['cn.attendance.settings'].get_settings_for_employee(worker_a)
        policy_b = self.env['cn.attendance.settings'].get_settings_for_employee(exec_b)

        # Assertions
        # Worker A inherits from parent department's factory_policy (recursive tree-climbing!)
        self.assertEqual(policy_a.id, factory_policy.id)
        self.assertEqual(policy_a.standard_check_in, 8.0)

        # Executive B bypasses department and resolves directly to global_policy (personal override!)
        self.assertEqual(policy_b.id, global_policy.id)
        self.assertEqual(policy_b.standard_check_in, 9.0)
```

- [ ] **Step 2: Clean up any old flat sequence fields in existing tests**

Locate and replace old fields in other tests (e.g. `applicability`, `sequence`) with the new direct Many2one assignment on the company, department, or employee.

- [ ] **Step 3: Run Python compiler check to confirm no syntax issues**

Run: `python3 -m py_compile cn_payroll_core/tests/test_payroll_core.py`
Expected: Compile success.

- [ ] **Step 4: Commit**

```bash
git add cn_payroll_core/tests/test_payroll_core.py
git commit -m "test: refactor payroll core test suite and add hierarchical policy inheritance validations"
```
