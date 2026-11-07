"""Run every lab's reference solution and check its numbers against the lessons.

    python tools/run_all.py            (all labs)
    python tools/run_all.py 04 07      (some labs)

Each lab prints RECORD key = value lines and a VERDICT. The lesson for the lab lists the same keys with
reference values in its ::: measure block; with the mock model they must match (timings within 50%).
"""
import pathlib
import re
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]


def refs():
    out = {}
    for md in sorted((ROOT / "course").glob("*.md")):
        text = md.read_text()
        lab = re.search(r"^lab:\s*(\S+)", text, re.M)
        blk = re.search(r"^::: *measure\s*\n(.*?)^:::", text, re.S | re.M)
        if lab and blk:
            fields = {}
            for line in blk.group(1).splitlines():
                cells = [c.strip() for c in line.strip()[1:].split("|")] if line.strip().startswith("-") else []
                if len(cells) >= 3 and cells[2]:
                    fields[cells[0]] = (float(cells[2]), cells[3] if len(cells) > 3 else "")
            out[pathlib.Path(lab.group(1)).name] = fields
    return out


def close(got, want, unit):
    if unit in ("s", "ms"):
        return abs(got - want) <= 0.5 * abs(want) + 0.05
    return abs(got - want) <= 1e-3 * max(1.0, abs(want))


def main():
    only = sys.argv[1:]
    labs = sorted(p for p in (ROOT / "labs").iterdir() if (p / "run.py").exists()
                  and (not only or any(p.name.startswith(o) for o in only)))
    expected, failed = refs(), []
    for lab in labs:
        t = time.time()
        p = subprocess.run([sys.executable, str(lab / "run.py"), "--solution"], cwd=ROOT, capture_output=True,
                           text=True, timeout=600)
        out = p.stdout + p.stderr
        got = {}
        for line in out.splitlines():
            if line.startswith("RECORD"):
                got.update({k: float(v) for k, v in re.findall(r"(\w+) = (-?[\d.]+)", line)})
        verdict = (re.findall(r"^VERDICT\s+(.*)", out, re.M) or ["(none)"])[-1]
        problems = [] if p.returncode == 0 and verdict.startswith("PASS") else [f"exit {p.returncode}, verdict {verdict}"]
        for key, (want, unit) in expected.get(lab.name, {}).items():
            if key not in got:
                problems.append(f"{key} not recorded")
            elif not close(got[key], want, unit):
                problems.append(f"{key} = {got[key]:g}, lesson says {want:g}")
        print(f"{'ok  ' if not problems else 'FAIL'} {lab.name:28} {time.time() - t:5.1f}s  "
              + ("  ".join(f"{k}={v:g}" for k, v in got.items()) if not problems else "; ".join(problems)))
        if problems:
            failed.append(lab.name)
            if p.returncode:
                print(out[-2000:])
    print(f"\n{len(labs) - len(failed)}/{len(labs)} labs pass" + (f"; failing: {', '.join(failed)}" if failed else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
