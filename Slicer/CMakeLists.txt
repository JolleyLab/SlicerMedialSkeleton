cmake_minimum_required(VERSION 2.8.9)

project(PICSLTools)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "")
set(EXTENSION_CATEGORY "Image Computing")
set(EXTENSION_CONTRIBUTORS "Nicolas Vergnat (PICSL), Christian Herz (CHOP), Andras Lasso (PerkLab, Queen's), Matthew Jolley (CHOP/UPenn), Paul Yushkevich (PICSL), Alison Pouch (PICSL)")
set(EXTENSION_DESCRIPTION "Developments for cmrep")
set(EXTENSION_ICONURL "")
set(EXTENSION_SCREENSHOTURLS "")
set(EXTENSION_WC_REVISION "100")
set(PICSLTools_WC_REVISION "100")


#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

mark_as_superbuild(Slicer_DIR)

find_package(Git REQUIRED)
mark_as_superbuild(GIT_EXECUTABLE)

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(SkeletonTool)
## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_CPACK})