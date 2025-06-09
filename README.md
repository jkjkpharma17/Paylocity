# OIG Screener

This project contains a small Python utility to screen active employees against the [OIG](https://oig.hhs.gov/) exclusion list. It downloads the most recent exclusion data, compares it to a local Excel file of employees, and generates a PDF report.

## Requirements

* Python 3.8+
* Packages: `pandas`, `requests`, `reportlab`, `python-dateutil`

Install the dependencies with:

```bash
pip install pandas requests reportlab python-dateutil
```

## Usage

Provide the path to the employee Excel file with `-e` or `--employee-file`:

```bash
python oig_screener.py -e path/to/ActiveEmployees.xlsx
```

If the argument is omitted, the script will prompt for the Excel path interactively.

After running, a PDF report is created in the `reports/` directory with a file name such as `HSPHARMOIG_MMDDYYYY.pdf`.

## Output

The PDF lists any active employee names found on the OIG exclusion list and includes the exclusion start and end dates when present. If no matches are found, the report states so explicitly.

## Notes

The script contacts `https://oig.hhs.gov/exclusions/downloadables/UPDATED.csv` to obtain the exclusion list. Ensure internet connectivity for the download step.
