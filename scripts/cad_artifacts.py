"""Inspect or render saved CAD in a fresh offline Podman sandbox."""

import argparse
import json
import subprocess
import sys

from sandbox_postprocess import PostprocessJob, run_postprocess


def inspect(args):
    return postprocess(args, "inspect")


def render(args):
    return postprocess(args, "render")


def postprocess(args, operation):
    if getattr(args, "freecadcmd", None) is not None:
        raise ValueError("--freecadcmd is no longer supported. Host FreeCAD execution is forbidden; use the trial's recorded Podman runtime.")
    job = PostprocessJob.load(args.trial, operation, args.timeout)
    result = run_postprocess(job)
    print(json.dumps({"success": result.get("success") is True,
                      "evidence": str(job.root / "evidence" / job.result_name),
                      "host_source_unchanged": result["host_source_unchanged"]},
                     ensure_ascii=False))
    return 0 if result.get("success") is True else 1


def render_code(_args):
    raise ValueError("render-code is disabled because it could run saved CAD in host FreeCAD. Use: cad_artifacts.py render --trial <TRIAL>")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, handler in (("inspect", inspect), ("render", render)):
        command = sub.add_parser(name, help="Run " + name + " in a fresh offline Podman container")
        command.add_argument("--trial", required=True)
        command.add_argument("--timeout", type=int, default=180)
        command.add_argument("--freecadcmd", help=argparse.SUPPRESS)
        command.set_defaults(handler=handler)
    command = sub.add_parser("render-code", help="Disabled host execution path")
    command.add_argument("--trial", required=True)
    command.set_defaults(handler=render_code)
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

