# SlicerCMRep 3D Slicer extension

This extension provides Continuous Medial Representation (CM-Rep) related developments. Further information can be found
on https://github.com/pyushkevich/cmrep

## Modules

### SkeletonTool

Creation of a Voronoi skeleton with additional cleaning (pruning) of hanging triangles (spikes) of the resulting skeleton.

### Synthetic Skeleton

Creation of a synthetic skeleton (a medial template) in preparation to run cm-rep for fitting a medial surface to image data.


### InflateMedialModel

Creation of an inflated model from a skeleton.


# Skeletonize GUI standalone application (SkelGUIStandalone)

Compilation instruction:
- VTK > 8.0 
- ITK > 4.0 
- Qt4 or Qt5 (Qt5 is recommended)
- CMake 
- MacOS, Linux or Windows (Visual Studio 11+)