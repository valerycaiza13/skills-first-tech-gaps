# Skills-First Tech Gaps (Demo)

This project demonstrates a skills-first approach to identify technical skill gaps in a Technology department.

The objective is to compare the technical skills required for each role with the actual skill levels of employees, detect gaps, and generate insights to support upskilling, reskilling, and talent decisions.

## Scope
- Area: Technology
- Focus: Technical skills
- Roles: Software, Data, QA, IT
- Approach: Skills-first (inspired by platforms such as 365Talents)

## Inputs
- Employees data (role, area, seniority)
- Required skills per role (skill, required level, importance)
- Actual skills per employee (current level)

## Outputs
- Gap per skill
- Gap per employee
- Gap per role and area
- Identification of critical skills at risk
- Upskilling and reskilling recommendations
- Aggregated indicators:
  - % of employees with technical gaps
  - Top roles with the highest gaps
  - Top 3 skills with the highest weighted gaps

## Tech Stack
- Python
- Pandas
- Streamlit

## How to run the app
```bash
pip install -r requirements.txt
streamlit run app.py
