from contextlib import contextmanager
from contextvars import ContextVar


_current_audit_user = ContextVar("current_audit_user", default=None)
_audit_suppressed = ContextVar("audit_suppressed", default=False)


def get_current_audit_user():
    return _current_audit_user.get()


def is_audit_suppressed():
    return _audit_suppressed.get()


@contextmanager
def set_current_audit_user(user):
    token = _current_audit_user.set(user)
    try:
        yield
    finally:
        _current_audit_user.reset(token)


@contextmanager
def suppress_audit_signals():
    token = _audit_suppressed.set(True)
    try:
        yield
    finally:
        _audit_suppressed.reset(token)
