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
clustered_porosity_module = import_module('.clustered-porosity-mask-generator', package=__name__)
lof_module = import_module('.lack-of-fusion-mask-generator', package=__name__)
lop_module = import_module('.lack-of-penetration-mask-generator', package=__name__)
loswf_module = import_module('.lack-of-side-wall-fusion-mask-generator', package=__name__)
slag_module = import_module('.slag-inclusion-mask-generator', package=__name__)
linear_slag_module = import_module('.linear-slag-inclusion-mask-generator', package=__name__)
metallic_module = import_module('.metallic-inclusion-mask-generator', package=__name__)
undercut_module = import_module('.undercut-mask-generator', package=__name__)
linear_porosity_module = import_module('.linear-porosity-mask-generator', package=__name__)
elongated_cavity_module = import_module('.elongated-cavity-mask-generator', package=__name__)
feathering_module = import_module('.feathering-utility', package=__name__)
roi_module = import_module('.weld-roi-constraint', package=__name__)

DefectMaskGenerator = base_module.DefectMaskGenerator
CrackMaskGenerator = crack_module.CrackMaskGenerator
PorosityMaskGenerator = porosity_module.PorosityMaskGenerator
ClusteredPorosityMaskGenerator = clustered_porosity_module.ClusteredPorosityMaskGenerator
LackOfFusionMaskGenerator = lof_module.LackOfFusionMaskGenerator
LackOfPenetrationMaskGenerator = lop_module.LackOfPenetrationMaskGenerator
LackOfSideWallFusionMaskGenerator = loswf_module.LackOfSideWallFusionMaskGenerator
SlagInclusionMaskGenerator = slag_module.SlagInclusionMaskGenerator
LinearSlagInclusionMaskGenerator = linear_slag_module.LinearSlagInclusionMaskGenerator
MetallicInclusionMaskGenerator = metallic_module.MetallicInclusionMaskGenerator
UndercutMaskGenerator = undercut_module.UndercutMaskGenerator
LinearPorosityMaskGenerator = linear_porosity_module.LinearPorosityMaskGenerator
ElongatedCavityMaskGenerator = elongated_cavity_module.ElongatedCavityMaskGenerator
feather_mask = feathering_module.feather_mask
dilate_mask_for_inpainting = feathering_module.dilate_mask_for_inpainting
create_weld_roi_mask = roi_module.create_weld_roi_mask
apply_weld_roi = roi_module.apply_weld_roi

__all__ = [
    'DefectMaskGenerator',
    'CrackMaskGenerator',
    'PorosityMaskGenerator',
    'ClusteredPorosityMaskGenerator',
    'LackOfFusionMaskGenerator',
    'LackOfPenetrationMaskGenerator',
    'LackOfSideWallFusionMaskGenerator',
    'SlagInclusionMaskGenerator',
    'LinearSlagInclusionMaskGenerator',
    'MetallicInclusionMaskGenerator',
    'UndercutMaskGenerator',
    'LinearPorosityMaskGenerator',
    'ElongatedCavityMaskGenerator',
    'feather_mask',
    'dilate_mask_for_inpainting',
    'create_weld_roi_mask',
    'apply_weld_roi',
]
