
#-----------------------------------------------------------------------------
set(MODULE_NAME SkeletonTool)
#-----------------------------------------------------------------------------

#
# SlicerExecutionModel
#
find_package(SlicerExecutionModel REQUIRED)
include(${SlicerExecutionModel_USE_FILE})

find_package(VTK REQUIRED)
include(${VTK_USE_FILE})

#------ CM-REP ------ #
include(ExternalProject)
ExternalProject_add(cmrep
    GIT_REPOSITORY https://github.com/JolleyLab/cmrep.git
    GIT_TAG b6a509df3ae233eeddb3244fcefae61ca8ab2c98
    GIT_PROGRESS TRUE
    SOURCE_DIR ${CMAKE_BINARY_DIR}/cmrep
    CONFIGURE_COMMAND ""
    BUILD_COMMAND ""
    INSTALL_COMMAND ""
    LOG_DOWNLOAD ON
    )
set(CMREP_DIR ${CMAKE_BINARY_DIR}/cmrep)

#------ QHull ------ #
# https://stackoverflow.com/questions/61093084/how-to-use-qhull-as-an-external-project-in-cmake

include(ExternalProject)
ExternalProject_add(qhull
    GIT_REPOSITORY https://github.com/qhull/qhull.git
    GIT_TAG 2020.2
    GIT_PROGRESS TRUE
    SOURCE_DIR ${CMAKE_BINARY_DIR}/qhull
    BINARY_DIR ${CMAKE_BINARY_DIR}/qhull-build
    CMAKE_ARGS
      -DCMAKE_INSTALL_PREFIX=${CMAKE_BINARY_DIR}/qhull-install
      -DCMAKE_OSX_DEPLOYMENT_TARGET:STRING=${CMAKE_OSX_DEPLOYMENT_TARGET}
    CMAKE_CACHE_ARGS
      -DCMAKE_POSITION_INDEPENDENT_CODE:BOOL=true
    )

set(Qhull_DIR ${CMAKE_BINARY_DIR}/qhull-build/QhullExport)
find_package(Qhull REQUIRED)

include_directories(${CMAKE_BINARY_DIR}/qhull-install/include/)

#-----------------------------------------------------------------------------
set(MODULE_SRCS
  SkeletonTool.cxx
  ${CMREP_DIR}/src/dijkstra/VTKMeshShortestDistance.cxx
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
    ${CMREP_DIR}/src/dijkstra
    ${vtkTeem_INCLUDE_DIRS}
    ${MRMLCore_INCLUDE_DIRS}
    ${vtkITK_INCLUDE_DIRS}
    ${SlicerBaseCLI_SOURCE_DIR}
    ${SlicerBaseCLI_BINARY_DIR}
)

add_dependencies(${MODULE_NAME} cmrep)
