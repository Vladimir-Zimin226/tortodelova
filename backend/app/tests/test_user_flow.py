def test_profile_balance_deposit_and_transactions(client, auth_headers):
    # profile
    prof = client.get("/api/me/profile", headers=auth_headers)
    assert prof.status_code == 200
    assert prof.json()["email"].endswith("@example.com")

    # initial balance
    bal = client.get("/api/me/balance", headers=auth_headers)
    assert bal.status_code == 200
    assert bal.json()["balance_credits"] == 0

    # deposit
    dep = client.post("/api/me/balance/deposit", headers=auth_headers, json={"amount": 10, "description": "Top up"})
    assert dep.status_code == 200, dep.text
    assert dep.json()["balance_credits"] == 10

    # tx history
    txs = client.get("/api/me/transactions?limit=100&offset=0", headers=auth_headers)
    assert txs.status_code == 200
    data = txs.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["type"] == "credit"
    assert data[0]["amount"] == 10
