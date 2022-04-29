
#-----------------------------------------------------------------------------
set(MODULE_NAME SkeletonTool)
#-----------------------------------------------------------------------------

#
# SlicerExecutionModel
#
find_package(SlicerExecutionModel REQUIRED)
include(${SlicerExecutionModel_USE_FILE})

find_package(VTK REQUIRED)

find_package(Qhull REQUIRED)

include_directories(${CMREP_SOURCE_DIR}/src/dijkstra)

#-----------------------------------------------------------------------------
set(MODULE_SRCS
  SkeletonTool.cxx
  dijkstra/VTKMeshShortestDistance.cxx
  )

set(MODULE_TARGET_LIBRARIES
  ${ITK_LIBRARIES}
  ${VTK_LIBRARIES}
  )

#-----------------------------------------------------------------------------
SEMMacroBuildCLI(
  NAME ${MODULE_NAME}
  ADDITIONAL_SRCS ${MODULE_SRCS}
  TARGET_LIBRARIES
    ModuleDescriptionParser
    ${ITK_LIBRARIES}
    vtkTeem
    MRMLCore
    ${VTK_LIBRARIES}
    Qhull::qhullstatic_r
    Qhull::qhullcpp
  INCLUDE_DIRECTORIES
    dijkstra
    ${vtkTeem_INCLUDE_DIRS}
    ${MRMLCore_INCLUDE_DIRS}
    ${vtkITK_INCLUDE_DIRS}
    ${SlicerBaseCLI_SOURCE_DIR}
    ${SlicerBaseCLI_BINARY_DIR}
)
