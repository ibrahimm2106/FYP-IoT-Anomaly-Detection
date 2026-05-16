param(
    [string]$OutputPath = "IoT_Autoencoder_Viva.pptx"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$outFile = Join-Path $root $OutputPath

$ppLayoutBlank = 12
$ppSaveAsOpenXMLPresentation = 24
$msoFalse = 0
$msoTrue = -1
$msoTextOrientationHorizontal = 1
$msoShapeRectangle = 1
$msoShapeRoundedRectangle = 5
$msoLine = 9
$msoConnectorStraight = 1
$msoAnchorTop = 1
$msoAutoSizeNone = 0
$msoArrowheadTriangle = 3

function Add-TextBox {
    param(
        $Slide,
        [double]$Left,
        [double]$Top,
        [double]$Width,
        [double]$Height,
        [string[]]$Lines,
        [int]$FontSize = 20,
        [string]$Color = "172033",
        [bool]$Bold = $false,
        [string]$Fill = "",
        [string]$Line = "",
        [bool]$Bullets = $false
    )
    $shape = $Slide.Shapes.AddTextbox($msoTextOrientationHorizontal, $Left, $Top, $Width, $Height)
    $shape.TextFrame2.MarginLeft = 8
    $shape.TextFrame2.MarginRight = 8
    $shape.TextFrame2.MarginTop = 5
    $shape.TextFrame2.MarginBottom = 5
    $shape.TextFrame2.AutoSize = $msoAutoSizeNone
    $shape.TextFrame2.VerticalAnchor = $msoAnchorTop
    $shape.TextFrame2.TextRange.Text = ($Lines -join "`r")
    $shape.TextFrame2.TextRange.Font.Name = "Aptos"
    $shape.TextFrame2.TextRange.Font.Size = $FontSize
    $shape.TextFrame2.TextRange.Font.Fill.ForeColor.RGB = Convert-HexColor $Color
    $shape.TextFrame2.TextRange.Font.Bold = if ($Bold) { $msoTrue } else { $msoFalse }
    if ($Bullets) {
        foreach ($para in $shape.TextFrame2.TextRange.Paragraphs()) {
            $para.ParagraphFormat.Bullet.Visible = $msoTrue
            $para.ParagraphFormat.FirstLineIndent = -14
            $para.ParagraphFormat.LeftIndent = 20
        }
    }
    if ($Fill) {
        $shape.Fill.Visible = $msoTrue
        $shape.Fill.ForeColor.RGB = Convert-HexColor $Fill
    } else {
        $shape.Fill.Visible = $msoFalse
    }
    if ($Line) {
        $shape.Line.Visible = $msoTrue
        $shape.Line.ForeColor.RGB = Convert-HexColor $Line
        $shape.Line.Weight = 1
    } else {
        $shape.Line.Visible = $msoFalse
    }
    return $shape
}

function Add-Box {
    param(
        $Slide,
        [double]$Left,
        [double]$Top,
        [double]$Width,
        [double]$Height,
        [string[]]$Lines,
        [string]$Fill = "FFFFFF",
        [string]$Line = "B8C4D6",
        [string]$TextColor = "172033",
        [int]$FontSize = 16,
        [bool]$Bold = $false
    )
    $shape = $Slide.Shapes.AddShape($msoShapeRoundedRectangle, $Left, $Top, $Width, $Height)
    $shape.Fill.ForeColor.RGB = Convert-HexColor $Fill
    $shape.Line.ForeColor.RGB = Convert-HexColor $Line
    $shape.Line.Weight = 1
    $shape.TextFrame2.MarginLeft = 8
    $shape.TextFrame2.MarginRight = 8
    $shape.TextFrame2.MarginTop = 6
    $shape.TextFrame2.MarginBottom = 6
    $shape.TextFrame2.TextRange.Text = ($Lines -join "`r")
    $shape.TextFrame2.TextRange.Font.Name = "Aptos"
    $shape.TextFrame2.TextRange.Font.Size = $FontSize
    $shape.TextFrame2.TextRange.Font.Fill.ForeColor.RGB = Convert-HexColor $TextColor
    $shape.TextFrame2.TextRange.Font.Bold = if ($Bold) { $msoTrue } else { $msoFalse }
    return $shape
}

function Convert-HexColor {
    param([string]$Hex)
    $h = $Hex.TrimStart("#")
    $r = [Convert]::ToInt32($h.Substring(0,2),16)
    $g = [Convert]::ToInt32($h.Substring(2,2),16)
    $b = [Convert]::ToInt32($h.Substring(4,2),16)
    return $r + ($g * 256) + ($b * 65536)
}

function Add-Header {
    param($Slide, [string]$Title)
    $bg = $Slide.Shapes.AddShape($msoShapeRectangle, 0, 0, 960, 540)
    $bg.Fill.ForeColor.RGB = Convert-HexColor "F7F9FC"
    $bg.Line.Visible = $msoFalse
    $bg.ZOrder(1) | Out-Null
    $bar = $Slide.Shapes.AddShape($msoShapeRectangle, 0, 0, 960, 17)
    $bar.Fill.ForeColor.RGB = Convert-HexColor "17324D"
    $bar.Line.Visible = $msoFalse
    Add-TextBox $Slide 40 30 850 38 @($Title) 25 "17324D" $true | Out-Null
    $line = $Slide.Shapes.AddShape($msoShapeRectangle, 40, 76, 880, 1.4)
    $line.Fill.ForeColor.RGB = Convert-HexColor "B8C4D6"
    $line.Line.Visible = $msoFalse
}

function Add-Slide {
    param($Presentation, [string]$Title)
    $slide = $Presentation.Slides.Add($Presentation.Slides.Count + 1, $ppLayoutBlank)
    Add-Header $slide $Title
    return $slide
}

function Add-Arrow {
    param($Slide, [double]$X1, [double]$Y1, [double]$X2, [double]$Y2)
    $line = $Slide.Shapes.AddConnector($msoConnectorStraight, $X1, $Y1, $X2, $Y2)
    $line.Line.ForeColor.RGB = Convert-HexColor "5B6B7F"
    $line.Line.Weight = 2
    $line.Line.EndArrowheadStyle = $msoArrowheadTriangle
}

$ppt = $null
$pres = $null
$primaryError = $null
try {
    $ppt = New-Object -ComObject PowerPoint.Application
    $ppt.Visible = $msoTrue
    $pres = $ppt.Presentations.Add($msoTrue)
    $pres.PageSetup.SlideWidth = 960
    $pres.PageSetup.SlideHeight = 540

    $s = Add-Slide $pres "Title & Overview"
    Add-TextBox $s 55 105 840 78 @("An Interactive IoT Network Anomaly Detection System Using Deep Autoencoders") 30 "172033" $true | Out-Null
    Add-TextBox $s 62 200 460 90 @("BSc Software Engineering final-year viva","Student: <Your Name>","Supervisor: <Supervisor Name>") 18 "334155" | Out-Null
    Add-Box $s 62 305 760 68 @("One-sentence summary: a benign-trained autoencoder scores IoT-23 network flows and presents anomalies through an interactive Streamlit dashboard.") "FFFFFF" "D6DEE8" "172033" 17 | Out-Null
    Add-TextBox $s 62 410 760 35 @("Python  |  TensorFlow/Keras  |  scikit-learn  |  Streamlit") 18 "17324D" $true | Out-Null

    $s = Add-Slide $pres "Problem & Motivation"
    Add-TextBox $s 60 105 470 260 @("IoT devices are often resource-constrained and inconsistently secured","Mirai-style botnets show how weak IoT devices can be weaponised","Network behaviour is heterogeneous across device types and services","New attacks may appear before high-quality labels are available") 20 "172033" $false "" "" $true | Out-Null
    Add-Box $s 570 115 300 55 @("Core challenge") "17324D" "17324D" "FFFFFF" 24 $true | Out-Null
    Add-Box $s 570 195 300 125 @("Detect suspicious network flows when complete labelled attack data is limited or unavailable.") "FFFFFF" "D6DEE8" "172033" 23 $true | Out-Null
    Add-Box $s 570 360 300 68 @("Unsupervised anomaly detection models normal behaviour first.") "EAF0F7" "D6DEE8" "334155" 17 | Out-Null

    $s = Add-Slide $pres "Aim & Objectives"
    Add-Box $s 60 110 830 72 @("Aim: design and evaluate an interactive system for detecting anomalous IoT network flows using a deep autoencoder trained on benign traffic.") "FFFFFF" "D6DEE8" "172033" 19 $true | Out-Null
    Add-TextBox $s 75 215 790 230 @("Preprocess IoT-23 Zeek flow logs into a model-ready tabular dataset","Train an unsupervised autoencoder on benign flows and derive an MSE threshold","Implement an Isolation Forest baseline for comparison","Evaluate detection with precision, recall, F1-score and PR-AUC","Build a Streamlit dashboard for threshold exploration and anomaly inspection") 20 "172033" $false "" "" $true | Out-Null

    $s = Add-Slide $pres "Dataset & Features (IoT-23)"
    Add-TextBox $s 60 105 420 250 @("Public IoT-23 / CTU-IoT-23 flow-level traffic dataset","Zeek conn.log.labeled style records from real IoT network scenarios","Suitable because it includes benign and malicious-labelled connection flows","Labels are used for evaluation, not for autoencoder training") 19 "172033" $false "" "" $true | Out-Null
    Add-TextBox $s 540 105 340 25 @("Visual space: feature/data snapshot") 16 "5B6B7F" $true | Out-Null
    Add-Box $s 540 145 350 250 @("Zeek flow features","proto, service, conn_state","duration, bytes, packets","history, tunnel fields","label, detailed-label","UID/IP columns dropped for generalisation") "FFFFFF" "B8C4D6" "172033" 17 | Out-Null

    $s = Add-Slide $pres "System Architecture & Models"
    Add-Box $s 55 105 140 54 @("IoT-23","Zeek flows") "FFFFFF" "AAB7C8" "172033" 14 $true | Out-Null
    Add-Arrow $s 198 132 255 132
    Add-Box $s 260 105 145 54 @("Preprocessing","scale + one-hot") "FFFFFF" "AAB7C8" "172033" 14 $true | Out-Null
    Add-Arrow $s 408 132 465 132
    Add-Box $s 470 85 150 48 @("Autoencoder","MSE score") "17324D" "17324D" "FFFFFF" 13 $true | Out-Null
    Add-Box $s 470 150 150 48 @("Isolation Forest","baseline") "EAF0F7" "AAB7C8" "17324D" 13 $true | Out-Null
    Add-Arrow $s 625 132 682 132
    Add-Box $s 690 105 180 54 @("Streamlit","dashboard") "FFFFFF" "AAB7C8" "172033" 14 $true | Out-Null
    Add-TextBox $s 60 245 420 185 @("Autoencoder reconstructs benign flow vectors","High reconstruction MSE indicates poor fit to benign behaviour","Threshold converts score into anomaly flag","Isolation Forest isolates sparse/outlying points as baseline") 18 "172033" $false "" "" $true | Out-Null
    Add-TextBox $s 540 245 350 150 @("Why unsupervised?","Practical attack labels may be incomplete","New IoT attacks can appear after deployment","Benign-only training supports anomaly discovery") 18 "172033" $false "" "" $true | Out-Null

    $s = Add-Slide $pres "Evaluation & Results"
    Add-TextBox $s 60 105 440 230 @("Stratified 70 / 15 / 15 train, validation and test split","Autoencoder trained on benign training flows only","Threshold calibrated from benign validation MSE","Held-out test set scored by autoencoder and Isolation Forest") 19 "172033" $false "" "" $true | Out-Null
    Add-Box $s 560 105 330 245 @("Results placeholders","Precision AE: <PRECISION_AE>","Recall AE: <RECALL_AE>","F1-score AE: <F1_AE>","PR-AUC AE: <PR_AUC_AE>","F1-score IF: <F1_IF>","PR-AUC IF: <PR_AUC_IF>") "FFFFFF" "D6DEE8" "172033" 18 | Out-Null
    Add-TextBox $s 560 380 330 45 @("Comparison focus: thresholded detection quality plus ranking quality from continuous anomaly scores.") 16 "334155" | Out-Null

    $s = Add-Slide $pres "Demo & Dashboard"
    Add-TextBox $s 60 105 390 190 @("Overview: rows scored, rows flagged and headline metrics","Reconstruction-error histogram with threshold line","Prepare Model: adjustable session threshold slider","Detection Results: ranked anomalous flow table","Export anomaly CSV / metrics evidence") 18 "172033" $false "" "" $true | Out-Null
    Add-TextBox $s 500 105 360 25 @("Visual space: dashboard screenshot") 16 "5B6B7F" $true | Out-Null
    Add-Box $s 500 145 360 150 @("Dashboard screenshot placeholder","Histogram  |  Threshold slider","Anomaly table  |  Metrics cards") "FFFFFF" "B8C4D6" "5B6B7F" 18 | Out-Null
    Add-Box $s 60 320 800 105 @("How to run the project","Command Prompt: cd C:\Users\User\Documents\iot-autoencoder-artifact","activate: .\.venv\Scripts\activate.bat","run app: python -m streamlit run app.py","optional tunnel: %LOCALAPPDATA%\Microsoft\WindowsApps\ngrok.exe http 8501") "FFFFFF" "D6DEE8" "172033" 14 | Out-Null
    Add-TextBox $s 70 445 780 35 @("Admin value: threshold control makes the false-positive / false-negative trade-off visible during investigation.") 17 "17324D" $true | Out-Null

    $s = Add-Slide $pres "Limitations, Ethics & Future Work"
    Add-TextBox $s 60 105 390 220 @("Batch CSV scoring, not live network capture","Results depend on IoT-23 scenario and selected threshold","Concept drift may change benign behaviour over time","Reconstruction MSE is not a calibrated attack probability","Public/anonymised benchmark data reduces privacy risk") 18 "172033" $false "" "" $true | Out-Null
    Add-Box $s 515 105 345 200 @("Future work","Integrate a controlled real-time Zeek ingestion pipeline","Evaluate on more IoT-23 scenarios and external datasets","Add adaptive thresholds and drift monitoring","Improve explainability and analyst feedback loops") "FFFFFF" "D6DEE8" "172033" 17 | Out-Null
    Add-Box $s 60 350 800 70 @("AUC - Area under the Curve","MSE - Mean Squared Error","PR - Precision Recall") "F7F9FC" "F7F9FC" "12203D" 23 $true | Out-Null
    Add-TextBox $s 70 445 780 35 @("Closing message: an end-to-end ML engineering pipeline with transparent evaluation and an examiner-facing dashboard.") 17 "17324D" $true | Out-Null

    if (Test-Path -LiteralPath $outFile) {
        Remove-Item -LiteralPath $outFile -Force
    }
    $pres.SaveAs($outFile, $ppSaveAsOpenXMLPresentation)
    Write-Output $outFile
}
catch {
    $primaryError = $_
    Write-Error $_
}
finally {
    if ($pres -ne $null) {
        try { $pres.Close() } catch { Write-Warning "PowerPoint presentation cleanup skipped: $($_.Exception.Message)" }
        try { [System.Runtime.InteropServices.Marshal]::ReleaseComObject($pres) | Out-Null } catch {}
    }
    if ($ppt -ne $null) {
        try { $ppt.Quit() } catch { Write-Warning "PowerPoint application cleanup skipped: $($_.Exception.Message)" }
        try { [System.Runtime.InteropServices.Marshal]::ReleaseComObject($ppt) | Out-Null } catch {}
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

if ($primaryError -ne $null) {
    exit 1
}
