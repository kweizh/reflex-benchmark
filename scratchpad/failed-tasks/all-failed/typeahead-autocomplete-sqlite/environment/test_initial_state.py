import csv
import os
import shutil

PROJECT_DIR = "/home/user/catalog_app"
SEED_CSV = os.path.join(PROJECT_DIR, "products.csv")

# Product names referenced by the verification plan; they must be present in the
# seed dataset that ships as part of the initial environment.
EXPECTED_NAMES = [
    "Apple",
    "Appliance Hub",
    "Application Framework",
    "Application Server",
    "Pineapple",
    "Snapple",
    "Processor",
    "Projector",
    "Laptop Pro",
    "Notebook Pro",
]


def test_uv_available():
    assert shutil.which("uv") is not None, "The 'uv' package manager was not found in PATH."


def test_python3_available():
    assert shutil.which("python3") is not None, "python3 was not found in PATH."


def test_project_dir_exists():
    assert os.path.isdir(PROJECT_DIR), f"Project directory {PROJECT_DIR} does not exist."


def test_seed_csv_exists():
    assert os.path.isfile(SEED_CSV), f"Seed dataset {SEED_CSV} does not exist."


def test_seed_csv_header():
    with open(SEED_CSV, newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
    assert header == ["name", "category", "price", "description"], (
        f"Seed CSV header must be name,category,price,description but was {header}."
    )


def test_seed_csv_has_expected_rows():
    with open(SEED_CSV, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) >= 20, f"Seed CSV should contain at least 20 products but had {len(rows)}."
    names = {row["name"] for row in rows}
    missing = [name for name in EXPECTED_NAMES if name not in names]
    assert not missing, f"Seed CSV is missing expected products: {missing}."
