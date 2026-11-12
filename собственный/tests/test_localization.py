from localization import display_name


def test_known_chinese_labels_are_translated_to_russian():
    assert display_name("宝箱") == "Сундук"
    assert display_name("传送锚点") == "Точка телепортации"


def test_unknown_labels_are_preserved_without_corruption():
    assert display_name("Unmapped label") == "Unmapped label"


def test_embedded_known_label_is_translated():
    assert display_name("普通宝箱") == "Обычный сундук"
