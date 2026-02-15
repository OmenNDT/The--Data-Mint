"""
Mask Generator Module

Procedural binary mask generators for weld defect types.
Each generator produces:
  - Sharp binary mask (ground truth annotation)
  - Feathered mask (inpainting input for seamless blending)
"""

from importlib import import_module

# Import from kebab-case filenames (Python converts to module names)
base_module = import_module('.base-defect-mask-generator', package=__name__)
crack_module = import_module('.crack-mask-generator', package=__name__)
porosity_module = import_module('.porosity-mask-generator', package=__name__)
lof_module = import_module('.lack-of-fusion-mask-generator', package=__name__)
slag_module = import_module('.slag-inclusion-mask-generator', package=__name__)
undercut_module = import_module('.undercut-mask-generator', package=__name__)
feathering_module = import_module('.feathering-utility', package=__name__)
roi_module = import_module('.weld-roi-constraint', package=__name__)

DefectMaskGenerator = base_module.DefectMaskGenerator
CrackMaskGenerator = crack_module.CrackMaskGenerator
PorosityMaskGenerator = porosity_module.PorosityMaskGenerator
LackOfFusionMaskGenerator = lof_module.LackOfFusionMaskGenerator
SlagInclusionMaskGenerator = slag_module.SlagInclusionMaskGenerator
UndercutMaskGenerator = undercut_module.UndercutMaskGenerator
feather_mask = feathering_module.feather_mask
create_weld_roi_mask = roi_module.create_weld_roi_mask
apply_weld_roi = roi_module.apply_weld_roi

__all__ = [
    'DefectMaskGenerator',
    'CrackMaskGenerator',
    'PorosityMaskGenerator',
    'LackOfFusionMaskGenerator',
    'SlagInclusionMaskGenerator',
    'UndercutMaskGenerator',
    'feather_mask',
    'create_weld_roi_mask',
    'apply_weld_roi',
]
