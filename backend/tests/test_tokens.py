from app.security import generate_token


def test_generate_invite_token_prefix_and_uniqueness():
    t1 = generate_token("comp_")
    t2 = generate_token("comp_")

    assert t1.startswith("comp_")
    assert t2.startswith("comp_")
    assert t1 != t2
