#!/usr/bin/env python3
# -*- coding: utf-8 -*-


"""
oig_screener.py

Monthly OIG Exclusion Screening:
1. Downloads the latest OIG Exclusions CSV.
2. Prompts user for the active employee Excel file path.
3. Screens employees against OIG list.
4. Generates a timestamped PDF report (reports/HSPHARMOIG_MMDDYYYY.pdf).

Dependencies:
    pip install pandas requests reportlab python-dateutil
"""

import os
import sys
import io
import datetime
import requests
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import argparse

# ───–───[ CONFIGURATION ]───────────────────────────────────────────────────────

# URL of the OIG exclusions CSV
OIG_CSV_URL = "https://oig.hhs.gov/exclusions/downloadables/UPDATED.csv"
# Directory to save PDF reports
REPORTS_DIR = "reports"

# ───–───[ END CONFIGURATION ]───────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Screen active employees against the OIG Exclusion list and generate a PDF report."
    )
    parser.add_argument(
        "-e", "--employee-file",
        help="Path to the Excel file containing active employees. If omitted, you will be prompted."
    )
    return parser.parse_args()


def get_employee_excel_path(provided_path):
    """Return the Excel path: use provided argument or prompt the user."""
    if provided_path:
        return provided_path
    path = input("Enter path to your employee list Excel file: ").strip()
    return path


def download_oig_csv(url: str) -> pd.DataFrame:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text), dtype=str, low_memory=False)
    df.columns = [col.strip().upper() for col in df.columns]
    return df


def load_employee_list(excel_path: str) -> pd.DataFrame:
    if not os.path.isfile(excel_path):
        print(f"ERROR: Cannot find file at '{excel_path}'. Exiting.", file=sys.stderr)
        sys.exit(1)

    df = pd.read_excel(excel_path, dtype=str)
    # Handle sample with "Unnamed: 1" & "Unnamed: 2"
    if "Unnamed: 2" in df.columns and "Unnamed: 1" in df.columns:
        df = df[df["Unnamed: 2"].notna()].reset_index(drop=True)
        df = df.iloc[1:].reset_index(drop=True)
        df = df.rename(columns={"Unnamed: 1": "ID", "Unnamed: 2": "EMPLOYEE"})
    else:
        df = df.rename(columns=lambda c: c.strip())

    df = df[["ID", "EMPLOYEE"]].copy()

    def parse_last(name_str: str) -> str:
        parts = name_str.split(",", 1)
        return parts[0].strip().upper() if parts else ""

    def parse_first(name_str: str) -> str:
        parts = name_str.split(",", 1)
        if len(parts) < 2:
            return ""
        first_part = parts[1].strip().split()
        return first_part[0].strip().upper() if first_part else ""

    df["LAST_NAME"] = df["EMPLOYEE"].apply(parse_last)
    df["FIRST_NAME"] = df["EMPLOYEE"].apply(parse_first)
    return df


def find_name_columns(oig_df: pd.DataFrame):
    cols = oig_df.columns
    first_cols = [c for c in cols if "FIRST" in c]
    last_cols = [c for c in cols if "LAST" in c]
    date_cols = [c for c in cols if "DATE" in c]

    if not first_cols or not last_cols:
        raise Exception("Could not identify FIRST_NAME or LAST_NAME columns in OIG CSV.")

    first_col = first_cols[0]
    last_col = last_cols[0]
    start_date_col = next((c for c in date_cols if any(w in c for w in ("START","EFFECT"))), None)
    end_date_col = next((c for c in date_cols if any(w in c for w in ("END","REINSTATEMENT"))), None)
    if not start_date_col and date_cols:
        start_date_col = date_cols[0]
    if not end_date_col and len(date_cols) > 1:
        end_date_col = date_cols[1]

    return first_col, last_col, start_date_col, end_date_col


def screen_against_oig(emp_df: pd.DataFrame, oig_df: pd.DataFrame) -> pd.DataFrame:
    first_col, last_col, start_col, end_col = find_name_columns(oig_df)
    oig_df["OIG_FIRST_UP"] = oig_df[first_col].fillna("").str.upper().str.strip()
    oig_df["OIG_LAST_UP"] = oig_df[last_col].fillna("").str.upper().str.strip()
    subset = ["OIG_LAST_UP","OIG_FIRST_UP"]
    if start_col:
        oig_df["OIG_START_DATE"] = oig_df[start_col]
        subset.append("OIG_START_DATE")
    if end_col:
        oig_df["OIG_END_DATE"] = oig_df[end_col]
        subset.append("OIG_END_DATE")
    oig_subset = oig_df[subset].drop_duplicates(subset=["OIG_LAST_UP","OIG_FIRST_UP"])

    emp_df["EMP_LAST_UP"] = emp_df["LAST_NAME"].str.upper().str.strip()
    emp_df["EMP_FIRST_UP"] = emp_df["FIRST_NAME"].str.upper().str.strip()

    merged = pd.merge(
        emp_df,
        oig_subset,
        left_on=["EMP_LAST_UP","EMP_FIRST_UP"],
        right_on=["OIG_LAST_UP","OIG_FIRST_UP"],
        how="inner"
    )
    return merged


def make_pdf_report(merged_df: pd.DataFrame, output_path: str):
    today = datetime.datetime.now().strftime("%B %d, %Y")
    title = f"H&S Pharmacies LLC\nOIG Exclusion Screening Report\nDate: {today}"
    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter

    text = c.beginText(40, height - 60)
    text.setFont("Helvetica-Bold", 14)
    for line in title.split("\n"):
        text.textLine(line)
    text.moveCursor(0, 20)
    c.drawText(text)

    if merged_df.empty:
        t2 = c.beginText(40, height - 140)
        t2.setFont("Helvetica", 12)
        t2.textLine("No exclusions found for any active employee this month.")
        c.drawText(t2)
    else:
        t2 = c.beginText(40, height - 140)
        t2.setFont("Helvetica-Bold", 12)
        header = f"{'ID':<8} {'EMPLOYEE NAME':<30} {'EXCL START':<12} {'EXCL END':<12}"
        t2.textLine(header)
        t2.moveCursor(0, 8)
        t2.setFont("Helvetica", 11)

        lines_per_page = 45
        count = 0
        for _, row in merged_df.iterrows():
            emp_id = row["ID"]
            emp_name = row["EMPLOYEE"]
            start = row.get("OIG_START_DATE","") or ""
            end = row.get("OIG_END_DATE","") or ""
            line = f"{emp_id:<8} {emp_name:<30} {start:<12} {end:<12}"
            t2.textLine(line)
            count += 1
            if count >= lines_per_page:
                c.drawText(t2)
                c.showPage()
                t2 = c.beginText(40, height - 40)
                t2.setFont("Helvetica", 11)
                count = 0
        c.drawText(t2)

    c.save()
    print(f"PDF report saved to '{output_path}'")


def main():
    args = parse_args()
    emp_file = get_employee_excel_path(args.employee_file)

    os.makedirs(REPORTS_DIR, exist_ok=True)
    oig_df = download_oig_csv(OIG_CSV_URL)
    emp_df = load_employee_list(emp_file)
    merged = screen_against_oig(emp_df, oig_df)

    date_str = datetime.datetime.now().strftime("%m%d%Y")
    output_pdf = os.path.join(REPORTS_DIR, f"HSPHARMOIG_{date_str}.pdf")
    make_pdf_report(merged, output_pdf)

if __name__ == "__main__":
    main()
