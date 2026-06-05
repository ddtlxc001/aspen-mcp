"""COM bridge with Pfsctrl IAccessible + CoCreateInstance support."""

# Insert after line 361 (generate_input_summary), before set_stream_param
# This file contains the insertable block only.

PFD_SUPPORT_CODE = r'''
    # ---------- PFS / PFD graphics layer ----------

    def _get_pfd_window_hwnd(self):
        """Find the Aspen Plus main window and PFD host HWND.
        Returns (main_hwnd, pfd_hwnd). Called from COM thread only.
        """
        import win32gui, time
        from .com_bridge import _GUID, _iid  # noqa

        self._app.Visible = True
        for _ in range(10):
            hwnd = None
            def _ecb(h, _):
                nonlocal hwnd
                try:
                    if win32gui.IsWindowVisible(h) and "Aspen Plus V15" in win32gui.GetWindowText(h):
                        hwnd = h
                except: pass
            win32gui.EnumWindows(_ecb, None)
            if hwnd:
                break
            pythoncom.PumpWaitingMessages()
            time.sleep(0.2)

        if not hwnd:
            raise RuntimeError("Aspen Plus V15 window not found")

        afx = []
        def _fx(h, _):
            if "AfxOleControl140" in win32gui.GetClassName(h):
                afx.append(h)
        win32gui.EnumChildWindows(hwnd, _fx, None)
        if not afx:
            raise RuntimeError("PFD host (AfxOleControl140) not found")

        pfd = max(afx, key=lambda h:
            win32gui.GetWindowRect(h)[2] - win32gui.GetWindowRect(h)[0])
        return hwnd, pfd

    def _get_pfd_accessible(self):
        """Get IAccessible for the PFD window. Called from COM thread.
        Cached in self._pfd_accessible.
        """
        if getattr(self, "_pfd_accessible", None) is not None:
            return self._pfd_accessible

        import ctypes, win32gui, pythoncom
        from ctypes import wintypes
        from win32com.client import Dispatch

        class _G(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                        ("Data3", wintypes.WORD), ("Data4", wintypes.BYTE * 8)]
        def _iid(s):
            g = _G(); ctypes.windll.ole32.CLSIDFromString(s, ctypes.byref(g)); return g

        _, pfd_hwnd = self._get_pfd_window_hwnd()
        oleacc = ctypes.windll.oleacc
        ptr = ctypes.c_void_p()
        hr = oleacc.AccessibleObjectFromWindow(
            pfd_hwnd, 0,
            ctypes.byref(_iid("{618736E0-3C3D-11CF-810C-00AA00389B71}")),
            ctypes.byref(ptr),
        )
        if hr != 0 or not ptr.value:
            raise RuntimeError(f"IAccessible from PFD window failed: 0x{hr:08X}")

        obj = pythoncom.ObjectFromAddress(
            ctypes.addressof(ptr),
            _iid("{618736E0-3C3D-11CF-810C-00AA00389B71}"),
        )
        acc = Dispatch(obj)
        self._pfd_accessible = acc
        return acc

    def _walk_accessible_tree(self, acc, depth=0, max_depth=4):
        """Recursively walk IAccessible tree and return block-like objects.
        Returns list of {name, left, top, width, height, role, children}.
        """
        import pythoncom, time
        result = []
        if depth > max_depth:
            return result

        role = None
        name = None
        location = None
        try:
            role = int(str(acc.accRole))
        except: pass
        try:
            name = str(acc.accName)
        except: pass
        try:
            loc = acc.accLocation
            if loc:
                location = {"left": loc[0], "top": loc[1], "width": loc[2], "height": loc[3]}
        except: pass
        try:
            child_count = int(str(acc.accChildCount))
        except:
            child_count = 0

        # If this object has a name and position, record it
        entry = {"role": role, "name": name, "location": location, "child_count": child_count}

        # Try to get children via accNavigate (NAVDIR_FIRSTCHILD = 4)
        children = []
        try:
            child = acc.accNavigate(4, 0)  # FIRSTCHILD
            while child is not None:
                sub = self._walk_accessible_tree(child, depth + 1)
                if sub:
                    children.extend(sub)
                try:
                    child = child.accNavigate(3, 0)  # NEXTSIBLING
                except:
                    child = None
        except:
            # Fallback: iterate by index
            for i in range(1, min(child_count + 1, 50)):
                try:
                    child = acc.accChild(i)
                    if child:
                        sub = self._walk_accessible_tree(child, depth + 1)
                        if sub:
                            children.extend(sub)
                        # Record single child info
                        try:
                            cn = str(child.accName)
                            cr = int(str(child.accRole))
                            cl = list(child.accLocation) if child.accLocation else None
                            if cn or cl:
                                c_entry = {"role": cr, "name": cn, "location": cl, "child_count": 0}
                                if c_entry not in children:
                                    children.append(c_entry)
                        except: pass
                except:
                    break

        if children:
            entry["children"] = children
            result.extend(children)
        elif name or location:
            result.append(entry)

        return result

    def get_block_position(self, block_name):
        """Read block PFD position via IAccessible. Returns {x, y, w, h} in pixels."""
        def impl():
            import ctypes, pythoncom, time
            from win32com.client import Dispatch

            acc = self._get_pfd_accessible()
            rect = win32gui.GetWindowRect(self._get_pfd_window_hwnd()[1])

            # Walk accessible tree to find the block
            def find_block(node, depth=0):
                if depth > 6:
                    return None
                try:
                    name = str(node.accName)
                    if name and block_name.lower() in name.lower():
                        try:
                            loc = node.accLocation
                            if loc:
                                return {"name": name, "x": loc[0], "y": loc[1],
                                        "w": loc[2], "h": loc[3],
                                        "source": "accessible"}
                        except: pass
                except: pass
                try:
                    cc = int(str(node.accChildCount))
                    for i in range(1, min(cc + 1, 100)):
                        try:
                            child = node.accChild(i)
                            if child:
                                result = find_block(child, depth + 1)
                                if result:
                                    return result
                        except: break
                except: pass
                # Try FIRSTCHILD navigation
                try:
                    child = node.accNavigate(4, 0)
                    while child:
                        result = find_block(child, depth + 1)
                        if result:
                            return result
                        try:
                            child = child.accNavigate(3, 0)
                        except:
                            child = None
                except: pass
                return None

            found = find_block(acc)
            if found:
                return found

            # Fallback: scan all hit-tested points
            left, top, right, bottom = rect
            scan_points = [(left + 80, top + 80), (right - 80, bottom - 40),
                          (left + 200, top + 100), (right - 200, top + 100)]
            for px, py in scan_points:
                try:
                    hit = acc.accHitTest(px, py)
                    if hit:
                        try:
                            hn = str(hit.accName)
                        except:
                            hn = ""
                        if block_name.lower() in hn.lower():
                            try:
                                loc = hit.accLocation
                                return {"name": hn, "x": loc[0], "y": loc[1],
                                        "w": loc[2], "h": loc[3], "source": "hittest"}
                            except: pass
                except: pass

            # Block not found on PFD — try placing it first
            from win32com.client import Dispatch as D
            ctrl = D("PFSCTRL.PfsctrlCtrl.410")
            root = self._app.RootModel("")
            ctrl.SetRootModel(root)
            ctrl.PlaceBlock(block_name)
            pythoncom.PumpWaitingMessages()
            time.sleep(0.5)
            return {"name": block_name, "source": "just_placed", "note": "Check PFD visually"}

        return self.call(impl)

    def get_all_block_positions(self):
        """Read ALL block positions via IAccessible tree walk."""
        def impl():
            acc = self._get_pfd_accessible()
            all_items = self._walk_accessible_tree(acc)
            # Filter to likely block items (role 10 = ROLE_SYSTEM_WINDOW with names)
            blocks = []
            for item in all_items:
                if item.get("name") and item.get("location"):
                    loc = item["location"]
                    blocks.append({
                        "name": item["name"],
                        "x": loc["left"], "y": loc["top"],
                        "w": loc["width"], "h": loc["height"],
                    })
            return blocks
        return self.call(impl)

    def place_all_blocks(self):
        """Place all blocks via Pfsctrl OCX."""
        def impl():
            import pythoncom, time
            from win32com.client import Dispatch as D
            try:
                ctrl = D("PFSCTRL.PfsctrlCtrl.410")
                root = self._app.RootModel("")
                ctrl.SetRootModel(root)
                ctrl.PlaceAllBlocks()
                for _ in range(10):
                    pythoncom.PumpWaitingMessages()
                    time.sleep(0.05)
                return "OK"
            except Exception as e:
                return f"Pfsctrl error: {e}"
        return self.call(impl)

    def place_block(self, block_name):
        """Place a specific block via Pfsctrl OCX."""
        def impl():
            import pythoncom, time
            from win32com.client import Dispatch as D
            try:
                ctrl = D("PFSCTRL.PfsctrlCtrl.410")
                root = self._app.RootModel("")
                ctrl.SetRootModel(root)
                ctrl.PlaceBlock(block_name)
                for _ in range(10):
                    pythoncom.PumpWaitingMessages()
                    time.sleep(0.05)
                return "OK"
            except Exception as e:
                return f"Pfsctrl error: {e}"
        return self.call(impl)

    def get_pfd_zoom(self):
        """Get PFD zoom via Pfsctrl."""
        def impl():
            from win32com.client import Dispatch as D
            try:
                ctrl = D("PFSCTRL.PfsctrlCtrl.410")
                return float(ctrl.GetZoomLevel())
            except Exception as e:
                return f"Pfsctrl error: {e}"
        return self.call(impl)

'''  # noqa
