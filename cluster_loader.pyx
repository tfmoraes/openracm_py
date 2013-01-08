import struct

from libc.stdio cimport *

cdef extern from "stdlib.h": 
    void *memcpy(void *dst, void *src, long n)

STRUCT_FORMATS = {'v': 'cLddd',
                  'L': 'clll',
                  'R': 'clll',
                  'S': 'clllll',

                  'V': 'cll',
                  'O': 'cll',
                  'C': 'cll',
                 }


cdef struct struct_v:
    char c
    long v_id
    double vx
    double vy
    double vz

cdef struct struct_L:
    char c
    long l0
    long l1
    long l2

cdef struct struct_R:
    char c
    long r0
    long r1
    long r2

cdef struct struct_S:
    char c
    long s0
    long s1
    long s2
    long s3
    long s4

cdef struct struct_V:
    char c
    long c_id
    long v_id

cdef struct struct_C:
    char c
    long v_id
    long c_id

cdef struct struct_O:
    char c
    long c_id
    long c_o


STRUCT_SIZES = {key:struct.calcsize(f) for (key, f) in STRUCT_FORMATS.items()}

cpdef tuple cluster_loader(str cluster):
    cdef long init, cluster_size
    cdef  struct_v tmp_v
    cdef  struct_L tmp_L
    cdef  struct_R tmp_R
    cdef  struct_S tmp_S
    cdef  struct_V tmp_V
    cdef  struct_C tmp_C
    cdef  struct_O tmp_O
    #cdef char t_element
    cdef char* tmp
    vertices = {}

    L = {}
    R = {}
    VOs = {}

    V = {}
    C = {}
    O = {}
    #cluster = str_cluster
    init = 0
    cluster_size = len(cluster)
    while init != cluster_size:
        tmp_p = cluster[init: init + STRUCT_SIZES[cluster[init]]]
        tmp = <char *> tmp_p
        init += STRUCT_SIZES[cluster[init]]
        t_element = tmp[0]
        #cluster = cluster[STRUCT_SIZES[cluster[0]]::]

        if t_element == 'v':
            #c_, v_id, vx, vy, vz = struct.unpack(STRUCT_FORMATS['v'], tmp) 
            #vertices[v_id] = [vx, vy, vz]
            memcpy(&tmp_v, tmp, sizeof(tmp_v))
            vertices[tmp_v.v_id] = [tmp_v.vx, tmp_v.vy, tmp_v.vz]

        elif t_element == 'L':
            #c_, l0, l1, l2 = struct.unpack(STRUCT_FORMATS['L'], tmp) 
            memcpy(&tmp_L, tmp, sizeof(tmp_L))
            L[tmp_v.v_id] = [tmp_L.l0, tmp_L.l1, tmp_L.l2]

        elif t_element == 'R':
            #c_, r0, r1, r2 = struct.unpack(STRUCT_FORMATS['R'], tmp) 
            #R[v_id] = [r0, r1, r2]
            memcpy(&tmp_R, tmp, sizeof(tmp_R))
            R[tmp_v.v_id] = [tmp_R.r0, tmp_R.r1, tmp_R.r2]

        elif t_element == 'S':
            #c_, s0, s1, s2, s3, s4 = struct.unpack(STRUCT_FORMATS['S'], tmp)
            #VOs[v_id] = [s0, s1, s2, s3, s4]
            memcpy(&tmp_S, tmp, sizeof(tmp_S))
            VOs[tmp_v.v_id] = [tmp_S.s0, tmp_S.s1, tmp_S.s2, tmp_S.s3, tmp_S.s4]

        elif t_element == 'V':
            #c_, c_id, v_id = struct.unpack(STRUCT_FORMATS['V'], tmp)
            #V[c_id] = v_id
            memcpy(&tmp_V, tmp, sizeof(tmp_V))
            V[tmp_V.c_id] = tmp_V.v_id

        elif t_element == 'C':
            #c_, v_id, c_id = struct.unpack(STRUCT_FORMATS['C'], tmp)
            #C[v_id] = c_id
            memcpy(&tmp_C, tmp, sizeof(tmp_C))
            C[tmp_C.v_id] = tmp_C.c_id

        elif t_element == 'O':
            #c_, c_id, c_o = struct.unpack(STRUCT_FORMATS['O'], tmp)
            #O[c_id] = c_o
            memcpy(&tmp_O, tmp, sizeof(tmp_O))
            O[tmp_O.c_id] = tmp_O.c_o

    return vertices, L, R, VOs, V, C, O
