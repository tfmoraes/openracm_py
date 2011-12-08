#!/usr/bin/env python
# -*- coding: UTF-8 -*-

class PlyWriter(object):
    def __init__(self, filename):
        self.filename = filename

    def from_corner_table(self, ct):
        with file(self.filename, 'w') as ply_file:
            ply_file.write('ply\n')
            ply_file.write('format ascii 1.0\n')
            ply_file.write('element vertex %d\n' % len(ct.vertices))
            ply_file.write('property float x\n')
            ply_file.write('property float y\n')
            ply_file.write('property float z\n')
            ply_file.write('element face %d\n' % (len(ct.V)/3))
            ply_file.write('property list uchar int vertex_indices\n')
            ply_file.write('end_header\n')

            for v in ct.vertices.values():
                ply_file.write(' '.join(['%f' % i for i in v]) + '\n')

            for c_id in xrange(0, len(ct.V), 3):
                cn = ct.next_corner(c_id)
                cp = ct.previous_corner(c_id)
                ply_file.write('3 %d %d %d\n' % (ct.V[c_id], ct.V[cn], ct.V[cp]))
