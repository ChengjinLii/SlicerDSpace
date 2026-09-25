cmake_minimum_required(VERSION 3.20.6...3.22.6 FATAL_ERROR)

project(SlicerDDSurfer)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://github.com/ChengjinLii/SlicerDDSurfer")
set(EXTENSION_CATEGORY "Diffusion")
set(EXTENSION_CONTRIBUTORS "Chengjin Li")
set(EXTENSION_DESCRIPTION "Integrated diffusion MRI workflows for anatomical reconstruction, tractography, bundle analysis, and structural connectivity.")
set(EXTENSION_ICONURL "https://raw.githubusercontent.com/ChengjinLii/SlicerDDSurfer/main/Resources/Icons/SlicerDDSurfer.png")
set(EXTENSION_SCREENSHOTURLS "")
set(EXTENSION_DEPENDS SlicerDMRI PyTorch)

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
set(MODULE_NAME SlicerDDSurfer)

#-----------------------------------------------------------------------------
file(GLOB_RECURSE SHARED_PYTHON_SCRIPTS "shared/*.py")
file(GLOB_RECURSE PREPROCESSING_PYTHON_SCRIPTS "preprocessing/*.py")
file(GLOB_RECURSE SURFACE_PYTHON_SCRIPTS "surface/*.py")
file(GLOB_RECURSE PARCELLATION_PYTHON_SCRIPTS "parcellation/*.py")
list(FILTER PARCELLATION_PYTHON_SCRIPTS EXCLUDE REGEX "/tests/")
file(GLOB_RECURSE SEGMENTATION_PYTHON_SCRIPTS "segmentation/*.py")
file(GLOB_RECURSE MICROSTRUCTURE_PYTHON_SCRIPTS "microstructure/*.py")
file(GLOB_RECURSE TRACTOGRAPHY_PYTHON_SCRIPTS "tractography/*.py")
# Local copies used only to study SlicerDMRI APIs are deliberately not runtime
# resources.  Keep this filter next to the glob so a normal Slicer extension
# build cannot install the reference modules as accidental scripted modules.
list(FILTER TRACTOGRAPHY_PYTHON_SCRIPTS EXCLUDE REGEX "/slicer_dmri_reference/")
file(GLOB_RECURSE CONNECTOME_PYTHON_SCRIPTS "connectome/*.py")
file(GLOB_RECURSE SCRIPT_TOOL_FILES "scripts/*.py" "scripts/*.sh" "scripts/*.ps1")
file(GLOB_RECURSE DOC_FILES "docs/*.md")
file(GLOB_RECURSE DDSURFER_POSTPROCESS_RELEASE_FILES
  "surface/ddsurfer_postprocess_release/*.md"
  "surface/ddsurfer_postprocess_release/*.sh"
  "surface/ddsurfer_postprocess_release/config/*"
  "surface/ddsurfer_postprocess_release/scripts/*"
  )
# Third-party license/notice files that must travel with the bundled code
# they cover (see THIRD_PARTY_NOTICES.md); these are not *.py and were
# previously never packaged even though the code itself was.
file(GLOB LICENSE_FILES "licenses/*")

set(MODULE_PYTHON_SCRIPTS
  ${MODULE_NAME}.py
  )

set(MODULE_PYTHON_RESOURCES
  ${DOC_FILES}
  ${SHARED_PYTHON_SCRIPTS}
  ${PREPROCESSING_PYTHON_SCRIPTS}
  ${SURFACE_PYTHON_SCRIPTS}
  ${PARCELLATION_PYTHON_SCRIPTS}
  ${SEGMENTATION_PYTHON_SCRIPTS}
  ${MICROSTRUCTURE_PYTHON_SCRIPTS}
  ${TRACTOGRAPHY_PYTHON_SCRIPTS}
  ${CONNECTOME_PYTHON_SCRIPTS}
  ${SCRIPT_TOOL_FILES}
  ${DDSURFER_POSTPROCESS_RELEASE_FILES}
  ${LICENSE_FILES}
  models/assets_manifest.json
  Resources/Icons/${MODULE_NAME}.png
  Resources/UI/${MODULE_NAME}.ui
  parcellation/conversion/data/FreeSurferColorLUT.txt
  tractography/saf_backend/LICENSE.md
  LICENSE
  THIRD_PARTY_NOTICES.md
  )

#-----------------------------------------------------------------------------
slicerMacroBuildScriptedModule(
  NAME ${MODULE_NAME}
  SCRIPTS ${MODULE_PYTHON_SCRIPTS}
  RESOURCES ${MODULE_PYTHON_RESOURCES}
  WITH_GENERIC_TESTS
  )

#-----------------------------------------------------------------------------
if(BUILD_TESTING)

  # Register the unittest subclass in the main script as a ctest.
  # Note that the test will also be available at runtime.
  slicer_add_python_unittest(SCRIPT ${MODULE_NAME}.py)

  # Additional build-time testing
  add_subdirectory(Testing)
endif()

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_CPACK})
