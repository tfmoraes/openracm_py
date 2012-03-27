#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# cython: profile=True

import copy
import cy_corner_table
import sys
import random

from cy_corner_table cimport CornerTable

cdef int FIFO=1
cdef int CONTROLLABLE=2

cdef int BUFFER_SIZE = 20

cdef int WHITE = 0
cdef int GRAY = 1
cdef int BLACK = 2

cdef float K1 = 1.0
cdef float K2 = 0.5
cdef float K3 = 3.0

def _count_degree(ct, v_id):
    c = ct.get_corner_v(v_id)
    t = ct.get_triangle(c)
    cc = c
    d = 1
    while 1:
        cc = ct.swing(cc)
        nt = ct.get_triangle(cc)
        if nt == t:
            break
        else:
            d += 1
    return d

cdef int _get_minimun_degree_vertex(CornerTable ct, list v_w):
    cdef int v
    cdef int minimun = 1000000
    for v in v_w:
        if ct.get_vertex_degree(v) < minimun:
            minimun = v
    return minimun

cdef list _get_white_bounding_vertices(CornerTable ct, list v_w, int t_id, dict vstatus):
    cdef int c_id, v_id
    cdef list output = []
    for c_id in ct.iterate_triangle_corner(t_id):
        v_id = ct.V[c_id]
        if vstatus.get(v_id, WHITE) == WHITE:
            output.append(v_id)
    return output

cdef list _get_renderable_faces_in_buffer(CornerTable ct, list v_g, list v_w, dict v_status):
    cdef int t_id, c_id
    cdef list output = []
    for v_id in v_g:
        for t_id in ct.get_faces_connected_to_v(v_id):
            for c_id in ct.iterate_triangle_corner(t_id):
                if v_status[ct.V[c_id]] == WHITE:
                    break
            else:
                if t_id not in output:
                    output.append(t_id)
    return output


cdef list _get_unrenderable_faces_in_buffer(CornerTable ct, list v_g, list v_w, dict v_status):
    cdef int t_id, c_id
    cdef list output = []
    for v_id in v_g:
        for t_id in ct.get_faces_connected_to_v(v_id):
            for c_id in ct.iterate_triangle_corner(t_id):
                if v_status[ct.V[c_id]] == GRAY:
                    break
            else:
                output.append(t_id)
    return output

cdef int has_unrenderable_faces_connected_v(CornerTable ct, int vfocus, dict v_status):
    cdef int t_id, c_id
    for t_id in ct.get_faces_connected_to_v(vfocus):
        for c_id in ct.iterate_triangle_corner(t_id):
            if v_status.get(ct.V[c_id], WHITE) == WHITE:
                return True
    return False


cdef list _get_unrenderable_faces_in_buffer_connected_v(CornerTable ct, int vfocus, list
                                                        v_g, list v_w, dict
                                                        v_status):
    """
    Unrenderable face is that ones whose not all it vertices are in buffer.
    """
    cdef list output = []
    cdef int t_id, c_id, cg
    for t_id in ct.get_faces_connected_to_v(vfocus):
        for c_id in ct.iterate_triangle_corner(t_id):
            if v_status.get(ct.V[c_id], WHITE) == WHITE:
                output.append(t_id)
                break
    return output


cdef int _calc_c2(CornerTable ct, int vfocus, list v_w, list v_g, dict v_status, dict f_status):
    cdef int f, c
    c = 0
    for f in ct.get_faces_connected_to_v(vfocus):
        if f_status.get(f, 0) == 0:
            c += 1
    #return len(_get_unrenderable_faces_in_buffer_connected_v(ct, vfocus, v_g,
                                                             #v_w, v_status))
    return c

cdef tuple _calc_c1_c3(CornerTable ct, int vfocus, list v_w, list v_g, list
                       F_output, dict v_status, dict f_status, int buffer_size):
    cdef list v_ws = v_w[:]
    cdef list v_gs = v_g[:]
    cdef dict v_status_s = v_status.copy()
    cdef dict f_status_s = f_status.copy()
    #cdef list F_output_s = F_output[:]
    cdef int c1 = 0
    cdef int f, fr, vl, c3, i

    for f in ct.get_faces_connected_to_v(vfocus):
        if f_status_s.get(f, 0):
            continue
        #for vl in _get_white_bounding_vertices(ct, v_w, f, v_status):
        for c_id in ct.iterate_triangle_corner(f):
            vl = ct.V[c_id]
            if v_status_s.get(vl, WHITE) != WHITE:
                continue
            if len(v_gs) == buffer_size:
                va = v_gs.pop(0)
                v_ws.append(va)
                v_status_s[va] = WHITE
            v_ws.remove(vl)
            v_gs.append(vl)
            v_status_s[vl] = GRAY
            c1 += 1

            for fr in _get_renderable_faces_in_buffer(ct, v_gs, v_ws, v_status_s):
                if (fr != f) and f_status_s.get(fr, 0) == 0:
                    ##F_output_s.append(fr)
                    f_status_s[fr] = 1
        #F_output_s.append(f)
        f_status_s[f] = 1

    #v_b.append(v_focus)

    try:
        c3 = v_gs.index(vfocus)
    except ValueError:
        c3 = buffer_size

    return c1, float(c3) / buffer_size


cdef int get_minimun_cost_vertex(CornerTable ct, list v_w, list v_g, list
                                 F_output, dict v_status, dict f_status,
                                 int buffer_size):
    cdef int v, vmin, c1, c2
    cdef float c, c3
    cdef float minimun = 1000000
    for v in v_g:
        c2 = _calc_c2(ct, v, v_w, v_g, v_status, f_status)
        c1, c3 = _calc_c1_c3(ct, v, v_w, v_g, F_output, v_status, f_status, buffer_size)
        c = c1*K1 + c2*K2 + c3*K3
        if (c < minimun):
            minimun = c
            vmin = v
    return vmin


cdef list get_unrendered_faces_connected_v(ct, v, f_status):
    cdef int f
    cdef list output = []
    for f in ct.get_faces_connected_to_v(v):
        if f_status.get(f, 0) == 0:
            output.append(f)
    return output


cpdef k_cache_reorder(CornerTable ct, buffer_size, model=FIFO):
    cdef list v_w, v_g, v_b, F_output
    cdef dict v_status, f_status
    cdef int vfocus, vl, vi, fb, fr, f
    v_w = ct.vertices.keys()
    
    v_g = []
    v_b = []

    F = range(len(ct.V)/3)
    F_output = []

    v_status = dict([(i, 0) for i in xrange(len(v_w))])
    f_status = {} #dict([(i, 0) for i in xrange(len(F))])

    while len(v_b) < len(ct.vertices):
        if v_g:
            vfocus =  get_minimun_cost_vertex(ct, v_w, v_g, F_output, v_status,
                                              f_status, buffer_size)
        else:
            vfocus = _get_minimun_degree_vertex(ct, v_w)
        #for f in get_unrendered_faces_connected_v(ct, vfocus, f_status):
        for f in ct.get_faces_connected_to_v(vfocus):
            if f_status.get(f, 0):
                continue
            #for vl in _get_white_bounding_vertices(ct, v_w, f, v_status):

            for c_id in ct.iterate_triangle_corner(f):
                vl = ct.V[c_id]
                if v_status.get(vl, WHITE) != WHITE:
                    continue
                if len(v_g) == buffer_size:
                    va = v_g.pop(0)
                    v_w.insert(0, va)
                    v_status[va] = WHITE
                v_w.remove(vl)
                v_g.append(vl)
                v_status[vl] = GRAY

                for fr in _get_renderable_faces_in_buffer(ct, v_g, v_w, v_status):
                    if (fr != f) and f_status.get(fr, 0) == 0:
                        F_output.append(fr)
                        f_status[fr] = 1
                #F_output.extend([i for i in _get_renderable_faces_in_buffer(ct, v_g) if (i != f) and (i not in F_output)])

            F_output.append(f)
            f_status[f] = 1

        v_b.append(vfocus)

        if v_g:
            try:
                v_g.remove(vfocus)
            except ValueError:
                pass

        sys.stdout.write('\rSorting: %.2f - %d - %d - %d' % ((100.0*len(F_output))/(len(F)),
                                              len(v_b), len(v_w), len(v_g)))
        sys.stdout.flush()

        while 1:
            if v_g and has_unrenderable_faces_connected_v(ct, v_g[0], v_status):
                v_b.append(v_g.pop(0))
            else:
                break
    print 
    print len(F_output), len(F)
    return F_output
