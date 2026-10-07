# LoRA Batch Training Script
# Trains all 5 defect-specific LoRAs sequentially
# Pilot mode: train crack first, then rest

param(
    [switch]$PilotOnly,
    [switch]$SkipCrack
)

$ErrorActionPreference = "Stop"

# Paths
$KohyaRoot = "E:\The Data Mint\kohya-ss"
$VenvActivate = "$KohyaRoot\venv\Scripts\Activate.ps1"
$ComfyUILoraDir = "E:\ComfyUI_windows_portable\ComfyUI\models\loras"

# Training configs
$Configs = @(
    @{Name="crack"; Config="$KohyaRoot\configs\crack-lora-training-config.toml"; Output="$KohyaRoot\output\crack\xray_crack_lora_r32.safetensors"},
    @{Name="porosity"; Config="$KohyaRoot\configs\porosity-lora-training-config.toml"; Output="$KohyaRoot\output\porosity\xray_porosity_lora_r32.safetensors"},
    @{Name="inclusion"; Config="$KohyaRoot\configs\inclusion-lora-training-config.toml"; Output="$KohyaRoot\output\inclusion\xray_inclusion_lora_r32.safetensors"},
    @{Name="lack_of_fusion"; Config="$KohyaRoot\configs\lack-of-fusion-lora-training-config.toml"; Output="$KohyaRoot\output\lack_of_fusion\xray_lack_of_fusion_lora_r32.safetensors"},
    @{Name="undercut"; Config="$KohyaRoot\configs\undercut-lora-training-config.toml"; Output="$KohyaRoot\output\undercut\xray_undercut_lora_r32.safetensors"}
)

# Filter based on flags
if ($PilotOnly) {
    $Configs = $Configs | Where-Object { $_.Name -eq "crack" }
    Write-Host "`n[PILOT MODE] Training crack LoRA only`n" -ForegroundColor Yellow
}
elseif ($SkipCrack) {
    $Configs = $Configs | Where-Object { $_.Name -ne "crack" }
    Write-Host "`n[SKIP CRACK] Training remaining 4 LoRAs`n" -ForegroundColor Yellow
}

# Activate venv
Write-Host "`n=== Activating kohya-ss venv ===" -ForegroundColor Cyan
if (-not (Test-Path $VenvActivate)) {
    Write-Error "venv not found at $VenvActivate. Run setup-kohya-venv.ps1 first."
}
& $VenvActivate

# Create output directories
Write-Host "`n=== Creating output directories ===" -ForegroundColor Cyan
foreach ($cfg in $Configs) {
    $outDir = Split-Path $cfg.Output
    if (-not (Test-Path $outDir)) {
        New-Item -ItemType Directory -Path $outDir -Force | Out-Null
        Write-Host "Created: $outDir" -ForegroundColor Green
    }
}

# Train each LoRA
$StartTime = Get-Date
$SuccessCount = 0
$FailedConfigs = @()

foreach ($cfg in $Configs) {
    Write-Host "`n========================================" -ForegroundColor Magenta
    Write-Host "Training: $($cfg.Name) LoRA" -ForegroundColor Magenta
    Write-Host "Config: $($cfg.Config)" -ForegroundColor Magenta
    Write-Host "========================================`n" -ForegroundColor Magenta

    $TrainStartTime = Get-Date

    try {
        # Run training
        accelerate launch --num_cpu_threads_per_process=8 `
            "$KohyaRoot\sd-scripts\train_network.py" `
            --config_file="$($cfg.Config)"

        if ($LASTEXITCODE -ne 0) {
            throw "Training failed with exit code $LASTEXITCODE"
        }

        # Verify output file exists
        if (-not (Test-Path $cfg.Output)) {
            throw "Output file not found: $($cfg.Output)"
        }

        # Copy to ComfyUI
        Write-Host "`n[SUCCESS] Copying LoRA to ComfyUI..." -ForegroundColor Green
        Copy-Item -Path $cfg.Output -Destination $ComfyUILoraDir -Force

        $TrainDuration = (Get-Date) - $TrainStartTime
        Write-Host "[SUCCESS] $($cfg.Name) LoRA trained in $($TrainDuration.ToString('hh\:mm\:ss'))" -ForegroundColor Green
        $SuccessCount++

    } catch {
        Write-Host "`n[FAILED] $($cfg.Name) LoRA training failed: $_" -ForegroundColor Red
        $FailedConfigs += $cfg.Name
    }
}

# Summary
$TotalDuration = (Get-Date) - $StartTime
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "TRAINING SUMMARY" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Total time: $($TotalDuration.ToString('hh\:mm\:ss'))" -ForegroundColor White
Write-Host "Successful: $SuccessCount / $($Configs.Count)" -ForegroundColor White

if ($FailedConfigs.Count -gt 0) {
    Write-Host "Failed: $($FailedConfigs -join ', ')" -ForegroundColor Red
} else {
    Write-Host "All LoRAs trained successfully!" -ForegroundColor Green
}

# List output files
Write-Host "`n=== Output LoRAs ===" -ForegroundColor Cyan
Get-ChildItem -Path "$KohyaRoot\output" -Filter "*.safetensors" -Recurse | ForEach-Object {
    $sizeKB = [math]::Round($_.Length / 1KB, 2)
    Write-Host "$($_.Name) - $sizeKB KB" -ForegroundColor White
}

Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "1. Review TensorBoard logs: tensorboard --logdir='$KohyaRoot\logs'" -ForegroundColor White
Write-Host "2. Test LoRAs in ComfyUI: Load from $ComfyUILoraDir" -ForegroundColor White
Write-Host "3. Generate test images using trigger words (xray_crack, xray_porosity, etc.)" -ForegroundColor White
