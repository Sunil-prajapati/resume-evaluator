from datetime import date

import pytest

from resume_evaluator.extractor import parse_date, total_years
from resume_evaluator.models import Job

TODAY = date(2026, 11, 11)


def job(start, end, title="Dev", company="Acme"):
    return Job(title=title, company=company, start=start, end=end)


def years(*jobs, today=TODAY):
    return total_years(list(jobs), today)


# ---------------------------------------------------------------- parse_date
@pytest.mark.parametrize(
    "value, is_end, expected",
    [
        ("2022-06", False, 2022 * 12 + 5),
        ("2022/6", False, 2022 * 12 + 5),
        ("2022", False, 2022 * 12 + 0),  # bare year start -> January
        ("2022", True, 2022 * 12 + 11),  # bare year end -> December
        ("Jun 2022", False, 2022 * 12 + 5),
        ("June 2022", False, 2022 * 12 + 5),
        ("sept. 2021", True, 2021 * 12 + 8),
        ("present", True, 2026 * 12 + 10),
        ("Present", True, 2026 * 12 + 10),
    ],
)
def test_parse_date_valid(value, is_end, expected):
    assert parse_date(value, is_end=is_end, today=TODAY) == expected


@pytest.mark.parametrize("value", [None, "", "soon", "2022-13", "2022-00", "13/2022", "present"])
def test_parse_date_invalid(value):
    # "present" is invalid as a *start* date
    assert parse_date(value, is_end=False, today=TODAY) is None


# ---------------------------------------------------------------- total_years
def test_single_job_inclusive_months():
    # Jan 2022 .. Dec 2022 inclusive = 12 months
    assert years(job("2022-01", "2022-12"))[0] == 1.0


def test_sequential_jobs_add_up():
    # 5 months (Jan-May 2022) + 12 months (Jan-Dec 2023) = 17 months = 1.4 years
    assert years(job("2022-01", "2022-05"), job("2023-01", "2023-12"))[0] == 1.4


def test_overlapping_jobs_not_double_counted():
    # Jan 2020-Dec 2021 (24 mo) overlaps Jul 2021-Jun 2022 -> union Jan 2020..Jun 2022 = 30 months
    assert years(job("2020-01", "2021-12"), job("2021-07", "2022-06"))[0] == 2.5


def test_job_fully_inside_another_adds_nothing():
    assert years(job("2020-01", "2022-12"), job("2021-03", "2021-09"))[0] == 3.0


def test_touching_jobs_merge_without_gap_or_overlap():
    # Jan-Jun 2020 then Jul-Dec 2020 = 12 months
    assert years(job("2020-01", "2020-06"), job("2020-07", "2020-12"))[0] == 1.0


def test_present_uses_today():
    # Jun 2022 .. Nov 2026 inclusive = 7 (2022) + 36 (2023-25) + 11 (2026) = 54 months = 4.5 years
    assert years(job("2022-06", "present"))[0] == 4.5


def test_year_only_dates():
    # 2020 .. 2021 = Jan 2020 .. Dec 2021 = 24 months
    assert years(job("2020", "2021"))[0] == 2.0


def test_text_month_dates():
    assert years(job("Jan 2022", "Dec 2022"))[0] == 1.0


def test_order_of_jobs_does_not_matter():
    a, b = job("2023-01", "2023-12"), job("2020-01", "2020-12")
    assert years(a, b) == years(b, a)


def test_unparseable_date_skipped_with_warning():
    total, warnings = years(job("sometime", "2021"), job("2022-01", "2022-12", company="Beta"))
    assert total == 1.0
    assert len(warnings) == 1 and "Acme" in warnings[0]


def test_missing_end_date_skipped_with_warning():
    total, warnings = years(job("2022-01", None))
    assert total == 0.0
    assert warnings


def test_end_before_start_skipped_with_warning():
    total, warnings = years(job("2022-06", "2021-01"))
    assert total == 0.0
    assert warnings


def test_future_end_date_clamped_to_today():
    # Jan 2026 .. (clamped) Nov 2026 = 11 months
    assert years(job("2026-01", "2027-12"))[0] == 0.9


def test_no_jobs():
    assert years() == (0.0, [])
