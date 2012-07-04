import itertools
import sys

cdef class CornerTable:
    cdef public list V
    cdef public list O 
    cdef public dict C
    cdef public dict vertices

    cpdef create_corner_from_vertex_face(self, dict vertices, list faces, dict vertices_faces)

    cdef int is_clockwise(self, list v0, list v1, list v2)

    cdef void _compute_V(self, list faces)

    cdef void _compute_O(self, dict vertices, list faces, dict vertices_faces)

    cpdef list get_vertex_position(self, int c_id)

    cpdef int get_vertex(self, int c_id)

    cpdef int get_triangle(self, int c_id)

    cpdef int get_corner_f(self, int t_id)

    cpdef int get_corner_v(self, int v_id)

    cpdef int next_corner(self, int c_id)

    cpdef int previous_corner(self, c_id)

    cpdef tuple iterate_triangle_corner(self, int t_id)

    cpdef int get_oposite_corner(self, int c_id)

    cpdef int get_left_corner(self, int c_id)

    cpdef int get_right_corner(self, int c_id)

    cpdef int swing(self, int c_id)

    cpdef list get_faces_connected_to_v(self, Py_ssize_t v_id)

    cpdef int get_vertex_degree(self, v_id)
