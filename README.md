# Monthly MOH Reporting Pipeline

Python automation for preparing monthly transplant outpatient reporting data from five Excel sources.

Developed independently in 2024 to replace repetitive manual cleaning, registry lookups, and reporting classifications performed by quality coordinators.

## Operational results

- Manual preparation required approximately **12–15 cumulative staff-hours per month**.
- The automated workflow using this pipeline completed processing in **under 30 seconds**, timed from loading the files through exporting the workbook.
- Automated output matched manual preparation across **two validation cycles**.
- The pipeline has supported recurring monthly reporting since 2024. Coordinators review the output, particularly records flagged for human assessment, before submission.

These results describe the original operational workflow. Human review remains a separate step.

## Inputs

| Excel source | Purpose |
|---|---|
| Monthly outpatient visits | Main visit dataset |
| Liver registry | Liver recipient/donor information |
| Kidney recipient registry | Kidney recipient information |
| Kidney donor registry | Kidney donor information |
| Historical outpatient visits | Reference for new versus follow-up classification |

## Processing

The pipeline:

- Removes no-show visits and applies reporting exclusions.
- Links outpatient visits to transplant registries using medical record numbers.
- Derives recipient/donor, patient, age-group, and clinic classifications.
- Standardizes visit types using historical visit references.
- Corrects repeated “NEW” labels within eligible patient–clinic groups.
- Flags records requiring human review.
- Exports a standardized Excel workbook for review before submission.

## Usage

Requires Python with pandas, NumPy, and openpyxl:

```bash
pip install pandas numpy openpyxl
```

Run the pipeline:

```bash
python moh_reporting_pipeline.py \
  --opd outpatient_visits.xlsx \
  --liver liver_registry.xlsx \
  --kidney-recipient kidney_recipients.xlsx \
  --kidney-donor kidney_donors.xlsx \
  --history historical_visits.xlsx \
  --output output/cleaned_monthly_report.xlsx
```

The input workbooks must follow the column names and structure expected by the script.

### Application integration

The processing function accepts five Excel paths or file-like objects, including files uploaded through a Streamlit interface:

```python
from moh_reporting_pipeline import prepare_report

report = prepare_report(
    opd_file,
    liver_file,
    kidney_recipient_file,
    kidney_donor_file,
    historical_visits_file,
)

report.to_excel("cleaned_monthly_report.xlsx", index=False)
```

This repository contains the Python processing component.

## Data privacy

Patient datasets, source workbooks, reporting outputs, and original notebook outputs are excluded from this public repository.

