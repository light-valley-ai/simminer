from simminer.benchmarks import run_benchmarks


def test_benchmarks_meet_thresholds(example_repo):
    report = run_benchmarks(example_repo)
    # classification and metadata extraction should be near-perfect on clean data
    assert report["classification"]["accuracy"] >= 0.95
    assert report["metadata_extraction"]["accuracy"] >= 0.95
    assert report["discovery"]["duplicate_detection_ok"]
    assert report["classification"]["n"] > 50
