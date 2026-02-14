# NVIDIA Omniverse Replicator: Installation & Usage Guide for Windows 11

**Report Date:** 2026-01-10
**Research Scope:** Official NVIDIA documentation, technical requirements, installation procedures, practical workflows
**Status:** Comprehensive Research Complete

---

## Executive Summary

NVIDIA Omniverse Replicator is a production-ready synthetic data generation framework for AI training in autonomous vehicles, robotics, and computer vision. Windows 11 is the recommended platform for development (Windows 10 support ends October 14, 2025). The system requires RTX-capable GPUs with 12GB+ VRAM, modern CPUs, and 32GB RAM minimum.

**Critical Update:** Omniverse Launcher was deprecated October 1, 2025. New installations should use direct SDKs via GitHub and NVIDIA's NGC Catalog.

---

## 1. SYSTEM REQUIREMENTS FOR WINDOWS 11

### 1.1 Operating System
- **Recommended:** Windows 11 (full support, recommended for development)
- **Legacy:** Windows 10 support ends October 14, 2025; NVIDIA dropping support post-2025
- **Architecture:** x86-64 only

### 1.2 GPU Requirements (Critical)

| Usage Level | GPU Model | VRAM | CUDA Cores | Tensor Cores | Memory BW |
|---|---|---|---|---|---|
| **Basic** | RTX 3060 | 12GB | 3,584 | 112 | 360 GB/s |
| **Intermediate** | RTX 4080 | 16GB | 9,728 | 304 | 716 GB/s |
| **Advanced** | RTX 4090 | 24GB | 16,384 | 512 | 936 GB/s |

**GPU Minimum Requirements:**
- NVIDIA RTX capable graphics card (Quadro RTX 4000, RTX A4000 or higher)
- 12GB VRAM minimum for basic usage
- **Unsupported architectures:** Tesla, Fermi, Kepler, Maxwell, Pascal, Volta (no RT Cores)

### 1.3 CPU Recommendations

| Usage Level | Cores | Clock Speed | Cache | Architecture |
|---|---|---|---|---|
| **Basic** | 8 cores | 3.5 GHz | 16 MB | x86-64 |
| **Intermediate** | 12 cores | 4.0 GHz | 32 MB | x86-64 |
| **Advanced** | 16+ cores | 4.5+ GHz | 64+ MB | x86-64 |

**Intel/AMD Support:** 7th Gen Intel i7 or AMD Ryzen and newer

### 1.4 Memory & Storage
- **RAM:** Minimum 32GB; 64GB recommended for advanced workflows
- **Disk Space:** 250GB for full Isaac Sim/Replicator installation
- **Internet:** Required for asset access and extensions

### 1.5 GPU Drivers
- **Blackwell GPUs:** R570 or R580
- **Ada/Ampere/Turing:** R550, R570, or R580
- **Minimum requirement:** Drivers older than listed are unsupported
- **Windows 11 latest recommended:** Driver version 580.88

### 1.6 Known Driver Issues
- Windows R550: Occasional Real-Time 2.0 crashes
- Multi-GPU Blackwell on Windows 11 24H2: Kit crashes possible
- Vulkan 535.256+: Incorrect version reporting (requires workaround)

### 1.7 Admin Rights
- Local admin rights recommended for full functionality
- Can install without admin, but some tools/connectors/apps require UAC elevation

---

## 2. INSTALLATION STEPS

### 2.1 Path: Isaac Sim with Replicator (Recommended for Most Users)

Isaac Sim is the primary Omniverse application integrating Replicator for robotics and synthetic data generation.

#### Step 1: Prerequisites Check
```
Run Isaac Sim Compatibility Checker:
pip install isaacsim[compatibility-check]
isaacsim isaacsim.exp.compatibility_check
```

#### Step 2: Download Isaac Sim
1. Navigate to: https://docs.isaacsim.omniverse.nvidia.com/latest/installation/download.html
2. Download Windows release (latest stable version; v5.1.0 recommended)
3. Extract to `C:/isaacsim/` (create directory if needed)

#### Step 3: Directory Setup
```
Create directory:  C:\isaacsim
Extract archive to: C:\isaacsim\
```

#### Step 4: Post-Installation Configuration
```batch
# In C:\isaacsim folder:
double-click post_install.bat
# This creates symlinks to extension examples needed for tutorials
```

#### Step 5: Launch Application Selector
```batch
# In C:\isaacsim folder:
double-click isaac-sim.selector.bat
```

#### Step 6: Start Isaac Sim
- Application Selector window opens
- Select "Isaac Sim Full" from dropdown
- Click **START**

**First Launch Timing:** 5-10 minutes (shader cache compilation)

#### Step 7: Optional Login
- Omniverse login may be required
- Nucleus and Hub optional (not required for basic operation)

#### Step 8: Configuration Reset (If Needed)
```batch
isaac-sim.selector.bat --reset-user
# Starts with default configuration
```

### 2.2 Alternative Path: Container Deployment

For cloud or containerized workflows (AWS RTX instances):
- Replicator available as container running locally or on AWS
- Provides RTX graphics without local GPU requirement
- Latest version always available in container

### 2.3 Python Environment Setup (Isaac Sim 5.X)
```
Required Python: 3.11
pip install --upgrade pip
```

### 2.4 Legacy Path: Omniverse Launcher (NOT Recommended - Deprecated Oct 1, 2025)

**Status:** Omniverse Launcher deprecated. Use direct SDK installation via:
- GitHub repositories
- NVIDIA NGC Catalog
- Container-based deployment

---

## 3. REPLICATOR EXTENSION SETUP

### 3.1 Replicator Extension Access

Once Isaac Sim launches, Replicator is pre-integrated as core extension.

### 3.2 Accessing Replicator in Isaac Sim

#### Via Script Editor (Primary Development Environment)
```
Menu: Window → Script Editor
```

The Script Editor provides Python scripting interface for Replicator API.

#### Via Extension Manager
```
Menu: Extensions → Extension Manager
Search: "replicator"
View available Replicator-related extensions
```

### 3.3 Example Scripts Location
- Path: `{isaac-sim-root}/scripts/` folder
- Includes: BasicWriter, KITTI writer, domain randomization examples
- Usage: Templates for custom development

### 3.4 Running Replicator Scripts

**Execution Control (via Replicator menu):**
```
• Run        → Execute full data generation + disk output
• Preview    → Single randomization iteration without writing
• Stop       → Halt generation process
```

**Programmatic Control:**
```python
rep.orchestrator.run()     # Execute generation
rep.orchestrator.preview() # Single preview iteration
```

### 3.5 Output Directory Configuration
- **Linux Default:** `HOME/omni.replicator_out/_output`
- **Windows:** Specify valid output path (permission restrictions apply)

**Recommended Windows Path:**
```python
output_dir = "C:/omniverse_output"  # Adjust as needed
```

---

## 4. BASIC USAGE & WORKFLOW

### 4.1 Two-Step Generation Process

**Step 1: Scene Setup (Build OmniGraph)**
- Import 3D assets from CAD/Houdini/Blender
- Define and register randomizers (position, color, lighting, etc.)
- Register annotators (bounding boxes, segmentation, depth, etc.)
- Register writers (output format specification)
- Define event triggers for randomizer execution
- Result: OmniGraph nodes built efficiently

**Step 2: Execution (Generate Data)**
- Execute OmniGraph nodes
- Generate annotated synthetic data
- Write output to disk in specified format

### 4.2 Standard Workflow Pattern

```python
import omni.replicator.core as rep

# Step 1: Create scene layer
with rep.new_layer():

    # Setup viewport & camera
    camera = rep.create.camera(position=(0, 0, 100))
    render_product = rep.create.render_product(camera, (1024, 1024))

    # Import/create 3D assets
    rep.create.cube(position=(0, 0, 0), semantic_label="object")
    rep.create.sphere(position=(50, 0, 0), semantic_label="object")

    # Define randomizer function
    def randomize_scene():
        objects = rep.get.prims(semantics=[("class", "object")])
        with objects:
            rep.modify.pose(
                position=rep.distribution.uniform((-100, -100, -100), (100, 100, 100)),
                rotation=rep.distribution.uniform((0, -180, 0), (0, 180, 0)),
            )

    # Register randomizer (executes each frame)
    rep.randomizer.register(randomize_scene)

    # Setup annotators
    rep.AnnotatorRegistry.get("rgb")
    rep.AnnotatorRegistry.get("bounding_box_2d_tight")
    rep.AnnotatorRegistry.get("semantic_segmentation")

    # Setup writer
    writer = rep.WriterRegistry.get("BasicWriter")
    writer.initialize(
        output_dir="C:/omniverse_output",
        rgb=True,
        bounding_box_2d_tight=True,
        semantic_segmentation=True
    )
    writer.attach([render_product])

    # Execute generation
    rep.orchestrator.run()
```

### 4.3 Core API Functions Reference

| Function | Purpose |
|----------|---------|
| `rep.new_layer()` | Create isolated workspace for scene |
| `rep.create.camera()` | Define camera with position/orientation |
| `rep.create.render_product()` | Create render output at specified resolution |
| `rep.create.cube/sphere/torus()` | Create basic 3D primitives |
| `rep.get.prims()` | Query scene primitives by semantic labels |
| `rep.modify.pose()` | Randomize position, rotation, scale |
| `rep.randomizer.register()` | Register randomization function |
| `rep.distribution.uniform()` | Uniform random distribution |
| `rep.distribution.normal()` | Gaussian distribution |
| `rep.distribution.choice()` | Random selection from list |
| `rep.WriterRegistry.get()` | Initialize writer (BasicWriter, KITTI, etc.) |
| `rep.AnnotatorRegistry.get()` | Access specific annotator |
| `rep.orchestrator.run()` | Execute full generation pipeline |
| `rep.orchestrator.preview()` | Single preview iteration |

---

## 5. KEY FEATURES & CAPABILITIES

### 5.1 Synthetic Data Generation

**What It Generates:**
- Physically accurate 3D synthetic images
- Perfect pixel-level annotations (no manual labeling)
- Multi-sensor data (camera, radar, lidar simulations)
- Edge case scenarios (rare conditions, adverse weather)

### 5.2 Domain Randomization

**Randomizable Scene Parameters:**

| Category | Examples |
|----------|----------|
| **Object Pose** | Position (X, Y, Z), rotation (roll, pitch, yaw), scale |
| **Lighting** | Intensity, temperature, color, position, dome textures |
| **Materials/Textures** | Diffuse color, roughness, metallic, custom materials |
| **Camera** | Position, focal length, aperture, motion blur settings |
| **Scene Population** | Asset instantiation as distractors, object occlusion |
| **Physics** | Dynamics parameters (for RL domain randomization) |

**Distribution Functions:**
```python
rep.distribution.uniform(min, max)        # Uniform random
rep.distribution.normal(mean, std)        # Gaussian
rep.distribution.choice(list)             # Random selection
rep.distribution.log_uniform(min, max)    # Log-scale uniform
```

### 5.3 Annotators (Ground Truth Labels)

**Available Annotators:**

| Annotator | Output Format |
|-----------|---------------|
| **rgb** | RGB images (8-bit or 16-bit) |
| **bounding_box_2d_tight** | 2D tight bounding boxes (minimal occlusion) |
| **bounding_box_2d_loose** | 2D loose bounding boxes (object fully contained) |
| **bounding_box_3d** | 3D bounding box corners (8 points) |
| **semantic_segmentation** | Per-class 2D segmentation masks |
| **instance_segmentation** | Per-instance 2D segmentation masks |
| **distance_to_image_plane** | Depth/distance from camera |
| **normals** | Surface normal vectors |
| **occlusion** | Pixel occlusion percentage per object |
| **pose** | 6D object pose (position + rotation) |
| **optical_flow** | Motion vectors between frames |

**Colorized Output Option:**
```python
rep.AnnotatorRegistry.get("semantic_segmentation",
    init_params={"colorize": True})
```

### 5.4 Writers (Output Formats)

**Built-in Writers:**
- **BasicWriter:** Standard format with JSON metadata
- **KITTIWriter:** KITTI autonomous driving format
- **COCOWriter:** MS COCO format for object detection
- **Custom Writers:** Extensible for domain-specific formats

**Writer Initialization Example:**
```python
writer = rep.WriterRegistry.get("BasicWriter")
writer.initialize(
    output_dir="C:/output",
    rgb=True,
    bounding_box_2d_tight=True,
    semantic_segmentation=True,
    instance_segmentation=True,
    distance_to_image_plane=True,
    bounding_box_3d=True,
    occlusion=True,
    normals=True
)
```

### 5.5 Semantic Annotations Requirement

Critical for proper annotation generation:
```python
# Assign semantic labels to objects for Replicator to identify
rep.create.cube(position=(0, 0, 0), semantic_label="vehicle_class")
rep.create.sphere(position=(50, 0, 0), semantic_label="pedestrian_class")

# Query by semantic label
objects = rep.get.prims(semantics=[("class", "vehicle_class")])
```

### 5.6 Open Standards Integration
- **Universal Scene Description (USD):** Scene representation
- **PhysX:** Physics engine for realistic dynamics
- **Material Definition Language (MDL):** Material definitions
- **OmniGraph:** Efficient node-based execution graph

### 5.7 Recent Feature: YAML-based Configuration (v1.10+)

Low-code approach for data generation:
```yaml
scene:
  assets:
    - path: "path/to/model.usd"
      semantic_label: "object"

randomization:
  position:
    distribution: "uniform"
    range: [[-100, -100, -100], [100, 100, 100]]

annotators:
  - rgb
  - bounding_box_2d_tight
  - semantic_segmentation

output:
  writer: "BasicWriter"
  num_frames: 1000
```

Batch generation via Omniverse Farm on NVIDIA OVX systems.

### 5.8 Asynchronous Rendering (v1.10+)

Disaggregates sensor simulation from rendering:
- Scale across multiple GPUs
- Better throughput for large datasets
- Maintains annotation accuracy

---

## 6. COMMON USE CASES

### 6.1 Autonomous Vehicle Development

**NVIDIA DRIVE Sim Example:**
- Virtual world for AV digital twins
- Generates physically accurate sensor data (camera, radar, lidar, ultrasonic)
- Captures real-world effects:
  - LED flicker
  - Motion blur
  - Rolling shutter
  - Lidar beam divergence
  - Doppler effect

**Workflow:**
1. Import 3D road environments
2. Randomize weather, lighting, traffic scenarios
3. Generate labeled sensor data
4. Train AV perception models

### 6.2 Robotics & Control Training

**Isaac Sim Integration:**
- GPU-accelerated high-fidelity simulation
- Deep reinforcement learning via Isaac Gym
- Domain randomization for sim-to-real transfer
- On-the-fly physics attribute randomization (no asset reloading)

**Use Cases:**
- Robotic arm grasping
- Mobile robot navigation
- Manipulation under uncertainty

### 6.3 Computer Vision Model Training

**Defect Detection Example:**
- Started with 50 ground-truth images of automotive panel defects
- Generated synthetic data with domain randomization (lighting, reflection)
- **Result:** 94.5% mAP, significantly outperforming baseline

**General CV Applications:**
- Object detection
- Instance segmentation
- Pose estimation
- 3D reconstruction

### 6.4 Pose Estimation

**Flying Distractors Pattern:**
- Add randomized objects around target object
- Randomize colors, materials, lighting
- Generate diverse occlusion scenarios
- Multi-dataset support (MESH, DOME, custom)

### 6.5 Intelligent Video Analytics

**Surveillance & Security:**
- Rare event detection (criminal activity, accidents)
- Large-scale scenario generation
- Perfect labels for anomaly detection training

### 6.6 Reinforcement Learning Domain Randomization

**Physics Parameter Randomization:**
- Sim-to-real policy transfer
- Agent robustness to dynamics variation
- On-the-fly randomization without reloading assets
- Framework: `omni.replicator.isaac`

---

## 7. PRODUCTION DEPLOYMENT OPTIONS

### 7.1 Local Workstation (Windows 11)
- Direct installation with RTX GPU
- Immediate iteration and development
- Limited by single GPU throughput

### 7.2 Cloud Deployment (AWS)
- RTX-equipped AWS instances
- Scalable throughput
- Managed infrastructure
- Container-based Replicator

### 7.3 Omniverse Farm (Enterprise)
- Multi-GPU batch processing
- NVIDIA OVX systems
- YAML-based workflow automation
- Managed via Hub Workstation (replacement for Nucleus)

### 7.4 Output Storage Backends
- Local storage (primary)
- Cloud-based backends (SwiftStack)
- Network storage (future support)

---

## 8. WORKFLOW INTEGRATION & STANDARDS

### 8.1 Asset Import

**Supported Formats:**
- .obj (Wavefront OBJ)
- .fbx (Autodesk FBX)
- .glif (USD variants)
- CAD formats (via CAD Importer extension)

**Import Process:**
```
1. Menu: Extensions → CAD Importer
2. Select 3D model file
3. Automatic USD conversion
4. Ready for Replicator use
```

### 8.2 Data Export Formats

**Per-Writer Output:**
- BasicWriter: PNG images + JSON metadata
- KITTIWriter: KITTI benchmark format
- COCOWriter: MS COCO JSON
- Custom formats via custom writers

### 8.3 Batch Processing

**Workflow Sharing:**
- YAML configuration files
- Python scripts
- Reproducible data generation
- Version control friendly

---

## 9. TECHNICAL TROUBLESHOOTING

### 9.1 First Launch Issues

| Issue | Solution |
|-------|----------|
| Blank window on startup | Wait 5-10 minutes (shader compilation) |
| Isaac Sim selector won't open | Run with admin rights; check GPU driver R580.88+ |
| "GPU not found" error | Verify RTX GPU (not Tesla/Volta); update driver |
| VRAM insufficient | Check GPU has ≥12GB; lower resolution (512x512 vs 1024x1024) |

### 9.2 Output Directory Permissions (Windows)

**Problem:** Write permission errors
**Solution:** Use explicit paths in C:/ drive root
```python
output_dir = "C:/omniverse_output"  # Not %USERPROFILE% or UNC paths
```

### 9.3 Extension Loading Issues

**Problem:** Replicator extension not visible
**Solution:**
```
1. Verify Isaac Sim installed correctly
2. Check Extension Manager (Window → Extensions)
3. Search "replicator" explicitly
4. Ensure Script Editor available (Window → Script Editor)
```

### 9.4 Multi-GPU Setup (Windows 11 24H2)

**Known Issue:** Blackwell multi-GPU configurations may crash Kit
**Workaround:** Use single GPU; or update drivers to R580+

---

## 10. KEY RESOURCES & DOCUMENTATION

### Official NVIDIA Documentation
- [Replicator Extension Docs](https://docs.omniverse.nvidia.com/extensions/latest/ext_replicator.html)
- [Replicator Getting Started](https://docs.omniverse.nvidia.com/extensions/latest/ext_replicator/getting_started.html)
- [Isaac Sim Installation](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_workstation.html)
- [Technical Requirements](https://docs.omniverse.nvidia.com/launcher/latest/common/technical-requirements.html)
- [Replicator Python API](https://docs.omniverse.nvidia.com/py/replicator/)

### Example Code Repositories
- [NVIDIA Synthetic Data Examples](https://github.com/NVIDIA-Omniverse/synthetic-data-examples/)
- Isaac Sim scripts folder: `{install-dir}/scripts/`

### Tutorials & Guides
- [Randomizer Examples](https://docs.omniverse.nvidia.com/extensions/latest/ext_replicator/randomizer_details.html)
- [Annotators Reference](https://docs.omniverse.nvidia.com/extensions/latest/ext_replicator/annotators_details.html)
- [Online Generation Tutorial](https://docs.isaacsim.omniverse.nvidia.com/4.5.0/replicator_tutorials/tutorial_replicator_online_generation.html)
- [Pose Estimation with Synthetic Data](https://docs-prod.omniverse.nvidia.com/isaacsim/latest/replicator_tutorials/tutorial_replicator_pose_estimation.html)
- [Domain Randomization for RL](https://docs.omniverse.nvidia.com/app_isaacsim/app_isaacsim/tutorial_gym_domain_randomization.html)

---

## UNRESOLVED QUESTIONS / OPEN ITEMS

1. **Custom Writer Development:** Detailed specification for implementing domain-specific output writers (beyond KITTI/COCO)

2. **Real-world Validation Metrics:** Guidance on measuring synthetic-to-real domain gap and transfer effectiveness

3. **Scalability Benchmarks:** Performance data for batch processing throughput on multi-GPU setups (Isaac Sim 5.X+)

4. **Integration with ML Frameworks:** Official examples for PyTorch DataLoader, TensorFlow integration with online generation

5. **Licensing & Enterprise Support:** Clarification on commercial usage terms and enterprise support tiers post-Launcher deprecation

6. **Performance Optimization:** Best practices for YAML-based batch workflows and GPU memory management under load

---

## SUMMARY TABLE: Quick Reference

| Item | Detail |
|------|--------|
| **OS** | Windows 11 (Windows 10 EOL Oct 14, 2025) |
| **GPU Min** | RTX 3060 (12GB); RTX 4080+ recommended |
| **CPU Min** | Intel i7-7th gen or AMD Ryzen (8+ cores) |
| **RAM** | 32GB minimum; 64GB recommended |
| **Installation** | Download → Extract to C:/isaacsim → run post_install.bat → isaac-sim.selector.bat |
| **Primary Entry** | Isaac Sim integrated with Replicator |
| **Dev Environment** | Script Editor (Python API) |
| **Core Workflow** | Scene setup → Randomization → Annotation → Writing → Execution |
| **Data Output** | PNG + JSON metadata; KITTI/COCO/custom formats |
| **Main Use Cases** | AV perception, robotics RL, CV model training, pose estimation |
| **Deployment** | Local workstation, AWS cloud, NVIDIA OVX/Farm |
| **Launcher Status** | DEPRECATED (Oct 1, 2025) → Use direct SDK/NGC |
| **Driver Recommended** | R580.88+ (Windows 11) |

---

**Report Generated:** 2026-01-10
**Research Cutoff:** February 2025 (Claude knowledge) + January 2026 web search
**Sources:** Official NVIDIA documentation, GitHub, technical blogs, enterprise resources
