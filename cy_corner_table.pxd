import itertools
import sys

cdef class CornerTable:
    cdef public list V
    cdef public list O 
    cdef public dict C
    cdef public dict vertices

    cpdef create_corner_from_vertex_face(self, dict vertices, dict faces, dict vertices_faces)

    cdef void _compute_V(self, dict faces)

    cdef void _compute_O(self, dict vertices, dict faces, dict vertices_faces)

    cdef int get_vertex(self, int c_id)

    cdef int get_triangle(self, int c_id)

    cdef int get_corner_f(self, int t_id)

    cdef int get_corner_v(self, int v_id)

    cdef int next_corner(self, int c_id)

    cdef int previous_corner(self, c_id)

    cpdef tuple iterate_triangle_corner(self, int t_id)

    cdef int get_oposite_corner(self, int c_id)

    cdef int get_left_corner(self, int c_id)

    cdef int get_right_corner(self, int c_id)

    cdef int swing(self, int c_id)

    cpdef list get_faces_connected_to_v(self, Py_ssize_t v_id)

    cpdef int get_vertex_degree(self, v_id)
