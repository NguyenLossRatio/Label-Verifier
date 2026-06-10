from app.extraction import extract_field_guesses


def test_extract_field_guesses_finds_common_label_values():
    raw_text = """
    OLD TOM DISTILLERY
    Kentucky Straight Bourbon Whiskey
    45% Alc./Vol. (90 Proof)
    750 mL
    Bottled by Old Tom Distillery, Louisville, KY
    """

    guesses = extract_field_guesses(raw_text)

    assert guesses["alcohol_content"] == "45% Alc./Vol. (90 Proof)"
    assert guesses["net_contents"] == "750 mL"
    assert guesses["bottler_address"] == "Bottled by Old Tom Distillery, Louisville, KY"


def test_extract_field_guesses_returns_empty_strings_when_unknown():
    guesses = extract_field_guesses("Decorative label text only")

    assert guesses["alcohol_content"] == ""
    assert guesses["net_contents"] == ""
    assert guesses["bottler_address"] == ""
