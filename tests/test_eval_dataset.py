from eval.load_dataset import load_dataset


def test_dataset_has_at_least_20_items():
    items = load_dataset()
    assert len(items) >= 20


def test_refuse_items_present():
    items = load_dataset()
    refuse = [i for i in items if i.expected_behavior == "refuse"]
    assert len(refuse) >= 3
