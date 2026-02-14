# NVIDIA Omniverse Replicator: Windows 11 Setup Checklist

**Quick Implementation Checklist** | Last Updated: 2026-01-10

---

## PRE-INSTALLATION VERIFICATION

- [ ] Windows 11 installed (21H2 or later recommended)
- [ ] NVIDIA RTX GPU installed (RTX 3060/4080/4090)
- [ ] GPU driver R580.88 (Windows 11) or R550/R570/R580 variant
- [ ] 32GB+ RAM available (check via `wmic OS get TotalVisibleMemorySize`)
- [ ] 250GB+ disk space on C:/ drive (or installation target)
- [ ] Internet connection active (for asset downloads)
- [ ] Local admin rights available (recommended)

### Verify GPU Compatibility
```powershell
# Check installed GPU
wmic path win32_videocontroller get name

# Check VRAM
wmic path win32_videocontroller get AdapterRAM
```

### Update NVIDIA Driver
1. Visit: https://www.nvidia.com/Download/driverDetails.aspx
2. Select: GPU Type → Driver Type (Game Ready/Studio)
3. Download Windows 11 driver (R580.88 or later)
4. Uninstall old driver (Device Manager)
5. Install new driver with admin rights
6. Restart system

---

## INSTALLATION PROCEDURE

### Step 1: Create Installation Directory
```powershell
# Create target directory
mkdir C:\isaacsim
cd C:\isaacsim
```

### Step 2: Download Isaac Sim
1. Navigate to: https://docs.isaacsim.omniverse.nvidia.com/latest/installation/download.html
2. Select: **Isaac Sim for Windows**
3. Download latest stable version (currently v5.1.0 recommended)
4. Save to: `C:\Users\YourUsername\Downloads\`

### Step 3: Extract Archive
```powershell
# In C:\isaacsim directory
tar -xvzf "$env:USERPROFILE\Downloads\isaac-sim-2024.X.X-windows-x86_64.zip" -C C:\isaacsim
# OR use Windows Explorer: Right-click → Extract All
```

### Step 4: Post-Installation Setup
```batch
# In C:\isaacsim folder
cd C:\isaacsim
post_install.bat
# Wait for completion (creates symlinks to examples)
```

### Step 5: Run Application Selector
```batch
# In C:\isaacsim folder
isaac-sim.selector.bat
# Window opens - DO NOT CLOSE
```

### Step 6: Select & Launch Isaac Sim
- **Application Selector Window:**
  - Dropdown: Select "Isaac Sim Full"
  - Click: **START**
  - Wait 5-10 minutes (first launch compiles shaders)

### Step 7: Complete Login (If Prompted)
- Omniverse login may appear
- Use NVIDIA Account or create new
- Hub/Nucleus setup optional (skip if unsure)

---

## POST-INSTALLATION VERIFICATION

- [ ] Isaac Sim main window opened successfully
- [ ] 3D viewport visible and responsive
- [ ] No error dialogs in console
- [ ] File menu accessible (File → New, Open, etc.)

### Test Installation
```
Menu: Window → Script Editor
```
If Script Editor opens successfully → Replicator is ready

---

## REPLICATOR FIRST-RUN SETUP

### Access Replicator Development Environment
```
Menu: Window → Script Editor
(Python editor opens - this is your Replicator workspace)
```

### Create Output Directory
```powershell
# Create output directory for synthetic data
mkdir C:\omniverse_output
mkdir C:\omniverse_output\dataset_001
```

### Minimal Test Script
Paste into Script Editor and run:

```python
import omni.replicator.core as rep

# Create scene layer
with rep.new_layer():

    # Create camera
    camera = rep.create.camera(position=(0, 0, 100))
    render_product = rep.create.render_product(camera, (512, 512))

    # Create simple objects with labels
    rep.create.cube(position=(0, 0, 0), semantic_label="test_cube")
    rep.create.sphere(position=(50, 0, 0), semantic_label="test_sphere")

    # Define randomizer
    def randomize_pose():
        objects = rep.get.prims(semantics=[("class", "test_cube")])
        with objects:
            rep.modify.pose(
                position=rep.distribution.uniform((-50, -50, -50), (50, 50, 50)),
                rotation=rep.distribution.uniform((0, -180, 0), (0, 180, 0))
            )

    # Register randomizer
    rep.randomizer.register(randomize_pose)

    # Setup writer
    writer = rep.WriterRegistry.get("BasicWriter")
    writer.initialize(
        output_dir="C:/omniverse_output/dataset_001",
        rgb=True,
        bounding_box_2d_tight=True,
        semantic_segmentation=True
    )
    writer.attach([render_product])

    # Generate 10 frames
    rep.orchestrator.run()

print("Test generation complete! Check C:/omniverse_output/dataset_001/")
```

**Execute:**
- Script Editor → Menu: Replicator → Run
- OR: Right-click in editor → Execute

**Verify:**
- Check output directory for PNG files and JSON metadata
- If files appear → Installation successful!

---

## TROUBLESHOOTING QUICK-FIX TABLE

| Problem | Quick Fix |
|---------|-----------|
| Isaac Sim won't launch | Run as admin; check GPU driver (R580+); wait 10 min |
| "GPU not found" error | Verify RTX GPU installed; check NVIDIA Control Panel |
| Script Editor won't open | Restart Isaac Sim; check Extensions Manager |
| Output write errors | Create C:/omniverse_output; use absolute paths (not %USERPROFILE%) |
| Blank screen on startup | This is NORMAL; wait for shader compilation (5-10 min) |
| VRAM insufficient | Lower resolution (512x512 vs 1024x1024); check for background apps |
| Permission denied errors | Run as admin; check folder permissions on output dir |

---

## DEPENDENCY VERIFICATION

### Check Python Version
```powershell
# Isaac Sim 5.X requires Python 3.11
python --version
# Should show: Python 3.11.x
```

### Verify Extensions Installed
```
Menu: Extensions → Extension Manager
Search for:
  - replicator
  - syntheticdata
  - semantics
  - base
```
All should show as "Enabled" (green check)

---

## NEXT STEPS AFTER SUCCESSFUL INSTALLATION

1. **Explore Tutorial Scripts**
   - Path: `C:\isaacsim\scripts\`
   - Contains: BasicWriter, KITTI examples, domain randomization samples

2. **Read Official Docs**
   - Replicator Extension: https://docs.omniverse.nvidia.com/extensions/latest/ext_replicator.html
   - Getting Started: https://docs.omniverse.nvidia.com/extensions/latest/ext_replicator/getting_started.html

3. **Try Example Workflows**
   - Menu: Help → Tutorials
   - Select Replicator-related tutorials
   - Execute provided example scripts

4. **Setup Version Control**
   - Create GitHub repo for scripts
   - Version YAML configs and Python generation scripts
   - Track dataset metadata

5. **Plan Data Generation Pipeline**
   - Define output format (COCO, KITTI, Custom)
   - Plan asset library
   - Design randomization strategy

---

## SYSTEM OPTIMIZATION TIPS

### For Better Performance
1. **Close background apps** (Discord, Slack, browsers)
2. **Disable unnecessary Windows services**
3. **Use dedicated disk for output** (separate SSD if possible)
4. **Monitor GPU/CPU** during generation:
   ```powershell
   # Open Task Manager (Ctrl+Shift+Esc)
   # Monitor: GPU %, VRAM usage, CPU %
   ```

### For Batch Generation
1. Use YAML-based configurator (Replicator 1.10+)
2. Leverage Omniverse Farm for multi-GPU processing
3. Increase frame count incrementally (test 10 → 100 → 1000 frames)

### For Production Workflows
1. Use cloud deployment (AWS RTX instances)
2. Implement monitoring/logging in custom writers
3. Version output datasets with metadata
4. Validate synthetic-to-real transfer via ablation studies

---

## CRITICAL DEPRECATION NOTICE

**Omniverse Launcher** was deprecated October 1, 2025

- **OLD:** Download via Omniverse Launcher
- **NEW:** Download direct from:
  - GitHub: https://github.com/NVIDIA-Omniverse
  - NVIDIA NGC: https://catalog.ngc.nvidia.com/
  - Direct archives: https://docs.isaacsim.omniverse.nvidia.com/latest/installation/download.html

**Migration Path:**
```
Launcher (EOL) → Direct SDK Download + NGC Catalog + Container Deployment
```

---

## QUICK COMMAND REFERENCE

### Windows PowerShell Commands
```powershell
# Check system specs
Get-ComputerInfo -Property CsSystemType
wmic os get caption
wmic logicaldisk get name,freespace  # Free disk space

# Navigate to Isaac Sim
cd C:\isaacsim

# Run selector
.\isaac-sim.selector.bat

# Run with user reset (if config corrupt)
.\isaac-sim.selector.bat --reset-user
```

### Python Environment (Isaac Sim 5.X)
```bash
# Verify Python
python --version  # Must be 3.11.x

# Replicator is built-in; no pip install needed
# Access via: import omni.replicator.core as rep
```

### File Locations
```
Installation:     C:\isaacsim\
Examples:         C:\isaacsim\scripts\
Output Directory: C:\omniverse_output\
Logs:            C:\Users\{user}\AppData\Local\ov\
Config:          C:\Users\{user}\AppData\Local\ov\pkg\
```

---

## SUCCESS INDICATORS

✓ Checklist Complete if:
1. Isaac Sim launches and 3D viewport is responsive
2. Script Editor opens without errors
3. Test script generates PNG files + JSON metadata in output directory
4. No VRAM/memory errors during 10-frame generation
5. GPU utilization visible in Task Manager during generation

**Installation Successful!** → Ready for production workflows

---

**Last Updated:** 2026-01-10
**Tested On:** Windows 11 (21H2+) + Isaac Sim 5.1.0
**GPU Models:** RTX 3060 (12GB), RTX 4080 (16GB), RTX 4090 (24GB)
