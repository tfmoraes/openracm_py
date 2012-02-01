#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# cython: profile=True

import itertools
import sys

cdef class CornerTable:
    def __init__(self):
        self.V = []
        self.O = []
        self.C = {}
        self.vertices = {}

    cpdef create_corner_from_vertex_face(self, dict vertices, dict faces, dict vertices_faces):
        self.vertices = vertices
        self._compute_V(faces)
        self._compute_O(vertices, faces, vertices_faces)

    cdef void _compute_V(self, dict faces):
        cdef int face
        cdef int i=0
        for face in sorted(faces):
            for vertex in faces[face]:
                self.V.append(vertex)
                self.C[vertex] = i
                i += 1

            sys.stdout.write('\rComputing V: %.2f' % ((100.0*face)/(len(faces)-1)))
            sys.stdout.flush()
        print 

    cdef void _compute_O(self, dict vertices, dict faces, dict vertices_faces):
        cdef int t, c, cn, cp, v0, v1, f0, f1, oface, c_id, n, i
        for i in xrange(len(self.V)):
            self.O.append(-1)

        for c_id in xrange(len(self.V)):
            t = self.get_triangle(c_id)
            cn = self.next_corner(c_id)
            cp = self.previous_corner(c_id)
            v0 = self.V[cn]
            v1 = self.V[cp]

            # Getting the faces which share a vertex
            f = set(vertices_faces[v0]) & set(vertices_faces[v1])
            if len(f) != 2:
                raise("Error")
            f0, f1 = f
            if t == f0:
                oface = f1
            elif t == f1:
                oface = f0
            else:
                raise("Error")

            for c in self.iterate_triangle_corner(oface):
                if self.V[c] not in (self.V[cn], self.V[cp]):
                    self.O[c_id] = c
                    break

            sys.stdout.write('\rComputing O: %.2f' % ((100.0*c_id)/(len(self.V)-1)))
            sys.stdout.flush()
        print 

    cdef int get_vertex(self, int c_id):
        return self.vertices[self.V[c_id]]

    cdef int get_triangle(self, int c_id):
        return c_id / 3

    cdef int get_corner_f(self, int t_id):
        return t_id * 3

    cdef int get_corner_v(self, int v_id):
        return self.C[v_id]

    cdef int next_corner(self, int c_id):
        return 3 * self.get_triangle(c_id) + ((c_id + 1) % 3)

    cdef int previous_corner(self, c_id):
        return self.next_corner(self.next_corner(c_id))

    cpdef tuple iterate_triangle_corner(self, int t_id):
        cdef int corner
        corner = self.get_corner_f(t_id)
        return corner, self.next_corner(corner), self.previous_corner(corner)

    cdef int get_oposite_corner(self, int c_id):
        return self.O[c_id]

    cdef int get_left_corner(self, int c_id):
        return self.get_oposite_corner(self.next_corner(c_id))

    cdef int get_right_corner(self, int c_id):
        return self.get_oposite_corner(self.previous_corner(c_id))

    cdef int swing(self, int c_id):
        return self.next_corner(self.get_left_corner(c_id))

    cpdef list get_faces_connected_to_v(self, Py_ssize_t v_id):
        cdef Py_ssize_t c, ti, t
        c = self.get_corner_v(v_id)
        ti = self.get_triangle(c)
        output = [ti, ]
        while 1:
            c = self.swing(c)
            t = self.get_triangle(c)
            if t == ti:
                break
            else:
                output.append(t)
        return output

    cpdef int get_vertex_degree(self, v_id):
        cdef int degree, f
        degree = 1
        for f in self.get_faces_connected_to_v(v_id):
            degree += 1
        return degree
