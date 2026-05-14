# pytest-free test runner. Walks tests/, resolves @fixture decorators
# (using the shim from tests/_pytest_shim.py when pytest is absent), and
# runs every test_* function. Exits nonzero on first failure batch.
#
# If you actually have pytest installed, just use `pytest -q` instead.
import importlib
import inspect
import sys
import time
import traceback
from pathlib import Path

import tests  # noqa: F401 - triggers the pytest shim


def _test_modules():
    here = Path(__file__).parent / "tests"
    for p in sorted(here.glob("test_*.py")):
        yield "tests." + p.stem


def _is_test(obj):
    return callable(obj) and getattr(obj, "__name__", "").startswith("test_")


def _is_fixture(obj):
    return callable(obj) and getattr(obj, "_is_fixture", False)


def main():
    t0 = time.time()
    print("=== Aegis ControlRisk OS v2 — Test Runner ===\n")
    total = passed = 0
    failures = []

    for mod_name in _test_modules():
        try:
            mod = importlib.import_module(mod_name)
        except Exception as e:
            print(f"  IMPORT FAILED: {mod_name}: {e}")
            traceback.print_exc()
            failures.append((mod_name, "import error", str(e)))
            continue

        fixtures = {n: o for n, o in inspect.getmembers(mod) if _is_fixture(o)}
        cache = {}

        # tmp_path is provided inline below (function-scoped, fresh per test).
        # Module-scoped @fixture-decorated funcs flow through resolve().
        import tempfile
        from pathlib import Path as _P

        def resolve(name):
            if name in cache:
                return cache[name]
            if name not in fixtures:
                raise RuntimeError(f"missing fixture: {name}")
            fx = fixtures[name]
            sig = inspect.signature(
                fx.__wrapped__ if hasattr(fx, "__wrapped__") else fx
            )
            kw = {p: resolve(p) for p in sig.parameters}
            val = fx(**kw) if kw else fx()
            cache[name] = val
            return val

        tests_ = [(n, o) for n, o in inspect.getmembers(mod) if _is_test(o)]
        print(f"\n[{mod_name}] ({len(tests_)} tests)")
        for name, fn in tests_:
            total += 1
            sig = inspect.signature(fn)
            kwargs = {}
            broken = False
            for pname in sig.parameters:
                # tmp_path gets a fresh directory per test, not cached
                if pname == "tmp_path":
                    kwargs[pname] = _P(tempfile.mkdtemp(prefix="aegis_test_"))
                    continue
                try:
                    kwargs[pname] = resolve(pname)
                except Exception as e:
                    failures.append((mod_name, name, f"fixture {pname}: {e}"))
                    print(f"  ✗ {name} (fixture {pname} error: {e})")
                    broken = True
                    break
            if broken:
                continue
            try:
                fn(**kwargs)
                passed += 1
                print(f"  ✓ {name}")
            except AssertionError as e:
                failures.append((mod_name, name, f"assert: {e}"))
                print(f"  ✗ {name}: {e}")
            except Exception as e:
                failures.append((mod_name, name, f"crash: {e}"))
                print(f"  ✗ {name}: CRASH {type(e).__name__}: {e}")
                traceback.print_exc()

    elapsed = time.time() - t0
    print("\n" + "=" * 50)
    print(f"Ran {total} tests in {elapsed:.1f}s — {passed} passed, "
          f"{len(failures)} failed")
    if failures:
        print("\nFailures:")
        for mod, name, msg in failures:
            print(f"  {mod}::{name}: {msg}")
        return 1
    print("All tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
