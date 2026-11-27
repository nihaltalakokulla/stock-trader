import argparse
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stock_trader")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("train", help="train and save the ranking model")
    nightly = subcommands.add_parser("nightly", help="screen, rank, and propose")
    nightly.add_argument(
        "--dry-run", action="store_true", help="print texts instead of sending"
    )
    execute = subcommands.add_parser("execute", help="execute an approval")
    execute.add_argument("--key", required=True, help="approval idempotency key")
    subcommands.add_parser("paper-report", help="summarize the paper account")
    return parser


def main(argv: Sequence[str] | None = None, runtime=None) -> int:
    args = build_parser().parse_args(argv)
    if runtime is None:
        from stock_trader.runtime import build_runtime

        runtime = build_runtime(dry_run=getattr(args, "dry_run", False))
    if args.command == "train":
        runtime.train()
    elif args.command == "nightly":
        runtime.nightly(dry_run=args.dry_run)
    elif args.command == "execute":
        runtime.execute(args.key)
    elif args.command == "paper-report":
        runtime.paper_report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
