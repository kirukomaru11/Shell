from os import open as os_open, SEEK_SET, O_WRONLY, O_NONBLOCK, O_RDWR, O_CLOEXEC, O_RDONLY, set_blocking, pipe, read, write, lseek, close, environ
environ["GDK_DEBUG"] = "no-portals"

from struct import pack
from ctypes import *

CDLL(None).prctl(15, b"shell", 0, 0, 0)

try:
    layer_shell = CDLL("libgtk4-layer-shell.so")
except:
    layer_shell = False
    print("No Gtk4LayerShell")

try:
    from Utils import *
except ModuleNotFoundError:
    try:
        from .Utils import *
    except ModuleNotFoundError:
        print("No Utils")
        exit()

if FLATPAK_ID:
    GLib.old_spawn_command_line_sync = GLib.spawn_command_line_sync
    def spawn_command_line_sync(*args):
        args = list(args)
        args[0] = "/bin/flatpak-spawn --host " + args[0]
        return GLib.old_spawn_command_line_sync(*args)
    GLib.spawn_command_line_sync = spawn_command_line_sync
    GLib.old_spawn_command_line_async = GLib.spawn_command_line_async
    def spawn_command_line_async(*args):
        args = list(args)
        args[0] = "/bin/flatpak-spawn --host " + args[0]
        return GLib.old_spawn_command_line_async(*args)
    GLib.spawn_command_line_async = spawn_command_line_async

from io import FileIO
from re import compile as Regex
from json import loads as json, dumps as json_string
from string import ascii_uppercase
from select import select
from fnmatch import fnmatch
from fcntl import ioctl
from sqlite3 import register_adapter
from types import MethodType
from colorsys import hls_to_rgb, rgb_to_hls

if layer_shell:
    from gi.repository import Gtk4LayerShell as layer_shell

from gi.repository import GdkWayland

try:
    from gi.repository import Gst
except:
    Gst = False

INFO = {
    "ID": "io.github.kirukomaru11.Shell",
    "Developer": "きるこ丸11号",
    "Comment": "Simple Wayland Portal/Shell",
    "Issue URL": "https://github.com/kirukomaru11/Shell/issues",
    "Website": "https://github.com/kirukomaru11/Shell",
    "Categories": ["System"],
    "Branding": ["#546f4c", "#85a57c"],
    "MimeTypes": ["inode/directory", "x-scheme-handler/http", "x-scheme-handler/https"]
}

FLATPAK_FILES = ["flatpak", "app", INFO["ID"].replace(".Shell", ".Files"), "current", "active", "files", "lib"]

ROOT = "/run/host/root" if FLATPAK_ID else "/"

if FLATPAK_ID:
    HOST_ENV = {}
    for i in GLib.spawn_command_line_sync("env")[1].decode().split("\n"):
        i = i.split("=", 1)
        if len(i) == 2:
            HOST_ENV[i[0]] = i[1]
    HOST_HOME = Path(ROOT, HOST_ENV.get("HOME", Path("/home", GLib.getenv("USER"))))
    HOST_DATA = Path(ROOT, HOST_ENV.get("XDG_DATA_HOME", Path(HOST_HOME, ".local", "share")))
    HOST_SYSTEM_DATA = [Path(ROOT, i) for i in HOST_ENV.get("XDG_DATA_DIRS", "/usr/local/share/:/usr/share/").split(":") if i]
    f = Path(HOST_DATA, *FLATPAK_FILES)
    if exists(f):
        FLATPAK_FILES = f
    else:
        f = Path(ROOT, "var", "lib", *FLATPAK_FILES)
        if exists(f):
            FLATPAK_FILES = f
else:
    f = Path(DATA, *FLATPAK_FILES)
    if exists(f):
        FLATPAK_FILES = f
    else:
        f = Path("/var/lib", *FLATPAK_FILES)
        if exists(f):
            FLATPAK_FILES = f

if isinstance(FLATPAK_FILES, list):
    FLATPAK_FILES = ""

if FLATPAK_FILES:
    folder = next((i for i in list_dir(FLATPAK_FILES) if i.startswith("python")), False)
    if folder:
        FLATPAK_FILES = Path(FLATPAK_FILES, folder, "site-packages/Files.py")
    else:
        FLATPAK_FILES = ""

if FLATPAK_FILES:
    import importlib.util
    spec = importlib.util.spec_from_file_location("Files", FLATPAK_FILES)
    Files = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(Files)
    FileDialog = Files.FileDialog
else:
    try:
        from Files import FileDialog
    except:
        FileDialog = Gtk.FileDialog

try:
    wayland = CDLL("libwayland-client.so")
except:
    wayland = CDLL("libwayland-client.so.0")

try:
    gtk = CDLL("libgtk-4.so")
except:
    gtk = CDLL("libgtk-4.so.1")

try:
    gbm = CDLL("libgbm.so.1")
    gbm.gbm_create_device.argtypes = [c_int]
    gbm.gbm_create_device.restype = c_void_p
    gbm.gbm_bo_create.argtypes = [c_void_p, c_uint32, c_uint32, c_uint32, c_uint32]
    gbm.gbm_bo_create.restype = c_void_p
    gbm.gbm_bo_get_fd.argtypes = [c_void_p]
    gbm.gbm_bo_get_fd.restype = c_int
    gbm.gbm_bo_get_stride.argtypes = [c_void_p]
    gbm.gbm_bo_get_stride.restype = c_uint32
    gbm.gbm_bo_get_modifier.argtypes = [c_void_p]
    gbm.gbm_bo_get_modifier.restype = c_uint64
    from gi.repository import GstAllocators
except:
    gbm = False

pythonapi.PyCapsule_GetPointer.restype = c_void_p
pythonapi.PyCapsule_GetPointer.argtypes = [py_object]

def gtk_get_pointer(s, f):
    getattr(gtk, f).restype, getattr(gtk, f).argtypes  = c_void_p, [c_void_p]
    return getattr(gtk, f)(pythonapi.PyCapsule_GetPointer(s.__gpointer__, None))

class WlInterface(Structure):
    _instances = {}
    _types = {}
    def __init__(self, name="", version=1, requests=None, events=None):
        if requests:
            arr_type = WlMessage * len(requests)
            requests = arr_type(*tuple(WlMessage(i[0].encode(), i[1].encode(), i[2] if len(i) == 3 else WlInterface.types(None)) for i in requests))
        if events:
            arr_type = WlMessage * len(events)
            events = arr_type(*tuple(WlMessage(i[0].encode(), i[1].encode(), i[2] if len(i) == 3 else WlInterface.types(None)) for i in events))
        self._requests_ref = requests
        self._events_ref = events
        super().__init__(name=name.encode(), version=version, method_count=len(requests) if requests else 0, methods=requests, event_count=len(events) if events else 0, events=events)
        self.__class__._instances[name] = self

    @classmethod
    def __class_getitem__(cls, item): return cls._instances.get(item, None)

    @classmethod
    def set(cls, item, value):
        cls._instances[item] = value

    @staticmethod
    def type(*interfaces):
        arr_type = POINTER(WlInterface) * len(interfaces)
        return arr_type(*tuple(pointer(i) if i else i for i in interfaces))

    @staticmethod
    def types(*names):
        n = ",".join(str(i) for i in names)
        if n in WlInterface._types: return WlInterface._types[n]
        WlInterface._types[n] = WlInterface.type(*[WlInterface[i] if isinstance(i, str) else i for i in names])
        return WlInterface._types[n]

class WlProxy(GObject.Object):
    __gtype_name__ = "WlProxy"
    _dict = {}
    _dispatchs = {}
    dispatcher_function = GObject.Property(type=object)
    interface = GObject.Property(type=object)
    pointer = GObject.Property(type=object)
    def __init__(self, interface, pointer):
        super().__init__()
        self.interface = interface
        self.pointer = pointer
        for n, i in enumerate(interface.methods):
            if n + 1 > interface.method_count: break

            name = i.name.decode()
            setattr(self, name, MethodType(self.__class__.make_method(i, n), self))
        self.__class__._dict[self.pointer] = self

    @classmethod
    def from_params(cls, obj): return obj.pointer

    @staticmethod
    def make_method(method, opcode):
        def do_method(self, *args):
            if not (self.pointer and self.interface): return
            if opcode == 0 and self.interface.name.decode() == "wl_registry":
                interface, name, version = args
                arguments, interface = WlArgument.from_args([("u", name), ("s", interface.name), ("u", version), interface])
                return WlProxy(interface, wayland.wl_proxy_marshal_array_constructor_versioned(self.pointer, opcode, arguments, byref(interface), version))
            else:
                signature = method.signature.decode().replace("?", "")
                _args = []
                current = -1
                new_id_n = -1
                for i in signature:
                    if i == "n":
                        new_id_n += 1
                        n = new_id_n
                        if current >= 0:
                            n += current or 1
                        _args.append(method.types[n][0])
                    else:
                        current += 1
                        v = args[current]
                        if isinstance(v, WlProxy):
                            v = v.pointer
                        _args.append((i, v))
                arguments, interface = WlArgument.from_args(_args)
                if interface:
                    r = WlProxy(interface, wayland.wl_proxy_marshal_array_constructor_versioned(self.pointer, opcode, arguments, byref(interface), interface.version))
                else:
                    r = wayland.wl_proxy_marshal_array(self.pointer, opcode, arguments)
                if method.name.decode() == "destroy": self.do_dispose()
                return r
        return do_method

    def do_dispose(self):
        self.dispatcher_function = None
        if self.pointer in self.__class__._dispatchs:
            del self.__class__._dispatchs[self.pointer]
        if self.pointer in self.__class__._dict:
            del self.__class__._dict[self.pointer]
        self.pointer = None
        self.interface = None

    def dispatcher(self, function):
        if not self.pointer: return
        p = self.dispatcher_function
        self.dispatcher_function = function
        if not p:
            wayland.wl_proxy_add_dispatcher(self.pointer, self.__class__.do_dispatch, None, None)
            self.__class__._dispatchs[self.pointer] = self

    def do_dispatch(data, proxy, opcode, message, args):
        self = WlProxy._dispatchs.get(proxy, False)
        if self:
            a = []
            s = self.interface.events[opcode].signature.decode().replace("?", "")
            event = self.interface.events[opcode].name.decode()
            for n in range(10):
                s = s.replace(str(n), "")
            for n, i in enumerate(s):
                if i == "n":
                    i = "o"
                f = getattr(args[n], i, False)
                if i == "o" and f:
                    f = self.__class__.get(self.interface.events[opcode].types[n][0], f)
                if i == "s" and isinstance(f, bytes):
                    f = f.decode()
                if f != False: a.append(f)
            self.dispatcher_function(self, event, a)
        return 0

    @staticmethod
    def get(interface, p):
        if p in WlProxy._dict:
            p = WlProxy._dict[p]
        else:
            p = WlProxy(interface, p)
        return p

class WlMessage(Structure):
    _fields_ = [("name", c_char_p), ("signature", c_char_p), ("types", POINTER(POINTER(WlInterface)))]

class WlArgument(Union):
    _fields_ = [("i", c_int32), ("u", c_uint32), ("f", c_int32), ("s", c_char_p), ("o", c_void_p), ("n", c_uint32), ("a", c_void_p), ("h", c_int32)]

    @staticmethod
    def from_args(args=None):
        args = args or []
        arguments = (WlArgument * len(args))()
        interface = None
        for n, i in enumerate(args):
            if isinstance(i, WlInterface):
                interface = i
                arguments[n].o = None
            else:
                setattr(arguments[n], i[0], c_int32(int(round(i[1] * 256))) if i[0] == "f" and isinstance(i[1], float) else i[1].encode() if i[0] == "s" and isinstance(i[1], str) else i[1])
        return (arguments, interface)

WlInterface._fields_ = [("name", c_char_p), ("version", c_int), ("method_count", c_int), ("methods", POINTER(WlMessage)), ("event_count", c_int), ("events", POINTER(WlMessage)),]

WlDispatcher = CFUNCTYPE(c_int, c_void_p, c_void_p, c_uint32, POINTER(WlMessage), POINTER(WlArgument))
wayland.wl_proxy_add_dispatcher.argtypes = [c_void_p, WlDispatcher, c_void_p, c_void_p]
wayland.wl_proxy_add_dispatcher.restype = c_int
WlProxy.do_dispatch = WlDispatcher(WlProxy.do_dispatch)

wayland.wl_proxy_marshal_array_constructor_versioned.argtypes = [c_void_p, c_uint32, POINTER(WlArgument), POINTER(WlInterface), c_uint32]
wayland.wl_proxy_marshal_array_constructor_versioned.restype = c_void_p
wayland.wl_proxy_marshal_array.argtypes = [c_void_p, c_uint32, POINTER(WlArgument)]
wayland.wl_proxy_marshal_array.restype = c_void_p

class Wayland:
    def __init__(self):
        for i in ("display", "seat", "keyboard", "pointer", "surface", "output", "registry", "buffer", "shm", "shm_pool"): WlInterface.set(i, WlInterface.in_dll(wayland, f"wl_{i}_interface"))
        Wayland.registry = WlProxy(WlInterface["display"], gtk_get_pointer(Gdk.Display.get_default(), "gdk_wayland_display_get_wl_display")).get_registry()
        Wayland.registry.dispatcher(Wayland.registry_dispatcher)
        Wayland.interfaces = {}
        Gdk.Display.get_default().sync()
        Clipboard()
        if layer_shell and "zwlr_layer_shell_v1" in Wayland.interfaces:
            if Data.setting("Wallpaper", True): Wallpaper()
            if Data.setting("Background", True): Background()
            Keyboard()
        Pointer()
        ImageCopy()

    @staticmethod
    def registry_dispatcher(proxy, event, args):
        if event == "global":
            name, interface, version = args
            Wayland.interfaces.setdefault(interface, (name, version))

class LayerShell(Window):
    __gtype_name__ = "LayerShell"
    def __init__(self, layer="BACKGROUND", keyboard_mode="NONE", exclusive_zone=-1, anchor=(True, True, True, True), target=False, margin=(0, 0, 0, 0), css_name=None):
        if not css_name:
            css_name = self.__gtype_name__.lower()
        super().__init__(css_name=css_name)
        self.set_properties(default_width=1, default_height=1, height_request=1, width_request=1, title=self.__gtype_name__, decorated=False, focusable=target, can_focus=target, can_target=target, css_classes=("shell-window",))
        l = layer_shell
        l.init_for_window(self)
        l.set_namespace(self, self.get_css_name())
        l.set_layer(self, getattr(l.Layer, layer))
        l.set_keyboard_mode(self, getattr(l.KeyboardMode, keyboard_mode))
        l.set_exclusive_zone(self, exclusive_zone)
        if not target:
            self.present()
            self.get_surface().set_input_region(None)
        for n, i in enumerate((l.Edge.TOP, l.Edge.RIGHT, l.Edge.LEFT, l.Edge.BOTTOM)):
            l.set_anchor(self, i, anchor[n])
            l.set_margin(self, i, margin[n])

class Selector(LayerShell):
    __gtype_name__ = "Selector"
    function_data = GObject.Property(type=object)
    function = GObject.Property(type=object)
    draw = GObject.Property(type=Gtk.DrawingArea)
    square_width = GObject.Property(type=int)
    square_height = GObject.Property(type=int)
    x = GObject.Property(type=int)
    y = GObject.Property(type=int)
    single_pixel = GObject.Property(type=bool, default=False)
    def __init__(self, function=None, function_data=None, single_pixel=False):
        super().__init__(layer="OVERLAY", keyboard_mode="EXCLUSIVE" if hasattr(Wayfire, "connection") else "NONE")
        self.single_pixel = single_pixel
        self.function_data = function_data
        self.function = function
        self.set_cursor(Gdk.Cursor.new_from_name("crosshair", None))
        self.drag_to = self.drag_start = (0, 0)
        self.draw = Gtk.DrawingArea(can_target=False, can_focus=False, focus_on_click=False)
        self.draw.connect("resize", Window.reset_draw)
        self.draw.set_draw_func(self.__class__.draw_func)
        self.set_content(self.draw)
        self.present()

    @staticmethod
    def draw_func(d, cr, w, h):
        self = d.get_root()
        if self.drag_start == (0, 0) or self.single_pixel: return
        ds = self.compute_point(self.draw.get_parent(), Graphene.Point.init(Graphene.Point(), *self.drag_start))[-1]
        dt = self.compute_point(self.draw.get_parent(), Graphene.Point.init(Graphene.Point(), *self.drag_to))[-1]
        self.x, self.y = min(ds.x, dt.x), min(ds.y, dt.y)
        self.square_width, self.square_height = abs(dt.x - ds.x), abs(dt.y - ds.y)
        cr.set_source_rgba(0, 0, 0, 0.4)
        cr.rectangle(0, 0, w, h)
        cr.fill()
        cr.set_operator(0)
        cr.rectangle(self.x, self.y, self.square_width, self.square_height)
        cr.fill()
        cr.set_operator(2)

    @staticmethod
    def on_gesture_drag_drag_begin(e, x, y):
        self = e.get_widget()
        if self.single_pixel: return e.reset()
        self.drag_start = (x, y)
        self.drag_to = (x, y)

    @staticmethod
    def on_gesture_drag_drag_update(e, x, y):
        self = e.get_widget()
        if self.single_pixel: return e.reset()
        Window.draw_drag_update(e, x, y)

    @staticmethod
    def on_click(e, *args):
        self = e.get_widget().get_root()
        b = e.get_current_button()
        if isinstance(e, Gtk.GestureClick):
            n, x, y, signal = args
        else:
            x, y, signal = args
        e.set_state(Gtk.EventSequenceState.NONE)
        Task.invoke(e.reset)
        if b != 1: return self.finish(abort=True)
        if signal != "pressed": return
        if not self.single_pixel: return
        self.x, self.y = x, y
        self.square_width = self.square_height = 1
        self.finish()

    def finish(self, abort=False):
        if abort or not self.get_surface():
            args = False
        else:
            args = (self.get_display().get_monitor_at_surface(self.get_surface()), self.x or -1, self.y or -1, self.square_width, self.square_height)
        self.close()
        if self.function and self.function_data != None: Task.invoke(self.function, args, self.function_data)
        elif self.function: Task.invoke(self.function, args)

    @staticmethod
    def on_gesture_drag_drag_end(e, x, y):
        self = e.get_widget()
        if self.single_pixel or not self.get_mapped(): return
        Window.reset_draw(self)
        if self.square_width == 0 and self.square_height == 0: return
        self.finish()

    @staticmethod
    def on_key_pressed(e, v, c, s):
        if v == Gdk.KEY_Escape: e.get_widget().get_root().finish(abort=True)

class Background(LayerShell):
    __gtype_name__ = "Background"
    clock = GObject.Property(type=Gtk.MenuButton)
    current = False
    instance = None

    def __init__(self):
        super().__init__(target=True)
        self.__class__.instance = self
        self.overlay = Gtk.Overlay(child=Gtk.Picture(paintable=EMPTY_PAINTABLE, opacity=0.1))
        self.set_content(self.overlay)
        features = ["Apps", "Background", "Clipboard Manager", "Notifications Agent", "Player Agent", "Polkit Agent", "Portals", "Shell DBUS", "Virtual Keyboard", "Virtual Pointer", "Wallpaper", "Wayland Client"]
        for i in features: App.default.data.persist_action(self, i, (i, True), "Settings", "Value", "Key = ?", (i,))
        features = {"Features": dict((i, f"win.{i.lower().replace(' ', '-')}") for i in features)}
        menu = Menu({
            "Show Clock": "win.clock",
            "Clock Format": "win.change-clock-format",
            "!a": Menu({"Second Clock": "win.clock-update::Second", "Minute Clock": "win.clock-update::Minute",}),
            "!b": Menu(features),
            })
        self.context = Gtk.PopoverMenu(menu_model=menu, has_arrow=False)
        self.add_action(Gio.SimpleAction.new("change-clock-format"))
        self.lookup_action("change-clock-format").connect("activate", self.__class__.change_clock_format)
        App.default.data.persist_action(self, "Clock Format", ("Background Clock Format", "%H:%M"), "Settings", "Value", "Key = ?", ("Background Clock Format",))
        App.default.data.persist_action(self, "Clock Update", ("Background Clock Update", "Minute"), "Settings", "Value", "Key = ?", ("Background Clock Update",)).connect("notify::state", self.update_clock)
        App.default.data.persist_action(self, "Clock", ("Background Show Clock", False), "Settings", "Value", "Key = ?", ("Background Show Clock",)).connect("notify::state", self.toggle_clock)
        self.toggle_clock()
        self.present()

    @staticmethod
    def on_event_enter(e, x, y): Task.invoke(Wallpaper.instance.remove_css_class, "overview")

    def do_change_clock_format(d):
        self = Background.instance
        if not self: return
        self.lookup_action("clock-format").set_state(get_variant(d.get_extra_child().get_text()))

    def change_clock_format(*_):
        self = Background.instance
        if not self: return
        d = EntryPrompt(heading="Clock Format", callback=Background.do_change_clock_format)
        d.present()
        d.get_extra_child().set_text(self.lookup_action("clock-format").get_state().unpack())

    def on_click(e, *args):
        self = e.get_widget().get_root()
        b = e.get_current_button()
        if isinstance(e, Gtk.GestureClick):
            n, x, y, signal = args
        else:
            x, y, signal = args
        if signal != "pressed": return
        w = self.overlay.pick(x, y, Gtk.PickFlags.DEFAULT)
        w = w.get_ancestor(Gtk.MenuButton) if w else None
        if w: return w.set_active(not w.get_active())
        if isinstance(e, Gtk.GestureClick) and b != 3: return
        self.show_popover_at_widget(self.context, self, x, y)

    @staticmethod
    def update_clock(*_):
        self = Background.instance
        if not self: return
        if self.current: GLib.source_remove(self.current)
        self.current = False
        mono_us = GLib.get_monotonic_time()
        us_until_next = 1e6 - (mono_us % 1e6)
        ms_until_next = max(1, us_until_next // 1e3)
        GLib.timeout_add(ms_until_next, self.align)

    @staticmethod
    def toggle_clock(*_):
        self = Background.instance
        if not self: return
        s = self.lookup_action("clock").get_state().unpack()
        if s and not self.clock:
            self.clock = Gtk.MenuButton(css_classes=("clock",), hexpand=True, vexpand=True, halign=Gtk.Align.CENTER, valign=Gtk.Align.START, popover=Gtk.Popover(child=Gtk.Calendar()), child=Gtk.Label())
            self.get_content().add_overlay(self.clock)
        if self.clock: self.clock.set_visible(s)
        if not s: return
        self.update_clock()

    def update(self):
        self.current = False
        self.clock.get_child().set_label(GLib.DateTime.new_now_local().format(self.lookup_action("clock-format").get_state().unpack()))
        return self.clock.get_visible()

    def align(self):
        self.update()
        if self.current: GLib.source_remove(self.current)
        self.current = GLib.timeout_add(1e3 * (60 if self.lookup_action("clock-update").get_state().unpack() == "Minute" else 1), self.update)

class Wallpaper(LayerShell):
    __gtype_name__ = "Wallpaper"
    overlay = GObject.Property(type=Gtk.Overlay)
    before = GObject.Property(type=Adw.Bin)
    instance = None

    def __init__(self):
        super().__init__()
        WM.connect("notify::is-overview", self.__class__.overview_changed)
        self.__class__.instance = self
        self.overlay = Gtk.Overlay(child=Adw.Bin())
        self.before = Adw.Bin(css_name="before", hexpand=True, vexpand=True)
        self.overlay.add_overlay(self.before)
        self.set_content(self.overlay)

    @staticmethod
    def overview_changed(*_):
        if Wallpaper.instance: Task.invoke(Wallpaper.instance.add_css_class if WM.is_overview else Wallpaper.instance.remove_css_class, "overview")

class GamepadEmulator:
    cross = 304
    circle = 305
    square = 307
    triangle = 308
    lx = 0
    ly = 1
    lt = 2
    rx = 3
    ry = 4
    rt = 5
    l1 = 310
    r1 = 311
    share = 314
    options = 315
    l3 = 317
    r3 = 318
    ps = 316
    leftright, updown = 16, 17

    def __init__(self):
        super().__init__()
        self.fd = os_open("/dev/uinput", O_WRONLY | O_NONBLOCK)
        e = 0x40045564
        for i in [self.circle, self.cross, self.triangle, self.square, self.l1, self.r1, self.share, self.options, self.l3, self.r3, self.ps]:
            ioctl(self.fd, e, 1)
            ioctl(self.fd, 0x40045565, i)
        for i in [self.lx, self.ly, self.lt, self.rx, self.ry, self.rt, self.leftright, self.updown]:
            ioctl(self.fd, e, 3)
            ioctl(self.fd, 0x40045567, i)
        absmin = [0] * 64
        absmax = [0] * 64
        absmin[self.lx] = 0
        absmax[self.lx] = 255
        absmin[self.ly] = 0
        absmax[self.ly] = 255
        absmin[self.rx] = 0
        absmax[self.rx] = 255
        absmin[self.ry] = 0
        absmax[self.ry] = 255
        absmin[self.lt] = 0
        absmax[self.lt] = 255
        absmin[self.rt] = 0
        absmax[self.rt] = 255
        absmin[self.leftright] = -1
        absmax[self.leftright] = 1
        absmin[self.updown] = -1
        absmax[self.updown] = 1
        uidev = pack("80sHHHHI", b"Microsoft X-Box 360 pad", 0x03, 1118, 654, 272, 0)
        uidev += pack("64i", *absmax)
        uidev += pack("64i", *absmin)
        uidev += pack("64i", *([0] * 64))
        uidev += pack("64i", *([0] * 64))
        write(self.fd, uidev)
        ioctl(self.fd, 0x5501)

    def handle(self, name, v):
        if name in ("circle", "cross", "triangle", "square", "share", "options", "l1", "r1", "l3", "r3"): self.button(getattr(self.__class__, name), v)
        if name in ("rx", "ry", "rt", "ly", "lx", "lt"): self.axis(getattr(self.__class__, name), v)
        if name == "left": self.axis(self.leftright, -1 if v else 0)
        if name == "right": self.axis(self.leftright, 1 if v else 0)
        if name == "up": self.axis(self.updown, -1 if v else 0)
        if name == "down": self.axis(self.updown, 1 if v else 0)

    def dispose(self):
        try:
            ioctl(self.fd, 0x5502)
            close(self.fd)
        except: pass
        if hasattr(self, "fd"):
            del self.fd

    def emit(self, etype, code, value):
        if not hasattr(self, "fd"): return
        try: write(self.fd, pack("llHHi", 0, 0, etype, code, value))
        except: self.dispose()

    def sync(self): self.emit(0x00, 0, 0)

    def axis(self, code, value):
        self.emit(0x03, code, value)
        self.sync()

    def button(self, code, pressed):
        self.emit(0x01, code, int(pressed))
        self.sync()

class Controller(GObject.Object):
    __gtype_name__ = "Controller"
    type = GObject.Property(type=str)
    sink_name = GObject.Property(type=str)
    device = GObject.Property(type=str)
    addr = GObject.Property(type=str)
    audio_id = GObject.Property(type=str)
    report_size = GObject.Property(type=int)
    valid_report_id = GObject.Property(type=int)
    battery = GObject.Property(type=int)
    charging = GObject.Property(type=bool, default=False)

    audio_output = GObject.Property(type=str, default="None")

    _1_zero = bytearray(1)
    _4_zeros = bytearray(4)

    @GObject.Property(type=bool, default=False)
    def grabbed(self): return getattr(self, "_grabbed", False)

    @grabbed.setter
    def grabbed(self, value):
        self._grabbed = value
        self.rgb = self.rgb
        if not hasattr(self, "event_devices"): return
        for i in self.event_devices:
            try: ioctl(i, 0x40044590, int(self.grabbed))
            except: pass
    locked = GObject.Property(type=bool, default=False)

    mouse_sensitivity = GObject.Property(type=float, default=8.0, minimum=1.0, maximum=100.0)
    scroll_sensitivity = GObject.Property(type=float, default=6.0, minimum=1.0, maximum=100.0)

    weak_rumble = GObject.Property(type=int, minimum=0, maximum=100)
    strong_rumble = GObject.Property(type=int, minimum=0, maximum=100)
    flash_bright = GObject.Property(type=int)
    flash_dark = GObject.Property(type=int)
    volume_headphones = GObject.Property(type=int, default=50, minimum=0, maximum=100)
    volume_microphone = GObject.Property(type=int, default=50, maximum=100)
    volume_speakers = GObject.Property(type=int, default=50, minimum=0, maximum=100)

    audio_pipeline = GObject.Property(type=GObject.Object)

    headphones = GObject.Property(type=bool, default=False)
    microphone = GObject.Property(type=bool, default=False)
    ext = GObject.Property(type=bool, default=False)

    rgb = GObject.Property(type=Gdk.RGBA)

    @GObject.Property(type=bool, default=False)
    def emulate_xbox_gamepad(self): return getattr(self, "_emulate_xbox_gamepad", False)

    @emulate_xbox_gamepad.setter
    def emulate_xbox_gamepad(self, value):
        self._emulate_xbox_gamepad = value
        if not self.emulate_xbox_gamepad and hasattr(self, "emulator"):
            self.emulator.dispose()
            del self.emulator
        if self.emulate_xbox_gamepad and not hasattr(self, "emulator"):
            self.grabbed = True
            self.emulator = GamepadEmulator()
        elif not self.desktop:
            self.grabbed = True

    @GObject.Property(type=bool, default=False)
    def desktop(self): return getattr(self, "_desktop", False)

    @desktop.setter
    def desktop(self, value):
        self._desktop = value
        if self.desktop:
            self.grabbed = True
        elif not self.emulate_xbox_gamepad:
            self.grabbed = False

    def __init__(self, device, info, t):
        self.sent_battery_notification = False
        self.comboed = set()
        super().__init__()
        self.device = device
        self.type = t
        self.addr = info.split("HID_UNIQ=", 1)[-1].split("\n", 1)[0].upper()
        if Controller.list[self.addr]: return
        if self.type == "bluetooth":
            self.report_size = 78
            self.valid_report_id = 0x11
        else:
            self.report_size = 64
            self.valid_report_id = 0x01
        self.report_fd = os_open(device, O_RDWR)
        self.fd = FileIO(self.report_fd, "wb+", closefd=False)
        self.buf = bytearray(self.report_size)
        self.event_devices = []
        n = basename(device)
        r = f"/sys/class/hidraw/{n}/device/input/"
        for inp in list_dir(r):
            for i in list_dir(Path(r, inp)):
                if i.startswith("event"): self.event_devices.append(os_open(f"/dev/input/{i}", O_RDONLY))
        if Gst and self.type == "bluetooth":
            self.sink_name = f'shell-ds4-{self.addr.replace(":", "-")}'
            self.connect("notify::audio-output", self.__class__.audio_changed)
        Task(self.read).start()
        for i in ("rgb", "volume-headphones", "volume-microphone", "volume-peakers", "weak-rumble", "strong-rumble"): self.connect(f"notify::{i}", self.__class__.setting_changed)
        self.rgb = RGBA("#000000")
        self.__class__.list.append(self)

    @staticmethod
    def setting_changed(self, p):
        if (not self.audio_pipeline or self.audio_output == "None") and hasattr(self, "fd"):
            try: self.fd.write(self._11_report() if self.type == "bluetooth" else self._05_report())
            except: Task.invoke(self.remove)

    @staticmethod
    def audio_changed(self, p):
        if not Gst: return
        if self.audio_output == "None":
            if self.audio_id: GLib.spawn_command_line_async(f"pactl unload-module {self.audio_id}")
            self.audio_id = ""
            MediaStream.destroy_pipeline(self.audio_pipeline)
            self.audio_pipeline = None
        elif not self.audio_pipeline:
            if not Gst.is_initialized(): Gst.init()
            if not Gst.ElementFactory.find("sbcenc"):
                print("Controller: sbcenc not found")
                return
            rate = "48000"
            channels = "2"
            self.audio_id = GLib.spawn_command_line_sync(f'pactl load-module module-null-sink sink_name="{self.sink_name}" rate="{rate}" channels="{channels}" sink_properties="device.description=\'DualShock\\ 4\'"')[1].decode("utf-8").split("\n")[0]
            self.audio_pipeline = Gst.parse_bin_from_description(f'pulsesrc device="{self.sink_name}.monitor" ! sbcenc ! audio/x-sbc,channels={channels},rate={rate},channel-mode={"stereo" if channels == "2" else "mono"},blocks=16,subbands=8,bitpool=30 ! queue ! appsink async=false sync=false emit-signals=true name=Sink')
            self.audio_pipeline.get_by_name("Sink").connect("new-sample", self.__class__.new_sample, self)
            self.audio_pipeline.set_state(Gst.State.PLAYING)

    def get_controls(self):
        wr = format(int(self.weak_rumble % 255), "02x")
        sr = format(int(self.strong_rumble % 255), "02x")
        r = format(int(self.rgb.red * 255), "02x")
        g = format(int(self.rgb.green * 255), "02x")
        b = format(int(self.rgb.blue * 255), "02x")
        fb = format(self.flash_bright, "02x")
        fd = format(self.flash_dark, "02x")
        vl = format(0 if not self.audio_output == "Headset" else int((self.volume_speakers / 0x4F) * 100), "02x")
        vr = format(0 if not self.audio_output == "Headset" else int((self.volume_speakers / 0x4F) * 100), "02x")
        vm = format(int((max(0x01, self.volume_microphone) / 0x40) * 100), "02x")
        vs = format(0 if not self.audio_output == "Speakers" else int((self.volume_speakers / 0x4F) * 100), "02x")
        d = (b"\xF3" if self.type == "bluetooth" else b"\xF7") + (self.__class__._1_zero * 2)
        unk1 = format(5, "02x")
        unk2 = format(1, "02x")
        d += bytes.fromhex(f"{wr} {sr} {r} {g} {b} {fb} {fd}")
        d += self.__class__._1_zero * 8
        d += bytes.fromhex(f"{vl} {vr} {vm} {vs} {unk1} {unk2}")
        d += self.__class__._1_zero * (70 - len(d))
        return d

    def frame_number(self, inc):
        n = getattr(self, "frame_n", 0)
        res = pack("<H", n)
        self.frame_n = n + inc
        if self.frame_n > 0xFFFF:
          self.frame_n = 0
        return res

    def _05_report(self):
        data = b"\x05" + self.get_controls()
        data += self.__class__._1_zero * (32 - len(data))
        return data

    def _11_report(self):
        data = b"\x11\x00\xFF" + self.get_controls()
        data += self.__class__._1_zero * (78 - len(data))
        return data

    def _19_report(self, ad):
        audio_header = bytes(0x24 if self.audio_output == "Headset" else 0x02 if self.audio_output == "Speakers" else 0x03)
        if self.audio_output == "None":
            ad = self.__class__._1_zero
        data = b"\x19\x00\xFF" + self.get_controls() + self.__class__._4_zeros + self.frame_number(4) + audio_header + ad
        data += self.__class__._1_zero * (547 - len(data))
        return data

    @staticmethod
    def new_sample(sink, self):
        sample = sink.emit("pull-sample")
        if sample is None: return Gst.FlowReturn.ERROR
        buffer = sample.get_buffer()
        success, map_info = buffer.map(Gst.MapFlags.READ)
        if success:
            data = bytes(map_info.data)
            try: self.fd.write(self._19_report(data))
            except: pass
            buffer.unmap(map_info)
        return Gst.FlowReturn.OK

    def read(self):
        while True:
            try:
                ret = self.fd.readinto(self.buf)
            except: break
            if ret < self.report_size or self.buf[0] != self.valid_report_id: print(self.addr, "weird report", [hex(i) for i in self.buf])
            else: self.handle_report(memoryview(self.buf))

    def handle_report(self, buf):
        n = 0 if self.type == "bluetooth" else -2
        info = buf[n+32]
        charging = (info & 0x10) != 0
        battery = info & 0x0F
        if self.charging != charging or self.battery != battery:
            self.charging = charging
            self.battery = battery
            if self.type == "bluetooth" and not self.charging and 2 > self.battery:
                if not self.sent_battery_notification:
                    self.sent_battery_notification = True
                    Notification(app=App.default.get_application_id(), title="DualShock 4", description=f"{self.addr}\n10% battery remaining")
            else: self.sent_battery_notification = False
        c = buf[n+9]
        self.handle_value("ps", (c & 1) != 0)
        if not self.grabbed or self.locked: return
        self.handle_value("touchpad", (c & 2) != 0)
        self.handle_value("lx", buf[n+3], False, True)
        self.handle_value("ly", buf[n+4], False, True)
        self.handle_value("rx", buf[n+5], False, True)
        self.handle_value("ry", buf[n+6], False, True)
        self.handle_value("lt", buf[n+10], False, True)
        self.handle_value("rt", buf[n+11], False, True)
        b = buf[n+7]
        self.handle_value("cross", (b & 32) != 0)
        self.handle_value("circle", (b & 64) != 0)
        self.handle_value("triangle", (b & 128) != 0)
        self.handle_value("square", (b & 16) != 0)
        m = buf[n+8]
        self.handle_value("options", (m & 32) != 0)
        self.handle_value("share", (m & 16) != 0)
        d = buf[n+7] % 16
        self.handle_value("up", d in (0, 1, 7))
        self.handle_value("down", d in (3, 4, 5))
        self.handle_value("left", d in (5, 6, 7))
        self.handle_value("right", d in (1, 2, 3))
        t = buf[n+8]
        self.handle_value("r1", (t & 2) != 0)
        self.handle_value("r2", (t & 8) != 0)
        self.handle_value("r3", (t & 128) != 0)
        self.handle_value("l1", (t & 1) != 0)
        self.handle_value("l2", (t & 4) != 0)
        self.handle_value("l3", (t & 64) != 0)
        self.handle_value("headphones", (info & 0x20) != 0, False)
        self.handle_value("microphone", (info & 0x40) != 0, False)
        self.handle_value("ext", (info & 0x80) != 0, False)

    def press(self, a=""):
        if self.locked:
            GLib.timeout_add(100, self.press, a)
            return
        self.locked = True
        self.handle_value(a, True, force=True)
        GLib.timeout_add(50, self.unpress, a)

    def unpress(self, a=""):
        self.locked = True
        self.handle_value(a, False, force=True)
        self.locked = False

    def scroll(self, t):
        request_sent = False
        x, y = [getattr(self, f"{t}{i}", 128) for i in ("x", "y")]
        for h, v in (("y", y), ("x", x)):
            v = self.analog_normalize(v) * self.scroll_sensitivity
            if v != 0:
                h = 0 if h == "y" else 1
                request_sent = True
                Pointer.pointer.axis_source(0)
                Pointer.pointer.axis(0, h, v)
                Pointer.pointer.frame()
                Pointer.pointer.axis_source(0)
                Pointer.pointer.axis_stop(0, h)
                Pointer.pointer.frame()
        return request_sent

    def mouse(self, t):
        request_sent = False
        x, y = [getattr(self, f"{t}{i}", 128) for i in ("x", "y")]
        motionx = self.analog_normalize(x) * self.mouse_sensitivity
        motiony = self.analog_normalize(y) * self.mouse_sensitivity
        if (motionx != 0 or motiony != 0):
            request_sent = True
            Pointer.pointer.motion(0, motionx, motiony)
            Pointer.pointer.frame()
        return request_sent

    def keyboard_handle(self, kb, name, v):
        if name == "lx": kb.move_x(self.analog_normalize(self.lx))
        if name == "ly": kb.move_y(self.analog_normalize(self.ly))
        if name == "rx": kb.move_x(self.analog_normalize(self.rx))
        if name == "ry": kb.move_y(self.analog_normalize(self.ry))
        if name == "cross": kb.confirm(v)
        if name == "circle": kb.cancel(v)
        if name == "square": self.send(Keyboard, "backspace", v)
        if name == "triangle": self.send(Keyboard, "space", v)
        if name == "l1": self.send(Keyboard, "left", v)
        if name == "r1": self.send(Keyboard, "right", v)
        if name == "r2":
            self.send(Keyboard, "enter", v)
            if not v: kb.close()
        if name == "l2": Task.invoke(kb.modifiers["Shift"].set_active, v)
        if name == "share" and v: Task.invoke(kb.modifiers["Ctrl"].set_active, not kb.modifiers["Ctrl"].get_active())
        if name == "options" and v: Task.invoke(kb.modifiers["Super"].set_active, not kb.modifiers["Super"].get_active())
        if name == "l3" and v: Task.invoke(kb.modifiers["Symbol"].set_active, not kb.modifiers["Symbol"].get_active())
        if name == "r3" and v: Task.invoke(kb.toggle_context)
        if name in ("up", "down", "left", "right"): kb.move_focus(name, v)
        if name == "touchpad" and v: kb.close()

    def send(self, cls, k, v): cls.send(key=k, hold=v, release=not v)

    @staticmethod
    def changed(self, name):
        name = name if isinstance(name, str) else name.get_name()
        v = getattr(self, name, False)
        if name in self.comboed:
            if not v: self.comboed.remove(name)
            return
        if name == "ps" and not v:
            self.desktop = not self.desktop
            return
        kb = Keyboard.instance
        if kb and kb.get_mapped(): return self.keyboard_handle(kb, name, v)
        if not self.desktop and hasattr(self, "emulator"):
            self.emulator.handle(name, v)
            return
        if not self.desktop: return
        if WM.is_overview:
            if name in ("rx", "ry"):
                if getattr(self, "r_reseted", False):
                    if v > 128:
                        Niri.request("Action", { f"Focus{'Workspace' if 'y' in name else 'Column'}{'Down' if 'y' in name else 'Right'}": {} })
                    if 128 > v:
                        Niri.request("Action", { f"Focus{'Workspace' if 'y' in name else 'Column'}{'Up' if 'y' in name else 'Left'}": {} })
                setattr(self, "r_reseted", self.ry == 128 and self.rx == 128)
            elif name == "ly" and self.mouse("l"): Gdk.Display.get_default().flush()
        else:
            if name == "ry" and (self.mouse("l") or self.scroll("r")): Gdk.Display.get_default().flush()
        if name == "r3" and v: Niri.request("Action", { "ToggleOverview": {}})
        if name == "l3" and v: self.comboed.add("l3")
        if name == "cross":
            if getattr(self, "ps", False) and v:
                self.comboed.add("ps")
                self.comboed.add(name)
                call(i=PLAYER_IFACE, m="Next")
            else:
                self.send(Pointer, "Left", v)
        if name == "circle":
            if getattr(self, "ps", False) and v:
                self.comboed.add("ps")
                self.comboed.add(name)
                call(i=PLAYER_IFACE, m="Previous")
            else:
                self.send(Pointer, "Right", v)
        if name == "triangle":
            if getattr(self, "ps", False) and v:
                self.comboed.add("ps")
                self.comboed.add(name)
                call(i=PLAYER_IFACE, m="PlayPause")
            else:
                self.send(Pointer, "Middle", v)
        if name == "square":
            if getattr(self, "ps", False) and v:
                self.comboed.add("ps")
                self.comboed.add(name)
                call(i=PLAYER_IFACE, m="Shift")
            elif WM.is_overview and v: Niri.request("Action", { "CloseWindow": {} })
        if name == "r2":
            if getattr(self, "ps", False) and v:
                self.comboed.add("ps")
                self.comboed.add(name)
                GLib.spawn_command_line_async("pactl set-sink-volume @DEFAULT_SINK@ +5%")
            elif "l3" in self.comboed:
                self.send(Keyboard, "Ctrl", v)
                self.send(Keyboard, "W", v)
            elif not v:
                for v in (True, False):
                    self.send(Keyboard, "Ctrl", v)
                    self.send(Keyboard, "Tab", v)
        if name == "l2":
            if getattr(self, "ps", False) and v:
                self.comboed.add("ps")
                self.comboed.add(name)
                GLib.spawn_command_line_async("pactl set-sink-volume @DEFAULT_SINK@ -5%")
            elif "l3" in self.comboed:
                self.send(Keyboard, "Ctrl", v)
                self.send(Keyboard, "Shift", v)
                self.send(Keyboard, "T", v)
            elif not v:
                for v in (True, False):
                    self.send(Keyboard, "Ctrl", v)
                    self.send(Keyboard, "Shift", v)
                    self.send(Keyboard, "Tab", v)
        if name == "r1":
            if getattr(self, "ps", False) and v:
                self.comboed.add("ps")
                self.comboed.add(name)
                call(i=PLAYER_IFACE, m="Forward")
            elif v and Pointer.instance: Pointer.send("EXTRA")
        if name == "l1":
            if getattr(self, "ps", False) and v:
                self.comboed.add("ps")
                self.comboed.add(name)
                call(i=PLAYER_IFACE, m="Backward")
            elif v and Pointer.instance: Pointer.send("SIDE")
        if name in ("up", "down", "left", "right"):
            if WM.is_overview and v:
                self.comboed.add(name)
                Niri.request("Action", { f"Focus{'Workspace' if name in ('up', 'down') else 'Column'}{name.title()}": {} })
            elif getattr(self, "r2", False) and name in ("up", "down"):
                self.comboed.add("r2")
                self.send(Keyboard, "Home" if name == "up" else "End", v)
            elif getattr(self, "l2", False) and name in ("up", "down"):
                self.comboed.add("l2")
                self.send(Keyboard, f"Page{name.title()}", v)
            else: self.send(Keyboard, name, v)
        if name == "touchpad" and v: Task.invoke(Keyboard.do)
        if name == "share" and v: Task.invoke(Controllers.do)
        if name == "options" and v: Task.invoke(Apps.do)

    def handle_value(self, name, value, g=True, force=False):
        v = getattr(self, name, None)
        if v != value:
            setattr(self, name, value)
            if g and v != None: return self.__class__.changed(self, name)
        if force: return self.__class__.changed(self, name)

    @staticmethod
    def analog_normalize(v): return max(-1.0, min(1.0, (v - 128) / 128))

    def remove(self):
        self.type = "none"
        self.desktop = self.emulate_xbox_gamepad = False
        self.grabbed = False
        if hasattr(self, "fd"):
            del self.fd
        self.audio_output = "None"
        self.__class__.list.remove(self)

Controller.list = List(Controller, "addr")

class ControllerItem(Adw.Bin):
    __gtype_name__ = "ControllerItem"
    controller = GObject.Property(type=Controller)
    led_row = GObject.Property(type=ColorRow)
    emulate_row = GObject.Property(type=Adw.SwitchRow)
    audio_output_row = GObject.Property(type=ToggleGroupRow)
    def __init__(self):
        super().__init__(child=Adw.PreferencesGroup())
        self.bindings = []
        self.connect("notify::controller", self.__class__.controller_changed)
        self.led_row = ColorRow(title="LED", with_alpha=False)
        self.emulate_row = Adw.SwitchRow(title="Emulate Xbox Gamepad")
        self.audio_output_row = ToggleGroupRow(title="Audio Output", toggles=[Adw.Toggle(tooltip=a, icon_name=b + "-symbolic", name=a) for a, b in (("Speakers", "audio-speakers"), ("Headset", "audio-headset"), ("None", "audio-volume-muted"))])
        self.audio_output_row.active = "None"
        for i in (self.led_row, self.emulate_row, self.audio_output_row): self.get_child().add(i)
        for n, g in (("volume", ("volume headphones", "volume microphone", "volume speakers")), ("rumble", ("weak rumble", "strong rumble"))):
            e = Adw.ExpanderRow(title=n.title())
            for i in g:
                r = ScaleRow(title=i.replace(n, "").strip().title())
                p = f"{i.replace(' ', '_')}"
                setattr(self, p, r)
                e.add_row(r)
            self.get_child().add(e)
        self.battery_button = Button(callback=self.__class__.disconnect, css_classes=["flat", "circular"], bindings=[(None, "icon-name", None, "tooltip-text", None, self.__class__.battery_tooltip_bind)])
        self.get_child().set_header_suffix(self.battery_button)

    @staticmethod
    def disconnect(b):
        self = b.get_ancestor(ControllerItem)
        if self.controller:
            if self.controller.type == "bluetooth": GLib.spawn_command_line_async(f"/usr/bin/bluetoothctl disconnect {self.controller.addr}")
            self.controller.remove()

    @staticmethod
    def controller_changed(self, p=None):
        for i in getattr(self, "bindings", []): i.unbind()
        self.bindings = []
        if self.controller:
            self.bindings.append(self.controller.bind_property("addr", self.get_child(), "title", DEFAULT_BIND))
            self.bindings.append(self.controller.bind_property("rgb", self.led_row, "rgba", SYNC_BIND))
            self.bindings.append(self.controller.bind_property("emulate-xbox-gamepad", self.emulate_row, "active", SYNC_BIND))
            self.bindings.append(self.controller.bind_property("type", self.audio_output_row, "visible", DEFAULT_BIND, self.__class__.bluetooth_bind))
            self.bindings.append(self.controller.bind_property("audio-output", self.audio_output_row, "active", SYNC_BIND))
            self.bindings.append(self.controller.bind_property("type", self.battery_button, "visible", DEFAULT_BIND, self.__class__.bluetooth_bind))
            self.bindings.append(self.controller.bind_property("battery", self.battery_button, "icon-name", DEFAULT_BIND, self.__class__.battery_icon_bind))
            for i in ("volume_headphones", "volume_microphone", "volume_speakers", "weak_rumble", "strong_rumble"): self.bindings.append(self.controller.bind_property(i.replace("_", "-"), getattr(self, i), "value", SYNC_BIND))


    @staticmethod
    def bluetooth_bind(b, v): return v == "bluetooth"

    @staticmethod
    def battery_tooltip_bind(b, v): return v.replace("-symbolic", "").replace("battery-", "").replace("level-", "").replace("-", " ").title() if v else ""

    @staticmethod
    def battery_icon_bind(b, v):
        v = "full" if v == 10 else ("level-" + str(v) + "0")
        if b.get_source().charging:
            v += "-plugged-in" if b.get_source().type == "usb" else f"-charg{'ed' if v == 'full' else 'ing'}"
        v = "battery-" + v.replace("full-plugged", "level-100-plugged") + "-symbolic"
        return v

    factory = Gtk.SignalListItemFactory.new()
    @staticmethod
    def setup(f, l): l.set_child(ControllerItem())
    factory.connect("setup", setup)
    @staticmethod
    def bind(f, l):
        if not l.get_child(): return
        l.get_child().controller = l.get_property("item")
        Task.invoke(l.get_child().get_parent().set_properties, css_classes=[], focusable=False      )
    factory.connect("bind", bind)
    @staticmethod
    def unbind(f, l):
        l.get_child().controller = None
    factory.connect("unbind", unbind)
    @staticmethod
    def teardown(f, l): l.set_child(None)
    factory.connect("teardown", teardown)

class Controllers(Window):
    __gtype_name__ = "Controllers"
    instance = None
    def __init__(self):
        super().__init__()
        status = Adw.StatusPage(title="No Controllers", icon_name="input-gaming-symbolic")
        Controller.list.bind_property("n-items", status, "visible", DEFAULT_BIND, invert_bool_bind)
        self.__class__.instance = self
        view = Gtk.ListView(model=Gtk.NoSelection(model=Controller.list), factory=ControllerItem.factory)
        view.set_css_classes([])
        overlay = Gtk.Overlay(child=Gtk.ScrolledWindow(child=view))
        overlay.add_overlay(status)
        toolbar = Adw.ToolbarView(content=overlay)
        toolbar.add_top_bar(Adw.HeaderBar())
        self.set_content(toolbar)
        self.set_properties(title="Controllers", hide_on_close=True, default_height=370, default_width=400)
        Task.invoke(self.start)

    def start(self):
        try:
            previous = GLib.spawn_command_line_sync("pactl list short")[1].decode("utf-8").split("\n")
            for i in previous:
                if "sink_name=shell-ds4" in i:
                    _id = i.split("\t", 1)[0]
                    GLib.spawn_command_line_async(f"pactl unload-module {_id}")
        except: pass
        for i in list_dir("/dev"):
            if i.startswith("hidraw"): Task.invoke(self.try_hidraw, f"/dev/{i}")
        self.monitor = Gio.File.new_for_path("/dev").monitor_directory(Gio.FileMonitorFlags.NONE)
        self.monitor.connect("changed", self.__class__.changed, self)

    def try_hidraw(self, device):
        info = GLib.spawn_command_line_sync(f"udevadm info -t -q all -n {device}")[1].decode("utf-8")
        name = info.split("HID_NAME=", 1)[-1].split("\n", 1)[0]
        if name in ("Wireless Controller",): Controller(device, info, "bluetooth")
        elif name in ("Sony Computer Entertainment Wireless Controller", "Sony Interactive Entertainment Wireless Controller"): Controller(device, info, "usb")

    @staticmethod
    def changed(m, f, fo, t, self):
        path = f.get_path()
        name = basename(path)
        if name.startswith("hidraw"):
            if t == Gio.FileMonitorEvent.DELETED:
                for i in Controller.list:
                    if i.device == path: Task.invoke(i.remove)
            if t == Gio.FileMonitorEvent.CREATED: GLib.timeout_add(1000, self.try_hidraw, path)

    @staticmethod
    def do():
        if Controllers.instance.get_mapped(): Controllers.instance.close()
        else: Controllers.instance.present()

class EventCodes:
    @staticmethod
    def get():
        if getattr(EventCodes, "codes", False): return
        EventCodes.codes = {}
        try:
            p = "/usr/include/linux/input-event-codes.h"
            if FLATPAK_ID:
                p = Path(ROOT, p)
            codes = get_contents(p).decode()
            for line in codes.split("\n"):
                if not (line and line.startswith("#define")): continue
                line = line.split("#define", 1)[-1].split("/*", 1)[0].strip(" \t").replace(" + ", "+")
                line = " ".join([i.strip(" \t") for i in line.split("\t") if i.strip(" \t")])
                line = [i.strip(" \t") for i in line.split(" ") if i.strip(" \t")]
                if len(line) != 2: continue
                name, value = line
                try:
                    if value.startswith("0x"):
                        value = int(value, 0)
                    else:
                        value = int(value)
                except:
                    value = eval(value, EventCodes.codes, EventCodes.codes)
                EventCodes.codes[name] = int(value)
        except Exception as e: print("Couldn't get event codes", e)

class Pointer:
    aliases = {}
    instance = None
    def __init__(self):
        if not Data.setting("Virtual Pointer", True): return
        self.get_codes()
        p = "zwlr_virtual_pointer_manager_v1"
        vp = p.replace("_manager", "")
        WlInterface(vp, version=2, requests=[("motion", "uff"), ("motion_absolute", "uuuuu"), ("button", "uuu"), ("axis", "uuf"), ("frame", ""), ("axis_source", "u"), ("axis_stop", "uu"), ("axis_discrete", "uufi"), ("destroy", "")])
        p = WlInterface(p, version=2, requests=[("create_virtual_pointer", "on", WlInterface.types("seat", vp)), ("destroy", ""), ("create_virtual_pointer_with_output", "oon", WlInterface.types("seat", "output", vp))])
        if Wayland.interfaces.get(p.name.decode(), (0, 0))[1] == p.version:
            seat = WlProxy.get(WlInterface["seat"], gtk_get_pointer(Gdk.Display.get_default().get_default_seat(), "gdk_wayland_seat_get_wl_seat"))
            self.__class__.pointer = Wayland.registry.bind(p, *Wayland.interfaces[p.name.decode()]).create_virtual_pointer(seat)
            self.__class__.instance = self
        super().__init__()

    @staticmethod
    def get_codes():
        if getattr(Pointer, "keycodes", False): return
        EventCodes.get()
        Pointer.keycodes = dict((i.split("BTN_", 1)[-1], v) for i, v in EventCodes.codes.items() if i.startswith("BTN_"))

    @staticmethod
    def alias(k):
        for a, v in Pointer.aliases.items():
            if k.lower() == a:
                k = v
        return k

    @staticmethod
    def send(key="", hold=True, release=True):
        self = Pointer.instance
        if not self: return
        ok = key
        if ok in self.__class__.keycodes:
            n = ok
        else:
            n = self.__class__.alias(ok).upper()
        key = self.__class__.keycodes.get(n, None)
        if key == None: return print("Pointer:", ok, "not in keycodes")
        for n in range(2):
            if n == 0 and hold or n == 1 and release:
                Pointer.pointer.button(0, key, int(hold if n == 0 else not release))
                Pointer.pointer.frame()
                Gdk.Display.get_default().flush()

    @staticmethod
    def scroll(x=0, y=0):
        request_sent = False
        for h, v in (("y", y), ("x", x)):
            if v != 0:
                h = 0 if h == "y" else 1
                request_sent = True
                Pointer.pointer.axis_source(0)
                Pointer.pointer.axis(0, h, v)
                Pointer.pointer.frame()
                Pointer.pointer.axis_source(0)
                Pointer.pointer.axis_stop(0, h)
                Pointer.pointer.frame()
        if request_sent: Gdk.Display.get_default().flush()

    @staticmethod
    def mouse(x=0, y=0):
        if (x != 0 or y != 0):
            Pointer.pointer.motion(0, x, y)
            Pointer.pointer.frame()
            Gdk.Display.get_default().flush()

class Key(Gtk.ToggleButton):
    __gtype_name__ = "Key"
    def __init__(self, l="", name="Key", **kwargs):
        super().__init__(hexpand=True, name=name, **kwargs)
        if l.endswith("-symbolic"):
            self.set_icon_name(l)
            self.set_tooltip_text(self.get_name())
        else: self.set_label(l)
        for i in ("key", "flat"): self.add_css_class(i)

class MaskKey(Key):
    __gtype_name__ = "MaskKey"
    def __init__(self, l="", name="MaskKey", **kwargs):
        Key.__init__(self, l=l, name=name, **kwargs)
        self.add_css_class("modifier")
        self.connect("notify::active", self.__class__.mask_update)

    @staticmethod
    def do_mask_update(keyboard):
        current = 0
        for k, i in keyboard.modifiers.items():
            if not k in Keyboard.modifiers: continue
            if i.get_active():
                current = current | Keyboard.modifiers[i.get_name()]
                Keyboard.send(key=i.get_name(), hold=True, release=False)
                i.down = True
            elif getattr(i, "down", False):
                i.down = False
                Keyboard.send(key=i.get_name(), hold=False, release=True)
        Keyboard.virtual_keyboard.modifiers(current, 0, 0, 0)

    @staticmethod
    def mask_update(w, p=None):
        k = w.get_name()
        s = w.get_active()
        kb = w.get_root()
        MaskKey.do_mask_update(kb)
        for i in w.get_root().keys.values():
            c = i.get_name()
            t = False
            if c in Keyboard.masks_transform["Shift"]:
                if kb.modifiers["Shift"].get_active():
                    c = Keyboard.masks_transform["Shift"][c]
                t = True
            if c in Keyboard.masks_transform["Symbol"]:
                if kb.modifiers["Symbol"].get_active():
                    c = Keyboard.masks_transform["Symbol"][c]
                t = True
            if t: i.set_label(c)

class Keyboard(LayerShell):
    __gtype_name__ = "Keyboard"
    aliases = { "ctrl": "leftctrl", "super": "leftmeta", "shift": "leftshift", "alt": "leftalt", ",": "comma", ".": "dot", "-": "minus", "/": "slash", "\\": "backslash", ";": "semicolon", "=": "kpequal", "'": "apostrophe", "[": "leftbrace", "]": "rightbrace"}
    instance = None

    modifiers = {
        "Shift": 0x00000001,
        "Ctrl": 0x00000004,
        "Alt": 0x00000008,
        "AltGr": 0x00000080,
        "Super": 0x00000040,
    }

    masks_transform = {
        "Shift": dict((i.lower(), i) for i in ascii_uppercase),
        "Symbol": {
            "q": "1", "w": "2", "e": "3", "r": "4", "t": "5", "y": "6", "u": "7", "i": "8", "o": "9", "p": "0",
            "Q": "@", "W": "!", "E": "#", "R": "$", "T": "%", "Y": "¨", "U": "&", "I": "*", "O": "(", "P": ")",
            "a": "/", "s": "\\", "d": ";", "f": "-", "g": "=", "k": "[", "l": "]",
            "A": "?", "S": "|", "D": ":", "F": "_", "G": "+", "K": "{", "L": "}",
        }
    }

    rows = GObject.Property(type=Gtk.Box)
    context = GObject.Property(type=Gtk.PopoverMenu)
    has_hover = GObject.Property(type=bool, default=False)

    @GObject.Property(type=int, default=0, minimum=0)
    def x(self): return getattr(self, "_x", 0)

    @x.setter
    def x(self, value):
        av = self.get_av("width")
        self._x = max(min(av, value), 0)
        l = layer_shell
        l.set_margin(self, l.Edge.RIGHT, max(min(av, av - value), 0))
        Data.setting("Keyboard Position X", 0, self._x)

    @GObject.Property(type=int, default=0, minimum=0)
    def y(self): return getattr(self, "_y", 0)

    @y.setter
    def y(self, value):
        av = self.get_av("height")
        self._y = max(min(av, value), 0)
        l = layer_shell
        l.set_margin(self, l.Edge.BOTTOM, max(min(av, av - value), 0))
        Data.setting("Keyboard Position Y", 0, self._y)

    def __init__(self):
        if not Data.setting("Virtual Keyboard", True): return

        keyboard_backend = "zwp_virtual_keyboard_manager_v1"
        vkb = keyboard_backend.replace("_manager", "")
        WlInterface(vkb, requests=[("keymap", "uhu"), ("key", "uuu"), ("modifiers", "uuuu"), ("destroy", "")])
        kb = WlInterface(keyboard_backend, requests=[("create_virtual_keyboard", "on", WlInterface.types("seat", vkb))])

        input_backend = "zwp_input_method_manager_v2"
        ipm = input_backend.replace("_manager", "")
        ipp = input_backend.replace("method_manager", "popup_surface")
        ipkg = input_backend.replace("manager", "keyboard_grab")
        WlInterface(ipp, requests=[("destroy", "")], events=[("text_input_rectangle", "iiii")])
        WlInterface(ipkg, requests=[("release", "")], events=[("keymap", "uhu"), ("key", "uuuu"), ("modifiers", "uuuuu"), ("repeat_info", "ii")])
        WlInterface(ipm, requests=[("commit_string", "s"), ("set_preedit_string", "sii"), ("delete_surrounding_text", "uu"), ("commit", "u"), ("get_input_popup_surface", "no", WlInterface.types(ipp, "surface")), ("grab_keyboard", "n",  WlInterface.types(ipkg)), ("destroy", "")], events=[("activate", ""), ("deactivate", ""), ("surrounding_text", "suu"), ("text_change_cause", "u"), ("content_type", "uu"), ("done", ""), ("unavailable", "")])
        ip = WlInterface(input_backend, requests=[("get_input_method", "on", WlInterface.types("seat", ipm)), ("destroy", "")])

        text_backend = "zwp_text_input_manager_v3"
        tip = text_backend.replace("_manager", "")
        WlInterface(tip, requests=[("destroy", ""), ("enable", ""), ("disable", ""), ("set_surrounding_text", "sii"), ("set_text_change_cause", "u"), ("set_content_type", "uu"), ("set_cursor_rectangle", "iiii"), ("commit", "")], events=[("enter", "o", WlInterface.types("surface")), ("leave", "o", WlInterface.types("surface")), ("preedit_string", "?sii"), ("commit_string", "?s"), ("delete_surrounding_text", "uu"), ("done", "u")])
        tb = WlInterface(text_backend, requests=[("destroy", ""), ("get_text_input", "no", WlInterface.types(tip, "seat"))])

        if Wayland.interfaces.get(kb.name.decode(), (0, 0))[1] == kb.version and Wayland.interfaces.get(ip.name.decode(), (0, 0))[1] == ip.version and Wayland.interfaces.get(tb.name.decode(), (0, 0))[1] == tb.version:
            seat = WlProxy.get(WlInterface["seat"], gtk_get_pointer(Gdk.Display.get_default().get_default_seat(), "gdk_wayland_seat_get_wl_seat"))
            Keyboard.input_method = Wayland.registry.bind(WlInterface[input_backend], *Wayland.interfaces[input_backend]).get_input_method(seat)
            Keyboard.text_input = Wayland.registry.bind(WlInterface[text_backend], *Wayland.interfaces[text_backend]).get_text_input(seat)
            Keyboard.text_input.enable()
            Keyboard.text_input.dispatcher(Keyboard.dispatcher)
            Keyboard.input_method.dispatcher(Keyboard.dispatcher)
            Keyboard.virtual_keyboard = Wayland.registry.bind(WlInterface[keyboard_backend], *Wayland.interfaces[keyboard_backend]).create_virtual_keyboard(seat)
            seat.get_keyboard().dispatcher(Keyboard.keyboard_dispatcher)
        else: return
        super().__init__(layer="OVERLAY", anchor=(False, True, False, True), margin=(0, 0, 0, 0), target=True)
        m = Menu()
        it = Gio.MenuItem.new("move", "move")
        it.set_attribute_value("custom", get_variant("move"))
        m.append_item(it)
        self.context = Gtk.PopoverMenu(has_arrow=False, menu_model=Menu({"Show Keyboard on Demand": "win.showk", "Hide Keyboard on Demand": "win.hidek", "!b": m}))
        move = Gtk.Box(css_name="move")
        b = [Button(css_classes=["flat", "circular"], halign=Gtk.Align.START, label=i, callback=self.__class__.move) for i in ("←", "→", "↓", "↑")]
        for i in b: move.append(i)
        move.append(Button(css_classes=["flat", "circular"], halign=Gtk.Align.END, hexpand=True, icon_name="window-close-symbolic", tooltip_text="Close", callback=self.__class__.close_button))
        self.context.add_child(move, "move")
        for i in ("Show", "Hide"): setattr(self, f"{i.lower()}k", App.default.data.persist_action(self, f"{i.lower()}k", (f"{i} Keyboard on Demand", False), "Settings", "Value", "Key = ?", (f"{i} Keyboard on Demand",)))
        self.get_codes()
        Keyboard.masks_transform["Shift"][","] = "<"
        Keyboard.masks_transform["Shift"]["."] = ">"
        self.keys = {}
        self.__class__.instance = self
        self.add_css_class("view")
        self.set_properties(focus_on_click=False, default_height=-1, default_width=-1, width_request=0, height_request=0, title=self.__gtype_name__)
        i = self.get_first_child()
        while i:
            i.set_focus_on_click(False)
            i = i.get_first_child()
        self.rows = Gtk.Box(css_name="rows", homogeneous=True, orientation=Gtk.Orientation.VERTICAL)
        self.modifiers = {}
        for a, b in (("Shift", "arrow5-up-symbolic"), ("Super", "Super"), ("Ctrl", "Ctrl"), ("Alt", "Alt"), ("Symbol", "junk-symbolic")):
            self.modifiers[a] = MaskKey(b, name=a)
        for row in [[Key("⎋", "Esc"), list("qwertyuiop"), Key("entry-clear-outline-symbolic", "Backspace")],
                    [Key("horizontal-arrows-symbolic", "Tab"), list("asdfghjkl"), Key("arrow-turn-down-left-symbolic", "Enter")],
                    [self.modifiers["Shift"], list("zxcvbnm"), "'", self.modifiers["Symbol"]],
                    [self.modifiers["Ctrl"], self.modifiers["Super"], self.modifiers["Alt"], "", ",", "."]]:
            box = Gtk.Box(css_name="row", hexpand=True)
            for i in row:
                if isinstance(i, list):
                    for it in i:
                        self.keys[it] = Key(it, it)
                        box.append(self.keys[it])
                elif isinstance(i, Gtk.Widget):
                    i.set_tooltip_text(i.get_name())
                    self.keys[i.get_name()] = i
                    box.append(self.keys[i.get_name()])
                else:
                    self.keys[i] = Key(i, i)
                    box.append(self.keys[i])
            self.rows.append(box)
        for i in box:
            if i.get_label() == "": i.add_css_class("space")
            else: i.set_hexpand(False)
        self.set_content(Gtk.WindowHandle(child=self.rows))
        motion = Gtk.EventControllerMotion(propagation_limit=Gtk.PropagationLimit.NONE, propagation_phase=Gtk.PropagationPhase.CAPTURE)
        self.add_controller(motion)
        motion.bind_property("contains-pointer", self, "has-hover", DEFAULT_BIND)

    @staticmethod
    def get_codes():
        if getattr(Keyboard, "keycodes", False): return
        EventCodes.get()
        Keyboard.keycodes = dict((i.split("KEY_", 1)[-1], v) for i, v in EventCodes.codes.items() if i.startswith("KEY_"))

    @staticmethod
    def close_button(b): b.get_root().close()

    @staticmethod
    def move(b):
        self = b.get_root()
        l = b.get_label()
        if l in ("←", "→"): self.move_x(-1 if l == "←" else 1)
        else: self.move_y(-1 if l == "↑" else 1)

    def idle_move(self, d, v=True):
        w = self.get_focus()
        Adw.Window.do_move_focus(self, d)
        if w == self.get_focus():
            s = [i for i in w.get_parent()]
            n = s.index(w)
            if d in (Gtk.DirectionType.UP, Gtk.DirectionType.DOWN):
                b = self.rows.get_last_child() if d == Gtk.DirectionType.UP else self.rows.get_first_child()
                c = [i for i in b]
                if n >= len(c) or len(c) > len(s) and w == s[-1]:
                    n = len(c) - 1
                self.set_focus(c[n])
            else: self.set_focus(s[0] if s[0] != w else s[-1])
        return v

    def move_focus(self, name, v):
        ex = getattr(self, f"{name}_move_focus", None)
        if ex: GLib.source_remove(ex)
        setattr(self, f"{name}_move_focus", None)
        d = getattr(Gtk.DirectionType, name.upper(), 0)
        if v:
            GLib.idle_add(self.idle_move, *(d, False))
            setattr(self, f"{name}_move_focus", GLib.timeout_add(150, self.idle_move, d))

    def toggle_context(self):
        if self.context.get_mapped(): self.context.popdown()
        else: self.show_popover_at_widget(self.context, self, 0, 0)

    def cancel(self, v):
        if v: return
        if self.context.get_mapped(): self.context.popdown()
        else: self.close()

    def confirm(self, v):
        if self.context.get_mapped():
            b = self.get_focus()
            if b and v: b.activate()
            return
        widget = self.get_focus()
        if isinstance(widget, MaskKey):
            if v: widget.set_active(not widget.get_active())
        elif isinstance(widget, Key):
            for i in self.keys.values():
                if i.get_active() and not isinstance(i, MaskKey) and not i == widget:
                    i.set_active(False)
                    self.send_key_widget(i, "released")
            self.send_key_widget(widget, "pressed" if v else "released")

    def get_av(self, h): return getattr(self.get_display().get_monitor_at_surface(self.get_surface()).get_geometry(), h) -  getattr(self.get_content(), f"get_{h}", )()

    def do_move_stuff(self, h, v):
        if not self.get_mapped(): return
        v = max(min(v, 1.0), -1.0)
        if v == 0: return
        setattr(self, h, max(getattr(self, h, 0) + (v * 6), 0))

    def move_x(self, amount): self.do_move_stuff("x", amount)
    def move_y(self, amount): self.do_move_stuff("y", amount)

    @staticmethod
    def do():
        if not Keyboard.instance: return
        if Keyboard.instance.get_mapped(): Keyboard.instance.close()
        else: Keyboard.instance.present()

    @staticmethod
    def on_click(*args):
        self, e, n, x, y, signal, b, state = Window.click_to_args(*args)
        if self.context.get_mapped(): return self.context.popdown()
        w = self.pick(x, y, Gtk.PickFlags.DEFAULT)
        if b == 3:
            if signal == "pressed": self.show_popover_at_widget(self.context, self.get_content(), x, y)
            return
        key = w.get_ancestor(Key) if w else None
        if not key or isinstance(key, MaskKey): return
        if e: e.set_state(Gtk.EventSequenceState.CLAIMED)
        self.send_key_widget(key, signal)

    def send_key_widget(self, key, signal):
        k = key.get_name() or "Space"
        if self.modifiers["Symbol"].get_active() and k in Keyboard.masks_transform["Symbol"]:
            k = Keyboard.masks_transform["Symbol"][k]
        key.set_active(signal == "pressed")
        self.send(key=k, hold=signal == "pressed", release=signal == "released")

    @staticmethod
    def alias(k):
        for a, v in Keyboard.aliases.items():
            if k.lower() == a:
                k = v
        return k

    @staticmethod
    def send(key="", hold=True, release=True):
        self = Keyboard.instance
        if not key or not self: return
        ok = key
        if key in self.__class__.keycodes:
            n = ok
        else:
            n = self.__class__.alias(key).upper()
        m = n.replace("LEFT", "").replace("RIGHT", "").title()
        if m in self.__class__.modifiers:
            self.modifiers[m].set_active(hold)
            return
        key = self.__class__.keycodes.get(n, None)
        if key == None: return print("Keyboard:", ok, "not in keycodes")
        for n in range(2):
            if n == 0 and hold or n == 1 and release:
                Keyboard.virtual_keyboard.key(0, key, int(hold if n == 0 else not release))
                Gdk.Display.get_default().flush()

    @staticmethod
    def keyboard_dispatcher(proxy, event, args):
        if event == "keymap":
            format, fd, size = args
            lseek(fd, 0, SEEK_SET)
            Keyboard.virtual_keyboard.keymap(format, fd, size)

    def present(self):
        if self.get_mapped(): return
        self.set_focus(None)
        self.set_focus(None)
        self.has_hover = True
        if Pointer.instance:
            Pointer.pointer.button(0, Pointer.keycodes["LEFT"], 0)
            Gdk.Display.get_default().flush()
        Adw.Window.present(self)
        if not hasattr(self, "_x"):
            self.realize()
            for i in ("x", "y"): Task.invoke(setattr, self, i, int(Data.setting(f"Keyboard Position {i.upper()}", 0)))

    def close(self):
        for i in self.keys.values():
            if i.get_active():
                Task.invoke(i.set_active, False)
                if not isinstance(i, MaskKey): self.send_key_widget(i, "released")
        Task.invoke(self.set_visible, False)

    @staticmethod
    def dispatcher(proxy, event, args):
        if not Keyboard.instance: return
        if event == "enter" and Keyboard.instance.showk.get_state().unpack(): Keyboard.instance.present()
        if event == "leave" and Keyboard.instance.hidek.get_state().unpack(): Keyboard.instance.close()

Keyboard.masks_transform["Shift"]["'"] = '"'

class Notification(ListObject):
    __gtype_name__ = "Notification"
    app = GObject.Property(type=str)
    title = GObject.Property(type=str)
    description = GObject.Property(type=str)
    display = GObject.Property(type=object)

    def __init__(self, app="", title="", description="", display=None):
        if isinstance(display, tuple):
            display = list(display)
            for n, i in enumerate(display):
                if i == "themed":
                    display = {i: display[n + 1]}
                    break
                if i == "bytes":
                    display = {i: display[n + 1]}
                    break
        if isinstance(display, dict):
            if "themed" in display:
                display = Gio.ThemedIcon.new_from_names(display["themed"])
            elif "bytes" in display:
                display = Gio.BytesIcon.new(GLib.Bytes.new(display["bytes"]))
        super().__init__(app=app, title=title, description=description, display=display)
        self.__class__.list.prepend(self)
        if len(self.__class__.list) > 30: self.__class__.list.remove(31)
        if not (getattr(Notifications, "instance", False) and Notifications.instance.get_mapped() or Notifications.instance.do_not_disturb):
            for i in Gtk.Window.list_toplevels():
                if isinstance(i, NotificationPopup): Task.invoke(i.close)
            Task.invoke(NotificationPopup, self)

    def remove(self): self.__class__.list.remove(self)

    @staticmethod
    def remove_all(*_): Notification.list.replace()

Notification.list = List(Notification, None, True)

class NotificationItem(Gtk.Overlay):
    __gtype_name__ = "NotificationItem"
    notification = GObject.Property(type=Notification)
    def __init__(self, notification=None):
        super().__init__(overflow=Gtk.Overflow.VISIBLE, css_name="notification", child=Gtk.Box(), css_classes=["card"])
        self.connect("notify::notification", self.__class__.notification_changed)
        self.bindings = []
        self.add_overlay(Button(tooltip_text="Remove", css_classes=("close", "circular"), icon_name="window-close", callback=self.__class__.remove, valign=Gtk.Align.START, halign=Gtk.Align.END))
        self.image = Gtk.Image(overflow=Gtk.Overflow.HIDDEN, pixel_size=92)
        self.image.bind_property("storage-type", self.image, "visible", DEFAULT_BIND, self.__class__.icon_bind)
        self.title = Gtk.Label(selectable=True, css_classes=("summary", "title-4"), wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR, justify=Gtk.Justification.CENTER)
        self.body = Gtk.Label(selectable=True, css_classes=("body",), wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR, justify=Gtk.Justification.CENTER)
        self.get_child().append(self.image)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(self.title)
        box.append(self.body)
        for i in box: i.bind_property("label", i, "visible", DEFAULT_BIND, bool_bind)
        self.get_child().append(Gtk.ScrolledWindow(hexpand=True, child=box))
        self.notification = notification

    @staticmethod
    def icon_bind(b, v): return v != Gtk.ImageType.EMPTY

    @staticmethod
    def do_icon_bind(b, v):
        image = b.get_property("target")
        if isinstance(v, Gdk.Paintable): image.set_from_paintable(v)
        if isinstance(v, Gio.Icon): image.set_from_gicon(v)
        if isinstance(v, str): image.set_from_icon_name(v)
        return ""

    @staticmethod
    def notification_changed(self, *_):
        for i in getattr(self, "bindings", []): i.unbind()
        self.bindings = []
        if self.notification:
            self.bindings.append(self.notification.bind_property("app", self.image, "tooltip-text", DEFAULT_BIND))
            self.bindings.append(self.notification.bind_property("title", self.title, "label", DEFAULT_BIND))
            self.bindings.append(self.notification.bind_property("description", self.body, "label", DEFAULT_BIND))
            self.bindings.append(self.notification.bind_property("display", self.image, "name", DEFAULT_BIND, self.__class__.do_icon_bind))

    @staticmethod
    def remove(b):
        self = b.get_ancestor(NotificationItem)
        if self.get_ancestor(NotificationPopup): return self.get_ancestor(NotificationPopup).close()
        if self and self.notification: self.notification.remove()

    factory = Gtk.SignalListItemFactory.new()
    @staticmethod
    def setup(f, l): l.set_child(NotificationItem())
    factory.connect("setup", setup)
    @staticmethod
    def bind(f, l):
        if not l.get_child(): return
        l.get_child().notification = l.get_property("item")
        Task.invoke(l.get_child().get_parent().set_properties, css_classes=[], focusable=False      )
    factory.connect("bind", bind)
    @staticmethod
    def unbind(f, l):
        l.get_child().notification = None
    factory.connect("unbind", unbind)
    @staticmethod
    def teardown(f, l): l.set_child(None)
    factory.connect("teardown", teardown)

class NotificationPopup(Adw.ApplicationWindow):
    __gtype_name__ = "NotificationPopup"
    def __init__(self, notification):
        super().__init__(height_request=1, width_request=1, default_width=360, default_height=100, application=App.default, content=Gtk.WindowHandle(focusable=True, child=NotificationItem(notification)), title=f"{notification.app}'s notification" if notification.app else "Notification")
        self.add_css_class("notifications")
        self.add_css_class("shell-window")
        self.present()

class Notifications(Window):
    __gtype_name__ = "Notifications"
    do_not_disturb = GObject.Property(type=bool, default=False)
    pause = GObject.Property(type=bool, default=False)
    def __init__(self):
        super().__init__()
        DBUS(NOTIFICATION_DBUS, NF_ID, DBUS.path(NF_ID), call)
        view = Gtk.ListView(model=Gtk.NoSelection(model=Notification.list), factory=NotificationItem.factory)
        view.set_css_classes([])
        overlay = Gtk.Overlay(child=Gtk.ScrolledWindow(child=view))
        self.do_not_disturb = int(Data.setting("Do Not Disturb", False))
        self.connect("notify::do-not-disturb", self.__class__.dnd_changed)
        self.pause = int(Data.setting("Clipboard Pause", False))
        self.connect("notify::pause", self.__class__.pause_changed)
        empty = Adw.StatusPage(title="Empty", icon_name="preferences-system-notifications-symbolic")
        Notification.list.bind_property("n-items", empty, "visible", DEFAULT_BIND, invert_bool_bind)
        overlay.add_overlay(empty)
        self.set_content(Adw.ToolbarView(content=overlay))
        header = Adw.HeaderBar()
        for i in (Button(callback=Notification.remove_all, tooltip_text="Clear All", icon_name="edit-clear-all", css_classes=("flat", "circular", "destructive-action",)),): header.pack_end(i)
        for i in (Button(t=Gtk.ToggleButton, tooltip_text="Do Not Disturb", icon_name="notifications-disabled", css_classes=("flat", "circular"), bindings=[(self, "do-not-disturb", None, "active", SYNC_BIND)]), Button(t=Gtk.ToggleButton, css_classes=("flat",), tooltip_text="Pause", icon_name="media-playback-pause", bindings=[(self, "pause", None, "active", SYNC_BIND)])): header.pack_start(i)
        self.get_content().add_top_bar(header)
        self.set_properties(title=self.__gtype_name__, hide_on_close=True, default_width=360, default_height=364)
        self.__class__.instance = self

    @staticmethod
    def dnd_changed(self, p): Data.setting("Do Not Disturb", False, self.do_not_disturb)

    @staticmethod
    def pause_changed(b, p): Data.setting("Notifications Pause", False, self.pause)

    @staticmethod
    def on_key_pressed(e, v, c, s):
        if v == Gdk.KEY_Escape: e.get_widget().get_root().set_visible(False)

    @staticmethod
    def do():
        self = Notifications.instance
        if self.get_mapped(): self.set_visible(False)
        else: self.present()

    @staticmethod
    def add(inv=None, n=None):
        self = Notifications.instance
        if self.pause: return
        app_name, replaces, app_icon, summary, body, actions, hints, expire = n
        v = hints.get("image-data", False) or hints.get("image-path", False) or app_icon
        p = None
        if isinstance(v, str):
            if v.startswith("file://"):
                p = Gdk.Texture.new_for_filename(Path(ROOT, uri_decode(v)))
            else:
                p = v
        elif isinstance(v, tuple) and len(v) == 7:
            p = Gdk.MemoryTexture.new(v[0], v[1], Gdk.MemoryFormat.R8G8B8A8 if v[3] else Gdk.MemoryFormat.R8G8B8,GLib.Bytes.new(v[6]), v[2])
        n = Notification(app=app_name, title=summary, description=body, display=p)
        if inv: inv.return_value(GLib.Variant("(u)", (len(Notification.list),)))

class ClipboardData(ListObject):
    __gtype_name__ = "ClipboardData"
    mimetypes = GObject.Property(type=object)
    paintable = GObject.Property(type=Gdk.Paintable)

    def __init__(self, mimetypes=None):
        super().__init__()
        self.mimetypes = mimetypes or {}
        self.__class__.list.prepend(self)
        if len(self.__class__.list) > 30: self.__class__.list.remove(31)

    def remove(self):
        self.mimetypes = None
        self.__class__.list.remove(self)

    @staticmethod
    def remove_all(*_):
        for i in ClipboardData.list:
            i.mimetypes = None
        ClipboardData.list.replace()

    def save(self):
        l = [Gio.content_type_get_description(Gio.content_type_from_mime_type(i.rsplit(";charset", 1)[0])) for i in self.mimetypes]
        d = Gtk.ScrolledWindow(vscrollbar_policy=Gtk.PolicyType.NEVER, child=Gtk.DropDown(model=Gtk.StringList.new(l)))
        p = Prompt(heading="Save", extra_child=d, callback=self.__class__.try_save, confirm_callback=False)
        p.data = self
        p.present(getattr(Clipboard, "instance", None))

    @staticmethod
    def try_save(d, r):
        data = getattr(d, "data", False)
        if not data: return
        del d.data
        l = list(data.mimetypes.keys())[d.get_extra_child().get_child().get_child().get_selected()]
        FileDialog(initial_name="clipboard").save(getattr(Clipboard, "instance", None), None, data.__class__.do_save, data.mimetypes[l])

    @staticmethod
    def do_save(a, b, d):
        try:
            f = a.save_finish(b)
            set_contents(f.get_path(), contents=d)
        except: return

    def get_search_term(self):
        if "text/uri-list" in self.mimetypes: return self.mimetypes["text/uri-list"].decode()
        if "image/png" in self.mimetypes: return "image"
        return self.mimetypes.get("text/plain;charset=utf-8", b"").decode()

    @staticmethod
    def items_changed(*_):
        if not getattr(Clipboard, "instance", False): return
        s = (Clipboard.instance.search or "").lower()
        l = []
        for i in ClipboardData.list:
            if not s or s in i.get_search_term(): l.append(i)
        for i in Clipboard.instance.masonry.children:
            if not i.data or not i.data in ClipboardData.list:
                i.data = None
                Task.invoke(Clipboard.instance.masonry.remove, i)
            else: Task.invoke(i.set_visible, False)
        if Clipboard.instance.get_mapped():
            for i in l:
                existing = next((it for it in Clipboard.instance.masonry if it.data == i), False)
                if existing: Task.invoke(existing.set_visible, True)
                else: Task.invoke(Clipboard.instance.masonry.prepend, ClipboardItem(i))
            Task.invoke(Clipboard.instance.do_status)

    def do_paintable(self):
        if self.paintable: return
        self.paintable = MediaStream(data=self.mimetypes["image/png"])
        if getattr(Clipboard, "instance", False): Task.invoke(Clipboard.instance.masonry.check_layout)

ClipboardData.list = List(ClipboardData, None, True)

class ClipboardItem(Gtk.Overlay):
    __gtype_name__ = "ClipboardItem"
    data = GObject.Property(type=ClipboardData)

    def __init__(self, data):
        super().__init__(css_name="clipboard", overflow=Gtk.Overflow.HIDDEN)
        classes = ["card"]
        self.data = data
        self.add_overlay(Button(callback=self.__class__.remove, halign=Gtk.Align.END, tooltip_text="Remove", valign=Gtk.Align.START, icon_name="window-close", css_classes=("circular", "close-button")))
        self.add_overlay(Button(callback=self.__class__.save, halign=Gtk.Align.START, tooltip_text="Save", valign=Gtk.Align.START, icon_name="document-save", css_classes=("circular", "save-button")))
        if "text/uri-list" in self.data.mimetypes:
            widget = Gtk.FlowBox(halign=Gtk.Align.CENTER, valign=Gtk.Align.START, selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=200)
            widget.connect("child-activated", self.__class__.launch_file)
            for i in self.data.mimetypes["text/uri-list"].decode().split("\n"):
                if not i: continue
                image = Gtk.Image(halign=Gtk.Align.START, tooltip_text=i.strip())
                if i.startswith("file://"):
                    f = Gio.File.new_for_uri(i)
                    image.path = f.get_path()
                    if hasattr(FileDialog, "set_icon"):
                        if hasattr(FileDialog, "set_icon"): FileDialog.set_icon(image, image.path)
                    else:
                        try:
                            info = Gio.File.new_for_path(image.path).query_info("standard::icon", Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS)
                            image.set_from_gicon(info.get_icon())
                        except:
                            image.set_from_icon_name("image-missing-symbolic")
                elif i: image.set_from_gicon(Gio.content_type_get_icon(Gio.content_type_guess(i)[0]))
                else: image.set_from_icon_name("image-missing-symbolic")
                widget.append(image)
            classes.append("files")
            widget = Gtk.ScrolledWindow(child=widget)
            if not any(isinstance(i, FileDialog) for i in Gtk.Window.list_toplevels()) and hasattr(FileDialog, "data_uninit"): Task.invoke(FileDialog.data_uninit)
        elif "image/png" in self.data.mimetypes:
            widget = Gtk.Picture(content_fit=Gtk.ContentFit.COVER)
            classes.append("image")
            self.data.bind_property("paintable", widget, "paintable", DEFAULT_BIND)
            Task(self.data.do_paintable).start()
        elif "text/plain;charset=utf-8" in self.data.mimetypes:
            t = self.data.mimetypes["text/plain;charset=utf-8"].decode("utf-8")
            c = []
            if HAS_COLOR.search(t):
                for i in COLOR.findall(t):
                    co = RGBA(i, validate=True)
                    if not co.valid:
                        c = []
                        break
                    c.append(co)
            if c:
                c = [Gtk.ColorDialogButton(rgba=i, dialog=Gtk.ColorDialog(), vexpand=True, hexpand=True) for i in c]
                if len(c) > 1:
                    widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                    classes.append("colors")
                    for i in c: widget.append(i)
                else:
                    widget = c[0]
                    classes.append("color")
            else:
                if is_online(t):
                    widget = Gtk.Label(use_markup=True, label=f"<a href=\"{GLib.markup_escape_text(t)}\">{GLib.markup_escape_text(t)}</a>")
                else:
                    widget = Gtk.Label(label=t)
        else:
            widget = Gtk.Label(label=" ".join(self.data.mimetypes.keys()))
        if isinstance(widget, Gtk.Label):
            widget.set_properties(hexpand=True, vexpand=True, justify=Gtk.Justification.CENTER, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
            widget = Gtk.ScrolledWindow(child=widget)
            classes.append("text")
        self.set_css_classes(classes)
        self.set_child(widget)

    @staticmethod
    def launch_file(flowbox, child): launch(child.get_child().get_tooltip_text())

    @staticmethod
    def remove(b):
        self = b.get_ancestor(ClipboardItem)
        if self and self.data: self.data.remove()

    @staticmethod
    def save(b):
        self = b.get_ancestor(ClipboardItem)
        if self and self.data: self.data.save()

class Clipboard(Window):
    __gtype_name__ = "Clipboard"
    owning = False

    masonry = GObject.Property(type=Masonry)
    empty = GObject.Property(type=Adw.StatusPage)
    no_results = GObject.Property(type=Adw.StatusPage)

    search = GObject.Property(type=str)
    pause = GObject.Property(type=bool, default=False)

    drop_target_gtypes = (Gdk.RGBA, Gdk.Texture, Gdk.FileList, Gio.File, str)
    instance = None

    def __init__(self):
        clipboard_backend = "ext_data_control_manager_v1" if "ext_data_control_manager_v1" in Wayland.interfaces else "zwlr_data_control_manager_v1" if "zwlr_data_control_manager_v1" in Wayland.interfaces else False
        if not Data.setting("Clipboard Manager", True):
            clipboard_backed = ""
        if clipboard_backend:
            prefix = clipboard_backend.split("_", 1)[0]
            version = Wayland.interfaces[clipboard_backend][1]
            WlInterface(f"{prefix}_data_control_source_v1", version=version, requests=[("offer", "s"), ("destroy", "")], events=[("send", "sh"), ("cancelled", "")])
            WlInterface(f"{prefix}_data_control_offer_v1", version=version, requests=[("receive", "sh"), ("destroy", "")], events=[("offer", "s")])
            WlInterface(f"{prefix}_data_control_device_v1", version=version, requests=[("set_selection", "?o", WlInterface.types(f"{prefix}_data_control_source_v1")), ("destroy", ""), ("set_primary_selection", "?o", WlInterface.types(f"{prefix}_data_control_source_v1"))], events=[("data_offer", "n", WlInterface.types(f"{prefix}_data_control_offer_v1")), ("selection", "?o", WlInterface.types(f"{prefix}_data_control_offer_v1")), ("finished", ""), ("primary_selection", "?o", WlInterface.types(f"{prefix}_data_control_offer_v1"))])
            self.__class__.data_control_manager = Wayland.registry.bind(WlInterface(f"{prefix}_data_control_manager_v1", version=version, requests=[("create_data_source", "n", WlInterface.types(f"{prefix}_data_control_source_v1")), ("get_data_device", "no", WlInterface.types(f"{prefix}_data_control_device_v1", "seat")), ("destroy", "")]), *Wayland.interfaces[clipboard_backend])
            seat = WlProxy.get(WlInterface["seat"], gtk_get_pointer(Gdk.Display.get_default().get_default_seat(), "gdk_wayland_seat_get_wl_seat"))
            self.__class__.data_control_device = self.__class__.data_control_manager.get_data_device(seat)
            self.__class__.data_control_device.dispatcher(self.__class__.data_control_device_dispatcher)
        else: return
        super().__init__()
        self.__class__.read, self.__class__.write = pipe()
        self.__class__.instance = self
        self.masonry = Masonry()
        overlay = Gtk.Overlay(child=self.masonry)
        self.pause = int(Data.setting("Clipboard Pause", False))
        self.connect("notify::pause", self.__class__.pause_changed)
        self.empty, self.no_results = Adw.StatusPage(title="Empty", icon_name="edit-paste-symbolic", visible=True), Adw.StatusPage(title="No Results", icon_name="edit-find-symbolic", visible=False)
        overlay.add_overlay(self.empty)
        overlay.add_overlay(self.no_results)
        self.set_content(Adw.ToolbarView(content=overlay))
        header = Adw.HeaderBar()
        for i in (Button(callback=ClipboardData.remove_all, tooltip_text="Clear All", icon_name="edit-clear-all-symbolic", css_classes=("flat", "circular", "destructive-action",)),): header.pack_end(i)
        self.get_content().add_top_bar(header)
        search = Gtk.SearchEntry(placeholder_text="Search")
        search.bind_property("text", self, "search", SYNC_BIND)
        self.connect("notify::search", ClipboardData.items_changed)
        search_bar = Gtk.SearchBar(child=search, key_capture_widget=self)
        self.get_content().add_top_bar(search_bar)
        for i in (Button(t=Gtk.ToggleButton, icon_name="edit-find", tooltip_text="Search", bindings=((None, "active", search_bar, "search-mode-enabled", SYNC_BIND),)), Button(t=Gtk.ToggleButton, css_classes=("flat",), tooltip_text="Pause", icon_name="media-playback-pause", bindings=[(self, "pause", None, "active", SYNC_BIND)])): header.pack_start(i)
        self.set_properties(title=self.__gtype_name__, hide_on_close=True, default_width=360, default_height=364)
        self.add_action(Gio.SimpleAction.new_stateful("search", None, get_variant(False)))
        self.lookup_action("search").bind_property("state", search_bar, "search-mode-enabled", SYNC_BIND, unpack_bind, variant_bind)
        App.default.set_accels_for_action("win.search", ["<primary>f"])

    def do_status(self):
        self.empty.set_visible(not self.search and len(ClipboardData.list) == 0)
        self.no_results.set_visible(self.search and not any(i.get_visible() for i in self.masonry.children))

    @staticmethod
    def pause_changed(self, p): Data.setting("Clipboard Pause", False, self.pause)

    @staticmethod
    def do():
        if not Clipboard.instance: return
        if Clipboard.instance.get_mapped(): Clipboard.instance.set_visible(False)
        else:
            Clipboard.instance.present()
            Task.invoke(ClipboardData.items_changed)

    @staticmethod
    def on_drop_target_drop(e, v, x, y):
        self = e.get_widget().get_root()
        w = self.pick(x, y, Gtk.PickFlags.DEFAULT)
        if isinstance(v, Gio.File):
            v = v.get_uri()
        if isinstance(v, Gdk.RGBA):
            if w and w.get_ancestor(Gtk.ColorDialogButton): w.get_ancestor(Gtk.ColorDialogButton).set_rgba(v)
            else: self.set(v.to_string())
        elif isinstance(v, Gdk.Texture): self.set({"image/png": v.save_to_png_bytes().get_data()})
        elif isinstance(v, Gdk.FileList): self.set({"text/uri-list": "\n".join(tuple(i.get_uri() for i in v)).encode("utf-8")})
        else: self.set(v)
        return True

    @staticmethod
    def on_drag_source_prepare(e, x, y):
        self = e.get_widget().get_root()
        e.v, c, w = [], None, self.pick(x, y, Gtk.PickFlags.DEFAULT)
        ow = w
        o = w.get_ancestor(ClipboardItem) if w else None
        a = Gdk.DragAction.NONE
        if o and o.data:
            css = o.get_css_classes()
            if "colors" in css and ow.get_ancestor(Gtk.ColorDialogButton):
                css = ["color"]
                o = ow.get_ancestor(Gtk.ColorDialogButton)
            if "color" in css:
                color = o.get_rgba() if hasattr(o, "get_rgba") else o.get_child().get_rgba()
                a, c = Gdk.DragAction.COPY, Gdk.ContentProvider.new_union([Gdk.ContentProvider.new_for_bytes("text/plain;charset=utf-8", GLib.Bytes.new(color.to_string().encode("utf-8"))), Gdk.ContentProvider.new_for_value(color)])
            if "text" in css and "text/plain;charset=utf-8" in o.data.mimetypes:
                text = GLib.Bytes.new(o.data.mimetypes["text/plain;charset=utf-8"])
                e.v.append(o.data.mimetypes["text/plain;charset=utf-8"].decode())
                a, u = Gdk.DragAction.COPY, []
                for i in ("text/plain", "text/plain;charset=utf-8"): u.append(Gdk.ContentProvider.new_for_bytes(i, text))
                if o.get_child().get_child().get_child().get_use_markup(): u.append(Gdk.ContentProvider.new_for_bytes("text/uri-list", text))
                c = Gdk.ContentProvider.new_union(u)
            if "files" in css and "text/uri-list" in o.data.mimetypes:
                if ow.get_ancestor(Gtk.FlowBoxChild):
                    files = [ow.get_ancestor(Gtk.FlowBoxChild).get_child()]
                else:
                    files = [i.get_child() for i in o.get_child().get_child().get_child()]
                a, l = Gdk.DragAction.COPY | Gdk.DragAction.MOVE, Gdk.FileList.new_from_list([Gio.File.new_for_uri(i.get_tooltip_text()) for i in files])
                e.v.append(files)
                c = Gdk.ContentProvider.new_for_value(l)
            if "image" in css and "image/png" in o.data.mimetypes:
                a = Gdk.DragAction.COPY
                e.v.append(o.get_child().get_paintable())
                c = Gdk.ContentProvider.new_for_bytes("image/png", GLib.Bytes.new(o.data.mimetypes["image/png"]))
            e.set_state(Gtk.EventSequenceState.CLAIMED)
            Task.invoke(e.reset)
        else: e.reset()
        e.set_actions(a)
        e.set_content(c)
        return c

    @staticmethod
    def on_drag_source_drag_begin(e, d):
        self = e.get_widget().get_root()
        for i in e.v:
            if isinstance(i, list) and all(isinstance(it, Gtk.Image) for it in i):
                box = Gtk.FlowBox(halign=Gtk.Align.START, valign=Gtk.Align.START, selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=200)
                for n, it in enumerate(i):
                    if n == 8 and not it == i[-1]:
                        box.append(Gtk.Label(opacity=0.4, css_classes=("title-2",), label=f"{len(i) - 8} +"))
                        break
                    image = Gtk.Image(pixel_size=92)
                    if it.get_paintable(): image.set_from_paintable(it.get_paintable())
                    elif it.get_gicon(): image.set_from_gicon(it.get_gicon())
                    box.append(image)
                return Gtk.DragIcon.get_for_drag(d).set_child(Adw.Clamp(maximum_size=300, child=box))
            if isinstance(i, Gdk.Paintable): return Gtk.DragIcon.get_for_drag(d).set_child(Adw.Clamp(tightening_threshold=300, maximum_size=300, orientation=Gtk.Orientation.VERTICAL, child=Adw.Clamp(css_name="media", margin_top=10, margin_start=10, tightening_threshold=300, maximum_size=300, child=Gtk.Picture.new_for_paintable(i))))
            if isinstance(i, str): Gtk.DragIcon.get_for_drag(d).set_child(Gtk.Label(margin_top=10, margin_start=10, label=i[:1000] + ("..." if len(i) > 1000 else ""), css_classes=["title-4"], ellipsize=Pango.EllipsizeMode.END))

    @staticmethod
    def on_drag_source_drag_end(e, d, de):
        e.set_content(None)
        e.set_actions(Gdk.DragAction.NONE)

    @staticmethod
    def on_click(e, *args):
        self = e.get_widget().get_root()
        bn = e.get_current_button()
        if isinstance(e, Gtk.GestureClick):
            n, x, y, signal = args
        else:
            x, y, signal = args
        w = self.pick(x, y, Gtk.PickFlags.DEFAULT)
        if not w: return
        if w.get_ancestor(Masonry):
            if isinstance(w, Gtk.Label) and w.get_use_markup():
                if not w.get_current_uri(): e.reset()
                return
            if signal != "released": return
            i = w.get_ancestor(ClipboardItem)
            if not (i and i.data): return
            b = w if isinstance(w, Gtk.Button) else w.get_ancestor(Gtk.ColorDialogButton) or w.get_ancestor(Gtk.Button)
            if b and b.get_tooltip_text() in ("Save", "Remove"): return
            if isinstance(b, Gtk.ColorDialogButton):
                if bn == 3:
                    i,data.remove()
                    Task.invoke(Clipboard.set, Palette.get_hex(b.get_rgba()) if Gdk.ModifierType.SHIFT_MASK in e.get_current_event_state() else b.get_rgba().to_string())
                    if Gdk.ModifierType.SHIFT_MASK in e.get_current_event_state(): Toast("Copied HEX", timeout=2)
            elif bn == 1:
                if i != self.masonry.children[0]:
                    m = i.data.mimetypes
                    i.data.remove()
                    Task.invoke(Clipboard.set, m)

    @staticmethod
    def on_key_pressed(e, v, c, s):
        self = e.get_widget().get_root()
        if v == Gdk.KEY_Escape:
            if self.lookup_action("search").get_state().unpack(): self.lookup_action("search").set_state(get_variant(False))
            else: self.set_visible(False)

    @staticmethod
    def set(content):
        Clipboard.owning = True
        if isinstance(content, dict):
            mimetypes = content
        else:
            mimetypes= {"text/plain;charset=utf-8": content.encode()}
        if getattr(Clipboard, "data_control_manager", False):
            source = Clipboard.data_control_manager.create_data_source()
            source.mimetypes = mimetypes
            source.dispatcher(Clipboard.data_control_source_dispatcher)
            for i in mimetypes: source.offer(i)
            Clipboard.data_control_device.set_selection(source)
            Gdk.Display.get_default().sync()
            Task.invoke(Gdk.Display.get_default().sync)
        if not (getattr(Clipboard, "instance", False) and Clipboard.instance.pause): ClipboardData(mimetypes)
        Clipboard.owning = False

    @staticmethod
    def do_selection(offer):
        mimetypes = getattr(offer, "mimetypes", set())
        if hasattr(offer, "mimetypes"): del offer.mimetypes
        if "image/png" in mimetypes:
            mimetypes = ["image/png"]
        t = "application/vnd.portal.filetransfer" in mimetypes
        for i in ("application/vnd.portal.filetransfer", "application/vnd.portal.files"):
            if i in mimetypes: mimetypes.remove(i)
        if "text/plain;charset=utf-8" in mimetypes:
            for i in [i for i in mimetypes if i.startswith("text/") and not i == "text/plain;charset=utf-8"]: mimetypes.remove(i)
            for i in ("UTF8_STRING", "STRING", "TEXT", "COMPOUND_TEXT"):
                if i in mimetypes: mimetypes.remove(i)
        data = {}
        for i in mimetypes:
            if not Clipboard.owning: continue
            chunks = []
            set_blocking(Clipboard.read, True)
            offer.receive(i, Clipboard.write)
            ready, _, _ = select([Clipboard.read], [], [], 1)
            if ready:
                set_blocking(Clipboard.read, False)
                while True:
                    if not Clipboard.owning: break
                    try:
                        d = read(Clipboard.read, 1024)
                        if not d: break
                        chunks.append(d)
                    except: break
            else: continue
            data[i] = b"".join(chunks)
        if t and "text/plain;charset=utf-8" in data and not "text/uri-list" in data:
            try:
                data["text/uri-list"] = list_to_str([uri_encode(i) for i in str_to_list(data["text/plain;charset=utf-8"].decode().replace("\x00", ""))]).encode()
            except Exception as e: print(e)
        Task.invoke(Clipboard.set, data)

    @staticmethod
    def data_control_source_dispatcher(proxy, event, args):
        if event == "send":
            mime, fd = args
            try:
                if hasattr(proxy, "mimetypes") and mime in proxy.mimetypes: write(fd, proxy.mimetypes[mime])
            finally: close(fd)
        if event == "cancelled":
            if hasattr(proxy, "mimetypes"): del proxy.mimetypes
            Task.invoke(proxy.destroy)

    @staticmethod
    def data_control_device_dispatcher(proxy, event, args):
        if Clipboard.owning or Clipboard.instance.pause: return
        if event == "data_offer":
            args[0].dispatcher(Clipboard.data_control_offer_dispatcher)
        if event == "selection":
            o = args[0]
            if o:
                Clipboard.owning = True
                Task(Clipboard.do_selection, o).start()
            elif not o:
                Clipboard.owning = False
        if event == "primary_selection":
            Clipboard.data_control_device.set_primary_selection(None)
            Gdk.Display.get_default().flush()

    @staticmethod
    def data_control_offer_dispatcher(proxy, event, args):
        if event == "offer" and not Clipboard.owning:
            if not hasattr(proxy, "mimetypes"):
                proxy.mimetypes = set()
            proxy.mimetypes.add(args[0])

class DesktopApp(ListObject):
    __gtype_name__ = "DesktopApp"
    custom = GObject.Property(type=int)
    id = GObject.Property(type=str)
    icon = GObject.Property(type=str)
    display_icon = GObject.Property(type=object)
    name = GObject.Property(type=str)
    command = GObject.Property(type=str)
    mimetypes = GObject.Property(type=object)
    hidden = GObject.Property(type=bool, default=False)
    default = GObject.Property(type=object)

    def __init__(self, path="", data=None, **kwargs):
        super().__init__(**kwargs)
        self.default = {}
        if path:
            self.id = basename(path)
            keyfile = GLib.KeyFile()
            keyfile.load_from_file(path, GLib.KeyFileFlags.NONE)
            try:
                v = keyfile.get_value("Desktop Entry", "Icon")
            except:
                v = None
            self.default["icon"] = self.icon = v
            self.default["name"] = self.name = keyfile.get_value("Desktop Entry", "Name") or self.id.rsplit(".desktop", 1)[0]
            self.default["command"] = self.command = keyfile.get_value("Desktop Entry", "Exec")
            try:
                v = keyfile.get_value("Desktop Entry", "MimeType").strip(";").split(";")
            except:
                v = []
            self.default["mimetypes"] = self.mimetypes = v
        if not self.name:
            self.name = f"Custom App {self.id}"
        if data:
            for k, v in data.items():
                if getattr(self, k.lower(), None) != v and v: setattr(self, k.lower(), v)

    @staticmethod
    def update(*_):
        apps = json(Data.setting("Apps Data", {}))
        l = []
        d = set((HOST_SYSTEM_DATA if FLATPAK_ID else SYSTEM_DATA) + [HOST_DATA if FLATPAK_ID else DATA])
        d.add(Path(HOST_DATA if FLATPAK_ID else DATA, "flatpak/exports/share"))
        d.add(Path(ROOT, "var/lib/flatpak/exports/share"))
        d.add(Path(ROOT, "usr/share"))
        if not getattr(DesktopApp, "monitors", False):
            DesktopApp.monitors = []
            theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
            for i in d:
                monitor = Gio.File.new_for_path(Path(i, "applications")).monitor_directory(Gio.FileMonitorFlags.NONE)
                DesktopApp.monitors.append(monitor)
                monitor.connect("changed", DesktopApp.update)
                p = Path(i, "icons")
                theme.add_search_path(p)
                if "/flatpak/" in p:
                    for r, dd, f in walk(Path(p, "hicolor")):
                        for it in dd: theme.add_search_path(Path(r, it))
        for p in d:
            p = Path(p, "applications")
            if not exists(p): continue
            for i in list_dir(p):
                if not i.endswith(".desktop") or i.startswith(App.default.get_application_id()): continue
                l.append(DesktopApp(data=apps.get(i, {}), path=Path(p, i)))
        for k, v in apps.items():
            if not k.endswith(".desktop"): l.append(DesktopApp(id=k, data=v))
        a = dict((i, n) for n, i in enumerate(apps))
        for i in l:
            i.custom = a.get(i.id, 0)
        DesktopApp.list.get_model().replace(l)
        DesktopApp.save()

    @staticmethod
    def custom_sort(self): return self.custom

    def save():
        c = {}
        for i in sorted([i for i in DesktopApp.list.get_model()], key=DesktopApp.custom_sort):
            c[i.id] = {"Name": i.name or "", "Icon": i.icon or "", "Command": i.command or "", "MimeTypes": i.mimetypes or [], "Hidden": i.hidden}
        for k, v in json(Data.setting("Apps Data", {})).items(): c.setdefault(k, v)
        Data.setting("Apps Data", {}, c)

    def launch(self, uris=None):
        uris = uris or []
        if Apps.instance and Apps.instance.get_mapped(): Apps.instance.set_visible(False)
        command = self.command
        if uris:
            if "%U" in command:
                command = command.replace("%U", " ".join(["\"" + i + "\"" for i in uris]))
            elif "%F" in command:
                command = command.replace("%F", " ".join(["\"" + Gio.File.new_for_uri(i).get_path() + "\"" for i in uris]))
            elif "%u" in command:
                command = command.replace("%u", "\"" + uris[0] + "\"")
            elif "%f" in command:
                command = command.replace("%f", "\"" + Gio.File.new_for_uri(uris[0]).get_path() + "\"")
        else:
            for i in ("F", "U"):
                command = command.replace(f" %{i}", "")
                command = command.replace(f" %{i.lower()}", "")
        command = command.strip()
        if command:
            if hasattr(Niri, "connection"): Niri.request("Action", { "SpawnSh": { "command": command } })
            else: GLib.spawn_command_line_async(command)

    def do_display_icon(self):
        v = self.icon or "image-x-generic-symbolic"
        if "/" in v:
            if "://" in v:
                v = uri_decode(v)
            if v.endswith(".svg"): setattr(self, "display_icon", Gtk.IconPaintable.new_for_file(Gio.File.new_for_path(Path(ROOT, v)), 1, 1))
            else: setattr(self, "display_icon", Gio.File.new_for_path(v))
        else: setattr(self, "display_icon", v)

    def do_icon(self, i):
        if not self.display_icon: self.do_display_icon()
        if isinstance(self.display_icon, Gdk.Paintable): i.set_from_paintable(self.display_icon)
        elif isinstance(self.display_icon, Gio.File): i.set_from_file(self.display_icon.get_path())
        elif isinstance(self.display_icon, str): i.set_from_icon_name(self.display_icon)

DesktopApp.list = Gtk.SortListModel(model=List(DesktopApp, "id"))

class AppChooser(Window):
    __gtype_name__ = "AppChooser"
    uri = GObject.Property(type=str)
    content_type = GObject.Property(type=str)
    activation_token = GObject.Property(type=str)
    filter = GObject.Property(type=Gtk.Filter)
    @staticmethod
    def all_filter_expression(a, b): return bool(b)
    all_filter = Gtk.BoolFilter(expression=Gtk.ClosureExpression.new(bool, all_filter_expression, [Gtk.PropertyExpression.new(DesktopApp, None, "mimetypes")]))
    default_filters = GObject.Property(type=Gtk.EveryFilter)

    def __init__(self, inv=None, handle="", app_id="", parent_window="", choices="", options={}):
        super().__init__()
        self.add_action(Gio.SimpleAction.new_stateful("show-all", None, get_variant(False)))
        self.activation_token = options.get("activation_token", "")
        if inv: inv.return_value(GLib.Variant("(ua{sv})", (1, {})))
        self.uri = options["uri"]
        self.content_type = options.get("content_type", False) or Gio.content_type_guess(self.uri)[0]
        if is_online(self.uri):
            self.content_type = "x-scheme-handler/https"
        sorter = Gtk.CustomSorter()
        sorter.set_sort_func(self.__class__.do_sort, json(Data.setting("Apps Last Used", {})).get(self.content_type, ""))
        filter = Gtk.FilterListModel(model=Gtk.SortListModel(model=DesktopApp.list, sorter=sorter))
        self.bind_property("filter", filter, "filter", DEFAULT_BIND)
        self.default_filters = Gtk.EveryFilter()
        self.default_filters.append(self.__class__.all_filter)
        self.default_filters.append(Apps.hidden_filter)
        self.default_filters.append(Gtk.BoolFilter(expression=Gtk.ClosureExpression.new(bool, self.__class__.do_filter, [Gtk.PropertyExpression.new(self.__class__, Gtk.ObjectExpression.new(self), "content-type")])))
        self.lookup_action("show-all").bind_property("state", self, "filter", DEFAULT_BIND, self.__class__.filter_bind)
        gridview = Gtk.GridView(single_click_activate=True, factory=DesktopAppItem.factory, min_columns=3, model=Gtk.NoSelection(model=filter))
        gridview.set_css_classes([])
        gridview.connect("activate", self.__class__.selection_activate)
        App.default.set_accels_for_action("win.show-all", ["<primary>h"])
        overlay = Gtk.Overlay(child=Gtk.ScrolledWindow(child=gridview))
        status = Adw.StatusPage(title="No Apps", icon_name="preferences-desktop-apps-symbolic")
        gridview.get_model().bind_property("n-items", status, "visible", DEFAULT_BIND, invert_bool_bind)
        overlay.add_overlay(status)
        self.set_content(Adw.ToolbarView(content=overlay))
        header = Adw.HeaderBar()
        header.pack_end(Button(action_name="win.show-all", bindings=[(self.lookup_action("show-all"), "state", None, "tooltip-text", None, self.__class__.tooltip_bind), (None, "tooltip-text", None, "icon-name", None, self.__class__.icon_bind)]))
        self.get_content().add_top_bar(header)
        self.set_properties(title=options.get("filename", "") or self.uri, default_width=360, default_height=400)
        self.present()

    @staticmethod
    def tooltip_bind(b, v): return "Show Default" if v.unpack() else "Show All"

    @staticmethod
    def icon_bind(b, v): return "view-reveal-symbolic" if v == "Show All" else "view-conceal-symbolic"

    @staticmethod
    def do_filter(a, b): return b in a.mimetypes or any(i.endswith("/*") and b.startswith(i.rstrip("/*")) for i in a.mimetypes)

    @staticmethod
    def filter_bind(b, v): return AppChooser.all_filter if v.unpack() else b.get_property("target").default_filters

    @staticmethod
    def do_sort(a, b, last):
        a_last = a.id.rsplit(".desktop", 1)[0] == last
        if a_last != b.id.rsplit(".desktop", 1)[0]: return -1 if a_last else 1
        return 0

    @staticmethod
    def on_key_pressed(e, v, c, s):
        if v == Gdk.KEY_Escape:
            e.get_widget().get_root().close()
            return True

    @staticmethod
    def selection_activate(g, p):
        self = g.get_root()
        if not self: return
        i = g.get_model().get_item(p)
        i.launch([self.uri])
        l = json(Data.setting("Apps Last Used", {}))
        l[self.content_type] = i.id.rsplit(".desktop", 1)[0]
        Data.setting("Apps Last Used", {}, l)
        self.close()

class DesktopAppItem(Gtk.Image):
    __gtype_name__ = "DesktopAppItem"
    app = GObject.Property(type=DesktopApp)

    factory = Gtk.SignalListItemFactory.new()
    @staticmethod
    def setup(f, l): l.set_child(DesktopAppItem())
    factory.connect("setup", setup)
    @staticmethod
    def bind(f, l):
        if not l.get_child(): return
        l.get_child().bindings = []
        l.get_child().bindings.append(l.bind_property("item", l.get_child(), "app", DEFAULT_BIND))
        l.get_child().bindings.append(l.get_property("item").bind_property("name", l.get_child(), "tooltip-text", DEFAULT_BIND))
        l.get_child().bindings.append(l.get_property("item").bind_property("display-icon", l.get_child(), "name", DEFAULT_BIND, l.get_child().icon_bind))
    factory.connect("bind", bind)
    @staticmethod
    def unbind(f, l):
        for i in getattr(l.get_child(), "bindings", []): i.unbind()
        if hasattr(l.get_child(), "bindings"): del l.get_child().bindings
    factory.connect("unbind", unbind)
    @staticmethod
    def teardown(f, l): l.set_child(None)
    factory.connect("teardown", teardown)

    @staticmethod
    def icon_bind(b, v):
        b.get_property("source").do_icon(b.get_property("target"))
        return ""

class AppEditor(Window):
    __gtype_name__ = "AppEditor"
    app = GObject.Property(type=DesktopApp)
    box = GObject.Property(type=Adw.PreferencesGroup)
    def __init__(self, app):
        box = Adw.PreferencesGroup()
        super().__init__(content=Adw.ToolbarView(content=Gtk.ScrolledWindow(child=box)))
        self.box = box
        self.app = app
        self.set_properties(default_width=450, default_height=450, title=app.id)
        header = Adw.HeaderBar(show_end_title_buttons=False, show_start_title_buttons=False)
        header.pack_start(Button(callback=self.__class__.cancel, label="Cancel"))
        header.pack_end(Button(callback=self.__class__.confirm, label="Confirm", css_classes=("suggested-action",)))
        self.get_content().add_top_bar(header)
        box.add(Adw.EntryRow(title="Name", text=app.name))
        box.add(Adw.EntryRow(title="Icon", text=app.icon))
        box.add(Adw.EntryRow(title="Command", text=app.command))
        box.add(TagRow(title="MimeType", tags=app.mimetypes or []))
        self.present()

    @staticmethod
    def cancel(b): b.get_root().close()

    @staticmethod
    def confirm(b):
        self = b.get_root()
        v = {}
        r = []
        row = self.box.get_row(0)
        while row:
            r.append(row)
            row = self.box.get_row(len(r))
        for i in r:
            k = ("MimeTypes" if i.get_title() == "MimeType" else i.get_title()).lower()
            v = i.get_text() if isinstance(i, Adw.EntryRow) else i.tags
            if not v and k in self.app.default: setattr(self.app, k, self.app.default[k])
            else: setattr(self.app, k, v)
        self.app.display_icon = None
        DesktopApp.save()
        self.app = None
        self.close()

class Apps(LayerShell):
    __gtype_name__ = "Apps"
    instance = None
    drop_target_gtypes = (DesktopApp,)

    search = GObject.Property(type=Gtk.SearchEntry)
    context = GObject.Property(type=Gtk.Popover)
    context_widget = GObject.Property(type=Gtk.Widget)
    default_menu = GObject.Property(type=Gio.Menu)
    filters = GObject.Property(type=Gtk.EveryFilter)

    alphabetical_sort = Gtk.StringSorter(expression=Gtk.PropertyExpression.new(DesktopApp, None, "name"))
    custom_sort = Gtk.NumericSorter(expression=Gtk.PropertyExpression.new(DesktopApp, None, "custom"))
    hidden_filter = Gtk.BoolFilter(invert=True, expression=Gtk.PropertyExpression.new(DesktopApp, None, "hidden"))

    def __init__(self):
        super().__init__(layer=("OVERLAY" if hasattr(Wayfire, "connection") else "TOP"), target=True, keyboard_mode="EXCLUSIVE", css_name=self.__class__.__gtype_name__.lower())
        self.__class__.instance = self
        self.context = Gtk.PopoverMenu(has_arrow=False)
        self.search = Gtk.SearchEntry(opacity=0, can_target=False)
        self.search.set_key_capture_widget(self)
        self.set_content(Gtk.Overlay(hexpand=True, vexpand=True, child=self.search))
        self.filters = Gtk.EveryFilter()
        s = Gtk.StringFilter.new(Gtk.PropertyExpression.new(DesktopApp, None, "name"))
        self.search.bind_property("text", s, "search", DEFAULT_BIND)
        self.filters.append(s)
        filter = Gtk.FilterListModel(filter=self.filters, model=DesktopApp.list)
        gridview = Gtk.GridView(single_click_activate=True, factory=DesktopAppItem.factory, min_columns=6, model=Gtk.NoSelection(model=filter))
        gridview.set_css_classes([])
        gridview.connect("activate", self.__class__.selection_activate)
        self.get_content().add_overlay(Gtk.ScrolledWindow(child=gridview, hscrollbar_policy=Gtk.PolicyType.NEVER))
        self.get_content().get_last_child().get_vscrollbar().set_visible(False)
        self.get_content().add_overlay(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, visible=False, valign=Gtk.Align.CENTER, vexpand=True))
        for i in (Gtk.Image(icon_name="edit-find-symbolic", pixel_size=256), Gtk.Label(label="No Results")): self.get_content().get_last_child().append(i)
        gridview.get_model().bind_property("n-items", self.get_content().get_last_child(), "visible", DEFAULT_BIND, invert_bool_bind)
        App.default.data.persist_action(self, "Show Hidden", ("Apps Show Hidden", False), "Settings", "Value", "Key = ?", ("Apps Show Hidden",)).connect("notify::state", self.__class__.do_hidden)
        self.__class__.do_hidden()
        App.default.data.persist_action(self, "Sort", ("Apps Sort", "Alphabetical"), "Settings", "Value", "Key = ?", ("Apps Sort",)).bind_property("state", DesktopApp.list, "sorter", DEFAULT_BIND, self.__class__.sort_bind)
        self.default_menu = Gio.Menu.new()
        self.default_menu.append_section(None, Menu(dict((f"Sort by {i}", f"win.sort::{i}") for i in ("Alphabetical", "Custom"))))
        self.default_menu.append_section(None, Menu({"Show Hidden": "win.show-hidden", "Reload": "win.action::Reload", "Add New": "win.action::Add New"}))
        self.add_action(Gio.SimpleAction.new("action", get_variant("str").get_type()))
        self.lookup_action("action").connect("activate", self.__class__.act)
        DesktopApp.update()
        WM.connect("notify::is-overview", self.__class__.overview_changed)
        App.default.set_accels_for_action("win.show-hidden", ["<primary>h"])

    @staticmethod
    def sort_bind(b, v):
        if "Custom" in v.unpack(): return Apps.custom_sort
        return Apps.alphabetical_sort

    @staticmethod
    def do_hidden(*_):
        self = Apps.instance
        if not self: return
        while self.filters.get_n_items() > 1: self.filters.remove(1)
        if not self.lookup_action("show-hidden").get_state().unpack(): self.filters.append(self.__class__.hidden_filter)

    @staticmethod
    def selection_activate(g, p): g.get_model().get_item(p).launch()

    @staticmethod
    def overview_changed(*_):
        if Apps.instance and Apps.instance.get_mapped() and WM.is_overview: Task.invoke(Apps.instance.set_visible, False)

    @staticmethod
    def act(a, b):
        b = b.unpack().strip("'")
        self = Apps.instance
        i = self.context_widget
        if b == "Reload": DesktopApp.update()
        if b == "Open": i.app.launch()
        if b.lower().endswith("hide"):
            i.app.hidden = b == "Hide"
            DesktopApp.save()
        if b == "Edit":
            AppEditor(i.app)
            self.set_visible(False)
        if b == "Remove":
            d = json(Data.setting("Apps Data", {}))
            del d[i.app.id]
            Data.setting("Apps Data", {}, d)
            DesktopApp.list.get_model().remove(i.app)
            DesktopApp.save()
        if b == "Add New":
            l = []
            for i in DesktopApp.list.get_model():
                if i.id and i.id.isdigit(): l.append(int(i.id))
            n = 1
            while n in l:
                n += 1
            DesktopApp.list.get_model().append(DesktopApp(id=str(n), custom=max((i.custom for i in DesktopApp.list.get_model()), default=0)))
            DesktopApp.save()

    @staticmethod
    def do(*_):
        self = Apps.instance
        if self and self.get_mapped(): self.set_visible(False)
        elif self:
            if WM.is_overview: Niri.request("Action", {"ToggleOverview": {}})
            self.present()
            self.search.grab_focus()

    @staticmethod
    def on_click(e, *args):
        if isinstance(e, Gtk.GestureClick):
            n, x, y, signal = args
            if signal != "released": return
        else:
            x, y, signal = args
        self = e.get_widget().get_root()
        if self.context.get_mapped(): return self.context.popdown()
        self.context_widget = self.pick(x, y, Gtk.PickFlags.DEFAULT)
        if e.get_current_button() != 3:
            self.context_widget = None
            return
        if self.context_widget.get_ancestor(DesktopAppItem):
            self.context_widget = self.context_widget.get_ancestor(DesktopAppItem)
            actions = ["Open", ["Edit", "Unhide" if self.context_widget.app.hidden else "Hide"], "Remove" if not self.context_widget.app.id.endswith(".desktop") else ""]
            menu = Gio.Menu.new()
            for i in actions:
                if isinstance(i, list) and all(it for it in i):
                    m = Gio.Menu.new()
                    for it in i: m.append(it, f"win.action::{it}")
                    menu.append_section(None, m)
                    m.freeze()
                elif not isinstance(i, list) and i:
                    m = Gio.Menu.new()
                    m.append(i, f"win.action::{i}")
                    menu.append_section(None, m)
                    m.freeze()
            self.context.set_menu_model(menu)
        else:
            self.context_widget = None
            self.context.set_menu_model(self.default_menu)
        self.show_popover_at_widget(self.context, self.get_content(), x, y)

    @staticmethod
    def on_key_pressed(e, v, c, s):
        self = e.get_widget().get_root()
        if v == Gdk.KEY_Escape:
            if self.search.get_text() == "": self.set_visible(False)
            else: self.search.set_text("")

    @staticmethod
    def save():
        original = json(Data.setting("Apps Data", {}))
        d = {}
        for i in Apps.apps:
            if hasattr(i, "id"):
                d[i.id] = {"Name": i.name, "Icon": i.icon, "Command": i.command, "MimeTypes": i.mimetypes, "Hidden": i.hidden}
        for i in original:
            if not i in d:
                d[i] = original[i]
        Data.setting("Apps Data", {}, d)

    @staticmethod
    def on_drag_source_prepare(e, x, y):
        self = e.get_widget().get_root()
        w = self.pick(x, y, Gtk.PickFlags.DEFAULT)
        self.context_widget = w.get_ancestor(DesktopAppItem) if w and w.get_ancestor(DesktopAppItem) and self.lookup_action("sort").get_state().unpack() == "Custom" else None
        c = None
        if self.context_widget:
            e.set_actions(Gdk.DragAction.MOVE)
            c = Gdk.ContentProvider.new_for_value(self.context_widget.app)
        else: e.set_actions(Gdk.DragAction.NONE)
        e.set_content(c)
        return c

    @staticmethod
    def on_drag_source_drag_begin(e, d):
        self = e.get_widget().get_root()
        if self.context_widget: Gtk.DragIcon.get_for_drag(d).set_child(Gtk.Picture(paintable=Gtk.WidgetPaintable.new(self.context_widget)))

    @staticmethod
    def on_drag_source_drag_end(e, d, de):
        e.set_content(None)
        e.set_actions(Gdk.DragAction.NONE)
        e.get_widget().get_root().context_widget = None

    @staticmethod
    def on_drop_target_drop(e, v, x, y):
        self = e.get_widget().get_root()
        if not self.context_widget: return
        self.clear_drop()
        h = self.pick(x, y, Gtk.PickFlags.DEFAULT)
        h = h.get_ancestor(DesktopAppItem) if h else None
        if h and h.app != self.context_widget.app:
            l = [DesktopApp.list.get_item(i) for i in range(DesktopApp.list.get_n_items())]
            start = l.index(h.app)
            l.remove(self.context_widget.app)
            l.insert(start, self.context_widget.app)
            for n, i in enumerate(l):
                i.custom = n
            self.__class__.custom_sort.set_expression(Gtk.PropertyExpression.new(DesktopApp, None, "custom"))
            Task.invoke(DesktopApp.save)
            return True

    @staticmethod
    def on_drop_target_motion(e, x, y):
        self = e.get_widget().get_root()
        if not self.context_widget: return Gdk.DragAction.NONE
        self.clear_drop()
        w = self.pick(x, y, Gtk.PickFlags.DEFAULT)
        self.highlight = w.get_ancestor(DesktopAppItem) if w else None
        if self.highlight and self.highlight.app == self.context_widget.app:
            self.highlight = None
        if self.highlight: self.highlight.add_css_class("highlight")
        return Gdk.DragAction.MOVE

    def clear_drop(self):
        if getattr(self, "highlight", False): self.highlight.remove_css_class("highlight")
        self.highlight = None

class Palette(Window):
    __gtype_name__ = "Palette"
    def __init__(self):
        super().__init__(title=self.__class__.__gtype_name__)
        self.set_content(Adw.ToolbarView(extend_content_to_top_edge=True, content=Gtk.Box(orientation=Gtk.Orientation.VERTICAL)))
        header = Adw.HeaderBar(show_title=False)
        header.pack_start(Button(icon_name="color-select", css_classes=["flat", "circular"], callback=self.__class__.do))
        self.get_content().add_top_bar(header)

    def start(self, color):
        self = self or Palette()
        box = self.get_content().get_content()
        while box.get_first_child(): box.remove(box.get_first_child())
        for i in self.adjust_rgb(color):
            i = RGBA(i)
            if any(it.get_rgba().equal(i) for it in box): continue
            box.append(Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(), rgba=i, vexpand=True, hexpand=True))
        self.set_default_size(210, 122 * len([i for i in box]))
        self.present()

    def adjust_rgb(self, r):
        c = rgb_to_hls(*RGBA.rgb(r, f=True))
        lightest = [min(1.0, i + 0.2) if n == 1 else i for n, i in enumerate(c)]
        light = [min(1.0, i + 0.1) if n == 1 else i for n, i in enumerate(c)]
        if not any(i >= 0.02 for i in (lightest[0] - light[0], lightest[1] - light[1], lightest[2] - light[2])):
            light = lightest
        dark = [max(0.0, i - 0.1) if n == 1 else i for n, i in enumerate(c)]
        darkest = [max(0.0, i - 0.2) if n == 1 else i for n, i in enumerate(c)]
        if not any(i >= 0.02 for i in (dark[0] - darkest[0], dark[1] - darkest[1], dark[2] - darkest[2])):
            dark = darkest
        if lightest[1] >= 0.8: self.add_css_class("dark")
        return (hls_to_rgb(*lightest), hls_to_rgb(*light), r, hls_to_rgb(*dark), hls_to_rgb(*darkest))

    @staticmethod
    def on_click(e, *args):
        self = e.get_widget().get_root()
        if isinstance(e, Gtk.GestureClick):
            n, x, y, signal = args
        else:
            x, y, signal = args
        if signal == "released": return
        b = e.get_current_button()
        w = self.pick(x, y, Gtk.PickFlags.DEFAULT)
        if w:
            w = w.get_ancestor(Gtk.ColorDialogButton)
        if not(b == 3 and isinstance(w, Gtk.ColorDialogButton)): return
        if Gdk.ModifierType.SHIFT_MASK in e.get_current_event_state():
            c = self.__class__.get_hex(w.get_rgba())
        else:
            c = w.get_rgba().to_string()
        Gdk.Display.get_default().get_clipboard().set(c)
        Toast(f"Copied {'HEX' if c.startswith('#') else 'RGB'}", timeout=2)

    @staticmethod
    def get_hex(rgba): return "#{:02x}{:02x}{:02x}".format(*RGBA.rgb(rgba)) if rgba.is_opaque() else "#{:02x}{:02x}{:02x}{:02x}".format(*RGBA.rgb(rgba, a=True))

    @staticmethod
    def on_key_pressed(e, v, kc, s):
        if v == Gdk.KEY_Escape:
            e.get_widget().close()
            return True

    @staticmethod
    def finish(proxy, buffer):
        data, x, y = proxy.function_data
        del proxy.function_data
        offset = y * (proxy.width * 4) + x * 4
        pixel = buffer.map(Gst.MapFlags.READ)[-1].data[offset:offset + 4]
        if ImageCopy.get_default_format().startswith("BGR"):
            pixel = (pixel[2], pixel[1], pixel[0])
        else:
            pixel = (pixel[0], pixel[1], pixel[2])
        if isinstance(data, Gio.DBusMethodInvocation): data.return_value(GLib.Variant("(ua{sv})", (0, {"color": GLib.Variant("(uuu)", tuple(i / 255 for i in pixel))})))
        else: Task.invoke(Palette.start, False, pixel)

    @staticmethod
    def do_pick(arg, data):
        if arg == False:
            if isinstance(data, Gio.DBusMethodInvocation): data.return_value(GLib.Variant("(ua{sv})", (1, {})))
        else:
            if not Gst.is_initialized(): Gst.init()
            frame = ImageCopy.capture_frame(source=arg[0])
            if not frame: return
            frame.do_ready = Palette.finish
            frame.function_data = [data, arg[1], arg[2]]

    @staticmethod
    def do(b=False):
        if b: b.get_root().set_visible(False)
        Selector(function_data=b.get_root() if b else False, function=Palette.do_pick, single_pixel=True)

class Authorize(EntryPrompt):
    __gtype_name__ = "Authorize"
    cookie = GObject.Property(type=str)
    stdout_channel = GObject.Property(type=GLib.IOChannel)
    stdin_channel = GObject.Property(type=GLib.IOChannel)
    invocation = GObject.Property(type=Gio.DBusMethodInvocation)

    def __init__(self, invocation, args):
        super().__init__(callback=self.__class__.do, confirm_callback=False, password=True)
        self.invocation = invocation
        action_id, message, icon_name, details, self.cookie, identities = args
        self.set_heading(message)
        self.present()

    @staticmethod
    def do(self, r):
        if r == "cancel" or not self.invocation: return self.finish()
        if FLATPAK_ID:
            success, pid, stdin_fd, stdout_fd, stderr_fd = GLib.spawn_async_with_pipes(None, ["/bin/flatpak-spawn", "--host", "/usr/lib/polkit-1/polkit-agent-helper-1", GLib.getenv("USER"), self.cookie], None, GLib.SpawnFlags.DEFAULT | GLib.SpawnFlags.CHILD_INHERITS_STDERR, None, None)
        else:
            success, pid, stdin_fd, stdout_fd, stderr_fd = GLib.spawn_async_with_pipes(None, ["/usr/lib/polkit-1/polkit-agent-helper-1", GLib.getenv("USER"), self.cookie], ["LC_ALL=C"], GLib.SpawnFlags.DEFAULT | GLib.SpawnFlags.CHILD_INHERITS_STDERR, None, None)
        if not success: return self.finish()
        self.stdin_channel = GLib.IOChannel.unix_new(stdin_fd)
        self.stdin_channel.set_encoding("utf-8")
        self.stdout_channel = GLib.IOChannel.unix_new(stdout_fd)
        GLib.io_add_watch(self.stdout_channel, GLib.PRIORITY_DEFAULT, GLib.IOCondition.IN, self.__class__.communicate, self)
        GLib.io_add_watch(self.stdin_channel, GLib.PRIORITY_DEFAULT, GLib.IOCondition.OUT, self.__class__.communicate, self)

    @staticmethod
    def communicate(channel, condition, self):
        if not self.invocation: return
        if channel == self.stdin_channel:
            channel.write_chars(self.get_extra_child().get_text().encode("utf-8"), -1)
            channel.flush()
            channel.write_chars("\n".encode("utf-8"), -1)
            channel.flush()
        elif channel == self.stdout_channel:
            message = channel.read_to_end()[-1].decode("utf-8")
            if "SUCCESS" in message: self.finish()
            if "FAILURE" in message:
                self.get_extra_child().set_text("")
                self.get_extra_child().set_property("placeholder-text", "Try Again...")
                self.present()

    def finish(self):
        for i in (self.stdout_channel, self.stdin_channel):
            if i: i.shutdown(True)
        if self.invocation: self.invocation.return_value(None)
        self.invocation = None

class PortalFileDialog(FileDialog):
    __gtype_name__ = "PortalFileDialog"
    invocation = GObject.Property(type=Gio.DBusMethodInvocation)
    files = GObject.Property(type=object)
    args = GObject.Property(type=object)
    def __init__(self, invocation=None, operation="SaveFile", args=False):
        v = args[-1].get("current_folder", None)
        if v:
            v = Gio.File.new_for_path(bytes(v).rstrip(b"\x00").decode("utf-8"))
        default_filter = args[-1].get("current_filter", None)
        if default_filter:
            default_filter = self.__class__.convert_filter(default_filter)
        filters = args[-1].get("filters", None) or None
        if filters:
            filters = list(filters)
            if not any(i[0] == "All Files" and i[1][0] == 0 for i in filters): filters.insert(0, ("All Files", [(0, "*")]))
            l = Gio.ListStore.new(Gtk.FileFilter)
            for i in filters: l.append(self.__class__.convert_filter(i))
            filters = l
        super().__init__(title=args[3], modal=args[-1].get("modal", True), accept_label=args[-1]["accept_label"].replace("_", "") if args[-1].get("accept_label", False) else " File".join(operation.split("File")), initial_name=args[-1].get("current_name", ""), initial_folder=v, default_filter=default_filter, filters=filters)
        self.multiple = args[-1].get("multiple", False)
        self.args = args
        if hasattr(self, "extra_menu") and self.args[-1].get("choices", False):
            self.extra_menu = m = Menu()
            c = []
            for i in self.args[-1].get("choices", []):
                c.append(i[0])
                v = bool(i[-1]) if not i[2] else i[-1]
                variant = get_variant(v)
                self.add_action(Gio.SimpleAction.new_stateful(i[0], variant.get_type() if type(v) == str else None, variant))
                if type(v) == str: m.append_submenu(i[1], Menu(dict((it[1], f"win.{i[0]}::{it[0]}") for it in i[2])))
                else: m.append(i[1], f"win.{i[0]}")
        self.invocation = invocation
        self.files = [bytes(i).rstrip(b"\x00").decode("utf-8") for i in self.args[-1].get("files", [])]
        if operation == "OpenFile":
            if self.args[-1].get("directory", False):
                if self.multiple: self.select_multiple_folders(callback=self.__class__.do, user_data=operation)
                else: self.select_folder(callback=self.__class__.do, user_data=operation)
            else:
                if self.multiple: self.open_multiple(callback=self.__class__.do, user_data=operation)
                else: self.open(callback=self.__class__.do, user_data=operation)
        if operation == "SaveFile": self.save(callback=self.__class__.do, user_data=operation)
        if operation == "SaveFiles": self.select_folder(callback=self.__class__.do, user_data=operation)

    @staticmethod
    def convert_filter(filter):
        f = Gtk.FileFilter(name=filter[0])
        for i in filter[1]:
            if i[0] == 0: f.add_pattern(i[1])
            elif i[0] == 1: f.add_mime_type(i[1])
        return f

    @staticmethod
    def do(self, r, operation):
        try:
            if not self.invocation: raise Exception
            f = None
            if operation == "OpenFile":
                if self.args[-1].get("directory", False):
                    if self.multiple:
                        f = self.select_multiple_folders_finish(r)
                    else:
                        f = self.select_folder_finish(r)
                else:
                    if self.multiple:
                        f = self.open_multiple_finish(r)
                    else:
                        f = self.open_finish(r)
            if operation == "SaveFile":
                f = self.save_finish(r)
            if operation == "SaveFiles":
                f = self.select_folder_finish(r)
                if self.files:
                    selected = []
                    for i in self.files:
                        ff, n = f.get_child(i), 0
                        while ff.query_exists() or any(it for it in selected if it == ff.get_uri()):
                            n += 1
                            ff = f.get_child(f"{i} ({n})")
                        selected.append(ff)
                    f = selected
                else:
                    f = []
            if f == None: raise Exception
            if isinstance(f, Gio.File):
                f = [f.get_uri()]
            else:
                f = [i.get_uri() for i in f]
            if FLATPAK_ID:
                for n, i in enumerate(f):
                    f[n] = f[n].replace(f"file://{ROOT}", "file:///")
            v = {"uris": GLib.Variant("as", f)}
            if operation == "OpenFile":
                v["writable"] = GLib.Variant("b", False)
            f = self.get_property("default-filter")
            if operation in ("OpenFile", "SaveFile") and f:
                f = next((i for i in self.args[-1].get("filters", []) if i[0] == f.get_name()), None)
                if f:
                    v["current_filter"] = GLib.Variant("(sa(us))", f)
            if getattr(self, "extra_menu"):
                c = []
                for i in self.args[-1].get("choices", []):
                    va = self.lookup_action(i).get_state().unpack()
                    c.append((i, str(va).lower() if isinstance(va, bool) else va))
                v["choices"] = GLib.Variant("a(ss)", c)
            self.invocation.return_value(GLib.Variant("(ua{sv})", (0, v)))
        except Exception as e:
            print(e)
            if self.invocation: self.invocation.return_value(GLib.Variant("(ua{sv})", (1, {})))
        if not any(i != self and isinstance(i, FileDialog) for i in Gtk.Window.list_toplevels()) and hasattr(FileDialog, "data_uninit"): FileDialog.data_uninit()

class Niri:
    seen_sessions = []
    def __init__(self):
        super().__init__()
        self = self.__class__
        s = GLib.getenv("NIRI_SOCKET")
        if FLATPAK_ID:
            s = Path(ROOT, s)
        address = Gio.UnixSocketAddress.new(s)
        connection = Gio.SocketClient().connect(address)
        connection.get_output_stream().write_all("\"EventStream\"\n".encode("utf-8"))
        connection.get_output_stream().close()
        reader = Gio.DataInputStream.new(connection.get_input_stream())
        reader.read_line_async(GLib.PRIORITY_DEFAULT, None, self.read_line_async)
        self.connection = Gio.SocketClient().connect(address)
        self.reader = Gio.DataInputStream.new(self.connection.get_input_stream())

    @staticmethod
    def request(r, args={}):
        Niri.connection.get_output_stream().write_all(((json_string({r: args}) if r == "Action" else f'"{r}"') + "\n").encode("utf-8"), None)
        Niri.connection.get_output_stream().flush()
        return Niri.reader.read_line_utf8()[0]

    @staticmethod
    def read_line_async(reader, r):
        line, size = reader.read_line_finish_utf8(r)
        if not line: return reader.read_line_async(GLib.PRIORITY_DEFAULT, None, Niri.read_line_async)
        if line.startswith("{\"OverviewOpenedOrClosed"):
            WM.is_overview = "true" in line
        elif line.startswith(("{\"CastsChanged", "{\"CastStartedOrChanged")):
            casts = json(line)["CastsChanged"]["casts"] if line.startswith("{\"CastsChanged") else [json(line)["CastStartedOrChanged"]["cast"]]
            for i in casts:
                if line.startswith("{\"CastStartedOrChanged"):
                    if not i["session_id"] in Niri.seen_sessions:
                        if i["pw_node_id"] == None: continue
                        Niri.seen_sessions.append(i["session_id"])
                        continue
                if not i["is_active"]: Niri.request("Action", { "StopCast": { "session_id": i["session_id"] } })
        GLib.timeout_add(50, reader.read_line_async, *(GLib.PRIORITY_DEFAULT, None, Niri.read_line_async))

class Wayfire:
    def __init__(self):
        super().__init__()
        self.__class__.connection = connection = Gio.SocketClient().connect(Gio.UnixSocketAddress.new(GLib.getenv("WAYFIRE_SOCKET")))
        data = '{"method": "window-rules/events/watch", "data": {"events": ["plugin-activation-state-changed"]}}'.encode("utf-8")
        connection.get_output_stream().write(len(data).to_bytes(4, byteorder="little"))
        connection.get_output_stream().write(data)
        connection.get_output_stream().close()
        Wayfire.read()

    @staticmethod
    def do_get_number(a, r):
        n = int.from_bytes(a.read_bytes_finish(r).get_data(), byteorder="little")
        Wayfire.connection.get_input_stream().read_bytes_async(n, GLib.PRIORITY_LOW, None, Wayfire.read)

    @staticmethod
    def read(a=None, r=None):
        message = a.read_bytes_finish(r).get_data().decode("utf-8") if a and r else ""
        if "event" in message and '"plugin":"scale"' in message:
            WM.is_overview = '"state":true' in message
        Wayfire.connection.get_input_stream().read_bytes_async(4, GLib.PRIORITY_LOW, None, Wayfire.do_get_number)

class WM(GObject.Object):
    __gtype_name__ = "WindowManager"
    is_overview = GObject.Property(type=bool, default=False)

WM = WM()

class ImageCopy:
    sessions = []
    def __init__(self):
        n = "zwlr_screencopy_manager_v1"
        f = WlInterface(n.replace("manager", "frame"), version=3, requests=[("copy", "o", WlInterface.types("buffer")), ("destroy", ""), ("copy_with_damage", "o", WlInterface.types("buffer"))], events=[("buffer", "uuuu"), ("flags", "u"), ("ready", "uuu"), ("failed", ""), ("damage", "uuuu"), ("linux_dmabuf", "uuu"), ("buffer_done", "")])
        m = WlInterface(n, version=3, requests=[("capture_output", "nio", WlInterface.types(f.name.decode(), None, "output")), ("capture_output_region", "nioiiii", WlInterface.types(f.name.decode(), None, "output", None, None, None, None)), ("destroy", "")])

        if Wayland.interfaces.get(m.name.decode(), (0, 0))[1] == m.version:
            ImageCopy.manager = Wayland.registry.bind(m, *Wayland.interfaces[m.name.decode()])
            ImageCopy.shm = Wayland.registry.bind(WlInterface["shm"], *Wayland.interfaces["wl_shm"])

        n = "zwp_linux_dmabuf_v1"
        version = 4 if Wayland.interfaces.get(n, (0, 0))[1] == 4 else 6
        req = [("destroy", ""), ("add", "huuuuu"), ("create", "iiuu"), ("create_immed", "niiuu", WlInterface.types("buffer"))]
        if version == 6: req.append(("set_sampling_device", "a"))
        p = WlInterface.types(WlInterface(n.replace("dmabuf", "buffer_params"), requests=req, events=[("created", "n", WlInterface.types("buffer")), ("failed", "")], version=version).name.decode())
        f = WlInterface(n.replace("v1", "feedback_v1"), requests=[("destroy", "")], events=[("done", ""), ("format_table", "hu"), ("main_device", "a"), ("tranche_done", ""), ("tranche_target_device", "a"), ("tranche_formats", "a"), ("tranche_flags", "u")], version=version)
        m = WlInterface(n, requests=[("destroy", ""), ("create_params", "n", p), ("get_default_feedback", "n", WlInterface.types(f)), ("get_surface_feedback", "no", WlInterface.types(f, "surface"))], events=[("format", "u"), ("modifier", "uuu")], version=version)
        if gbm and Wayland.interfaces.get(m.name.decode(), (0, 0))[1] == m.version:
            ImageCopy.dmabuf = Wayland.registry.bind(m, *Wayland.interfaces[m.name.decode()])
        n = "ext_foreign_toplevel_list_v1"
        handle = WlInterface(n.replace("list", "handle"), requests=[("destroy", "")], events=[("closed", ""), ("done", ""), ("title", "s"), ("app_id", "s"), ("identifier", "s")])
        ImageCopy.toplevel_list = WlInterface(n, requests=[("stop", ""), ("destroy", "")], events=[("toplevel", "n", WlInterface.types(n.replace("list", "handle"))), ("finished", "")])
        capture = n = "ext_image_capture_source_v1"
        WlInterface(n, requests=[("destroy", "")])
        b = WlInterface(n.replace("image", "output_image").replace("v1", "manager_v1"), requests=[("create_source", "no", WlInterface.types(n, "output")), ("destroy", "")])
        a = WlInterface(n.replace("image", "foreign_toplevel_image").replace("v1", "manager_v1"), requests=[("create_source", "no", WlInterface.types(n, handle)), ("destroy", "")])
        n = "ext_image_copy_capture_manager_v1"
        f = WlInterface(n.replace("manager", "frame"), requests=[("destroy", ""), ("attach_buffer", "o", WlInterface.types("buffer")), ("damage_buffer", "iiii"), ("capture", "")], events=[("transform", "u"), ("damage", "iiii"), ("presentation_time", "uuu"), ("ready", ""), ("failed", "u")])
        WlInterface(n.replace("manager", "session"), requests=[("create_frame", "n", WlInterface.types(f)), ("destroy", "")], events=[("buffer_size", "uu"), ("shm_format", "u"), ("dmabuf_device", "a"), ("dmabuf_format", "ua"), ("done", ""), ("stopped", "")])
        WlInterface(n.replace("manager", "cursor_session"), requests=[("destroy", ""), ("get_capture_session", "n", WlInterface.types(n.replace("manager", "session")))], events=[("enter", ""), ("leave", ""), ("position", "ii"), ("hotspot", "ii")])
        c = WlInterface(n, requests=[("create_session", "nou", WlInterface.types(n.replace("manager", "session"), capture)), ("create_pointer_cursor_session", "noo", WlInterface.types(n.replace("manager", "cursor_session"), capture, "pointer")), ("destroy", "")])
        if Wayland.interfaces.get(a.name.decode(), (0, 0))[1] == a.version:
            ImageCopy.toplevel_capture = Wayland.registry.bind(a, *Wayland.interfaces[a.name.decode()])
        if Wayland.interfaces.get(b.name.decode(), (0, 0))[1] == b.version:
            ImageCopy.output_capture = Wayland.registry.bind(b, *Wayland.interfaces[b.name.decode()])
        if Wayland.interfaces.get(c.name.decode(), (0, 0))[1] == c.version:
            ImageCopy.capture_manager = Wayland.registry.bind(c, *Wayland.interfaces[c.name.decode()])

    @staticmethod
    def get_default_format(): return "RGBx" if hasattr(Wayfire, "connection") and not getattr(ImageCopy, "dmabuf", False) else "BGRx"

    @staticmethod
    def get_crop(W=0, H=0, w=0, h=0, x=-1, y=-1):
        if (x != -1 or y != -1) and w and h:
            crop = f" videocrop left={x} top={y} right={max(0, W - x - w)} bottom={max(0, H - y - h)} !"
        else:
            crop = ""
        return crop

    @staticmethod
    def capture_frame(source=None, cursor=False, add_user=True):
        frame = None
        if not source:
            source = Gdk.Display.get_default().get_monitors()[0]
        if getattr(ImageCopy, "capture_manager", False):
            session = next((i for i in ImageCopy.sessions if i["Source"] == source and i["Show Cursor"] == cursor), False)
            if session:
                if add_user:
                    session["Users"] += 1
            else:
                if isinstance(source, Gdk.Monitor) and getattr(ImageCopy, "output_capture", False):
                    s = ImageCopy.output_capture.create_source(gtk_get_pointer(source, "gdk_wayland_monitor_get_wl_output"))
                elif hasattr(source, "identifier") and getattr(ImageCopy, "toplevel_capture", False):
                    s = ImageCopy.toplevel_capture.create_source(source)
                else: return frame
                session = {"Source": source, "Session": ImageCopy.capture_manager.create_session(s, int(cursor)), "Show Cursor": cursor, "Users": 1}
                s.destroy()
                ImageCopy.sessions.append(session)
                session["Session"].dispatcher(ImageCopy.session_dispatcher)
                Gdk.Display.get_default().sync()
                if not hasattr(session["Session"], "format"):
                    session["Session"].destroy()
                    return frame
                if getattr(ImageCopy, "dmabuf", False) and gbm and hasattr(session["Session"], "dmabuf_device"):
                    ImageCopy.device(device=session["Session"].dmabuf_device)
                    if GBM_DEVICE:
                        session["Session"].buffer = ImageCopy.create_dmabuf(format=session["Session"].format, height=session["Session"].height, width=session["Session"].width)
                if not hasattr(session["Session"], "buffer"):
                    session["Session"].buffer = ImageCopy.create_shm_buffer(format=session["Session"].format, height=session["Session"].height, width=session["Session"].width, stride=session["Session"].width * 4)
            frame = session["Session"].create_frame()
            frame.dispatcher(ImageCopy.frame_dispatcher)
            frame.width, frame.height, frame.format = session["Session"].width, session["Session"].height, session["Session"].format
            frame.capture_session = session["Session"]
            frame.attach_buffer(session["Session"].buffer)
            frame.capture()
        elif isinstance(source, Gdk.Monitor):
            frame = ImageCopy.manager.capture_output(int(cursor), gtk_get_pointer(source, "gdk_wayland_monitor_get_wl_output"))
            frame.dispatcher(ImageCopy.frame_dispatcher)
        return frame

    @staticmethod
    def create_shm_buffer(format=0, height=0, width=0, stride=0):
        size = stride * height
        GstAllocators.ShmAllocator.init_once()
        allocator = GstAllocators.ShmAllocator.get()
        memory = Gst.Allocator.alloc(allocator, size, None)
        pool = ImageCopy.shm.create_pool(GstAllocators.fd_memory_get_fd(memory), size)
        buffer = pool.create_buffer(0, width, height, stride, format)
        buffer.data = Gst.Buffer.new()
        buffer.data.append_memory(memory)
        pool.destroy()
        return buffer

    @staticmethod
    def device(device=False):
        global GBM_DEVICE
        try:
            GBM_DEVICE
        except NameError:
            l = next((i for i in list_dir("/dev/dri") if i.startswith("render")), False)
            if l:
                GBM_DEVICE = gbm.gbm_create_device(os_open(f"/dev/dri/{l}", O_RDWR | O_CLOEXEC))
            else:
                GBM_DEVICE = False

    @staticmethod
    def create_dmabuf(format=0, height=0, width=0):
        allocator = GstAllocators.DmaBufAllocator.new()
        bo = gbm.gbm_bo_create(GBM_DEVICE, width, height, format, 16 | 4)
        fd = gbm.gbm_bo_get_fd(bo)
        stride = gbm.gbm_bo_get_stride(bo)
        params = ImageCopy.dmabuf.create_params()
        modifier = gbm.gbm_bo_get_modifier(bo)
        params.add(fd, 0, 0, stride, modifier >> 32, modifier & 0xFFFFFFFF)
        buffer = params.create_immed(width, height, format, 0)
        params.destroy()
        buffer.data = Gst.Buffer.new()
        buffer.data.append_memory(allocator.alloc_with_flags(allocator, fd, stride * height, 0))
        return buffer

    @staticmethod
    def session_dispatcher(proxy, event, args):
        if event == "buffer_size":
            proxy.width, proxy.height = args
        if event == "shm_format" and args:
            proxy.format = args[0]
        if event == "dmabuf_device" and args:
            if getattr(ImageCopy, "dmabuf", False) and gbm:
                if hasattr(proxy, "format"): del proxy.format
                proxy.dmabuf_device = args[0]
        if event == "dmabuf_format" and args:
            if hasattr(proxy, "dmabuf_device") and not hasattr(proxy, "format"):
                proxy.format = args[0]
                proxy.modifier = args[-1]
        if event == "stopped":
            for i in [i for i in ImageCopy.sessions]:
                if i["Session"] == proxy: ImageCopy.sessions.remove(i)
            proxy.destroy()

    @staticmethod
    def toplevel_list_dispatcher(proxy, event, args):
        if event == "toplevel":
            toplevel = args[0]
            toplevel.screencast = proxy.screencast
            toplevel.dispatcher(ImageCopy.toplevel_dispatcher)
        if event == "finished":
            proxy.destroy()
            del proxy.screencast

    @staticmethod
    def toplevel_dispatcher(proxy, event, args):
        if event == "title":
            proxy.title = args[0]
        if event == "identifier":
            proxy.identifier = args[0]
        if event == "done":
            if all(hasattr(proxy, i) for i in ("screencast", "title", "identifier")):
                proxy.screencast.videos[unique_name(proxy.title, proxy.screencast.videos)] = proxy
        if event in ("closed", "done"):
            if hasattr(proxy, "screencast"):
                del proxy.screencast

    @staticmethod
    def frame_dispatcher(proxy, event, args):
        if not getattr(proxy, "do_ready", False): return proxy.destroy()
        if event == "buffer" and not hasattr(proxy, "format"):
            proxy.format, proxy.width, proxy.height, proxy.stride = args
            if gbm and getattr(ImageCopy, "dmabuf", False):
                ImageCopy.device()
                if GBM_DEVICE:
                    proxy.dmabuf = True
        elif event == "linux_dmabuf" and getattr(proxy, "dmabuf", False):
            if not hasattr(proxy, "buffer"):
                proxy.format, proxy.width, proxy.height = args
                proxy.buffer = ImageCopy.create_dmabuf(format=proxy.format, height=proxy.height, width=proxy.width)
            proxy.copy_with_damage(proxy.buffer)
        elif event == "buffer_done":
            if not getattr(proxy, "dmabuf", False):
                if not hasattr(proxy, "buffer"):
                    proxy.buffer = ImageCopy.create_shm_buffer(format=proxy.format, height=proxy.height, width=proxy.width, stride=proxy.stride)
                proxy.copy_with_damage(proxy.buffer)
        elif event in ("ready", "failed"):
            if event == "ready" and hasattr(proxy, "do_ready") and hasattr(proxy, "buffer"): proxy.do_ready(proxy, proxy.buffer.data)
            elif event == "ready" and hasattr(proxy, "do_ready") and hasattr(proxy, "capture_session") and hasattr(proxy.capture_session, "buffer"): proxy.do_ready(proxy, proxy.capture_session.buffer.data)
            ImageCopy.destroy_object(proxy)

    @staticmethod
    def destroy_object(o):
        MediaStream.destroy_pipeline(o)
        if hasattr(o, "pipeline"): ImageCopy.destroy_object(o.pipeline)
        if hasattr(o, "children") and hasattr(o, "proxy"): ImageCopy.destroy_object(o.proxy)
        if hasattr(o, "params"): o.params.destroy()
        if hasattr(o, "data"):
            if hasattr(o.data, "close"): o.data.close()
            if hasattr(o.data, "remove_all_memory"): o.data.remove_all_memory()
        if hasattr(o, "buffer"):
            if o.buffer:
                ImageCopy.destroy_object(o.buffer)
                o.buffer.destroy()
        if hasattr(o, "session") and o.session in ScreenCast.sessions: del ScreenCast.sessions[o.session]
        if hasattr(o, "capture_session"):
            session = next((i for i in ImageCopy.sessions if i["Session"] == o.capture_session), False)
            if session:
                session["Users"] -= 1
                if not session["Users"]:
                    ImageCopy.sessions.remove(session)
                    ImageCopy.destroy_object(o.capture_session)
            else: ImageCopy.destroy_object(o.capture_session)
        for i in ("capture_session", "session", "buffer", "serial", "node_id", "pipewire", "source", "prompt", "dmabuf", "data", "width", "height", "stride", "format", "do_ready"):
            if hasattr(o, i): delattr(o, i)
        if hasattr(o, "destroy"): o.destroy()

    @staticmethod
    def new_frame(proxy, frame):
        for i in ("buffer", "session", "prompt", "dmabuf", "format", "do_ready"):
            if hasattr(proxy, i): setattr(frame, i, getattr(proxy, i))
        for i in ("capture_session", "buffer", "session", "prompt"):
            if hasattr(proxy, i): delattr(proxy, i)

    @staticmethod
    def get_gsr():
        ImageCopy.gsr = "/bin/gpu-screen-recorder"
        if FLATPAK_ID: return exists(Path(ROOT, ImageCopy.gsr))
        return exists(ImageCopy.gsr)

class ScreenCast(Prompt):
    __gtype_name__ = "ScreenCast"
    niri_sessions = {}
    sessions = {}
    session = GObject.Property(type=str)
    video_selected = GObject.Property(type=str)
    audio_selected = GObject.Property(type=str)
    file = GObject.Property(type=Gio.File)
    show_cursor = GObject.Property(type=bool, default=True)
    gpu_screen_recorder = GObject.Property(type=bool, default=False)
    invocation = GObject.Property(type=Gio.DBusMethodInvocation)
    options = GObject.Property(type=object)
    iface = "org.gnome.Mutter.ScreenCast"
    watcher = None

    def __init__(self, inv=None, p=None, audio_select=False):
        ScreenCast.watch()
        super().__init__(callback=self.__class__.do, confirm_callback=False)
        self.invocation = inv
        self.audios, self.videos = {}, {}
        box = Gtk.ListBox(css_classes=("boxed-list", "main"), selection_mode=Gtk.SelectionMode.NONE)
        self.set_properties(heading="Start Share" if self.invocation else "Start Recording", extra_child=box)
        if not self.invocation:
            self.gpu_screen_recorder = ImageCopy.get_gsr()
        if self.gpu_screen_recorder: Task(self.__class__.get_gsr_options, self).start()
        else:
            if not self.invocation:
                self.videos["None"] = False
            toplevels = getattr(ImageCopy, "toplevel_capture", False)
            if hasattr(ImageCopy, "manager"):
                if not Gst.is_initialized(): Gst.init()
                for i in Gdk.Display.get_default().get_monitors():
                    self.videos[i.get_connector()] = i
                self.videos["Select Area"] = "Select Area"
            if self.invocation and p and hasattr(self.__class__, "iface") and hasattr(Niri, "connection"):
                self.session = self.__class__.niri_sessions[p[1]]
                self.videos["niri Dynamic Cast Target"] = 1
                toplevels = True
            if toplevels and ImageCopy.toplevel_list.name.decode() in Wayland.interfaces:
                o = Wayland.registry.bind(ImageCopy.toplevel_list, *Wayland.interfaces[ImageCopy.toplevel_list.name.decode()])
                o.screencast = self
                o.dispatcher(ImageCopy.toplevel_list_dispatcher)
                Gdk.Display.get_default().sync()
                o.stop()
            Task.invoke(self.setup, audio_select)

    def setup(self, audio_select):
        if not self.videos: return self.invocation.return_value(GLib.Variant("(ua{sv})", (1, {}))) if self.invocation else None
        select = Adw.ComboRow(title="Video Source", model=Gtk.StringList.new(tuple(self.videos.keys())))
        box = self.get_extra_child()
        box.append(select)
        if audio_select:
            if not hasattr(self, "audios"):
                self.audios = {"None": False}
            if not self.gpu_screen_recorder:
                lines = GLib.spawn_command_line_sync("wpctl status")[1].decode().splitlines()
                result = []
                for n, i in enumerate(lines):
                    if i == "Audio":
                        lines = lines[n:]
                        break
                group = ""
                previous = ""
                for n, i in enumerate(lines):
                    if not i: break
                    if not group:
                        group = i if i.endswith(("Sinks:", "Sources:", "Streams:")) else ""
                        continue
                    if len(i) == 4:
                        group = ""
                        continue
                    if ". input_" in i or ". output_" in i: continue
                    if ". monitor_" in i:
                        if previous:
                            previous = ""
                        continue
                    if previous: result.append(previous)
                    previous = i.split(".", 1)[0].replace("│", "").replace("*", "").strip()
                if previous: result.append(previous)
                for _id in result:
                    r = GLib.spawn_command_line_sync(f"wpctl inspect {_id}")[1].decode()
                    if not "object.serial = \"" in r: continue
                    name = ""
                    for i in ("media.name", "node.description"):
                        if not name and i in r:
                            name = r.split(f"{i} = \"", 1)[-1].split("\n", 1)[0].split("\"", 1)[0]
                    if "port.group = \"capture\"" in r:
                        name = "(Input) " + name
                    if name:
                        self.audios[unique_name(name, self.audios)] = r.split("object.serial = \"", 1)[-1].split("\"", 1)[0]
            s = Adw.ComboRow(title="Audio Source", model=Gtk.StringList.new(tuple(self.audios.keys())))
            s.bind_property("selected-item", self, "audio-selected", DEFAULT_BIND, self.__class__.select_bind)
            box.append(s)
        r = Adw.SwitchRow(title="Show Cursor", active=True)
        r.bind_property("active", self, "show-cursor", DEFAULT_BIND)
        box.append(r)
        if not self.invocation:
            select.bind_property("selected", r, "visible", DEFAULT_BIND, self.__class__.cursor_bind)
            r = Adw.ActionRow(title="Save Location")
            b = Button(callback=self.__class__.select_file, icon_name="folder-open", valign=Gtk.Align.CENTER, bindings=[(self, "file", None, "tooltip-text", None, self.__class__.file_bind)])
            r.add_suffix(b)
            box.append(r)
        select.bind_property("selected-item", self, "video-selected", DEFAULT_BIND, self.__class__.select_bind)
        self.present()

    @staticmethod
    def get_gsr_options(self):
        r = str_to_list(GLib.spawn_command_line_sync(f"{ImageCopy.gsr} --list-capture-options")[1].decode())
        self.videos["Select Area"] = "Select Area"
        self.videos.update(dict((i.split("|", 1)[0], i.split("|", 1)[0]) for i in r if not i in ("portal", "region")))
        self.audios = {"None": False}
        for i in ("audio-devices", "application-audio"):
            r = str_to_list(GLib.spawn_command_line_sync(f"{ImageCopy.gsr} --list-{i}")[1].decode())
            for it in r:
                if it.startswith(("default_output", "default_input")): continue
                self.audios[it.split("|", 1)[-1]] = ("device:" if "device" in i else "app:") + it.split("|", 1)[0]
        Task.invoke(self.setup, True)

    @staticmethod
    def cursor_bind(b, v): return v != 0

    @staticmethod
    def file_bind(b, v): return v.get_uri() if v else ""

    def get_filename(self): return f"{GLib.DateTime.new_now_local().format('%Y%m%d%H%M%S')}.mp4"

    @staticmethod
    def select_file(b):
        self = b.get_ancestor(ScreenCast)
        if not self: return
        FileDialog(initial_name=self.get_filename()).save(callback=self.__class__.do_select_file, data=self)

    @staticmethod
    def do_select_file(d, r, self):
        try:
            self.file = d.save_finish(r)
        except:
            self.file = None

    @staticmethod
    def stop_recording(d):
        if getattr(d, "pipeline", None):
            pipeline = d.pipeline
            del d.pipeline
            p = pipeline.get_by_name("PipeWire")
            if p: p.send_event(Gst.Event.new_eos())
            if getattr(pipeline, "source", False): pipeline.source.emit("end-of-stream")
            bus = pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message", ScreenCast.do_finish, pipeline)
            pipeline.send_event(Gst.Event.new_eos())
        if hasattr(d, "pid"): GLib.spawn_command_line_sync(f"pkill -SIGINT -p {d.pid}")

    @staticmethod
    def do_finish(bus, message, pipeline):
        if message.type == Gst.MessageType.ERROR or message.type == Gst.MessageType.EOS: Task.invoke(pipeline.set_state, Gst.State.NULL)

    @staticmethod
    def do_pick(arg, self):
        if arg == False: self.__class__.do(self, "cancel")
        else: self.__class__.do(self, "confirm", tuple(arg))

    @staticmethod
    def do(self, c, result=False):
        if c != "confirm":
            if self.invocation: self.invocation.return_value(GLib.Variant("(ua{sv})", (1, {})))
            return
        vs = self.videos[self.video_selected]
        if vs == "Select Area" and not result:
            Selector(function_data=self, function=self.__class__.do_pick)
            return
        if not self.invocation:
            if self.video_selected == "None" and self.videos["None"] == False and self.audio_selected == "None" and self.audios["None"] == False: return
            plaunch = ""
            video = audio = False
            if vs:
                if result:
                    video, x, y, w, h = result
                else:
                    video, x, y, w, h = vs, -1, -1, 0, 0
                if isinstance(video, Gdk.Monitor):
                    g = video.get_geometry()
                    crop = ImageCopy.get_crop(W=g.width, H=g.height, w=w, h=h, x=x, y=y)
                    plaunch += f" appsrc emit-signals=false format=time do-timestamp=true is-live=true max-buffers=4 block=false name=Source ! video/x-raw,format={ImageCopy.get_default_format()},width={g.width},height={g.height},framerate=60/1 !{crop} vapostproc ! vah264enc ! h264parse ! queue ! Mux."
            if self.audios.get(self.audio_selected, False) != False:
                audio = self.audios[self.audio_selected]
                plaunch += " pipewiresrc name=PipeWire do-timestamp=true provide-clock=false ! queue max-size-time=500000000 ! audioconvert ! audioresample ! audio/x-raw,rate=48000,channels=2 ! opusenc bitrate-type=cbr bitrate=128000 frame-size=20 ! queue ! Mux."
            if not (audio or video): return
            p = Prompt(heading="Stop Recording", callback=self.__class__.stop_recording)
            p.remove_response("cancel")
            plaunch = plaunch.strip() + f" mp4mux name=Mux ! filesink name=File"
            if self.gpu_screen_recorder:
                command = ["/bin/flatpak-spawn", "--host"] if FLATPAK_ID else []
                command.extend([ImageCopy.gsr, "-cursor", "yes" if self.show_cursor else "no", "-o", self.file.get_path() if self.file else self.get_filename()])
                if video:
                    if isinstance(video, Gdk.Monitor): command.extend(["-w", f"{w}x{h}+{x}+{y}"])
                    else: command.extend(["-w", video])
                if audio: command.extend(["-a", audio])
                success, p.pid, stdin_fd, stdout_fd, stderr_fd = GLib.spawn_async_with_pipes(argv=command, flags=GLib.SpawnFlags.DEFAULT | GLib.SpawnFlags.CHILD_INHERITS_STDERR)
            else:
                pipeline = p.pipeline = Gst.parse_launch(plaunch.strip())
                pipeline.get_by_name("File").set_property("location", self.file.get_uri() if self.file else self.get_filename())
                if audio: pipeline.get_by_name("PipeWire").set_property("target-object", audio)
                if video:
                    pipeline.source = pipeline.get_by_name("Source")
                    pipeline.args = {"source": video, "cursor": self.show_cursor}
                    frame = ImageCopy.capture_frame(**pipeline.args)
                    if not frame: return
                    frame.prompt = p
                    frame.do_ready = self.__class__.recording_do_ready
                    pipeline.set_state(Gst.State.PLAYING)
                else: pipeline.set_state(Gst.State.PLAYING)
            p.present()
        elif not isinstance(vs, Gdk.Monitor) and not result and self.session and hasattr(Niri, "connection") and SESSION:
            b = Gio.DBusProxy.new_sync(SESSION, Gio.DBusProxyFlags.NONE, None, self.__class__.iface, self.session, self.__class__.iface + ".Session", None)
            SESSION.signal_subscribe(None, self.__class__.iface + ".Stream", "PipeWireStreamAdded", b.call_sync("RecordWindow", GLib.Variant("(a{sv})", ({"window-id": GLib.Variant("t", int(vs)), "cursor-mode": GLib.Variant("u", int(self.show_cursor))}, )), Gio.DBusCallFlags.NONE, 5000, None)[0], None, Gio.DBusSignalFlags.NONE, self.__class__.stream_added, self)
            b.call_sync("Start", None, Gio.DBusCallFlags.NONE, 5000, None)
        else:
            vs = result or vs
            for k, v in ScreenCast.sessions.items():
                if v["Video Source"] == vs and v["Show Cursor"] == self.show_cursor: return ScreenCast.sessions[k]["Invocations"].append(self.invocation)
            n = str(len(tuple(ScreenCast.sessions.keys())))
            ScreenCast.sessions[n] = {
                "Invocations": [self.invocation],
                "Video Source": vs,
                "Show Cursor": self.show_cursor
            }
            if self.audios:
                ScreenCast.sessions[n]["Audio Source"] = self.audios[self.audio_selected]
            a = vs if isinstance(vs, tuple) else False
            ScreenCast.sessions[n]["Args"] = args = {"source": a[0] if a else vs, "x": a[1] if a else -1, "y": a[2] if a else -1, "w": a[3] if a else 0, "h": a[4] if a else 0, "cursor": self.show_cursor}
            ScreenCast.watch()
            frame = ImageCopy.capture_frame(source=args["source"], cursor=args["cursor"])
            if not frame: return
            frame.session, frame.do_ready = n, self.__class__.share_do_ready

    @staticmethod
    def select_bind(b, v): return v.get_string()

    @staticmethod
    def watch():
        for i in [i for i in ScreenCast.sessions.values()]:
            p = i.get("Pipeline", False)
            if p and (not hasattr(p, "node_id") or not 'state: "running"' in GLib.spawn_command_line_sync(f"/bin/pw-cli info {p.node_id}")[1].decode()): ImageCopy.destroy_object(p)
        v = bool(ScreenCast.sessions)
        if not v and hasattr(ScreenCast, "watcher"):
            del ScreenCast.watcher
        return v

    @staticmethod
    def recording_do_ready(proxy, buffer):
        if not hasattr(proxy, "prompt"): return
        if not hasattr(proxy.prompt, "pipeline"):
            del proxy.prompt
            return
        pipeline = proxy.prompt.pipeline
        pipeline.source.emit("push-buffer", buffer)
        ImageCopy.new_frame(proxy, ImageCopy.capture_frame(add_user=False, **pipeline.args))

    @staticmethod
    def share_do_ready(proxy, buffer):
        if not hasattr(proxy, "session"): return
        if not proxy.session in ScreenCast.sessions:
            Task.invoke(ImageCopy.destroy_object, proxy)
            return
        args = ScreenCast.sessions[proxy.session]["Args"]
        if not ScreenCast.sessions[proxy.session].get("Pipeline", False):
            crop = ImageCopy.get_crop(W=proxy.width, H=proxy.height, w=args["w"], h=args["h"], x=args["x"], y=args["y"])
            p = f"appsrc emit-signals=false format=time do-timestamp=true is-live=true max-buffers=4 block=false name=Source ! video/x-raw,format={ImageCopy.get_default_format()},width={proxy.width},height={proxy.height},framerate=60/1 !{crop} vapostproc ! pipewiresink name=PipeWire client_name=shell-screencast-{proxy.session} mode=2"
            ScreenCast.sessions[proxy.session]["Pipeline"] = pipeline = Gst.parse_launch(p)
            pipeline.session = proxy.session
            pipeline.pipewire, pipeline.source = [pipeline.get_by_name(i) for i in ("PipeWire", "Source")]
            pipeline.set_bus(None)
            pipeline.set_properties(async_handling=False, message_forward=False)
            pipeline.set_state(Gst.State.PLAYING)
            if getattr(ScreenCast, "watcher", False):
                try: GLib.source_remove(ScreenCast.watcher)
                except: pass
            ScreenCast.watcher = GLib.timeout_add(1000 * 10, ScreenCast.watch)
        pipeline = ScreenCast.sessions[proxy.session]["Pipeline"]
        pipeline.source.emit("push-buffer", buffer)
        if not hasattr(pipeline, "node_id"):
            try:
                pipeline.node_id = int(GLib.spawn_command_line_sync("wpctl status")[1].decode().split(". " + pipeline.pipewire.get_property("client-name"), 1)[0].rsplit(" ", 1)[-1])
                pipeline.serial = int(GLib.spawn_command_line_sync(f"wpctl inspect {pipeline.node_id}")[1].decode().split("object.serial = \"", 1)[-1].split("\"", 1)[0])
            except: pass
        if hasattr(pipeline, "node_id") and ScreenCast.sessions[proxy.session]["Invocations"]:
            for i in [i for i in ScreenCast.sessions[proxy.session]["Invocations"]]:
                if ScreenCast.sessions[proxy.session].get("Audio Source", False): pass
                i.return_value(GLib.Variant("(ua{sv})", (0, { "streams": GLib.Variant("a(ua{sv})", [(pipeline.node_id, {"position": GLib.Variant("(ii)", (0, 0)), "size": GLib.Variant("(ii)", (1, 1)), "source_type": GLib.Variant("u", 1)}), ]), "persist_mode": GLib.Variant("u", 0), "pipewire-serial": GLib.Variant("t", pipeline.serial)})))
                ScreenCast.sessions[proxy.session]["Invocations"].remove(i)
        ImageCopy.new_frame(proxy, ImageCopy.capture_frame(add_user=False, source=args["source"], cursor=args["cursor"]))

    @staticmethod
    def stream_added(conn, sender, signal, path, iface, params, self): self.invocation.return_value(GLib.Variant("(ua{sv})", (0, { "streams": GLib.Variant("a(ua{sv})", [(params[0], {"size": GLib.Variant("(ii)", (1, 1)), "source_type": GLib.Variant("u", 2)}), ]), "persist_mode": GLib.Variant("u", 0), })))

class Screenshot:
    @staticmethod
    def finish(proxy, buffer):
        data, x, y, width, height = proxy.function_data
        crop = ImageCopy.get_crop(W=proxy.width, H=proxy.height, w=width, h=height, x=x, y=y)
        pipeline = Gst.parse_launch(f"appsrc emit-signals=false format=time do-timestamp=true is-live=true max-buffers=4 block=false name=Source ! video/x-raw,format={ImageCopy.get_default_format()},width={proxy.width},height={proxy.height},framerate=1/1 !{crop} vapostproc ! pngenc ! filesink name=File location={GLib.DateTime.new_now_local().format('%Y%m%d%H%M%S')}.png")
        del proxy.function_data
        pipeline.set_bus(None)
        pipeline.set_properties(async_handling=False, message_forward=False)
        pipeline.set_state(Gst.State.PLAYING)
        pipeline.get_by_name("Source").emit("push-buffer", buffer)
        pipeline.get_state(1 * Gst.SECOND)
        file = pipeline.get_by_name("File").get_property("location")
        ImageCopy.destroy_object(pipeline)
        if isinstance(data, Gio.DBusMethodInvocation):
            file = Gio.File.new_for_path(file)
            if getattr(Clipboard, "instance", False): Clipboard.set({"text/uri-list": file.get_uri().encode()})
            else:
                Gdk.Display.get_default().get_clipboard().set(Gdk.FileList.new_from_list([file]))
                Gdk.Display.get_default().flush()
            if data.get_object_path().endswith("Shell"): Task.invoke(data.return_value, GLib.Variant("(s)", (file.get_path(),)))
            else: Task.invoke(data.return_value, GLib.Variant("(ua{sv})", (0, {"uri": GLib.Variant("s", file.get_uri())})))

    @staticmethod
    def check(event, file):
        if event.is_set(): return
        if exists(file):
            event.set()
            return
        return True

    @staticmethod
    def do_pick(arg, data):
        if arg == False:
            if isinstance(data, Gio.DBusMethodInvocation):
                if data.get_object_path().endswith("Shell"): Task.invoke(data.return_value, GLib.Variant("(s)", ("",)))
                else: Task.invoke(data.return_value, GLib.Variant("(ua{sv})", (1, {})))
        else: Screenshot.do(output=arg[0], x=arg[1], y=arg[2], width=arg[3], height=arg[4], function=Screenshot.finish, data=data)

    @staticmethod
    def do(output=None, x=-1, y=-1, width=0, height=0, function=None, data=None):
        if not Gst.is_initialized(): Gst.init()
        frame = ImageCopy.capture_frame(source=output)
        if not frame: return
        frame.do_ready = Screenshot.finish
        frame.function_data = [data, x, y, width, height]

class Player(Window):
    __gtype_name__ = "Player"
    players = []
    current = 0
    loops = {"None": "consecutive", "Track": "repeat-song", "Playlist": "repeat"}
    properties_iface = "org.freedesktop.DBus.Properties"
    iface = "org.mpris.MediaPlayer2"
    playback = GObject.Property(type=Gtk.Button)
    previous = GObject.Property(type=Gtk.Button)
    loop = GObject.Property(type=Gtk.Button)
    volume_button = GObject.Property(type=VolumeButton)
    speed_button = GObject.Property(type=SpeedButton)
    shift = GObject.Property(type=Gtk.Button)
    unshift = GObject.Property(type=Gtk.Button)
    shuffle = GObject.Property(type=Gtk.ToggleButton)
    next = GObject.Property(type=Gtk.Button)
    empty = GObject.Property(type=Adw.StatusPage)
    controls = GObject.Property(type=Gtk.CenterBox)
    cover = GObject.Property(type=Gtk.Picture)
    default_cover = GObject.Property(type=Gdk.Paintable)
    spinner = GObject.Property(type=Gdk.Paintable)

    @GObject.Property(type=float, flags=GObject.ParamFlags.READWRITE)
    def volume(self): return self._volume

    @volume.setter
    def volume(self, value):
        self._volume = value
        if not Player.players or self.updating or not self.volume_button.get_mapped(): return
        if SESSION: Gio.DBusProxy.new_sync(SESSION, Gio.DBusProxyFlags.NONE, None, Player.players[Player.current], Player.path, Player.properties_iface, None).call_sync("Set", GLib.Variant("(ssv)", (Player.player_iface, "Volume", GLib.Variant("d", value))), Gio.DBusCallFlags.NONE, 5000, None)

    @GObject.Property(type=float, flags=GObject.ParamFlags.READWRITE, minimum=-10.0, maximum=10.0)
    def speed(self): return self._speed

    @speed.setter
    def speed(self, value):
        self._speed = value
        if not Player.players or self.updating or not self.speed_button.get_mapped(): return
        if SESSION: Gio.DBusProxy.new_sync(SESSION, Gio.DBusProxyFlags.NONE, None, Player.players[Player.current], Player.path, Player.properties_iface, None).call_sync("Set", GLib.Variant("(ssv)", (Player.player_iface, "Rate", GLib.Variant("d", value))), Gio.DBusCallFlags.NONE, 5000, None)

    def __init__(self):
        self.updating = False
        self._speed = self._volume = 0.0
        super().__init__()
        self.add_css_class("player")
        try:
            self.default_cover = Gtk.Svg.new_from_resource("/org/gtk/libgtk/icons/folder-music-symbolic.svg")
        except:
            self.default_cover = Gtk.IconPaintable.new_for_file(Gio.File.new_for_path("/usr/share/icons/Adwaita/symbolic/places/folder-music-symbolic.svg"), 1, 1)
        self.spinner = Adw.SpinnerPaintable.new(self)
        self.set_properties(title="Player", hide_on_close=True, default_width=360, default_height=364)
        centerbox = Gtk.Box(valign=Gtk.Align.END, halign=Gtk.Align.CENTER, hexpand=True)
        self.backward = Button(css_classes=("flat",), callback=self.__class__.callback, icon_name="media-seek-backward", tooltip_text="Backward")
        self.forward = Button(css_classes=("flat",), callback=self.__class__.callback, icon_name="media-seek-forward", tooltip_text="Forward")
        self.playback = Button(css_classes=("flat", "circular", "playback"), callback=self.__class__.callback, bindings=((None, "tooltip-text", None, "icon-name", None, PlaybackButton.icon_bind),))
        self.previous = Button(css_classes=("flat",), callback=self.__class__.callback, icon_name="media-skip-backward", tooltip_text="Previous")
        self.next = Button(css_classes=("flat",), callback=self.__class__.callback, icon_name="media-skip-forward", tooltip_text="Next")
        for i in (self.previous, self.backward, self.forward, self.next): i.add_css_class(i.get_tooltip_text().lower())
        for i in (self.previous, self.playback, self.next): centerbox.append(i)
        leftbox, rightbox = [Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.END) for _ in range(2)]
        self.shuffle = Button(t=Gtk.ToggleButton, icon_name="media-playlist-shuffle", css_classes=("flat",), tooltip_text="Shuffle", callback=self.__class__.callback)
        self.volume_button = VolumeButton(media=self)
        self.speed_button = SpeedButton(media=self)
        for i in (self.volume_button, self.speed_button, self.backward): leftbox.append(i)
        self.loop = Button(css_classes=("flat",), callback=self.__class__.callback, tooltip_text="None", bindings=((None, "tooltip-text", None, "icon-name", None, self.__class__.update_loop_icon_name),))
        self.unshift = Button(css_classes=("flat",), callback=self.__class__.callback, icon_name="go-previous", tooltip_text="Previous Player")
        self.shift = Button(css_classes=("flat",), callback=self.__class__.callback, icon_name="go-next", tooltip_text="Next Player")
        self.shift.bind_property("visible", self.unshift, "visible", DEFAULT_BIND)
        for i in (self.shuffle, self.loop, self.forward): rightbox.append(i)
        self.controls = Gtk.CenterBox(css_name="controls", valign=Gtk.Align.END, start_widget=leftbox, center_widget=centerbox, end_widget=rightbox)
        self.cover = Gtk.Picture(content_fit=Gtk.ContentFit.COVER)
        overlay = Gtk.Overlay(child=self.cover)
        overlay.add_overlay(self.controls)
        self.controls.bind_property("visible", self.cover, "visible", DEFAULT_BIND)
        self.empty = Adw.StatusPage(icon_name="folder-music-symbolic", title="Nothing Playing...")
        self.empty.bind_property("visible", self.controls, "visible", INVERT_BIND)
        overlay.add_overlay(self.empty)
        self.set_content(Gtk.WindowHandle(child=overlay))
        header = Gtk.CenterBox(valign=Gtk.Align.START, start_widget=self.unshift, center_widget=Adw.WindowTitle(), end_widget=self.shift)
        self.bind_property("title", header.get_center_widget(), "title", DEFAULT_BIND)
        overlay.add_overlay(header)
        self.__class__.instance = self
        self.__class__.player_iface = self.__class__.iface + ".Player"
        self.__class__.path = "/" + self.__class__.iface.replace(".", "/")
        if SESSION:
            SESSION.signal_subscribe(None, "org.freedesktop.DBus", "NameOwnerChanged", "/org/freedesktop/DBus", None, Gio.DBusSignalFlags.NONE, self.on_name_owner_changed)
            proxy = Gio.DBusProxy.new_sync(SESSION, Gio.DBusProxyFlags.NONE, None, "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", None)
            res = proxy.call_sync("ListNames", None, Gio.DBusCallFlags.NONE, -1, None)
            names = res.unpack()[0]
            for n in names:
                if n.startswith(Player.iface + ".") and n not in self.__class__.players: self.__class__.players.append(n)
            SESSION.signal_subscribe(None, "org.freedesktop.DBus.Properties", "PropertiesChanged", Player.path, None, Gio.DBusSignalFlags.NONE, self.__class__.properties_changed)
        self.__class__.update()

    @staticmethod
    def on_key_pressed(e, v, c, s):
        if v == Gdk.KEY_Escape: e.get_widget().get_root().set_visible(False)

    @staticmethod
    def callback(b, p=None):
        self = b.get_root()
        if self.updating: return
        if b in (self.previous, self.backward, self.forward, self.next): call(i=PLAYER_IFACE, m=b.get_tooltip_text())
        if b == self.playback: call(i=PLAYER_IFACE, m="PlayPause")
        if b == self.shift: call(i=PLAYER_IFACE, m="Shift")
        if b == self.unshift: call(i=PLAYER_IFACE, m="Unshift")
        if b == self.loop: call(i=PLAYER_IFACE, m="Loop")
        if b.get_visible() and b == self.shuffle: call(i=PLAYER_IFACE, m="Shuffle")

    @staticmethod
    def update_loop_icon_name(b, v): return "media-playlist-" + next((f for s, f in Player.loops.items() if s == v), "")

    @staticmethod
    def do():
        Player.update(force=True)
        if Player.instance.get_mapped(): Player.instance.set_visible(False)
        else: Player.instance.present()

    @staticmethod
    def on_name_owner_changed(conn, sender, signal, path, iface, params):
        old_owner, new_owner = params.unpack()[1:3]
        name = params.unpack()[0]
        if not name.startswith(Player.iface + "."): return
        if new_owner:
            if name not in Player.players: Player.players.append(name)
        else:
            if name in Player.players:
                if Player.players.index(name) == Player.current:
                    Player.current = 0
                Player.players.remove(name)
        Task.invoke(Player.update)

    @staticmethod
    def finish_func(paintable): Player.instance.cover.set_paintable(paintable)

    @staticmethod
    def properties_changed(*args): Task.invoke(Player.update)

    @staticmethod
    def update(*_, force=False):
        if not force and not Player.instance.get_mapped(): return
        self = Player.instance
        self.empty.set_visible(not bool(Player.players))
        if self.empty.get_visible(): return
        current = Player.players[Player.current]
        props = Gio.DBusProxy.new_sync(SESSION, Gio.DBusProxyFlags.NONE, None, current, Player.path, Player.properties_iface, None).call_sync("GetAll", GLib.Variant("(s)", (Player.player_iface,)), Gio.DBusCallFlags.NONE, 5000, None) if SESSION else None
        if not props: return
        self.updating = True
        props = props[0]
        u = props.get("Metadata", {}).get("mpris:artUrl", False)
        self.cover.remove_css_class("default")
        if u:
            if not (self.cover.get_paintable() and getattr(self.cover.get_paintable(), "uri", "") == u):
                self.cover.set_paintable(self.spinner)
                PaintableTask(func=self.__class__.finish_func, uri=u)
        else:
            self.cover.set_paintable(self.default_cover)
            self.cover.add_css_class("default")
        self.volume_button.set_visible("Volume" in props)
        self._volume = props.get("Volume", 0.0)
        self.notify("volume")
        self.speed_button.set_visible("Rate" in props and not (props.get("MinimumRate", 1.0) == props.get("MaximumRate", 1.0)))
        self._speed = props.get("Rate", 0.0)
        self.notify("speed")
        self.previous.set_sensitive(props.get("CanGoPrevious", False))
        self.next.set_sensitive(props.get("CanGoNext", False))
        self.loop.set_visible("LoopStatus" in props)
        self.loop.set_tooltip_text(props.get("LoopStatus", "None"))
        self.shuffle.set_visible("Shuffle" in props)
        self.shuffle.set_active(props.get("Shuffle", False))
        self.shift.set_visible(len(Player.players) > 1)
        self.playback.set_sensitive(props.get("CanPause", False) and props.get("CanPlay", False))
        self.playback.set_tooltip_text(PlaybackButton.playing_bind2(None, props.get("PlaybackStatus", None) == "Playing"))
        self.set_title(props.get("Metadata", {}).get("xesam:title", "Player"))
        self.updating = False

class AccessDialog(Prompt):
    __gtype_name__ = "AccessDialog"
    def __init__(self, inv, handle, app_id, parent_window, title, subtitle, body, options):
        self.responses = (options.get("deny_label", "cancel"), options.get("grant_label", "confirm"))
        super().__init__(confirm_callback=False, callback=self.__class__.response, responses=self.responses, heading=title, extra_child=Gtk.Label(wrap=True, label=f"{subtitle}\n{body}".strip(), justify=Gtk.Justification.CENTER) if body or subtitle else None)
        self.inv = inv
        self.present()

    @staticmethod
    def response(self, r):
        if not self.inv: return
        if r == self.responses[0]: self.inv.return_value(GLib.Variant("(ua{sv})", (1, {})))
        else: self.inv.return_value(GLib.Variant("(ua{sv})", (0, {})))
        self.inv = None

class Settings:
    def __init__(self):
        super().__init__()
        APPEARANCE_NAMESPACE = "org.freedesktop.appearance"
        DESKTOP_NAMESPACE = "org.gnome.desktop.interface"
        WM_NAMESPACE = "org.gnome.desktop.wm.preferences"
        self.__class__.namespaces = {
            "color-scheme": (APPEARANCE_NAMESPACE,),
            "contrast": (APPEARANCE_NAMESPACE,),
            "reduced-motion": (APPEARANCE_NAMESPACE,),
            "accent-color": (APPEARANCE_NAMESPACE,),
            "font-name": (DESKTOP_NAMESPACE, "gtk-font-name"),
            "document-font-name": (DESKTOP_NAMESPACE,),
            "monospace-font-name": (DESKTOP_NAMESPACE,),
            "icon-theme": (DESKTOP_NAMESPACE, "gtk-icon-theme-name"),
            "text-scaling-factor": (DESKTOP_NAMESPACE,),
            "gtk-enable-primary-paste": (DESKTOP_NAMESPACE, "gtk-enable-primary-paste"),
            "button-layout": (WM_NAMESPACE, "gtk-decoration-layout"),
            "theme": (DESKTOP_NAMESPACE, "gtk-theme-name")
        }
        self.__class__.instance = self
        App.default.get_style_manager().set_color_scheme(Adw.ColorScheme.FORCE_DARK if Data.setting("Color Scheme", "Light") == "Dark" else Adw.ColorScheme.FORCE_LIGHT)
        for i in ("color-scheme", "accent-color-rgba", "document-font-name", "monospace-font-name"): App.default.get_style_manager().connect(f"notify::{i}", self.__class__.changed)

    @staticmethod
    def changed(self=None, p="", get=False):
        self = Settings.instance
        name = p if isinstance(p, str) else p.get_name()
        if not name in self.__class__.namespaces: return
        if len(self.__class__.namespaces[name]) == 2:
            value = get_variant(Gtk.Settings.get_default().get_property(self.__class__.namespaces[name][-1]))
        elif name == "color-scheme":
            v = App.default.get_style_manager().get_color_scheme()
            Data.setting("Color Scheme", "Light", "Light" if v == Adw.ColorScheme.FORCE_LIGHT else "Dark")
            value = GLib.Variant.new_uint32(1 if v == Adw.ColorScheme.FORCE_DARK else 2 if v == Adw.ColorScheme.FORCE_LIGHT else 0)
        elif name == "accent-color":
            value = GLib.Variant.new_tuple(*tuple(GLib.Variant("d", i) for i in RGBA.rgb(App.default.get_style_manager().get_accent_color_rgba(), True)))
        elif name == "text-scaling-factor":
            value = get_variant(1.0)
        elif name == "reduced-motion":
            value = GLib.Variant.new_uint32(int(Gtk.Settings.get_default().get_property("gtk-interface-reduced-motion")))
        elif name == "contrast":
            v = Gtk.Settings.get_default().get_property("gtk-interface-contrast")
            if v == Gtk.InterfaceContrast.MORE:
                v = 1
            else:
                v = 0
            value = GLib.Variant.new_uint32(int(v))
        elif name in ("document-font-name", "monospace-font-name"):
            value = get_variant(App.default.get_style_manager().get_property(name))
        else:
            value = get_variant("")
        if get: return value
        if hasattr(Niri, "connection"): Niri.request("Action", { "DoScreenTransition": {} })
        App.default.get_dbus_connection().emit_signal(None, "/org/freedesktop/portal/desktop", f"{PT_ID}.Settings", "SettingChanged", GLib.Variant("(ssv)", (self.__class__.namespaces[name][0], name, value)))

def call(dbus=None, _c=None, _s=None, _o=None, i="", m="", p=None, inv=None):
    p = p or []
    if i == App.default.get_application_id():
        if m == "CursorButton" and getattr(Pointer, "instance", False): Pointer.send(key=p[0], hold=p[1], release=p[2])
        if m == "CursorScroll" and getattr(Pointer, "instance", False): Pointer.scroll(x=p[0], y=p[1])
        if m == "CursorMotion" and getattr(Pointer, "instance", False): Pointer.mouse(x=p[0], y=p[1])
        if m == "ScreenRecord": ScreenCast(audio_select=True)
        if m == "Controllers": Controllers.do()
        if Gst and m == "Screenshot": return Screenshot.do(data=inv if inv else False)
        if Gst and m == "ScreenshotArea": return Selector(function_data=inv if inv else False, function=Screenshot.do_pick)
        if m == "Notifications": Notifications.do()
        if m == "Exit": exit()
        if m == "Key" and getattr(Keyboard, "instance", False): Keyboard.send(key=p[0], hold=p[1], release=p[2])
        if m == "Keyboard" and getattr(Keyboard, "instance", False): Keyboard.do()
        if m == "Clipboard" and getattr(Clipboard, "instance", False): Clipboard.do()
        if m == "Copy": Clipboard.set(p[0])
        if m == "Paste":
            v = ""
            item = ClipboardData.list[0]
            if item and "text/plain;charset=utf-8" in item.mimetypes:
                v = item.mimetypes["text/plain;charset=utf-8"].decode("utf-8")
            return inv.return_value(GLib.Variant("(s)", (v,))) if inv else None
        if m == "Apps": Apps.do()
        if m == "Player": Player.do()
        if m == "ColorScheme" and getattr(Settings, "instance", False): App.default.get_style_manager().set_color_scheme(Adw.ColorScheme.FORCE_DARK if App.default.get_style_manager().get_color_scheme() == Adw.ColorScheme.FORCE_LIGHT else Adw.ColorScheme.FORCE_LIGHT)
        if Gst and m == "Palette" and hasattr(ImageCopy, "manager"): Palette.do()
        return inv.return_value(None) if inv else None
    if i == NF_ID:
        if m == "CloseNotification": return inv.return_value(None) if inv else None
        if m == "GetServerInformation": return inv.return_value(GLib.Variant("(ssss)", ("Shell", "Shell", "1", "1.3"))) if inv else None
        if m == "GetCapabilities": return inv.return_value(GLib.Variant("(as)", (("actions", "body", "body-images", "body-markup", "icon-static", "persistence"),))) if inv else None
        if m == "Notify": return Task(Notifications.add, inv, p).start() if inv else None
    if m == "AddNotification":
        app_id, id, notification = p
        Notification(app=app_id, title=notification.get("title", None), description=notification.get("body", None), display=notification.get("icon", {}))
        return inv.return_value(None) if inv else None
    if m == "RemoveNotification": return inv.return_value(None) if inv else None
    if i == PLAYER_IFACE:
        if not Player.players: return
        if m == "Shift":
            Player.current += 1
            if Player.current >= len(Player.players):
                Player.current = 0
        if m == "Unshift":
            if Player.current == 0:
                Player.current = len(Player.players) - 1
            else:
                Player.current -= 1
        else:
            while Player.current >= len(Player.players):
                Player.current -= 1
        current = Player.players[Player.current]
        if m.startswith(("Play", "Pause", "Next", "Previous")) and SESSION:
            try: Gio.DBusProxy.new_sync(SESSION, Gio.DBusProxyFlags.NONE, None, current, Player.path, Player.player_iface, None).call_sync(m, None, Gio.DBusCallFlags.NONE, 5000, None)
            except Exception as e:
                if " is not available now" in str(e): pass
                else: print(e)
        elif not "hift" in m and SESSION:
            props = Gio.DBusProxy.new_sync(SESSION, Gio.DBusProxyFlags.NONE, None, current, Player.path, Player.properties_iface, None).call_sync("GetAll", GLib.Variant("(s)", (Player.player_iface,)), Gio.DBusCallFlags.NONE, 5000, None)
            if not props: return
            props = props[0]
            if m == "Shuffle" and m in props: Gio.DBusProxy.new_sync(SESSION, Gio.DBusProxyFlags.NONE, None, current, Player.path, Player.properties_iface, None).call_sync("Set", GLib.Variant("(ssv)", (Player.player_iface, m, GLib.Variant("b", not props[m]))), Gio.DBusCallFlags.NONE, 5000, None)
            if m.startswith("Volume") and "Volume" in props: Gio.DBusProxy.new_sync(SESSION, Gio.DBusProxyFlags.NONE, None, current, Player.path, Player.properties_iface, None).call_sync("Set", GLib.Variant("(ssv)", (Player.player_iface, "Volume", GLib.Variant("d", props["Volume"] + (-0.05 if m.endswith("Down") else +0.05)))), Gio.DBusCallFlags.NONE, 5000, None)
            if m == "Loop" and "LoopStatus" in props:
                l = tuple(Player.loops.keys())
                n = l.index(props["LoopStatus"]) + 1
                if n >= len(l):
                    n = 0
                Gio.DBusProxy.new_sync(SESSION, Gio.DBusProxyFlags.NONE, None, current, Player.path, Player.properties_iface, None).call_sync("Set", GLib.Variant("(ssv)", (Player.player_iface, "LoopStatus", GLib.Variant("s", l[n]))), Gio.DBusCallFlags.NONE, 5000, None)
            if m in ("Backward", "Forward") and "Position" in props and props.get("CanSeek", True) == True:
                track = props.get("Metadata", {}).get("mpris:trackid", "/org/mpris/MediaPlayer2/TrackList/NoTrack")
                v = props["Position"] + (-2e6 if m == "Backward" else 2e6)
                p = Gio.DBusProxy.new_sync(SESSION, Gio.DBusProxyFlags.NONE, None, current, Player.path, Player.player_iface, None)
                if track.startswith("/org/mpris/MediaPlayer2/webkit"): p.call_sync("Seek", GLib.Variant("(x)", (v,)), Gio.DBusCallFlags.NONE, 5000, None)
                else: p.call_sync("SetPosition", GLib.Variant("(ox)", ("/org/mpris/MediaPlayer2/TrackList/NoTrack", v)), Gio.DBusCallFlags.NONE, 5000, None)
        Task.invoke(Player.update)
        return inv.return_value(None) if inv else None
    if Gst and m == "CreateSession":
        if hasattr(Niri, "connection") and SESSION and hasattr(ScreenCast, "iface"):
            try:
                r = Gio.DBusProxy.new_sync(SESSION, Gio.DBusProxyFlags.NONE, None, ScreenCast.iface, DBUS.path(ScreenCast.iface), ScreenCast.iface, None).call_sync("CreateSession", GLib.Variant("(a{sv})", ({},)), Gio.DBusCallFlags.NONE, 5000, None)[0]
                ScreenCast.niri_sessions[p[1]] = r
                return inv.return_value(GLib.Variant("(ua{sv})", (0, {"session_id": GLib.Variant("s", r)})))
            except Exception as e: del ScreenCast.iface
        if hasattr(ImageCopy, "manager"): return inv.return_value(GLib.Variant("(ua{sv})", (0, {"session_id": GLib.Variant("s", "1")})))
    if Gst and m == "SelectSources": return inv.return_value(GLib.Variant("(ua{sv})", (0, {})))
    if Gst and m == "Start": return ScreenCast(inv, p)
    if m == "AccessDialog": return AccessDialog(inv, *p)
    if Gst and m == "Screenshot":
        if p[-1].get("interactive", False): return Selector(function_data=inv if inv else False, function=Screenshot.do_pick)
        else: return Screenshot.do(data=inv)
    if Gst and m == "PickColor": return Selector(function_data=inv if inv else False, function=Palette.do_pick, single_pixel=True)
    if AUTHENTICATION_AGENT:
        if m == "BeginAuthentication": return Authorize(inv, p)
        if m == "CancelAuthentication":
            for it in Gtk.Window.get_toplevels():
                if isinstance(it.get_child(), Authorize) and it.get_child().cookie == p[0]: it.get_child().close()
            return
    if m in ("OpenFile", "SaveFile", "SaveFiles"): return PortalFileDialog(inv, m, p)
    if m == "CreateMonitor": return inv.return_value(GLib.Variant("(u)", (1,)))
    if m == "ChooseApplication" and Apps.instance:
        if p[-1].get("content_type", "") == "application/x-executable":
            f = p[-1].get("uri", "").split("file://", 1)[-1]
            GLib.spawn_command_line_async(f'sh -c "cd \"{get_parent(f)}\" && exec \"./{basename(f)}\""')
            return inv.return_value(GLib.Variant("(ua{sv})", (0, {"choice": GLib.Variant("s", "executed"), "activation_token": GLib.Variant("s", p[-1]["activation_token"])})))
        else: return AppChooser(inv, *p)
    if m == "UpdateChoices":
        Apps.update()
        return inv.return_value(None) if inv else None
    if m == "SetWallpaperURI":
        Notification(title=f"Set Wallpaper Request", description=p[3])
        return inv.return_value(GLib.Variant("(u)", (1, ))) if inv else None
    if m == "ReadAll" and getattr(Settings, "instance", False):
        d = {}
        p = p[0]
        if GLib.getenv("GSETTINGS") and any(i == "org.gnome.*" for i in p):
            for i in Gio.SettingsSchemaSource.get_default().list_schemas(False)[0]:
                if i.startswith("org.gnome."):
                    s = Gio.Settings.new(i)
                    d[i] = {}
                    for it in s.get_property("settings-schema").list_keys():
                        d[i][it] = s.get_value(it)
        for i, v in Settings.namespaces.items():
            n = v[0]
            if not any(n.startswith(it.strip("*")) if it.endswith("*") else n == it for it in p): continue
            d.setdefault(n, {})
            d[n][i] = Settings.changed(Settings.instance, i, True)
        return inv.return_value(GLib.Variant("(a{sa{sv}})", (d,)))
    if m == "Read" and getattr(Settings, "instance", False):
        if p[1] in Settings.namespaces:
            v = Settings.changed(Settings.instance, p[1], True)
        elif p[1] in ("cursor-theme", "gtk-cursor-theme-name"):
            v = get_variant(GLib.getenv("XCURSOR_THEME"))
        elif p[1] in ("cursor-size", "gtk-cursor-theme-size"):
            v = get_variant(GLib.getenv("XCURSOR_SIZE"))
        else:
            print("Setting", p, "not found")
            v = get_variant("")
        try:
            if inv: return inv.return_value(GLib.Variant("(v)", (v,)))
            else: return v
        except: print("Except", i, m, p)
    if m == "Get":
        v = None
        if p[1] == "AvailableTargets":
            v = 1 | 4
        if p[1] == "AvailableSourceTypes":
            v = 1 | 2 | 4
        if p[1] == "AvailableCursorModes":
            v = 2
        if p[1] == "SupportedOptions":
            v = {}
        if p[1] == "version":
            v = 0
            if i.endswith("ScreenCast"):
                v = 5 if hasattr(Niri, "connection") else 6
            elif i.endswith("FileChooser"):
                v = 4
            elif i.endswith(("AppChooser", "Settings", "Notification")):
                v = 2
            elif i.endswith(("Screenshot", "Inhibit")):
                v = 3
            elif i.endswith("Clipboard"):
                v = 1
        v = GLib.Variant(dbus.interfaces[p[0]]["properties"][p[1]]["type"], v)
        if inv: return inv.return_value(GLib.Variant("(v)", (v,)))
        else: return v
    if m == "GetAll":
        if p[0] in dbus.interfaces and dbus.interfaces[p[0]].get("properties", False):
            s = dict((it, call(dbus, None, None, None, p[0], "Get", (p[0], it), None)) for it in dbus.interfaces[p[0]]["properties"])
        else:
            s = {}
        if inv: return inv.return_value(GLib.Variant("(a{sv})", (s, )))
        else: return GLib.Variant("a{sv}", s)
    if not (isinstance(i, str) and i.endswith("Inhibit")): print(i, m, p)
    if inv: inv.return_value(None)

def file_open(a, files, *_):
    if Apps.instance:
        for i in files: AppChooser(options={"uri": (("file://" if not i.startswith(("file://", "https://", "http://")) else "") + i) if isinstance(i, str) else i.get_uri(),})

def shutdown(a):
    App.default.data.data.close()
    for i in [i for i in Controller.list]: i.remove()

def install_portal():
    try:
        name = App.default.get_application_id().rsplit(".", 1)[-1]
        t = f"[portal]\nDBusName=org.freedesktop.impl.portal.desktop.{name}\nInterfaces="
        t += ";".join([i for i in PORTAL_DBUS])
        set_contents(Path(ROOT, f"/usr/share/xdg-desktop-portal/portals/{name}.portal"), contents=t)
    except Exception as e: print("Couldn't install portal:", e)

Install.extra = install_portal

register_adapter(dict, json_string)
register_adapter(list, json_string)
register_adapter(tuple, json_string)

App(data="CREATE TABLE IF NOT EXISTS Settings (Key TEXT PRIMARY KEY NOT NULL, Value TEXT);", info=INFO, activate=nothing, file_open=file_open, shutdown=shutdown, about=False, log=False)

VALUE = r"(?:#(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})|rgb\(\s*\d+(?:\.\d+)?\s*,\s*\d+(?:\.\d+)?\s*,\s*\d+(?:\.\d+)?\s*\)|rgba\(\s*\d+(?:\.\d+)?\s*,\s*\d+(?:\.\d+)?\s*,\s*\d+(?:\.\d+)?\s*,\s*(?:0|1|0?\.\d+)\s*\)|hsl\(\s*\d{1,3}(?:\.\d+)?\s*,\s*\d{1,3}(?:\.\d+)?%\s*,\s*\d{1,3}(?:\.\d+)?%\s*\)|hsla\(\s*\d{1,3}(?:\.\d+)?\s*,\s*\d{1,3}(?:\.\d+)?%\s*,\s*\d{1,3}(?:\.\d+)?%\s*,\s*(?:0|1|0?\.\d+)\s*\))"
COLOR = Regex(VALUE)
HAS_COLOR = Regex(rf"^(?:{VALUE}|\[\s*['\"]{VALUE}['\"](?:\s*,\s*['\"]{VALUE}['\"])*\s*\]|\s*{VALUE}(?:\s*,\s*{VALUE})*\s*)$")

APP_CSS = """
.header-suffix { border-spacing: 4px; }

background { color: var(--window-fg-color); }
background .clock { font-size: 20px; margin: 16px; }

wallpaper overlay > widget { transition: all 0.4s;}
wallpaper overlay > before { transition: backdrop-filter ease-in-out 0.4s;}
wallpaper.overview overlay > before { backdrop-filter: blur(10px); }

.player { color: white; background: black;}
.player overlay > box { min-height: 34px; padding: 4px; }
.player controls { border-spacing: 6px; padding: 4px; background: linear-gradient(to top, color-mix(in srgb, black 50%, transparent), transparent); }
.player controls box { border-spacing: 6px; }
.player .default { -gtk-icon-transform: scale(0.8); }
.player.maximized .default { -gtk-icon-transform: scale(0.3); }
.player .backward image,
.player .forward image { -gtk-icon-transform: scale(1.2); }
.player controls > box:nth-child(2) > :nth-child(odd) { transform: scale(1.2); }
.player controls > box:nth-child(2) > :nth-child(2) { transform: scale(1.6); margin: 0px 14px 0px 14px; }
.player controls > box:nth-child(2) { padding-bottom: 10px; }
.player overlay > box,
.player controls { opacity: 0; transition: opacity 0.3s; }
.player:hover overlay > box,
.player:hover controls { opacity: 1; }

apps:drop(active) { box-shadow: none; outline: none; }
apps:drop(active) .highlight { box-shadow: 0 0 0 2px var(--accent-bg-color); }
apps overlay > box { border-spacing: 4px; }
apps overlay > box > label { font-size: 42px; font-weight: bold; }
apps overlay > box > label,
apps gridview { border-spacing: 0px 60px; background: none; padding: 40px; border-radius: 22px; margin: 0px; }
apps gridview child { padding: 0px; }
apps gridview image { -gtk-icon-size: 256px; filter: drop-shadow(0 1px 1px rgba(0, 0, 0, 0.3)); color: white; border-radius: 13px; padding: 12px; transition: all 0.2s; }

.appeditor preferencesgroup { padding: 0px 6px 6px 6px; }

.appchooser gridview { margin: 0px 6px 6px 6px; }
.appchooser gridview child { border-radius: 13px; padding: 6px; transition: all 0.2s; filter: drop-shadow(0 1px 1px rgba(0,0,0, 0.3)); }
.appchooser gridview image { -gtk-icon-size: 100px; }

.palette colorbutton:first-child button { border-radius: 15px 15px 0px 0px; }
.palette colorbutton:last-child button { border-radius: 0px 0px 15px 15px; }
.palette headerbar button { color: white; }
.palette.dark headerbar button { color: rgb(0 0 6 / 80%); }
.palette colorbutton colorswatch,
.palette colorbutton button { border-radius: 0px; padding: 0px; border: none; }

keyboard { border-radius: 15px; }
keyboard .key { font-weight: normal; border-radius: 0px; min-width: 4px; min-height: 0px; padding: 12px 14px; }
keyboard .key:focus-within { outline-color: color-mix(in srgb, var(--accent-color) 50%, transparent); outline-width: 2px; outline-offset: -2px; }
keyboard row:first-child .key:first-child { border-radius: 15px 0px 0px 0px; }
keyboard row:first-child .key:last-child { border-radius: 0px 15px 0px 0px; }
keyboard row:last-child .key:first-child { border-radius: 0px 0px 0px 15px; }
keyboard row:last-child .key:last-child { border-radius: 0px 0px 15px 0px; }
keyboard .modifier label,
keyboard #Esc label { font-weight: bold; }
keyboard .key#Esc label { transform: scale(1.25); }

.clipboard colorbutton button,
.clipboard colorbutton colorswatch { border-radius: 0px; padding: 0px; border: none; }
.clipboard masonry view { margin-top: 0px; }
.clipboard overlay flowbox image { -gtk-icon-size: 44px; }
.clipboard .close-button { padding: 0px; min-width: 24px; min-height: 24px; }
.clipboard masonry column > clipboard > button { margin: 6px; opacity: 0; transition: all 0.3s; }
.clipboard masonry column > clipboard:hover > button,
.clipboard masonry column > clipboard:focus-within > button { opacity: 1; }
.clipboard masonry column > clipboard { min-height: 150px; }
.clipboard masonry column > clipboard > scrolledwindow label { padding: 20px; font-size: 20px; font-weight: bold; }

.notifications listview { background: none; border-spacing: 6px; padding: 0px 6px 6px 6px; }
.notifications listview row { padding: 0px; border-radius: 12px; }
.notifications notification { min-height: 82px; padding: 10px 6px 0px 6px; }
.notifications notification image { margin-bottom: 6px; border-radius: 12px; }
.notifications notification scrolledwindow > viewport > box { padding: 0px 6px 0px 6px; }
.notifications notification .summary { font-size: 18px; }
.notifications notification .close { opacity: 0; transition: opacity 0.3s; min-height: 20px; min-width: 20px; }
.notifications notification:hover .close,
.notifications notification:focus-within .close { opacity: 1; }

.controllers listview { background: none; border-spacing: 6px; padding: 0px 6px 6px 6px; }
"""

PLAYER_IFACE = App.default.get_application_id().replace("Shell", "Player")

SHELL_DBUS = {
    App.default.get_application_id(): {
        "methods": { "Exit": {}, "Apps": {}, "ColorScheme": {}, "Palette": {}, "Clipboard": {}, "Copy": { "text": { "direction": "in", "type": "s" } }, "Paste": { "text": { "direction": "out", "type": "s" } }, "Keyboard": {}, "Key": { "key": { "direction": "in", "type": "s" }, "hold": { "direction": "in", "type": "b" }, "release": { "direction": "in", "type": "b" } }, "Player": {}, "Notifications": {}, "Screenshot": { "path": { "direction": "out", "type": "s" } }, "ScreenshotArea": { "path": { "direction": "out", "type": "s" } }, "Controllers": {}, "ScreenRecord": {}, "CursorMotion": { "x": { "direction": "in", "type": "d" }, "y": { "direction": "in", "type": "d" } }, "CursorScroll": { "x": { "direction": "in", "type": "d" }, "y": { "direction": "in", "type": "d" } }, "CursorButton": { "key": { "direction": "in", "type": "s" }, "hold": { "direction": "in", "type": "b" }, "release": { "direction": "in", "type": "b" } } },
     },
    PLAYER_IFACE: {
        "methods": { "Backward": {}, "Forward": {}, "Play": {}, "Pause": {}, "PlayPause": {}, "Shift": {}, "Unshift": {}, "Loop": {}, "Shuffle": {}, "VolumeDown": {}, "VolumeUp": {}, "Next": {}, "Previous": {} }
}}

PT_ID = "org.freedesktop.impl.portal"
PORTAL_DBUS = {
    f"{PT_ID}.Access": {
        "methods": {
            "AccessDialog": { "handle": { "direction": "in", "type": "o" }, "app_id": { "direction": "in", "type": "s" }, "parent_window": { "direction": "in", "type": "s" }, "title": { "direction": "in", "type": "s" }, "subtitle": { "direction": "in", "type": "s" }, "body": { "direction": "in", "type": "s" }, "options": { "direction": "in", "type": "a{sv}" }, "response": { "direction": "out", "type": "u" }, "results": { "direction": "out", "type": "a{sv}" } }
        }
    },
    f"{PT_ID}.AppChooser": {
        "methods": {
          "ChooseApplication": { "handle": { "direction": "in", "type": "o" }, "app_id": { "direction": "in", "type": "s" }, "parent_window": { "direction": "in", "type": "s" }, "choices": { "direction": "in", "type": "as" }, "options": { "direction": "in", "type": "a{sv}" }, "response": { "direction": "out", "type": "u" }, "results": { "direction": "out", "type": "a{sv}" } , },
          "UpdateChoices": { "handle": { "direction": "in", "type": "o" }, "choices": { "direction": "in", "type": "as" }, },
        }
     },
    f"{PT_ID}.FileChooser": {
        "methods": {
          "OpenFile": { "handle": { "direction": "in", "type": "o" }, "app_id": { "direction": "in", "type": "s" }, "parent_window": { "direction": "in", "type": "s" }, "title": { "direction": "in", "type": "s" }, "options": { "direction": "in", "type": "a{sv}" }, "response": { "direction": "out", "type": "u" }, "results": { "direction": "out", "type": "a{sv}" }, },
          "SaveFile": { "handle": { "direction": "in", "type": "o" }, "app_id": { "direction": "in", "type": "s" }, "parent_window": { "direction": "in", "type": "s" }, "title": { "direction": "in", "type": "s" }, "options": { "direction": "in", "type": "a{sv}" }, "response": { "direction": "out", "type": "u" }, "results": { "direction": "out", "type": "a{sv}" }, },
          "SaveFiles": { "handle": { "direction": "in", "type": "o" }, "app_id": { "direction": "in", "type": "s" }, "parent_window": { "direction": "in", "type": "s" }, "title": { "direction": "in", "type": "s" }, "options": { "direction": "in", "type": "a{sv}" }, "response": { "direction": "out", "type": "u" }, "results": { "direction": "out", "type": "a{sv}" }, }
        }
     },
    f"{PT_ID}.Notification": {
        "methods": {
          "AddNotification": { "app_id": { "direction": "in", "type": "s" }, "id": { "direction": "in", "type": "s" }, "notification": { "direction": "in", "type": "a{sv}" }, },
          "RemoveNotification": { "app_id": { "direction": "in", "type": "s" }, "id": { "direction": "in", "type": "s" }, },
        },
        "signals": { "ActionInvoked": { "app_id": "s", "id": "s", "action": "s", "parameter": "av" } },
        "properties": {
            "version": { "type": "u", "access": "read" },
            "SupportedOptions": { "type": "a{sv}", "access": "read" },
        }
     },
    f"{PT_ID}.ScreenCast": {
        "methods": {
          "CreateSession": { "handle": { "direction": "in", "type": "o" }, "session_handle": { "direction": "in", "type": "o" }, "app_id": { "direction": "in", "type": "s" }, "options": { "direction": "in", "type": "a{sv}" }, "response": { "direction": "out", "type": "u" }, "results": { "direction": "out", "type": "a{sv}" } , },
          "SelectSources": { "handle": { "direction": "in", "type": "o" }, "session_handle": { "direction": "in", "type": "o" }, "app_id": { "direction": "in", "type": "s" }, "options": { "direction": "in", "type": "a{sv}" }, "response": { "direction": "out", "type": "u" }, "results": { "direction": "out", "type": "a{sv}" } , },
          "Start": { "handle": { "direction": "in", "type": "o" }, "session_handle": { "direction": "in", "type": "o" }, "app_id": { "direction": "in", "type": "s" }, "parent_window": { "direction": "in", "type": "s" }, "options": { "direction": "in", "type": "a{sv}" }, "response": { "direction": "out", "type": "u" }, "results": { "direction": "out", "type": "a{sv}" } , },
        },
        "properties": {
            "version": { "type": "u", "access": "read" },
            "AvailableSourceTypes": { "type": "u", "access": "read" },
            "AvailableCursorModes": { "type": "u", "access": "read" },
        }
    },
    f"{PT_ID}.Screenshot": {
        "methods": {
          "Screenshot": { "handle": { "direction": "in", "type": "o" }, "app_id": { "direction": "in", "type": "s" }, "parent_window": { "direction": "in", "type": "s" }, "options": { "direction": "in", "type": "a{sv}" }, "response": { "direction": "out", "type": "u" }, "results": { "direction": "out", "type": "a{sv}" } , },
          "PickColor": { "handle": { "direction": "in", "type": "o" }, "app_id": { "direction": "in", "type": "s" }, "parent_window": { "direction": "in", "type": "s" }, "options": { "direction": "in", "type": "a{sv}" }, "response": { "direction": "out", "type": "u" }, "results": { "direction": "out", "type": "a{sv}" } , },
        },
        "properties": {
            "version": { "type": "u", "access": "read" },
            "AvailableTargets": { "type": "u", "access": "read" },
        }
     },
    f"{PT_ID}.Settings": {
        "methods": {
          "Read": { "namespace": { "direction": "in", "type": "s" }, "key": { "direction": "in", "type": "s" }, "value": { "direction": "out", "type": "v" } },
          "ReadAll": { "namespaces": { "direction": "in", "type": "as" }, "value": { "direction": "out", "type": "a{sa{sv}}" } },
        },
        "signals": { "SettingChanged": { "namespace": "s", "key": "s", "value": "v" } },
        "properties": {
            "version": { "type": "u", "access": "read" },
        }
     },
    f"{PT_ID}.Wallpaper": {
        "methods": {
          "SetWallpaperURI": { "handle": { "direction": "in", "type": "o" }, "app_id": { "direction": "in", "type": "s" }, "parent_window": { "direction": "in", "type": "s" }, "uri": { "direction": "in", "type": "s" }, "options": { "direction": "in", "type": "a{sv}" }, "response": { "direction": "out", "type": "u" }, },
}}}

NF_ID = "org.freedesktop.Notifications"
NOTIFICATION_DBUS = {
    NF_ID: {
        "methods": { "GetCapabilities": { "capabilities": { "direction": "out", "type": "as" } }, "Notify": { "app_name": { "direction": "in", "type": "s" }, "replaces_id": { "direction": "in", "type": "u" }, "app_icon": { "direction": "in", "type": "s" }, "summary": { "direction": "in", "type": "s" }, "body": { "direction": "in", "type": "s" }, "actions": { "direction": "in", "type": "as" }, "hints": { "direction": "in", "type": "a{sv}" }, "expire_timeout": { "direction": "in", "type": "i" }, "id": { "direction": "out", "type": "u" },}, "CloseNotification": { "id": { "direction": "in", "type": "u" }, }, "GetServerInformation": { "name": { "direction": "out", "type": "s" }, "vendor": { "direction": "out", "type": "s" }, "version": { "direction": "out", "type": "s" }, "spec_version": { "direction": "out", "type": "s" },},  },
        "signals": { "NotificationClosed": { "id": "u", "reason": "u" }, "ActionInvoked": { "id": "u", "action_key": "s" }, "ActivationToken": { "id": "u", "activation_token": "s" } },
    },
}

AUTHENTICATION_DBUS = {
    "org.freedesktop.PolicyKit1.AuthenticationAgent": {
        "methods": {
          "BeginAuthentication": { "action_id": { "direction": "in", "type": "s" }, "message": { "direction": "in", "type": "s" }, "icon_name": { "direction": "in", "type": "s" }, "details": { "direction": "in", "type": "a{ss}" }, "cookie": { "direction": "in", "type": "s" }, "identities": { "direction": "in", "type": "a(sa{sv})" } },
          "CancelAuthentication": { "cookie": { "direction": "in", "type": "s" }, },
        },}}

snapshot = Gtk.Snapshot()
rec = Graphene.Rect()
Graphene.Rect.init(rec, 0, 0, 1, 1)
snapshot.append_color(RGBA("#00000000"), rec)
EMPTY_PAINTABLE = snapshot.to_paintable()

def main():
    if Data.setting("Portals", True):
        Settings()
        DBUS(PORTAL_DBUS, f"{PT_ID}.desktop.Shell", "/org/freedesktop/portal/desktop", call)
        if not FLATPAK_ID:
            try:
                Install.do_desktop(INFO)
                default_browser = GLib.spawn_command_line_sync("xdg-settings get default-web-browser")[1].decode().strip()
                d = f"{INFO['ID']}.desktop"
                if default_browser != d: GLib.spawn_command_line_sync(f"/usr/bin/xdg-settings set default-web-browser {d}")
            except: pass
    global SESSION, AUTHENTICATION_AGENT
    AUTHENTICATION_AGENT = False
    try:
        SESSION = Gio.bus_get_sync(Gio.BusType.SESSION)
    except:
        SESSION = False
    if Data.setting("Polkit Agent", True):
        try:
            AUTHENTICATION_AGENT = DBUS(AUTHENTICATION_DBUS, None, "/org/freedesktop/PolicyKit1/AuthenticationAgent", call, bus_type=Gio.BusType.SYSTEM)
            Gio.DBusProxy.new_sync(AUTHENTICATION_AGENT.bus, Gio.DBusProxyFlags.NONE, None, "org.freedesktop.PolicyKit1", "/org/freedesktop/PolicyKit1/Authority", "org.freedesktop.PolicyKit1.Authority", None).call_sync("RegisterAuthenticationAgent", GLib.Variant("((sa{sv})ss)", (("unix-session", {"session-id": GLib.Variant("s", GLib.getenv("XDG_SESSION_ID"))}), GLib.get_language_names()[0], AUTHENTICATION_AGENT.register)), Gio.DBusCallFlags.ALLOW_INTERACTIVE_AUTHORIZATION, GLib.MAXINT, None)
        except Exception as e:
            AUTHENTICATION_AGENT = False
            print(e)
    if Data.setting("Shell DBUS", True): DBUS(SHELL_DBUS, App.default.get_application_id(), DBUS.path(App.default.get_application_id()), call)
    if GLib.getenv("NIRI_SOCKET"): Niri()
    if GLib.getenv("WAYFIRE_SOCKET"): Wayfire()
    if Data.setting("Wayland Client", True): Wayland()
    if Data.setting("Player Agent", True) and SESSION: Player()
    if Data.setting("Notifications Agent", True): Notifications()
    if Data.setting("Apps", True): Apps()
    if GLib.getenv("DUALSHOCK") == "4": Controllers()
    App.default.main(css=APP_CSS)

if __name__ == "__main__": main()