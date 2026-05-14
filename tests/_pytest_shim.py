# If pytest isn't installed (some CI environments don't have it), inject a
# minimal stub so the test files can still be imported and discovered by
# run_tests.py. The stub only implements what we actually use: @fixture
# decorator and the raises() context manager.
import sys

try:
    import pytest  # noqa: F401
except ImportError:
    class _Stub:
        @staticmethod
        def fixture(*args, **kwargs):
            def decorator(fn):
                cache = {}

                def wrapper(*a, **kw):
                    if "v" not in cache:
                        cache["v"] = fn(*a, **kw)
                    return cache["v"]

                wrapper.__wrapped__ = fn
                wrapper._is_fixture = True
                return wrapper

            # Support both `@pytest.fixture` and `@pytest.fixture(scope=...)`
            if args and callable(args[0]):
                return decorator(args[0])
            return decorator

        class raises:
            def __init__(self, exc):
                self.exc = exc
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                if exc_type is None:
                    raise AssertionError(f"expected {self.exc.__name__}")
                return issubclass(exc_type, self.exc)

    sys.modules["pytest"] = _Stub()
