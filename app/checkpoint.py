import json
import os

CHECKPOINT_FILE = "sync_checkpoint.json"


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

    with open(
        CHECKPOINT_FILE,
        "w"
    ) as f:

        json.dump(
            data,
            f,
            indent=2
        )