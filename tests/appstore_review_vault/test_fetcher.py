import pytest

from appstore_review_vault.fetcher import build_review_url, validate_fetch_params


def test_build_review_url_uses_apple_rss_json_endpoint():
    assert build_review_url("1477376905", "us", "mostrecent", 1) == (
        "https://itunes.apple.com/us/rss/customerreviews/page=1/id=1477376905/sortby=mostrecent/json"
    )


@pytest.mark.parametrize("country", ["us", "gb", "ca", "au"])
def test_validate_fetch_params_accepts_supported_countries(country):
    validate_fetch_params("1477376905", country, "mosthelpful", 10)


@pytest.mark.parametrize("country", ["de", "usa", ""])
def test_validate_fetch_params_rejects_unsupported_countries(country):
    with pytest.raises(ValueError):
        validate_fetch_params("1477376905", country, "mostrecent", 1)


@pytest.mark.parametrize("sort", ["oldest", "", "mostRecent"])
def test_validate_fetch_params_rejects_unsupported_sorts(sort):
    with pytest.raises(ValueError):
        validate_fetch_params("1477376905", "us", sort, 1)


@pytest.mark.parametrize("page", [0, 11])
def test_validate_fetch_params_rejects_pages_outside_rss_cap(page):
    with pytest.raises(ValueError):
        validate_fetch_params("1477376905", "us", "mostrecent", page)
