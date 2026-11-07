from datetime import datetime

import pytest
from pydantic import ValidationError

from app.crawlers.normalized import DeadlineInput, NormalizedNotice, load_source_samples


def test_sample_set_has_at_least_ten_offline_synthetic_cases():
    samples = load_source_samples()
    assert len(samples) >= 10
    assert all(item.notice.sample_type == "synthetic" for item in samples)
    assert {item.case for item in samples} >= {
        "normal_datetime", "date_only", "unknown_deadline", "multiple_deadlines",
        "delayed_v2", "cross_edition", "cross_track", "different_school", "missing_entry",
    }


def test_date_only_sample_does_not_guess_time():
    sample = next(item for item in load_source_samples() if item.case == "date_only")
    deadline = sample.notice.deadlines[0]
    assert deadline.precision == "date"
    assert deadline.at is None
    assert deadline.on_date.isoformat() == "2027-04-01"


def test_unknown_deadline_sample_preserves_unknown():
    sample = next(item for item in load_source_samples() if item.case == "unknown_deadline")
    deadline = sample.notice.deadlines[0]
    assert deadline.precision == "unknown"
    assert deadline.at is None and deadline.on_date is None


def test_missing_major_is_not_filled():
    sample = next(item for item in load_source_samples() if item.case == "missing_major")
    assert sample.notice.allowed_majors == []
    assert sample.notice.grade_min is None


def test_naive_datetime_is_rejected():
    data = load_source_samples()[0].notice.model_dump(mode="json")
    data["deadlines"][0]["precision"] = "datetime"
    data["deadlines"][0]["at"] = "2027-03-15T18:00:00"
    data["deadlines"][0]["on_date"] = None
    with pytest.raises(ValidationError):
        NormalizedNotice.model_validate(data)


def test_http_url_is_rejected():
    data = load_source_samples()[0].notice.model_dump(mode="json")
    data["source_url"] = "http://example.org/notices/1"
    with pytest.raises(ValidationError):
        NormalizedNotice.model_validate(data)


def test_date_precision_cannot_include_datetime():
    data = load_source_samples()[0].notice.model_dump(mode="json")
    data["deadlines"][0]["precision"] = "date"
    data["deadlines"][0]["on_date"] = "2027-03-15"
    with pytest.raises(ValidationError):
        NormalizedNotice.model_validate(data)
