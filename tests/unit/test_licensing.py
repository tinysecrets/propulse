# SPDX-License-Identifier: AGPL-3.0-or-later
from propulse_core.licensing import (
    COMMERCIAL_TIERS,
    SourceDisclosure,
    agreement_text,
    is_signed_commercial,
    license_id_for,
    mint_commercial_key,
    source_fingerprint,
)

SECRET = "license-secret"


def test_disclosure_declares_agpl():
    d = SourceDisclosure().to_dict()
    assert d["license"] == "AGPL-3.0-or-later"
    assert d["repo"].startswith("https://github.com/")
    assert "modifications" in d["notices"]


def test_two_tiers_at_expected_prices():
    assert {t["price_usd"] for t in COMMERCIAL_TIERS.values()} == {15000, 25000}


def test_key_roundtrip_verifies():
    key = mint_commercial_key("single", 9999999999, SECRET)
    assert is_signed_commercial(key, secret=SECRET)


def test_tampered_key_fails():
    key = mint_commercial_key("single", 9999999999, SECRET)
    assert not is_signed_commercial(key[:-1] + "0", secret=SECRET)


def test_wrong_secret_fails():
    key = mint_commercial_key("unlimited", 9999999999, SECRET)
    assert not is_signed_commercial(key, secret="other")


def test_unknown_tier_rejected():
    assert not is_signed_commercial("PP-C-GOLD-999-abcdefgh", secret=SECRET)


def test_agreement_mentions_parties_and_scope():
    text = agreement_text(
        tier="unlimited",
        licensee="Acme",
        email="a@acme.com",
        license_key="PP-C-UNLIMITED-1-x",
        issued_at=0,
    )
    assert "Acme" in text
    assert "Unlimited" in text
    assert "AGPL-3.0 section 13" in text


def test_license_id_is_deterministic():
    assert license_id_for("cs_test_1") == license_id_for("cs_test_1")
    assert license_id_for("a") != license_id_for("b")


def test_fingerprint_is_stable():
    assert source_fingerprint() == source_fingerprint()
