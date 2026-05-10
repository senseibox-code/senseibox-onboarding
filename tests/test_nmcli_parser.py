from senseibox_onboarding.services.network import _split_nmcli_row


def test_split_nmcli_row_handles_escaped_colon() -> None:
    assert _split_nmcli_row(r"My\:Wifi:aa\:bb:80:WPA2:") == [
        "My:Wifi",
        "aa:bb",
        "80",
        "WPA2",
        "",
    ]
