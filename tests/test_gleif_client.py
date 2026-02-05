import responses
from lei_enricher.core import GleifClient, make_session

@responses.activate
def test_gleif_batch_lookup():
    url = "https://api.gleif.org/api/v1/lei-records?page[size]=2&filter[lei]=AAAABBBBCCCCDDDDEEEE,213800NZT1VX6PZ7BT53"
    responses.add(
        responses.GET,
        url,
        json={
            "data": [
                {"id": "213800NZT1VX6PZ7BT53",
                 "attributes": {"lei": "213800NZT1VX6PZ7BT53",
                                "entity": {"status": "ACTIVE"},
                                "registration": {"nextRenewalDate": "2026-09-29"}}}
            ]
        },
        status=200,
    )

    client = GleifClient(session=make_session(), throttle_s=0.0)
    out = client.lookup_batch(["AAAABBBBCCCCDDDDEEEE", "213800NZT1VX6PZ7BT53"])
    assert out["213800NZT1VX6PZ7BT53"].entity_status == "ACTIVE"