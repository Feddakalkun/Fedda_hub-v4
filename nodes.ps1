# ============================================================
#  Fedda Hub v4 — ComfyUI Custom Nodes Manager
#  Run directly:  .\nodes.ps1
#  Or called from install.bat / update.bat
# ============================================================

param(
    [switch]$Update   # Pass -Update to pull latest instead of fresh clone
)

# ── ComfyUI root (change if yours is elsewhere) ─────────────────────────────
$ComfyRoot = "$env:USERPROFILE\ComfyUI"

# ── Node list — add new entries here ────────────────────────────────────────
#    Each entry: @{ Name = "folder-name"; Repo = "https://github.com/..."; Reqs = $true/$false }
$Nodes = @(
    @{
        Name = "ComfyUI-SadTalker"
        Repo = "https://github.com/AIFSH/ComfyUI-SadTalker"
        Reqs = $true
    }
    # Add more nodes below, e.g.:
    # @{ Name = "ComfyUI-VideoHelperSuite"; Repo = "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite"; Reqs = $true }
    # @{ Name = "comfyui_controlnet_aux";   Repo = "https://github.com/Fannovel16/comfyui_controlnet_aux";   Reqs = $true }
    # @{ Name = "ComfyUI-Impact-Pack";      Repo = "https://github.com/ltdrdata/ComfyUI-Impact-Pack";        Reqs = $true }
)

# ── Guard: ComfyUI must exist ────────────────────────────────────────────────
if (-not (Test-Path $ComfyRoot)) {
    Write-Host ""
    Write-Host "  WARNING: ComfyUI not found at $ComfyRoot" -ForegroundColor Yellow
    Write-Host "  Skipping custom node installation." -ForegroundColor Yellow
    Write-Host "  Install ComfyUI first, then re-run this script." -ForegroundColor Yellow
    Write-Host ""
    exit 0
}

$NodesDir = "$ComfyRoot\custom_nodes"
if (-not (Test-Path $NodesDir)) {
    New-Item -ItemType Directory -Path $NodesDir | Out-Null
}

Write-Host ""
Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host "   ComfyUI Custom Nodes — $($Update ? 'Update' : 'Install')" -ForegroundColor Cyan
Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host "  ComfyUI path: $ComfyRoot" -ForegroundColor DarkGray
Write-Host ""

$ok = 0
$skipped = 0
$failed = 0

foreach ($node in $Nodes) {
    $target = "$NodesDir\$($node.Name)"
    Write-Host "  [$($node.Name)]" -ForegroundColor White -NoNewline

    # ── Clone or update ──────────────────────────────────────────────────────
    if (-not (Test-Path $target)) {
        Write-Host " cloning..." -ForegroundColor DarkGray
        git clone --depth 1 $node.Repo $target 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "    ERROR: git clone failed" -ForegroundColor Red
            $failed++
            continue
        }
    } elseif ($Update) {
        Write-Host " updating..." -ForegroundColor DarkGray
        Push-Location $target
        git pull 2>&1 | Out-Null
        Pop-Location
    } else {
        Write-Host " already installed, skipping." -ForegroundColor DarkGray
        $skipped++
        continue
    }

    # ── Install requirements if present ─────────────────────────────────────
    if ($node.Reqs) {
        $reqFile = "$target\requirements.txt"
        if (Test-Path $reqFile) {
            Write-Host "    Installing requirements..." -ForegroundColor DarkGray
            pip install -r $reqFile --quiet
            if ($LASTEXITCODE -ne 0) {
                Write-Host "    WARNING: some requirements failed to install" -ForegroundColor Yellow
            }
        }
    }

    Write-Host "    OK" -ForegroundColor Green
    $ok++
}

Write-Host ""
Write-Host "  Done: $ok installed, $skipped skipped, $failed failed." -ForegroundColor Cyan
Write-Host ""
