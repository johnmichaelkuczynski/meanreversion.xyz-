from unittest.mock import Mock, patch

import pytest

from trend_reversion_data import _history


def test_full_tiingo_adjusted_history():
    _history.clear()
    response = Mock(ok=True, status_code=200)
    response.json.return_value = [
        {"date": "1981-01-02T00:00:00Z", "close": 500, "adjClose": 1.25},
        {"date": "1981-01-05T00:00:00Z", "close": 600, "adjClose": 1.5},
    ]
    with patch.dict("os.environ", {"TIINGO_API_KEY": "test-only"}), patch(
            "trend_reversion_data.requests.get", return_value=response) as request:
        result = _history("MSFT", "2026-11-18")
    assert result["prices"] == [1.25, 1.5]
    assert result["dates"][0] == "1981-01-02"
    assert request.call_args.kwargs["params"]["startDate"] == "1800-01-01"
    assert result["source"] == "Tiingo"
    _history.clear()


def test_unknown_ticker_and_missing_adjusted_prices():
    _history.clear()
    with patch.dict("os.environ", {"TIINGO_API_KEY": "test-only"}), patch(
            "trend_reversion_data.requests.get", return_value=Mock(status_code=404)):
        with pytest.raises(ValueError, match="Unknown ticker"):
            _history("UNKNOWN", "2026-11-18")
    response = Mock(ok=True, status_code=200)
    response.json.return_value = [{"date": "2020-01-01", "close": 100}]
    with patch.dict("os.environ", {"TIINGO_API_KEY": "test-only"}), patch(
            "trend_reversion_data.requests.get", return_value=response):
        with pytest.raises(ValueError, match="Adjusted daily closes are unavailable"):
            _history("MSFT", "2026-11-18")
    _history.clear()
