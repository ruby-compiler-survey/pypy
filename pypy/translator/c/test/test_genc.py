import autopath, sys, os, py
from pypy.rpython.lltype import *
from pypy.rpython.rtyper import RPythonTyper
from pypy.translator.translator import Translator
from pypy.translator.c.database import LowLevelDatabase
from pypy.translator.c.genc import gen_source
from pypy.objspace.flow.model import Constant, Variable, SpaceOperation
from pypy.objspace.flow.model import Block, Link, FunctionGraph
from pypy.tool.udir import udir
from pypy.translator.tool.buildpyxmodule import make_module_from_c
from pypy.translator.gensupp import uniquemodulename

# XXX this tries to make compiling faster for full-scale testing
from pypy.translator.tool import buildpyxmodule
buildpyxmodule.enable_fast_compilation()


def compile_db(db):
    modulename = uniquemodulename('testing')
    targetdir = udir.join(modulename).ensure(dir=1)
    gen_source(db, modulename, str(targetdir), defines={'COUNT_OP_MALLOCS': 1})
    m = make_module_from_c(targetdir.join(modulename+'.c'),
                           include_dirs = [os.path.dirname(autopath.this_dir)])
    return m


def test_untyped_func():
    def f(x):
        return x+1
    t = Translator(f)
    graph = t.getflowgraph()

    F = FuncType([Ptr(PyObject)], Ptr(PyObject))
    S = GcStruct('testing', ('fptr', Ptr(F)))
    f = functionptr(F, "f", graph=graph)
    s = malloc(S)
    s.fptr = f
    db = LowLevelDatabase()
    db.get(s)
    db.complete()
    compile_db(db)


def test_func_as_pyobject():
    def f(x):
        return x*2
    t = Translator(f)
    a = t.annotate([int])
    rtyper = RPythonTyper(t.annotator)
    rtyper.specialize()

    db = LowLevelDatabase(rtyper)
    entrypoint = db.get(pyobjectptr(f))
    db.complete()
    module = compile_db(db)

    f1 = getattr(module, entrypoint)
    assert f1(5) == 10
    assert f1(x=5) == 10
    assert f1(-123) == -246
    py.test.raises(TypeError, f1, "world")  # check that it's really typed
    py.test.raises(TypeError, f1)
    py.test.raises(TypeError, f1, 2, 3)
    py.test.raises(TypeError, f1, 2, x=2)
    #py.test.raises(TypeError, f1, 2, y=2)   XXX missing a check at the moment
    assert module.malloc_counters() == (0, 0)


def test_rlist():
    def f(x):
        l = [x]
        l.append(x+1)
        return l[0] * l[-1]
    t = Translator(f)
    a = t.annotate([int])
    rtyper = RPythonTyper(t.annotator)
    rtyper.specialize()

    db = LowLevelDatabase(rtyper)
    entrypoint = db.get(pyobjectptr(f))
    db.complete()
    #t.view()
    module = compile_db(db)

    f1 = getattr(module, entrypoint)
    assert f1(5) == 30
    assert f1(x=5) == 30
    mallocs, frees = module.malloc_counters()
    assert mallocs == frees


def test_rptr():
    S = GcStruct('testing', ('x', Signed), ('y', Signed))
    def f(i):
        if i < 0:
            p = nullptr(S)
        else:
            p = malloc(S)
            p.x = i*2
        if i > 0:
            return p.x
        else:
            return -42
    t = Translator(f)
    a = t.annotate([int])
    rtyper = RPythonTyper(t.annotator)
    rtyper.specialize()

    db = LowLevelDatabase(rtyper)
    entrypoint = db.get(pyobjectptr(f))
    db.complete()
    #t.view()
    module = compile_db(db)

    f1 = getattr(module, entrypoint)
    assert f1(5) == 10
    assert f1(i=5) == 10
    assert f1(1) == 2
    assert f1(0) == -42
    assert f1(-1) == -42
    assert f1(-5) == -42
    mallocs, frees = module.malloc_counters()
    assert mallocs == frees
