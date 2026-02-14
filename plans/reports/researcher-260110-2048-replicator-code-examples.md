# NVIDIA Omniverse Replicator: Practical Code Examples

**Reference Guide for Common Workflows** | 2026-01-10

---

## EXAMPLE 1: Basic Hello World - Create & Annotate Objects

**Purpose:** Minimal example demonstrating core Replicator workflow

```python
import omni.replicator.core as rep

# Create isolated scene layer
with rep.new_layer():

    # STEP 1: Setup camera and render output
    camera = rep.create.camera(
        position=(0, 100, 0),
        focal_length=50,
        focus_distance=100
    )
    render_product = rep.create.render_product(camera, (1024, 1024))

    # STEP 2: Create 3D objects with semantic labels
    rep.create.cube(
        position=(0, 0, 0),
        scale=(10, 10, 10),
        semantic_label="cube"
    )
    rep.create.sphere(
        position=(50, 0, 0),
        scale=(5, 5, 5),
        semantic_label="sphere"
    )
    rep.create.cylinder(
        position=(-50, 0, 0),
        scale=(5, 5, 10),
        semantic_label="cylinder"
    )

    # STEP 3: Setup RGB annotation
    annotators = [rep.AnnotatorRegistry.get("rgb")]

    # STEP 4: Configure BasicWriter
    writer = rep.WriterRegistry.get("BasicWriter")
    writer.initialize(
        output_dir="C:/omniverse_output/example_01_hello_world",
        rgb=True  # Save RGB images
    )
    writer.attach([render_product])

    # STEP 5: Generate 10 frames
    rep.orchestrator.run(num_frames=10)

print("✓ Generated 10 frames with RGB output")
print("Output: C:/omniverse_output/example_01_hello_world/")
```

**Output Structure:**
```
example_01_hello_world/
├── 000000.png          # Frame 0 RGB image
├── 000001.png          # Frame 1 RGB image
├── ...
└── metadata.json       # Generation parameters
```

---

## EXAMPLE 2: Bounding Box Generation - Object Detection Training

**Purpose:** Generate annotated images with 2D bounding boxes for object detection

```python
import omni.replicator.core as rep

with rep.new_layer():

    # Setup camera and renderer
    camera = rep.create.camera(position=(0, 50, 150), focal_length=50)
    render_product = rep.create.render_product(camera, (1024, 1024))

    # Create objects to detect
    cube = rep.create.cube(
        position=(0, 0, 0),
        scale=(20, 20, 20),
        semantic_label="vehicle"  # Label for detection
    )
    sphere = rep.create.sphere(
        position=(100, 0, 0),
        scale=(15, 15, 15),
        semantic_label="pedestrian"
    )

    # Configure writer with bounding box annotation
    writer = rep.WriterRegistry.get("BasicWriter")
    writer.initialize(
        output_dir="C:/omniverse_output/example_02_bbox",
        rgb=True,
        bounding_box_2d_tight=True,  # Tight 2D bboxes
        bounding_box_2d_loose=False  # Optional: loose bboxes
    )
    writer.attach([render_product])

    # Generate 100 frames
    rep.orchestrator.run(num_frames=100)

print("✓ Generated 100 frames with 2D bounding box annotations")
```

**JSON Annotation Format:**
```json
{
  "frame_id": 0,
  "objects": [
    {
      "class": "vehicle",
      "bbox_2d_tight": [x1, y1, x2, y2],
      "area": 15600,
      "visibility": 1.0
    },
    {
      "class": "pedestrian",
      "bbox_2d_tight": [x1, y1, x2, y2],
      "area": 9600,
      "visibility": 0.95
    }
  ]
}
```

---

## EXAMPLE 3: Domain Randomization - Lighting & Color

**Purpose:** Randomize lighting, colors, materials to increase dataset diversity

```python
import omni.replicator.core as rep

with rep.new_layer():

    # Setup camera
    camera = rep.create.camera(position=(0, 100, 200), focal_length=50)
    render_product = rep.create.render_product(camera, (1024, 1024))

    # Create objects
    cube = rep.create.cube(
        position=(0, 0, 0),
        scale=(30, 30, 30),
        semantic_label="object"
    )

    # Add lighting
    dome_light = rep.create.light_dome(
        intensity=rep.distribution.uniform(0.5, 2.0),
        rotation=rep.distribution.uniform((0, 0, 0), (0, 360, 0))
    )

    # Add directional light
    directional = rep.create.light(
        light_type="directional",
        position=(100, 200, 100),
        look_at=(0, 0, 0),
        intensity=rep.distribution.uniform(1.0, 3.0),
        color=rep.distribution.choice([
            (1.0, 1.0, 1.0),  # White
            (1.0, 0.8, 0.6),  # Warm
            (0.6, 0.8, 1.0)   # Cool
        ])
    )

    # Define randomization function
    def randomize_scene():
        # Get cube by semantic label
        objects = rep.get.prims(semantics=[("class", "object")])

        with objects:
            # Randomize material properties
            rep.modify.material(
                diffuse_color=rep.distribution.choice([
                    (1.0, 0.0, 0.0),  # Red
                    (0.0, 1.0, 0.0),  # Green
                    (0.0, 0.0, 1.0),  # Blue
                    (1.0, 1.0, 1.0)   # White
                ])
            )

    # Register randomization trigger (runs every frame)
    rep.randomizer.register(randomize_scene)

    # Configure output
    writer = rep.WriterRegistry.get("BasicWriter")
    writer.initialize(
        output_dir="C:/omniverse_output/example_03_domain_randomization",
        rgb=True,
        semantic_segmentation=True  # Add segmentation
    )
    writer.attach([render_product])

    # Generate 500 diverse frames
    rep.orchestrator.run(num_frames=500)

print("✓ Generated 500 frames with randomized lighting & colors")
print("Dataset diversity achieved through domain randomization")
```

**Randomization Parameters Varied Each Frame:**
- Lighting intensity: 0.5 → 2.0x
- Lighting rotation: 0° → 360°
- Light color: White/Warm/Cool variations
- Object color: Red/Green/Blue/White

---

## EXAMPLE 4: Pose Randomization - Object Position & Rotation

**Purpose:** Randomize object poses (position, rotation) for robust detection

```python
import omni.replicator.core as rep

with rep.new_layer():

    # Setup camera
    camera = rep.create.camera(
        position=(0, 150, 300),
        look_at=(0, 0, 0),
        focal_length=50
    )
    render_product = rep.create.render_product(camera, (1024, 1024))

    # Create multiple objects
    objects_to_randomize = []
    for i in range(5):
        obj = rep.create.cube(
            position=(0, 0, 0),  # Will be randomized
            scale=(20, 20, 20),
            semantic_label="box"
        )
        objects_to_randomize.append(obj)

    # Define pose randomization
    def randomize_poses():
        # Get all boxes
        boxes = rep.get.prims(semantics=[("class", "box")])

        with boxes:
            # Randomize position (within a 200x200x200 space)
            rep.modify.pose(
                position=rep.distribution.uniform(
                    (-100, 0, -100),    # Min (x, y, z)
                    (100, 100, 100)     # Max (x, y, z)
                ),
                rotation=rep.distribution.uniform(
                    (0, -180, 0),       # Min rotation (deg)
                    (360, 180, 360)     # Max rotation (deg)
                ),
                scale=rep.distribution.normal(
                    mean=1.0,           # Scale mean
                    std=0.2             # Scale variance
                )
            )

    rep.randomizer.register(randomize_poses)

    # Configure output with 3D bounding boxes
    writer = rep.WriterRegistry.get("BasicWriter")
    writer.initialize(
        output_dir="C:/omniverse_output/example_04_pose_randomization",
        rgb=True,
        bounding_box_2d_tight=True,
        bounding_box_3d=True,  # 3D box corners (8 points)
        instance_segmentation=True
    )
    writer.attach([render_product])

    # Generate dataset
    rep.orchestrator.run(num_frames=1000)

print("✓ Generated 1000 frames with randomized poses")
print("Boxes appear at random positions/orientations/scales")
```

**Pose Distributions:**
- **Position:** Uniform (-100 to 100) in X/Z, (0 to 100) in Y
- **Rotation:** Full 360° rotation in all axes
- **Scale:** Normal distribution (mean=1.0, std=0.2)

---

## EXAMPLE 5: Semantic & Instance Segmentation

**Purpose:** Generate pixel-level segmentation masks for segmentation tasks

```python
import omni.replicator.core as rep

with rep.new_layer():

    # Setup camera
    camera = rep.create.camera(position=(0, 100, 200), focal_length=50)
    render_product = rep.create.render_product(camera, (1024, 1024))

    # Create multiple object classes
    # Class 1: Vehicles
    for i in range(3):
        rep.create.cube(
            position=(i*60-60, 0, 0),
            scale=(20, 20, 40),
            semantic_label="vehicle"
        )

    # Class 2: Pedestrians
    for i in range(5):
        rep.create.sphere(
            position=(i*40-80, 0, 50),
            scale=(10, 10, 10),
            semantic_label="pedestrian"
        )

    # Class 3: Background/Scene
    rep.create.plane(
        position=(0, -50, 0),
        scale=(500, 1, 500),
        semantic_label="ground"
    )

    # Configure output with segmentation
    writer = rep.WriterRegistry.get("BasicWriter")
    writer.initialize(
        output_dir="C:/omniverse_output/example_05_segmentation",
        rgb=True,
        semantic_segmentation=True,      # Per-class segmentation
        instance_segmentation=True,      # Per-instance segmentation (each object)
        instance_segmentation_colorize=True  # Colorized for visualization
    )
    writer.attach([render_product])

    # Generate 200 frames
    rep.orchestrator.run(num_frames=200)

print("✓ Generated semantic & instance segmentation masks")
print("Output includes:")
print("  - RGB images")
print("  - Semantic segmentation (vehicle/pedestrian/ground)")
print("  - Instance segmentation (each object separately)")
```

**Segmentation Output:**
```
Frame 000000:
├── 000000.png                              # RGB image
├── 000000_semantic_segmentation.png        # Per-class masks
└── 000000_instance_segmentation.png        # Per-instance masks
```

---

## EXAMPLE 6: Depth & Surface Normals

**Purpose:** Generate depth maps and normal maps for 3D understanding

```python
import omni.replicator.core as rep

with rep.new_layer():

    # Setup camera
    camera = rep.create.camera(position=(0, 100, 200), focal_length=50)
    render_product = rep.create.render_product(camera, (1024, 1024))

    # Create 3D scene with depth variation
    rep.create.cube(
        position=(0, 0, 0),
        scale=(30, 30, 30),
        semantic_label="near_object"
    )
    rep.create.sphere(
        position=(100, 50, 100),
        scale=(40, 40, 40),
        semantic_label="far_object"
    )
    rep.create.plane(
        position=(0, -50, 0),
        scale=(500, 1, 500),
        semantic_label="ground"
    )

    # Configure output with depth/normals
    writer = rep.WriterRegistry.get("BasicWriter")
    writer.initialize(
        output_dir="C:/omniverse_output/example_06_depth_normals",
        rgb=True,
        distance_to_image_plane=True,      # Depth map
        normals=True,                      # Surface normals
        occlusion=True                     # Per-pixel occlusion
    )
    writer.attach([render_product])

    rep.orchestrator.run(num_frames=100)

print("✓ Generated depth maps and surface normals")
print("Useful for: 3D reconstruction, depth estimation, normal prediction")
```

**Output Annotations:**
- `distance_to_image_plane`: Per-pixel distance from camera
- `normals`: Per-pixel surface normal vectors (R, G, B = X, Y, Z)
- `occlusion`: Per-object occlusion percentage

---

## EXAMPLE 7: Asset Variation - Distractors & Scene Population

**Purpose:** Add random distractor objects to increase scene complexity

```python
import omni.replicator.core as rep
import random

with rep.new_layer():

    # Setup camera
    camera = rep.create.camera(position=(0, 150, 300), focal_length=50)
    render_product = rep.create.render_product(camera, (1024, 1024))

    # Main object to detect
    main_object = rep.create.cube(
        position=(0, 0, 0),
        scale=(30, 30, 30),
        semantic_label="target"
    )

    # Define randomization with distractors
    def randomize_with_distractors():
        # Randomize main object
        target = rep.get.prims(semantics=[("class", "target")])
        with target:
            rep.modify.pose(
                position=rep.distribution.uniform((-50, 0, -50), (50, 50, 50)),
                rotation=rep.distribution.uniform((0, -180, 0), (0, 180, 0))
            )

        # Add random distractors (cubes, spheres, cylinders)
        distractor_shapes = ["cube", "sphere", "cylinder"]
        for i in range(5):  # Add 5 random distractors
            shape_type = rep.distribution.choice(distractor_shapes)

            if shape_type == "cube":
                rep.create.cube(
                    position=rep.distribution.uniform((-150, 0, -150), (150, 100, 150)),
                    scale=(15, 15, 15),
                    semantic_label="distractor"
                )
            elif shape_type == "sphere":
                rep.create.sphere(
                    position=rep.distribution.uniform((-150, 0, -150), (150, 100, 150)),
                    scale=(10, 10, 10),
                    semantic_label="distractor"
                )
            elif shape_type == "cylinder":
                rep.create.cylinder(
                    position=rep.distribution.uniform((-150, 0, -150), (150, 100, 150)),
                    scale=(10, 10, 20),
                    semantic_label="distractor"
                )

    rep.randomizer.register(randomize_with_distractors)

    # Configure output
    writer = rep.WriterRegistry.get("BasicWriter")
    writer.initialize(
        output_dir="C:/omniverse_output/example_07_distractors",
        rgb=True,
        bounding_box_2d_tight=True,
        instance_segmentation=True
    )
    writer.attach([render_product])

    rep.orchestrator.run(num_frames=500)

print("✓ Generated 500 frames with random distractors")
print("Improves robustness against background clutter")
```

---

## EXAMPLE 8: Custom Randomization with Distributions

**Purpose:** Demonstrate various distribution types for flexible randomization

```python
import omni.replicator.core as rep
import math

with rep.new_layer():

    # Setup camera
    camera = rep.create.camera(position=(0, 100, 200), focal_length=50)
    render_product = rep.create.render_product(camera, (1024, 1024))

    # Create test object
    test_obj = rep.create.cube(
        position=(0, 0, 0),
        scale=(20, 20, 20),
        semantic_label="test_object"
    )

    # Define randomization with multiple distribution types
    def randomize_distributions():
        obj = rep.get.prims(semantics=[("class", "test_object")])

        with obj:
            rep.modify.pose(
                # UNIFORM distribution - equal probability across range
                position=(
                    rep.distribution.uniform(-100, 100),           # X
                    rep.distribution.uniform(0, 100),               # Y
                    rep.distribution.uniform(-100, 100)             # Z
                ),

                # NORMAL (Gaussian) distribution - clustered around mean
                # mean=0, std=30 → most values within ±30 of center
                rotation=(
                    rep.distribution.normal(mean=0, std=30),       # Roll
                    rep.distribution.normal(mean=180, std=45),     # Pitch
                    rep.distribution.normal(mean=0, std=30)        # Yaw
                ),

                # LOG-UNIFORM distribution - exponential scaling
                # Good for scale/intensity parameters (0.1 to 10.0)
                scale=rep.distribution.log_uniform(0.5, 2.0)
            )

    # Alternative: CHOICE distribution - select from discrete options
    def randomize_colors():
        obj = rep.get.prims(semantics=[("class", "test_object")])

        with obj:
            rep.modify.material(
                # Random selection from list
                diffuse_color=rep.distribution.choice([
                    (1.0, 0.0, 0.0),      # Red
                    (0.0, 1.0, 0.0),      # Green
                    (0.0, 0.0, 1.0),      # Blue
                    (1.0, 1.0, 0.0),      # Yellow
                    (1.0, 0.0, 1.0)       # Magenta
                ])
            )

    rep.randomizer.register(randomize_distributions)
    rep.randomizer.register(randomize_colors)

    # Configure output
    writer = rep.WriterRegistry.get("BasicWriter")
    writer.initialize(
        output_dir="C:/omniverse_output/example_08_distributions",
        rgb=True
    )
    writer.attach([render_product])

    rep.orchestrator.run(num_frames=300)

print("✓ Demonstrated multiple distribution types:")
print("  - Uniform: Even probability across range")
print("  - Normal: Gaussian clustering")
print("  - Log-Uniform: Exponential scaling")
print("  - Choice: Discrete selection")
```

---

## EXAMPLE 9: KITTI Format Export for Autonomous Driving

**Purpose:** Generate dataset in KITTI benchmark format for AV training

```python
import omni.replicator.core as rep

with rep.new_layer():

    # Setup camera (simulate vehicle camera)
    camera = rep.create.camera(
        position=(0, 150, 0),    # Typical vehicle camera height
        focal_length=800,        # KITTI typical focal length
        aperture_size=(1024, 1024)
    )
    render_product = rep.create.render_product(camera, (1242, 375))  # KITTI resolution

    # Create road environment
    rep.create.plane(
        position=(0, -100, 0),
        scale=(1000, 1, 1000),
        semantic_label="road"
    )

    # Create vehicles
    for i in range(3):
        rep.create.cube(
            position=(i*100-100, 150, 100),
            scale=(40, 40, 80),
            semantic_label="vehicle"
        )

    # Create pedestrians
    for i in range(5):
        rep.create.sphere(
            position=(i*50-100, 175, 50),
            scale=(15, 40, 15),
            semantic_label="pedestrian"
        )

    # Randomize scene
    def randomize_scene():
        vehicles = rep.get.prims(semantics=[("class", "vehicle")])
        pedestrians = rep.get.prims(semantics=[("class", "pedestrian")])

        with vehicles:
            rep.modify.pose(
                position=rep.distribution.uniform((-300, 150, -100), (300, 150, 200)),
                rotation=rep.distribution.uniform((0, -10, 0), (0, 10, 0))
            )

        with pedestrians:
            rep.modify.pose(
                position=rep.distribution.uniform((-300, 175, -100), (300, 175, 200))
            )

    rep.randomizer.register(randomize_scene)

    # Use KITTI writer (if available)
    # Note: May require custom writer setup in production
    writer = rep.WriterRegistry.get("BasicWriter")
    writer.initialize(
        output_dir="C:/omniverse_output/example_09_kitti_format",
        rgb=True,
        bounding_box_3d=True,
        instance_segmentation=True
    )
    writer.attach([render_product])

    rep.orchestrator.run(num_frames=2000)

print("✓ Generated KITTI-compatible dataset")
print("Resolution: 1242x375 (KITTI standard)")
print("Includes: 3D boxes, instance masks")
```

---

## EXAMPLE 10: Preview vs Production Workflow

**Purpose:** Compare preview (single frame) vs full generation

```python
import omni.replicator.core as rep

# PART 1: PREVIEW MODE (test setup without generating dataset)
print("=== PREVIEW MODE ===")
with rep.new_layer():

    camera = rep.create.camera(position=(0, 100, 200), focal_length=50)
    render_product = rep.create.render_product(camera, (1024, 1024))

    cube = rep.create.cube(position=(0, 0, 0), semantic_label="cube")

    def randomize():
        objs = rep.get.prims(semantics=[("class", "cube")])
        with objs:
            rep.modify.pose(
                position=rep.distribution.uniform((-100, 0, -100), (100, 100, 100))
            )

    rep.randomizer.register(randomize)

    writer = rep.WriterRegistry.get("BasicWriter")
    writer.initialize(
        output_dir="C:/omniverse_output/example_10_preview",
        rgb=True
    )
    writer.attach([render_product])

    # Preview: Single frame to verify setup
    print("Previewing single frame...")
    rep.orchestrator.preview()
    print("✓ Preview complete - check image in output folder")

# PART 2: PRODUCTION MODE (generate full dataset)
print("\n=== PRODUCTION MODE ===")
with rep.new_layer():

    camera = rep.create.camera(position=(0, 100, 200), focal_length=50)
    render_product = rep.create.render_product(camera, (1024, 1024))

    cube = rep.create.cube(position=(0, 0, 0), semantic_label="cube")

    def randomize():
        objs = rep.get.prims(semantics=[("class", "cube")])
        with objs:
            rep.modify.pose(
                position=rep.distribution.uniform((-100, 0, -100), (100, 100, 100))
            )

    rep.randomizer.register(randomize)

    writer = rep.WriterRegistry.get("BasicWriter")
    writer.initialize(
        output_dir="C:/omniverse_output/example_10_production",
        rgb=True,
        bounding_box_2d_tight=True,
        semantic_segmentation=True
    )
    writer.attach([render_product])

    # Production: Generate 10,000 frames
    print("Generating 10,000 frames...")
    rep.orchestrator.run(num_frames=10000)
    print("✓ Production generation complete")

print("\n=== WORKFLOW COMPLETE ===")
print("Preview: Single test frame")
print("Production: 10,000 annotated frames")
```

**Workflow Best Practices:**
1. Use `preview()` to verify setup (5 seconds)
2. Test with small batch (100 frames)
3. Monitor GPU memory during generation
4. Generate production dataset (1000+ frames)

---

## COMMON API PATTERNS

### Query Objects by Semantic Label
```python
# Get specific objects
specific_objs = rep.get.prims(semantics=[("class", "vehicle")])

# Get multiple classes
multi_class = rep.get.prims(semantics=[
    ("class", "vehicle"),
    ("class", "pedestrian")
])
```

### Apply Properties Conditionally
```python
objects = rep.get.prims(semantics=[("class", "car")])
with objects:
    rep.modify.pose(position=(10, 20, 30))
    rep.modify.material(diffuse_color=(1.0, 0.0, 0.0))
```

### Register Multiple Randomizers
```python
def randomize_positions():
    # Position logic
    pass

def randomize_colors():
    # Color logic
    pass

def randomize_lighting():
    # Lighting logic
    pass

# Register all
rep.randomizer.register(randomize_positions)
rep.randomizer.register(randomize_colors)
rep.randomizer.register(randomize_lighting)

# All execute each frame in order
```

### Frame-based Triggers
```python
def randomize_every_10_frames():
    # Only apply some randomization every 10 frames
    pass

# Advanced: Conditional randomization
def conditional_randomization():
    pass  # Condition inside function

rep.randomizer.register(conditional_randomization)
```

---

## PERFORMANCE OPTIMIZATION TIPS

1. **Resolution Trade-off**
   - Lower: 512x512 (2-3 FPS)
   - Medium: 1024x1024 (0.5-1 FPS)
   - High: 2048x2048 (0.1 FPS on RTX 3060)

2. **Simplify Meshes**
   - Use primitive shapes when possible
   - LOD (level-of-detail) models for complex assets

3. **Batch Processing**
   - Generate 1000-frame batches
   - Parallel processing with Omniverse Farm

4. **Monitor Resources**
   ```powershell
   # Task Manager: GPU %, VRAM usage, CPU usage
   # Target: GPU 90%+, VRAM stable
   ```

---

## NEXT STEPS

1. Copy-paste examples into Script Editor
2. Modify output paths (C:/omniverse_output/)
3. Run with `Replicator → Run` or `rep.orchestrator.run()`
4. Check output directory for generated images
5. Integrate with training pipeline (PyTorch DataLoader, etc.)

---

**Last Updated:** 2026-01-10
**Tested With:** Isaac Sim 5.1.0 + Replicator 1.11.8
**Omniverse Version:** Latest (2024+)
