"""Registry helpers, incl. the Gmail-labeling surfaced-emails query."""
import json

from pipeline import processed


def test_message_id_from_link_both_forms():
    assert processed._message_id_from_link(
        "https://mail.google.com/mail/u/0/#all/19f664850eeaf0fa") == "19f664850eeaf0fa"
    assert processed._message_id_from_link(
        "https://mail.google.com/mail/u/0/#search/rfc822msgid:abc@geopod-90") == "abc@geopod-90"
    assert processed._message_id_from_link("") == ""


def test_surfaced_message_ids(tmp_path):
    deals = {"deals": [
        {"verdict": "PASS",       "email_link": ".../#all/aaa"},
        {"verdict": "BORDERLINE", "email_link": ".../#all/bbb"},
        {"verdict": "FAIL",       "email_link": ".../#all/ccc"},
        {"verdict": "KILLED",     "email_link": ".../#all/ddd"},
        # A second deal from email bbb that failed — bbb still surfaced via the borderline one
        {"verdict": "FAIL",       "email_link": ".../#all/bbb"},
        {"verdict": "PASS",       "email_link": ".../#search/rfc822msgid:eee@x"},
    ]}
    p = tmp_path / "deals.json"
    p.write_text(json.dumps(deals))
    assert processed.surfaced_message_ids(p) == {"aaa", "bbb", "eee@x"}


def test_surfaced_message_ids_missing_file(tmp_path):
    assert processed.surfaced_message_ids(tmp_path / "nope.json") == set()
