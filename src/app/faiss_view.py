"""CLI utility to inspect the contents of the FAISS indexes on disk."""

import argparse

import faiss

try:
    from .index_gen import load_index, list_indexed_ids, get_embedding
except ImportError:  # allows running this file directly as a script
    from index_gen import load_index, list_indexed_ids, get_embedding


def print_index_summary(is_user: bool, preview_len: int = 8):

    label = "USER" if is_user else "ADMIN"
    index = load_index(is_user)
    ids = list_indexed_ids(index)

    print(f"\n=== {label} index ===")
    print(f"Total vectors : {index.ntotal}")
    print(f"Dimension     : {index.d}")
    print(f"Indexed ids   : {ids}")

    for row_id in ids:
        vector = get_embedding(index, row_id)
        preview = [round(float(value), 4) for value in vector[:preview_len]]
        print(f"  id={row_id:<6} dim={vector.shape[0]:<6} preview={preview} ...")


def print_vector(is_user: bool, row_id: int):

    index = load_index(is_user)

    try:
        vector = get_embedding(index, row_id)
    except ValueError as exc:
        print(str(exc))
        return

    print(f"id={row_id} dim={vector.shape[0]}")
    print(vector.tolist())


def main():

    parser = argparse.ArgumentParser(description="View FAISS index contents.")
    parser.add_argument(
        "--which",
        choices=["user", "admin", "both"],
        default="both",
        help="Which index to inspect (default: both).",
    )
    parser.add_argument(
        "--id",
        type=int,
        default=None,
        help="Print the full stored vector for a specific row id.",
    )
    parser.add_argument(
        "--preview-len",
        type=int,
        default=8,
        help="Number of vector values to preview per row (default: 8).",
    )

    args = parser.parse_args()

    targets = []
    if args.which in ("user", "both"):
        targets.append(True)
    if args.which in ("admin", "both"):
        targets.append(False)

    if args.id is not None:
        for is_user in targets:
            print_vector(is_user, args.id)
        return

    for is_user in targets:
        print_index_summary(is_user, args.preview_len)


if __name__ == "__main__":
    main()
