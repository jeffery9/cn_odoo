# Worker Qualifications & Compliance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement qualification check constraints for outsourced workers, extending contracts and employees, and updating the onboarding wizard and test suite.

**Architecture:** Add fields to `cn.outsourcing.contract`, extend `hr.employee` model, write active chronological age/experience constraints on `cn.outsourcing.assignment`, and write multi-column parsers inside the onboarding wizard.

**Tech Stack:** Odoo 17, Python.

**Spec:** `docs/mi_system/plans/2026-08-30-worker-qualifications-design.md`

## Global Constraints
*   **Think in Odoo:** Rely on Odoo database constraints, `@api.constrains`, and standard Active Record validation exceptions (`ValidationError`).

---

### Task 1: Model Extensions & Assignment Active Validation

**Files:**
- Modify: `cn_payroll_outsourcing/models/cn_outsourcing_contract.py`
- Modify: `cn_payroll_outsourcing/models/cn_outsourcing_assignment.py`

**Interfaces:**
- Produces: Age and experience columns on contract, constraints on assignment.

- [ ] **Step 1: Add Fields to `cn_outsourcing_contract.py`**
Append fields defining qualifications to `CnOutsourcingContract`:

```python
    age_min = fields.Integer(default=18, string='Min Age Required')
    age_max = fields.Integer(default=60, string='Max Age Allowed')
    required_experience_years = fields.Integer(default=0, string='Min Experience Years')
    required_skills = fields.Text(string='Required Skills')
```

- [ ] **Step 2: Extend `hr.employee` Model**
Add a new class or extend `hr.employee` in `cn_payroll_outsourcing/models/cn_outsourcing_contract.py` or a separate model file:

```python
class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    experience_years = fields.Integer(default=0, string='Experience Years')
    skills_description = fields.Text(string='Skills Description')
```

- [ ] **Step 3: Implement Active Validator on `cn_outsourcing_assignment.py`**
Add the `@api.constrains` to check birthday and experience levels on assignment save:

```python
    @api.constrains('employee_id', 'contract_id', 'date_start')
    def _check_worker_qualifications(self):
        from odoo.exceptions import ValidationError
        from datetime import date
        
        for rec in self:
            contract = rec.contract_id
            employee = rec.employee_id
            
            # 1. Validate Age if birthday is configured
            if employee.birthday:
                b_date = fields.Date.from_string(employee.birthday)
                ref_date = fields.Date.from_string(rec.date_start) or date.today()
                
                # Compute age
                age = ref_date.year - b_date.year - ((ref_date.month, ref_date.day) < (b_date.month, b_date.day))
                
                if age < contract.age_min:
                    raise ValidationError(
                        f"Compliance Error: Worker {employee.name} (Age: {age}) is under "
                        f"the minimum age requirement of {contract.age_min} defined in contract '{contract.name}'."
                    )
                if age > contract.age_max:
                    raise ValidationError(
                        f"Compliance Error: Worker {employee.name} (Age: {age}) exceeds "
                        f"the maximum age requirement of {contract.age_max} defined in contract '{contract.name}'."
                    )
                    
            # 2. Validate Experience
            if employee.experience_years < contract.required_experience_years:
                raise ValidationError(
                    f"Compliance Error: Worker {employee.name} has only {employee.experience_years} years of experience, "
                    f"which fails to meet the contract's minimum requirement of {contract.required_experience_years} years."
                )
```

- [ ] **Step 4: Syntax Check & Commit**
Run: `python3 -m py_compile cn_payroll_outsourcing/models/cn_outsourcing_contract.py cn_payroll_outsourcing/models/cn_outsourcing_assignment.py`
```bash
git add cn_payroll_outsourcing/
git commit -m "feat: implement worker entry qualifications and active compliance validation constraints"
```

---

### Task 2: Robust Multi-Column Bulk Onboarding Wizard

**Files:**
- Modify: `cn_payroll_outsourcing/models/cn_outsourcing_backfill_wizard.py`

**Interfaces:**
- Produces: Flexibly parsed multi-column rows (`Name,Barcode,Birthday,ExperienceYears`).

- [ ] **Step 1: Rewrite Onboarding Parse Logic**
Update `action_onboard_bulk()` inside `cn_payroll_outsourcing/models/cn_outsourcing_backfill_wizard.py` to parse optional qualification columns:

```python
    def action_onboard_bulk(self):
        self.ensure_one()
        lines = self.worker_raw_list.strip().split('\n')
        for line in lines:
            if not line:
                continue
            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 2:
                continue
            name, barcode = parts[0], parts[1]
            
            # Optional columns
            birthday = False
            experience_years = 0
            if len(parts) >= 3 and parts[2]:
                birthday = parts[2]
            if len(parts) >= 4 and parts[3]:
                try:
                    experience_years = int(parts[3])
                except ValueError:
                    pass
            
            # 1. Create Employee with qualifications
            employee = self.env['hr.employee'].create({
                'name': name,
                'barcode': barcode,
                'birthday': birthday,
                'experience_years': experience_years,
                'attendance_settings_id': self.attendance_settings_id.id if self.attendance_settings_id else False,
            })
            
            # 2. Register Assignment (this triggers the constrains checks atomically!)
            self.env['cn.outsourcing.assignment'].create({
                'contract_id': self.contract_id.id,
                'employee_id': employee.id,
                'date_start': self.date_start,
            })
```

- [ ] **Step 2: Syntax Check & Commit**
Run: `python3 -m py_compile cn_payroll_outsourcing/models/cn_outsourcing_backfill_wizard.py`
```bash
git add cn_payroll_outsourcing/
git commit -m "feat: support optional multi-column qualifications parsing in backfill onboarding wizard"
```

---

### Task 3: Unit Testing Worker Qualification Constraints

**Files:**
- Modify: `cn_payroll_outsourcing/tests/test_outsourcing.py`

- [ ] **Step 1: Add Qualification Unit Tests**
Append these tests to `TestOutsourcing`:

```python
    def test_worker_age_and_experience_compliance_constraints(self):
        """Verify that validation errors block assignment if worker doesn't meet requirements"""
        from odoo.exceptions import ValidationError
        
        contract = self.env['cn.outsourcing.contract'].create({
            'name': 'Strict Qualifications',
            'agency_id': self.agency.id,
            'contract_type': 'service_rate',
            'age_min': 18,
            'age_max': 45,
            'required_experience_years': 3,
        })
        
        # 1. Underage worker (Age 15)
        young_worker = self.env['hr.employee'].create({
            'name': 'Too Young',
            'birthday': '2011-03-01', # Age 15
            'experience_years': 4,
        })
        with self.assertRaises(ValidationError):
            self.env['cn.outsourcing.assignment'].create({
                'contract_id': contract.id,
                'employee_id': young_worker.id,
                'date_start': '2026-03-01',
            })
            
        # 2. Insufficient experience (has 1 year, requires 3)
        inexperienced_worker = self.env['hr.employee'].create({
            'name': 'No Experience',
            'birthday': '1995-03-01', # Age 31
            'experience_years': 1,
        })
        with self.assertRaises(ValidationError):
            self.env['cn.outsourcing.assignment'].create({
                'contract_id': contract.id,
                'employee_id': inexperienced_worker.id,
                'date_start': '2026-03-01',
            })
            
        # 3. Compliant worker (Age 26, 5 years experience)
        compliant_worker = self.env['hr.employee'].create({
            'name': 'Fully Qualified',
            'birthday': '2000-03-01',
            'experience_years': 5,
        })
        assignment = self.env['cn.outsourcing.assignment'].create({
            'contract_id': contract.id,
            'employee_id': compliant_worker.id,
            'date_start': '2026-03-01',
        })
        self.assertTrue(assignment)
```

- [ ] **Step 2: Syntax Check & Commit**
Run: `python3 -m py_compile cn_payroll_outsourcing/tests/test_outsourcing.py`
```bash
git add cn_payroll_outsourcing/tests/test_outsourcing.py
git commit -m "test: add TDD unit tests verifying worker qualification compliance checks"
```
