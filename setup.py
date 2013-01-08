from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext

setup(
    cmdclass = {'build_ext': build_ext},
    ext_modules = [Extension("cy_sorter", ["sorter.pyx"]),
                  Extension("cy_corner_table", ["corner_table.pyx"]),
                  Extension("cluster_loader", ["cluster_loader.pyx"])]
)
