import argparse
import csv
import json
import os
from decimal import Decimal, ROUND_HALF_UP


def decimal_money(value):
    try:
        return Decimal(str(value or "0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.00")


def cents(value):
    return int((decimal_money(value) * 100).to_integral_value(rounding=ROUND_HALF_UP))


def money(value_cents):
    return str((Decimal(value_cents) / Decimal(100)).quantize(Decimal("0.01")))


def rate_decimal(value):
    try:
        return Decimal(str(value)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.1900")


def calculated_tax_cents(net_cents, tax_rate):
    tax = (Decimal(net_cents) / Decimal(100)) * tax_rate
    return int((tax * 100).to_integral_value(rounding=ROUND_HALF_UP))


def row_net_cents(row):
    net = cents(row.get("TOTAL_ACTIVITY_VALUE_AMT_VAT_EXCL"))
    if net != 0:
        return net
    return cents(row.get("TOTAL_ACTIVITY_VALUE_AMT_VAT_INCL")) - cents(row.get("TOTAL_ACTIVITY_VALUE_VAT_AMT"))


def is_eligible(row):
    return (
        row.get("TAX_REPORTING_SCHEME") == "REGULAR"
        and row.get("TAX_COLLECTION_RESPONSIBILITY") == "SELLER"
        and (row.get("SALE_ARRIVAL_COUNTRY") == "DE" or row.get("ARRIVAL_COUNTRY") == "DE")
        and row.get("TRANSACTION_TYPE") in ("SALE", "LIQUIDATION_SALE")
        and row_net_cents(row) > 0
    )


def choose_rows(items, target_net_cents):
    if target_net_cents <= 0:
        return set(), 0

    total = sum(item["net_cents"] for item in items)
    if total <= target_net_cents:
        return {item["index"] for item in items}, total

    largest_item = max((item["net_cents"] for item in items), default=0)
    search_limit = target_net_cents + largest_item

    # Subset-sum over euro cents. Tie-breaks prefer not exceeding target, then keeping more rows.
    dp = {0: (0, [])}
    for item in items:
        for current, (count, chosen) in list(dp.items()):
            new_total = current + item["net_cents"]
            if new_total > search_limit:
                continue
            new_count = count + 1
            if new_total not in dp or new_count > dp[new_total][0]:
                dp[new_total] = (new_count, chosen + [item["index"]])

    def rank(total_net_cents):
        return (
            abs(total_net_cents - target_net_cents),
            0 if total_net_cents <= target_net_cents else 1,
            -dp[total_net_cents][0],
        )

    best = min(dp.keys(), key=rank)
    return set(dp[best][1]), best


def adjust_csv(input_path, target_vat, output_dir=None, output_path=None, tax_rate="0.19"):
    tax_rate = rate_decimal(tax_rate)
    with open(input_path, newline="", encoding="utf-8-sig", errors="replace") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = reader.fieldnames

    if not fieldnames:
        raise ValueError("CSV has no header row.")

    items = []
    for index, row in enumerate(rows):
        if is_eligible(row):
            items.append(
                {
                    "index": index,
                    "net_cents": row_net_cents(row),
                    "vat_cents": cents(row.get("TOTAL_ACTIVITY_VALUE_VAT_AMT")),
                    "gross_cents": cents(row.get("TOTAL_ACTIVITY_VALUE_AMT_VAT_INCL")),
                }
            )

    target_cents = cents(target_vat)
    target_net_cents = int(((Decimal(target_cents) / Decimal(100)) / tax_rate * 100).to_integral_value(rounding=ROUND_HALF_UP))
    keep_indices, kept_net = choose_rows(items, target_net_cents)
    eligible_indices = {item["index"] for item in items}
    remove_indices = eligible_indices - keep_indices
    output_rows = [row for index, row in enumerate(rows) if index not in remove_indices]

    if output_path is None:
        output_dir = output_dir or os.path.dirname(os.path.abspath(input_path))
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "GG-" + os.path.basename(input_path))
    else:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)

    original_vat = sum(item["vat_cents"] for item in items)
    original_net = sum(item["net_cents"] for item in items)
    original_gross = sum(item["gross_cents"] for item in items)
    kept_vat = sum(item["vat_cents"] for item in items if item["index"] in keep_indices)
    kept_gross = sum(item["gross_cents"] for item in items if item["index"] in keep_indices)
    removed_net = sum(item["net_cents"] for item in items if item["index"] in remove_indices)
    removed_vat = sum(item["vat_cents"] for item in items if item["index"] in remove_indices)
    removed_gross = sum(item["gross_cents"] for item in items if item["index"] in remove_indices)
    original_calculated_vat = calculated_tax_cents(original_net, tax_rate)
    kept_calculated_vat = calculated_tax_cents(kept_net, tax_rate)
    removed_calculated_vat = calculated_tax_cents(removed_net, tax_rate)

    return {
        "output_path": output_path,
        "input_rows": len(rows),
        "output_rows": len(output_rows),
        "eligible_rows": len(items),
        "kept_eligible_rows": len(keep_indices),
        "removed_eligible_rows": len(remove_indices),
        "target_vat": money(target_cents),
        "tax_rate": str(tax_rate),
        "target_net_sales": money(target_net_cents),
        "original_platform_estimated_net_sales": money(original_net),
        "kept_platform_estimated_net_sales": money(kept_net),
        "removed_platform_estimated_net_sales": money(removed_net),
        "original_calculated_vat": money(original_calculated_vat),
        "kept_calculated_vat": money(kept_calculated_vat),
        "removed_calculated_vat": money(removed_calculated_vat),
        "original_csv_vat": money(original_vat),
        "kept_csv_vat": money(kept_vat),
        "removed_csv_vat": money(removed_vat),
        "original_eligible_gross": money(original_gross),
        "kept_eligible_gross": money(kept_gross),
        "removed_eligible_gross": money(removed_gross),
    }


def main():
    parser = argparse.ArgumentParser(description="Adjust German seller-paid VAT rows in an Amazon VAT CSV.")
    parser.add_argument("--input", required=True, help="Input CSV path.")
    parser.add_argument("--target-vat", required=True, help="Target remaining VAT amount in euros, calculated as net sales times tax rate.")
    parser.add_argument("--tax-rate", default="0.19", help="Tax rate used to recalculate VAT from net sales. Default: 0.19.")
    parser.add_argument("--output-dir", help="Directory for GG-prefixed output file.")
    parser.add_argument("--output", help="Exact output CSV path. Overrides --output-dir.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON summary.")
    args = parser.parse_args()

    summary = adjust_csv(args.input, args.target_vat, output_dir=args.output_dir, output_path=args.output, tax_rate=args.tax_rate)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        for key, value in summary.items():
            print(f"{key}: {value}")


if __name__ == "__main__":
    main()
