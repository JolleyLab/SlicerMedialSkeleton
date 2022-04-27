cmake_minimum_required(VERSION 3.16.3...3.19.7 FATAL_ERROR)

project(MedialSkeleton)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://github.com/JolleyLab/MedialSkeleton")
set(EXTENSION_CATEGORY "Skeletonization")
set(EXTENSION_CONTRIBUTORS "Paul Yushkevich (PICSL/UPenn), Alison Pouch (PICSL/UPenn), Matthew Jolley (CHOP/UPenn), Christian Herz (CHOP), Andras Lasso (PerkLab, Queen's University)")
set(EXTENSION_DESCRIPTION "Modules for creating medial skeletons")
set(EXTENSION_ICONURL "http://www.example.com/Slicer/Extensions/MedialSkeleton.png")
set(EXTENSION_SCREENSHOTURLS "https://raw.githubusercontent.com/JolleyLab/MedialSkeleton/master/SyntheticSkeleton/Resources/Screenshots/SyntheticSkeleton01.png")
set(EXTENSION_DEPENDS "NA") # Specified as a list or "NA" if no dependencies
set(EXTENSION_BUILD_SUBDIRECTORY inner-build)

set(SUPERBUILD_TOPLEVEL_PROJECT inner)

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})
mark_as_superbuild(Slicer_DIR)

find_package(Git REQUIRED)
mark_as_superbuild(GIT_EXECUTABLE)

#-----------------------------------------------------------------------------
# SuperBuild setup
option(${EXTENSION_NAME}_SUPERBUILD "Build ${EXTENSION_NAME} and the projects it depends on." ON)
mark_as_advanced(${EXTENSION_NAME}_SUPERBUILD)
if(${EXTENSION_NAME}_SUPERBUILD)
  include("${CMAKE_CURRENT_SOURCE_DIR}/SuperBuild.cmake")
  return()
endif()

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(SkeletonTool)
add_subdirectory(SyntheticSkeleton)
add_subdirectory(InflateMedialModel)

#-----------------------------------------------------------------------------
set(EXTENSION_CPACK_INSTALL_CMAKE_PROJECTS)
set(${EXTENSION_NAME}_CPACK_INSTALL_CMAKE_PROJECTS "${EXTENSION_CPACK_INSTALL_CMAKE_PROJECTS}" CACHE STRING "List of external projects to install" FORCE)

#-----------------------------------------------------------------------------
list(APPEND CPACK_INSTALL_CMAKE_PROJECTS "${CMAKE_BINARY_DIR};${EXTENSION_NAME};ALL;/")
list(APPEND CPACK_INSTALL_CMAKE_PROJECTS "${${EXTENSION_NAME}_CPACK_INSTALL_CMAKE_PROJECTS}")
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
