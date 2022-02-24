cmake_minimum_required(VERSION 2.8)

option(USE_QT4 "Chosse between Qt4 and Qt5" OFF)

SET(CXXS
    AddLabelDialog.cxx
    AddTagDialog.cxx
    EventQtSlotConnect.cxx
    EventQtSlotConnectDriver.cxx
    global.cxx
    importNiftiiWindow.cxx
    MouseInteractor.cxx
    PreviewWindow.cxx
    ShortestPath.cxx
    SparseMatrix.cxx
    ToggleTriLabel.cxx
    VoronoiSkeletonTool.cxx
    VTKMeshShortestDistance.cxx
)

SET(MOC_HDRS
    AddLabelDialog.h
    AddTagDialog.h
    BinaryHeap.h
    EventQtSlotConnect.h
    global.h
    importNiftiiWindow.h
    itk_to_nifti_xform.h
    itkOrientedRASImage.h
    MouseInteractor.h
    PreviewWindow.h
    ShortestPath.h
    SparseMatrix.h
    ToggleTriLabel.h
    VoronoiSkeletonTool.h
    VTKMeshHalfEdgeWrapper.h
    VTKMeshShortestDistance.h
)

SET(UIS
    EventQtSlotConnect.ui
    PreviewWindow.ui
)

SET( BUNDLE_NAME EventQtSlotConnect )

IF (WIN32)
    SET (QT_USE_QTMAIN TRUE)
ENDIF (WIN32)

find_package(VTK REQUIRED)
include(${VTK_USE_FILE})

find_package(ITK REQUIRED)
include(${ITK_USE_FILE})

if(NOT USE_QT4)
  find_package(Qt5 COMPONENTS Core Widgets Concurrent Gui Sql REQUIRED)
else(NOT USE_QT4)
  find_package(Qt4 REQUIRED)
  include(${QT_USE_FILE})
endif(NOT USE_QT4)

if (NOT USE_QT4)
	QT5_WRAP_UI(UISrcs ${UIS})
	QT5_WRAP_CPP(MOCSrcs ${MOC_HDRS})
else (NOT USE_QT4)
	QT4_WRAP_UI(UISrcs ${UIS})
	QT4_WRAP_CPP(MOCSrcs ${MOC_HDRS})
endif (NOT USE_QT4)

include_directories(${CMAKE_CURRENT_SOURCE_DIR} ${CMAKE_CURRENT_BINARY_DIR}) 

IF(NOT APPLE)
	add_executable(${BUNDLE_NAME} WIN32 
		${CXXS} 
		${UISrcs} 
		${MOCSrcs} 
	)
ELSE(NOT APPLE)
	add_executable(${BUNDLE_NAME} MACOSX_BUNDLE 
		${CXXS} 
		${UISrcs} 
		${MOCSrcs} 
	)
ENDIF(NOT APPLE)

target_link_libraries(${BUNDLE_NAME} ${VTK_LIBRARIES})
target_link_libraries(${BUNDLE_NAME} ${ITK_LIBRARIES})

if (NOT USE_QT4)
	TARGET_LINK_LIBRARIES ( ${BUNDLE_NAME}  Qt5::Widgets )
	TARGET_LINK_LIBRARIES ( ${BUNDLE_NAME}  Qt5::Concurrent )
	TARGET_LINK_LIBRARIES ( ${BUNDLE_NAME}  Qt5::Core )
	TARGET_LINK_LIBRARIES ( ${BUNDLE_NAME}  Qt5::Gui )
else (NOT USE_QT4)
	TARGET_LINK_LIBRARIES ( ${BUNDLE_NAME}  ${QT_LIBRARIES} )
endif (NOT USE_QT4)

#--------------------------------------------------------------------------------
# Now the installation
#--------------------------------------------------------------------------------
SET(plugin_dest_dir bin)
SET(qtconf_dest_dir bin)
SET(APPS "\${CMAKE_INSTALL_PREFIX}/bin/${BUNDLE_NAME}")
IF(APPLE)
  SET(macprefix "${BUNDLE_NAME}.app/Contents")
  SET(plugin_dest_dir ${macprefix}/MacOS)
  SET(qtconf_dest_dir ${macprefix}/Resources)
  SET(APPS "\${CMAKE_INSTALL_PREFIX}/${BUNDLE_NAME}.app")
ENDIF(APPLE)
IF(WIN32)
  SET(APPS "\${CMAKE_INSTALL_PREFIX}/bin/${BUNDLE_NAME}.exe")
ENDIF(WIN32)

# based on code from CMake's QtDialog/CMakeLists.txt
macro(install_qt5_plugin _qt_plugin_name _qt_plugins_var _prefix)
    get_target_property(_qt_plugin_path "${_qt_plugin_name}" LOCATION)
    if(EXISTS "${_qt_plugin_path}")
        get_filename_component(_qt_plugin_file "${_qt_plugin_path}" NAME)
        get_filename_component(_qt_plugin_type "${_qt_plugin_path}" PATH)
        get_filename_component(_qt_plugin_type "${_qt_plugin_type}" NAME)
        set(_qt_plugin_dest "${_prefix}/PlugIns/${_qt_plugin_type}")
        install(FILES "${_qt_plugin_path}"
            DESTINATION "${_qt_plugin_dest}")
        set(${_qt_plugins_var}
            "${${_qt_plugins_var}};\${CMAKE_INSTALL_PREFIX}/${_qt_plugin_dest}/${_qt_plugin_file}")
    else()
        message(FATAL_ERROR "QT plugin ${_qt_plugin_name} not found")
    endif()
endmacro()

foreach(plugin ${Qt5Widgets_PLUGINS})
	if(NOT APPLE)
		install_qt5_plugin("${plugin}" QT_PLUGINS ${plugin_dest_dir})
	else(NOT APPLE)
		install_qt5_plugin("${plugin}" QT_PLUGINS ${macprefix})
	endif(NOT APPLE)
endforeach()
foreach(plugin ${Qt5Gui_PLUGINS})
	if(NOT APPLE)
		install_qt5_plugin("${plugin}" QT_PLUGINS ${plugin_dest_dir})
	else(NOT APPLE)
		install_qt5_plugin("${plugin}" QT_PLUGINS ${macprefix})
	endif(NOT APPLE)
endforeach()

#--------------------------------------------------------------------------------
# Install the QtTest application, on Apple, the bundle is at the root of the
# install tree, and on other platforms it'll go into the bin directory.
if(NOT APPLE)
	INSTALL(TARGETS ${BUNDLE_NAME} 
		BUNDLE DESTINATION . COMPONENT Runtime
    	RUNTIME DESTINATION ${qtconf_dest_dir} COMPONENT Runtime
    	)
else(NOT APPLE)
	INSTALL(TARGETS ${BUNDLE_NAME} 
		BUNDLE DESTINATION . COMPONENT Runtime
    	RUNTIME DESTINATION ${plugin_dest_dir} COMPONENT Runtime
    	)
endif(NOT APPLE)

#--------------------------------------------------------------------------------
# Install needed Qt plugins by copying directories from the qt installation
# One can cull what gets copied by using 'REGEX "..." EXCLUDE'

if(WIN32)
	SET(VITK_DIR "/bin/Release")
else(WIN32)
	SET(VITK_DIR "/lib")
endif(WIN32)

#--------------------------------------------------------------------------------
# install a qt.conf file
# this inserts some cmake code into the install script to write the file
INSTALL(CODE "
    file(WRITE \"\${CMAKE_INSTALL_PREFIX}/${qtconf_dest_dir}/qt.conf\" 
	\"[Paths]\nPlugins = PlugIns\n\")
    " COMPONENT Runtime)


#--------------------------------------------------------------------------------
# Use BundleUtilities to get all other dependencies for the application to work.
# It takes a bundle or executable along with possible plugins and inspects it
# for dependencies.  If they are not system dependencies, they are copied.
# directories to look for dependencies

set(DIRS "${CMAKE_BINARY_DIR}")

if(NOT WIN32)
	get_filename_component(QT_LIB "${Qt5Widgets_DIR}/../.." ABSOLUTE)
	list(APPEND DIRS ${QT_LIB})
	get_filename_component(VTK_LIB "${VTK_DIR}/${VITK_DIR}" ABSOLUTE)
	list(APPEND DIRS ${VTK_LIB})
	get_filename_component(ITK_LIB "${ITK_DIR}/${VITK_DIR}" ABSOLUTE)
	list(APPEND DIRS ${ITK_LIB})
else(NOT WIN32)
	get_filename_component(QT_LIB "${Qt5Widgets_DIR}/../../../bin" ABSOLUTE)
	list(APPEND DIRS ${QT_LIB})
	get_filename_component(VTK_LIB "${VTK_DIR}/${VITK_DIR}" ABSOLUTE)
	list(APPEND DIRS ${VTK_LIB})
	get_filename_component(ITK_LIB "${ITK_DIR}/${VITK_DIR}" ABSOLUTE)
	list(APPEND DIRS ${ITK_LIB})
endif(NOT WIN32)

# Now the work of copying dependencies into the bundle/package
# The quotes are escaped and variables to use at install time have their $ escaped
# An alternative is the do a configure_file() on a script and use install(SCRIPT  ...).
# Note that the image plugins depend on QtSvg and QtXml, and it got those copied
# over.

include(InstallRequiredSystemLibraries)

message(STATUS "APPS: ${APPS}")
message(STATUS "QT_PLUGINS: ${QT_PLUGINS}")
message(STATUS "DIRS: ${DIRS}")

install(CODE "
	include(BundleUtilities)
    fixup_bundle(\"${APPS}\" \"${QT_PLUGINS}\" \"${DIRS}\")
	" COMPONENT Runtime)

#-----------------------------------------------------------------------------------
# CPack information

IF(APPLE)
	set(CPACK_BINARY_DRAGNDROP ON)
ENDIF(APPLE)
IF(UNIX)
	set(CPACK_GENERATOR TGZ)
ENDIF(UNIX)
set(CPACK_PACKAGE_NAME "${BUNDLE_NAME}")
set(CPACK_PACKAGE_VENDOR "Tian Sijie, Nicolas Vergnet")
set(CPACK_PACKAGE_VERSION_MAJOR "1")
set(CPACK_PACKAGE_VERSION_MINOR "0")
set(CPACK_PACKAGE_VERSION_PATCH "0")
set(CPACK_PACKAGE_VERSION "${CPACK_PACKAGE_VERSION_MAJOR}.${CPACK_PACKAGE_VERSION_MINOR}.${CPACK_PACKAGE_VERSION_PATCH}")
set(CPACK_PACKAGE_INSTALL_DIRECTORY "${BUNDLE_NAME}")

include(CPack)
