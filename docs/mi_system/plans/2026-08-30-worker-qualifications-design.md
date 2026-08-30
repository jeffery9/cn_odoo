# Specification: Worker Qualification & Compliance Auditing

## 1. Architectural Intent
To prevent operational liability, safe-operation accidents, and compliance violations under Chinese Labor Law, outsourcing agreements must enforce strict qualification standards for workers supplied by third-party agencies.

We will introduce a server-side automated **Compliance Validation Engine** that audit:
1.  **Age Limits (年龄门槛):** Audits minimum and maximum age (e.g., 18 to 55) to prevent underage labor (child labor is strictly illegal under PRC Labor Law) and senior-liability accidents.
2.  **Experience Threshold (从业经历/工龄):** Validates minimum years of experience.
3.  **Required Skills (技能要求):** Audits key operational certifications (e.g., forklift driving).

---

## 2. Model Extensions

### 2.1. `cn.outsourcing.contract` Extensions
*   Add parameters defining basic entry criteria:
    *   `age_min` (`Integer`, Default=18): Minimum age required.
    *   `age_max` (`Integer`, Default=60): Maximum age allowed.
    *   `required_experience_years` (`Integer`, Default=0): Minimum experience required.
    *   `required_skills` (`Text`): Text details of certifications or skills needed.

### 2.2. `hr.employee` Extensions
*   Add worker record fields inside `cn_payroll_outsourcing` to capture qualifications:
    *   `birthday` (Odoo standard `birthday` field is used).
    *   `experience_years` (`Integer`, Default=0): Years of actual experience.
    *   `skills_description` (`Text`): Certified skills and licenses description.

### 2.3. `cn.outsourcing.assignment` Constraints
*   Add a server-side active validator `@api.constrains('employee_id', 'contract_id')` to enforce criteria:
    1.  **Age Validation:** Computes the worker's age at the start date:
        $$\text{Age} = \text{Date Start}.\text{Year} - \text{Birthday}.\text{Year}$$
        *(with day precision adjustment)*. Raises `ValidationError` if the worker is too young or too old.
    2.  **Experience Validation:** Compares `experience_years` against `required_experience_years`. Raises `ValidationError` if years are insufficient.

---

## 3. Onboarding Wizard Integration
*   The `cn.outsourcing.backfill.wizard` is expanded to accept optional raw birthday and experience columns (e.g. `Name,Barcode,Birthday,ExperienceYears` as `Zhang San,9001,1995-05-20,3`) and automatically registers them, triggering the contract compliance constraint atomically on save.
