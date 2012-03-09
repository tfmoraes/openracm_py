import glob
import os
import sys
import vtk

def test_connectivity(pd):
    conn = vtk.vtkPolyDataConnectivityFilter()
    conn.SetInput(pd)
    conn.SetExtractionModeToAllRegions()
    conn.Update()

    return conn.GetNumberOfExtractedRegions()

def main():
    files = glob.glob(os.path.join(sys.argv[1], '*'))
    
    for f in sorted(files):
        ply_reader = vtk.vtkPLYReader()
        ply_reader.SetFileName(f)
        ply_reader.Update()

        nc = test_connectivity(ply_reader.GetOutput())
        print f, nc

if __name__ == '__main__':
    main()
