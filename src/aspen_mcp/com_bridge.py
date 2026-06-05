"""COM bridge --- Aspen Plus v15 (41.0) connection via dedicated COM thread.

Architecture
------------
A single background thread (the *COM apartment thread*) owns all COM
interaction.  Every public method submits a job to that thread and blocks
until the result arrives.  This avoids RPC_E_WRONG_THREAD errors that
plague per-call thread spawning, and lets us pump COM messages between
operations.

Key behaviours
  - Auto-connect on first call via the COM thread.
  - Thread-safe: all methods submit to the same apartment thread.
  - SuppressDialogs set on connect to prevent modal dialogs from hanging.
  - Timeout + auto-retry with back-off; reconnects on connection loss.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from contextlib import contextmanager
from typing import Any, Callable

import pythoncom
import win32com.client

# Initialize COM on the importing thread (the MCP server's main thread)
# so COM proxy objects returned from the COM apartment thread work.
try:
    pythoncom.CoInitialize()
except Exception:
    pass

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_TIMEOUT_SECONDS = 55
_RETRY_DELAYS = [0.5, 1.0, 2.0]
_STOP_SENTINEL = object()

_CONNECTION_LOST_CODES = {
    0x800706BA,   # RPC_S_SERVER_UNAVAILABLE
    0x800706BE,   # RPC_S_CALL_FAILED
    0x80010108,   # RPC_E_DISCONNECTED
    0x800706BF,   # RPC_S_CALL_FAILED_DNE
    0x80004005,   # E_FAIL
}


def _is_connection_error(exc):
    try:
        if hasattr(exc, "hresult"):
            return exc.hresult in _CONNECTION_LOST_CODES
        if hasattr(exc, "args") and len(exc.args) > 0:
            if isinstance(exc.args[0], int):
                return exc.args[0] in _CONNECTION_LOST_CODES
    except Exception:
        pass
    return False


# --- Dedicated COM apartment thread ----------------------------------------


class _ComJob:
    """A single unit of work for the COM apartment thread."""

    def __init__(self, fn: Callable):
        self.fn = fn
        self.result_queue: queue.Queue[tuple[str, Any]] = queue.Queue(1)

    def run(self) -> None:
        try:
            value = self.fn()
            self.result_queue.put(("ok", value))
        except BaseException as exc:
            self.result_queue.put(("exc", exc))

    def wait(self, timeout: float) -> Any:
        status, value = self.result_queue.get(timeout=timeout)
        if status == "exc":
            raise value
        return value


class _ComApartment:
    """Owns the COM apartment thread and dispatches jobs."""

    def __init__(self):
        self._job_queue: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._thread = threading.Thread(
                target=self._run, name="com-apartment", daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        self._job_queue.put(_STOP_SENTINEL)

    def _run(self) -> None:
        """COM apartment thread main loop (STA + message pump)."""
        pythoncom.CoInitialize()  # STA — single-threaded apartment
        while True:
            item = self._job_queue.get()
            if item is _STOP_SENTINEL:
                break
            assert isinstance(item, _ComJob)
            item.run()
            # Pump pending COM messages to prevent cross-thread call deadlock
            try:
                pythoncom.PumpWaitingMessages()
            except Exception:
                pass
        pythoncom.CoUninitialize()

    def submit(self, fn: Callable, timeout: float = _TIMEOUT_SECONDS) -> Any:
        """Submit a callable to the COM thread and wait for the result."""
        self.start()
        job = _ComJob(fn)
        self._job_queue.put(job)
        return job.wait(timeout)


_COM = _ComApartment()


# --- AspenConnection -------------------------------------------------------


class AspenConnection:

    def __init__(self):
        self._app = None
        self._lock = threading.Lock()

    # -- internal helpers called only from the COM thread ------------------

    def _connect(self):
        """Connect to Aspen Plus (must be called on the COM thread)."""
        if self._app is not None:
            return
        app = win32com.client.Dispatch("Apwn.Document")
        app.SuppressDialogs = True
        _ = app.Name
        self._app = app
        logger.info("Connected to Aspen Plus (v15 / 41.0)")

    def _disconnect(self):
        self._app = None
        logger.info("Disconnected")

    def _is_dead(self) -> bool:
        if self._app is None:
            return True
        try:
            _ = self._app.Name
            return False
        except Exception:
            return True

    def _force_reconnect(self):
        try:
            self._app = None
        except Exception:
            pass
        self._connect()

    # -- public API --------------------------------------------------------

    def connect(self):
        """Connect (from any thread --- delegates to the COM thread)."""
        def impl():
            self._connect()
            return True
        self.call(impl)

    def call(self, fn: Callable) -> Any:
        """Execute *fn* on the COM apartment thread with retry-on-failure.

        *fn* is called inside an automatic retry loop; transient connection
        errors trigger a re-connect and retry.
        """
        last_exc = None
        for attempt in range(_MAX_RETRIES):
            try:
                # Ensure we have a connection on the COM thread first
                if self._app is None:
                    _COM.submit(self._connect, _TIMEOUT_SECONDS)
                return _COM.submit(fn, _TIMEOUT_SECONDS)
            except queue.Empty:
                logger.warning("COM call timed out (attempt %d/%d)", attempt + 1, _MAX_RETRIES)
                last_exc = TimeoutError(f"COM call timed out after {_TIMEOUT_SECONDS}s")
                _COM.submit(self._force_reconnect, 10)
            except Exception as exc:
                last_exc = exc
                is_dead = _COM.submit(self._is_dead, 10)
                if _is_connection_error(exc) or is_dead:
                    logger.warning("COM connection lost (attempt %d/%d): %s", attempt + 1, _MAX_RETRIES, exc)
                    _COM.submit(self._force_reconnect, 10)
                else:
                    raise
            if attempt < len(_RETRY_DELAYS):
                time.sleep(_RETRY_DELAYS[attempt])
        raise RuntimeError("COM call failed after %d attempts" % _MAX_RETRIES) from last_exc

    def status(self) -> dict:
        """Return the current Aspen Plus connection / engine status."""
        def impl():
            if self._app is None:
                return {"connected": False, "file": None, "engine": "stopped"}
            try:
                engine = self._app.Engine
                return {
                    "connected": True,
                    "app": self._app.Name,
                    "engine": "running" if engine.IsRunning else "stopped",
                    "ready": engine.Ready,
                }
            except Exception:
                return {"connected": False, "file": None, "engine": "stopped"}
        return self.call(impl)

    def probe(self) -> dict:
        """Diagnose COM state (app, root, tree access)."""
        def impl():
            result = {}
            try:
                result["app_name"] = self._app.Name if self._app else "NO_APP"
            except Exception as e:
                result["app_error"] = str(e)[:60]
            try:
                if self._app is None:
                    result["root_error"] = "No app (not connected)"
                    return result
                root = self._app.RootModel("")
                result["root_type"] = type(root).__name__
                try:
                    c0 = root.Elements(0)
                    result["root_0_name"] = c0.Name if c0 else "None"
                except Exception as e:
                    result["root_0_err"] = str(e)[:60]
                try:
                    cd = root.Elements("Data")
                    result["root_Data"] = cd.Name if cd else "None"
                except Exception as e:
                    result["root_Data_err"] = str(e)[:60]
            except Exception as e:
                result["root_error"] = str(e)[:60]
            return result
        return self.call(impl)

    def root(self):
        return self.call(lambda: self._app.RootModel(""))

    def get_node(self, *parts):
        def impl():
            return _walk(self._app.RootModel(""), *parts)
        return self.call(impl)

    def get_value(self, *parts):
        def impl():
            node = _walk(self._app.RootModel(""), *parts)
            return node.Value if node is not None else None
        return self.call(impl)

    def set_value(self, value, *parts):
        def impl():
            node = _walk(self._app.RootModel(""), *parts)
            if node is None:
                return False
            try:
                node.SetValue(0, value)
                return True
            except Exception as exc:
                logger.warning("set_value(%r) failed: %s", parts, exc)
                return False
        return self.call(impl)

    def get_path_value(self, path):
        def impl():
            node = self._app.RootModel("").FindNode(path)
            if node is None:
                return None
            return node.Value
        return self.call(impl)

    def set_path_value(self, path, value, unit=None):
        def impl():
            node = self._app.RootModel("").FindNode(path)
            if node is None:
                return "Node not found: %s" % path
            # If node has children and value is a string, try child match first
            try:
                if node.Elements.Count > 0 and isinstance(value, str):
                    for i in range(node.Elements.Count):
                        try:
                            child = node.Elements(i)
                            if child.Name.upper() == value.upper():
                                child.SetValue(0, value)
                                return "OK"
                        except Exception:
                            pass
            except Exception:
                pass
            node.SetValue(0, value)
            return "OK"
        return self.call(impl)

    def set_node_attribute(self, path, attribute, value):
        def impl():
            node = self._app.RootModel("").FindNode(path)
            if node is None:
                return "Node not found: %s" % path
            dispid = node._oleobj_.GetIDsOfNames("AttributeValue")
            if isinstance(dispid, tuple):
                dispid = dispid[0]
            node._oleobj_.Invoke(
                dispid, 0, pythoncom.DISPATCH_PROPERTYPUT, 0,
                attribute, False, value,
            )
            return "OK"
        return self.call(impl)

    def open_file(self, path):
        self.call(lambda: self._app.InitFromFile(path))

    def close_file(self):
        # Close on COM thread and always clear the stale reference
        try:
            self.call(lambda: self._app.Close())
        except Exception:
            pass
        self._app = None
        # Next call() will auto-connect fresh

    def save(self, path=None):
        if path:
            self.call(lambda: self._app.SaveAs(path))
        else:
            self.call(lambda: self._app.Save())

        # ---------- engine execution (Run2 with built-in timeout) ----------

    _RUN_TIMEOUT_SECONDS = 45

    def run(self):
        self.call(lambda: self._app.Run2())

    def run_async(self):
        self.call(lambda: self._app.Engine.Run())

    def reinit(self):
        self.call(lambda: self._app.Engine.Reinit())

    def reinit_and_run(self):
        def impl():
            self._app.Engine.Reinit()
            self._app.Run2()
        self.call(impl)

    def stop(self):
        self.call(lambda: self._app.Engine.Stop())

    def set_visible(self, show):
        self.call(lambda: setattr(self._app, "Visible", show))

    def set_batch_refresh(self, off):
        self.call(lambda: setattr(self._app, "RefreshOff", off))

    def run_script(self, file_path):
        self.call(lambda: self._app.RunScript(file_path))

    def generate_input_summary(self, file_path):
        self.call(lambda: self._app.Generate(file_path, 0))

    def set_stream_param(self, stream_name, param, value):
        def impl():
            node = _walk(self._app.RootModel(""), "Data", "Streams", stream_name, "Input", param)
            if node is None:
                return False
            try:
                if node.Elements.Count > 0:
                    node.Elements(0).SetValue(0, value)
                else:
                    node.SetValue(0, value)
                return True
            except Exception:
                try:
                    node.SetValue(0, value)
                    return True
                except Exception:
                    return False
        return self.call(impl)

    def set_stream_composition(self, stream_name, component, flow):
        def impl():
            node = _walk(self._app.RootModel(""),
                         "Data", "Streams", stream_name, "Input", "FLOW", "MIXED", component)
            if node is None:
                return False
            try:
                node.SetValue(0, flow)
                return True
            except Exception:
                return False
        return self.call(impl)

    def enumerate_children(self, node):
        kids = []
        for i in range(10000):
            try:
                child = node.Elements(i)
            except Exception:
                break
            if child is None:
                break
            kids.append(child)
        return kids

    def child_names(self, node):
        return [c.Name for c in self.enumerate_children(node)]

    def find_node(self, path):
        def impl():
            return self._app.RootModel("").FindNode(path)
        return self.call(impl)

    def disconnect(self):
        self._disconnect()

    @contextmanager
    def ensure(self):
        _COM.submit(self._connect)
        try:
            yield self
        finally:
            _COM.submit(self._disconnect)


def _walk(root, *parts):
    node = root
    for p in parts:
        try:
            node = node.Elements(p)
        except Exception:
            return None
        if node is None:
            return None
    return node


aspen = AspenConnection()
