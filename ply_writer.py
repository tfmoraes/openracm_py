#!/usr/bin/env python
# -*- coding: UTF-8 -*-

class PlyWriter(object):
    def __init__(self, filename):
        self.filename = filename

    def _write_header(self, ply_file, n_vertices, n_faces, has_colours=False):
        ply_file.write('ply\n')
        ply_file.write('format ascii 1.0\n')
        ply_file.write('element vertex %d\n' % n_vertices)
        ply_file.write('property float x\n')
        ply_file.write('property float y\n')
        ply_file.write('property float z\n')

        if has_colours:
            ply_file.write('property uchar red\n')
            ply_file.write('property uchar green\n')
            ply_file.write('property uchar blue\n')
            ply_file.write('property uchar alpha\n')

        ply_file.write('element face %d\n' % n_faces)
        ply_file.write('property list uchar int vertex_indices\n')
        ply_file.write('end_header\n')


    def from_corner_table(self, ct):
        with file(self.filename, 'w') as ply_file:
            self._write_header(ply_file, len(ct.vertices), len(ct.V)/3)
            for v in ct.vertices.values():
                ply_file.write(' '.join(['%f' % i for i in v]) + '\n')

            for c_id in xrange(0, len(ct.V), 3):
                cn = ct.next_corner(c_id)
                cp = ct.previous_corner(c_id)
                ply_file.write('3 %d %d %d\n' % (ct.V[c_id], ct.V[cn], ct.V[cp]))

    def from_faces_vertices_list(self, faces, vertices, colours=None):
        with file(self.filename, 'w') as ply_file:
            self._write_header(ply_file, len(vertices), len(faces),
                               colours is not None)
            for k, v in vertices.items():
                if colours is not None:
                    ply_file.write((' '.join(['%f' % i for i in v[:3]])).replace('.', ','))
                    try:
                        ply_file.write(' %d %d %d 255\n' % colours[k])
                    except KeyError:
                        ply_file.write(' %d %d %d 255\n' % (0, 0, 0))
                else:
                    ply_file.write((' '.join(['%f' % i for i in v[:3]]) +
                                    '\n').replace('.', ','))

            for vx, vy, vz in faces:
                ply_file.write('3 %d %d %d\n' % (vx, vy, vz))
