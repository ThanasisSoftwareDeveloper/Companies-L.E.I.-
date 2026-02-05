from lei_enricher.core import normalize_lei, is_valid_lei, parse_gleif_item

def test_normalize():
    assert normalize_lei(" 213800NZT1VX6PZ7BT53 ") == "213800NZT1VX6PZ7BT53"

def test_valid():
    assert is_valid_lei("213800NZT1VX6PZ7BT53") is True
    assert is_valid_lei("123") is False

def test_parse_gleif_item():
    item = {
        "id": "213800NZT1VX6PZ7BT53",
        "attributes": {
            "lei": "213800NZT1VX6PZ7BT53",
            "entity": {"status": "ACTIVE"},
            "registration": {"nextRenewalDate": "2026-09-29"},
        }
    }
    lei, res = parse_gleif_item(item)
    assert lei == "213800NZT1VX6PZ7BT53"
    assert res.entity_status == "ACTIVE"
    assert res.next_renewal_date == "2026-09-29"
    