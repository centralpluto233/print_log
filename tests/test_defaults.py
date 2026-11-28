from pl.defaults import DEFAULT_NOTIFICATIONS, TEXTS


def test_texts_have_the_same_keys_in_every_language():
    assert set(TEXTS["nl"]) == set(TEXTS["en"])


def test_every_notification_text_setting_has_a_default_text():
    keys = [k for k in DEFAULT_NOTIFICATIONS if k.endswith(("_title", "_message"))]
    assert "low_stock_title" in keys and "low_stock_message" in keys
    for lang in TEXTS.values():
        assert all(k in lang for k in keys)


def test_low_stock_notification_is_on_by_default_and_switchable():
    assert DEFAULT_NOTIFICATIONS["on_low_stock"] is True
