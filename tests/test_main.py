import pytest

from src.main import main


@pytest.fixture
def tmp_db(tmp_path):
    return tmp_path / "prices.db"


@pytest.fixture
def products_yaml(tmp_path):
    yaml_path = tmp_path / "products.yaml"
    yaml_path.write_text("""
baseline:
  date: "2026-02-24"
  notes: test

products:
  - key: cpu
    label: "Test CPU"
    quantity: 1
    baseline_price: 6490
    match_all: ["AMD", "R7 7700 MPK"]
    exclude: []

  - key: ssd
    label: "Test SSD"
    quantity: 2
    baseline_price: 9500
    match_all: ["金士頓", "KC3000", "2TB"]
    exclude: []
""", encoding="utf-8")
    return yaml_path


def _fake_raw_products():
    from src.models import RawProduct
    return [
        RawProduct(option_value="1", option_text="AMD R7 7700 MPK $6490",
                   price=6490, optgroup="CPU"),
        RawProduct(option_value="2", option_text="金士頓 KC3000 2TB $9500",
                   price=9500, optgroup="SSD"),
    ] + [
        RawProduct(option_value=str(i), option_text=f"filler{i} ${100 + i}",
                   price=100 + i, optgroup=None)
        for i in range(300)
    ]


def test_main_dry_run_does_not_send_email(mocker, tmp_db, products_yaml, capsys):
    mocker.patch("src.fetchers.coolpc.CoolpcFetcher.fetch", return_value=_fake_raw_products())
    send_mock = mocker.patch("src.notifier.send_email")

    rc = main(argv=["--dry-run",
                    "--config", str(products_yaml),
                    "--db", str(tmp_db)])

    assert rc == 0
    assert send_mock.call_count == 0
    captured = capsys.readouterr()
    assert "matched 2/2" in captured.out
    assert "would send" in captured.out or "dry-run" in captured.out


def test_main_real_run_sends_email(mocker, tmp_db, products_yaml):
    mocker.patch("src.fetchers.coolpc.CoolpcFetcher.fetch", return_value=_fake_raw_products())
    send_mock = mocker.patch("src.notifier.send_email")
    mocker.patch.dict("os.environ", {
        "GMAIL_USER": "u@g.com", "GMAIL_APP_PASSWORD": "pw", "TO_EMAIL": "t@g.com",
    })

    rc = main(argv=["--config", str(products_yaml),
                    "--db", str(tmp_db)])

    assert rc == 0
    assert send_mock.call_count == 1
    kwargs = send_mock.call_args.kwargs
    assert "原價屋" in kwargs["subject"]


def test_main_fetcher_failure_sends_alert_and_exits_nonzero(mocker, tmp_db, products_yaml):
    from src.fetchers.base import FetcherError
    mocker.patch("src.fetchers.coolpc.CoolpcFetcher.fetch",
                 side_effect=FetcherError("Only 45 options"))
    send_mock = mocker.patch("src.notifier.send_email")
    mocker.patch.dict("os.environ", {
        "GMAIL_USER": "u@g.com", "GMAIL_APP_PASSWORD": "pw", "TO_EMAIL": "t@g.com",
    })

    rc = main(argv=["--config", str(products_yaml), "--db", str(tmp_db)])

    assert rc == 1
    assert send_mock.call_count == 1
    subject = send_mock.call_args.kwargs["subject"]
    assert "故障" in subject or "alert" in subject.lower()
