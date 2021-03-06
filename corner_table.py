#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import itertools
import sys

class CornerTable(object):
    def __init__(self):
        self.V = []
        self.O = []
        self.C = {}

    def create_corner_from_vertex_face(self, vertices, faces, vertices_faces):
        self.vertices = vertices
        self._compute_V(faces)
        self._compute_O(vertices, faces, vertices_faces)

    def _compute_V(self, faces):
        for face in sorted(faces):
            for vertex in faces[face]:
                self.V.append(vertex)
                self.C[vertex] = len(self.V) - 1

            sys.stdout.write('\rComputing V: %.2f' % ((100.0*face)/(len(faces)-1)))
            sys.stdout.flush()
        print 

    def _compute_O(self, vertices, faces, vertices_faces):
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

            for n, c in enumerate(self.iterate_triangle_corner(oface)):
                if self.V[c] not in (self.V[cn], self.V[cp]):
                    self.O[c_id] = c
                    break

            sys.stdout.write('\rComputing O: %.2f' % ((100.0*c_id)/(len(self.V)-1)))
            sys.stdout.flush()
        print 

    def get_vertex(self, c_id):
        return self.vertices[self.V[c_id]]

    def get_triangle(self, c_id):
        return c_id / 3

    def get_corner_f(self, t_id):
        return t_id * 3

    def get_corner_v(self, v_id):
        return self.C[v_id]

    def next_corner(self, c_id):
        return 3 * self.get_triangle(c_id) + ((c_id + 1) % 3)

    def previous_corner(self, c_id):
        return self.next_corner(self.next_corner(c_id))

    def iterate_triangle_corner(self, t_id):
        corner = self.get_corner_f(t_id)
        yield corner
        yield self.next_corner(corner)
        yield self.previous_corner(corner)

    def get_oposite_corner(self, c_id):
        return self.O[c_id]

    def get_left_corner(self, c_id):
        return self.get_oposite_corner(self.next_corner(c_id))

    def get_right_corner(self, c_id):
        return self.get_oposite_corner(self.previous_corner(c_id))

    def swing(self, c_id):
        return self.next_corner(self.get_left_corner(c_id))

    def get_faces_connected_to_v(self, v_id):
        c = self.get_corner_v(v_id)
        ti = self.get_triangle(c)
        yield ti
        while 1:
            c = self.swing(c)
            t = self.get_triangle(c)
            if t == ti:
                break
            else:
                yield t

    def get_vertex_degree(self, v_id):
        degree = 1
        for f in self.get_faces_connected_to_v(v_id):
            degree += 1
        return degree
