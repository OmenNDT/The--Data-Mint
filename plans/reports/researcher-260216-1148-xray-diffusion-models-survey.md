# Research Report: Stable Diffusion Models for X-ray and Medical Imaging

**Date**: 2026-02-16
**Context**: Synthetic weld defect X-ray image generation pipeline
**Current Base**: sd-v1-5-pruned-emaonly.safetensors with LoRA fine-tuning
**Objective**: Identify 4 alternative SD base models for improved X-ray defect image quality

---

## Executive Summary

Research identified medical imaging diffusion models showing significant promise for industrial radiographic applications. RoentGen (Stanford) leads in X-ray synthesis quality. SDXL-based models offer higher resolution but require more compute. Most medical models target chest X-rays but transfer learning to industrial RT is feasible. Key finding: medical domain fine-tuning + ControlNet conditioning provides superior control over defect generation.

---

## Model Recommendations

### 1. RoentGen v2 (Stanford MIMI)
**Architecture**: SD 1.5-based latent diffusion
**Source**: [HuggingFace Collection](https://huggingface.co/collections/stanfordmimi/roentgen-v2-68c1f1dc6e02405ad5a3e018) | [GitHub](https://github.com/StanfordMIMI/RoentGen)

**Description**:
- Vision-language foundation model fine-tuned on MIMIC-CXR dataset (224k+ chest X-rays)
- Text-to-image generation with radiology-specific language understanding
- v2 adds demographic conditioning (age, race, sex)
- Produces high-fidelity grayscale radiographic images with controlled anatomical features

**Pros for Weld Defects**:
- Specialized for X-ray domain → better grayscale/contrast handling
- Text prompt control → natural language defect descriptions
- Proven synthetic data quality (3-5% AUROC improvement in downstream tasks)
- Compatible with SD 1.5 tooling/ControlNet

**Cons**:
- Access restricted to MIMIC-CXR credentialed researchers
- Trained on medical anatomy (not industrial materials/welds)
- Requires transfer learning for defect-specific features

**License**: Research-only (requires MIMIC-CXR access agreement)
**Download**: Credential-gated via [Stanford form](https://stanfordmimi.github.io/RoentGen/)

---

### 2. DoctorDiffusion X-Ray XL LoRA
**Architecture**: SDXL-based LoRA
**Source**: [HuggingFace](https://huggingface.co/DoctorDiffusion/doctor-diffusion-s-xray-xl-lora-0)

**Description**:
- Experimental SDXL LoRA using "xray" trigger word in prompts
- Generates X-ray style images at 1024x1024 native resolution
- Lightweight adapter (LoRA) allows easy integration with base SDXL

**Pros for Weld Defects**:
- Higher resolution (1024x1024 vs 512x512)
- SDXL architecture → better detail preservation (+156% vs SD 1.5)
- LoRA format → fast iteration/combining with custom defect LoRAs
- No credential restrictions

**Cons**:
- Experimental/community model (less validation than RoentGen)
- SDXL requires 2-3x more VRAM (needs 8GB+ vs 4GB for SD 1.5)
- Slower inference (4-6s vs 1-2s on same hardware)
- May need additional fine-tuning for industrial RT aesthetics

**License**: Likely permissive (check HuggingFace model card)
**Download**: Direct from HuggingFace

---

### 3. Osama03 Medical X-Ray Generation (SD 1.5)
**Architecture**: SD 1.5 fine-tuned
**Source**: [HuggingFace](https://huggingface.co/Osama03/Medical-X-ray-image-generation-stable-diffusion)

**Description**:
- SD 1.5 base fine-tuned on medical X-ray dataset
- Text-to-image for radiographic images
- Community-trained model with public access

**Pros for Weld Defects**:
- SD 1.5 compatibility → direct drop-in replacement for current pipeline
- Lower compute requirements (4GB VRAM)
- Fast inference (1-2s)
- Open access (no credential requirements)
- Already optimized for X-ray aesthetic

**Cons**:
- Less documentation than RoentGen
- Unknown training data quality/size
- May require validation for defect realism
- Community model → less research validation

**License**: Check HuggingFace (likely open)
**Download**: Direct from HuggingFace

---

### 4. Chest-Diffusion (Lightweight Text-to-CXR)
**Architecture**: Lightweight SD variant
**Source**: [ArXiv Paper](https://arxiv.org/html/2407.00752v1)

**Description**:
- Light-weight text-to-image model specifically for chest X-ray generation
- Optimized for report-to-CXR synthesis
- Reduced parameters vs full SD models

**Pros for Weld Defects**:
- Designed for resource-constrained environments
- Fast training/inference
- Text-conditioned X-ray generation
- Medical domain expertise

**Cons**:
- Model weights availability unclear (research paper, no clear HF/download link found)
- May need to contact authors for access
- Lighter architecture → potentially lower image quality
- Chest-specific → transfer to industrial may be challenging

**License**: Research (TBD - contact authors)
**Download**: Not publicly available yet (check paper/contact authors)

---

## Alternative/Honorable Mentions

### Prompt2MedImage (ROCO Fine-tuned)
- **Source**: [HuggingFace](https://huggingface.co/Nihirc/Prompt2MedImage)
- SD model fine-tuned on ROCO medical imaging dataset
- Text-to-image for various medical modalities (not X-ray specific)
- Open access but broader domain (less X-ray specialization)

### CivitAI X-Ray Style Models
- **Xray XL LoRA**: [CivitAI](https://civitai.com/models/231655/xray-xl-lora)
- **Detailed X-Ray Style SDXL**: [CivitAI](https://civitai.com/models/599427/detailed-x-ray-style-sdxl)
- Stylistic X-ray effects (transparency/see-through)
- NOT medical/industrial accurate (artistic interpretations)
- Good for aesthetic transfer but poor for defect realism

### Monochrome/Grayscale LoRAs
- **Source**: [Tensor.Art](https://tensor.art/models/637132465619730515)
- Trigger words: "monochrome", "grayscale", "sketch"
- Generic grayscale optimization (not X-ray specific)
- Can complement medical models for improved contrast

---

## Architecture Comparison: SD 1.5 vs SDXL

### SD 1.5
- **Resolution**: 512x512 native
- **Parameters**: 860M
- **VRAM**: 4GB minimum
- **Inference**: 1-2s (consumer GPU)
- **Prompt Adherence**: 71% (baseline)
- **ControlNet Support**: Extensive (many pretrained models)

### SDXL
- **Resolution**: 1024x1024 native
- **Parameters**: 3.5B (base model)
- **VRAM**: 8GB+ recommended
- **Inference**: 4-6s (consumer GPU)
- **Prompt Adherence**: 89% (+25% vs SD 1.5)
- **Detail Preservation**: +156% vs SD 1.5
- **Color Accuracy**: +67% vs SD 1.5
- **ControlNet Support**: Growing (fewer pretrained variants)

**Recommendation for Weld Defects**:
- SD 1.5 for production (proven ControlNet workflows, lower compute)
- SDXL for high-resolution research/validation datasets

---

## ControlNet for Medical/Industrial X-Ray

### Key Research Findings
Recent work demonstrates ControlNet with **segmentation mask conditioning** for X-ray generation:

1. **Mask + Text Dual Conditioning**:
   - Input: Defect segmentation mask + text prompt ("porosity in upper region")
   - Output: Synthetic X-ray with exact defect placement and characteristics
   - [Research](https://arxiv.org/html/2411.18602v1)

2. **Zero-Convolution Architecture**:
   - Adds adapter layers to frozen SD model
   - Trains only control network → preserves base model quality
   - Supports multiple conditioning inputs (mask, depth, edge)

3. **Best Practices for X-Ray**:
   - Single-disease/defect labels per generation (better fidelity)
   - Geometrically-transformed masks (augmentation)
   - Combine with text for fine-grained control

4. **Performance**:
   - Synthetic data improved segmentation F1 from 0.209 to 0.290 (CheXpert, 1% ground truth)
   - [Source](https://arxiv.org/html/2411.18602v1)

**Application to Weld Pipeline**:
- Current ControlNet setup compatible with recommended models
- Consider mask-guided generation for precise defect placement
- Text prompts for defect type/severity control

---

## Industrial NDT/Radiographic Research

### Synthetic Defect Generation Techniques

1. **CAD-Based Simulation**:
   - Generate 3D models of pores/voids → simulate X-ray projections
   - Combine real + synthetic → 87% accuracy (segmentation)
   - [Source](https://www.nature.com/articles/s41598-024-56794-9)

2. **GAN-Based Methods (Pre-Diffusion)**:
   - CycleGAN-ES for defect image synthesis
   - DA-DCGAN with attention for imbalanced datasets
   - Diffusion models now **superior to GANs** for industrial defects (+10% accuracy)
   - [Source](https://www.mdpi.com/1424-8220/25/10/3038)

3. **Latent Diffusion for Steel Defects**:
   - SD fine-tuning with LoRA for steel surface defects
   - Mask-guided defect learning mechanisms
   - 10% improvement in continuous casting billet recognition
   - [Source](https://www.mdpi.com/1424-8220/24/18/6016)

4. **Few-Shot Defect Generation**:
   - Diffusion models effective with limited defect samples
   - Probabilistic denoising → better diversity than GANs
   - [Source](https://www.mdpi.com/1424-8220/25/10/3038)

**Key Insight**: Industrial defect research validates diffusion superiority over GANs, but **medical X-ray models have better base quality** → transfer learning from medical to industrial recommended.

---

## Academic Papers (2024-2026)

### Medical X-Ray Synthesis
1. **"A vision–language foundation model for the generation of realistic chest X-ray images"** (2024)
   - RoentGen publication in Nature Biomedical Engineering
   - [Paper](https://www.nature.com/articles/s41551-024-01246-y)

2. **"Evaluating and Improving the Effectiveness of Synthetic Chest X-Rays"** (2024)
   - ControlNet with mask conditioning
   - F1 score improvements with synthetic data
   - [ArXiv](https://arxiv.org/html/2411.18602v1)

3. **"Chest-Diffusion: A Light-Weight Text-to-Image Model"** (2024)
   - Resource-efficient CXR generation
   - [ArXiv](https://arxiv.org/html/2407.00752v1)

### Industrial/Radiographic
4. **"A Few-Shot Steel Surface Defect Generation Method Based on Diffusion Models"** (2024)
   - Diffusion vs GAN comparison
   - Few-shot learning for defects
   - [MDPI Sensors](https://www.mdpi.com/1424-8220/25/10/3038)

5. **"Latent Diffusion Models to Enhance Visual Defect Segmentation in Steel"** (2024)
   - LoRA fine-tuning for industrial inspection
   - [MDPI Sensors](https://www.mdpi.com/1424-8220/24/18/6016)

6. **"Structured Guided Diffusion Models for Industrial Defect Generation"** (2025)
   - Mask-guided learning for defects
   - [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0950705125016818)

### Comprehensive Surveys
7. **"Diffusion Models in Medical Imaging"** (2023, updated 2025)
   - Survey of diffusion for medical imaging (Jan 2021-2025)
   - [GitHub Collection](https://github.com/amirhossein-kz/Awesome-Diffusion-Models-in-Medical-Imaging)
   - [Medical Image Analysis Journal](https://www.sciencedirect.com/science/article/abs/pii/S1361841523001068)

---

## License Considerations

### Commercial Use Compatibility

1. **SD 1.5 Base (OpenRAIL-M)**:
   - Permissive for commercial use
   - Prohibits medical advice (fine-tuning for industrial use OK)
   - [License](https://github.com/CompVis/stable-diffusion/blob/main/LICENSE)

2. **SDXL (Tiered Licensing)**:
   - Community License: <$1M revenue (free)
   - Creator License: $20/mo (<$1M revenue)
   - Enterprise: >$1M revenue (custom pricing)
   - [Stability AI License](https://stability.ai/license)

3. **RoentGen**:
   - Research-only (MIMIC-CXR access agreement)
   - NOT commercial without permission

4. **Community Models (HF/CivitAI)**:
   - Check individual model cards
   - Most use base SD license (commercial OK)
   - Medical fine-tunes may have data restrictions

**Recommendation**: For commercial weld inspection product:
- Use SD 1.5 base or community models with permissive licenses
- Avoid RoentGen without Stanford permission
- SDXL requires paid license for revenue >$1M

---

## Implementation Recommendations

### Short-Term (Immediate Improvements)
1. **Try DoctorDiffusion X-Ray XL LoRA**:
   - Drop-in LoRA for current SDXL pipeline (if using)
   - Test higher resolution defect generation
   - Compare against SD 1.5 baseline

2. **Test Osama03 Medical X-Ray SD 1.5**:
   - Direct replacement for sd-v1-5-pruned-emaonly
   - Minimal pipeline changes
   - Validate X-ray aesthetic improvement

### Medium-Term (Pipeline Enhancement)
3. **Implement Mask-Guided ControlNet**:
   - Generate defect masks from annotations
   - Dual conditioning: mask + text prompts
   - Test with both SD 1.5 and SDXL bases

4. **Few-Shot LoRA Fine-Tuning**:
   - Fine-tune medical X-ray base on small weld defect dataset
   - Use LoRA (low-rank adaptation) for efficiency
   - Preserve X-ray domain knowledge while specializing for welds

### Long-Term (Research/Advanced)
5. **Custom RoentGen-Inspired Model**:
   - Train SD 1.5/SDXL on industrial RT dataset
   - Vision-language approach with defect reports
   - Requires large dataset + compute investment

6. **Cascaded Diffusion for High-Res**:
   - Base model generates 512x512 → upscaler to 1024x1024+
   - Inspired by Cheff (megapixel chest X-rays)
   - [Research](https://link.springer.com/chapter/10.1007/978-3-031-33380-4_14)

---

## Testing Methodology

### Quantitative Metrics
1. **Defect Detection Performance**:
   - Train YOLOv8/RT-DETR on synthetic + real data
   - Measure mAP, precision, recall vs real-only baseline
   - Target: +5-10% improvement (per industrial defect literature)

2. **Segmentation Quality**:
   - Dice coefficient, IoU for defect masks
   - Compare synthetic-augmented vs real-only training

3. **Image Quality Metrics**:
   - FID (Fréchet Inception Distance) between synthetic and real X-rays
   - SSIM (structural similarity) for texture/contrast
   - Grayscale histogram distributions

### Qualitative Validation
1. **Expert Review**:
   - NDT inspectors evaluate realism
   - Blind A/B tests (real vs synthetic)

2. **Defect Type Fidelity**:
   - Crack morphology accuracy
   - Porosity distribution patterns
   - Lack-of-fusion boundaries

3. **Material/Weld Characteristics**:
   - Metal density gradients
   - Weld bead profiles
   - Background noise patterns

---

## Unresolved Questions

1. **RoentGen Access**: Can we obtain MIMIC-CXR credentials for research use? Alternative: Contact Stanford MIMI for industrial collaboration.

2. **Transfer Learning Efficiency**: How many weld X-ray samples needed to fine-tune medical models? Literature suggests few-shot possible (50-200 images).

3. **ControlNet Compatibility**: Are pretrained medical ControlNets (segmentation, edge) compatible with industrial RT images without retraining?

4. **SDXL ROI**: Does 2-3x compute cost for SDXL justify quality gains for industrial inspection? Need A/B testing with defect detection downstream task.

5. **Chest-Diffusion Availability**: Model weights not found on HuggingFace - contact authors or wait for public release?

6. **Hybrid Approach**: Should we combine CAD-simulated defects (physics-based) with diffusion models (learned priors)? Potential for best of both worlds.

7. **Real-Time Constraints**: Current pipeline targets batch generation - if moving to real-time augmentation, SD 1.5 vs SDXL speed critical. Benchmark needed.

8. **Defect Severity Control**: How well can text prompts control subtle differences (e.g., "minor porosity" vs "severe porosity")? Needs empirical testing.

---

## Sources

### Medical Imaging Models
- [Stanford HAI: Stable Diffusion for Medical Imaging](https://hai.stanford.edu/news/could-stable-diffusion-solve-gap-medical-imaging-data)
- [RoentGen: Vision-Language Foundation Model (Nature)](https://www.nature.com/articles/s41551-024-01246-y)
- [RoentGen Official Site](https://stanfordmimi.github.io/RoentGen/)
- [RoentGen GitHub](https://github.com/StanfordMIMI/RoentGen)
- [RoentGen v2 HuggingFace Collection](https://huggingface.co/collections/stanfordmimi/roentgen-v2-68c1f1dc6e02405ad5a3e018)
- [Chest-Diffusion Paper](https://arxiv.org/html/2407.00752v1)

### HuggingFace Models
- [DoctorDiffusion X-Ray XL LoRA](https://huggingface.co/DoctorDiffusion/doctor-diffusion-s-xray-xl-lora-0)
- [Osama03 Medical X-Ray Generation](https://huggingface.co/Osama03/Medical-X-ray-image-generation-stable-diffusion)
- [nathansutton/generate-cxr](https://huggingface.co/nathansutton/generate-cxr)
- [Jivi-RadX-v1 Visual Language Model](https://huggingface.co/jiviai/Jivi-RadX-v1)
- [Prompt2MedImage](https://huggingface.co/Nihirc/Prompt2MedImage)
- [BiomedCLIP](https://huggingface.co/microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224)

### CivitAI Models
- [Xray XL LoRA](https://civitai.com/models/231655/xray-xl-lora)
- [Detailed X-Ray Style SDXL](https://civitai.com/models/599427/detailed-x-ray-style-sdxl)
- [X-Ray Tag Collection](https://civitai.com/tag/x-ray)

### Industrial NDT Research
- [Few-Shot Steel Defect Generation (MDPI Sensors 2024)](https://www.mdpi.com/1424-8220/25/10/3038)
- [Overview of Industrial Surface Defect Generation](https://pmc.ncbi.nlm.nih.gov/articles/PMC10575288/)
- [Latent Diffusion for Steel Defect Segmentation (MDPI Sensors 2024)](https://www.mdpi.com/1424-8220/24/18/6016)
- [DiffDD: Surface Defect Detection Framework](https://www.sciencedirect.com/science/article/abs/pii/S1474034624002854)
- [Structured Guided Diffusion for Industrial Defects (2025)](https://www.sciencedirect.com/science/article/abs/pii/S0950705125016818)
- [DefectFill: Realistic Defect Generation](https://arxiv.org/html/2503.13985v1)
- [Awesome Industrial Anomaly Detection (GitHub)](https://github.com/M-3LAB/awesome-industrial-anomaly-detection)

### Weld Defect Detection
- [Automated Aerospace Weld Defect Detection (Springer)](https://link.springer.com/article/10.1007/s40194-022-01257-w)
- [Pressure Vessel Weld Defect Detection (Nature)](https://www.nature.com/articles/s41598-024-56794-9)
- [Multiclass Welding Defect Categorization (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10385814/)
- [Lightweight DCGAN for Weld Defects (Nature 2025)](https://www.nature.com/articles/s41598-025-89558-0)

### ControlNet Research
- [Evaluating Synthetic Chest X-Rays with ControlNet (ArXiv 2024)](https://arxiv.org/html/2411.18602v1)
- [Adaptively Distilled ControlNet for Medical (ArXiv 2025)](https://arxiv.org/abs/2507.23652)
- [Anatomically-Controllable Medical Image Generation (MICCAI 2024)](https://arxiv.org/html/2402.05210v2)
- [NVIDIA: Synthetic Medical Data Generation](https://developer.nvidia.com/blog/addressing-medical-imaging-limitations-with-synthetic-data-generation/)
- [ControlNet with Inexplicit Masks (ACM 2024)](https://arxiv.org/html/2403.00467v1)

### Architecture Comparisons
- [SDXL vs SD 1.5 Hands-on Comparison](https://sdxlturbo.ai/blog-SDXL-10-vs-Stable-Diffusion-15-Handson-Comparison-1518)
- [Comparative Study: SD1.5, SDXL, SD3, Flux (CivitAI)](https://civitai.com/articles/7058/comparative-study-sd15-sdxl-sd3-pony-flux)
- [Deep Dive: SDXL vs SD 1.5 Performance](https://sandner.art/sdxl-vs-sd-15-a-deep-dive-into-image-generation-ai-performance/)

### Licensing
- [Stable Diffusion LICENSE (GitHub)](https://github.com/CompVis/stable-diffusion/blob/main/LICENSE)
- [Stability AI License](https://stability.ai/license)
- [Stable Diffusion Commercial Use Explained](https://medium.com/@promptingpixels/can-stable-diffusion-models-be-used-for-commercial-use-it-depends-eedd89272245)

### Academic Surveys
- [Awesome Diffusion Models in Medical Imaging (GitHub)](https://github.com/amirhossein-kz/Awesome-Diffusion-Models-in-Medical-Imaging)
- [Diffusion Models in Medical Imaging Survey (Medical Image Analysis)](https://www.sciencedirect.com/science/article/abs/pii/S1361841523001068)
- [Systematic Review: Deep Learning for Synthetic Medical Images (Frontiers)](https://www.frontiersin.org/journals/radiology/articles/10.3389/fradi.2024.1385742/full)
- [Diffusion-Based Medical Image Augmentation (ICCV 2025)](https://openaccess.thecvf.com/content/ICCV2025W/CVAMD/papers/Nazir_Diffusion-Based_Data_Augmentation_for_Medical_Image_Segmentation_ICCVW_2025_paper.pdf)
