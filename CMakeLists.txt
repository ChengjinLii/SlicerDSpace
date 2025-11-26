#-----------------------------------------------------------------------------
set(MODULE_NAME SlicerDDSurfer)

#-----------------------------------------------------------------------------
set(MODULE_PYTHON_SCRIPTS
  ${MODULE_NAME}.py
  ddspipeline/__init__.py
  ddspipeline/preprocessing.py
  ddspipeline/prediction.py
  ddspipeline/postprocessing.py
  ddspipeline/models/__init__.py
  ddspipeline/models/cmunext_3d.py
  ddspipeline/models/d_lka_attention.py
  ddspipeline/models/dsc_volume_reg.py
  ddspipeline/networks/__init__.py
  ddspipeline/networks/tanet.py
  )

set(MODULE_PYTHON_RESOURCES
  Resources/Icons/${MODULE_NAME}.png
  Resources/UI/${MODULE_NAME}.ui
  Resources/Data/template/100307-FA.nii.gz
  Resources/Data/template/hcp_hemi-left_init_160k.obj
  Resources/Data/template/hcp_hemi-right_init_160k.obj
  Resources/Data/ckpts/hcp/DDCSR_white_lh_Full_DualStream_no_b0_Cascaded.pt
  Resources/Data/ckpts/hcp/DDCSR_white_rh_Full_DualStream_no_b0_Cascaded.pt
  Resources/Data/ckpts/hcp/DDCSR_pial_lh_Full_DualStream_no_b0_Cascaded.pt
  Resources/Data/ckpts/hcp/DDCSR_pial_rh_Full_DualStream_no_b0_Cascaded.pt
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
