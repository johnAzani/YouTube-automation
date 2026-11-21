"""Read existing channel snapshots for YPP planning; make no network requests."""
import argparse
from datetime import date
import math

from scripts import analytics_reader as reader
from scripts.view_analytics import format_table


COVERAGE = {
    "subscribers": "subscriber count (public)",
    "watch_hours": "watch time by kind of video, 365 days",
    "shorts_views_90d": "views by kind of video, 90 days",
}


def snapshot_values(report):
    coverage = report.get("coverage", {})
    program = report.get("partner_program", {})
    values = {}
    for key, label in COVERAGE.items():
        status = coverage.get(label, "")
        value = program.get("watch_hours_counted" if key == "watch_hours" else key)
        available = status == "read" if key == "subscribers" else bool(status.endswith((" row", " rows")))
        values[key] = value if available and type(value) in (int, float) and math.isfinite(value) and value >= 0 else None
    return values


def gaps(values, targets):
    return {key: None if values.get(key) is None else max(0, target - values[key])
            for key, target in targets.items()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today(),
                        help="select eligibility targets for this date, not the snapshot date")
    args = parser.parse_args(argv)
    targets = reader.needs(args.as_of)
    reports = reader.load_reports()
    print(f"Planning on {args.as_of}. These are Analytics-based gaps, not verified Earn eligibility.")
    print("The subscriber requirement applies to both routes; either watch hours or qualified Shorts views can satisfy the viewing requirement.")
    for name, tier in (("Ads and Premium (new applicants)", targets), ("Earlier fan funding", reader.EARLY_NEEDS)):
        rows = []
        for channel in reader.CHANNELS:
            report = reports.get(channel, {})
            window = report.get("windows", {}).get("year", [])
            gap = gaps(snapshot_values(report), tier)
            cells = ["—" if v is None else f"{v:,.2f}" if k == "watch_hours" else f"{v:,.0f}"
                     for k, v in gap.items()]
            rows.append([channel, window[-1] if window else "No snapshot", *cells])
        print(f"\n{name}")
        print(format_table(["Channel", "Data through", "Subs gap", "Long/live h gap", "Shorts views gap"], rows))
    print("— means unknown. Analytics totals can include activity that does not qualify; verify every channel in Studio → Earn.")
    print("Shorts-feed watch time does not count toward the long-form hour route. No earnings or approval date is predicted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
