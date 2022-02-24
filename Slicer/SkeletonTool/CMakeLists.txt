
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

### qhullstatic reentrant library
add_library(libqhullstatic_r STATIC IMPORTED)
set_property(TARGET libqhullstatic_r PROPERTY IMPORTED_LOCATION ${CMAKE_BINARY_DIR}/qhull-build/${CMAKE_STATIC_LIBRARY_PREFIX}qhullstatic_r${CMAKE_STATIC_LIBRARY_SUFFIX})
add_dependencies(libqhullstatic_r qhull)
### qhullcpp library
add_library(libqhullcpp STATIC IMPORTED)
set_property(TARGET libqhullcpp PROPERTY IMPORTED_LOCATION ${CMAKE_BINARY_DIR}/qhull-build/${CMAKE_STATIC_LIBRARY_PREFIX}qhullcpp${CMAKE_STATIC_LIBRARY_SUFFIX})
set_property(TARGET libqhullcpp PROPERTY INTERFACE_LINK_LIBRARIES libqhullstatic_r)
add_dependencies(libqhullcpp qhull)

include_directories(${CMAKE_BINARY_DIR}/qhull-install/include/)

set(CMREP_DIR ${CMAKE_SOURCE_DIR}/submodules/cmrep)

#-----------------------------------------------------------------------------
set(MODULE_SRCS
  SkeletonTool.cxx
  ${CMREP_DIR}/src/dijkstra/VTKMeshShortestDistance.cxx
  ${CMREP_DIR}/src/dijkstra/ShortestPath.cxx
  )

set(MODULE_TARGET_LIBRARIES
  ${ITK_LIBRARIES}
  ${VTK_LIBRARIES}
  )

#-----------------------------------------------------------------------------
SEMMacroBuildCLI(
  NAME ${MODULE_NAME}
  ADDITIONAL_SRCS ${MODULE_SRCS}
  TARGET_LIBRARIES ModuleDescriptionParser ${ITK_LIBRARIES} vtkTeem MRMLCore ${VTK_LIBRARIES} libqhullstatic_r libqhullcpp
  INCLUDE_DIRECTORIES
    ${CMREP_DIR}/src/dijkstra
    ${vtkTeem_INCLUDE_DIRS}
    ${MRMLCore_INCLUDE_DIRS}
    ${vtkITK_INCLUDE_DIRS}
    ${SlicerBaseCLI_SOURCE_DIR}
    ${SlicerBaseCLI_BINARY_DIR}
)