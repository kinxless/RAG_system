import json
import os

DATA_DIR = os.getenv("DATA_DIR", ".")
CHECKPOINT_FILE = os.getenv(
    "CHECKPOINT_FILE",
    os.path.join(DATA_DIR, "sync_checkpoint.json")
)


def load_last_id(table_name):

    if not os.path.exists(
        CHECKPOINT_FILE
    ):
        return 0

    try:

        with open(
            CHECKPOINT_FILE,
            "r"
        ) as f:

            data = json.load(f)

        return data.get(
            table_name,
            0
        )

    except Exception:

        return 0


def save_last_id(
    table_name,
    last_id
):

    data = {}

    if os.path.exists(
        CHECKPOINT_FILE
    ):

        try:

            with open(
                CHECKPOINT_FILE,
                "r"
            ) as f:

                data = json.load(f)

        except Exception:

            data = {}

    data[table_name] = last_id

    checkpoint_dir = os.path.dirname(CHECKPOINT_FILE)
    if checkpoint_dir:
        os.makedirs(checkpoint_dir, exist_ok=True)

    with open(
        CHECKPOINT_FILE,
        "w"
    ) as f:

        json.dump(
            data,
            f,
            indent=2
        )