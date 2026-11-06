"""Command line adapter for the same content operations used by Python clients."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from . import ContentRef, build_context, load, merge, parse, validate
from .errors import ContentError, ContentIOError
from .io import serialize, write_atomic
from .validation import SECTIONS


def _positive(text):
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError("Expected a positive integer") from None
    if value <= 0:
        raise argparse.ArgumentTypeError("Expected a positive integer")
    return value


def _task(text):
    if not text.strip():
        raise argparse.ArgumentTypeError("Task must contain text")
    return text


def _ref(text):
    try:
        return ContentRef.parse(text)
    except ContentError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def _document(path):
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ContentIOError(str(error), source=str(path), code="read_error") from error
    return parse(text, source=str(path))


def _protect_inputs(output, inputs):
    if output is None:
        return
    try:
        target = Path(output)
        for path in inputs:
            original = Path(path)
            if target.resolve() == original.resolve() or (target.exists() and original.exists() and target.samefile(original)):
                raise ContentIOError("Output aliases an input", source=str(output), code="output_alias")
    except OSError as error:
        raise ContentIOError(str(error), source=str(output), code="write_error") from error


def _parser():
    parser = argparse.ArgumentParser(prog="python -m rpg_content")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("validate")
    check.add_argument("input")
    check.add_argument("--base")
    combine = commands.add_parser("merge")
    combine.add_argument("inputs", nargs="+")
    combine.add_argument("--output", required=True)
    context = commands.add_parser("context")
    context.add_argument("input")
    context.add_argument("--type", dest="section", choices=SECTIONS, required=True)
    context.add_argument("--task", type=_task, required=True)
    refs = context.add_mutually_exclusive_group(required=True)
    refs.add_argument("--ref", dest="refs", action="append", type=_ref)
    refs.add_argument("--no-refs", action="store_true")
    index = context.add_mutually_exclusive_group(required=True)
    index.add_argument("--index-ref", dest="index_refs", action="append", type=_ref)
    index.add_argument("--no-index", action="store_true")
    context.add_argument("--max-chars", type=_positive, required=True)
    context.add_argument("--output")
    return parser


def main(argv=None):
    # Explicit UTF-8 also covers redirected output on Windows without env flags.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", newline="\n")
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate":
            validate(_document(args.input), base=load(args.base) if args.base else None)
            return 0
        inputs = args.inputs if args.command == "merge" else [args.input]
        _protect_inputs(args.output, inputs)
        if args.command == "merge":
            text = serialize(merge(_document(path) for path in inputs))
        else:
            text = build_context(load(args.input), section=args.section, task=args.task,
                                 refs=tuple(args.refs or ()), index_refs=tuple(args.index_refs or ()),
                                 max_chars=args.max_chars)
            print(f"Context: {len(text)} characters (limit {args.max_chars})", file=sys.stderr)
        if args.output:
            write_atomic(args.output, text)
        else:
            sys.stdout.write(text)
        return 0
    except ContentIOError as error:
        print(str(error), file=sys.stderr)
        return 3
    except ContentError as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
