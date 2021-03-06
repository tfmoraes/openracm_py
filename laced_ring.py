#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import math
import random
import sys
import time

import ply_reader
import cy_corner_table
import ply_writer
import colour_clusters

import copy

class DefaultDict(dict):
    """Dictionary with a default value for unknown keys."""
    def __init__(self, default):
        self.default = default

    def __getitem__(self, key):
        if key in self: 
            return self.get(key)
        else:
            ## Need copy in case self.default is something like []
            return self.setdefault(key, copy.deepcopy(self.default))

    def __copy__(self):
        copy = DefaultDict(self.default)
        copy.update(self)
        return copy

class EdgeRinge(object):
    def __init__(self, ct):
        self.ct = ct
        self.edges = DefaultDict(-1)
        self.triangles = []

    def add_edge(self, edge):
        c0, c1 = edge

        nc = self.ct.next_corner(c1)
        pc = self.ct.previous_corner(c1)

        v0 = self.ct.get_vertex(c0)
        v1 = self.ct.get_vertex(c1)
        nv = self.ct.get_vertex(nc)
        pv = self.ct.get_vertex(pc)
        v2 = pv

        self.edges[v0] = v1
        self.edges[v1] = v2
        #self.edges[v2] = v0

    def add_triangle(self, triangle, c0):
        #c0 = self.ct.get_corner_f(triangle)
        c1 = self.ct.next_corner(c0)
        c2 = self.ct.next_corner(c1)

        v0 = self.ct.get_vertex(c0)
        v1 = self.ct.get_vertex(c1)
        v2 = self.ct.get_vertex(c2)

        self.triangles.append((v0, v1, v2))

        o = [1, 1, 1]
        for i, (vi, vj) in enumerate(((v0, v1), (v1, v2), (v2, v0))):
            if self.edges[vj] == vi or self.edges[vi] == vj:
                o[i] = 0
                #del self.edges[vj]
            #elif self.edges[vi] == vj:
                #o[i] = 0
                #del self.edges[vi]

        for i, (vi, vj) in enumerate(((v0, v1), (v1, v2), (v2, v0))):
            if o[i] or vi not in self.edges:
                self.edges[vi] = vj



        #if self.edges[v1] == v0:
            #self.edges[v1] = v2
        #else:
            #self.edges[v0] = v1
        #if self.edges[v2] == v1:
            #self.edges[v2] = v0
        #else:
            #self.edges[v1] = v2
        #if self.edges[v0] == v2:
            #self.edges[v0] = v1
        #else:
            #self.edges[v2] = v0
        #else:
            ##print 4
            #self.edges[v0] = v1
            #self.edges[v1] = v2
            #self.edges[v2] = v0

        #if self.edges[v1] == v0:
            #print 1
            #self.edges[v1] = v2
            #self.edges[v2] = v0
        #elif self.edges[v2] == v1:
            ##print 2
            #self.edges[v2] = v0
            #self.edges[v0] = v1
        #elif self.edges[v0] == v2:
            #print 3
            #self.edges[v1] = v2
            #self.edges[v2] = v0
        #else:
            ##print 4
            #self.edges[v0] = v1
            #self.edges[v1] = v2
            #self.edges[v2] = v0
        #if v0 in self.edges:
            ##print 1
            #self.edges[v1] = v2
            #self.edges[v2] = v0
        #elif v1 in self.edges:
            #print 2
            #self.edges[v0] = v1
            #self.edges[v2] = v0
        #elif v2 in self.edges:
            #self.edges[v0] = v1
            #self.edges[v1] = v2

    def save_edge(self):
        lines = []
        for v0 in self.edges:
            v1 = self.edges[v0]
            v2 = v0
            if v0 > 0 and v1 > 0 and v2 > 0:
                lines.append((v0, v1, v2))
        writer = ply_writer.PlyWriter('/tmp/saida_edges.ply')
        writer.from_faces_vertices_list(lines, self.ct.vertices)

        writer = ply_writer.PlyWriter('/tmp/saida_triangulos.ply')
        writer.from_faces_vertices_list(self.triangles, self.ct.vertices)



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

    def make_lr(self, ct, edge_ring):
        map_ct_lr, map_lr_ct = self.reorder_vertices(ct, edge_ring)

        map_clr_cct = {}
        map_cct_clr = {}

        for v0 in xrange(self.mr):
            v1 = self.next_vertex_ring(v0)
            t, c0, c1 = ct.get_triangle_by_edge(map_lr_ct[v0], map_lr_ct[v1])

            r = ct.previous_corner(c0)
            l = ct.get_oposite_corner(r)

            vl = map_ct_lr[ct.get_vertex(l)]
            vr = map_ct_lr[ct.get_vertex(r)]

            self.L[v0] = [vl, 1, 0]
            self.R[v0] = [vr, 1, 0]

            # v.Tl
            ct_c0 = ct.previous_corner(l)
            ct_c1 = l
            ct_c2 = ct.next_corner(l)

            lr_v0 = 8*v0 + 0
            lr_v1 = 8*v0 + 1
            lr_v2 = 8*v0 + 2
            
            map_cct_clr[ct_c0] = lr_v0
            map_clr_cct[lr_v0] = ct_c0

            map_cct_clr[ct_c1] = lr_v1
            map_clr_cct[lr_v1] = ct_c1

            map_cct_clr[ct_c2] = lr_v2
            map_clr_cct[lr_v2] = ct_c2

            # v.TR
            ct_c4 = c1
            ct_c5 = r
            ct_c6 = c0

            lr_v4 = 8*v0 + 4
            lr_v5 = 8*v0 + 5
            lr_v6 = 8*v0 + 6
            
            map_cct_clr[ct_c4] = lr_v4
            map_clr_cct[lr_v4] = ct_c4

            map_cct_clr[ct_c5] = lr_v5
            map_clr_cct[lr_v5] = ct_c5

            map_cct_clr[ct_c6] = lr_v6
            map_clr_cct[lr_v6] = ct_c6

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

        self._handle_t0(ct, edge_ring, map_ct_lr, map_lr_ct, map_cct_clr, map_clr_cct)

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
                self.ring.append(v0)
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

        self.m = i
            
        return map_ct_lr, map_lr_ct

    def _handle_t0(self, ct, edge_ring, map_ct_lr, map_lr_ct, map_cct_clr, map_clr_cct):
        t0_triangles = set()
        for t_id in xrange(len(ct.V) / 3):
            c, nc, pc = ct.iterate_triangle_corner(t_id)
            v, nv, pv = [ct.get_vertex(i) for i in (c, nc, pc)]
            if not (edge_ring.edges.get(v, -1) in (nv, pv) \
               or edge_ring.edges.get(nv, -1) in (pv, v) \
               or edge_ring.edges.get(pv, -1) in (v, nv)):
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

            map_cct_clr[c] = t_c_id
            map_clr_cct[t_c_id] = c

            map_cct_clr[nc] = t_c_id + 1
            map_clr_cct[t_c_id + 1] = nc

            map_cct_clr[pc] = t_c_id + 2
            map_clr_cct[t_c_id + 2] = pc

            t_c_id += 4


        for c in xrange(8*self.mr, t_c_id - 1, 4):
            cn = c + 1
            cp = c + 2

            o = self.to_canonical(map_cct_clr[ct.get_oposite_corner(map_clr_cct[c])])
            on = self.to_canonical(map_cct_clr[ct.get_oposite_corner(map_clr_cct[cn])])
            op = self.to_canonical(map_cct_clr[ct.get_oposite_corner(map_clr_cct[cp])])

            self.O[c] = o
            self.O[cn] = on
            self.O[cp] = op

            self.map_VOs(o, c)
            self.map_VOs(on, cn)
            self.map_VOs(op, cp)

        ##for c in (8 * self.mr, c_id, 3):
            ##v0 = self.V[c]
            ##v1 = self.V[c + 1]
            ##v2 = self.V[c + 2]

        #ti = set()
        #for c_id in xrange(8*self.mr, t_c_id, 4):
            #cn = c_id + 1
            #cp = c_id + 2
            #v = self.vertex(c_id)
            #vn = self.vertex(cn)
            #vp = self.vertex(cp)

            #s = set((v, vn, vp))
            #for ci, vi in ((c_id, v), (cn, vn), (cp, vp)):
                #cs = s - set((vi,))
                #for t in xrange(self.number_triangles):
                    #c0 = self.corner_triangle(t)
                    #c1 = self.next_corner(c0)
                    #c2 = self.next_corner(c1)

                    #v0 = self.vertex(c0)
                    #v1 = self.vertex(c1)
                    #v2 = self.vertex(c2)

                    #diff = set((v0, v1, v2)) - cs

                    #if len(diff) == 1:
                        #vo = diff.pop()
                        #if vo == v0 and vo != vi:
                            #o = c0
                        #elif vo == v1 and vo != vi:
                            #o = c1
                        #elif vo == v2 and vo != vi:
                            #o = c2
                        #else:
                            #print "YES!"
                            #continue

                        #self.O[ci] = o
                        #break


                #t = self.triangle(o)
                #v = int(math.floor(o / 8.0))

                #if v not in self.VOs and (v in self.R or v in self.L):
                    #self.VOs[v] = [-1, -1, -1, -1]
                #if t % 2:
                    #try:
                        #self.R[v][2] = 1
                        #if o % 8 == 4: 
                            #self.VOs[v][2] = ci
                        #elif o % 8 == 6:
                            #self.VOs[v][3] = ci
                    #except KeyError:
                        #pass
                #else:
                    #try:
                        #self.L[v][2] = 1
                        #if o % 8 == 0:
                            #self.VOs[v][0] = ci
                        #elif o % 8 == 2:
                            #self.VOs[v][1] = ci
                    #except KeyError:
                        #pass

                ## Mapping VO* to the cannonical t2 triangle
                #if self.is_t2_triangle(t) and self.to_canonical(o) != o:
                    #o = self.to_canonical(o)
                    #t = self.triangle(o)
                    #v = int(math.floor(o / 8.0))

                    #if v not in self.VOs:
                        #self.VOs[v] = [-1, -1, -1, -1]
                    #if t % 2:
                        #self.R[v][2] = 1
                        #if o % 8 == 4: 
                            #self.VOs[v][2] = ci
                        #elif o % 8 == 6:
                            #self.VOs[v][3] = ci
                    #else:
                        #self.L[v][2] = 1
                        #if o % 8 == 0:
                            #self.VOs[v][0] = ci
                        #elif o % 8 == 2:
                            #self.VOs[v][1] = ci


        ##for t in self.VOs:
            ##c = self.corner_triangle(t)
            ##v = int(math.floor(c / 8.0))
            ##if t % 2:
                ##if self.VOs[t][0] == -1:
                    ##self.VOs[t][0] = self.oposite(v*8)[0]
                ##else:
                    ##self.VOs[t][1] = self.oposite(v*8 + 2)[0]
            ##else:
                ##if self.VOs[t][0] == -1:
                    ##self.VOs[t][0] = self.oposite(v*8 + 4)[0]
                ##else:
                    ##self.VOs[t][1] = self.oposite(v*8 + 6)[0]

    def map_VOs(self, c, o):
        if c < self.mr * 8:
            v = int(math.floor(c / 8.0))
            t = self.triangle(c)

            if v not in self.VOs and (v in self.R or v in self.L):
                self.VOs[v] = [-1, -1, -1, -1]
            if t % 2:
                try:
                    self.R[v][2] = 1
                    if c % 8 == 4: 
                        self.VOs[v][2] = o
                    elif c % 8 == 6:
                        self.VOs[v][3] = o
                except KeyError:
                    pass
            else:
                try:
                    self.L[v][2] = 1
                    if c % 8 == 0:
                        self.VOs[v][0] = o
                    elif c % 8 == 2:
                        self.VOs[v][1] = o
                except KeyError:
                    pass

    def test(self):
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
                            print "Certo 0", (c, self.vertex(c), self.triangle(c), self.is_t2_triangle(self.triangle(c))), (o, self.vertex(o[0]), self.triangle(o[0]), self.is_t2_triangle(self.triangle(o[0]))), co
                        elif c == self.to_canonical(co[0]):
                            print "Certo 1", (c, self.vertex(c), self.triangle(c), self.is_t2_triangle(self.triangle(c))), (o, self.vertex(o[0]), self.triangle(o[0]), self.is_t2_triangle(self.triangle(o[0]))), co
                        elif self.to_canonical(c) == self.to_canonical(co[0]):
                            print "Certo 2", (c, self.vertex(c), self.triangle(c), self.is_t2_triangle(self.triangle(c))), (o, self.vertex(o[0]), self.triangle(o[0]), self.is_t2_triangle(self.triangle(o[0]))), co
                        else:
                            print "Erro", (c, self.vertex(c), self.triangle(c), self.is_t2_triangle(self.triangle(c))), (o, self.vertex(o[0]), self.triangle(o[0]), self.is_t2_triangle(self.triangle(o[0]))), (co, self.vertex(co[0]), self.triangle(co[0]), self.is_t2_triangle(self.triangle(co[0])))
                    else:
                        print "Certo 3", (c, self.vertex(c), self.triangle(c), self.is_t2_triangle(self.triangle(c))), (o, self.vertex(o[0]), self.triangle(o[0]), self.is_t2_triangle(self.triangle(o[0]))), (co, self.vertex(co[0]), self.triangle(co[0]), self.is_t2_triangle(self.triangle(co[0])))
                else:
                    print "No tratado 2",(c, self.vertex(c), self.triangle(c), self.is_t2_triangle(self.triangle(c)))

    def vertex(self, c_id):
        """
        Return the vertex `v' related to the given corner `c_id'.
        """
        if c_id >= 8 * self.mr:
            if isinstance(self.V, list):
                i = int(c_id - math.floor(c_id / 4) - 6 * self.mr)
                return self.V[i]
            else:
                return self.V[c_id]
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

            c_id = self.to_canonical(c_id)
            #if self.L[v][0] == self.next_vertex_ring(self.next_vertex_ring(v)) and c_id % 8 in (0, 1, 2):
                #if c_id % 8 == 0:
                    #r = 1
                #elif c_id % 8 == 1:
                    #r = 2
                #elif c_id % 8 == 2:
                    #r = 0

                #c_id = 8*self.next_vertex_ring(v) + r
                #v = int(math.floor(c_id / 8.0))
            
            #elif self.R[v][0] == self.next_vertex_ring(self.next_vertex_ring(v)) and c_id % 8 in (4, 5, 6):
                #if c_id % 8 == 4:
                    #r = 6
                #elif c_id % 8 == 5:
                    #r = 4
                #elif c_id % 8 == 6:
                    #r = 5

                #c_id = 8*self.next_vertex_ring(v) + r
            v = int(math.floor(c_id / 8.0))
            t = self.triangle(c_id)

        #################################################


        ## This corner if related to a T0 triangle, so its oposity is in O
        ## array.
        if c_id >= 8 * self.mr:
            #i = int(c_id - math.floor(c_id / 4.0) - 6 * self.mr)
            o = self.O[c_id], 0
            #return -1, -1


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

        # the triangle t related to the given corner is a expensive triangle,
        # so it's necessary to lookup VOs structure to find c.o.
        
        elif c_id % 8 == 0 and self.is_expensive_triangle(t) and self.VOs[v] and self.VOs[v][0] != -1:
            o = self.VOs[v][0], 40
        elif c_id % 8 == 2 and self.is_expensive_triangle(t) and self.VOs[v] and self.VOs[v][1] != -1:           
            o = self.VOs[v][1], 41
        elif c_id % 8 == 4 and self.is_expensive_triangle(t) and self.VOs[v] and self.VOs[v][2] != -1:           
            o = self.VOs[v][2], 42
        elif c_id % 8 == 6 and self.is_expensive_triangle(t) and self.VOs[v] and self.VOs[v][3] != -1:           
            o = self.VOs[v][3], 43

        elif c_id % 8 == 2 and self.is_t2_triangle(t) and self.to_canonical(c_id) == c_id:
            o = 8*self.previous_vertex_ring(v) + 5, 666

        elif c_id % 8 == 4 and self.is_t2_triangle(t) and self.to_canonical(c_id) == c_id:
            o = 8*self.previous_vertex_ring(v) + 1, 999

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

        # TODO: Verify if it's correct.
        elif self.next_vertex_ring(self.L[v][0]) == self.L[self.previous_vertex_ring(v)][0] and c_id % 8 == 2:
            o = 8 * self.L[v][0] + 2, 1036

        elif self.L[self.next_vertex_ring(self.L[v][0])][0] == v and c_id % 8 == 2:
            o = 8 * self.L[v][0] + 2, 3033

        elif self.L[self.previous_vertex_ring(self.L[v][0])][0] == self.next_vertex_ring(v) and c_id % 8 == 2:
            o = 8 * self.L[v][0] + 2, 4044

        elif self.L[self.L[v][0]][0] == v and c_id % 8 == 2:
            o = 8 * self.L[v][0] + 2, 5055


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
        elif self.R[self.previous_vertex_ring(self.R[v][0])][0] == self.next_vertex_ring(v) and c_id % 8 == 4:
            o = 8*self.R[v][0] + 4, 9

        elif self.next_vertex_ring(self.R[v][0]) == self.R[self.previous_vertex_ring(v)][0] and c_id % 8 == 4:
            o = 8 * self.R[v][0] + 4, 9876

        elif self.R[self.next_vertex_ring(self.R[v][0])][0] == v and c_id % 8 == 4:
            o = 8 * self.R[v][0] + 4, 7410

        elif self.R[self.R[v][0]][0] == v and c_id % 8 == 4:
            o = 8 * self.R[v][0] + 4, 9099

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

            o = -1, -1

        try:
            t_o = self.triangle(o[0])
        except:
            print o, c_id
            sys.exit()

        if t_o == -1:
            print v, c_id, self.vertex(c_id), t, t_o, o, self.R[v], self.L[v]
        if self.is_t2_triangle(t_o):

            o = self.to_canonical(o[0]), o[1]
            #if self.L[v][0] == self.next_vertex_ring(self.next_vertex_ring(v)) and c_id % 8 in (0, 1, 2):
                #if c_id % 8 == 0:
                    #r = 1
                #elif c_id % 8 == 1:
                    #r = 2
                #elif c_id % 8 == 2:
                    #r = 0

                #c_id = 8*self.next_vertex_ring(v) + r
                #v = int(math.floor(c_id / 8.0))
            
            #elif self.R[v][0] == self.next_vertex_ring(self.next_vertex_ring(v)) and c_id % 8 in (4, 5, 6):
                #if c_id % 8 == 4:
                    #r = 6
                #elif c_id % 8 == 5:
                    #r = 4
                #elif c_id % 8 == 6:
                    #r = 5

                #c_id = 8*self.next_vertex_ring(v) + r
            #v = int(math.floor(c_id / 8.0))
            #t = self.triangle(c_id)

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
            return self.C[v_id]
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
        return self.next_corner(self.oposite(self.next_corner(c_id))[0])

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

    def get_ring0(self, v_id):
        c_id = self.to_canonical(self.corner_vertex(v_id))
        c = c_id
        ring0 = set()
        while 1:
            cn = self.next_corner(c)
            cp = self.previous_corner(c)
            vn = self.vertex(cn)
            vp = self.vertex(cp)

            ring0.add(vn)
            ring0.add(vp)

            c = self.swing(c)
            #print c, c_id
            if c == c_id:
                break
        return ring0
            
    def get_corners_triangle(self, t_id):
        corner = self.corner_triangle(t_id)
        return corner, self.next_corner(corner), self.previous_corner(corner)

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
            colours[v]=  255,255,255
            colours[nv]=  255,255,255
            colours[self.L[v][0]]=  255,255,255
            colours[self.R[v][0]]=  255,255,255
            #cl[nv]= 255,255,255
            #v = self.ct.get_vertex(v)
            #nv = self.ct.get_vertex(nv)
            #if nv == self.ct.get_vertex(self.ct.get_oposite_corner(cv)):
                #lines.append((v, nv, v))
                #break
            faces.append((v, self.L[v][0], nv))
            faces.append((nv, self.R[v][0], v))
            #v = nv

        faces_t0 = []
        init = self.triangle(8 * self.mr)
        for t in xrange(init, self.number_triangles):
            v, vn, vp = [self.vertex(c) for c in self.get_corners_triangle(t)]
            faces_t0.append((v, vn, vp))


        writer = ply_writer.PlyWriter('/tmp/saida_faces_t0.ply')
        writer.from_faces_vertices_list(faces_t0, self.vertices)

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

def _expand_ring(ct, s, min_, max_):
    c = s
    m_v = {ct.get_vertex(ct.previous_corner(c)): 1,
           ct.get_vertex(ct.next_corner(c)): 1}
    m_t = {}
    edge_ring = EdgeRinge(ct)
    #edge_ring.add_edge(ct.previous_corner(c))
    #edge_ring.add_edge((ct.previous_corner(c), ct.next_corner(c)))
    #edge_ring.edges[ct.get_vertex(ct.previous_corner(c))] = ct.get_vertex(ct.next_corner(c))
    while 1:
        if not m_v.get(ct.get_vertex(c), 0):
            m_v[ct.get_vertex(c)] = 1
            m_t[ct.get_triangle(c)] = 1

            edge_ring.add_triangle(ct.get_triangle(c), c)

        elif not m_t.get(ct.get_triangle(c), 0):
            c = ct.get_oposite_corner(c)

        c = ct.get_right_corner(c)

        if c == ct.get_oposite_corner(s):
            return m_v, m_t, edge_ring
    

    #n = 0
    #last = ct.next_corner(c)
    #while 1:
        #if not m_v.get(ct.get_vertex(c), 0):
            #if min_ <= ct.get_triangle(c) < max_:
                #m_v[ct.get_vertex(c)] = 1
                #m_t[ct.get_triangle(c)] = 1
                ##edge_ring.append(ct.next_corner(c))
                ##edge_ring.append(c)
                ##edge_ring.append(ct.next_corner(c))
                ##if last is not None:
                    ##edge_ring.add_edge((last, c))
                #edge_ring.add_triangle(ct.get_triangle(c))
                #n = 0
            #else:
                #c = ct.get_oposite_corner(c)
                #if n > 100:
                    #return m_v, m_t, edge_ring
                #n += 1

        #elif not m_t.get(ct.get_triangle(c), 0):
            #c = ct.get_oposite_corner(c)

        ##elif (not min_ <= ct.get_triangle(c) < max_) and (not m_t.get(ct.get_triangle(c), 0)) :
            ###print n, ct.get_triangle(c), min_, max_
            ##c = ct.get_oposite_corner(c)
            ###c = ct.get_right_corner(c)
            ###print n, ct.get_triangle(c), min_, max_
        #last = c
        #c = ct.get_right_corner(c)
        #if c == ct.get_oposite_corner(s):
            ##edge_ring.edges[ct.get_vertex(last)] = edge_ring.edges[30]
            ##edge_ring.add_edge((c, s))
            ##edge_ring.add_edge((c, s))
            #return m_v, m_t, edge_ring

def expand_ring(ct):
    #s = ct.get_corner_f(random.randint(min(clusters[ncluster]),
                                       #max(clusters[ncluster])))
    n_too_little = 0
    min_, max_ = 0, len(ct.vertices) * 1000

    nvertices = len(ct.vertices)

    gt_t = -1
    gt = None

    for i in xrange(10):
        s = ct.get_corner_f(random.randint(min_, max_))
        for c in ct.iterate_triangle_corner(i):
            s = c
            m_v, m_t, edge_ring = _expand_ring(ct, s, min_, max_)
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

    m_v, m_t, edge_ring = _expand_ring(ct, gt, min_, max_)

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
    #clusters = colour_clusters.clusterize(faces, cluster_size) # clusterize_ct(ct, cluster_size)
    #print clusters.keys()
    #ecluster = {}
    #for i, cluster in enumerate(clusters):
        #if len(cluster) > 1:
            #ncluster, m_t = expand_ring(ct, cluster, pmin)
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
    ncluster, m_t, edge_ring = expand_ring(ct)
    del ncluster
    del m_t
    edge_ring.save_edge()
    lr = LacedRing()
    lr.make_lr(ct, edge_ring)
    #lr.test()
    vertices, faces, colours = lr.to_vertices_faces()
    writer = ply_writer.PlyWriter('/tmp/saida.ply')
    writer.from_faces_vertices_list(faces, vertices, colours)


def main():
    vertices, faces = read_ply(sys.argv[1])
    test_laced_ring(vertices, faces, int(sys.argv[2]), float(sys.argv[3]))

if __name__ == '__main__':
    main()


