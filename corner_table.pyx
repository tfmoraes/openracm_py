#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# cython: profile=True

import itertools
import sys
import numpy

cdef class CornerTable:
    def __init__(self):
        self.V = []
        self.O = []
        self.C = {}
        self.vertices = {}

    cpdef create_corner_from_vertex_face(self, dict vertices, list faces, dict vertices_faces):
        self.vertices = vertices
        self._compute_V(faces)
        self._compute_O(vertices, faces, vertices_faces)

    cdef int is_clockwise(self, list v0, list v1, list v2):
        # Based on this link http://mathforum.org/library/drmath/view/55343.html
        u = v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2]
        v = v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2]
        vn = numpy.cross(u, v)

        d = numpy.array([[v0[0], v0[1], v0[2], 1],
                         [v1[0], v1[1], v1[2], 1],
                         [v2[0], v2[1], v2[2], 1],
                         [vn[0], vn[1], vn[2], 1]]), 

        return numpy.linalg.det(d) > 0

    cdef void _compute_V(self, list faces):
        cdef list face
        cdef int i=0
        cdef nface=0
        for face in faces:
            if self.is_clockwise(self.vertices[face[0]],
                                 self.vertices[face[1]],
                                 self.vertices[face[2]]):
                vertices = face[0], face[1], face[2]
            else:
                vertices = face[2], face[1], face[0]
            for vertex in vertices:
                self.V.append(vertex)
                self.C[vertex] = i
                i += 1
            sys.stdout.write('\rComputing V: %.2f' % ((100.0*nface)/(len(faces)-1)))
            sys.stdout.flush()
            nface += 1

    cdef void _compute_O(self, dict vertices, list faces, dict vertices_faces):
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
                raise(Exception("Error"))
            f0, f1 = f
            if t == f0:
                oface = f1
            elif t == f1:
                oface = f0
            else:
                raise(Exception("Error"))

            for c in self.iterate_triangle_corner(oface):
                if self.V[c] not in (self.V[cn], self.V[cp]):
                    self.O[c_id] = c
                    break

            sys.stdout.write('\rComputing O: %.2f' % ((100.0*c_id)/(len(self.V)-1)))
            sys.stdout.flush()
        print 

    cpdef list get_vertex_position(self, int c_id):
        return self.vertices[self.V[c_id]]

    cpdef int get_vertex(self, int c_id):
        return self.V[c_id]

    cpdef int get_triangle(self, int c_id):
        return c_id / 3

    cpdef int get_corner_f(self, int t_id):
        return t_id * 3

    cpdef int get_corner_v(self, int v_id):
        return self.C[v_id]

    cpdef int next_corner(self, int c_id):
        return 3 * self.get_triangle(c_id) + ((c_id + 1) % 3)

    cpdef int previous_corner(self, c_id):
        return self.next_corner(self.next_corner(c_id))

    cpdef tuple iterate_triangle_corner(self, int t_id):
        cdef int corner
        corner = self.get_corner_f(t_id)
        return corner, self.next_corner(corner), self.previous_corner(corner)

    cpdef int get_oposite_corner(self, int c_id):
        return self.O[c_id]

    cpdef int get_left_corner(self, int c_id):
        return self.get_oposite_corner(self.next_corner(c_id))

    cpdef int get_right_corner(self, int c_id):
        return self.get_oposite_corner(self.previous_corner(c_id))

    cpdef int swing(self, int c_id):
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

    cpdef int get_triangle_by_edge(self, int v0, int v1):
        cdef int c0, c1
        c0 = self.get_corner_v(v0)
        c1 = self.get_corner_v(v1)

        while v1 not in (self.get_vertex(self.next_corner(c0)),
                         self.get_vertex(self.previous_corner(c0))):
            c0 = self.swing(c0)

        return self.get_triangle(c0)
