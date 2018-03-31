from rpython.memory.gc.hook import GcHooks
from pypy.interpreter.baseobjspace import ObjSpace
from pypy.interpreter.gateway import interp2app, unwrap_spec
from pypy.interpreter.executioncontext import AsyncAction

class LowLevelGcHooks(GcHooks):

    def setspace(self, space):
        self.space = space
        self.hooks = space.fromcache(AppLevelHooks)

    def is_gc_minor_enabled(self):
        return self.hooks.gc_minor_enabled

    def on_gc_minor(self, total_memory_used, pinned_objects):
        action = self.hooks.gc_minor
        action.total_memory_used = total_memory_used
        action.pinned_objects = pinned_objects
        action.fire()

    def on_gc_collect_step(self, oldstate, newstate):
        pass

    def on_gc_collect(self, count, arenas_count_before, arenas_count_after,
                      arenas_bytes, rawmalloc_bytes_before,
                      rawmalloc_bytes_after):
        pass


gchooks = LowLevelGcHooks()

class AppLevelHooks(object):

    def __init__(self, space):
        self.space = space
        self.gc_minor_enabled = False
        self.gc_minor = GcMinorHookAction(space)

    def set_hooks(self, space, w_on_gc_minor):
        self.gc_minor_enabled = not space.is_none(w_on_gc_minor)
        self.gc_minor.w_callable = w_on_gc_minor


class GcMinorHookAction(AsyncAction):
    w_callable = None
    total_memory_used = 0
    pinned_objects = 0

    def perform(self, ec, frame):
        self.space.call_function(self.w_callable,
                                 self.space.wrap(self.total_memory_used),
                                 self.space.wrap(self.pinned_objects))




def set_hooks(space, w_on_gc_minor):
    space.fromcache(AppLevelHooks).set_hooks(space, w_on_gc_minor)
