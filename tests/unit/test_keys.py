# SPDX-License-Identifier: AGPL-3.0-or-later
import pytest
from propulse_core.security.keys import (
    PUBLIC_PREFIX,
    SECRET_PREFIX,
    hash_lookup_token,
    mint_key,
    parse_key,
    scopes_for,
    verify_key,
)


def test_public_key_roundtrip():
    minted = mint_key("pub", "live")
    assert minted.plaintext.startswith(PUBLIC_PREFIX)
    parsed = parse_key(minted.plaintext)
    assert parsed.key_id == minted.key_id
    assert parsed.kind == "pub"
    assert verify_key(minted.plaintext, minted.digest, "pub")


def test_secret_key_uses_argon2id():
    minted = mint_key("sec", "live")
    assert minted.plaintext.startswith(SECRET_PREFIX)
    assert minted.digest.startswith("$argon2id$")
    assert verify_key(minted.plaintext, minted.digest, "sec")


def test_wrong_key_fails():
    a, b = mint_key("pub"), mint_key("pub")
    assert not verify_key(a.plaintext, b.digest, "pub")


def test_key_ids_are_unique():
    assert len({mint_key("pub").key_id for _ in range(200)}) == 200


def test_key_id_is_lowercase_crockford():
    kid = mint_key("pub").key_id
    assert kid == kid.lower()
    assert not (set(kid) & set("ilou"))


def test_public_scopes_are_a_strict_subset():
    assert scopes_for("pub") < scopes_for("sec")


def test_unknown_scope_is_dropped():
    assert "billing:read" not in scopes_for("pub", ["billing:read", "made:up"])


def test_malformed_key_raises():
    with pytest.raises(ValueError, match="unknown key prefix"):
        parse_key("nope")
    with pytest.raises(ValueError, match="malformed key"):
        parse_key("pp_pub_live_onlythree")


def test_lookup_token_is_stable():
    k = mint_key("pub")
    assert hash_lookup_token(k.plaintext) == hash_lookup_token(k.plaintext)
