
#-----------------------------------------------------------------------------
set(MODULE_NAME InflateMedialModel)
#-----------------------------------------------------------------------------

#
# SlicerExecutionModel
#
find_package(SlicerExecutionModel REQUIRED)
include(${SlicerExecutionModel_USE_FILE})

find_package(VTK REQUIRED)
include(${VTK_USE_FILE})

set(CMREP_SOURCE_DIR ${CMAKE_BINARY_DIR}/../cmrep)
include_directories(${CMREP_SOURCE_DIR}/src)

#-----------------------------------------------------------------------------
set(MODULE_SRCS
  InflateMedialModel.cxx
  ${CMREP_SOURCE_DIR}/src/MeshTraversal.h
  ${CMREP_SOURCE_DIR}/src/MedialException.h
  ${CMREP_SOURCE_DIR}/src/SparseMatrix.h
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
  INCLUDE_DIRECTORIES
    ${CMREP_DIR}/src/dijkstra
    ${vtkTeem_INCLUDE_DIRS}
    ${MRMLCore_INCLUDE_DIRS}
    ${vtkITK_INCLUDE_DIRS}
    ${SlicerBaseCLI_SOURCE_DIR}
    ${SlicerBaseCLI_BINARY_DIR}
)

#add_dependencies(${MODULE_NAME} cmrep)
