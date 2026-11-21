"""Where the pages read the cameras and the detection from: the camera
manager and the detection pipeline on the office PC. The cloud copy has no
cameras of its own: there the pages read what the office PC sent
(core/cloud.py)."""

from officeeye.core import cloud
from officeeye.services.cameras import manager
from officeeye.services.detection import pipeline

if cloud.CLOUD:
    manager, pipeline = cloud.ManagerView(), cloud.PipelineView()
