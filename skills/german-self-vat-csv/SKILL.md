---
name: german-self-vat-csv
description: Use when the user asks to modify an Amazon VAT CSV so German seller-paid self VAT is kept around a target euro amount, especially requests like "改到自缴税100欧左右", "德国自缴税80欧", or "GG-原文件名".
---

# German Self VAT CSV

Use this skill when the user provides an Amazon VAT transaction CSV and asks to adjust it to a target German seller-paid VAT amount.

## Default Rule

Ask for the missing file or target amount only if it is not available from the user message.

Target amount means the remaining German seller-paid VAT amount recalculated the same way as the VAT reporting system:

Platform estimated net sales multiplied by `19%`.

Platform estimated net sales for each eligible row:

- Use `TOTAL_ACTIVITY_VALUE_AMT_VAT_EXCL` when it is non-zero.
- If `TOTAL_ACTIVITY_VALUE_AMT_VAT_EXCL` is blank or zero, use `TOTAL_ACTIVITY_VALUE_AMT_VAT_INCL - TOTAL_ACTIVITY_VALUE_VAT_AMT`.

Do not use `TOTAL_ACTIVITY_VALUE_VAT_AMT` as the selection target. Keep it only as a cross-check in the final summary.

Eligible rows are positive sales rows matching all of:

- `DEPARTURE_COUNTRY = DE`
- `ARRIVAL_COUNTRY = DE`
- `SALE_DEPART_COUNTRY = DE`
- `SALE_ARRIVAL_COUNTRY = DE`
- `TAXABLE_JURISDICTION = GERMANY`
- `TAX_REPORTING_SCHEME = REGULAR`
- `TAX_COLLECTION_RESPONSIBILITY = SELLER`
- `SALE_ARRIVAL_COUNTRY = DE` or `ARRIVAL_COUNTRY = DE`
- `TRANSACTION_TYPE` is `SALE` or `LIQUIDATION_SALE`
- platform estimated net sales is positive

All non-eligible rows must be preserved. Delete only the eligible rows not selected for the target. Preserve the original column order and row order for the rows that remain.

## Output Naming

The output CSV name must be:

`GG-` + original filename

Save the output CSV in the same folder as the input CSV unless the user explicitly asks for another destination.

## Script

Use the bundled script:

`scripts/adjust_german_self_vat_csv.py`

Example:

```powershell
& <python> scripts/adjust_german_self_vat_csv.py --input "C:\path\file.csv" --target-vat 100
```

The script prints a compact summary with original rows, output rows, removed rows, target net sales, kept platform estimated net sales, recalculated VAT, CSV VAT cross-check, and output path.

## Final Response

Report:

- output file link
- original row count
- modified row count
- removed eligible row count
- original calculated VAT
- kept calculated VAT
- kept platform estimated net sales
- kept eligible gross amount
