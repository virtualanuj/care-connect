from app.adapters.argon2_hasher import Argon2PasswordHasher


def test_hash_verifies_only_the_original_password() -> None:
    hasher = Argon2PasswordHasher()

    stored = hasher.hash("correct horse battery")

    assert stored != "correct horse battery"
    assert stored.startswith("$argon2")
    assert hasher.verify("correct horse battery", stored)
    assert not hasher.verify("wrong horse battery", stored)


def test_same_password_hashes_differently_each_time() -> None:
    hasher = Argon2PasswordHasher()

    assert hasher.hash("correct horse battery") != hasher.hash("correct horse battery")


def test_malformed_stored_hash_fails_verification_instead_of_raising() -> None:
    assert not Argon2PasswordHasher().verify("anything", "not-a-hash")
