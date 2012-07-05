#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import math
import random
import sys

import ply_reader
import cy_corner_table
import ply_writer
import colour_clusters

class EdgeRinge(object):
    def __init__(self, ct):
        self.ct = ct
        self.edges = {}

    def add_edge(self, edge):
        c0, c1 = edge

        nc = self.ct.next_corner(c1)
        pc = self.ct.previous_corner(c1)

        v0 = self.ct.get_vertex(c0)
        v1 = self.ct.get_vertex(c1)
        nv = self.ct.get_vertex(nc)
        pv = self.ct.get_vertex(pc)
        v2 = nv

        self.edges[v0] = v1
        self.edges[v1] = v2


class LacedRing(object):
    """
    This class is a implementation of the Laced Ring from the paper
    "LR: Compact Connectivity Representation for Triangle Meshes".
    """
    def __init__(self):
        self.vertices = []
        #self.faces = faces
        #self.edge_ring = edge_ring
        #self.m_t = m_t
        self.ring = []
        self.L = {}
        self.R = {}
        self.O = {}
        self.V = []
        self.C = {}
        self.VOs = {}
        self.number_triangles = 0

    def reorder_vertices(self, ct, edge_ring):
        v0 = edge_ring.edges.keys()[0]
        v1 = edge_ring.edges[v0]
        vs = v0
        i = 0
        map_ct_lr = {}
        map_lr_ct = {}
        while 1:
            self.vertices.append(ct.vertices[v0])
            map_ct_lr[v0] = i
            map_lr_ct[i] = v0

            i += 1
            v0 = v1
            v1 = edge_ring.edges[v0]

            if v0 == vs:
                #self.ring.append(v0)
                break

        self.mr = i
        j = 0
        for v in xrange(len(ct.vertices)):
            if v not in map_ct_lr:
                self.vertices.append(ct.vertices[v])
                map_ct_lr[v] = i
                map_lr_ct[i] = v
                i += 1
                j += 1
            
        return map_ct_lr, map_lr_ct


    def make_lr(self, ct, edge_ring, m_t):
        map_ct_lr, map_lr_ct = self.reorder_vertices(ct, edge_ring)

        self.edge_ring = edge_ring
        self.ct = ct
        
        for v0 in xrange(self.mr):
            v1 = self.next_vertex_ring(v0)

            c0 = ct.get_corner_v(map_lr_ct[v0])
            c1 = ct.get_corner_v(map_lr_ct[v1])

            while map_lr_ct[v1] not in (ct.get_vertex(ct.next_corner(c0)), ct.get_vertex(ct.previous_corner(c0))):
                c0 = ct.swing(c0)

            if ct.get_vertex(ct.next_corner(c0)) == map_lr_ct[v1]:
                r = ct.previous_corner (c0)
                l = ct.get_oposite_corner(r)
            else:
                l = ct.next_corner(c0)
                r = ct.get_oposite_corner(l)

            vl = map_ct_lr[ct.get_vertex(l)]
            vr = map_ct_lr[ct.get_vertex(r)]

            self.L[v0] = [vl, 1, 0]
            self.R[v0] = [vr, 1, 0]
            self.number_triangles += 2

        for v0 in xrange(self.mr):
            if self.L[v0][0] == self.next_vertex_ring(self.next_vertex_ring(v0)) \
               or self.L[self.previous_vertex_ring(v0)][0] == self.next_vertex_ring(v0):
                # T2 triangle
                self.L[v0][1] = 2

            if self.R[v0][0] == self.next_vertex_ring(self.next_vertex_ring(v0)) \
               or self.R[self.previous_vertex_ring(v0)][0] == self.next_vertex_ring(v0):
                # T2 triangle
                self.R[v0][1] = 2


        self._handle_t0(ct, edge_ring, map_ct_lr, map_lr_ct)
        #print "OOO", edge_ring[0], ct.get_oposite_corner(edge_ring[ len(edge_ring) - 1 ])

    def _handle_t0(self, ct, edge_ring, map_ct_lr, map_lr_ct):
        t0_triangles = set()
        for t_id in xrange(len(ct.V) / 3):
            c, nc, pc = ct.iterate_triangle_corner(t_id)
            v, nv, pv = [ct.get_vertex(i) for i in (c, nc, pc)]
            if not (edge_ring.edges.get(v, -1) == nv \
               or edge_ring.edges.get(nv, -1) == pv \
               or edge_ring.edges.get(pv, -1) == v \
               or edge_ring.edges.get(nv, -1) == v \
               or edge_ring.edges.get(pv, -1) == nv \
               or edge_ring.edges.get(v, -1) == pv \
               ):
                t0_triangles.add(t_id)

        t_c_id = 8 * self.mr
        while t0_triangles:
            t_id = t0_triangles.pop()
            c, nc, pc = ct.iterate_triangle_corner(t_id)
            v, nv, pv = [ct.get_vertex(i) for i in (c, nc, pc)]

            self.V.append(map_ct_lr[v])
            self.V.append(map_ct_lr[nv])
            self.V.append(map_ct_lr[pv])
            self.number_triangles += 1

            self.C[map_ct_lr[v]] = t_c_id 
            self.C[map_ct_lr[nv]] = t_c_id + 1
            self.C[map_ct_lr[pv]] = t_c_id + 2

            t_c_id += 4

        #for c in (8 * self.mr, c_id, 3):
            #v0 = self.V[c]
            #v1 = self.V[c + 1]
            #v2 = self.V[c + 2]

        ti = set()
        for c_id in xrange(8*self.mr, t_c_id, 4):
            cn = c_id + 1
            cp = c_id + 2
            v = self.vertex(c_id)
            vn = self.vertex(cn)
            vp = self.vertex(cp)

            s = set((v, vn, vp))
            for cw, vi in ((c_id, v), (cn, vn), (cp, vp)):
                cs = s - set((vi,))
                for t in xrange(self.number_triangles):
                    c0 = self.corner_triangle(t)
                    c1 = self.next_corner(c0)
                    c2 = self.next_corner(c1)

                    v0 = self.vertex(c0)
                    v1 = self.vertex(c1)
                    v2 = self.vertex(c2)

                    diff = set((v0, v1, v2)) - cs

                    if len(diff) == 1:
                        vo = diff.pop()
                        if vo == v0 and vo != vi:
                            o = c0
                        elif vo == v1 and vo != vi:
                            o = c1
                        elif vo == v2 and vo != vi:
                            o = c2

                        self.O[cw] = o
                        break


                t = self.triangle(o)
                v = int(math.floor(o / 8.0))
                if t % 2:
                    self.R[v][2] = 1
                    if o % 8 == 4:
                        self.VOs[t] = [cw, -1]
                    else:
                        self.VOs[t] = [-1, cw]
                else:
                    self.L[v][2] = 1
                    if o % 8 == 0:
                        self.VOs[t] = [cw, -1]
                    else:
                        self.VOs[t] = [-1, cw]

        for t in self.VOs:
            c = self.corner_triangle(t)
            v = int(math.floor(c / 8.0))
            if t % 2:
                if self.VOs[t][0] == -1:
                    self.VOs[t][0] = self.oposite(v*8)[0]
                else:
                    self.VOs[t][1] = self.oposite(v*8 + 2)[0]
            else:
                if self.VOs[t][0] == -1:
                    self.VOs[t][0] = self.oposite(v*8 + 4)[0]
                else:
                    self.VOs[t][1] = self.oposite(v*8 + 6)[0]
                
        for t in xrange(self.number_triangles):
            c0 = self.corner_triangle(t)
            c1 = self.next_corner(c0)
            c2 = self.next_corner(c1)

            for c in (c0, c1, c2):
                o = self.oposite(c)
                if o[0] != -1:
                    co = self.oposite(o[0])
                    if co[0] == -1:
                        print "No tratado", (c, self.vertex(c), self.triangle(c), self.is_t2_triangle(self.triangle(c))), (o, self.vertex(o[0]), self.triangle(o[0]), self.is_t2_triangle(self.triangle(o[0]))), co
                    
                    elif c != co[0]:
                        if self.to_canonical(c) == co[0]:
                            pass
                        elif c == self.to_canonical(co[0]):
                            pass
                        elif self.to_canonical(c) == self.to_canonical(co[0]):
                            pass
                        else:
                            print "Erro", "%06d" % c, o, co, self.is_t2_triangle(t), self.is_t2_triangle(self.triangle(co[0])), self.to_canonical(c), self.to_canonical(co[0]), self.oposite(co[0])
                    else:
                        pass
                else:
                    print "No tratado", "%06d" % c, o, self.is_t2_triangle(t), self.triangle(c)

    def vertex(self, c_id):
        """
        Return the vertex `v' related to the given corner `c_id'.
        """
        if c_id >= 8 * self.mr:
            i = int(c_id - math.floor(c_id / 4) - 6 * self.mr)
            return self.V[i]
        else:
            v = int(math.floor(c_id / 8.0))
            if c_id % 8 in (0, 6):
                return v
            elif c_id % 8 in (2, 4):
                return self.next_vertex_ring(v)
            elif c_id % 8 == 1:
                return self.L[v][0]
            elif c_id % 8 == 5:
                return self.R[v][0]
            else:
                raise(Exception("Error"))
                # TODO: else returns an exception.

    def oposite(self, c_id):
        """
        Returns the oposite corner from the given corner.
        """
        # TODO: To implement the other cases of oposite operator, when it's not
        # neither single vertex, nor L nor R vertex.
        v = int(math.floor(c_id / 8.0))
        
        ########### Mapping redundant triangle to canonical one ###############
        t = self.triangle(c_id)
        if self.is_t2_triangle(t):
            if self.L[v][0] == self.next_vertex_ring(self.next_vertex_ring(v)) and c_id % 8 in (0, 1, 2):
                if c_id % 8 == 0:
                    r = 1
                elif c_id % 8 == 1:
                    r = 2
                elif c_id % 8 == 2:
                    r = 0

                c_id = 8*self.next_vertex_ring(v) + r
                v = int(math.floor(c_id / 8.0))
            
            elif self.R[v][0] == self.next_vertex_ring(self.next_vertex_ring(v)) and c_id % 8 in (4, 5, 6):
                if c_id % 8 == 4:
                    r = 6
                elif c_id % 8 == 5:
                    r = 4
                elif c_id % 8 == 6:
                    r = 5

                c_id = 8*self.next_vertex_ring(v) + r
                v = int(math.floor(c_id / 8.0))
            t = self.triangle(c_id)

        #################################################


        ## This corner if related to a T0 triangle, so its oposity is in O
        ## array.
        if c_id >= 8 * self.mr:
            #i = int(c_id - math.floor(c_id / 4.0) - 6 * self.mr)
            o = self.O[c_id], 0
            #return -1, -1

        # the triangle t related to the given corner is a expensive triangle,
        # so it's necessary to lookup VOs structure to find c.o.
        
        elif c_id % 8 == 0 and self.is_expensive_triangle(t):
            o = self.VOs[t][0], 40
        elif c_id % 8 == 2 and self.is_expensive_triangle(t):           
            o = self.VOs[t][1], 41
        elif c_id % 8 == 4 and self.is_expensive_triangle(t):           
            o = self.VOs[t][0], 42
        elif c_id % 8 == 6 and self.is_expensive_triangle(t):           
            o = self.VOs[t][1], 43

        #                  * v.1
        #                 - -            
        #                -   -           
        #               -     -          
        #              -       -         
        #             -         -     
        #          v -           - v.n
        #   ========o=============o=================>
        #            -           - 
        #             -         -  
        #              -       -      
        #               -     -       
        #                -   -        
        #                 - -                       
        #                  o v.5
        #
        elif c_id % 8 == 1:
            o = 8*v + 5, 1

        #                  o v.1
        #                 - -            
        #                -   -           
        #               -     -          
        #              -       -         
        #             -         -     
        #          v -           - v.n
        #   ========o=============o=================>
        #            -           - 
        #             -         -  
        #              -       -      
        #               -     -       
        #                -   -        
        #                 - -                       
        #                  * v.5
        #
        elif c_id % 8 == 5:
            o = 8*v + 1, 2


        #                         v.l                          ^
        #                         o---------------------------o
        #                        - -                   v.n.2 =
        #                       -   -                       =
        #                      -     -                     =
        #                     -       -                   =
        #                    -         -                 = 
        #                   -           -               =
        #                  -             -             =
        #                 -               -           =
        #                -                 -         =
        #               -                   -       =
        #              -                     -     =
        #             -                       -   =
        #            - v.0                     - =
        #    =======*===========================o v.n
        elif self.L[v][0] == self.L[self.next_vertex_ring(v)][0] and c_id % 8 == 0:
            o = 8*self.next_vertex_ring(v) + 2, 3

        #                         v.l                          ^
        #                         o---------------------------* v.n
        #                        - -                     v.2 =
        #                       -   -                       =
        #                      -     -                     =
        #                     -       -                   =
        #                    -         -                 = 
        #                   -           -               =
        #                  -             -             =
        #                 -               -           =
        #                -                 -         =
        #               -                   -       =
        #              -                     -     =
        #             -                       -   =
        #            - v.p.0                   - =
        #    =======o===========================o 
        #          v.p                          v
        #
        elif self.L[v][0] == self.L[self.previous_vertex_ring(v)][0] and c_id % 8 == 2:
            o = 8*self.previous_vertex_ring(v), 4

        #
        #              v.n                        
        #               o=========================o====>
        #              = -                  v.n.4-
        #             =   -                     -
        #            =     -                   -
        #           =       -                 -
        #          =         -               -
        #         =           -             -
        #        =             -           -
        #       =               -         -
        #      =                 -       -
        #     =                   -     -
        #    =                     -   -
        #   = v.6                   - -
        #  *-------------------------o
        #  v                         v.r
        #
        elif self.R[v][0] == self.R[self.next_vertex_ring(v)][0] and c_id % 8 == 6:
            o = 8*self.next_vertex_ring(v) + 4, 7

        #
        #              v                        
        #               o=========================o====>
        #              = -                    v.4-
        #             =   -                     -
        #            =     -                   -
        #           =       -                 -
        #          =         -               -
        #         =           -             -
        #        =             -           -
        #       =               -         -
        #      =                 -       -
        #     =                   -     -
        #    =                     -   -
        #   = v.p.6                 - -
        #  *-------------------------o
        # v.p                       v.r
        #
        elif self.R[v][0] == self.R[self.previous_vertex_ring(v)][0] and c_id % 8 == 4:
            o = 8*self.previous_vertex_ring(v) + 6, 8

        #
        #                 v.l                      v.l.p
        #     <============o=========================o======
        #                 - -                v.l.p.0-
        #                -   -                     -
        #               -     -                   -
        #              -       -                 -
        #             -         -               -
        #            -           -             -
        #           -             -           -
        #          -               -         -
        #         -                 -       -
        #        -                   -     -
        #       -                     -   -
        #      - v.0                   - -
        #   ==*=========================o=================>
        #     v                        v.n
        #
        elif self.L[self.previous_vertex_ring(self.L[v][0])][0] == self.next_vertex_ring(v) and c_id % 8 == 0:
            o = 8*self.previous_vertex_ring(self.L[v][0]), 5

        #
        #                v.l.n                       v.l
        # <===============o===========================o=====================
        #                - - v.l.2                   - -
        #               -   -                       -   -
        #              -     -                     -     -
        #             -       -                   -       -
        #            -         -                 -         -
        #           -           -               -           -
        #          -             -             -             -
        #         -               -           -               -
        #        -                 -         -                 -
        #       -                   -       -                   -
        #      -                     -     -                     -
        #     -                       -   -                       -
        #    -                         - -                     v.2 -
        #  =o===========================o===========================*===>
        #  v.p                          v                           
        #
        elif self.L[self.next_vertex_ring(self.L[v][0])][0] == self.previous_vertex_ring(v) and c_id % 8 == 2:
            o = 8*self.L[v][0] + 2, 6


        #elif self.R[self.previous_vertex_ring(self.L[v][0])][0] == v:
            #print "Manolo!", c_id % 8
            #if c_id % 8 == 2:
                #o = 8*self.L[v][0] + 6, 1024
            #else:
                #o = (-1, -1)

        #elif self.next_vertex_ring(self.R[v][0]) == self.R[self.next_vertex_ring(v)][0]:
            #print "Hello, manolo!"
            #if c_id % 8 == 6:
                #o = 8*self.R[v][0] + 2, 1025
            #else:
                #o = (-1, -1)

        #
        #                 v.r                      v.r.n
        #     =============o=========================o======>
        #                 - -                v.r.n.4-
        #                -   -                     -
        #               -     -                   -
        #              -       -                 -
        #             -         -               -
        #            -           -             -
        #           -             -           -
        #          -               -         -
        #         -                 -       -
        #        -                   -     -
        #       -                     -   -
        #      - v.4                   - -
        #  <==*=========================o==================
        #     v                        v.p
        #
        elif self.R[self.next_vertex_ring(self.R[v][0])][0] == self.previous_vertex_ring(v) and c_id % 8 == 4:
            o = 8*self.next_vertex_ring(self.R[v][0]) + 4, 9

        #
        #                v.r.p                       v.r
        # ================o===========================o=====================>
        #                - - v.r.p.6                 - -
        #               -   -                       -   -
        #              -     -                     -     -
        #             -       -                   -       -
        #            -         -                 -         -
        #           -           -               -           -
        #          -             -             -             -
        #         -               -           -               -
        #        -                 -         -                 -
        #       -                   -       -                   -
        #      -                     -     -                     -
        #     -                       -   -                       -
        #    -                         - -                     v.6 -
        # <=o===========================o===========================o===
        #                              v.n                           v
        #
        elif self.R[self.previous_vertex_ring(self.R[v][0])][0] == self.next_vertex_ring(v) and c_id % 8 == 6:
            o = 8*self.previous_vertex_ring(self.R[v][0]) + 6, 10

        elif self.L[self.previous_vertex_ring(v)][0] == self.next_vertex_ring(v):
            if c_id % 8 ==2:
                o = 8*self.previous_vertex_ring(v) + 5, 11
            elif c_id % 8 ==1:
                o = 8*v + 5, 12
            else:
                return -1, -1

        elif self.R[self.previous_vertex_ring(v)][0] == self.next_vertex_ring(v):
            if c_id % 8 == 4:
                o = 8*self.previous_vertex_ring(v) + 1, 13
            elif c_id % 8 == 5:
                o = 8*v+ 1, 14
            else:
                o = 8 * self.previous_vertex_ring(self.R[v][0]), 18

        else:
            #if self.L[self.previous_vertex_ring(v)][0] == self.next_vertex_ring(v):
                #print "Redundante L", c_id % 8, self.is_t2_triangle(t)
            #elif self.R[self.previous_vertex_ring(v)][0] == self.next_vertex_ring(v):
                #print "Redundante R", c_id % 8, self.is_t2_triangle(t)
            #else:
                #print "Sei la", c_id % 8, self.is_t2_triangle(t)

            return -1, -1

        #t = self.triangle(o[0])
        #ov = int(math.floor(o[0] / 8.0))
        #if self.is_t2_triangle(t) and \
           #(self.L[ov][0] == self.next_vertex_ring(self.next_vertex_ring(ov)) or\
           #self.R[ov][0] == self.next_vertex_ring(self.next_vertex_ring(ov))):
            #if o[0] % 8 == 0:
                #r = 1
            #elif o[0] % 8 == 1:
                #r = 2
            #elif o[0] % 8 == 2:
                #r = 0
            
            #elif o[0] % 8 == 4:
                #r = 6
            #elif o[0] % 8 == 5:
                #r = 4
            #elif o[0] % 8 == 6:
                #r = 5

            #o = 8*self.next_vertex_ring(ov) + r, 30, o[1]

        return o


    def corner_vertex(self, v_id):
        """
        Returns a corner related to the given vertex `v_id'.
        """
        if v_id >= self.mr:
            return self.C[v - self.mr]
        elif self.L[v_id] == self.next_vertex_ring(self.next_vertex_ring(v_id)):
            return 8 * self.next_vertex_ring(v_id) + 1
        elif self.R[v_id] == self.next_vertex_ring(self.next_vertex_ring(v_id)):
            return 8 * self.next_vertex_ring(v_id) + 1
        else:
            return 8 * v_id

    def triangle(self, c_id):
        """
        Returns the triangle related to the given corner `c_id'.
        """
        return int(math.floor(c_id/4))

    def corner_triangle(self, t_id):
        """
        Returns the first corner from the given triangle `t_id'.
        """
        return 4 * t_id

    def next_corner(self, c_id):
        """
        Returns the next corner from the given corner `c_id'.
        """
        if c_id % 4 == 2:
            return c_id - 2
        else:
            return c_id + 1

    def previous_corner(self, c_id):
        """
        Returns the previous corner from the given corner `c_id'.
        """
        if c_id % 4 == 0:
            return c_id + 2
        else:
            return c_id - 1

    def left_corner(self, c_id):
        """
        Returns the corner on left of the given `c_id'.
        """
        return self.oposite(self.next_corner(c_id))

    def right_corner(self, c_id):
        """
        Returns the corner on right of the given `c_id'.
        """
        return self.oposite(self.previous_corner(c_id))


    def swing(self, c_id):
        """
        Swings around the given corner `c_id' in the clockwise order. It
        returns the next corner related to the same vertex from c_id in next
        triangle around that vertex in clockwise order.
        """
        return self.next_corner(self.oposite(self.next_corner(c_id)))

    def next_vertex_ring(self, v):
        """
        Returns the next vertex on the edge ring for vertex `v'
        """
        return (v + 1) % self.mr

    def previous_vertex_ring(self, v):
        """
        Returns the previous vertex on the edge ring for vertex `v'
        """
        return (v + self.mr - 1) % self.mr

    def is_t2_triangle(self, t_id):
        if t_id >= 2*self.mr:
            return False
        elif t_id % 2:
            return self.R[t_id/2][1] == 2
        else:
            return self.L[t_id/2][1] == 2

    def is_expensive_triangle(self, t_id):
        if t_id >= 2*self.mr:
            return False
        c = self.corner_triangle(t_id)
        v = int(math.floor(c / 8.0))

        if t_id % 2:
            return self.R[v][2]
        else:
            return self.L[v][2]

    def to_canonical(self, c_id):
        t = self.triangle(c_id)
        v = int(math.floor(c_id / 8.0))
        if self.is_t2_triangle(t):
            if self.L[v][0] == self.next_vertex_ring(self.next_vertex_ring(v)) and c_id % 8 in (0, 1, 2):
                if c_id % 8 == 0:
                    r = 1
                elif c_id % 8 == 1:
                    r = 2
                elif c_id % 8 == 2:
                    r = 0

                c_id = 8*self.next_vertex_ring(v) + r
                v = int(math.floor(c_id / 8.0))
                return c_id
            
            elif self.R[v][0] == self.next_vertex_ring(self.next_vertex_ring(v)) and c_id % 8 in (4, 5, 6):
                if c_id % 8 == 4:
                    r = 6
                elif c_id % 8 == 5:
                    r = 4
                elif c_id % 8 == 6:
                    r = 5

                c_id = 8*self.next_vertex_ring(v) + r
                v = int(math.floor(c_id / 8.0))
                return c_id

            else:
                return c_id
        else:
            return c_id

    def to_vertices_faces(self):
        faces = []
        colours = {}
        lines = []
        for v0 in xrange(self.mr):
            v1 = self.next_vertex_ring(v0)

            #faces.append((v0, self.L[v0], v1))
            #faces.append((v1, self.R[v0], v0))

            lines.append((v0, v1, v0))

            #colours[v0] = 255, 0, 0
            #colours[v1] = 255, 0, 0
            #colours[self.L[v0]] = 0, 255, 0
            #colours[self.R[v0]] = 0, 0, 255

        #no_skip = set()

        #for t in xrange(self.number_triangles):
            #if self.is_t2_triangle(t):
                #continue
            #else:
                #c0 = self.corner_triangle(t)
                #c1 = self.next_corner(c0)
                #c2 = self.next_corner(c1)

                #v0 = self.vertex(c0)
                #v1 = self.vertex(c1)
                #v2 = self.vertex(c2)
                #faces.append((v0, v1, v2))

                #colours[v0] = 255,   0,   0
                #colours[v1] = 255,   0,   0
                #colours[v2] = 255,   0,   0

                #if self.is_t2_triangle(t):
                    #render_next = False

        #lines = []
        ##cv = self.edge_ring.edge_ring[0]
        ##v = self.edge_ring.edges[self.ct.get_vertex(cv)]
        ##s = v
        ##nv = self.edge_ring.edges[v]
        ##lines.append((v, nv, v))
        ##v = nv
        for i in xrange(self.mr):
            v = i
            nv = self.next_vertex_ring(i)
            #cl[v]=  255,255,255
            #cl[nv]= 255,255,255
            #v = self.ct.get_vertex(v)
            #nv = self.ct.get_vertex(nv)
            #if nv == self.ct.get_vertex(self.ct.get_oposite_corner(cv)):
                #lines.append((v, nv, v))
                #break
            faces.append((v, self.L[v][0], nv))
            faces.append((nv, self.R[v][0], v))
            #v = nv

        #cl[self.ring[0]] = 255, 0, 0
        #cl[self.ring[-1]] = 0, 255, 0

        writer = ply_writer.PlyWriter('/tmp/saida_linhas.ply')
        writer.from_faces_vertices_list(lines, self.vertices)

        return self.vertices, faces, colours
                         

            


def read_ply(ply_filename):
    vertices = {}
    faces = []
    reader = ply_reader.PlyReader(ply_filename)
    v_id = 0
    for evt, data in reader.read():
        if evt == ply_reader.EVENT_VERTEX:
            current_vertex = data
            vertices[v_id] = current_vertex
            v_id += 1

        elif evt == ply_reader.EVENT_FACE:
            faces.append(data)

    return vertices, faces


def ring_expander(ct):
    s = 0 #random.randint(0, len(ct.V))
    c = s
    m_v = {ct.get_vertex(ct.previous_corner(c)): 1,
           ct.get_vertex(ct.next_corner(c)): 1}
    m_t = {}

    while 1:
        if not m_v.get(ct.get_vertex(c), 0):
            m_v[ct.get_vertex(c)] = 1
            m_t[ct.get_triangle(c)] = 1
        elif not m_t.get(ct.get_triangle(c), 0):
            c = ct.get_oposite_corner(c)
        c = ct.get_right_corner(c)

        if c == ct.get_oposite_corner(s):
            break

    return m_v


def clusterize_ct(ct, cluster_size):
    number_cluster = (len(ct.V)/3) / cluster_size
    if (len(ct.V)/3) % cluster_size:
        number_cluster += 1

    clusters = {}
    for n in xrange(number_cluster):
        clusters[n] = range(n * cluster_size,
                            (n + 1) * cluster_size)
    return clusters
    

def make_vertex_faces(vertices, faces):
    vertices_faces = {}
    for f_id, face in enumerate(faces):
        for v in face:
            try:
                vertices_faces[v].append(f_id)
            except KeyError:
                vertices_faces[v] = [f_id,]
    return vertices_faces

def _expand_ring(ct, s, cluster, min_, max_):
    c = s
    m_v = {ct.get_vertex(ct.previous_corner(c)): 1,
           ct.get_vertex(ct.next_corner(c)): 1}
    m_t = {}
    edge_ring = EdgeRinge(ct)
    #edge_ring.add_edge(ct.previous_corner(c))
    #edge_ring.add_edge((ct.previous_corner(c), ct.next_corner(c)))
    #edge_ring.edges[ct.get_vertex(ct.previous_corner(c))] = ct.get_vertex(ct.next_corner(c))


    n = 0
    last = ct.next_corner(c)
    while 1:
        if not m_v.get(ct.get_vertex(c), 0):
            if min_ <= ct.get_triangle(c) < max_:
                m_v[ct.get_vertex(c)] = 1
                m_t[ct.get_triangle(c)] = 1
                #edge_ring.append(ct.next_corner(c))
                #edge_ring.append(c)
                #edge_ring.append(ct.next_corner(c))
                if last is not None:
                    edge_ring.add_edge((last, c))
                n = 0
            else:
                c = ct.get_oposite_corner(c)
                if n > 100:
                    return m_v, m_t, edge_ring
                n += 1

        elif not m_t.get(ct.get_triangle(c), 0):
            c = ct.get_oposite_corner(c)

        #elif (not min_ <= ct.get_triangle(c) < max_) and (not m_t.get(ct.get_triangle(c), 0)) :
            ##print n, ct.get_triangle(c), min_, max_
            #c = ct.get_oposite_corner(c)
            ##c = ct.get_right_corner(c)
            ##print n, ct.get_triangle(c), min_, max_
        last = c
        c = ct.get_right_corner(c)
        if c == ct.get_oposite_corner(s):
            #edge_ring.edges[ct.get_vertex(last)] = edge_ring.edges[30]
            #edge_ring.add_edge((c, s))
            #edge_ring.add_edge((c, s))
            return m_v, m_t, edge_ring

def expand_ring_into_cluster(ct, cluster, pmin):
    #s = ct.get_corner_f(random.randint(min(clusters[ncluster]),
                                       #max(clusters[ncluster])))
    n_too_little = 0
    min_, max_ = min(cluster), max(cluster)
    vertices = set()
    for i in xrange(min_, max_):
        for c in ct.iterate_triangle_corner(i):
            vertices.add(ct.get_vertex(c))

    nvertices = len(vertices)

    gt_t = -1
    gt = None

    print "Cluster size", len(cluster)
    for i in xrange(10):
        s = ct.get_corner_f(random.randint(min_, max_))
        for c in ct.iterate_triangle_corner(i):
            s = c
            m_v, m_t, edge_ring = _expand_ring(ct, s, cluster, min_, max_)
            if len(m_v) > gt_t or gt is None:
                gt_t = len(m_v)
                gt = s
        #if (float(len(m_t)) / (max_ - min_)) > pmin:
            #break
        #else:
            ##print "\tjust a little", len(m_v), len(m_t), float(len(m_t)) / (max_ - min_)
            #if n_too_little == 1000:
                #break
            #n_too_little += 1

    m_v, m_t, edge_ring = _expand_ring(ct, gt, cluster, min_, max_)
    print nvertices, len(m_v)

    #edge_ring_t = []
    #for c in edge_ring:
        #for ci in ct.iterate_triangle_corner(ct.get_triangle(c)):
            #edge_ring_t.append(ci)

    return m_v, m_t, edge_ring

def hybrid_expand_ring_into_cluster(ct, ncluster, clusters):
    min_, max_ = min(clusters[ncluster]), max(clusters[ncluster])
    s = ct.get_corner_f(random.randint(min_, max_))
    c = s
    k = 99999

    m_v = {ct.get_vertex(ct.previous_corner(c)): 1,
           ct.get_vertex(ct.next_corner(c)): 1}
    m_t = {}
    d = []
    n = 0
    while 1:
        if (not m_v.get(ct.get_vertex(c), 0)) and (min_ <= ct.get_triangle(c) < max_):
            m_v[ct.get_vertex(c)] = 1
            m_t[ct.get_triangle(c)] = 1

            d.append(ct.get_left_corner(c))
            d.append(ct.get_right_corner(c))
            n += 1

        if not d:
            break
        if n % k == 0:
            c = d.pop(0)
        else:
            c = d.pop()
        
    return m_v


def test_laced_ring(vertices, faces, cluster_size, pmin):
    vertices_faces = make_vertex_faces(vertices, faces)
    ct = cy_corner_table.CornerTable()
    ct.create_corner_from_vertex_face(vertices, faces, vertices_faces)
    clusters = colour_clusters.clusterize(faces, cluster_size) # clusterize_ct(ct, cluster_size)
    #print clusters.keys()
    ecluster = {}
    #for i, cluster in enumerate(clusters):
        #if len(cluster) > 1:
            #ncluster, m_t = expand_ring_into_cluster(ct, cluster, pmin)
            #print i, len(ncluster), len(m_t) / float(len(cluster))
            #ecluster.update(ncluster)

    #colours = {}
    #for v in xrange(len(vertices)):
        #if ecluster.get(v, 0):
            #colours[v] = (255, 0, 0)
        #else:
            #colours[v] = (255, 255, 255)
    #writer = ply_writer.PlyWriter('/tmp/saida.ply')
    #writer.from_faces_vertices_list(faces, vertices, colours)
    ncluster, m_t, edge_ring = expand_ring_into_cluster(ct, clusters[0], pmin)
    lr = LacedRing()
    lr.make_lr(ct, edge_ring, m_t)
    vertices, faces, colours = lr.to_vertices_faces()
    writer = ply_writer.PlyWriter('/tmp/saida.ply')
    writer.from_faces_vertices_list(faces, vertices, colours)


def main():
    vertices, faces = read_ply(sys.argv[1])
    test_laced_ring(vertices, faces, int(sys.argv[2]), float(sys.argv[3]))

if __name__ == '__main__':
    main()


