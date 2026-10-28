"""Legacy source-import alias; new installations expose SlicerDSpace."""

from SlicerDSpace import (
    SlicerDSpace,
    SlicerDSpaceWidget,
    SlicerDSpaceLogic,
    SlicerDSpaceParameterNode,
    SlicerDSpaceTest,
)


class SlicerDDSurfer(SlicerDSpace):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent.hidden = True


SlicerDDSurferWidget = SlicerDSpaceWidget
SlicerDDSurferLogic = SlicerDSpaceLogic
SlicerDDSurferParameterNode = SlicerDSpaceParameterNode
SlicerDDSurferTest = SlicerDSpaceTest
